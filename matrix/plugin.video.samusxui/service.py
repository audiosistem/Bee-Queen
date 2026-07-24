# -*- coding: utf-8 -*-
"""
Background service: auto-play trailer when hovering on a widget item (Home) or
a MyPrime view item (MyVideoNav). Sets a window property while the trailer is
active so the skin switches to the positioned videowindow.
"""
import re
import threading
import xbmc
import xbmcgui

_POLL_MS = 200
_IDLE_POLL_SECS = 1.0
_HOVER_SECS = 3
_STABLE_TARGET = int(_HOVER_SECS * 1000 / _POLL_MS)
_FOCUS_RETURN_GRACE_TICKS = int(8.0 * 1000 / _POLL_MS)
_PRIME_HOVER_SECS = 3
_PRIME_STABLE_TARGET = int(_PRIME_HOVER_SECS * 1000 / _POLL_MS)
_WIDGET_IDS = [wid for base in (801, 802, 803, 804) for wid in range(base * 100 + 14, base * 100 + 22)]
_SERVICE_PROPERTY = 'samusxui_trailer_service_running'
_TRAILER_OSD_SUPPRESS_MS = 1200
_YT_ID_RE = re.compile(
    r'(?:videoid=|[?&]v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
)
_logo_cache = {}     # (tmdb_id, media_type) -> url or ''
_trailer_cache = {}  # (tmdb_id, media_type) -> yt_key or ''


def _trailer_suppress_prop(prop_name):
    if prop_name == 'myprime_trailer_playing':
        return 'myprime_trailer_suppress_osd'
    return 'widget_trailer_suppress_osd'


def _extract_yt_id(url):
    m = _YT_ID_RE.search(url)
    return m.group(1) if m else None


def _fetch_prime_trailer_bg(tmdb_id, media_type):
    """Pre-fetch YouTube trailer key from TMDB /videos into _trailer_cache."""
    cache_key = (tmdb_id, media_type)
    if cache_key in _trailer_cache:
        return
    try:
        from resources.lib import tmdb as _tmdb
        data = _tmdb._get(f'/{media_type}/{tmdb_id}/videos', language='en-US')
        videos = data.get('results', [])
        yt_key = ''
        for v in videos:
            if v.get('site') == 'YouTube' and v.get('type') == 'Trailer':
                yt_key = v['key']
                break
        if not yt_key:
            for v in videos:
                if v.get('site') == 'YouTube':
                    yt_key = v['key']
                    break
        _trailer_cache[cache_key] = yt_key
    except Exception as e:
        xbmc.log(f'[SamusXUI/service] trailer key fetch error: {e}', xbmc.LOGWARNING)
        _trailer_cache[cache_key] = ''


def _fetch_prime_logo(tmdb_id, media_type, window):
    """Fetch clearlogo from TMDB for the focused MyPrime item. Runs in daemon thread."""
    cache_key = (tmdb_id, media_type)
    if cache_key not in _logo_cache:
        try:
            from resources.lib import tmdb as _tmdb
            data = _tmdb._get(f'/{media_type}/{tmdb_id}/images', include_image_language='en,null')
            logos = data.get('logos', [])
            logo_url = ''
            for logo in logos:
                if logo.get('iso_639_1') == 'en' and logo.get('file_path'):
                    logo_url = 'https://image.tmdb.org/t/p/w500' + logo['file_path']
                    break
            if not logo_url and logos:
                logo_url = 'https://image.tmdb.org/t/p/w500' + logos[0]['file_path']
            _logo_cache[cache_key] = logo_url
        except Exception as e:
            xbmc.log(f'[SamusXUI/service] logo fetch error: {e}', xbmc.LOGWARNING)
            _logo_cache[cache_key] = ''

    logo_url = _logo_cache.get(cache_key, '')
    current_tmdb = xbmc.getInfoLabel('Container(514).ListItem.Property(tmdb_id)')
    if current_tmdb == str(tmdb_id) and logo_url:
        window.setProperty('myprime_hero_logo', logo_url)


def _play_trailer_bg(key, window, state, prop_name='widget_trailer_playing', videowindow_delay=0):
    suppress_prop = _trailer_suppress_prop(prop_name)
    suppress_token = str(id(state))
    window.setProperty(suppress_prop, suppress_token)
    try:
        from resources.lib import player as _player

        # Resolve URL first (yt-dlp is slow; do it before touching the player)
        window.setProperty('widget_trailer_resolving', '1')
        stream_url = _player.resolve_trailer_url(key)
        if not stream_url:
            xbmc.log(f'[SamusXUI/service] no URL for key={key}', xbmc.LOGWARNING)
            return
        if state['cancelled']:
            return

        # Set property BEFORE p.play() so the skin switches to positioned videowindow
        # immediately — avoids fullscreen videowindow flashing for even one frame
        state['starting_player'] = True
        window.setProperty(prop_name, '1')
        if videowindow_delay:
            xbmc.sleep(videowindow_delay)
        if state['cancelled']:
            return

        li = xbmcgui.ListItem(path=stream_url)
        p = xbmc.Player()
        xbmc.log(f'[SamusXUI/service] opening trailer key={key}', xbmc.LOGINFO)
        p.play(stream_url, li, windowed=True)

        deadline = 10.0
        while deadline > 0 and not p.isPlaying() and not state['cancelled']:
            xbmc.sleep(200)
            deadline -= 0.2

        if state['cancelled']:
            p.stop()
            return
        if not p.isPlaying():
            xbmc.executebuiltin('Dialog.Close(okdialog)')
            xbmc.log(f'[SamusXUI/service] player did not start key={key}', xbmc.LOGWARNING)
            return

        # isPlaying() becomes true before the demuxer is necessarily ready.
        # Require one second of continuous playback before suppressing retries.
        confirm_deadline = 1.0
        while confirm_deadline > 0 and p.isPlaying() and not state['cancelled']:
            xbmc.sleep(200)
            confirm_deadline -= 0.2
        if state['cancelled'] or not p.isPlaying():
            if state['cancelled']:
                p.stop()
            else:
                xbmc.executebuiltin('Dialog.Close(okdialog)')
            xbmc.log(f'[SamusXUI/service] player start failed key={key}', xbmc.LOGWARNING)
            return

        state['started'] = True
        state['starting_player'] = False
        xbmc.log(f'[SamusXUI/service] trailer started key={key}', xbmc.LOGINFO)
        while p.isPlaying():
            if state['cancelled']:
                p.stop()
                break
            xbmc.sleep(200)
    except Exception as e:
        xbmc.log(f'[SamusXUI/service] trailer error: {e}', xbmc.LOGWARNING)
    finally:
        state['starting_player'] = False
        window.clearProperty('widget_trailer_resolving')
        # Keep the positioned trailer window active while Kodi drains the last
        # decoded frames; clearing immediately can flash the fullscreen player.
        xbmc.sleep(_TRAILER_OSD_SUPPRESS_MS)
        window.clearProperty(prop_name)
        if window.getProperty(suppress_prop) == suppress_token:
            window.clearProperty(suppress_prop)


def _get_focused_widget_key():
    for wid in _WIDGET_IDS:
        if xbmc.getCondVisibility(f'Control.HasFocus({wid})'):
            return xbmc.getInfoLabel(f'Container({wid}).ListItem.Property(trailer_key)'), wid
    return '', 0


def run():
    monitor = xbmc.Monitor()
    window = xbmcgui.Window(10000)

    # Home screen widget trailer state
    current_key = ''
    current_wid = 0
    stable_count = 0
    trailer_thread = None
    trailer_state = None
    trailer_started_for_focus = False
    _no_widget_focus_ticks = 0

    # MyPrime view trailer state
    prime_key = ''
    prime_stable_count = 0
    prime_thread = None
    prime_state = None
    prime_started_for_item = False
    prime_no_focus_ticks = 0

    xbmc.log('[SamusXUI/service] run() started', xbmc.LOGINFO)

    while not monitor.abortRequested():
        prime_window_active = xbmc.getCondVisibility('Window.IsActive(MyVideoNav.xml)')
        prime_view_active = (prime_window_active and
                             xbmc.getCondVisibility('Control.IsVisible(514)'))
        home_active = xbmc.getCondVisibility('Window.IsActive(Home)')
        prime_thread_alive = prime_thread is not None and prime_thread.is_alive()
        poll_secs = (_POLL_MS / 1000.0
                     if (home_active or prime_view_active or prime_thread_alive)
                     else _IDLE_POLL_SECS)
        if monitor.waitForAbort(poll_secs):
            break

        prime_window_active = xbmc.getCondVisibility('Window.IsActive(MyVideoNav.xml)')
        prime_view_active = (prime_window_active and
                             xbmc.getCondVisibility('Control.IsVisible(514)'))
        home_active = xbmc.getCondVisibility('Window.IsActive(Home)')
        prime_thread_alive = prime_thread is not None and prime_thread.is_alive()

        # ── MyPrime view trailer ──────────────────────────────────────────────
        # A windowed player can briefly hide view 514 or steal its focus.
        # Preserve the context during startup, as the Home widget path does.
        prime_starting = bool(prime_state and prime_state.get('starting_player'))
        if not prime_window_active and not (prime_thread_alive and prime_starting):
            if prime_thread_alive:
                if prime_state:
                    prime_state['cancelled'] = True
                xbmc.Player().stop()
            if prime_key:
                window.clearProperty('myprime_hero_logo')
            prime_key = ''
            prime_stable_count = 0
            prime_started_for_item = False
            prime_no_focus_ticks = 0
            prime_thread = None
            prime_state = None
        else:
            # Collect finished prime thread
            if prime_thread is not None and not prime_thread.is_alive():
                if prime_state and prime_state['started']:
                    prime_started_for_item = True
                else:
                    prime_stable_count = 0
                prime_thread = None
                prime_state = None

            focused_trailer_url = xbmc.getInfoLabel('Container(514).ListItem.Trailer')
            focused_item_label = xbmc.getInfoLabel('Container(514).ListItem.Label')
            focused_prime_key = focused_trailer_url or focused_item_label
            prime_has_focus = xbmc.getCondVisibility('Control.HasFocus(514)')

            prime_thread_alive = prime_thread is not None and prime_thread.is_alive()

            if prime_thread_alive:
                if focused_prime_key and focused_prime_key != prime_key:
                    prime_no_focus_ticks = 0
                    if prime_state:
                        prime_state['cancelled'] = True
                    xbmc.Player().stop()
                elif not prime_has_focus:
                    player_busy = xbmc.getCondVisibility('Window.IsVisible(busydialog)')
                    if (prime_state and not prime_state.get('starting_player') and
                            not player_busy):
                        prime_no_focus_ticks += 1
                        if prime_no_focus_ticks >= 2:
                            if prime_state:
                                prime_state['cancelled'] = True
                            xbmc.Player().stop()
                    else:
                        prime_no_focus_ticks = 0
                else:
                    prime_no_focus_ticks = 0
            elif not prime_view_active or not prime_has_focus:
                if window.getProperty('myprime_trailer_playing'):
                    xbmc.Player().stop()
                    window.clearProperty('myprime_trailer_playing')
                if prime_key:
                    window.clearProperty('myprime_hero_logo')
                prime_key = ''
                prime_stable_count = 0
                prime_started_for_item = False
                prime_no_focus_ticks = 0
            elif focused_prime_key:
                if focused_prime_key != prime_key:
                    if window.getProperty('myprime_trailer_playing'):
                        xbmc.Player().stop()
                        window.clearProperty('myprime_trailer_playing')
                    prime_key = focused_prime_key
                    prime_stable_count = 1
                    prime_started_for_item = False
                    # Logo fetch lazy: pornit imediat la schimbarea itemului
                    window.clearProperty('myprime_hero_logo')
                    focused_tmdb_id = xbmc.getInfoLabel('Container(514).ListItem.Property(tmdb_id)')
                    focused_media_type = xbmc.getInfoLabel('Container(514).ListItem.Property(media_type)') or 'movie'
                    if focused_tmdb_id:
                        threading.Thread(
                            target=_fetch_prime_logo,
                            args=(focused_tmdb_id, focused_media_type, window),
                            daemon=True,
                        ).start()
                        threading.Thread(
                            target=_fetch_prime_trailer_bg,
                            args=(focused_tmdb_id, focused_media_type),
                            daemon=True,
                        ).start()
                else:
                    prime_stable_count += 1
                    if (prime_stable_count >= _PRIME_STABLE_TARGET and
                            not prime_started_for_item and
                            not window.getProperty('myprime_trailer_playing')):
                        yt_id = _extract_yt_id(focused_trailer_url) if focused_trailer_url else None
                        if not yt_id:
                            cur_tmdb = xbmc.getInfoLabel('Container(514).ListItem.Property(tmdb_id)')
                            cur_media = xbmc.getInfoLabel('Container(514).ListItem.Property(media_type)') or 'movie'
                            yt_id = _trailer_cache.get((cur_tmdb, cur_media), '') if cur_tmdb else ''
                        if yt_id:
                            prime_stable_count = _PRIME_STABLE_TARGET + 9999
                            prime_no_focus_ticks = 0
                            prime_state = {
                                'cancelled': False,
                                'started': False,
                                'starting_player': False,
                            }
                            prime_thread = threading.Thread(
                                target=_play_trailer_bg,
                                args=(yt_id, window, prime_state, 'myprime_trailer_playing', 500),
                                daemon=True,
                            )
                            prime_thread.start()
            else:
                if window.getProperty('myprime_trailer_playing'):
                    xbmc.Player().stop()
                    window.clearProperty('myprime_trailer_playing')
                prime_key = ''
                prime_stable_count = 0
                prime_started_for_item = False

        if not home_active:
            current_key = ''
            current_wid = 0
            stable_count = 0
            trailer_started_for_focus = False
            continue

        # Don't trigger while user is actively watching something else
        if (xbmc.getCondVisibility('Player.HasVideo') and
                not window.getProperty('widget_trailer_playing') and
                (trailer_thread is None or not trailer_thread.is_alive())):
            current_key = ''
            stable_count = 0
            trailer_started_for_focus = False
            continue

        trailer_active = bool(window.getProperty('widget_trailer_playing'))
        thread_alive = trailer_thread is not None and trailer_thread.is_alive()

        # Collect the completed attempt. A trailer that really started must not
        # restart on the same focused item after Escape; a failed start retries
        # after a fresh hover delay.
        if trailer_thread is not None and not thread_alive:
            if trailer_state and trailer_state['started']:
                trailer_started_for_focus = True
            else:
                stable_count = 0
            trailer_thread = None
            trailer_state = None

        focused_key, focused_wid = _get_focused_widget_key()

        # While trailer is running:
        # - Different item (both keys non-empty, changed): stop immediately
        # - No widget focus (focused_wid==0): debounce 2 ticks (400ms) before stopping.
        #   p.play(windowed=True) briefly steals focus for ~1 tick (200ms), so 2-tick debounce
        #   ignores the momentary steal but still catches sustained Esc/Back → main menu.
        # - Empty focused_key alone: don't stop (container refresh during playback).
        if thread_alive:
            if xbmc.getCondVisibility('Control.HasFocus(9000)'):
                _no_widget_focus_ticks = 0
                trailer_state['cancelled'] = True
                window.clearProperty('widget_trailer_playing')
                xbmc.Player().stop()
            elif focused_key and focused_key != current_key:
                _no_widget_focus_ticks = 0
                trailer_state['cancelled'] = True
                xbmc.Player().stop()
            elif focused_wid == 0:
                # Opening a windowed player temporarily steals widget focus.
                # Do not stop it while Kodi is still opening its demuxer or
                # dismissing the internal busy dialog.
                if (trailer_state['starting_player'] or
                        xbmc.getCondVisibility('Window.IsVisible(busydialog)')):
                    _no_widget_focus_ticks = 0
                else:
                    _no_widget_focus_ticks += 1
                    if _no_widget_focus_ticks >= 2:
                        trailer_state['cancelled'] = True
                        xbmc.Player().stop()
            else:
                _no_widget_focus_ticks = 0
            continue

        if not focused_key:
            # Closing a windowed trailer briefly returns focus through Home
            # before Kodi restores the widget control. Keep the completed-item
            # marker during that transition so the same trailer cannot loop.
            if (current_key and trailer_started_for_focus and
                    not xbmc.getCondVisibility('Control.HasFocus(9000)') and
                    _no_widget_focus_ticks < _FOCUS_RETURN_GRACE_TICKS):
                _no_widget_focus_ticks += 1
                continue
            if trailer_active:
                xbmc.Player().stop()
                window.clearProperty('widget_trailer_playing')
            current_key = ''
            current_wid = 0
            stable_count = 0
            trailer_started_for_focus = False
            continue

        _no_widget_focus_ticks = 0

        if focused_key != current_key or focused_wid != current_wid:
            if trailer_active:
                xbmc.Player().stop()
                window.clearProperty('widget_trailer_playing')
            current_key = focused_key
            current_wid = focused_wid
            stable_count = 1
            trailer_started_for_focus = False
            continue

        stable_count += 1

        if (stable_count >= _STABLE_TARGET and
                not trailer_started_for_focus and
                not window.getProperty('widget_trailer_playing')):
            if trailer_thread is None or not trailer_thread.is_alive():
                stable_count = _STABLE_TARGET + 9999
                _no_widget_focus_ticks = 0
                trailer_state = {
                    'cancelled': False,
                    'started': False,
                    'starting_player': False,
                }
                trailer_thread = threading.Thread(
                    target=_play_trailer_bg,
                    args=(current_key, window, trailer_state),
                    daemon=True
                )
                trailer_thread.start()


def main():
    service_window = xbmcgui.Window(10000)
    if service_window.getProperty(_SERVICE_PROPERTY):
        return
    else:
        service_window.setProperty(_SERVICE_PROPERTY, '1')
        try:
            run()
        except Exception as e:
            xbmc.log(f'[SamusXUI/service] CRASH in run(): {e}', xbmc.LOGERROR)
            import traceback
            xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        finally:
            service_window.clearProperty(_SERVICE_PROPERTY)

if __name__ == '__main__':
    main()
