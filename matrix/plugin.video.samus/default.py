import sys
import xbmc
import xbmcplugin
import xbmcaddon
import xbmcgui
from urllib.parse import parse_qs, urlparse, unquote

from resources.lib import player
from resources.lib.tmdb import api
from resources.lib.utils import get_icon_path
from resources.lib.menus import movies, tvshows
from resources.lib.menus import trakt as trakt_menu
from resources.lib.menus import history as history_menu
from resources.lib import favorites as fav
from resources.lib import trakt as trakt_api
from resources.lib import db

addon = xbmcaddon.Addon()
handle = int(sys.argv[1])

params = parse_qs(urlparse(sys.argv[2]).query)
xbmc.log(f"[Samus] Params: {params}", xbmc.LOGINFO)
action = params.get('action', [''])[0]
page = int(params.get('page', [1])[0])

# ── Movies ──────────────────────────────────────────────────────────────────
if action == 'movies':
    movies.menu()
elif action == 'movies_popular':
    movies.show_popular(page)
elif action == 'movies_trending':
    movies.show_trending(page)
elif action == 'movies_genres':
    movies.show_genres()
elif action == 'movies_by_genre':
    genre_id = int(params.get('genre_id', [0])[0])
    genre_name = params.get('genre_name', [''])[0]
    movies.show_by_genre(genre_id, genre_name, page)
elif action == 'movies_years':
    movies.show_years()
elif action == 'movies_by_year':
    year = int(params.get('year', [2024])[0])
    movies.show_by_year(year, page)
elif action == 'movies_providers':
    movies.show_providers()
elif action == 'movies_by_provider':
    provider_id = int(params.get('provider_id', [0])[0])
    provider_name = params.get('provider_name', [''])[0]
    movies.show_by_provider(provider_id, provider_name, page)
elif action == 'movies_search':
    movies.search()
elif action == 'movies_search_results':
    query = params.get('query', [''])[0]
    movies.search_results(query)
elif action == 'movies_similar':
    tmdb_id = int(params.get('tmdb_id', [0])[0])
    movies.show_similar(tmdb_id, page)
elif action == 'movies_recommended':
    tmdb_id = int(params.get('tmdb_id', [0])[0])
    movies.show_recommended(tmdb_id, page)
elif action == 'movies_collection':
    tmdb_id = int(params.get('tmdb_id', [0])[0])
    movies.show_collection(tmdb_id)

# ── TV Shows ─────────────────────────────────────────────────────────────────
elif action == 'tvshows':
    tvshows.menu()
elif action == 'tvshows_popular':
    tvshows.show_popular(page)
elif action == 'tvshows_trending':
    tvshows.show_trending(page)
elif action == 'tvshows_genres':
    tvshows.show_genres()
elif action == 'tvshows_by_genre':
    genre_id = int(params.get('genre_id', [0])[0])
    genre_name = params.get('genre_name', [''])[0]
    tvshows.show_by_genre(genre_id, genre_name, page)
elif action == 'tvshows_years':
    tvshows.show_years()
elif action == 'tvshows_by_year':
    year = int(params.get('year', [2024])[0])
    tvshows.show_by_year(year, page)
elif action == 'tvshows_providers':
    tvshows.show_providers()
elif action == 'tvshows_by_provider':
    provider_id = int(params.get('provider_id', [0])[0])
    provider_name = params.get('provider_name', [''])[0]
    tvshows.show_by_provider(provider_id, provider_name, page)
elif action == 'tvshows_search':
    tvshows.search()
elif action == 'tvshows_similar':
    tv_id = int(params.get('tv_id', [0])[0])
    tvshows.show_similar(tv_id, page)
elif action == 'tvshows_recommended':
    tv_id = int(params.get('tv_id', [0])[0])
    tvshows.show_recommended(tv_id, page)
elif action == 'tv_details':
    tv_id = int(params.get('id', [0])[0])
    tvshows.show_seasons(tv_id)
elif action == 'tv_season':
    tv_id = int(params.get('tv_id', [0])[0])
    season_number = int(params.get('season', [0])[0])
    tvshows.show_episodes(tv_id, season_number)

# ── Playback ──────────────────────────────────────────────────────────────────
elif action == 'play_episode':
    tv_id = int(params.get('tv_id', [0])[0])
    season = int(params.get('season', [0])[0])
    episode = int(params.get('episode', [0])[0])
    preferred_provider = params.get('preferred_provider', [None])[0]
    try:
        player.play_tv_episode(handle, tv_id, season, episode, preferred_provider=preferred_provider)
    except Exception as e:
        xbmc.log(f'[Samus] Eroare play_tv_episode: {e}', xbmc.LOGERROR)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
elif action == 'play_movie':
    tmdb_id = int(params.get('tmdb_id', params.get('id', [0]))[0])
    try:
        player.play_movie(handle, tmdb_id)
    except Exception as e:
        xbmc.log(f'[Samus] Eroare play_movie: {e}', xbmc.LOGERROR)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())

# ── Trailer ───────────────────────────────────────────────────────────────────
elif action == 'play_trailer':
    _tmdb_id = int(params.get('tmdb_id', [0])[0])
    _media_type = params.get('media_type', ['movie'])[0]
    if _media_type == 'movie':
        from resources.lib.tmdb.movies import get_movie_details
        _details = get_movie_details(_tmdb_id)
    else:
        from resources.lib.tmdb.tv import get_tv_details
        _details = get_tv_details(_tmdb_id)
    _videos = (_details.get('videos') or {}).get('results') or []
    if not _videos:
        # Fallback: fetch videos fără filtru de limbă (trailerele pot fi indexate în altă limbă)
        from resources.lib.tmdb.api import tmdb_cached, TTL_DETAILS
        _endpoint = f'{"movie" if _media_type == "movie" else "tv"}/{_tmdb_id}/videos'
        _vdata = tmdb_cached(_endpoint, {'language': 'en'}, ttl=TTL_DETAILS)
        _videos = (_vdata.get('results') or [])
    _trailer = next((v for v in _videos if v.get('site') == 'YouTube' and v.get('type') == 'Trailer'), None)
    if not _trailer:
        _trailer = next((v for v in _videos if v.get('site') == 'YouTube'), None)
    _title = _details.get('title') or _details.get('name') or ''

    if not _title:
        xbmcgui.Dialog().notification('Samus', 'Niciun trailer disponibil.', xbmcgui.NOTIFICATION_INFO)
    elif xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)') and _trailer:
        xbmc.executebuiltin(f"RunPlugin(plugin://plugin.video.youtube/play/?video_id={_trailer['key']})")
    else:
        # Fallback: extrage URL direct cu yt-dlp (sau caută pe YouTube dacă TMDb nu are trailer)
        try:
            try:
                import yt_dlp
            except ImportError:
                import sys as _sys
                _ytdlp_lib = xbmcvfs.translatePath('special://home/addons/script.module.yt-dlp/lib')
                if _ytdlp_lib not in _sys.path:
                    _sys.path.insert(0, _ytdlp_lib)
                import yt_dlp
            xbmcgui.Dialog().notification('Samus', 'Se extrage trailer-ul...', xbmcgui.NOTIFICATION_INFO, 3000)
            _ydl_opts = {
                'format': 'best[height<=720]/best',
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 15,
            }
            _yt_url = (f'https://www.youtube.com/watch?v={_trailer["key"]}'
                       if _trailer else f'ytsearch1:{_title} official trailer')
            with yt_dlp.YoutubeDL(_ydl_opts) as _ydl:
                _info = _ydl.extract_info(_yt_url, download=False)
            if 'entries' in _info:
                _info = _info['entries'][0] if _info['entries'] else {}
            _stream_url = _info.get('url') or ((_info.get('formats') or [{}])[-1].get('url'))
            if _stream_url:
                _ua = (_info.get('http_headers') or {}).get('User-Agent', '')
                if _ua:
                    _stream_url = f'{_stream_url}|User-Agent={_ua}'
                _li = xbmcgui.ListItem(label=_title, path=_stream_url)
                _li.setProperty('IsPlayable', 'true')
                if '.m3u8' in _stream_url.split('|')[0]:
                    _li.setMimeType('application/vnd.apple.mpegurl')
                    _li.setContentLookup(False)
                    _li.setProperty('inputstream', 'inputstream.adaptive')
                    _li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                xbmc.Player().play(_stream_url, _li)
            else:
                xbmcgui.Dialog().notification('Samus', 'Nu s-a putut extrage URL-ul.', xbmcgui.NOTIFICATION_ERROR)
        except ImportError:
            xbmcgui.Dialog().notification(
                'Samus', 'Instalează plugin.video.youtube sau script.module.yt-dlp.',
                xbmcgui.NOTIFICATION_ERROR, 5000,
            )
        except Exception as _e:
            xbmc.log(f'[Samus/trailer] yt-dlp eroare: {_e}', xbmc.LOGERROR)
            xbmcgui.Dialog().notification('Samus', 'Eroare la extragerea trailerului.', xbmcgui.NOTIFICATION_ERROR)

# ── History ───────────────────────────────────────────────────────────────────
elif action == 'continue_watching':
    history_menu.show_continue_watching()
elif action == 'history_remove':
    tmdb_id = int(params.get('tmdb_id', [0])[0])
    media_type = params.get('media_type', ['movie'])[0]
    db.history_remove(tmdb_id, media_type)
    xbmc.executebuiltin('Container.Refresh')

# ── Favorites ─────────────────────────────────────────────────────────────────
elif action == 'favorites':
    fav.show_favorites(handle)
elif action == 'favorites_movies':
    fav.show_favorites(handle, media_type='movie')
elif action == 'favorites_shows':
    fav.show_favorites(handle, media_type='tvshow')
elif action == 'add_favorite':
    tmdb_id = int(params.get('tmdb_id', [0])[0])
    media_type = params.get('media_type', ['movie'])[0]
    title = unquote(params.get('title', [''])[0])
    year = params.get('year', [''])[0]
    poster = params.get('poster', [''])[0]
    plot = unquote(params.get('plot', [''])[0])
    fav.add_to_favorites(tmdb_id, media_type, title, year, poster, plot)
elif action == 'remove_favorite':
    tmdb_id = int(params.get('tmdb_id', [0])[0])
    media_type = params.get('media_type', ['movie'])[0]
    title = unquote(params.get('title', [''])[0])
    fav.remove_from_favorites(tmdb_id, media_type, title)

# ── Trakt ─────────────────────────────────────────────────────────────────────
elif action == 'trakt':
    trakt_menu.menu()
elif action == 'trakt_auth':
    trakt_api.authenticate()
    xbmc.executebuiltin('Container.Refresh')
elif action == 'trakt_logout':
    trakt_api.logout()
    xbmc.executebuiltin('Container.Refresh')
elif action == 'trakt_trending_movies':
    trakt_menu.show_trending_movies(page)
elif action == 'trakt_popular_movies':
    trakt_menu.show_popular_movies(page)
elif action == 'trakt_watched_movies':
    trakt_menu.show_watched_movies(page)
elif action == 'trakt_watchlist_movies':
    trakt_menu.show_watchlist_movies(page)
elif action == 'trakt_history_movies':
    trakt_menu.show_history_movies(page)
elif action == 'trakt_trending_shows':
    trakt_menu.show_trending_shows(page)
elif action == 'trakt_popular_shows':
    trakt_menu.show_popular_shows(page)
elif action == 'trakt_watched_shows':
    trakt_menu.show_watched_shows(page)
elif action == 'trakt_watchlist_shows':
    trakt_menu.show_watchlist_shows(page)
elif action == 'trakt_recommendations_movies':
    trakt_menu.show_recommendations_movies()
elif action == 'trakt_recommendations_shows':
    trakt_menu.show_recommendations_shows()
elif action == 'trakt_watchlist_add':
    tmdb_id = int(params.get('tmdb_id', [0])[0])
    media_type = params.get('media_type', ['movie'])[0]
    result = trakt_api.add_to_watchlist(media_type, tmdb_id)
    if result:
        xbmcgui.Dialog().notification('Trakt', 'Adăugat la Watchlist', xbmcgui.NOTIFICATION_INFO, 3000)
    else:
        xbmcgui.Dialog().notification('Trakt', 'Eroare la adăugare', xbmcgui.NOTIFICATION_ERROR, 3000)
elif action == 'trakt_watchlist_remove':
    tmdb_id = int(params.get('tmdb_id', [0])[0])
    media_type = params.get('media_type', ['movie'])[0]
    result = trakt_api.remove_from_watchlist(media_type, tmdb_id)
    if result:
        xbmcgui.Dialog().notification('Trakt', 'Șters din Watchlist', xbmcgui.NOTIFICATION_INFO, 3000)
    else:
        xbmcgui.Dialog().notification('Trakt', 'Eroare la ștergere', xbmcgui.NOTIFICATION_ERROR, 3000)
elif action == 'trakt_lists':
    trakt_menu.show_lists_menu()
elif action == 'trakt_trending_lists':
    trakt_menu.show_trending_lists(page)
elif action == 'trakt_popular_lists':
    trakt_menu.show_popular_lists(page)
elif action == 'trakt_my_lists':
    trakt_menu.show_my_lists()
elif action == 'trakt_search_lists':
    _query = xbmcgui.Dialog().input('Caută liste Trakt')
    if _query and _query.strip():
        from urllib.parse import quote as _quote
        xbmc.executebuiltin(f'Container.Update("{sys.argv[0]}?action=trakt_search_lists_results&query={_quote(_query.strip())}")')
elif action == 'trakt_search_lists_results':
    _query = params.get('query', [''])[0]
    if _query:
        trakt_menu.search_lists(_query, page)
elif action == 'trakt_list_items':
    _username  = params.get('username', [''])[0]
    _list_id   = params.get('list_id', [''])[0]
    _list_name = params.get('list_name', [''])[0]
    trakt_menu.show_list_items(_username, _list_id, _list_name, page)

elif action == 'person_cast':
    from resources.lib.menus import people as people_menu
    _tmdb_id    = int(params.get('tmdb_id', [0])[0])
    _media_type = params.get('media_type', ['movie'])[0]
    people_menu.show_cast(_tmdb_id, _media_type)
elif action == 'person_filmography':
    from resources.lib.menus import people as people_menu
    _person_id   = int(params.get('person_id', [0])[0])
    _person_name = params.get('person_name', [''])[0]
    people_menu.show_filmography(_person_id, _person_name)
elif action == 'person_bio':
    from resources.lib.menus import people as people_menu
    _person_id   = int(params.get('person_id', [0])[0])
    _person_name = params.get('person_name', [''])[0]
    people_menu.show_bio(_person_id, _person_name)
    xbmcplugin.endOfDirectory(handle, succeeded=False)
elif action == 'open_person_filmography':
    from resources.lib.menus import people as people_menu
    _name = params.get('name', [''])[0]
    people_menu.open_filmography_by_name(_name)
    xbmcplugin.endOfDirectory(handle, succeeded=False)
elif action == 'show_info':
    from urllib.parse import quote as _quote
    from resources.lib.info_dialog import VideoInfoDialog
    from resources.lib.tmdb import movies as _tmdb_m, tv as _tmdb_tv
    _tmdb_id    = int(params.get('tmdb_id', [0])[0])
    _media_type = params.get('media_type', ['movie'])[0]
    _item = (_tmdb_tv.get_tv_details(_tmdb_id)
             if _media_type in ('tv', 'tvshow')
             else _tmdb_m.get_movie_details(_tmdb_id))
    if _item:
        _dlg = VideoInfoDialog()
        _dlg.set_data(_item, _media_type)
        _dlg.doModal()
        if _dlg.navigate_to:
            _pid, _pname = _dlg.navigate_to
            xbmc.executebuiltin(
                f'ActivateWindow(Videos,plugin://plugin.video.samus'
                f'?action=person_filmography&person_id={_pid}'
                f'&person_name={_quote(_pname)},return)'
            )
        elif _dlg.play_action == 'play':
            _play_li = xbmcgui.ListItem()
            _play_li.setProperty('IsPlayable', 'true')
            xbmc.Player().play(
                f'plugin://plugin.video.samus?action=play_movie&tmdb_id={_tmdb_id}',
                _play_li
            )
        elif _dlg.play_action == 'seasons':
            xbmc.executebuiltin(
                f'ActivateWindow(Videos,plugin://plugin.video.samus'
                f'?action=tv_details&id={_tmdb_id},return)'
            )
        del _dlg
    xbmcplugin.endOfDirectory(handle, succeeded=False)

# ── Home ──────────────────────────────────────────────────────────────────────
else:
    xbmcplugin.setPluginCategory(handle, 'Samus')

    li = xbmcgui.ListItem('Continuă vizionarea')
    li.setArt({'thumb': get_icon_path('watch'), 'icon': get_icon_path('watch')})
    xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action=continue_watching', listitem=li, isFolder=True)

    li = xbmcgui.ListItem('Filme')
    li.setArt({'thumb': get_icon_path('movies'), 'icon': get_icon_path('movies')})
    xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action=movies', listitem=li, isFolder=True)

    li = xbmcgui.ListItem('Seriale')
    li.setArt({'thumb': get_icon_path('tvshows'), 'icon': get_icon_path('tvshows')})
    xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action=tvshows', listitem=li, isFolder=True)

    li = xbmcgui.ListItem('Favorite')
    li.setArt({'thumb': get_icon_path('favorites'), 'icon': get_icon_path('favorites')})
    xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action=favorites', listitem=li, isFolder=True)

    li = xbmcgui.ListItem('Trakt')
    li.setArt({'thumb': get_icon_path('trakt'), 'icon': get_icon_path('trakt')})
    xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action=trakt', listitem=li, isFolder=True)

    xbmcplugin.endOfDirectory(handle)
