import os
import xbmc
import xbmcgui
import xbmcaddon
from urllib.parse import quote
from .tmdb.api import tmdb_request, tmdb_cached, get_genre_map, TTL_DETAILS

addon = xbmcaddon.Addon()
IMG_BASE = 'https://image.tmdb.org/t/p/w500'
FANART_BASE = 'https://image.tmdb.org/t/p/original'
ICON_PATH = os.path.join(addon.getAddonInfo('path'), 'resources', 'media', 'icons')
LANGUAGE = addon.getSetting('language') or 'ro'
GENRE_ICON_MAP = {
    "aventuri": ["Acţiune & Aventuri", "Acțiune & Aventuri", "Action & Adventure", "Aventuri", "Adventure"],
    "razboi": ["Război", "Razboi", "Război & Politică", "Razboi & Politica", "War & Politics", "War"],
    "sf": ["SF", "Sci-Fi", "SF & Fantasy", "SF și Fantezie", "Sci-Fi & Fantasy", "Science Fiction"],
    "filmtv": ["Film TV", "TV Movie"],
    "animatie": ["Animație", "Animatie", "Animation"],
    "stiri": ["Știri", "Stiri", "News"],
    "soap": ["Telenovelă", "Telenovela", "Soap"],
    "reality": ["Reality"],
    "copii": ["Copii", "Kids"],
    "romantic": ["Romantic", "Romance"],
    "mister": ["Mister", "Mystery"],
    "crima": ["Crimă", "Crima", "Crime"],
    "actiune": ["Acțiune", "Actiune", "Action"],
    "drama": ["Dramă", "Drama"],
    "fantezie": ["Fantezie", "Fantasy"],
    "comedie": ["Comedie", "Comedy"],
    "western": ["Western"],
    "horror": ["Horror"],
    "documentar": ["Documentar", "Documentary"],
    "muzica": ["Muzical", "Music"],
    "istoric": ["Istoric", "History"],
    "familie": ["Familie", "Family"],
    "thriller": ["Thriller"],
    "talkshow": ["Talk", "Talkshow"]
}


def build_item_list(item, genre_map=None):
    """Construiește ListItem din datele unui endpoint de listing (fără apel API suplimentar)."""
    title = item.get('title') or item.get('name') or 'Fără titlu'
    year = (item.get('release_date') or '')[:4]
    rating = item.get('vote_average') or 0
    votes = int(item.get('vote_count') or 0)
    premiered = item.get('release_date', '')
    plot = item.get('overview', '')

    if genre_map is None:
        genre_map = get_genre_map('movie')
    genres_list = [genre_map[gid] for gid in item.get('genre_ids', []) if gid in genre_map]

    label = f"{title} ({year})" if year else title
    li = xbmcgui.ListItem(label=label)
    li.setLabel2(' / '.join(genres_list))
    li.setArt({
        'thumb': IMG_BASE + (item.get('poster_path') or ''),
        'icon':  IMG_BASE + (item.get('poster_path') or ''),
        'poster': IMG_BASE + (item.get('poster_path') or ''),
        'fanart': FANART_BASE + (item.get('backdrop_path') or '')
    })
    info = li.getVideoInfoTag()
    info.setTitle(title)
    if year:
        try:
            info.setYear(int(year))
        except ValueError:
            pass
    if genres_list:
        info.setGenres(genres_list)
    info.setPlot(plot)
    info.setRating(rating)
    info.setVotes(votes)
    if premiered:
        info.setPremiered(premiered)
    info.setMediaType('movie')
    return li


def build_item_tvshow_list(item, genre_map=None):
    """Construiește ListItem pentru serial din datele unui endpoint de listing."""
    title = item.get('name') or 'Fără titlu'
    year = (item.get('first_air_date') or '')[:4]
    rating = item.get('vote_average') or 0
    votes = int(item.get('vote_count') or 0)
    premiered = item.get('first_air_date', '')
    plot = item.get('overview', '')

    if genre_map is None:
        genre_map = get_genre_map('tv')
    genres_list = [genre_map[gid] for gid in item.get('genre_ids', []) if gid in genre_map]

    label = f"{title} ({year})" if year else title
    li = xbmcgui.ListItem(label=label)
    li.setLabel2(' / '.join(genres_list))
    li.setArt({
        'thumb': IMG_BASE + (item.get('poster_path') or ''),
        'icon':  IMG_BASE + (item.get('poster_path') or ''),
        'poster': IMG_BASE + (item.get('poster_path') or ''),
        'fanart': FANART_BASE + (item.get('backdrop_path') or '')
    })
    info = li.getVideoInfoTag()
    info.setTitle(title)
    info.setTvShowTitle(title)
    if year:
        try:
            info.setYear(int(year))
        except ValueError:
            pass
    if genres_list:
        info.setGenres(genres_list)
    info.setPlot(plot)
    info.setRating(rating)
    info.setVotes(votes)
    if premiered:
        info.setPremiered(premiered)
    info.setMediaType('tvshow')
    return li


#FILME - build din detalii complete (pentru redare / căutare)
def build_item(item):
    title = item.get('title') or item.get('name') or 'Fără titlu'
    year = (item.get('release_date') or '')[:4]
    genres_list = [g.get('name') for g in item.get('genres', [])]
    genres = ' / '.join(genres_list)
    duration = item.get('runtime') or 0
    rating = item.get('vote_average') or 0
    votes = int(item.get('vote_count') or 0)
    premiered = item.get('release_date', '')
    cast = item.get('credits', {}).get('cast', [])

    # Descriere cu fallback la engleză
    plot = item.get('overview', '')
    if not plot and LANGUAGE != 'en':
        fallback = tmdb_cached(f"movie/{item['id']}", {'language': 'en'}, ttl=TTL_DETAILS)
        plot = fallback.get('overview', '')

    label = f"{title} ({year})" if year else title

    li = xbmcgui.ListItem(label=label)
    li.setLabel2(genres)

    li.setArt({
        'thumb': IMG_BASE + (item.get('poster_path') or ''),
        'icon': IMG_BASE + (item.get('poster_path') or ''),
        'poster': IMG_BASE + (item.get('poster_path') or ''),
        'fanart': FANART_BASE + (item.get('backdrop_path') or '')
    })
    info = li.getVideoInfoTag()
    info.setTitle(title)
    if year:
        try:
            info.setYear(int(year))
        except ValueError:
            pass
    if genres_list:
        info.setGenres(genres_list)
    info.setDuration(duration)
    info.setPlot(plot)
    info.setPlotOutline(plot)
    info.setRating(rating)
    info.setVotes(votes)
    info.setPremiered(premiered)
    info.setMediaType('movie')

    if cast:
        cast_list = []
        for a in cast[:10]:
            name = a.get('name', '').strip()
            if not name:
                continue
            role = a.get('character', '')
            thumb = IMG_BASE + a['profile_path'] if a.get('profile_path') else ''
            person_id = a.get('id', '')
            actor_url = (f'plugin://plugin.video.samus?action=person_filmography'
                         f'&person_id={person_id}&person_name={quote(name)}') if person_id else ''
            try:
                actor = xbmc.Actor(name, role, -1, thumb, actor_url)
            except TypeError:
                actor = xbmc.Actor(name, role, -1, thumb)
            cast_list.append(actor)
        if cast_list:
            info.setCast(cast_list)

    videos = (item.get('videos') or {}).get('results') or []
    trailer = next((v for v in videos if v.get('site') == 'YouTube' and v.get('type') == 'Trailer'), None)
    if not trailer:
        trailer = next((v for v in videos if v.get('site') == 'YouTube'), None)
    if trailer:
        info.setTrailer(f"plugin://plugin.video.samus?action=play_trailer&tmdb_id={item['id']}&media_type=movie")

    return li


#SERIALE - build din detalii complete
def build_item_tvshow(item):
    title = item.get('name') or 'Fără titlu'
    year = (item.get('first_air_date') or '')[:4]
    genres_list = [g.get('name') for g in item.get('genres', [])]
    rating = item.get('vote_average') or 0
    votes = int(item.get('vote_count') or 0)
    premiered = item.get('first_air_date', '')
    status = item.get('status', '')
    cast = item.get('credits', {}).get('cast', [])
    seasons = item.get('number_of_seasons', 0)
    studios = [s.get('name') for s in item.get('production_companies', []) if s.get('name')]

    # Descriere cu fallback la engleză
    plot = item.get('overview', '')
    if not plot and LANGUAGE != 'en':
        fallback = tmdb_cached(f"tv/{item['id']}", {'language': 'en'}, ttl=TTL_DETAILS)
        plot = fallback.get('overview', '')

    label = f"{title} ({year})" if year else title

    li = xbmcgui.ListItem(label=label)
    li.setLabel2(' / '.join(genres_list))

    li.setArt({
        'thumb': IMG_BASE + (item.get('poster_path') or ''),
        'icon': IMG_BASE + (item.get('poster_path') or ''),
        'poster': IMG_BASE + (item.get('poster_path') or ''),
        'fanart': FANART_BASE + (item.get('backdrop_path') or '')
    })

    info = li.getVideoInfoTag()
    info.setTitle(title)
    info.setTvShowTitle(title)
    info.setTvShowStatus(status)
    if year:
        try:
            info.setYear(int(year))
        except ValueError:
            pass
    if genres_list:
        info.setGenres(genres_list)
    info.setPlot(plot)
    info.setPlotOutline(plot)
    info.setRating(rating)
    info.setVotes(votes)
    info.setPremiered(premiered)
    info.setMediaType('tvshow')

    if seasons:
        info.addSeasons([(i + 1, f"Sezon {i + 1}") for i in range(seasons)])

    tags = []
    if studios:
        tags += studios[:2]
        if any(s.lower() in ['netflix', 'hbo', 'bbc', 'prime video'] for s in studios):
            tags.append('Original')
    if seasons == 1:
        tags.append('Miniserie')
    if rating >= 7.5:
        tags.append('Popular')
    if tags:
        info.setTags(tags)

    if cast:
        cast_list = []
        for a in cast[:10]:
            name = a.get('name', '').strip()
            if not name:
                continue
            role = a.get('character', '')
            thumb = IMG_BASE + a['profile_path'] if a.get('profile_path') else ''
            person_id = a.get('id', '')
            actor_url = (f'plugin://plugin.video.samus?action=person_filmography'
                         f'&person_id={person_id}&person_name={quote(name)}') if person_id else ''
            try:
                actor = xbmc.Actor(name, role, -1, thumb, actor_url)
            except TypeError:
                actor = xbmc.Actor(name, role, -1, thumb)
            cast_list.append(actor)
        if cast_list:
            info.setCast(cast_list)

    videos = (item.get('videos') or {}).get('results') or []
    trailer = next((v for v in videos if v.get('site') == 'YouTube' and v.get('type') == 'Trailer'), None)
    if not trailer:
        trailer = next((v for v in videos if v.get('site') == 'YouTube'), None)
    if trailer:
        info.setTrailer(f"plugin://plugin.video.samus?action=play_trailer&tmdb_id={item['id']}&media_type=tv")

    return li


#ICONS
def get_icon_path(name):
    filename = f"{name.lower()}.png"
    path = os.path.join(ICON_PATH, filename)
    if os.path.exists(path):
        return path
    return ''


#STANDARDIZARE NUME GENURI
def normalize_genre_name(name):
    normalized = (
        name.lower()
            .replace('ă', 'a')
            .replace('â', 'a')
            .replace('î', 'i')
            .replace('ș', 's')
            .replace('ş', 's')
            .replace('ț', 't')
            .replace('ţ', 't')
            .strip()
    )

    for icon, names in GENRE_ICON_MAP.items():
        if any(n.lower()
               .replace('ă', 'a').replace('â', 'a').replace('î', 'i')
               .replace('ș', 's').replace('ş', 's')
               .replace('ț', 't').replace('ţ', 't')
               .strip() == normalized for n in names):
            return icon

    return normalized.replace(' ', '').replace('-', '')
