# -*- coding: utf-8 -*-

import re
import time
import threading
import xbmc
import xbmcgui
import xbmcaddon

ACTION_BACK = (10, 92)  # ACTION_PREVIOUS_MENU, ACTION_NAV_BACK

_ADDON = xbmcaddon.Addon('plugin.video.samusxui')
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
    new_tech = ' | '.join(tech_parts) if tech_parts else ''
    source['tech_line'] = new_tech or source.get('tech_line', '') or ''
    if not source['tech_line'] and source.get('_server_name'):
        source['tech_line'] = f"server:{source['_server_name']}"

    provider = source.get('provider') or ''
    seeds = source.get('seeds')
    size  = source.get('size') or ''

    stats_parts = []
    if seeds is not None:
        if seeds >= 50:
            seed_color = 'FF44DD44'   # verde — bine seeded
        elif seeds >= 10:
            seed_color = 'FFFFFF00'   # galben — moderat
        else:
            seed_color = 'FFFF5555'   # roșu — puțin seeded
        stats_parts.append(f'[COLOR {seed_color}]👤 {seeds}[/COLOR]')
    if size:
        stats_parts.append(f'[COLOR FF88CCFF]💾 {size}[/COLOR]')

    # Indicator sănătate provider pentru surse non-torrent
    if not source.get('is_torrent') and not stats_parts:
        try:
            from resources.lib import db as _db
            if provider and not _db.provider_is_healthy(provider):
                stats_parts.append('[COLOR FFFF5555]⚠ timeout recent[/COLOR]')
        except Exception:
            pass

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


_QUALITY_NORM = {'4K': '4K', '2160p': '4K', '1080p': '1080p', '720p': '720p', '480p': '480p', '360p': '360p'}
_QUALITY_ORDER = {'4K': 0, '2160p': 0, '1080p': 1, '720p': 2, '480p': 3, '360p': 4}
_QUALITY_COLORS = {
    '4K':    'FFFFCC00',  # gold
    '2160p': 'FFFFCC00',
    '1080p': 'FF44BB66',  # green
    '720p':  'FF4488EE',  # blue
    '480p':  'FF999999',  # gray
    '360p':  'FF777777',
}


def sort_sources(sources):
    """Sort: calitate primară, provider secundar, torrente la final."""
    def key(s):
        if s.get('is_torrent'):
            return (10, 5, 0, -(s.get('seeds') or 0))
        q = _QUALITY_ORDER.get(s.get('quality') or '', 5)
        provider = s.get('provider') or ''
        prio = _PROVIDER_ORDER.get(provider, 4)
        return (q, prio, 0, 0)

    return sorted(sources, key=key)


def _make_source_li(s):
    """Creează ListItem pentru o sursă cu toate proprietățile vizuale."""
    import xbmcgui as _gui
    quality  = s.get('quality') or ''
    provider = s.get('provider') or ''
    q_key    = _QUALITY_NORM.get(quality, quality)
    q_color  = _QUALITY_COLORS.get(quality, 'FF7B5CF4')
    q_label  = f'[B][COLOR {q_color}]{quality}[/COLOR][/B]' if quality else ''

    p_color  = 'FFFF9944' if s.get('is_torrent') else 'FF8899BB'
    p_label  = f'[COLOR {p_color}]{provider}[/COLOR]' if provider else ''

    li = _gui.ListItem(label='')
    seeds     = s.get('seeds') or s.get('seeders') or ''
    file_size = s.get('file_size') or s.get('size') or ''
    is_free   = s.get('is_free') or ''

    li.setProperty('quality',       q_label)
    li.setProperty('quality_key',   q_key)
    li.setProperty('provider',      p_label)
    li.setProperty('provider_raw',  provider)
    li.setProperty('release_title', s.get('title_line') or s.get('label') or '')
    li.setProperty('tech_line',     s.get('tech_line') or '')
    li.setProperty('stats_line',    s.get('stats_line') or '')
    li.setProperty('seeds',          str(seeds) if seeds else '')
    li.setProperty('file_size',      file_size)
    li.setProperty('is_free',        is_free)
    if file_size or is_free:
        import xbmc as _xbmc
        _xbmc.log(f'[Dialog] file_size={file_size!r} is_free={is_free!r} show_free={s.get("show_freeleech")!r}', _xbmc.LOGINFO)
    li.setProperty('show_freeleech', s.get('show_freeleech') or '')
    return li


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
                        ctrl.addItem(_make_source_li(s))
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
                ctrl.addItem(_make_source_li(s))

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
                if _pending_resolver is not None:
                    _pending_resolver.update_info(
                        fanart=self.item_data.get('fanart', ''),
                        title=self.item_data.get('title', ''),
                    )
                else:
                    _pending_resolver = DialogResolving(
                        'dialog_resolving.xml', _ADDON_PATH, 'Default', '1080i',
                        fanart=self.item_data.get('fanart', ''),
                        title=self.item_data.get('title', ''),
                    )
                    _pending_resolver.show()
                self.close()

        elif controlId == 1300:
            i = show_filter_dialog(self._qualities, 'Filtrează după calitate')
            if i >= 0:
                self._filter_q = self._qualities[i]
                self._refresh_list()
                self._update_filter_labels()

        elif controlId == 1400:
            i = show_filter_dialog(self._providers, 'Filtrează după provider')
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
        xbmc.executebuiltin('SetProperty(resolving.status,Se obțin sursele...,home)')
        self._suppress_active = False

    def show(self):
        super().show()
        self._suppress_active = True
        import threading
        def _suppress():
            while self._suppress_active:
                xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
                xbmc.executebuiltin('Dialog.Close(busydialog)')
                xbmc.sleep(150)
        threading.Thread(target=_suppress, daemon=True).start()

    def update_info(self, fanart='', title=''):
        xbmc.executebuiltin(f'SetProperty(resolving.fanart,{fanart},home)')
        xbmc.executebuiltin(f'SetProperty(resolving.title,{title},home)')

    def set_status(self, text):
        xbmc.executebuiltin(f'SetProperty(resolving.status,{text},home)')

    _PROGRESS_BAR_ID  = 6010
    _PROGRESS_BAR_MAX = 752

    def set_torrent_stats(self, speed_dl=0, speed_ul=0, seeders=0, peers=0, loaded=0, progress=0):
        def _fmt_speed(bps):
            if not bps:
                return '—'
            if bps >= 1_048_576:
                return f'{bps / 1_048_576:.1f} MB/s'
            return f'{int(bps / 1024)} KB/s'

        def _fmt_size(b):
            if not b:
                return '—'
            if b >= 1_073_741_824:
                return f'{b / 1_073_741_824:.1f} GB'
            if b >= 1_048_576:
                return f'{int(b / 1_048_576)} MB'
            return f'{int(b / 1024)} KB'

        pct = min(100, max(0, int(progress)))
        xbmc.executebuiltin(f'SetProperty(resolving.speed_dl,↓ {_fmt_speed(speed_dl)},home)')
        xbmc.executebuiltin(f'SetProperty(resolving.speed_ul,↑ {_fmt_speed(speed_ul)},home)')
        xbmc.executebuiltin(f'SetProperty(resolving.seeders,{seeders or 0},home)')
        xbmc.executebuiltin(f'SetProperty(resolving.peers,{peers or 0},home)')
        xbmc.executebuiltin(f'SetProperty(resolving.loaded,{_fmt_size(loaded)},home)')
        xbmc.executebuiltin(f'SetProperty(resolving.progress_pct,{pct}%,home)')
        try:
            self.getControl(self._PROGRESS_BAR_ID).setWidth(
                int(pct * self._PROGRESS_BAR_MAX // 100))
        except Exception:
            pass

    def close(self):
        self._suppress_active = False
        for prop in ('resolving.fanart', 'resolving.title', 'resolving.status',
                     'resolving.speed_dl', 'resolving.speed_ul', 'resolving.seeders',
                     'resolving.peers', 'resolving.loaded', 'resolving.progress_pct'):
            xbmc.executebuiltin(f'ClearProperty({prop},home)')
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
    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
    xbmc.executebuiltin('Dialog.Close(busydialog)')
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
        xbmc.log(f'[Samus/Dialog] show_source_dialog eroare: {e}', xbmc.LOGERROR)
        return None, list(sources)


# ---------------------------------------------------------------------------
# Trakt auth dialog
# ---------------------------------------------------------------------------

class TraktAuthDialog(xbmcgui.WindowXMLDialog):
    """Two-state dialog: prompt → device-code display.
    Polling runs in a background thread; doModal() captures keyboard properly."""

    _ID_BTN_CONN     = 210
    _ID_BTN_CANCEL_P = 211
    _ID_CODE_INST    = 220
    _ID_CODE         = 221
    _ID_URL          = 222
    _ID_COUNTDOWN    = 223
    _ID_BTN_CANCEL_C = 225

    _PROMPT_IDS = (201, 210, 211)
    _CODE_IDS   = (220, 221, 222, 223, 225)

    def __init__(self, *args, **kwargs):
        self.result    = False
        self.cancelled = False

    def onInit(self):
        self._set_state('prompt')

    def _set_state(self, state):
        show = self._PROMPT_IDS if state == 'prompt' else self._CODE_IDS
        hide = self._CODE_IDS   if state == 'prompt' else self._PROMPT_IDS
        for cid in show:
            try: self.getControl(cid).setVisible(True)
            except Exception: pass
        for cid in hide:
            try: self.getControl(cid).setVisible(False)
            except Exception: pass
        focus = self._ID_BTN_CONN if state == 'prompt' else self._ID_BTN_CANCEL_C
        try: self.setFocusId(focus)
        except Exception: pass

    def _set_countdown(self, text):
        try: self.getControl(self._ID_COUNTDOWN).setLabel(text)
        except Exception: pass

    def onClick(self, controlId):
        if controlId == self._ID_BTN_CONN:
            threading.Thread(target=self._run_device_flow, daemon=True).start()
        elif controlId in (self._ID_BTN_CANCEL_P, self._ID_BTN_CANCEL_C):
            self.cancelled = True
            self.close()

    def onAction(self, action):
        if action.getId() in ACTION_BACK:
            self.cancelled = True
            self.close()

    def _run_device_flow(self):
        from . import trakt as _trakt
        client_id     = _trakt._get('trakt_client_id') or _trakt._DEFAULT_CLIENT_ID
        client_secret = _trakt._get('trakt_client_secret')

        if not client_secret:
            xbmcgui.Dialog().notification('Trakt', 'Client Secret lipsă din setări',
                                          xbmcgui.NOTIFICATION_ERROR)
            self.close()
            return

        data = _trakt._request('POST', '/oauth/device/code', data={'client_id': client_id})
        if not data:
            xbmcgui.Dialog().notification('Trakt', 'Eroare la inițierea autentificării',
                                          xbmcgui.NOTIFICATION_ERROR)
            self.close()
            return

        device_code = data['device_code']
        user_code   = data['user_code']
        verify_url  = data['verification_url']
        expires_in  = data.get('expires_in', 600)
        interval    = data.get('interval', 5)

        try:
            self.getControl(self._ID_CODE).setLabel(f'[B]{user_code}[/B]')
            self.getControl(self._ID_URL).setLabel(verify_url)
        except Exception:
            pass
        self._set_state('code')

        deadline  = time.time() + expires_in
        last_poll = time.time() - interval

        while time.time() < deadline and not self.cancelled:
            remaining = max(0, int(deadline - time.time()))
            mins, secs = divmod(remaining, 60)
            self._set_countdown(f'Expiră în: {mins}:{secs:02d}')
            xbmc.sleep(1000)
            if self.cancelled:
                break
            if time.time() - last_poll >= interval:
                last_poll = time.time()
                token_data = _trakt._request('POST', '/oauth/device/token', data={
                    'code':          device_code,
                    'client_id':     client_id,
                    'client_secret': client_secret,
                })
                if token_data and isinstance(token_data, dict) and token_data.get('access_token'):
                    _trakt._set('trakt_access_token', token_data['access_token'])
                    _trakt._set('trakt_refresh_token', token_data.get('refresh_token', ''))
                    _trakt._set('trakt_expires_at',
                                str(time.time() + token_data.get('expires_in', 7776000)))
                    self.result = True
                    self._set_countdown('Autentificat cu succes!')
                    xbmc.sleep(1200)
                    self.close()
                    return

        if not self.cancelled:
            self._set_countdown('Codul a expirat.')
            xbmc.sleep(1500)
        self.close()


def show_trakt_auth_dialog():
    """Show Trakt auth dialog using doModal() — keyboard captured correctly."""
    dlg = TraktAuthDialog('dialog_trakt_auth.xml', _ADDON_PATH, 'Default', '1080i')
    dlg.doModal()
    result = dlg.result
    del dlg
    return result


# ---------------------------------------------------------------------------
# Trakt search dialog
# ---------------------------------------------------------------------------

class TraktSearchDialog(xbmcgui.WindowXMLDialog):
    """Picker tip media Trakt (Filme/Seriale/Liste) — apelat după CustomKeyboard."""

    _ID_QUERY   = 100
    _ID_FILME   = 110
    _ID_SERIALE = 111
    _ID_LISTE   = 112

    def __init__(self, *args, **kwargs):
        self._pre_query = ''  # setat de show_trakt_search_dialog() înainte de doModal()
        self.result = (None, None)

    def onInit(self):
        try:
            q = self._pre_query
            self.getControl(self._ID_QUERY).setLabel(
                f'[COLOR FF9090AA]„[/COLOR]{q}[COLOR FF9090AA]"[/COLOR]')
        except Exception:
            pass
        self.setFocusId(self._ID_FILME)

    def onAction(self, action):
        if action.getId() in ACTION_BACK:
            self.close()

    def onClick(self, controlId):
        if controlId not in (self._ID_FILME, self._ID_SERIALE, self._ID_LISTE):
            return
        query = self._pre_query
        if not query:
            self.close()
            return
        media = {self._ID_FILME: 'movie', self._ID_SERIALE: 'tv', self._ID_LISTE: 'list'}[controlId]
        self.result = (query, media)
        self.close()


def show_trakt_search_dialog():
    """Returnează (query, media_type) sau (None, None) dacă anulat."""
    from .settings_window import CustomKeyboard

    kb = CustomKeyboard(title='Caută pe Trakt')
    kb.doModal()
    xbmc.executebuiltin('Dialog.Close(virtualkeyboard)')
    xbmc.sleep(50)
    xbmc.executebuiltin('Dialog.Close(virtualkeyboard)')
    query = kb.result
    del kb
    if not query:
        return None, None

    dlg = TraktSearchDialog('dialog_trakt_search.xml', _ADDON_PATH, 'Default', '1080i')
    dlg._pre_query = query
    dlg.doModal()
    result = dlg.result
    del dlg
    return result


# ---------------------------------------------------------------------------
# Trakt list picker dialog
# ---------------------------------------------------------------------------

class TraktListPickerDialog(xbmcgui.WindowXMLDialog):
    """Dialog scrollabil pentru selectarea unei liste Trakt."""

    _ID_LIST   = 300
    _ID_TITLE  = 310
    _ID_CANCEL = 301

    def __init__(self, *args, **kwargs):
        self._items     = []   # [{'name', 'user', 'slug', 'count'}]
        self._title_lbl = 'Liste Trakt'
        self.result     = -1   # index selectat sau -1

    def onInit(self):
        try:
            self.getControl(self._ID_TITLE).setLabel(self._title_lbl)
        except Exception:
            pass
        ctrl = self.getControl(self._ID_LIST)
        ctrl.reset()
        for item in self._items:
            li = xbmcgui.ListItem(item['name'])
            count = item.get('count', 0)
            user  = item.get('user', '')
            sub   = f"@{user}  •  {count} iteme" if user and user != 'me' else f"{count} iteme"
            li.setLabel2(sub)
            ctrl.addItem(li)
        if self._items:
            self.setFocusId(self._ID_LIST)

    def onClick(self, controlId):
        if controlId == self._ID_LIST:
            self.result = self.getControl(self._ID_LIST).getSelectedPosition()
            self.close()
        elif controlId == self._ID_CANCEL:
            self.close()

    def onAction(self, action):
        if action.getId() in ACTION_BACK:
            self.close()


class FilterPickerDialog(xbmcgui.WindowXMLDialog):
    """Dialog custom pentru selectarea unui filtru (calitate / provider)."""

    _ID_LIST  = 300
    _ID_TITLE = 310

    def __init__(self, *args, **kwargs):
        self._options = []
        self._title   = 'Filtrează'
        self.result   = -1

    def onInit(self):
        self.getControl(self._ID_TITLE).setLabel(self._title)
        lst = self.getControl(self._ID_LIST)
        lst.reset()
        items = [xbmcgui.ListItem(label=o) for o in self._options]
        lst.addItems(items)
        if items:
            self.setFocus(lst)
        else:
            self.close()

    def onClick(self, controlId):
        if controlId == self._ID_LIST:
            self.result = self.getControl(self._ID_LIST).getSelectedPosition()
            self.close()

    def onAction(self, action):
        if action.getId() in ACTION_BACK:
            self.close()


def show_filter_dialog(options, title='Filtrează'):
    """Afișează dialogul custom de filtrare. Returnează indexul ales sau -1."""
    dlg = FilterPickerDialog('dialog_filter.xml', _ADDON_PATH, 'Default', '1080i')
    dlg._options = options
    dlg._title   = title
    dlg.doModal()
    result = dlg.result
    del dlg
    return result


def show_trakt_list_picker(items, title='Liste Trakt'):
    """Afișează dialogul de selectare liste. Returnează indexul ales sau -1."""
    dlg = TraktListPickerDialog('dialog_trakt_lists.xml', _ADDON_PATH, 'Default', '1080i')
    dlg._items     = items
    dlg._title_lbl = title
    dlg.doModal()
    result = dlg.result
    del dlg
    return result
