# -*- coding: utf-8 -*-

import re
import threading
import xbmc
import xbmcgui
import xbmcaddon

ACTION_BACK = (10, 92)  # ACTION_PREVIOUS_MENU, ACTION_NAV_BACK

_ADDON = xbmcaddon.Addon()
_ADDON_PATH = _ADDON.getAddonInfo('path')


# ---------------------------------------------------------------------------
# Tech metadata extraction
# ---------------------------------------------------------------------------

def _extract_tech(title):
    """Extract source, codec, HDR, audio from a release title string."""
    t = (title or '').upper()

    source = ''
    for pattern, label in (
        (r'BLU.?RAY|BDRIP|BDREMUX|REMUX', 'BluRay'),
        (r'WEB.?DL',                        'WEB-DL'),
        (r'WEBRIP',                         'WEBRip'),
        (r'HDTV',                           'HDTV'),
        (r'DVDRIP',                         'DVDRip'),
        (r'HDRIP',                          'HDRip'),
    ):
        if re.search(pattern, t):
            source = label
            break

    codec = ''
    for token, label in (
        ('AV1',  'AV1'),  ('X265',  'x265'), ('H.265', 'H.265'),
        ('H265', 'H.265'),('HEVC',  'HEVC'), ('X264',  'x264'),
        ('H.264','H.264'),('H264',  'H.264'),
    ):
        if token in t:
            codec = label
            break

    hdr = ''
    for token, label in (
        ('DOLBY.VISION', 'DV'), ('.DV.', 'DV'), ('DV.',  'DV'),
        ('HDR10+',       'HDR10+'), ('HDR10', 'HDR10'),
        ('HDR',          'HDR'),    ('HLG',   'HLG'),
    ):
        if token in t:
            hdr = label
            break

    audio = ''
    for token, label in (
        ('TRUEHD', 'TrueHD'), ('ATMOS', 'Atmos'), ('DTS-HD', 'DTS-HD'),
        ('DTS',    'DTS'),    ('DDP5.1','DD+5.1'), ('DD+',   'DD+'),
        ('DDP',    'DD+'),    ('DD5.1', 'DD5.1'),  ('AC3',   'DD'),
        ('AAC',    'AAC'),    ('FLAC',  'FLAC'),
    ):
        if token in t:
            audio = label
            break

    return source, codec, hdr, audio


def enrich_source(source):
    """Add tech_line and stats_line to a source dict (in-place). Returns it."""
    title = source.get('title_line') or source.get('label') or ''
    src_type, codec, hdr, audio = _extract_tech(title)

    source.setdefault('source_type', src_type)
    source.setdefault('codec', codec)
    source.setdefault('hdr', hdr)
    source.setdefault('audio', audio)

    tech_parts = [p for p in (codec, hdr, audio, src_type) if p]
    source['tech_line'] = ' | '.join(tech_parts) if tech_parts else ''
    if not source['tech_line'] and source.get('_server_name'):
        source['tech_line'] = f"server:{source['_server_name']}"

    provider = source.get('provider') or ''
    seeds = source.get('seeds')
    size = source.get('size') or ''

    stats_parts = []
    if seeds is not None:
        stats_parts.append(f'[COLOR FFFFFF00]👤 {seeds} seederi[/COLOR]')
    if size:
        stats_parts.append(f'[COLOR FF88CCFF]💾 {size}[/COLOR]')

    source['stats_line'] = '   '.join(stats_parts)
    return source


_PROVIDER_ORDER = {
    '[THX]': 0,   # Thrax — rapid, fiabil
    '[PSM]': 1,   # PrimeSrc.me — rapid, info calitate
    '[HDB]': 2,   # HDHub
    '[WSR]': 2,   # Webstreamr
    '[CPR]': 2,   # CinePro
    '[PLW]': 3,   # PulpWatch
    '[FLX]': 3,   # Flixer
    '[VSE]': 3,   # VSEmbed
    '[FHD]': 3,   # FilmeHD
    '[VXS]': 4,   # VixSrc
    '[VDL]': 4,   # VidLink
    '[VDY]': 4,   # Videasy
    '[YFX]': 4,   # YFlix
    '[NBS]': 5,   # NebulaStreams (lent)
    '[FNS]': 5,   # FlixNest (lent, 0 surse des)
}


def sort_sources(sources):
    """Sort: streams by provider preference + quality, torrents by seeders."""
    q_order = {'4K': 0, '2160p': 0, '1080p': 1, '720p': 2, '480p': 3}

    def key(s):
        if s.get('is_torrent'):
            return (10, 5, 0, -(s.get('seeds') or 0))
        provider = s.get('provider') or ''
        prio = _PROVIDER_ORDER.get(provider, 4)
        q = q_order.get(s.get('quality') or '', 5)
        return (prio, q, 0, 0)

    return sorted(sources, key=key)


# ---------------------------------------------------------------------------
# Custom dialog
# ---------------------------------------------------------------------------

_pending_resolver = None  # resolver dialog shown from onClick, picked up by run_resolving_dialog


class DialogSurse(xbmcgui.WindowXMLDialog):
    """Source selection dialog with quality/provider filter buttons."""

    def __init__(self, *args, **kwargs):
        self.sources_all = kwargs.get('sources', [])
        self.item_data = kwargs.get('item_data') or {}
        self.selection = None
        self.cancelled = False
        self._filtered = []
        self._source_feed = kwargs.get('source_feed')  # callable() -> (new_sources, is_done)

        # Build filter option lists (kept as sets for incremental updates)
        self._q_set = set()
        self._p_set = set()
        for s in self.sources_all:
            q = s.get('quality') or ''
            if q:
                self._q_set.add(q)
            p = s.get('provider') or ''
            if p:
                self._p_set.add(p)

        self._rebuild_filter_lists()
        self._filter_q = 'Toate'
        self._filter_p = 'Toți'

    def _rebuild_filter_lists(self):
        q_ord = {'4K': 0, '2160p': 0, '1080p': 1, '720p': 2, '480p': 3}
        self._qualities = ['Toate'] + sorted(self._q_set, key=lambda x: q_ord.get(x, 9))
        self._providers = ['Toți'] + sorted(self._p_set)

    def _update_quality_summary(self):
        _q_norm   = {'4K': '4K', '2160p': '4K', '1080p': '1080p', '720p': '720p', '480p': '480p', '360p': '360p'}
        _q_order  = {'4K': 0, '1080p': 1, '720p': 2, '480p': 3, '360p': 4}
        _q_colors = {'4K': 'FFFFD700', '1080p': 'FF5B9BD5', '720p': 'FF70AD47', '480p': 'FFFF8C00', '360p': 'FFAA88AA', 'N/A': 'FF666666'}
        counts = {}
        for s in self._filtered:
            q = _q_norm.get(s.get('quality') or '', 'N/A')
            counts[q] = counts.get(q, 0) + 1
        parts = [f'[COLOR FFAAAAAA]TOTAL: {len(self._filtered)}[/COLOR]'] + [
            f'[COLOR {_q_colors.get(q, "FFAAAAAA")}]{q}: {n}[/COLOR]'
            for q, n in sorted(counts.items(), key=lambda x: _q_order.get(x[0], 9))
        ]
        self.setProperty('quality_summary', ' · '.join(parts))

    def _poll_feed(self):
        """Background thread: pull new sources from feed and append them without flicker."""
        while not self.cancelled and self.selection is None:
            xbmc.sleep(400)
            if self.cancelled or self.selection is not None:
                return
            try:
                new_srcs, done = self._source_feed()
            except Exception as e:
                xbmc.log(f'[Samus/Dialog] _poll_feed eroare: {e}', xbmc.LOGERROR)
                self.setProperty('loading', '0')
                return
            if new_srcs:
                self.sources_all.extend(new_srcs)
                self.sources_all[:] = sort_sources(self.sources_all)
                for s in new_srcs:
                    q = s.get('quality') or ''
                    if q:
                        self._q_set.add(q)
                    p = s.get('provider') or ''
                    if p:
                        self._p_set.add(p)
                self._rebuild_filter_lists()
                self._update_filter_labels()
                # Append only the new items that pass the current filter — no reset, no flicker
                try:
                    ctrl = self.getControl(1000)
                    added = 0
                    for s in new_srcs:
                        if self._filter_q != 'Toate' and (s.get('quality') or '') != self._filter_q:
                            continue
                        if self._filter_p != 'Toți' and (s.get('provider') or '') != self._filter_p:
                            continue
                        li = xbmcgui.ListItem(label='')
                        li.setProperty('quality',       s.get('quality') or '')
                        li.setProperty('release_title', s.get('title_line') or s.get('label') or '')
                        li.setProperty('provider',      s.get('provider') or '')
                        li.setProperty('tech_line',     s.get('tech_line') or '')
                        li.setProperty('stats_line',    s.get('stats_line') or '')
                        ctrl.addItem(li)
                        self._filtered.append(s)
                        added += 1
                    if added:
                        self.setProperty('source_count', str(len(self._filtered)))
                        self._update_quality_summary()
                        if len(self._filtered) == added:  # first items arriving
                            self.setFocusId(1000)
                except Exception as e:
                    xbmc.log(f'[Samus/Dialog] _poll_feed append eroare: {e}', xbmc.LOGERROR)
            if done:
                self.setProperty('loading', '0')
                return

    def onInit(self):
        try:
            item = self.item_data
            self.setProperty('info.fanart',  item.get('fanart') or item.get('backdrop') or '')
            self.setProperty('info.poster',  item.get('poster') or '')
            self.setProperty('info.title',   item.get('title') or 'Selectează sursa')
            self.setProperty('info.logo',    item.get('logo') or '')
            self.setProperty('loading', '1' if self._source_feed else '0')
            self._refresh_list()
            self._update_filter_labels()
            xbmc.log(f'[Samus/Dialog] onInit: {len(self._filtered)} surse afișate', xbmc.LOGINFO)
            if self._filtered:
                self.setFocusId(1000)
            else:
                self.setFocusId(1300)
            if self._source_feed:
                t = threading.Thread(target=self._poll_feed, daemon=True)
                t.start()
        except Exception as e:
            xbmc.log(f'[Samus/Dialog] onInit: {e}', xbmc.LOGERROR)

    def _update_filter_labels(self):
        try:
            q = self._filter_q if self._filter_q != 'Toate' else 'Calitate'
            p = self._filter_p if self._filter_p != 'Toți' else 'Provider'
            self.setProperty('filter_quality_label', q)
            self.setProperty('filter_provider_label', p)
        except Exception as e:
            xbmc.log(f'[Samus/Dialog] _update_filter_labels: {e}', xbmc.LOGERROR)

    def _refresh_list(self):
        try:
            ctrl = self.getControl(1000)
            try:
                saved_pos = ctrl.getSelectedPosition()
            except Exception:
                saved_pos = 0
            ctrl.reset()

            self._filtered = []
            for s in self.sources_all:
                if self._filter_q != 'Toate' and (s.get('quality') or '') != self._filter_q:
                    continue
                if self._filter_p != 'Toți' and (s.get('provider') or '') != self._filter_p:
                    continue
                self._filtered.append(s)

            self.setProperty('source_count', str(len(self._filtered)))
            self._update_quality_summary()

            for s in self._filtered:
                li = xbmcgui.ListItem(label='')
                li.setProperty('quality',       s.get('quality') or '')
                li.setProperty('release_title', s.get('title_line') or s.get('label') or '')
                li.setProperty('provider',      s.get('provider') or '')
                li.setProperty('tech_line',     s.get('tech_line') or '')
                li.setProperty('stats_line',    s.get('stats_line') or '')
                ctrl.addItem(li)

            # Restore scroll position after live update
            if saved_pos > 0 and saved_pos < len(self._filtered):
                ctrl.selectItem(saved_pos)

        except Exception as e:
            xbmc.log(f'[Samus/Dialog] _refresh_list: {e}', xbmc.LOGERROR)

    def onClick(self, controlId):
        dlg = xbmcgui.Dialog()

        if controlId == 1000:
            idx = self.getControl(1000).getSelectedPosition()
            if 0 <= idx < len(self._filtered):
                self.selection = self._filtered[idx]
                # Show resolver overlay BEFORE closing so it appears on top —
                # source dialog closes behind it, movie list never flashes through.
                global _pending_resolver
                _pending_resolver = DialogResolving(
                    'dialog_resolving.xml', _ADDON_PATH, 'Default', '1080i',
                    fanart=self.item_data.get('fanart', ''),
                    title=self.item_data.get('title', ''),
                )
                _pending_resolver.show()
                self.close()

        elif controlId == 1300:
            i = dlg.select('Filtrează după calitate', self._qualities)
            if i >= 0:
                self._filter_q = self._qualities[i]
                self._refresh_list()
                self._update_filter_labels()

        elif controlId == 1400:
            i = dlg.select('Filtrează după provider', self._providers)
            if i >= 0:
                self._filter_p = self._providers[i]
                self._refresh_list()
                self._update_filter_labels()

    def onAction(self, action):
        if action.getId() in ACTION_BACK:
            self.cancelled = True
            self.close()


class DialogResolving(xbmcgui.WindowXMLDialog):
    """Full-screen resolving window — shown with show() so main plugin thread stays free."""

    def __init__(self, *args, **kwargs):
        fanart = kwargs.get('fanart', '')
        title  = kwargs.get('title', '')
        xbmc.executebuiltin(f'SetProperty(resolving.fanart,{fanart},home)')
        xbmc.executebuiltin(f'SetProperty(resolving.title,{title},home)')
        xbmc.executebuiltin('SetProperty(resolving.status,Se rezolvă sursa...,home)')

    def set_status(self, text):
        xbmc.executebuiltin(f'SetProperty(resolving.status,{text},home)')

    def close(self):
        xbmc.executebuiltin('ClearProperty(resolving.fanart,home)')
        xbmc.executebuiltin('ClearProperty(resolving.title,home)')
        xbmc.executebuiltin('ClearProperty(resolving.status,home)')
        super().close()


def run_resolving_dialog(fanart='', title='', resolver_fn=None):
    """Show the resolving window and run resolver in the main plugin thread.

    If a resolver dialog was already shown from DialogSurse.onClick, reuse it
    (avoids the movie-list flash between source dialog closing and resolver appearing).
    """
    global _pending_resolver
    dlg = _pending_resolver
    _pending_resolver = None
    if dlg is None:
        dlg = DialogResolving(
            'dialog_resolving.xml', _ADDON_PATH, 'Default', '1080i',
            fanart=fanart, title=title,
        )
        dlg.show()
        xbmc.sleep(150)
    result = False
    try:
        result = bool(resolver_fn(dlg))
    except Exception as e:
        xbmc.log(f'[Samus/DialogResolving] Eroare resolver: {e}', xbmc.LOGERROR)
    finally:
        dlg.close()
        del dlg
    return result


def show_source_dialog(sources, item_data=None, source_feed=None):
    """
    Show the custom source dialog.
    Returns the selected source dict, or None if cancelled.
    source_feed: optional callable() -> (new_sources, is_done) for live updates.
    """
    try:
        dlg = DialogSurse(
            'dialog_sources.xml',
            _ADDON_PATH,
            'Default',
            '1080i',
            sources=list(sources),
            item_data=item_data or {},
            source_feed=source_feed,
        )
        dlg.doModal()
        selection = dlg.selection if not dlg.cancelled else None
        final_sources = list(dlg.sources_all)
        del dlg
        return selection, final_sources
    except Exception as e:
        xbmc.log(f'[Samus/Dialog] show_source_dialog fallback: {e}', xbmc.LOGERROR)
        labels = [s.get('label', '?') for s in sources]
        idx = xbmcgui.Dialog().select('Alege o sursă', labels)
        sel = sources[idx] if idx >= 0 else None
        return sel, list(sources)
