import sys
import xbmc
import xbmcgui
import xbmcplugin
from urllib.parse import quote

from resources.lib.tmdb.people import get_person_details, get_person_credits

IMG_BASE    = 'https://image.tmdb.org/t/p/w500'
FANART_BASE = 'https://image.tmdb.org/t/p/original'

handle = int(sys.argv[1])
_BASE  = sys.argv[0]

IMG_PROFILE = 'https://image.tmdb.org/t/p/w185'


def show_cast(tmdb_id, media_type):
    """List cast members for a movie or TV show. Each item opens the actor's filmography."""
    if media_type == 'movie':
        from resources.lib.tmdb import movies as tmdb_movies
        details = tmdb_movies.get_movie_details(tmdb_id)
    else:
        from resources.lib.tmdb import tv as tmdb_tv
        details = tmdb_tv.get_tv_details(tmdb_id)

    cast = details.get('credits', {}).get('cast', [])
    if not cast:
        xbmcgui.Dialog().notification('Samus', 'Nicio distribuție găsită.', xbmcgui.NOTIFICATION_WARNING, 3000)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    title = details.get('title') or details.get('name') or ''
    xbmcplugin.setPluginCategory(handle, f'Distribuție — {title}')
    xbmcplugin.setContent(handle, 'actors')

    items = []
    for actor in cast[:30]:
        name      = actor.get('name', '').strip()
        character = actor.get('character', '')
        person_id = actor.get('id')
        profile   = actor.get('profile_path')
        thumb     = IMG_PROFILE + profile if profile else ''

        label = name
        li = xbmcgui.ListItem(label=label)
        li.setLabel2(character)
        li.setArt({'thumb': thumb, 'poster': thumb, 'icon': thumb})
        tag = li.getVideoInfoTag()
        tag.setTitle(name)
        tag.setPlot(character)

        url = f'{_BASE}?action=person_filmography&person_id={person_id}&person_name={quote(name)}'
        items.append((url, li, True))

    xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle)


def show_filmography(person_id, person_name=''):
    """Show combined movie+TV filmography for a person, sorted by popularity."""
    person  = get_person_details(person_id)
    credits = get_person_credits(person_id)

    name     = person.get('name') or person_name or f'Actor {person_id}'
    bio      = (person.get('biography') or '').strip()
    birthday = person.get('birthday') or ''
    birthplace = person.get('place_of_birth') or ''
    profile  = person.get('profile_path')
    thumb    = IMG_PROFILE + profile if profile else ''

    xbmcplugin.setPluginCategory(handle, name)
    xbmcplugin.setContent(handle, 'movies')

    items = []

    # Biografie — primul item, click → dialog text
    if bio:
        bio_li = xbmcgui.ListItem(label=f'[B]Biografie[/B]  ·  {name}')
        bio_li.setArt({'thumb': thumb, 'poster': thumb, 'icon': thumb})
        tag = bio_li.getVideoInfoTag()
        tag.setTitle(name)
        tag.setPlot(bio)
        bio_url = f'{_BASE}?action=person_bio&person_id={person_id}&person_name={quote(name)}'
        items.append((bio_url, bio_li, False))

    # Credits sortate după popularitate; filtrăm intrările fără poster
    cast_credits = credits.get('cast', [])
    cast_credits = sorted(cast_credits, key=lambda x: x.get('popularity', 0), reverse=True)

    for item in cast_credits:
        media_type = item.get('media_type', 'movie')
        tid        = item.get('id')
        if not tid:
            continue

        movie_title = item.get('title') or item.get('name') or ''
        year        = (item.get('release_date') or item.get('first_air_date') or '')[:4]
        poster_path = item.get('poster_path')
        poster      = IMG_BASE + poster_path if poster_path else thumb
        rating      = item.get('vote_average') or 0
        plot        = item.get('overview') or ''
        character   = item.get('character') or ''
        vote_count  = item.get('vote_count') or 0

        # Sări titluri obscure (foarte puține voturi)
        if vote_count < 5:
            continue

        type_badge = 'Film' if media_type == 'movie' else 'Serial'
        label = f'{movie_title}  ({year})' if year else movie_title
        label2 = f'[{type_badge}]'
        if character:
            label2 += f'  ·  {character}'

        li = xbmcgui.ListItem(label=label)
        li.setLabel2(label2)
        li.setArt({
            'thumb':  poster,
            'poster': poster,
            'icon':   poster,
            'fanart': FANART_BASE + (item.get('backdrop_path') or ''),
        })

        tag = li.getVideoInfoTag()
        tag.setTitle(movie_title)
        tag.setPlot(plot)
        if rating:
            tag.setRating(rating)
        tag.setMediaType(media_type)
        if year:
            try:
                tag.setYear(int(year))
            except ValueError:
                pass

        if media_type == 'movie':
            li.setProperty('IsPlayable', 'true')
            url = f'{_BASE}?action=play_movie&tmdb_id={tid}'
            is_folder = False
        else:
            url = f'{_BASE}?action=tv_details&id={tid}'
            is_folder = True

        items.append((url, li, is_folder))

    xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle)


def open_filmography_by_name(name):
    """Called via RunPlugin from the skin; searches person by name then navigates to filmography."""
    from resources.lib.tmdb.people import search_person
    results = search_person(name)
    persons = (results or {}).get('results', [])
    if not persons:
        xbmcgui.Dialog().notification('Samus', 'Persoană negăsită.', xbmcgui.NOTIFICATION_INFO)
        return
    person = persons[0]
    pid   = person['id']
    pname = person.get('name') or name
    xbmc.executebuiltin('Dialog.Close(MovieInformation)')
    xbmc.sleep(150)
    xbmc.executebuiltin(
        f'ActivateWindow(Videos,plugin://plugin.video.samus'
        f'?action=person_filmography&person_id={pid}&person_name={quote(pname)},return)'
    )


def show_bio(person_id, person_name=''):
    """Show biography in a text viewer dialog (called via RunPlugin)."""
    person = get_person_details(person_id)
    name   = person.get('name') or person_name
    bio    = (person.get('biography') or '').strip()

    parts = []
    if person.get('birthday'):
        born = person['birthday']
        if person.get('place_of_birth'):
            born += f"  ·  {person['place_of_birth']}"
        parts.append(born)
    if bio:
        parts.append(bio)

    text = '\n\n'.join(parts) if parts else 'Biografie indisponibilă.'
    xbmcgui.Dialog().textviewer(name, text)
