# -*- coding: utf-8 -*-
import sys

if 'service=true' in sys.argv[1:]:
    import service
    service.main()
    raise SystemExit

import threading
import atexit
import urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin


def _log_threads_at_exit():
    alive = [f'{t.name}(daemon={t.daemon})' for t in threading.enumerate()]
    xbmc.log(f'[SamusXUI/script] fire la final: {alive}', xbmc.LOGINFO)


atexit.register(_log_threads_at_exit)

# ── parse imediat ─────────────────────────────────────────────────────────────

HANDLE     = int(sys.argv[1]) if len(sys.argv) > 1 else -1
ADDON_PATH = xbmcaddon.Addon().getAddonInfo('path')

params = {}
if len(sys.argv) > 2 and sys.argv[2]:
    params = dict(urllib.parse.parse_qsl(sys.argv[2].lstrip('?')))

action = params.get('action', '')

# ── pentru home: dismiss + cover imediat, înainte de importuri grele ─────────

_splash = None
if not action and HANDLE < 0:
    class _Splash(xbmcgui.WindowXML):
        pass

    _splash = _Splash('splash.xml', ADDON_PATH, 'Default', '1080i')
    _splash.show()

# ── importuri grele + asset generation ───────────────────────────────────────

import os
import struct
import zlib

MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'skins', 'Default', 'media')


def _chunk(tag, data):
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', crc)


def _png_1x1(r, g, b, a=255):
    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)
    raw  = b'\x00' + bytes([r, g, b, a])
    return (b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', ihdr)
            + _chunk(b'IDAT', zlib.compress(raw))
            + _chunk(b'IEND', b''))


def _png_gradient(w, h, start_rgba, end_rgba, horizontal=True):
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    rows = b''
    for y in range(h):
        rows += b'\x00'
        for x in range(w):
            t = (x / max(w - 1, 1)) if horizontal else (y / max(h - 1, 1))
            rows += bytes(int(start_rgba[i] + (end_rgba[i] - start_rgba[i]) * t)
                          for i in range(4))
    return (b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', ihdr)
            + _chunk(b'IDAT', zlib.compress(rows))
            + _chunk(b'IEND', b''))


def _png_rounded_card(w, h, r, fill_rgba, accent_h=0, accent_rgba=None):
    cr, cg, cb, ca = fill_rgba
    ar, ag, ab, aa = accent_rgba if accent_rgba else fill_rgba
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    rows = b''
    for y in range(h):
        rows += b'\x00'
        px = (ar, ag, ab, aa) if y < accent_h else (cr, cg, cb, ca)
        for x in range(w):
            if (x < r or x >= w - r) and (y < r or y >= h - r):
                cx = r if x < r else w - r
                cy = r if y < r else h - r
                d2 = (x - cx) ** 2 + (y - cy) ** 2
                r2 = r * r
                if d2 > r2 + r:
                    rows += bytes([0, 0, 0, 0])
                    continue
                elif d2 > r2 - r:
                    rows += bytes([px[0], px[1], px[2], px[3] // 2])
                    continue
            rows += bytes(px)
    return (b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', ihdr)
            + _chunk(b'IDAT', zlib.compress(rows))
            + _chunk(b'IEND', b''))


def _ensure_assets():
    os.makedirs(MEDIA_PATH, exist_ok=True)
    assets = {
        'white.png':        lambda: _png_1x1(255, 255, 255, 255),
        'grad_l.png':       lambda: _png_gradient(
            128, 1, (14, 14, 26, 240), (14, 14, 26, 0), horizontal=True),
        'grad_b.png':       lambda: _png_gradient(
            1, 128, (14, 14, 26, 0), (14, 14, 26, 245), horizontal=False),
        'card_confirm.png': lambda: _png_rounded_card(
            64, 64, 16,
            fill_rgba=(15, 15, 28, 255),
            accent_h=8,
            accent_rgba=(123, 92, 244, 255),
        ),
    }
    for name, gen in assets.items():
        path = os.path.join(MEDIA_PATH, name)
        if not os.path.exists(path):
            with open(path, 'wb') as f:
                f.write(gen())


_ensure_assets()


def _browse_dir(handle):
    """Return Kodi-native sections when Skin Shortcuts browses the custom UI."""
    import urllib.parse as _up
    _base = 'plugin://plugin.video.samusxui/?'
    _cats = [
        ('movies',    'Filme'),
        ('tv',        'Seriale'),
        ('favorites', 'Favorite'),
        ('continue',  'Continuă vizionarea'),
    ]
    for _section, _label in _cats:
        _li = xbmcgui.ListItem(_label)
        _url = _base + _up.urlencode({'action': 'submenu', 'section': _section})
        xbmcplugin.addDirectoryItem(handle, _url, _li, True)
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=True)


def _open_home_over_handle(handle):
    import os
    import threading
    import time
    import xbmcvfs

    # Skin Shortcuts marks its widget browser explicitly. A generic modal-dialog
    # check also matches Kodi's own busy dialog during a normal add-on launch
    # and incorrectly turns that launch into a directory listing.
    if xbmcgui.Window(10000).getProperty('skinshortcuts-management-widget'):
        _browse_dir(handle)
        return

    # Finish the plugin directory before opening the custom modal UI. Creating
    # WindowXML from a worker thread while MyVideoNav is still active makes
    # Kodi refuse the window with "active modal dialogs".
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)

    # Widgeturile skinului interoghează rădăcina pluginului ori de câte ori se
    # revine la meniul principal — deci și imediat după ce interfața custom
    # s-a închis, fiindcă launcherul face ActivateWindow(home) la ieșire. Fără
    # cele două opriri de mai jos se închide o buclă: interogare → alarmă →
    # launcher → ActivateWindow(home) → interogare. Observată pe Fire TV la
    # 0.0.50: relansare la fiecare ~2,5 s, fără ieșire.
    _win = xbmcgui.Window(10000)
    if _win.getProperty('samusxui_custom_ui_open') == 'true':
        return
    try:
        if time.time() - float(_win.getProperty('samusxui_custom_ui_closed') or 0) < 2:
            return
    except ValueError:
        pass

    # Use a distinct script invocation. Kodi can suppress a parameterless
    # RunScript for this add-on while its plugin entry point is still exiting.
    xbmc.executebuiltin(
        'AlarmClock(SamusXUIPluginLaunch,'
        'RunScript(plugin.video.samusxui,custom_home=true,from_plugin=true),'
        '00:01,silent)'
    )
    return

    # Two flags prevent the Aeon Nox widget auto-fetch loop:
    #   hw_open  — atomically created before endOfDirectory; only one instance wins
    #   hw_closed — timestamp written on HomeWindow close; blocks re-fetch for 8 s
    _flag_open   = xbmcvfs.translatePath('special://temp/samusxui_hw_open.flag')
    _flag_closed = xbmcvfs.translatePath('special://temp/samusxui_hw_closed.flag')

    # Cooldown: HomeWindow was recently closed → skin auto-fetch → skip
    try:
        if time.time() - float(open(_flag_closed).read().strip()) < 0.1:
            xbmcplugin.addDirectoryItems(handle, [])
            xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
            return
    except Exception:
        pass

    # Remove stale open-flag (Kodi crash recovery — older than 30 min)
    try:
        if time.time() - os.path.getmtime(_flag_open) > 1800:
            os.remove(_flag_open)
    except Exception:
        pass

    # Atomic create: only the first instance gets through; all others return empty
    try:
        fd = os.open(_flag_open, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except OSError:
        xbmcplugin.addDirectoryItems(handle, [])
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
        return

    xbmcplugin.addDirectoryItems(handle, [])
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)

    monitor = xbmc.Monitor()

    def _bg():
        _shown = False
        _sp = None
        try:
            for _ in range(50):
                if monitor.abortRequested():
                    return
                if not (xbmc.getCondVisibility('Window.IsActive(busydialognocancel)') or
                        xbmc.getCondVisibility('Window.IsActive(busydialog)')):
                    break
                xbmc.sleep(100)
            else:
                return

            # Show splash in bg thread — after busy dialogs clear, before HomeWindow loads
            class _Sp(xbmcgui.WindowXML):
                pass
            _sp = _Sp('splash.xml', ADDON_PATH, 'Default', '1080i')
            _sp.show()

            from resources.lib.home_window import HomeWindow
            win = HomeWindow('home.xml', ADDON_PATH, 'Default', '1080i')
            _sp.close()
            _sp = None
            _shown = True
            win.doModal()
            del win
        finally:
            try:
                if _sp is not None:
                    _sp.close()
            except Exception:
                pass
            try:
                os.remove(_flag_open)
            except Exception:
                pass
            if _shown:
                try:
                    with open(_flag_closed, 'w') as f:
                        f.write(str(time.time()))
                except Exception:
                    pass

        if _shown:
            # Wait for HomeWindow close animation before ActivateWindow —
            # otherwise Kodi refuses it ("active modal dialogs")
            xbmc.sleep(500)
            xbmc.executebuiltin('ActivateWindow(home)')

    threading.Thread(target=_bg).start()


# ── acțiuni plugin ────────────────────────────────────────────────────────────

if action == 'play_movie':
    from resources.lib import player, dialogs
    from resources.lib.dialogs import DialogResolving
    _tmdb_id_raw = params.get('tmdb_id', '0')
    if not str(_tmdb_id_raw).lstrip('-').isdigit():
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        raise SystemExit
    tmdb_id      = int(_tmdb_id_raw)
    force_dialog = params.get('show_sources') == '1'
    _dlg = DialogResolving('dialog_resolving.xml', ADDON_PATH, 'Default', '1080i')
    _dlg.show()
    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
    xbmc.executebuiltin('Dialog.Close(busydialog)')
    dialogs._pending_resolver = _dlg
    player.play_movie(HANDLE, tmdb_id, force_dialog=force_dialog)
    if dialogs._pending_resolver is not None:
        dialogs._pending_resolver.close()
        dialogs._pending_resolver = None

elif action == 'play_asa':
    from resources.lib import asa as _asa, player as _player
    asa_id = params.get('asa_id', '')
    title  = params.get('title', '')
    if not asa_id:
        xbmcgui.Dialog().notification('SamusXUI', 'ID ASA lipsă', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
    else:
        streams = _asa.stream(asa_id)
        if not streams:
            xbmcgui.Dialog().notification('SamusXUI', 'Niciun stream disponibil', xbmcgui.NOTIFICATION_WARNING)
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        else:
            best    = streams[0]
            ihash   = best.get('infoHash', '')
            sources = best.get('sources', [])
            url = _player.resolve_torrent(ihash, trackers=sources, title=title)
            if url:
                li = xbmcgui.ListItem(title)
                li.setPath(url)
                xbmcplugin.setResolvedUrl(HANDLE, True, li)
            else:
                xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())

elif action == 'play_episode':
    from resources.lib import player, dialogs
    from resources.lib.dialogs import DialogResolving
    tv_id        = int(params.get('tv_id', 0))
    season       = int(params.get('season', 1))
    episode      = int(params.get('episode', 1))
    force_dialog = params.get('show_sources') == '1'
    _dlg = DialogResolving('dialog_resolving.xml', ADDON_PATH, 'Default', '1080i')
    _dlg.show()
    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
    xbmc.executebuiltin('Dialog.Close(busydialog)')
    dialogs._pending_resolver = _dlg
    player.play_tv_episode(HANDLE, tv_id, season, episode, force_dialog=force_dialog)
    if dialogs._pending_resolver is not None:
        dialogs._pending_resolver.close()
        dialogs._pending_resolver = None

elif action == 'show_info':
    from resources.lib import tmdb
    from resources.lib.info_dialog import VideoInfoDialog
    from resources.lib.seasons_window import SeasonsWindow

    tmdb_id    = int(params.get('tmdb_id', 0))
    media_type = params.get('media_type', 'movie')
    if media_type == 'tvshow':
        media_type = 'tv'

    if media_type == 'tv':
        data = tmdb.tv_details(tmdb_id)
    else:
        data = tmdb.movie_details(tmdb_id)

    xbmcplugin.endOfDirectory(HANDLE, succeeded=False,
                               updateListing=False, cacheToDisc=False)

    # Alegerea cheii este locală și instantanee. yt-dlp pornește numai când
    # utilizatorul apasă Trailer; un pre-resolver daemon putea rămâne viu după
    # închiderea dialogului și bloca Py_EndInterpreter la Quit.
    videos = data.get('videos', {}).get('results', [])
    yt_videos = [v for v in videos if v.get('site') == 'YouTube' and v.get('key')]
    yt_videos.sort(key=lambda v: (
        v.get('type') != 'Trailer', v.get('type') != 'Teaser'))
    _trailer_key = yt_videos[0]['key'] if yt_videos else None

    _show_info = True
    while _show_info:
        _show_info = False

        dlg = VideoInfoDialog()
        dlg.set_data(data, media_type)
        dlg.doModal()

        if dlg.navigate_to:
            person_id, _ = dlg.navigate_to
            from resources.lib.person_window import PersonWindow
            from resources.lib import tmdb as _tmdb
            person = _tmdb.person_details(person_id)
            win = PersonWindow('person.xml', ADDON_PATH, 'Default', '1080i')
            win._person_id = person_id
            win._person    = person
            win.doModal()
            del win
        elif dlg.play_action in ('play', 'sources') and media_type == 'movie':
            from resources.lib import player, dialogs
            from resources.lib.dialogs import DialogResolving
            _dlg = DialogResolving('dialog_resolving.xml', ADDON_PATH, 'Default', '1080i')
            _dlg.show()
            dialogs._pending_resolver = _dlg
            player.play_movie(-1, tmdb_id, force_dialog=(dlg.play_action == 'sources'))
            if dialogs._pending_resolver is not None:
                dialogs._pending_resolver.close()
                dialogs._pending_resolver = None
        elif dlg.play_action in ('seasons', 'play', 'sources') and media_type == 'tv':
            win = SeasonsWindow('tv_seasons.xml', ADDON_PATH, 'Default', '1080i')
            win._tv_id = tmdb_id
            win._show  = data
            win.doModal()
            del win
        elif dlg.play_action == 'trailer':
            from resources.lib.dialogs import DialogResolving
            from resources.lib import player
            fanart = tmdb.backdrop_url(data.get('backdrop_path', ''))
            title  = data.get('title') or data.get('name', '')
            loading = DialogResolving(
                'dialog_resolving.xml', ADDON_PATH, 'Default', '1080i',
                fanart=fanart, title=title,
            )
            loading.set_status('Se încarcă trailerul...')
            loading.show()
            yt_key = _trailer_key
            if not yt_key:
                videos = tmdb.videos(tmdb_id, media_type).get('results', [])
                yt_videos = [v for v in videos
                             if v.get('site') == 'YouTube' and v.get('key')]
                yt_videos.sort(key=lambda v: (
                    v.get('type') != 'Trailer', v.get('type') != 'Teaser'))
                yt_key = yt_videos[0]['key'] if yt_videos else None
            xbmc.log(f'[SamusXUI/trailer] key={yt_key} resolver=yt-dlp', xbmc.LOGINFO)
            if yt_key:
                started = player.play_trailer(yt_key)
                if not started:
                    loading.set_status('Trailerul nu este disponibil în această regiune.')
                    xbmc.sleep(3000)
                    loading.close()
                    del loading
                else:
                    # Keep loading visible until fullscreen player is actually shown
                    monitor = xbmc.Monitor()
                    for _ in range(30):
                        if xbmc.getCondVisibility('Window.IsVisible(fullscreenvideo)'):
                            break
                        if monitor.abortRequested():
                            break
                        xbmc.sleep(100)
                    loading.close()
                    del loading
                    # Wait for playback to finish then return to Info
                    p = xbmc.Player()
                    xbmc.sleep(200)
                    while p.isPlaying() and not monitor.abortRequested():
                        xbmc.sleep(200)
                    if not monitor.abortRequested():
                        # Cover HomeWindow flash while Info dialog initialises
                        class _Bg(xbmcgui.WindowXML):
                            pass
                        _bg = _Bg('splash.xml', ADDON_PATH, 'Default', '1080i')
                        _bg.show()
                        xbmc.sleep(300)
                        _bg.close()
                        _show_info = True
            else:
                loading.close()
                del loading

        elif dlg.play_action == 'similar':
            from resources.lib.search_results_window import SearchResultsWindow
            # Atenție: `data` ține detaliile titlului curent și e refolosit de
            # bucla `while _show_info` (fanart, titlu, trailer) — nu-l suprascrie.
            rec   = tmdb.recommendations(tmdb_id, media_type) or {}
            items = rec.get('results') or []
            if not items:
                # Titlurile obscure sau foarte noi n-au recomandări; /similar
                # e calculat altfel și de multe ori returnează totuși ceva.
                rec   = tmdb.similar(tmdb_id, media_type) or {}
                items = rec.get('results') or []
            if items:
                base_title = data.get('title') or data.get('name', '')
                win = SearchResultsWindow('results.xml', ADDON_PATH, 'Default', '1080i')
                win._query       = f'Similare cu {base_title}' if base_title else 'Similare'
                win._media       = media_type
                win._items       = items
                win._total_pages = rec.get('total_pages', 1)
                win.doModal()
                del win
            else:
                xbmcgui.Dialog().notification(
                    'SamusXUI', 'Nu am găsit titluri similare',
                    xbmcgui.NOTIFICATION_INFO, 2500)
            _show_info = True

        elif dlg.play_action == 'collection' and dlg.collection_id:
            from resources.lib.search_results_window import SearchResultsWindow
            coll_data = tmdb.collection(dlg.collection_id)
            parts     = coll_data.get('parts', [])
            parts.sort(key=lambda m: m.get('release_date') or '')
            coll_name = coll_data.get('name', 'Colecție')
            win = SearchResultsWindow('results.xml', ADDON_PATH, 'Default', '1080i')
            win._query       = coll_name
            win._media       = 'movie'
            win._items       = parts
            win._total_pages = 1
            win.doModal()
            del win
            _show_info = True

        del dlg

elif action == 'widget':
    from resources.lib.widgets import handle_widget
    handle_widget(HANDLE, params)

elif action == 'submenu':
    from resources.lib.native_ui import handle_native
    handle_native(HANDLE, params)

elif action == 'native':
    _ui_mode = xbmcaddon.Addon().getSetting('ui_mode') or 'SamusXUI'
    if _ui_mode == 'Nativ (skin)':
        from resources.lib.native_ui import handle_native
        handle_native(HANDLE, params)
    elif xbmc.getCondVisibility('System.HasActiveModalDialog(true)'):
        # Called from within a modal dialog (e.g. skinshortcuts widget browser).
        # Return a section-filtered directory listing instead of trying to open HomeWindow.
        import urllib.parse as _up
        _base = 'plugin://plugin.video.samusxui/?'
        _section = params.get('section', 'movie')
        _cats = [
            ('tv_popular',       'Seriale populare'),
            ('tv_trending',      'Seriale trending'),
            ('tv_on_air',        'Pe ecrane acum'),
            ('favorites_tv',     'Favorite seriale'),
        ] if _section == 'tv' else [
            ('movies_popular',   'Filme populare'),
            ('movies_trending',  'Filme trending'),
            ('movies_cinema',    'Acum la cinema'),
            ('favorites_movies', 'Favorite filme'),
        ]
        for _id, _label in _cats:
            _li = xbmcgui.ListItem(_label)
            xbmcplugin.addDirectoryItem(HANDLE, _base + _up.urlencode({'action': 'widget', 'type': _id}), _li, True)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True, cacheToDisc=True)
    else:
        # endOfDirectory first (closes plugin handle, dismisses busydialognocancel).
        # Then show splash immediately so it covers the empty Videos container
        # before Kodi has a chance to render it. HomeWindow opens under the splash.
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True, cacheToDisc=False)
        class _NativeSp(xbmcgui.WindowXML):
            pass
        _nsp = _NativeSp('splash.xml', ADDON_PATH, 'Default', '1080i')
        _nsp.show()
        from resources.lib.home_window import HomeWindow
        win = HomeWindow('home.xml', ADDON_PATH, 'Default', '1080i')
        _nsp.close()
        win.doModal()
        del win
        xbmc.sleep(300)
        xbmc.executebuiltin('ActivateWindow(home)')

else:
    if HANDLE >= 0:
        ui_mode = xbmcaddon.Addon().getSetting('ui_mode') or 'SamusXUI'
        if ui_mode == 'Nativ (skin)':
            from resources.lib.native_ui import handle_native
            handle_native(HANDLE, params)
        else:
            _open_home_over_handle(HANDLE)
    else:
        # RunScript (HANDLE == -1) — Home window cu splash
        from resources.lib.home_window import HomeWindow
        win = HomeWindow('home.xml', ADDON_PATH, 'Default', '1080i')
        win.doModal()
        del win
        if _splash:
            _splash.close()
            del _splash
        xbmc.sleep(300)
        xbmc.executebuiltin('ActivateWindow(home)')
