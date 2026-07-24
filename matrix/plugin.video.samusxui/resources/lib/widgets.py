# -*- coding: utf-8 -*-
import concurrent.futures
import urllib.parse
import xbmcgui
import xbmcplugin

from resources.lib import tmdb, db, trakt

_ADDON_ID = 'plugin.video.samusxui'
_BASE_URL  = f'plugin://{_ADDON_ID}/'
_LOGO_TTL  = 7 * 86400  # 7 zile


def _format_rating(value):
    try:
        value = float(value or 0)
    except Exception:
        return ''
    return f'{value:.1f}' if value else ''

_CATEGORIES = [
    ('movies_popular',    'Filme populare',      'movies'),
    ('movies_trending',   'Filme trending',       'movies'),
    ('movies_cinema',     'Acum la cinema',       'movies'),
    ('tv_popular',        'Seriale populare',     'tvshows'),
    ('tv_trending',       'Seriale trending',     'tvshows'),
    ('tv_on_air',         'Pe ecrane acum',       'tvshows'),
    ('favorites_movies',  'Favorite filme',       'movies'),
    ('favorites_tv',      'Favorite seriale',     'tvshows'),
    ('continue_watching', 'Continuă vizionarea',  'episodes'),
]


def _url(**kwargs):
    return _BASE_URL + '?' + urllib.parse.urlencode(kwargs)


def _resolve_poster(path):
    if not path:
        return ''
    return path if path.startswith('http') else tmdb.poster_url(path)


def _genre_names(genre_ids, media):
    mapping = tmdb._GENRES_MOVIE if media == 'movie' else tmdb._GENRES_TV
    return [mapping[g] for g in (genre_ids or []) if g in mapping]


def _fetch_meta_cached(tmdb_id, media):
    # v4 invalidates entries created before widget logos were exposed to skins.
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


def _apply_meta(entries):
    """Fetch logo/runtime/tagline in parallel and apply to list items."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {
            ex.submit(_fetch_meta_cached, tmdb_id, media): (li, art, tag)
            for tmdb_id, media, li, art, tag in entries
        }
        for fut in concurrent.futures.as_completed(futures):
            li, art, tag = futures[fut]
            try:
                meta = fut.result() or {}
            except Exception:
                continue
            if meta.get('logo'):
                art['clearlogo'] = meta['logo']
                li.setProperty('logo', meta['logo'])
            li.setArt(art)
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


def _movie_item(item):
    tmdb_id    = item.get('id')
    title      = item.get('title') or item.get('name', '')
    premiered  = item.get('release_date') or ''
    year_str   = premiered[:4]
    votes      = int(item.get('vote_count') or 0)
    poster     = tmdb.poster_url(item.get('poster_path', ''))
    fanart     = tmdb.backdrop_url(item.get('backdrop_path', ''))
    genres     = _genre_names(item.get('genre_ids'), 'movie')
    li  = xbmcgui.ListItem(title)
    tag = li.getVideoInfoTag()
    tag.setMediaType('movie')
    tag.setTitle(title)
    tag.setYear(int(year_str) if year_str.isdigit() else 0)
    tag.setPremiered(premiered)
    tag.setPlot(item.get('overview', ''))
    tag.setRating(float(item.get('vote_average') or 0), votes=votes, isdefault=True)
    tag.setGenres(genres)
    li.setProperty('tmdb_rating', _format_rating(item.get('vote_average')))
    li.setProperty('genre', tmdb.genre_names(item.get('genre_ids'), 'movie').upper())
    art = {'poster': poster, 'thumb': poster, 'fanart': fanart}
    li.setArt(art)
    url = _url(action='show_info', tmdb_id=tmdb_id, media_type='movie')
    return (url, li, False), (tmdb_id, 'movie', li, art, tag)


def _tv_item(item):
    tmdb_id    = item.get('id')
    title      = item.get('name') or item.get('title', '')
    first_air  = item.get('first_air_date') or ''
    year_str   = first_air[:4]
    votes      = int(item.get('vote_count') or 0)
    poster     = tmdb.poster_url(item.get('poster_path', ''))
    fanart     = tmdb.backdrop_url(item.get('backdrop_path', ''))
    genres     = _genre_names(item.get('genre_ids'), 'tv')
    li  = xbmcgui.ListItem(title)
    tag = li.getVideoInfoTag()
    tag.setMediaType('tvshow')
    tag.setTitle(title)
    tag.setYear(int(year_str) if year_str.isdigit() else 0)
    tag.setPremiered(first_air)
    tag.setFirstAired(first_air)
    tag.setPlot(item.get('overview', ''))
    tag.setRating(float(item.get('vote_average') or 0), votes=votes, isdefault=True)
    tag.setGenres(genres)
    li.setProperty('tmdb_rating', _format_rating(item.get('vote_average')))
    li.setProperty('genre', tmdb.genre_names(item.get('genre_ids'), 'tv').upper())
    art = {'poster': poster, 'thumb': poster, 'fanart': fanart}
    li.setArt(art)
    url = _url(action='show_info', tmdb_id=tmdb_id, media_type='tv')
    return (url, li, False), (tmdb_id, 'tv', li, art, tag)


def handle_widget(handle, params):
    widget_type = params.get('type', '')

    if not widget_type:
        items = []
        for cat_id, cat_label, _ in _CATEGORIES:
            li = xbmcgui.ListItem(cat_label)
            li.setProperty('IsPlayable', 'false')
            items.append((_url(action='widget', type=cat_id), li, True))
        xbmcplugin.addDirectoryItems(handle, items)
        xbmcplugin.endOfDirectory(handle)
        return

    results = []
    meta_entries = []
    content  = 'movies'

    if widget_type == 'movies_popular':
        data = tmdb.popular('movie')
        for i in data.get('results', [])[:20]:
            r, e = _movie_item(i)
            results.append(r); meta_entries.append(e)
        content = 'movies'

    elif widget_type == 'movies_trending':
        data = tmdb.trending('movie')
        for i in data.get('results', [])[:20]:
            r, e = _movie_item(i)
            results.append(r); meta_entries.append(e)
        content = 'movies'

    elif widget_type == 'movies_cinema':
        data = tmdb.now_playing()
        for i in data.get('results', [])[:20]:
            r, e = _movie_item(i)
            results.append(r); meta_entries.append(e)
        content = 'movies'

    elif widget_type == 'tv_popular':
        data = tmdb.popular('tv')
        for i in data.get('results', [])[:20]:
            r, e = _tv_item(i)
            results.append(r); meta_entries.append(e)
        content = 'tvshows'

    elif widget_type == 'tv_trending':
        data = tmdb.trending('tv')
        for i in data.get('results', [])[:20]:
            r, e = _tv_item(i)
            results.append(r); meta_entries.append(e)
        content = 'tvshows'

    elif widget_type == 'tv_on_air':
        data = tmdb.on_the_air()
        for i in data.get('results', [])[:20]:
            r, e = _tv_item(i)
            results.append(r); meta_entries.append(e)
        content = 'tvshows'

    elif widget_type == 'favorites_movies':
        for f in db.get_favorites('movie')[:20]:
            li       = xbmcgui.ListItem(f['title'])
            year_val = int(f['year']) if (f.get('year') or '').isdigit() else 0
            tag = li.getVideoInfoTag()
            tag.setMediaType('movie')
            tag.setTitle(f['title'])
            tag.setYear(year_val)
            tag.setPlot(f.get('plot', ''))
            poster = _resolve_poster(f.get('poster', ''))
            art = {'poster': poster, 'thumb': poster}
            li.setArt(art)
            results.append((_url(action='show_info', tmdb_id=f['tmdb_id'], media_type='movie'), li, False))
            meta_entries.append((f['tmdb_id'], 'movie', li, art, tag))
        content = 'movies'

    elif widget_type == 'favorites_tv':
        for f in db.get_favorites('tv')[:20]:
            li       = xbmcgui.ListItem(f['title'])
            year_val = int(f['year']) if (f.get('year') or '').isdigit() else 0
            tag = li.getVideoInfoTag()
            tag.setMediaType('tvshow')
            tag.setTitle(f['title'])
            tag.setYear(year_val)
            tag.setPlot(f.get('plot', ''))
            poster = _resolve_poster(f.get('poster', ''))
            art = {'poster': poster, 'thumb': poster}
            li.setArt(art)
            results.append((_url(action='show_info', tmdb_id=f['tmdb_id'], media_type='tv'), li, False))
            meta_entries.append((f['tmdb_id'], 'tv', li, art, tag))
        content = 'tvshows'

    elif widget_type == 'continue_watching':
        for c in db.get_continue_watching()[:20]:
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
            art = {'poster': poster, 'thumb': poster}
            li.setArt(art)
            url = _url(action='show_info', tmdb_id=c['tmdb_id'],
                       media_type='movie' if media == 'movie' else 'tv')
            results.append((url, li, False))
            meta_entries.append((c['tmdb_id'], media, li, art, tag))
        content = 'episodes'

    _apply_meta(meta_entries)

    xbmcplugin.setContent(handle, content)
    xbmcplugin.addDirectoryItems(handle, results)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
