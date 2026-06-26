# -*- coding: utf-8 -*-
"""Multi-source resolver coordinator.

Three modes (controlled by user settings):

1. **Sequential** (default) — primary first; on failure walk
   ``_AUTO_FALLBACK_HOSTS`` one at a time until one returns streams.
2. **Multi-link aggregation** — set ``aggregate_all_sources = true``.
   Runs the primary plus every secondary host **concurrently** in a thread
   pool, then merges all results into a single deduped candidate pool.
3. **User-toggled secondary** — original behaviour where the user picks a
   single secondary host in settings (kept for back-compat).

v1.4.9 — fixed the v1.4.8 regression where ``_run_secondary`` overrode
``secondary_source_host`` on a fresh ``xbmcaddon.Addon()`` instance, but
the secondary resolver read from the module-level ``common.ADDON``
singleton — meaning the override was invisible. The host is now passed as
an explicit parameter to ``vidsrc2.resolve_all``.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

from .common import get_setting_bool, get_setting_int, log
from . import vidsrc as V1
from . import vidsrc2 as V2
from . import stigstream as STIG
from . import vidnest as VN
from . import filehosts as FH
from . import extras as EX

try:
    import xbmcgui as _xbmcgui
except Exception:  # standalone testing
    _xbmcgui = None

# Order matters — most reliable mirrors first. v1.4.9: dropped DNS-dead
# embed.su / autoembed.cc / smashystream.com hosts and the broken JSON-API
# endpoints (vidsrc.icu / vidlink.pro / vidjoy.pro public APIs return 404).
# vidsrc.icu kept because its embed page wraps a real iframe we can chase.
_AUTO_FALLBACK_HOSTS = (
    'vidsrc.xyz',
    'vidsrc.to',
    'vidsrc.net',
    'vidsrc.icu',
    'multiembed.mov',
    'moviesapi.club',
    '2embed.cc',
)


def _run_stigstream(media_type, tmdb_id, season, episode, tracker=None):
    """Run the stigstream resolver — completely independent of the cloudnestra
    chain, queries its own AES/ChaCha-encrypted JSON API and returns multiple
    HLS streams across 8+ regional servers."""
    if not get_setting_bool('enable_stigstream', True):
        return []
    try:
        streams = STIG.resolve_streams(media_type, tmdb_id,
                                       season=season, episode=episode) or []
    except Exception as e:
        log('sources: stigstream failed %s' % e)
        if tracker:
            tracker.update('stigstream', 0, done=True)
        return []
    for s in streams:
        s.setdefault('provider', 'stigstream')
        s.setdefault('host_origin', 'stigstream.ru')
    if tracker:
        tracker.update('stigstream', len(streams), done=True)
    return streams


def _run_vidnest(media_type, tmdb_id, season, episode, tracker=None):
    """Run the vidnest.fun multi-backend resolver. Talks to 7 providers
    (MoviesAPI, PurStream, AllMovies, CatFlix, HollyMovieHD, FlixHQ, VidLink)
    in parallel via the new.vidnest.fun JSON envelope API and decodes the
    custom-Base64 cipher embedded in their site bundle."""
    if not get_setting_bool('enable_vidnest', True):
        return []

    # Per-provider callback funnels into the live progress dialog as a sub-row.
    def _cb(prov_key, count):
        if tracker:
            label = VN.PROVIDER_LABELS.get(prov_key, prov_key)
            tracker.add_sub('vidnest', label, count)

    try:
        streams = VN.resolve_streams(media_type, tmdb_id,
                                     season=season, episode=episode,
                                     progress_cb=_cb) or []
    except Exception as e:
        log('sources: vidnest failed %s' % e)
        return []
    for s in streams:
        s.setdefault('provider', 'vidnest')
        s.setdefault('host_origin', 'vidnest.fun')
    if tracker:
        # Final consolidation in case some providers errored before reporting.
        tracker.update('vidnest', len(streams), done=True, label='Vidnest')
    return streams


def _run_secondary(media_type, tmdb_id, season, episode, imdb_id, host=None):
    """Run vidsrc2.resolve_all, optionally pinning a specific host."""
    try:
        streams = V2.resolve_all(media_type, tmdb_id,
                                 season=season, episode=episode,
                                 imdb_id=imdb_id, host=host) or []
    except Exception as e:
        log('sources: secondary [%s] failed %s' % (host or 'user', e))
        streams = []
    for s in streams:
        s.setdefault('provider', 'secondary')
        s.setdefault('host_origin', host or 'user')
    return streams


def _run_filehosts(media_type, tmdb_id, imdb_id, title, year,
                   season, episode, tracker=None):
    """Run the file-host aggregator (4th independent source).

    This is intentionally a separate top-level worker — its streams are
    marked ``needs_resolveurl=True`` and sorted to the BOTTOM of the
    picker. The cloudnestra / stigstream / vidnest paths are completely
    untouched; failures here cannot affect existing playable streams.
    """
    if not get_setting_bool('enable_filehost_sources', True):
        log('sources: filehost source disabled by setting')
        return []
    log('sources: filehost START tmdb=%s imdb=%s title=%r year=%s'
        % (tmdb_id, imdb_id, title, year))

    def _cb(site_name, count):
        if tracker:
            tracker.add_sub('filehosts', site_name, count)

    try:
        streams = FH.resolve_streams(media_type, tmdb_id,
                                     imdb_id=imdb_id, title=title,
                                     year=year, season=season,
                                     episode=episode,
                                     progress_cb=_cb) or []
    except Exception as e:
        log('sources: filehost FAILED %s' % e)
        return []
    log('sources: filehost END -> %d candidates' % len(streams))
    if tracker:
        tracker.update('filehosts', len(streams), done=True,
                       label='File hosts')
    return streams


def _run_extras(media_type, tmdb_id, imdb_id, title, year, season, episode,
                tracker=None):
    """Run the community-indexer aggregator (6th independent tier).

    Same isolation contract as the file-host source: separate worker,
    streams tagged ``needs_resolveurl=True`` (or ``proto='DIRECT'`` for
    the rare direct-MP4 hit) and ``sort_weight=999`` so they always sit
    at the bottom of the picker. Existing direct-stream tiers are NEVER
    touched."""
    if not get_setting_bool('enable_extra_sources', True):
        log('sources: extras disabled by setting')
        return []
    log('sources: extras START tmdb=%s imdb=%s title=%r year=%s'
        % (tmdb_id, imdb_id, title, year))

    def _cb(site_name, count):
        if tracker:
            tracker.add_sub('extras', site_name, count)

    try:
        streams = EX.resolve_streams(media_type, tmdb_id,
                                     imdb_id=imdb_id, title=title,
                                     year=year, season=season,
                                     episode=episode,
                                     progress_cb=_cb) or []
    except Exception as e:
        log('sources: extras FAILED %s' % e)
        return []
    log('sources: extras END -> %d candidates' % len(streams))
    if tracker:
        tracker.update('extras', len(streams), done=True, label='Extras')
    return streams


def _dedupe(streams):
    """Merge streams from multiple hosts, keeping the first occurrence of
    each unique URL."""
    seen = set()
    out = []
    for s in streams:
        u = s.get('url')
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(s)
    return out


def _aggregate_all(media_type, tmdb_id, season, episode, imdb_id):
    """Multi-link mode: query every secondary host concurrently and merge
    all returned streams into a single pool."""
    workers = max(get_setting_int('aggregate_workers', 5), 2)
    log('sources: aggregating %d hosts in parallel (workers=%d)'
        % (len(_AUTO_FALLBACK_HOSTS), workers))
    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(_run_secondary, media_type, tmdb_id, season, episode,
                      imdb_id, host): host
            for host in _AUTO_FALLBACK_HOSTS
        }
        for fut in as_completed(futures, timeout=30):
            host = futures[fut]
            try:
                streams = fut.result(timeout=1) or []
            except Exception as e:
                log('sources: aggregate [%s] error %s' % (host, e))
                continue
            if streams:
                log('sources: aggregate [%s] returned %d streams' % (host, len(streams)))
                for s in streams:
                    s['provider'] = 'aggregate'
                    s.setdefault('host_origin', host)
                out.extend(streams)
    return out


# ---------------------------------------------------------------------------
# Per-source progress dialog
# ---------------------------------------------------------------------------

class _ProgressTracker(object):
    """Live background progress dialog showing each top-level source's stream
    count. Vidnest is a single top-level row whose subline summarises the
    per-provider tally as backends complete.

    Layout (DialogProgressBG has one header line + one message line, each
    capped to about ~60 chars on most skins, so we keep things compact):

        header:  ``9 streams across 3 sources``
        msg:     ``✓ Cloudnestra: 0 · ⋯ Stigstream · ✓ Vidnest: 9 (4/7)``
    """

    _ICONS = {True: u'\u2713', False: u'\u22ef'}  # ✓ / ⋯

    def __init__(self, title='Vidscr — Searching'):
        self._title = title
        self._dlg = None
        self._rows = []  # ordered top-level keys
        self._state = {}  # key -> {'count':int,'done':bool,'label':str,'sub':dict}
        self._closed = False
        if _xbmcgui is None:
            return
        try:
            self._dlg = _xbmcgui.DialogProgressBG()
            self._dlg.create(self._title, 'Querying sources...')
        except Exception as e:
            log('sources: progress dialog create failed %s' % e)
            self._dlg = None

    def announce(self, key, label=None, sub_keys=None):
        """Mark a top-level source as 'searching'. ``sub_keys`` is an optional
        list of sub-provider keys (e.g. vidnest backends) — used so
        ``X/N`` style counters can render even before any sub completes."""
        if self._closed or self._dlg is None:
            return
        if key not in self._rows:
            self._rows.append(key)
        st = self._state.setdefault(key, {'count': 0, 'done': False,
                                          'label': label or key, 'sub': {}})
        if label:
            st['label'] = label
        if sub_keys:
            for sk in sub_keys:
                st['sub'].setdefault(sk, None)  # None = pending
        self._render()

    def update(self, key, count, done=True, label=None, sub=None):
        """Update a top-level row, optionally recording a sub-provider entry.

        Pass ``sub=(sub_key, sub_count)`` to record per-sub-provider tallies;
        the top-level ``count`` should be the running total across all subs."""
        if self._closed or self._dlg is None:
            return
        if key not in self._rows:
            self._rows.append(key)
        st = self._state.setdefault(key, {'count': 0, 'done': False,
                                          'label': label or key, 'sub': {}})
        st['count'] = int(count)
        st['done'] = bool(done)
        if label:
            st['label'] = label
        if sub:
            sk, sc = sub
            st['sub'][sk] = int(sc)
        self._render()

    def add_sub(self, key, sub_key, sub_count):
        """Convenience: bump a sub-provider count and recompute total."""
        if self._closed or self._dlg is None:
            return
        st = self._state.setdefault(key, {'count': 0, 'done': False,
                                          'label': key, 'sub': {}})
        st['sub'][sub_key] = int(sub_count)
        st['count'] = sum(v for v in st['sub'].values() if isinstance(v, int))
        # All subs reported -> done.
        st['done'] = all(isinstance(v, int) for v in st['sub'].values())
        self._render()

    def _render(self):
        if self._dlg is None:
            return
        total = sum(s['count'] for s in self._state.values())
        sources_with = sum(1 for s in self._state.values() if s['count'] > 0)
        # Build the per-row mini-status
        chips = []
        for k in self._rows:
            st = self._state[k]
            mark = self._ICONS[st['done']]
            if st['sub']:
                done_n = sum(1 for v in st['sub'].values() if isinstance(v, int))
                tot_n = len(st['sub'])
                chips.append('%s %s: %d (%d/%d)' % (
                    mark, st['label'], st['count'], done_n, tot_n))
            else:
                chips.append('%s %s: %d' % (mark, st['label'], st['count']))
        msg = ' \u00b7 '.join(chips) if chips else 'Querying sources...'
        try:
            done_top = sum(1 for s in self._state.values() if s['done'])
            pct = min(99, int(100 * done_top / max(len(self._rows), 1)))
            head = '%d streams across %d source%s' % (
                total, sources_with, '' if sources_with == 1 else 's')
            self._dlg.update(pct, head, msg)
        except Exception:
            pass

    def close(self):
        if self._closed or self._dlg is None:
            return
        self._closed = True
        try:
            self._dlg.update(100, 'Done', 'Loading player...')
            self._dlg.close()
        except Exception:
            pass


def _make_tracker():
    if get_setting_bool('show_search_progress', True):
        return _ProgressTracker()
    return None


def resolve(media_type, tmdb_id, season=None, episode=None, imdb_id=None,
            force_provider=None, title=None, year=None):
    """Returns (primary_streams, secondary_streams).

    ``title`` and ``year`` are NEW (1.4.20) optional kwargs used only by
    the file-host source — they're needed because moviesfree.cv & co
    search by string, not TMDB ID. Existing callers that don't pass
    them are unaffected: the file-host source quietly returns [] when
    title is missing, and Cloudnestra / Stigstream / Vidnest don't care.
    """
    secondary_enabled = get_setting_bool('enable_secondary_source', False)
    auto_secondary = get_setting_bool('auto_secondary_on_404', True)
    aggregate_mode = get_setting_bool('aggregate_all_sources', False)
    vidnest_enabled = (get_setting_bool('enable_vidnest', True)
                       and force_provider is None)
    filehosts_enabled = (get_setting_bool('enable_filehost_sources', True)
                         and force_provider is None
                         and bool(title))
    extras_enabled = (get_setting_bool('enable_extra_sources', True)
                      and force_provider is None
                      and bool(title))

    primary, secondary = [], []
    use_primary = force_provider in (None, 'primary')
    use_secondary = secondary_enabled and force_provider in (None, 'secondary')

    tracker = _make_tracker()
    # Pre-announce expected sources so the user sees rows immediately.
    if tracker:
        if use_primary:
            tracker.announce('primary', 'Cloudnestra')
        if use_secondary:
            tracker.announce('secondary', 'Secondary')
        if force_provider is None and get_setting_bool('enable_stigstream', True):
            tracker.announce('stigstream', 'Stigstream')
        if vidnest_enabled:
            tracker.announce('vidnest', 'Vidnest',
                             sub_keys=list(VN.PROVIDER_LABELS.values()))
        if filehosts_enabled:
            fh_subs = [pretty for pretty, _ in FH.SCRAPERS]
            tracker.announce('filehosts', 'File hosts', sub_keys=fh_subs)
        if extras_enabled:
            ex_subs = [n for n, _ in EX.PROVIDERS]
            tracker.announce('extras', 'Extras', sub_keys=ex_subs)

    try:
        # Multi-link aggregation overrides the sequential flow entirely.
        if aggregate_mode and force_provider is None:
            log('sources: multi-link aggregation mode')
            with ThreadPoolExecutor(max_workers=4) as ex:
                f_primary = ex.submit(_resolve_primary, media_type, tmdb_id,
                                      season, episode, imdb_id)
                f_secondary = ex.submit(_aggregate_all, media_type, tmdb_id,
                                        season, episode, imdb_id)
                f_stig = ex.submit(_run_stigstream, media_type, tmdb_id,
                                   season, episode, tracker)
                f_vn = (ex.submit(_run_vidnest, media_type, tmdb_id, season,
                                  episode, tracker)
                        if vidnest_enabled else None)
                try:
                    primary = f_primary.result(timeout=30) or []
                except Exception as e:
                    log('sources: primary in aggregate mode failed %s' % e)
                    primary = []
                if tracker:
                    tracker.update('primary', len(primary), done=True,
                                   label='Cloudnestra')
                try:
                    secondary = f_secondary.result(timeout=35) or []
                except Exception as e:
                    log('sources: aggregate failed %s' % e)
                    secondary = []
                if tracker:
                    tracker.update('secondary', len(secondary), done=True,
                                   label='Secondary')
                try:
                    stig = f_stig.result(timeout=30) or []
                    if stig:
                        log('sources: stigstream contributed %d streams' % len(stig))
                        secondary.extend(stig)
                except Exception as e:
                    log('sources: stigstream in aggregate mode failed %s' % e)
                if f_vn is not None:
                    try:
                        vn = f_vn.result(timeout=30) or []
                        if vn:
                            log('sources: vidnest contributed %d streams' % len(vn))
                            secondary.extend(vn)
                    except Exception as e:
                        log('sources: vidnest in aggregate mode failed %s' % e)
                if filehosts_enabled:
                    try:
                        fh_streams = _run_filehosts(media_type, tmdb_id, imdb_id,
                                                    title, year, season,
                                                    episode, tracker)
                        if fh_streams:
                            log('sources: filehosts contributed %d candidates'
                                % len(fh_streams))
                            secondary.extend(fh_streams)
                    except Exception as e:
                        log('sources: filehost in aggregate mode failed %s' % e)
                if extras_enabled:
                    try:
                        ex_streams = _run_extras(media_type, tmdb_id, imdb_id,
                                                 title, year, season, episode,
                                                 tracker)
                        if ex_streams:
                            log('sources: extras contributed %d candidates'
                                % len(ex_streams))
                            secondary.extend(ex_streams)
                    except Exception as e:
                        log('sources: extras in aggregate mode failed %s' % e)
            primary = _dedupe(primary)
            secondary = _dedupe(secondary)
            log('sources: aggregate result — %d primary + %d secondary candidates'
                % (len(primary), len(secondary)))
            return primary, secondary

        # ---- standard flow: primary + (optional secondary) + stig + vidnest
        # + filehosts + extras — all in parallel so the per-source dialog
        # updates live.
        with ThreadPoolExecutor(max_workers=6) as ex:
            f_primary = (ex.submit(_resolve_primary, media_type, tmdb_id,
                                   season, episode, imdb_id)
                         if use_primary else None)
            f_secondary = (ex.submit(_run_secondary, media_type, tmdb_id,
                                     season, episode, imdb_id, None)
                           if use_secondary else None)
            f_stig = (ex.submit(_run_stigstream, media_type, tmdb_id,
                                season, episode, tracker)
                      if force_provider is None
                      and get_setting_bool('enable_stigstream', True)
                      else None)
            f_vn = (ex.submit(_run_vidnest, media_type, tmdb_id, season,
                              episode, tracker)
                    if vidnest_enabled else None)
            f_fh = (ex.submit(_run_filehosts, media_type, tmdb_id, imdb_id,
                              title, year, season, episode, tracker)
                    if filehosts_enabled else None)
            f_ex = (ex.submit(_run_extras, media_type, tmdb_id, imdb_id,
                              title, year, season, episode, tracker)
                    if extras_enabled else None)

            if f_primary is not None:
                try:
                    primary = f_primary.result(timeout=30) or []
                except Exception as e:
                    log('sources: primary failed %s' % e)
                if tracker:
                    tracker.update('primary', len(primary), done=True,
                                   label='Cloudnestra')

            if f_secondary is not None:
                try:
                    secondary.extend(f_secondary.result(timeout=30) or [])
                except Exception as e:
                    log('sources: secondary failed %s' % e)
                if tracker:
                    tracker.update('secondary', len(secondary), done=True,
                                   label='Secondary')

            if f_stig is not None:
                try:
                    stig = f_stig.result(timeout=30) or []
                    if stig:
                        log('sources: stigstream contributed %d streams'
                            % len(stig))
                        secondary.extend(stig)
                except Exception as e:
                    log('sources: stigstream lookup failed %s' % e)

            if f_vn is not None:
                try:
                    vn = f_vn.result(timeout=30) or []
                    if vn:
                        log('sources: vidnest contributed %d streams'
                            % len(vn))
                        secondary.extend(vn)
                except Exception as e:
                    log('sources: vidnest lookup failed %s' % e)

            if f_fh is not None:
                try:
                    fh = f_fh.result(timeout=30) or []
                    if fh:
                        log('sources: filehosts contributed %d candidates'
                            % len(fh))
                        secondary.extend(fh)
                except Exception as e:
                    log('sources: filehost lookup failed %s' % e)

            if f_ex is not None:
                try:
                    exs = f_ex.result(timeout=30) or []
                    if exs:
                        log('sources: extras contributed %d candidates'
                            % len(exs))
                        secondary.extend(exs)
                except Exception as e:
                    log('sources: extras lookup failed %s' % e)

        # Auto last-resort fallback chain when nothing came back.
        if not primary and not secondary and auto_secondary \
                and force_provider in (None, 'primary'):
            log('sources: primary returned nothing — trying auto-fallback hosts')
            for host in _AUTO_FALLBACK_HOSTS:
                for ident_imdb, ident_tmdb in (
                    (imdb_id, None) if imdb_id else (None, tmdb_id),
                    (None, tmdb_id) if (imdb_id and tmdb_id and imdb_id != tmdb_id) else (None, None),
                ):
                    if not ident_imdb and not ident_tmdb:
                        continue
                    log('sources: auto-fallback -> %s (imdb=%s tmdb=%s)'
                        % (host, ident_imdb, ident_tmdb))
                    streams = _run_secondary(media_type, ident_tmdb or tmdb_id,
                                             season, episode,
                                             ident_imdb, host=host)
                    if streams:
                        for s in streams:
                            s['provider'] = 'auto-secondary'
                        secondary.extend(streams)
                        break
                if secondary:
                    break

        return primary, secondary
    finally:
        if tracker:
            tracker.close()


def _resolve_primary(media_type, tmdb_id, season, episode, imdb_id):
    try:
        streams = V1.resolve_all(media_type, tmdb_id, season=season,
                                 episode=episode, imdb_id=imdb_id) or []
        for s in streams:
            s.setdefault('provider', 'primary')
        return streams
    except Exception as e:
        log('sources: primary failed %s' % e)
        return []
