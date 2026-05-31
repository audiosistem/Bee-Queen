import sys
import xbmc
import xbmcgui
import xbmcplugin
from datetime import datetime
from urllib.parse import urlencode, quote
from resources.lib.tmdb import tv as tmdb_tv
from resources.lib.utils import get_icon_path, normalize_genre_name, build_item_tvshow, build_item_tvshow_list
from resources.lib.tmdb.api import get_genre_map

handle = int(sys.argv[1])


def _cm(item):
    """Context menu entries for a tvshow item."""
    from resources.lib import trakt as trakt_api
    title  = item.get('name') or item.get('title') or ''
    year   = (item.get('first_air_date') or '')[:4]
    poster = item.get('poster_path') or ''
    plot   = item.get('overview') or ''
    tid    = item['id']
    base   = sys.argv[0]
    entries = [
        ('Informații',
         f"RunPlugin({base}?action=show_info&tmdb_id={tid}&media_type=tv)"),
        ('Adaugă la Favorite',
         f"RunPlugin({base}?action=add_favorite"
         f"&tmdb_id={tid}&media_type=tvshow"
         f"&title={quote(title)}&year={year}&poster={quote(poster)}&plot={quote(plot)})"),
        ('Seriale Similare',
         f"Container.Update({base}?action=tvshows_similar&tv_id={tid})"),
        ('Recomandate',
         f"Container.Update({base}?action=tvshows_recommended&tv_id={tid})"),
        ('Redă Trailer',
         f"RunPlugin({base}?action=play_trailer&tmdb_id={tid}&media_type=tv)"),
    ]
    if trakt_api.is_authenticated():
        entries += [
            ('Trakt: Adaugă la Watchlist',
             f"RunPlugin({base}?action=trakt_watchlist_add&tmdb_id={tid}&media_type=tvshow)"),
            ('Trakt: Șterge din Watchlist',
             f"RunPlugin({base}?action=trakt_watchlist_remove&tmdb_id={tid}&media_type=tvshow)"),
        ]
    return entries


def menu():
    xbmcplugin.setPluginCategory(handle, 'Seriale')

    for label, action, icon_key in [
        ('Populare',   'tvshows_popular',    'popular'),
        ('Trending',   'tvshows_trending',   'trending'),
        ('Genuri',     'tvshows_genres',     'genres'),
        ('Ani',        'tvshows_years',      'ani'),
        ('Furnizori',  'tvshows_providers',  'furnizori'),
    ]:
        li = xbmcgui.ListItem(label)
        li.setArt({'thumb': get_icon_path(icon_key), 'icon': get_icon_path(icon_key)})
        xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action={action}', li, isFolder=True)

    li = xbmcgui.ListItem('Căutare')
    li.setArt({'thumb': get_icon_path('search'), 'icon': get_icon_path('search')})
    xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action=tvshows_search', li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def search():
    keyboard = xbmcgui.Dialog().input('Caută serial TMDb')
    if not keyboard:
        return
    results = tmdb_tv.search_tvshows(keyboard)
    if not results or 'results' not in results:
        xbmcgui.Dialog().notification('Samus', 'Nicio potrivire găsită.', xbmcgui.NOTIFICATION_INFO)
        return
    xbmcplugin.setContent(handle, 'tvshows')
    genre_map = get_genre_map('tv')
    for item in results['results']:
        try:
            full = tmdb_tv.get_tv_details(item['id'])
            li = build_item_tvshow(full) if full else build_item_tvshow_list(item, genre_map)
        except Exception:
            li = build_item_tvshow_list(item, genre_map)
        li.addContextMenuItems(_cm(item))
        url = f'{sys.argv[0]}?action=tv_details&id={item["id"]}'
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def _show_list(data, category='', next_action='', next_params=None, page=1):
    """Generic: afișează o listă de seriale din TMDb cu paginare."""
    if not data or 'results' not in data:
        xbmcgui.Dialog().notification('Samus', 'Nicio potrivire găsită.', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(handle)
        return
    if category:
        xbmcplugin.setPluginCategory(handle, category)
    xbmcplugin.setContent(handle, 'tvshows')
    genre_map = get_genre_map('tv')

    for item in data['results']:
        try:
            full = tmdb_tv.get_tv_details(item['id'])
            li = build_item_tvshow(full) if full else build_item_tvshow_list(item, genre_map)
        except Exception:
            li = build_item_tvshow_list(item, genre_map)
        li.addContextMenuItems(_cm(item))
        url = f'{sys.argv[0]}?action=tv_details&id={item["id"]}'
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)
    total_pages = data.get('total_pages', 1)
    if next_action and page < total_pages:
        p = dict(next_params or {})
        p['page'] = page + 1
        next_url = f"{sys.argv[0]}?{urlencode({'action': next_action, **p})}"
        next_li = xbmcgui.ListItem(f'Pagina {page + 1} →')
        next_li.setArt({'thumb': get_icon_path('next'), 'icon': get_icon_path('next')})
        xbmcplugin.addDirectoryItem(handle, url=next_url, listitem=next_li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def show_popular(page=1):
    _show_list(tmdb_tv.get_popular_tv(page), next_action='tvshows_popular', page=page)


def show_trending(page=1):
    _show_list(tmdb_tv.get_trending_tv(page), next_action='tvshows_trending', page=page)


def show_genres():
    genres = tmdb_tv.get_tv_genres()
    if not genres or 'genres' not in genres:
        xbmcgui.Dialog().notification('Samus', 'Eroare la genuri.', xbmcgui.NOTIFICATION_ERROR)
        return
    for genre in genres['genres']:
        gid, gname = genre['id'], genre['name']
        icon = get_icon_path(normalize_genre_name(gname))
        url = f"{sys.argv[0]}?{urlencode({'action': 'tvshows_by_genre', 'genre_id': gid, 'genre_name': gname, 'page': 1})}"
        li = xbmcgui.ListItem(label=gname)
        li.setArt({'icon': icon, 'thumb': icon})
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def show_by_genre(genre_id, genre_name, page=1):
    _show_list(tmdb_tv.get_tv_by_genre(genre_id, page),
               category=f'Gen: {genre_name}',
               next_action='tvshows_by_genre',
               next_params={'genre_id': genre_id, 'genre_name': genre_name},
               page=page)


def show_years():
    icon = get_icon_path('ani')
    for year in range(datetime.now().year, 1940, -1):
        url = f"{sys.argv[0]}?{urlencode({'action': 'tvshows_by_year', 'year': year, 'page': 1})}"
        li = xbmcgui.ListItem(str(year))
        li.setArt({'icon': icon, 'thumb': icon})
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def show_by_year(year, page=1):
    _show_list(tmdb_tv.get_tv_by_year(year, page),
               next_action='tvshows_by_year',
               next_params={'year': year},
               page=page)


def show_providers():
    providers = tmdb_tv.get_tv_providers()
    if not providers or 'results' not in providers:
        xbmcgui.Dialog().notification('Samus', 'Eroare la furnizori.', xbmcgui.NOTIFICATION_ERROR)
        return
    for p in providers['results']:
        logo = p.get('logo_path', '')
        thumb = 'https://image.tmdb.org/t/p/w200' + logo if logo else ''
        li = xbmcgui.ListItem(label=p['provider_name'])
        li.setArt({'thumb': thumb, 'icon': thumb})
        url = f"{sys.argv[0]}?{urlencode({'action': 'tvshows_by_provider', 'provider_id': p['provider_id'], 'provider_name': p['provider_name'], 'page': 1})}"
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def show_by_provider(provider_id, provider_name, page=1):
    _show_list(tmdb_tv.get_tv_by_provider(provider_id, page),
               category=f'Furnizor: {provider_name}',
               next_action='tvshows_by_provider',
               next_params={'provider_id': provider_id, 'provider_name': provider_name},
               page=page)


def show_similar(tv_id, page=1):
    details = tmdb_tv.get_tv_details(tv_id)
    title   = details.get('name', str(tv_id))
    _show_list(tmdb_tv.get_similar_tv(tv_id, page),
               category=f'Similare: {title}',
               next_action='tvshows_similar',
               next_params={'tv_id': tv_id},
               page=page)


def show_recommended(tv_id, page=1):
    details = tmdb_tv.get_tv_details(tv_id)
    title   = details.get('name', str(tv_id))
    _show_list(tmdb_tv.get_recommended_tv(tv_id, page),
               category=f'Recomandate: {title}',
               next_action='tvshows_recommended',
               next_params={'tv_id': tv_id},
               page=page)


def show_seasons(tv_id):
    details = tmdb_tv.get_tv_details(tv_id)
    if not details or 'seasons' not in details:
        xbmcgui.Dialog().notification('Samus', 'Nu s-au găsit sezoane.', xbmcgui.NOTIFICATION_ERROR)
        return

    fanart = 'https://image.tmdb.org/t/p/w500' + (details.get('backdrop_path') or '')
    poster = 'https://image.tmdb.org/t/p/w500' + (details.get('poster_path') or '')

    for season in details['seasons']:
        name = season.get('name') or f"Sezonul {season['season_number']}"
        url = f"{sys.argv[0]}?{urlencode({'action': 'tv_season', 'tv_id': tv_id, 'season': season['season_number']})}"
        li = xbmcgui.ListItem(name)
        li.setArt({
            'thumb': 'https://image.tmdb.org/t/p/w500' + (season.get('poster_path') or details.get('poster_path') or ''),
            'fanart': fanart,
        })
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def show_episodes(tv_id, season_number):
    season  = tmdb_tv.get_season(tv_id, season_number)
    details = tmdb_tv.get_tv_details(tv_id)
    if not season or 'episodes' not in season:
        xbmcgui.Dialog().notification('Samus', 'Nu s-au găsit episoade.', xbmcgui.NOTIFICATION_ERROR)
        return

    show_title = details.get('name', '')
    fanart     = 'https://image.tmdb.org/t/p/w500' + (details.get('backdrop_path') or '')

    # Fallback EN pentru episoadele fără descriere
    episodes_en = {}
    if any(not ep.get('overview') for ep in season['episodes']):
        season_en = tmdb_tv.get_season(tv_id, season_number, language='en')
        if season_en:
            episodes_en = {ep['episode_number']: ep.get('overview', '') for ep in season_en.get('episodes', [])}

    xbmcplugin.setContent(handle, 'episodes')

    from resources.lib import db
    for ep in season['episodes']:
        ep_num  = ep['episode_number']
        name    = ep.get('name') or f"Episodul {ep_num}"
        plot    = ep.get('overview') or episodes_en.get(ep_num, '')
        air_date= ep.get('air_date', '')
        rating  = ep.get('vote_average') or 0
        votes   = int(ep.get('vote_count') or 0)
        runtime = ep.get('runtime') or 0

        li = xbmcgui.ListItem(name)
        li.setProperty('IsPlayable', 'true')
        li.setArt({
            'thumb':  'https://image.tmdb.org/t/p/w500' + (ep.get('still_path') or details.get('poster_path') or ''),
            'fanart': fanart,
            'poster': 'https://image.tmdb.org/t/p/w500' + (details.get('poster_path') or ''),
        })

        info = li.getVideoInfoTag()
        info.setTitle(name)
        info.setTvShowTitle(show_title)
        info.setSeason(season_number)
        info.setEpisode(ep_num)
        info.setPlot(plot)
        info.setPlotOutline(plot)
        if air_date:
            info.setPremiered(air_date)
            info.setFirstAired(air_date)
        if rating:
            info.setRating(rating)
        if votes:
            info.setVotes(votes)
        if runtime:
            info.setDuration(runtime * 60)
        info.setMediaType('episode')

        # Marchează episoadele văzute
        h = db.history_get(details.get('id', tv_id), 'tv', season=season_number, episode=ep_num)
        if h and h['watched']:
            li.setProperty('WatchedState', 'true')

        url = f"{sys.argv[0]}?{urlencode({'action': 'play_episode', 'tv_id': tv_id, 'season': season_number, 'episode': ep_num})}"
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=False)

    xbmcplugin.endOfDirectory(handle)
