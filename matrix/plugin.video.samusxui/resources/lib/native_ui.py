# -*- coding: utf-8 -*-
import concurrent.futures
import json
import os
import time
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib import tmdb, db, trakt

_SEARCH_STATE = xbmcvfs.translatePath('special://temp/samusxui_search.json')

_LOGO_TTL = 7 * 86400


def _format_rating(value):
    try:
        value = float(value or 0)
    except Exception:
        return ''
    return f'{value:.1f}' if value else ''


def _fetch_widget_meta_cached(tmdb_id, media):
    key = f'wmeta6_{media}_{tmdb_id}'
    cached = db.cache_get(key, _LOGO_TTL)
    if isinstance(cached, dict):
        return cached
    meta = tmdb.widget_meta(tmdb_id, media)
    tr = trakt.rating_for_tmdb(tmdb_id, media)
    if tr:
        meta['trakt_rating'] = tr
    db.cache_set(key, meta)
    return meta


def _apply_widget_meta(items):
    entries = []
    for _, li, _ in items:
        tmdb_id = li.getProperty('tmdb_id')
        media = li.getProperty('media_type') or 'movie'
        if tmdb_id:
            entries.append((tmdb_id, media, li, li.getVideoInfoTag()))
    if not entries:
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {
            ex.submit(_fetch_widget_meta_cached, tmdb_id, media): (li, tag)
            for tmdb_id, media, li, tag in entries
        }
        for fut in concurrent.futures.as_completed(futures):
            li, tag = futures[fut]
            try:
                meta = fut.result() or {}
            except Exception:
                continue
            logo = meta.get('logo')
            if logo:
                li.setArt({'clearlogo': logo})
                li.setProperty('logo', logo)
            if meta.get('tagline'):
                li.setProperty('tagline', meta['tagline'])
                tag.setTagLine(meta['tagline'])
            if meta.get('runtime'):
                rt = meta['runtime']
                rt_str = f'{rt // 60}h {rt % 60:02d}m' if rt >= 60 else f'{rt}m'
                li.setProperty('duration', rt_str)
                tag.setDuration(rt * 60)
            if meta.get('tmdb_rating'):
                li.setProperty('tmdb_rating', _format_rating(meta.get('tmdb_rating')))
            if meta.get('trakt_rating'):
                li.setProperty('trakt_rating', _format_rating(meta.get('trakt_rating')))
            if meta.get('age_cert'):
                li.setProperty('age_cert', meta.get('age_cert'))
                li.setProperty('age_cert_adult', 'true' if meta.get('age_cert') == '+18' else 'false')
            if meta.get('trailer_key'):
                li.setProperty('trailer_key', meta['trailer_key'])


def _search_save(query, media):
    try:
        with open(_SEARCH_STATE, 'w') as f:
            json.dump({'q': query, 'm': media, 'ts': time.time()}, f)
    except Exception:
        pass


def _search_load():
    try:
        with open(_SEARCH_STATE) as f:
            d = json.load(f)
        if time.time() - d.get('ts', 0) < 600:
            return d.get('q', ''), d.get('m', 'movie')
    except Exception:
        pass
    return '', ''

_ADDON_ID   = 'plugin.video.samusxui'
_ADDON_PATH = xbmcaddon.Addon(_ADDON_ID).getAddonInfo('path')
_BASE_URL   = f'plugin://{_ADDON_ID}/'
_THRAX_SKIN_ID = 'skin.aeon.nox.thrax'
_MYFLIX_VIEW_ID = 509
_MYFLIX_TRANSITION_PROPERTY = 'samusxui_myflix_transition'

_GENRES_MOVIE = [
    (28,    'Acțiune',   'actiune.png'),
    (12,    'Aventură',  'aventuri.png'),
    (16,    'Animație',  'animatie.png'),
    (35,    'Comedie',   'comedie.png'),
    (80,    'Crimă',     'crima.png'),
    (99,    'Documentar','documentar.png'),
    (18,    'Dramă',     'drama.png'),
    (10751, 'Familie',   'familie.png'),
    (14,    'Fantezie',  'fantezie.png'),
    (36,    'Istorie',   'istoric.png'),
    (27,    'Horror',    'horror.png'),
    (9648,  'Mister',    'mister.png'),
    (10749, 'Romantism', 'romantic.png'),
    (878,   'SF',        'sf.png'),
    (53,    'Thriller',  'thriller.png'),
    (10752, 'Război',    'razboi.png'),
    (37,    'Western',   'western.png'),
]

_GENRES_TV = [
    (10759, 'Acțiune',    'actiune.png'),
    (16,    'Animație',   'animatie.png'),
    (35,    'Comedie',    'comedie.png'),
    (80,    'Crimă',      'crima.png'),
    (99,    'Documentar', 'documentar.png'),
    (18,    'Dramă',      'drama.png'),
    (10751, 'Familie',    'familie.png'),
    (10765, 'SF & Fantasy','sf.png'),
    (9648,  'Mister',     'mister.png'),
    (10764, 'Reality',    'reality.png'),
    (37,    'Western',    'western.png'),
]


def _url(**kwargs):
    return _BASE_URL + '?' + urllib.parse.urlencode(kwargs)


def _icon(filename):
    return os.path.join(_ADDON_PATH, 'resources', 'skins', 'Default', 'media', filename)


def _genre_list(genre_ids, media):
    mapping = tmdb._GENRES_MOVIE if media == 'movie' else tmdb._GENRES_TV
    return [mapping[genre_id] for genre_id in (genre_ids or []) if genre_id in mapping]


def _folder_item(label, url, icon=None):
    li = xbmcgui.ListItem(label)
    li.setProperty('IsPlayable', 'false')
    if icon:
        li.setArt({'thumb': icon, 'icon': icon})
    return (url, li, True)


def _end_media_directory(handle):
    use_myflix = (xbmc.getSkinDir() == _THRAX_SKIN_ID and
                  not xbmc.getCondVisibility('Skin.HasSetting(Disable.MyFlixView)'))
    home_window = xbmcgui.Window(10000)
    if use_myflix:
        home_window.setProperty(_MYFLIX_TRANSITION_PROPERTY, '1')
        home_window.setProperty('actualViewtype', 'MyFlix')
    try:
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        if use_myflix:
            xbmc.sleep(200)
            xbmc.executebuiltin(f'Container.SetViewMode({_MYFLIX_VIEW_ID})')
            for _ in range(15):
                if xbmc.getCondVisibility(f'Control.IsVisible({_MYFLIX_VIEW_ID})'):
                    break
                xbmc.sleep(20)
    finally:
        if use_myflix:
            home_window.clearProperty(_MYFLIX_TRANSITION_PROPERTY)


def _movie_li(item):
    tmdb_id  = item.get('id')
    title    = item.get('title') or item.get('name', '')
    year_str = (item.get('release_date') or '')[:4]
    poster   = tmdb.poster_url(item.get('poster_path', ''))
    fanart   = tmdb.backdrop_url(item.get('backdrop_path', ''))
    li  = xbmcgui.ListItem(title)
    tag = li.getVideoInfoTag()
    tag.setMediaType('movie')
    tag.setTitle(title)
    tag.setYear(int(year_str) if year_str.isdigit() else 0)
    tag.setPlot(item.get('overview', ''))
    tag.setRating(float(item.get('vote_average') or 0))
    tag.setGenres(_genre_list(item.get('genre_ids'), 'movie'))
    li.setProperty('genre', tmdb.genre_names(item.get('genre_ids'), 'movie').upper())
    li.setProperty('tmdb_rating', _format_rating(item.get('vote_average')))
    li.setArt({'poster': poster, 'thumb': poster, 'fanart': fanart})
    li.setProperty('tmdb_id', str(tmdb_id))
    li.setProperty('media_type', 'movie')
    return (_url(action='show_info', tmdb_id=tmdb_id, media_type='movie'), li, False)


def _tv_li(item):
    tmdb_id  = item.get('id')
    title    = item.get('name') or item.get('title', '')
    year_str = (item.get('first_air_date') or '')[:4]
    poster   = tmdb.poster_url(item.get('poster_path', ''))
    fanart   = tmdb.backdrop_url(item.get('backdrop_path', ''))
    li  = xbmcgui.ListItem(title)
    tag = li.getVideoInfoTag()
    tag.setMediaType('tvshow')
    tag.setTitle(title)
    tag.setYear(int(year_str) if year_str.isdigit() else 0)
    tag.setPlot(item.get('overview', ''))
    tag.setRating(float(item.get('vote_average') or 0))
    tag.setGenres(_genre_list(item.get('genre_ids'), 'tv'))
    li.setProperty('genre', tmdb.genre_names(item.get('genre_ids'), 'tv').upper())
    li.setProperty('tmdb_rating', _format_rating(item.get('vote_average')))
    li.setArt({'poster': poster, 'thumb': poster, 'fanart': fanart})
    li.setProperty('tmdb_id', str(tmdb_id))
    li.setProperty('media_type', 'tv')
    return (_url(action='show_info', tmdb_id=tmdb_id, media_type='tv'), li, False)


def _resolve_poster(path):
    if not path:
        return ''
    return path if path.startswith('http') else tmdb.poster_url(path)


# ── dispatcher ────────────────────────────────────────────────────────────────

def handle_native(handle, params):
    section = params.get('section', '')

    if not section:
        _root(handle)
    elif section == 'movies':
        _section_movies(handle)
    elif section == 'tv':
        _section_tv(handle)
    elif section == 'content':
        _content(handle, params)
    elif section == 'favorites':
        _favorites(handle)
    elif section == 'continue':
        _continue_watching(handle)
    elif section == 'search':
        _search(handle, params)
    else:
        xbmcplugin.endOfDirectory(handle, succeeded=False)


# ── secțiuni ─────────────────────────────────────────────────────────────────

def _root(handle):
    items = [
        _folder_item('Filme',               _url(action='submenu', section='movies'),
                     _icon('movies.png')),
        _folder_item('Seriale',             _url(action='submenu', section='tv'),
                     _icon('tvshows.png')),
        _folder_item('Favorite',            _url(action='submenu', section='favorites'),
                     _icon('favorites.png')),
        _folder_item('Continuă vizionarea', _url(action='submenu', section='continue'),
                     _icon('watch.png')),
        _folder_item('Căutare',             _url(action='submenu', section='search'),
                     _icon('search.png')),
    ]
    xbmcplugin.addDirectoryItems(handle, items)
    xbmcplugin.endOfDirectory(handle)


def _section_movies(handle):
    items = [
        _folder_item('Populare',       _url(action='submenu', section='content', media='movie', type='popular'),   _icon('popular.png')),
        _folder_item('Trending',       _url(action='submenu', section='content', media='movie', type='trending'),  _icon('trending.png')),
        _folder_item('Acum la cinema', _url(action='submenu', section='content', media='movie', type='cinema'),    _icon('filmtv.png')),
        _folder_item('Top Rated',      _url(action='submenu', section='content', media='movie', type='top_rated'), _icon('popular.png')),
    ] + [
        _folder_item(label, _url(action='submenu', section='content', media='movie', type='genre', genre_id=gid), _icon(icon))
        for gid, label, icon in _GENRES_MOVIE
    ]
    xbmcplugin.addDirectoryItems(handle, items)
    xbmcplugin.endOfDirectory(handle)


def _section_tv(handle):
    items = [
        _folder_item('Populare',  _url(action='submenu', section='content', media='tv', type='popular'),   _icon('popular.png')),
        _folder_item('Trending',  _url(action='submenu', section='content', media='tv', type='trending'),  _icon('trending.png')),
        _folder_item('Pe ecrane', _url(action='submenu', section='content', media='tv', type='on_air'),    _icon('filmtv.png')),
        _folder_item('Top Rated', _url(action='submenu', section='content', media='tv', type='top_rated'), _icon('popular.png')),
    ] + [
        _folder_item(label, _url(action='submenu', section='content', media='tv', type='genre', genre_id=gid), _icon(icon))
        for gid, label, icon in _GENRES_TV
    ]
    xbmcplugin.addDirectoryItems(handle, items)
    xbmcplugin.endOfDirectory(handle)


def _content(handle, params):
    media    = params.get('media', 'movie')
    ctype    = params.get('type', 'popular')
    genre_id = params.get('genre_id', '')
    page     = int(params.get('page', 1))

    if ctype == 'popular':
        data = tmdb.popular(media, page=page)
    elif ctype == 'trending':
        data = tmdb.trending(media, page=page)
    elif ctype == 'cinema':
        data = tmdb.now_playing(page=page)
    elif ctype == 'on_air':
        data = tmdb.on_the_air(page=page)
    elif ctype == 'top_rated':
        data = tmdb.top_rated(media, page=page)
    elif ctype == 'genre' and genre_id:
        data = tmdb.popular(media, genre_id=int(genre_id), page=page)
    else:
        data = {}

    results     = data.get('results', [])
    total_pages = data.get('total_pages', 1)

    if media == 'movie':
        items   = [_movie_li(i) for i in results]
        content = 'movies'
    else:
        items   = [_tv_li(i) for i in results]
        content = 'tvshows'

    _apply_widget_meta(items)

    if page < total_pages:
        next_params = {**params, 'page': page + 1}
        next_url    = _BASE_URL + '?' + urllib.parse.urlencode(next_params)
        li = xbmcgui.ListItem('Pagina următoare »')
        li.setProperty('IsPlayable', 'false')
        li.setArt({'thumb': _icon('next.png'), 'icon': _icon('next.png')})
        items.append((next_url, li, True))

    xbmcplugin.setContent(handle, content)
    xbmcplugin.addDirectoryItems(handle, items)
    _end_media_directory(handle)


def _favorites(handle):
    items = []
    for f in db.get_favorites():
        media    = f['media_type']
        li       = xbmcgui.ListItem(f['title'])
        year_val = int(f['year']) if (f.get('year') or '').isdigit() else 0
        tag = li.getVideoInfoTag()
        tag.setMediaType('movie' if media == 'movie' else 'tvshow')
        tag.setTitle(f['title'])
        tag.setYear(year_val)
        tag.setPlot(f.get('plot', ''))
        poster = _resolve_poster(f.get('poster', ''))
        li.setArt({'poster': poster, 'thumb': poster})
        items.append((_url(action='show_info', tmdb_id=f['tmdb_id'], media_type=media), li, False))
    xbmcplugin.setContent(handle, 'movies')
    xbmcplugin.addDirectoryItems(handle, items)
    _end_media_directory(handle)


def _continue_watching(handle):
    items = []
    for c in db.get_continue_watching():
        media = c['media_type']
        li    = xbmcgui.ListItem(c['title'])
        tag   = li.getVideoInfoTag()
        tag.setMediaType('movie' if media == 'movie' else 'episode')
        tag.setTitle(c['title'])
        tag.setPlot(c.get('plot', ''))
        if c.get('season') is not None:
            tag.setSeason(c['season'])
            tag.setEpisode(c.get('episode') or 0)
        poster = _resolve_poster(c.get('poster', ''))
        li.setArt({'poster': poster, 'thumb': poster})
        url = _url(action='show_info', tmdb_id=c['tmdb_id'],
                   media_type='movie' if media == 'movie' else 'tv')
        items.append((url, li, False))
    xbmcplugin.setContent(handle, 'episodes')
    xbmcplugin.addDirectoryItems(handle, items)
    _end_media_directory(handle)


def _search(handle, params):
    force_new = params.get('new') == '1'
    query     = params.get('query', '')
    media     = params.get('media', '')

    # On Kodi re-request (no query in params, no force_new) use cached state to skip dialog
    if not query and not force_new:
        query, media = _search_load()

    if not query:
        query = xbmcgui.Dialog().input('Caută')
        if not query:
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return

    if not media:
        choice = xbmcgui.Dialog().select('Tip media', ['Filme', 'Seriale'])
        if choice < 0:
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return
        media = 'movie' if choice == 0 else 'tv'

    _search_save(query, media)

    data    = tmdb.search(media, query)
    results = data.get('results', [])

    if media == 'movie':
        items   = [_movie_li(i) for i in results]
        content = 'movies'
    else:
        items   = [_tv_li(i) for i in results]
        content = 'tvshows'

    _apply_widget_meta(items)

    # "Caută din nou" item at top — force_new=1 bypasses cache
    new_li = xbmcgui.ListItem(f'» Caută din nou  [I](acum: {query})[/I]')
    new_li.setProperty('IsPlayable', 'false')
    new_li.setArt({'thumb': _icon('search.png'), 'icon': _icon('search.png')})
    items.insert(0, (_url(action='submenu', section='search', new='1'), new_li, True))

    xbmcplugin.setPluginCategory(handle, f'Căutare: {query}')
    xbmcplugin.setContent(handle, content)
    xbmcplugin.addDirectoryItems(handle, items)
    _end_media_directory(handle)
