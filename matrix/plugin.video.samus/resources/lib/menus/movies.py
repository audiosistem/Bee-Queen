import sys
import xbmc
import xbmcgui
import xbmcplugin
from datetime import datetime
from urllib.parse import urlencode, quote
from resources.lib.utils import build_item, build_item_list, get_icon_path, normalize_genre_name
from resources.lib.tmdb import movies as tmdb_movies
from resources.lib.tmdb.api import get_genre_map

handle = int(sys.argv[1])
IMG   = 'https://image.tmdb.org/t/p/w500'


def _cm(item):
    """Context menu entries for a movie item."""
    from resources.lib import trakt as trakt_api
    title  = item.get('title') or item.get('name') or ''
    year   = (item.get('release_date') or '')[:4]
    poster = item.get('poster_path') or ''
    plot   = item.get('overview') or ''
    tid    = item['id']
    base   = sys.argv[0]
    entries = [
        ('Informații',
         f"RunPlugin({base}?action=show_info&tmdb_id={tid}&media_type=movie)"),
        ('Adaugă la Favorite',
         f"RunPlugin({base}?action=add_favorite"
         f"&tmdb_id={tid}&media_type=movie"
         f"&title={quote(title)}&year={year}&poster={quote(poster)}&plot={quote(plot)})"),
        ('Filme Similare',
         f"Container.Update({base}?action=movies_similar&tmdb_id={tid})"),
        ('Recomandate',
         f"Container.Update({base}?action=movies_recommended&tmdb_id={tid})"),
        ('Colecție',
         f"Container.Update({base}?action=movies_collection&tmdb_id={tid})"),
        ('Redă Trailer',
         f"RunPlugin({base}?action=play_trailer&tmdb_id={tid}&media_type=movie)"),
    ]
    if trakt_api.is_authenticated():
        entries += [
            ('Trakt: Adaugă la Watchlist',
             f"RunPlugin({base}?action=trakt_watchlist_add&tmdb_id={tid}&media_type=movie)"),
            ('Trakt: Șterge din Watchlist',
             f"RunPlugin({base}?action=trakt_watchlist_remove&tmdb_id={tid}&media_type=movie)"),
        ]
    return entries


def menu():
    xbmcplugin.setPluginCategory(handle, 'Filme')

    for label, action, icon_key in [
        ('Populare',   'movies_popular',    'popular'),
        ('Trending',   'movies_trending',   'trending'),
        ('Genuri',     'movies_genres',     'genres'),
        ('Ani',        'movies_years',      'ani'),
        ('Furnizori',  'movies_providers',  'furnizori'),
    ]:
        li = xbmcgui.ListItem(label)
        li.setArt({'thumb': get_icon_path(icon_key), 'icon': get_icon_path(icon_key)})
        xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action={action}', li, isFolder=True)

    li = xbmcgui.ListItem('Căutare')
    li.setArt({'thumb': get_icon_path('search'), 'icon': get_icon_path('search')})
    xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action=movies_search', li, isFolder=False)
    xbmcplugin.endOfDirectory(handle)


def search():
    keyboard = xbmcgui.Dialog().input('Caută film TMDb')
    if not keyboard:
        return
    query = keyboard.strip()
    if not query:
        return
    xbmc.executebuiltin(f'Container.Update("{sys.argv[0]}?action=movies_search_results&query={quote(query)}")')


def _show_list(data, category='', next_action='', next_params=None, page=1):
    """Generic: afișează o listă de filme din TMDb cu paginare."""
    if not data or 'results' not in data:
        xbmcgui.Dialog().notification('Samus', 'Nicio potrivire găsită.', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(handle)
        return
    if category:
        xbmcplugin.setPluginCategory(handle, category)
    xbmcplugin.setContent(handle, 'movies')
    genre_map = get_genre_map('movie')

    for item in data['results']:
        try:
            full = tmdb_movies.get_movie_details(item['id'])
            li = build_item(full) if full else build_item_list(item, genre_map)
        except Exception:
            li = build_item_list(item, genre_map)
        li.setProperty('IsPlayable', 'true')
        li.addContextMenuItems(_cm(item))
        url = f'{sys.argv[0]}?action=play_movie&tmdb_id={item["id"]}'
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=False)

    total_pages = data.get('total_pages', 1)
    if next_action and page < total_pages:
        p = dict(next_params or {})
        p['page'] = page + 1
        next_url = f"{sys.argv[0]}?{urlencode({'action': next_action, **p})}"
        next_li = xbmcgui.ListItem(f'Pagina {page + 1} →')
        next_li.setArt({'thumb': get_icon_path('next'), 'icon': get_icon_path('next')})
        xbmcplugin.addDirectoryItem(handle, url=next_url, listitem=next_li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def search_results(query):
    _show_list(tmdb_movies.search_movies(query), category=f'Rezultate: {query}')


def show_popular(page=1):
    _show_list(tmdb_movies.get_popular_movies(page), next_action='movies_popular', page=page)


def show_trending(page=1):
    _show_list(tmdb_movies.get_trending_movies(page), next_action='movies_trending', page=page)


def show_genres():
    genres = tmdb_movies.get_movie_genres()
    if not genres or 'genres' not in genres:
        xbmcgui.Dialog().notification('Samus', 'Eroare la extragerea genurilor.', xbmcgui.NOTIFICATION_ERROR)
        return
    for genre in genres['genres']:
        gid, gname = genre['id'], genre['name']
        icon = get_icon_path(normalize_genre_name(gname))
        url = f"{sys.argv[0]}?{urlencode({'action': 'movies_by_genre', 'genre_id': gid, 'genre_name': gname, 'page': 1})}"
        li = xbmcgui.ListItem(label=gname)
        li.setArt({'icon': icon, 'thumb': icon})
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def show_by_genre(genre_id, genre_name, page=1):
    _show_list(tmdb_movies.get_movies_by_genre(genre_id, page),
               category=f'Gen: {genre_name}',
               next_action='movies_by_genre',
               next_params={'genre_id': genre_id, 'genre_name': genre_name},
               page=page)


def show_years():
    icon = get_icon_path('ani')
    for year in range(datetime.now().year, 1940, -1):
        url = f"{sys.argv[0]}?{urlencode({'action': 'movies_by_year', 'year': year, 'page': 1})}"
        li = xbmcgui.ListItem(str(year))
        li.setArt({'icon': icon, 'thumb': icon})
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def show_by_year(year, page=1):
    _show_list(tmdb_movies.get_movies_by_year(year, page),
               next_action='movies_by_year',
               next_params={'year': year},
               page=page)


def show_providers():
    providers = tmdb_movies.get_movie_providers()
    if not providers or 'results' not in providers:
        xbmcgui.Dialog().notification('Samus', 'Eroare la furnizori.', xbmcgui.NOTIFICATION_ERROR)
        return
    for p in providers['results']:
        logo = p.get('logo_path', '')
        thumb = 'https://image.tmdb.org/t/p/w200' + logo if logo else ''
        li = xbmcgui.ListItem(label=p['provider_name'])
        li.setArt({'thumb': thumb, 'icon': thumb})
        url = f"{sys.argv[0]}?{urlencode({'action': 'movies_by_provider', 'provider_id': p['provider_id'], 'provider_name': p['provider_name'], 'page': 1})}"
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)


def show_by_provider(provider_id, provider_name, page=1):
    _show_list(tmdb_movies.get_movies_by_provider(provider_id, page),
               category=f'Furnizor: {provider_name}',
               next_action='movies_by_provider',
               next_params={'provider_id': provider_id, 'provider_name': provider_name},
               page=page)


def show_similar(tmdb_id, page=1):
    details = tmdb_movies.get_movie_details(tmdb_id)
    title   = details.get('title', str(tmdb_id))
    _show_list(tmdb_movies.get_similar_movies(tmdb_id, page),
               category=f'Similare: {title}',
               next_action='movies_similar',
               next_params={'tmdb_id': tmdb_id},
               page=page)


def show_recommended(tmdb_id, page=1):
    details = tmdb_movies.get_movie_details(tmdb_id)
    title   = details.get('title', str(tmdb_id))
    _show_list(tmdb_movies.get_recommended_movies(tmdb_id, page),
               category=f'Recomandate: {title}',
               next_action='movies_recommended',
               next_params={'tmdb_id': tmdb_id},
               page=page)


def show_collection(tmdb_id):
    """Deschide colecția filmului (dacă face parte dintr-una)."""
    details = tmdb_movies.get_movie_details(tmdb_id)
    coll    = details.get('belongs_to_collection')
    if not coll:
        xbmcgui.Dialog().notification('Samus', 'Filmul nu face parte dintr-o colecție.', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(handle)
        return
    coll_data = tmdb_movies.get_movie_collection(coll['id'])
    parts = coll_data.get('parts') or []
    if not parts:
        xbmcgui.Dialog().notification('Samus', 'Colecție goală.', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(handle)
        return

    xbmcplugin.setPluginCategory(handle, coll_data.get('name', 'Colecție'))
    xbmcplugin.setContent(handle, 'movies')
    genre_map = get_genre_map('movie')
    # Sortare după dată lansare
    parts.sort(key=lambda x: x.get('release_date') or '')
    for item in parts:
        li = build_item_list(item, genre_map)
        li.setProperty('IsPlayable', 'true')
        li.addContextMenuItems(_cm(item))
        url = f'{sys.argv[0]}?action=play_movie&tmdb_id={item["id"]}'
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=False)
    xbmcplugin.endOfDirectory(handle)
