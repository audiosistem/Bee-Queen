import xbmc
import sys
import xbmcvfs
import xbmcaddon
import xbmcgui
import xbmcplugin
import urllib.parse
import requests
import resolveurl
import json
import re
import os
import time
import base64
from bs4 import BeautifulSoup
from resources.lib.trakt_api import TraktAPI

# Get the addon ID
ADDON_ID = xbmcaddon.Addon().getAddonInfo('id')
ADDON = xbmcaddon.Addon(ADDON_ID)
HANDLE = int(sys.argv[1])
BASE_URL = 'https://veziaici.net/'
CACHE_DIR = xbmcvfs.translatePath(os.path.join(xbmcaddon.Addon().getAddonInfo('profile'), 'cache'))
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': BASE_URL,
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'cross-site',
    'Sec-Fetch-User': '?1'
}

def _get_html_content(url):
    return requests.get(url, headers=HEADERS)


# Dictionary for custom show images
CUSTOM_IMAGES = {
    'insula iubirii': 'https://www.fanatik.ro/wp-content/uploads/2024/08/insula-iubirii-2025.jpg',
    'las fierbinti': 'https://upload.wikimedia.org/wikipedia/en/0/0d/Las_Fierbin%C8%9Bi_logo.png',
    'asia express': 'https://cdn.adh.reperio.news/image-e/e410c82f-f849-4953-94fa-ed9ee2ba49bf/index.jpeg',
    'masterchef': 'https://static4.libertatea.ro/wp-content/uploads/2024/02/masterchef-romania-revine-la-pro-tv.jpg',
    'the ticket': 'https://static4.libertatea.ro/wp-content/uploads/2025/07/the-ticket.jpg',
    'vocea romaniei': 'https://upload.wikimedia.org/wikipedia/ro/thumb/8/83/Vocea_Rom%C3%A2niei_-_compila%C8%9Bie.jpg/250px-Vocea_Rom%C3%A2niei_-_compila%C8%9Bie.jpg',
    'ana mi-ai fost scrisa in adn': 'https://static4.libertatea.ro/wp-content/uploads/2024/11/ana-mi-ai-fost-scrisa-in-adn-serial-antena-1.jpg',
    'camera 609': 'https://static.cinemagia.ro/img/resize/db/movie/33/10/231/lasa-ma-imi-place-camera-609-729239l-600x0-w-09e9e09b.jpg',
    'clanul': 'https://cmero-ott-images-svod.ssl.cdn.cra.cz/r800x1160n/ad802c4a-901f-4700-9948-39361f41a677',
    'seriale': 'https://upload.wikimedia.org/wikipedia/en/0/0d/Las_Fierbin%C8%9Bi_logo.png',
    'iubire cu': 'https://dcasting.ro/wp-content/uploads/2025/02/Iubire-cu-parfum-de-lavanda.jpg',
    'sotia sotului': 'https://onemagia.com/upload/images/e7mDxkP6Qgbo735USy5telMF1wF.jpg',
    'scara b': 'https://static4.libertatea.ro/wp-content/uploads/2024/08/scara-b-scaled.jpg',
    'tatutu': 'https://image.stirileprotv.ro/media/images/1920x1080/Jun2025/62556367.jpg'
}

def get_main_menu_items():
    try:
        response = _get_html_content(BASE_URL)
        response.raise_for_status()
        html_content = response.text
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch main page: {e}")
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    categories = []
    
    for top_li in soup.select('ul#main-menu > li.menu-item-has-children'):
        category_title_element = top_li.find('span')
        if not category_title_element:
            continue
        
        category_title = category_title_element.text.strip()
        sub_menu = top_li.find('ul', class_='sub-menu')
        
        if category_title and sub_menu:
            shows = []
            for sub_li in sub_menu.find_all('li'):
                link = sub_li.find('a')
                if link and 'href' in link.attrs:
                    title = link.text.strip()
                    url = link['href']
                    if title and url:
                        shows.append({'title': title, 'url': url})
            if shows:
                categories.append({'title': category_title, 'shows': shows})
                        
    return categories

def list_main_menu():
    # Add a static search item
    list_item = xbmcgui.ListItem('Cauta')
    search_icon = "https://i.imgur.com/dvqhLCI.png"
    list_item.setArt({'icon': search_icon, 'thumb': search_icon})
    url = sys.argv[0] + '?' + urllib.parse.urlencode({'mode': 'search'})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=list_item, isFolder=True)

    categories = get_main_menu_items()
    for category in categories:
        list_item = xbmcgui.ListItem(category['title'])
        category_icon = ADDON.getAddonInfo('icon')  # Initialize with default
        
        if 'emisiuni' in category['title'].lower():
            category_icon = CUSTOM_IMAGES.get('asia express', category_icon)
            url = sys.argv[0] + '?' + urllib.parse.urlencode({'mode': 'list_show_categories', 'shows': json.dumps(category['shows']), 'name': category['title'], 'latest_url': 'https://veziaici.net/category/a-emisiuni-romanesti/'})
        elif 'seriale' in category['title'].lower():
            category_icon = CUSTOM_IMAGES.get('las fierbinti', category_icon)
            url = sys.argv[0] + '?' + urllib.parse.urlencode({'mode': 'list_show_categories', 'shows': json.dumps(category['shows']), 'name': category['title'], 'latest_url': 'https://veziaici.net/category/c-seriale-romanesti/'})
        else:
            url = sys.argv[0] + '?' + urllib.parse.urlencode({'mode': 'list_shows', 'shows': json.dumps(category['shows']), 'name': category['title']})

        list_item.setArt({'icon': category_icon, 'thumb': category_icon})
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=list_item, isFolder=True)

    # Add a static folder for Seriale Turcesti
    list_item = xbmcgui.ListItem('Seriale Turcesti')
    turk_icon = "https://fuzzy.ro/wp-content/uploads/2023/01/seriale-turcesti.jpg"
    list_item.setArt({'icon': turk_icon, 'thumb': turk_icon})
    url = sys.argv[0] + '?' + urllib.parse.urlencode({'mode': 'list_turkish_series_categories'})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=list_item, isFolder=True)

    # Add a static folder for Seriale Coreene
    list_item = xbmcgui.ListItem('Seriale Coreene')
    korean_icon = "https://fericitazi.com/wp-content/uploads/Seriale-coreene-de-dragoste-780x450.jpg"
    list_item.setArt({'icon': korean_icon, 'thumb': korean_icon})
    url = sys.argv[0] + '?' + urllib.parse.urlencode({'mode': 'list_korean_series_categories'})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=list_item, isFolder=True)

    # Add a static folder for Seriale Chinezesti
    list_item = xbmcgui.ListItem('Seriale Chinezesti')
    list_item.setArt({'icon': korean_icon, 'thumb': korean_icon})
    url_params = {
        'mode': 'list_korean_series',
        'url': 'https://blogul-lui-atanase.ro/categorie/serialefilme-chinezesti/',
        'name': 'Seriale Chinezesti'
    }
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Add a static folder for Seriale Japoneze
    list_item = xbmcgui.ListItem('Seriale Japoneze')
    list_item.setArt({'icon': korean_icon, 'thumb': korean_icon})
    url_params = {
        'mode': 'list_korean_series',
        'url': 'https://blogul-lui-atanase.ro/categorie/seriale-japoneze/',
        'name': 'Seriale Japoneze'
    }
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Add a static folder for Seriale Thailandeze
    list_item = xbmcgui.ListItem('Seriale Thailandeze')
    list_item.setArt({'icon': korean_icon, 'thumb': korean_icon})
    url_params = {
        'mode': 'list_korean_series',
        'url': 'https://blogul-lui-atanase.ro/categorie/seriale-thailandeze/',
        'name': 'Seriale Thailandeze'
    }
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Add a static folder for Seriale Taiwan
    list_item = xbmcgui.ListItem('Seriale Taiwan')
    list_item.setArt({'icon': korean_icon, 'thumb': korean_icon})
    url_params = {
        'mode': 'list_korean_series',
        'url': 'https://blogul-lui-atanase.ro/categorie/serialefilme-taiwanezethailandeze/',
        'name': 'Seriale Taiwan'
    }
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Add a static folder for SerialeCoreene.org
    list_item = xbmcgui.ListItem('SerialeCoreene.org')
    serialecoreene_icon = "https://serialecoreene.org/wp-content/uploads/2023/10/coreene-logo.png"
    list_item.setArt({'icon': serialecoreene_icon, 'thumb': serialecoreene_icon})
    url = sys.argv[0] + '?' + urllib.parse.urlencode({'mode': 'list_serialecoreene_main'})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=list_item, isFolder=True)

    # Add a static folder for Filme
    list_item = xbmcgui.ListItem('Filme')
    filme_icon = "https://1.bp.blogspot.com/-5utXzUd3Wk0/XcatUqtM9pI/AAAAAAAACTU/8Jbt1d8gO8Y7XVLGQnjHYYnJ9ou1_kTLACLcBGAsYHQ/s1600/www.tvnowstream.de.jpg"
    list_item.setArt({'icon': filme_icon, 'thumb': filme_icon})
    url = sys.argv[0] + '?' + urllib.parse.urlencode({'mode': 'list_movies_categories'})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_show_categories(shows_json, name, latest_url):
    # Add "Ultimile adaugate" item
    list_item = xbmcgui.ListItem('Ultimile adaugate')
    url_params = {'mode': 'list_latest', 'url': latest_url, 'name': 'Ultimile adaugate'}
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Add the rest of the shows
    shows = json.loads(shows_json)
    for show in shows:
        list_item = xbmcgui.ListItem(show['title'])
        
        # Default icon
        show_icon = ADDON.getAddonInfo('icon')
        # Check for custom image
        for keyword, image_url in CUSTOM_IMAGES.items():
            if keyword in show['title'].lower():
                show_icon = image_url
                break

        list_item.setArt({'icon': show_icon, 'thumb': show_icon})
        url = sys.argv[0] + '?' + urllib.parse.urlencode({'mode': 'list_episodes', 'url': show['url'], 'name': show['title']})
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_shows(shows_json):
    shows = json.loads(shows_json)
    for show in shows:
        list_item = xbmcgui.ListItem(show['title'])
        
        # Default icon
        show_icon = ADDON.getAddonInfo('icon')
        # Check for custom image
        for keyword, image_url in CUSTOM_IMAGES.items():
            if keyword in show['title'].lower():
                show_icon = image_url
                break

        list_item.setArt({'icon': show_icon, 'thumb': show_icon})
        url = sys.argv[0] + '?' + urllib.parse.urlencode({'mode': 'list_episodes', 'url': show['url'], 'name': show['title']})
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_episodes(url, name=""):
    cache_file = os.path.join(CACHE_DIR, name.replace(' ', '_') + '.json')
    cache_expiry = 24 * 3600 # 24 hours

    all_episodes = []

    # Try to load from cache first
    # Force refresh to clear potentially bad cache
    if False and os.path.exists(cache_file) and (time.time() - os.path.getmtime(cache_file)) < cache_expiry:
        with open(cache_file, 'r') as f:
            all_episodes = json.load(f)
    else:
        # If cache is invalid or missing, scrape all pages
        current_url = url
        while current_url:
            try:
                response = _get_html_content(current_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
            except requests.exceptions.RequestException:
                break

            for title_element in soup.find_all(['h3', 'h2'], class_='entry-title'):
                if title_element.find('a'):
                    link_element = title_element.find('a')
                    item_url = link_element.get('href')
                    title = link_element.text.strip()
                    if item_url and title:
                        all_episodes.append({'title': title, 'url': item_url, 'name': name})

            next_page_link = soup.find('a', class_='next page-numbers')
            if next_page_link and next_page_link.has_attr('href'):
                current_url = next_page_link['href']
            else:
                current_url = None
        
        # Save to cache
        with open(cache_file, 'w') as f:
            json.dump(all_episodes, f)

    # --- The rest of the function remains the same, processing 'all_episodes' ---

    # Extract seasons from episode titles
    seasons = {}
    no_season_episodes = []
    for episode in all_episodes:
        match = re.search(r'sez(?:onul|on|\.)\s*(\d+)', episode['title'], re.IGNORECASE)
        if match:
            season_num = int(match.group(1))
            if season_num not in seasons:
                seasons[season_num] = []
            seasons[season_num].append(episode)
        else:
            no_season_episodes.append(episode)

    # If only one season is found and no episodes without a season, list them directly
    if len(seasons) == 1 and not no_season_episodes:
        season_num = list(seasons.keys())[0]
        list_episodes_for_season(json.dumps(seasons[season_num]), season_num, name)
        return

    # Create folders for each season
    for season_num in sorted(seasons.keys(), reverse=True):
        list_item = xbmcgui.ListItem(f"Sezonul {season_num}")
        season_icon = ADDON.getAddonInfo('icon')
        for keyword, image_url in CUSTOM_IMAGES.items():
            if keyword in name.lower():
                season_icon = image_url
                break
        list_item.setArt({'icon': season_icon, 'thumb': season_icon})
        url_params = {'mode': 'list_episodes_for_season', 'episodes': json.dumps(seasons[season_num]), 'season': season_num, 'name': name}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    if no_season_episodes:
        list_item = xbmcgui.ListItem("Fara Sezon")
        list_item.setArt({'icon': ADDON.getAddonInfo('icon'), 'thumb': ADDON.getAddonInfo('icon')})
        url_params = {'mode': 'list_episodes_for_season', 'episodes': json.dumps(no_season_episodes), 'season': '0', 'name': name}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_episodes_for_season(episodes_json, season, name=""):
    episodes = json.loads(episodes_json)
    custom_image_found = None
    for keyword, image_url in CUSTOM_IMAGES.items():
        if keyword in name.lower():
            custom_image_found = image_url
            break

    for episode in episodes:
        list_item = xbmcgui.ListItem(episode['title'])
        image_to_use = custom_image_found if custom_image_found else ADDON.getAddonInfo('icon')
        list_item.setArt({'thumb': image_to_use, 'icon': image_to_use, 'fanart': ADDON.getAddonInfo('fanart')})
        list_item.setInfo('video', {'title': episode['title']})
        url_params = {'mode': 'list_sources', 'url': episode['url']}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_sources(url, name=""):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch source page: {e}")
        return

    iframes = soup.find_all('iframe', attrs={'data-lazy-src': True})
    for iframe in iframes:
        video_url = iframe['data-lazy-src']
        
        if 'player3.funny-cats.org' in video_url:
            continue

        if video_url.startswith('//'):
            video_url = 'https:' + video_url
        
        domain = urllib.parse.urlparse(video_url).netloc.replace('www.', '')
        
        list_item = xbmcgui.ListItem(f"Sursa: {domain}")
        list_item.setInfo('video', {'title': f"Sursa: {domain}"})
        list_item.setProperty('IsPlayable', 'true')
        
        # Pass the real title (name) to play_source
        url_params = {'mode': 'play_source', 'url': video_url, 'title': name}
        
        context_menu_items = [('Download', f'RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(video_url)})')]
        list_item.addContextMenuItems(context_menu_items)
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)
    
    xbmcplugin.endOfDirectory(HANDLE)

def resolve_url_wrapper(url):
    resolver_method = ADDON.getSetting('resolver')
    xbmc.log(f"[{ADDON.getAddonInfo('name')}] Resolver Setting: '{resolver_method}' (0=ResolveURL, 1=Youtube-DL)", xbmc.LOGINFO)
    
    # Method 1: Youtube-DL (Check for index '1' or value 'Youtube-DL')
    if resolver_method == '1' or resolver_method == 'Youtube-DL':
        
        ydl_module = None
        module_name = ""

        try:
            import yt_dlp as ydl_module
            module_name = "yt-dlp"
        except ImportError:
            try:
                import youtube_dl as ydl_module
                module_name = "youtube_dl"
            except ImportError:
                xbmc.log(f"[{ADDON.getAddonInfo('name')}] Nici yt-dlp, nici youtube_dl nu au fost gasite.", xbmc.LOGWARNING)

        if ydl_module:
            xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), f"Incercare rezolvare cu {module_name}...", xbmcgui.NOTIFICATION_INFO)
            
            try:
                # Options to mimic a browser and avoid bot detection
                ydl_opts = {
                    'format': 'best',
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'user_agent': HEADERS['User-Agent'],
                    'referer': BASE_URL,
                    # youtube_dl might not support all these, but usually ignores unknown opts or shares them
                }
                
                with ydl_module.YoutubeDL(ydl_opts) as ydl:
                    xbmc.log(f"[{ADDON.getAddonInfo('name')}] {module_name} Processing: {url}", xbmc.LOGINFO)
                    info = ydl.extract_info(url, download=False)
                    
                    if 'url' in info:
                        xbmc.log(f"[{ADDON.getAddonInfo('name')}] {module_name} Success: {info['url']}", xbmc.LOGINFO)
                        return info['url']
                    elif 'entries' in info:
                        # Sometimes it returns a playlist, take first item
                        first_entry = info['entries'][0]
                        if 'url' in first_entry:
                            xbmc.log(f"[{ADDON.getAddonInfo('name')}] {module_name} Success (Playlist): {first_entry['url']}", xbmc.LOGINFO)
                            return first_entry['url']
                    
                    xbmc.log(f"[{ADDON.getAddonInfo('name')}] {module_name} did not return a direct URL.", xbmc.LOGWARNING)

            except Exception as e:
                xbmc.log(f"[{ADDON.getAddonInfo('name')}] {module_name} Error: {e}. Falling back.", xbmc.LOGERROR)
                # Do not return None yet, fall through to ResolveURL
        else:
             xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), "Module Youtube-DL lipsa! Folosesc ResolveURL.", xbmcgui.NOTIFICATION_WARNING)

        xbmc.log(f"[{ADDON.getAddonInfo('name')}] Youtube-DL method failed. Falling back to ResolveURL.", xbmc.LOGINFO)
    
    # Method 0 (or Fallback): ResolveURL
    # Check if ResolveURL supports the host before trying blindly (optional, but ResolveURL handles checking)
    try:
        if resolveurl.HostedMediaFile(url=url).valid_url():
            xbmc.log(f"[{ADDON.getAddonInfo('name')}] Using ResolveURL for: {url}", xbmc.LOGINFO)
            return resolveurl.resolve(url)
        else:
            xbmc.log(f"[{ADDON.getAddonInfo('name')}] ResolveURL says URL is invalid: {url}", xbmc.LOGWARNING)
            # If we are here and YT-DLP also failed (or wasn't selected), we might try passing it directly
            # assuming it's a direct link (mp4/m3u8)
            if url.endswith('.mp4') or url.endswith('.m3u8'):
                 return url
    except Exception as e:
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] ResolveURL Error: {e}", xbmc.LOGERROR)

    return None

def play_source(url, title=None):
    resolved_url = resolve_url_wrapper(url)
    if resolved_url:
        list_item = xbmcgui.ListItem(path=resolved_url)
        if title:
            list_item.setInfo('video', {'title': title})
            # Communicate title to service.py via window property
            xbmcgui.Window(10000).setProperty('VeziAici_Title', title)
        else:
            xbmcgui.Window(10000).clearProperty('VeziAici_Title')
            
        xbmcplugin.setResolvedUrl(HANDLE, True, list_item)
    else:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), "Could not resolve video URL.")

def list_search_results(url):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch search results: {e}")
        return

    for item in soup.select('div.rb-p20-gutter.rb-col-m12.rb-col-t4'):
        title_element = item.select_one('h3.entry-title a.p-url')
        if title_element:
            title = title_element.get('title')
            item_url = title_element.get('href')
            
            show_icon = ADDON.getAddonInfo('icon')
            for keyword, image_url in CUSTOM_IMAGES.items():
                if keyword in title.lower():
                    show_icon = image_url
                    break

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({'thumb': show_icon, 'icon': show_icon})
            
            # We assume search results lead directly to sources
            url_params = {'mode': 'list_sources', 'url': item_url, 'name': title}
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Handle pagination
    next_page_link = soup.select_one('a.page-numbers')
    if next_page_link:
        next_page_url = next_page_link.get('href')
        if next_page_url:
            list_item = xbmcgui.ListItem('Next Page >>')
            url_params = {'mode': 'list_search_results', 'url': next_page_url}
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def search(query=None):
    if not query:
        keyboard = xbmcgui.Dialog().input('Cauta', type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            return
        query = keyboard

    search_url = BASE_URL + '?s=' + urllib.parse.quote_plus(query)
    list_search_results(search_url)

def list_latest(url, name=""):
    all_items = []
    current_url = url
    page_count = 0

    while current_url and page_count < 3:
        try:
            response = _get_html_content(current_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException:
            break

        for title_element in soup.find_all(['h3', 'h2'], class_='entry-title'):
            if title_element.find('a'):
                link_element = title_element.find('a')
                item_url = link_element.get('href')
                title = link_element.text.strip()

                show_icon = ADDON.getAddonInfo('icon')
                for keyword, image_url in CUSTOM_IMAGES.items():
                    if keyword in title.lower():
                        show_icon = image_url
                        break

                if item_url and title:
                    all_items.append({'title': title, 'url': item_url, 'thumbnail': show_icon})

        next_page_link = soup.find('a', class_='next page-numbers')
        if next_page_link and next_page_link.has_attr('href'):
            current_url = next_page_link['href']
        else:
            current_url = None
        
        page_count += 1

    for item in all_items:
        list_item = xbmcgui.ListItem(item['title'])
        list_item.setArt({'thumb': item['thumbnail'], 'icon': item['thumbnail']})
        list_item.setInfo('video', {'title': item['title']})
        url_params = {'mode': 'list_sources', 'url': item['url']}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    if current_url:
        list_item = xbmcgui.ListItem('Next Page >>')
        url_params = {'mode': 'list_latest', 'url': current_url, 'name': name}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_turkish_series(url, mode, page='1'):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch Turkish series: {e}")
        return
    all_series = []
    for figure in soup.find_all('figure', class_='wp-block-image'):
        link = figure.find('a')
        img = figure.find('img')
        if link and img and 'href' in link.attrs and 'src' in img.attrs:
            series_url = link['href']
            thumb = img['src']   
            # Extract name from URL
            name_part = series_url.strip('/').split('/')[-1]
            name = ' '.join(word.capitalize() for word in name_part.split('-'))
            all_series.append({'name': name, 'url': series_url, 'thumb': thumb})
    page = int(page)
    items_per_page = 20
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    page_items = all_series[start_index:end_index]
    for series in page_items:
        list_item = xbmcgui.ListItem(series['name'])
        list_item.setArt({'thumb': series['thumb'], 'icon': series['thumb']})
        url_params = {'mode': 'list_turkish_episodes', 'url': series['url'], 'name': series['name']}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)
    if end_index < len(all_series):
        next_page = page + 1
        list_item = xbmcgui.ListItem('Next Page >>')
        url_params = {'mode': mode, 'url': url, 'page': str(next_page)}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def list_turkish_episodes(url, name):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch episodes for {name}: {e}")
        return
    for article in soup.find_all('article'):
        thumb_link = article.find('a', class_='post-thumbnail')
        if thumb_link:
            episode_url = thumb_link['href']
            img = thumb_link.find('img')
            thumb = img['src'] if img and 'src' in img.attrs else ''
            title = img['alt'].replace('&#8211;', '-').strip() if img and 'alt' in img.attrs else 'Episode'
            list_item = xbmcgui.ListItem(title)
            list_item.setArt({'thumb': thumb, 'icon': thumb})
            list_item.setInfo('video', {'title': title})
            url_params = {'mode': 'list_turkish_sources', 'url': episode_url, 'name': name} # Pass name
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)
    # Handle pagination
    next_page_link = soup.find('a', class_='next page-numbers')
    if next_page_link and 'href' in next_page_link.attrs:
        next_page_url = next_page_link['href']
        list_item = xbmcgui.ListItem('Next Page >>')
        url_params = {'mode': 'list_turkish_episodes', 'url': next_page_url, 'name': name}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def list_turkish_sources(url, name=""):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch source page: {e}")
        return

    iframe_placeholders = soup.find_all('div', class_='iframe-placeholder')
    
    if not iframe_placeholders:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), "No playable source found.")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for placeholder in iframe_placeholders:
        if 'data-encoded' in placeholder.attrs:
            encoded_iframe = placeholder['data-encoded']
            try:
                decoded_iframe = base64.b64decode(encoded_iframe).decode('utf-8')
                src_match = re.search(r'src="([^"]+)"', decoded_iframe)
                if src_match:
                    video_url = src_match.group(1)

                    if 'player3.funny-cats.org' in video_url:
                        continue

                    if video_url.startswith('//'):
                        video_url = 'https:' + video_url
                    
                    domain = urllib.parse.urlparse(video_url).netloc.replace('www.', '')
                    
                    list_item = xbmcgui.ListItem(f"Sursa: {domain}")
                    list_item.setInfo('video', {'title': f"Sursa: {domain}"})
                    list_item.setProperty('IsPlayable', 'true')
                    
                    # Pass title
                    url_params = {'mode': 'play_source', 'url': video_url, 'title': name}
                    
                    context_menu_items = [('Download', f'RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(video_url)})')]
                    list_item.addContextMenuItems(context_menu_items)
                    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)
            except Exception:
                continue
    
    xbmcplugin.endOfDirectory(HANDLE)

def list_korean_series_categories():
    icon = "https://kdrama.ro/wp-content/uploads/2023/06/image7-1016x1024.jpg"

    # "Dupa Ani" item
    list_item = xbmcgui.ListItem('Dupa Ani')
    list_item.setArt({'icon': icon, 'thumb': icon})
    url_params = {'mode': 'list_korean_series_years'}
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # "Seriale Coreene de Familie" item
    list_item = xbmcgui.ListItem('Seriale Coreene de Familie')
    list_item.setArt({'icon': icon, 'thumb': icon})
    url_params = {
        'mode': 'list_korean_series',
        'url': 'https://blogul-lui-atanase.ro/categorie/seriale-coreene-de-familie-50-ep/',
        'name': 'Seriale Coreene de Familie'
    }
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # "Seriale Coreene Contemporane" item
    list_item = xbmcgui.ListItem('Seriale Coreene Contemporane')
    list_item.setArt({'icon': icon, 'thumb': icon})
    url_params = {
        'mode': 'list_korean_series',
        'url': 'https://blogul-lui-atanase.ro/categorie/seriale-coreene-contemporane/',
        'name': 'Seriale Coreene Contemporane'
    }
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # "Seriale Coreene Istorice" item
    list_item = xbmcgui.ListItem('Seriale Coreene Istorice')
    list_item.setArt({'icon': icon, 'thumb': icon})
    url_params = {
        'mode': 'list_korean_series',
        'url': 'https://blogul-lui-atanase.ro/categorie/seriale-coreene-istorice/',
        'name': 'Seriale Coreene Istorice'
    }
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # "Mini-Seriale Coreene" item
    list_item = xbmcgui.ListItem('Mini-Seriale Coreene')
    list_item.setArt({'icon': icon, 'thumb': icon})
    url_params = {
        'mode': 'list_korean_series',
        'url': 'https://blogul-lui-atanase.ro/categorie/miniseriale-coreene/',
        'name': 'Mini-Seriale Coreene'
    }
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_korean_series_years():
    try:
        response = _get_html_content('https://blogul-lui-atanase.ro/')
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch Korean series categories: {e}")
        return

    menu_item = soup.find('li', id='menu-item-15749')
    if menu_item:
        sub_menu = menu_item.find('ul', class_='sub-menu')
        if sub_menu:
            for item in sub_menu.find_all('li'):
                link = item.find('a')
                if link and link.has_attr('href'):
                    title = link.text.strip()
                    url = link['href']
                    list_item = xbmcgui.ListItem(title)
                    url_params = {'mode': 'list_korean_series', 'url': url, 'name': title}
                    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)
    
    xbmcplugin.endOfDirectory(HANDLE)


def list_korean_series(url, name, page='1'):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch Korean series for {name}: {e}")
        return

    # Determine the container items
    items = soup.find_all('div', class_='post-col')
    if not items:
        items = soup.find_all('article')

    for item in items:
        title_h2 = None
        thumb_figure = None # For new layout
        thumb_div = None    # For old layout
        description_div = None

        # Check for New Layout specific element (MagazineNP)
        if item.find('figure', class_='post-featured-image'):
             title_h2 = item.find('h2', class_='entry-title')
             thumb_figure = item.find('figure', class_='post-featured-image')
             description_div = item.find('div', class_='entry-content')
        else:
            # Try old structure
            title_h2 = item.find('h2', class_='post-title')
            thumb_div = item.find('div', class_='post-thumb')
            description_div = item.find('div', class_='entry-content')
            
            # Try new structure (ColorMag) if old not found
            if not title_h2:
                title_h2 = item.find('h2', class_='cm-entry-title')
            if not thumb_div:
                thumb_div = item.find('div', class_='cm-featured-image')
            if not description_div:
                description_div = item.find('div', class_='cm-entry-summary')

        if title_h2:
            title_link = title_h2.find('a')
            if title_link:
                series_url = title_link['href']
                # Use text if title attribute is missing
                title = title_link.get('title', title_link.text.strip())
                
                thumb = ''
                # Handle Image Extraction
                if thumb_figure: # New Layout
                    a_thumb = thumb_figure.find('a', class_='mnp-post-image')
                    if a_thumb and 'style' in a_thumb.attrs:
                        style = a_thumb['style']
                        match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style)
                        if match:
                            thumb = match.group(1)
                elif thumb_div: # Old Layouts
                    thumb_img = thumb_div.find('img')
                    if thumb_img:
                        thumb = thumb_img.get('data-src', thumb_img.get('src', ''))

                description = description_div.text.strip() if description_div else ''

                list_item = xbmcgui.ListItem(title)
                list_item.setArt({'thumb': thumb, 'icon': thumb})
                list_item.setInfo('video', {'title': title, 'plot': description})
                url_params = {'mode': 'list_korean_episodes_and_sources', 'url': series_url, 'name': title} # Pass name
                xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Pagination - try both methods
    next_page_link = None
    
    # Old pagination
    pagination = soup.find('div', id='post-navigator')
    if pagination:
        current_page_span = pagination.find('span', class_='current')
        if current_page_span:
            next_page_link = current_page_span.find_next_sibling('a')

    # New/Generic pagination (WordPress default)
    if not next_page_link:
         next_page_link = soup.find('a', class_='next page-numbers')

    if next_page_link and next_page_link.has_attr('href'):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem('Next Page >>')
        url_params = {'mode': 'list_korean_series', 'url': url, 'name': name, 'page': str(next_page_num)}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_movies(url, name, page='1'):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch movies for {name}: {e}")
        return

    # Determine the container items
    items = soup.find_all('div', class_='post-col')
    if not items:
        items = soup.find_all('article')

    for item in items:
        title_h2 = None
        thumb_figure = None # For new layout
        thumb_div = None    # For old layout
        description_div = None

        # Check for New Layout specific element (MagazineNP)
        if item.find('figure', class_='post-featured-image'):
             title_h2 = item.find('h2', class_='entry-title')
             thumb_figure = item.find('figure', class_='post-featured-image')
             description_div = item.find('div', class_='entry-content')
        else:
            # Try old structure
            title_h2 = item.find('h2', class_='post-title')
            thumb_div = item.find('div', class_='post-thumb')
            description_div = item.find('div', class_='entry-content')
            
            # Try new structure (ColorMag) if old not found
            if not title_h2:
                title_h2 = item.find('h2', class_='cm-entry-title')
            if not thumb_div:
                thumb_div = item.find('div', class_='cm-featured-image')
            if not description_div:
                description_div = item.find('div', class_='cm-entry-summary')

        if title_h2:
            title_link = title_h2.find('a')
            if title_link:
                series_url = title_link['href']
                # Use text if title attribute is missing
                title = title_link.get('title', title_link.text.strip())
                
                thumb = ''
                # Handle Image Extraction
                if thumb_figure: # New Layout
                    a_thumb = thumb_figure.find('a', class_='mnp-post-image')
                    if a_thumb and 'style' in a_thumb.attrs:
                        style = a_thumb['style']
                        match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style)
                        if match:
                            thumb = match.group(1)
                elif thumb_div: # Old Layouts
                    thumb_img = thumb_div.find('img')
                    if thumb_img:
                        thumb = thumb_img.get('data-src', thumb_img.get('src', ''))

                description = description_div.text.strip() if description_div else ''

                is_series = False
                keywords = ['serial', 'sezon', 'episod', 'episoade']
                if any(keyword in title.lower() for keyword in keywords) or any(keyword in description.lower() for keyword in keywords):
                    is_series = True

                list_item = xbmcgui.ListItem(title)
                list_item.setArt({'thumb': thumb, 'icon': thumb})
                list_item.setInfo('video', {'title': title, 'plot': description})

                if is_series:
                    url_params = {'mode': 'list_series_episodes', 'url': series_url, 'name': title}
                else:
                    url_params = {'mode': 'list_movie_sources', 'url': series_url, 'name': title} # Pass name
                
                xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Pagination - try both methods
    next_page_link = None
    
    # Old pagination
    pagination = soup.find('div', id='post-navigator')
    if pagination:
        current_page_span = pagination.find('span', class_='current')
        if current_page_span:
            next_page_link = current_page_span.find_next_sibling('a')

    # New/Generic pagination (WordPress default)
    if not next_page_link:
         next_page_link = soup.find('a', class_='next page-numbers')

    if next_page_link and next_page_link.has_attr('href'):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem('Next Page >>')
        url_params = {'mode': 'list_movies', 'url': url, 'name': name, 'page': str(next_page_num)}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_movie_sources(url, name=""):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch source page: {e}")
        return

    sources_found = False

    # Find sources in <a> tags
    for a_tag in soup.find_all('a', href=True):
        video_url = a_tag['href']
        if video_url.startswith('//'):
            video_url = 'https:' + video_url
        if 'netu.ac' in video_url or 'vidmoly.me' in video_url or 'waaw.ac' in video_url or 'streamtape.com' in video_url or 'ok.ru' in video_url or 'waaw.to' in video_url or 'uqload.cx' in video_url or 'vk.com' in video_url or 'sibnet.ru' in video_url or 'my.mail.ru' in video_url:
            domain = urllib.parse.urlparse(video_url).netloc.replace('www.', '')
            list_item = xbmcgui.ListItem(f"Sursa: {domain}")
            list_item.setInfo('video', {'title': f"Sursa: {domain}"})
            list_item.setProperty('IsPlayable', 'true')
            
            # Pass title
            url_params = {'mode': 'play_source', 'url': video_url, 'title': name}
            
            context_menu_items = [('Download', f'RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(video_url)})')]
            list_item.addContextMenuItems(context_menu_items)
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)
            sources_found = True

    # Find sources in <iframe> tags
    iframes = soup.find_all('iframe')
    for iframe in iframes:
        if iframe.has_attr('src'):
            video_url = iframe['src']
            if video_url.startswith('//'):
                video_url = 'https:' + video_url
            
            domain = urllib.parse.urlparse(video_url).netloc.replace('www.', '')
            
            list_item = xbmcgui.ListItem(f"Sursa: {domain}")
            list_item.setInfo('video', {'title': f"Sursa: {domain}"})
            list_item.setProperty('IsPlayable', 'true')
            
            # Pass title
            url_params = {'mode': 'play_source', 'url': video_url, 'title': name}
            
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)
            sources_found = True

    if not sources_found:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), "No sources found on this page.")

    xbmcplugin.endOfDirectory(HANDLE)

def list_series_episodes(url, name):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch episodes for {name}: {e}")
        return

    content = soup.find('div', class_='entry-content')
    if not content:
        return

    all_elements = content.find_all(['h3', 'p'])
    for element in all_elements:
        element_text = element.text.strip()
        if 'episodul' in element_text.lower() or 'episod' in element_text.lower():
            episode_title = element_text
            
            # Look for source links in the same element (for Korean-style formatting)
            source_links = element.find_all('a', href=True)
            if source_links:
                for source_link in source_links:
                    source_url = source_link['href']
                    source_name = source_link.text.strip()
                    if source_name and 'episodul' not in source_name.lower() and 'episod' not in source_name.lower():
                        display_title = f"{episode_title} - {source_name}"
                        list_item = xbmcgui.ListItem(display_title)
                        list_item.setProperty('IsPlayable', 'true')
                        list_item.setInfo('video', {'title': display_title})
                        
                        # Use Name + Episode Title for player title so Trakt can parse it
                        full_player_title = f"{name} - {episode_title}"
                        url_params = {'mode': 'play_source', 'url': source_url, 'title': full_player_title}
                        
                        context_menu_items = [('Download', f'RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(source_url)})')]
                        list_item.addContextMenuItems(context_menu_items)
                        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)

def list_korean_episodes_and_sources(url, name=""):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch episode page: {e}")
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    content = soup.find('div', class_='entry-content')
    if not content:
        content = soup.find('div', class_='cm-entry-summary')
    if not content:
        content = soup.find('article')
    
    if not content:
        xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), "Nu s-a gasit continutul paginii.", xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Check for season headers (h2, h3 or h4)
    season_headers = content.find_all(['h2', 'h3', 'h4'], string=re.compile(r'SEZONUL', re.IGNORECASE))

    if season_headers:
        for i, header in enumerate(season_headers):
            season_title = header.text.strip()
            # Pass the entire content and the start element index to the next function
            url_params = {
                'mode': 'list_korean_season_episodes',
                'url': url, # Pass the page URL
                'season_title': season_title,
                'name': name # Pass show name
            }
            list_item = xbmcgui.ListItem(season_title)
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Original logic for pages without seasons or if no season headers were found
    # Try to detect if the page contains direct episode links (e.g., EP.1 VK)
    direct_episode_links_found = False
    all_links = content.find_all('a', href=True)
    for link in all_links:
        link_text = link.text.strip()
        if re.search(r'ep(?:isodul|\.|\s*)?\s*\d+', link_text, re.IGNORECASE):
            direct_episode_links_found = True
            break

    if direct_episode_links_found:
        # Process pages with direct episode links (e.g., "EP.1 VK")
        for link in all_links:
            link_text = link.text.strip()
            if re.search(r'ep(?:isodul|\.|\s*)?\s*\d+', link_text, re.IGNORECASE):
                source_url = link['href']
                display_title = link_text

                list_item = xbmcgui.ListItem(display_title)
                list_item.setProperty('IsPlayable', 'true')
                list_item.setInfo('video', {'title': display_title})
                
                # Use Show Name + Episode Title
                full_player_title = f"{name} - {display_title}"
                url_params = {'mode': 'play_source', 'url': source_url, 'title': full_player_title}
                
                context_menu_items = [('Download', f'RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(source_url)})')]
                list_item.addContextMenuItems(context_menu_items)
                xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)
    else:
        # Universal logic using descendants to handle all structures (nested or sibling)
        current_episode_title = ""
        
        # Iterate through all descendants to find titles and sources in order
        for node in content.descendants:
            if node.name == 'iframe':
                iframe = node
                if current_episode_title:
                    video_url = iframe.get('src')
                    if not video_url or video_url == 'about:blank':
                        video_url = iframe.get('data-src')
                    if not video_url or video_url == 'about:blank':
                        video_url = iframe.get('data-lazy-src')
                        
                    if video_url and video_url != 'about:blank':
                        if video_url.startswith('//'):
                            video_url = 'https:' + video_url
                        
                        domain = urllib.parse.urlparse(video_url).netloc.replace('www.', '')
                        display_title = f"{current_episode_title} - {domain}"
                        list_item = xbmcgui.ListItem(display_title)
                        list_item.setProperty('IsPlayable', 'true')
                        list_item.setInfo('video', {'title': display_title})
                        
                        full_player_title = f"{name} - {current_episode_title}"
                        url_params = {'mode': 'play_source', 'url': video_url, 'title': full_player_title}
                        
                        context_menu_items = [('Download', f'RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(video_url)})')]
                        list_item.addContextMenuItems(context_menu_items)
                        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)
            
            elif node.name == 'a' and current_episode_title:
                # Handle <a> tags as sources
                source_url = node.get('href')
                if source_url:
                    source_name = node.text.strip()
                    if not source_name or 'episodul' in source_name.lower() or 'episod' in source_name.lower():
                         # This might be a link acting as a title, not a source
                         pass 
                    else:
                        display_title = f"{current_episode_title} - {source_name}"
                        list_item = xbmcgui.ListItem(display_title)
                        list_item.setProperty('IsPlayable', 'true')
                        list_item.setInfo('video', {'title': display_title})
                        
                        full_player_title = f"{name} - {current_episode_title}"
                        url_params = {'mode': 'play_source', 'url': source_url, 'title': full_player_title}
                        
                        context_menu_items = [('Download', f'RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(source_url)})')]
                        list_item.addContextMenuItems(context_menu_items)
                        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)

            elif isinstance(node, str): # NavigableString
                text_val = node.strip()
                if text_val and ('episodul' in text_val.lower() or 'episod' in text_val.lower()):
                    # Check for episode title in text nodes
                    # Use basic heuristics to ensure it's a title and not a long sentence
                    if len(text_val) < 50: 
                        parts = re.split(r'–|-', text_val)
                        if parts:
                             current_episode_title = parts[0].strip()

    xbmcplugin.endOfDirectory(HANDLE)

def list_korean_season_episodes(url, season_title, name=""):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch episode page: {e}")
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    content = soup.find('div', class_='entry-content')
    if not content:
        content = soup.find('div', class_='cm-entry-summary')
    if not content:
        content = soup.find('article')

    if not content:
        xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), "Nu s-a gasit continutul paginii.", xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    start_element = content.find(['h2', 'h3', 'h4'], string=re.compile(season_title, re.IGNORECASE))
    if not start_element:
        return

    current_episode_title = ""
    
    # Try to detect if the season content contains direct episode links (e.g., EP.1 VK)
    direct_episode_links_found_in_season = False
    season_links = start_element.find_next_siblings('a', href=True)
    for element in start_element.find_next_siblings():
        if element.name in ['h2', 'h3', 'h4'] and 'SEZONUL' in element.text.upper():
            break
        if element.name in ['p', 'h3']:
            for link in element.find_all('a', href=True):
                link_text = link.text.strip()
                if re.search(r'ep(?:isodul|\.|\s*)?\s*\d+', link_text, re.IGNORECASE):
                    direct_episode_links_found_in_season = True
                    break
            if direct_episode_links_found_in_season:
                break

    if direct_episode_links_found_in_season:
        # Process direct episode links within the season
        for element in start_element.find_next_siblings():
            if element.name in ['h2', 'h3', 'h4'] and 'SEZONUL' in element.text.upper():
                break
            if element.name in ['p', 'h3']:
                for link in element.find_all('a', href=True):
                    link_text = link.text.strip()
                    if re.search(r'ep(?:isodul|\.|\s*)?\s*\d+', link_text, re.IGNORECASE):
                        source_url = link['href']
                        display_title = link_text

                        list_item = xbmcgui.ListItem(display_title)
                        list_item.setProperty('IsPlayable', 'true')
                        list_item.setInfo('video', {'title': display_title})
                        
                        full_player_title = f"{name} - {display_title}"
                        url_params = {'mode': 'play_source', 'url': source_url, 'title': full_player_title}
                        
                        context_menu_items = [('Download', f'RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(source_url)})')]
                        list_item.addContextMenuItems(context_menu_items)
                        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)
    else:
        # Universal logic using descendants for season elements
        elements_in_season = []
        for element in start_element.find_next_siblings():
            if element.name in ['h2', 'h3', 'h4'] and 'SEZONUL' in element.text.upper():
                break  # Stop when the next season starts
            elements_in_season.append(element)

        current_episode_title = ""
        for element_container in elements_in_season:
            # iterate descendants of each top-level element in the season block
            for node in element_container.descendants:
                if node.name == 'iframe':
                    iframe = node
                    if current_episode_title:
                        video_url = iframe.get('src')
                        if not video_url or video_url == 'about:blank':
                            video_url = iframe.get('data-src')
                        if not video_url or video_url == 'about:blank':
                            video_url = iframe.get('data-lazy-src')
                            
                        if video_url and video_url != 'about:blank':
                            if video_url.startswith('//'):
                                video_url = 'https:' + video_url
                            
                            domain = urllib.parse.urlparse(video_url).netloc.replace('www.', '')
                            display_title = f"{current_episode_title} - {domain}"
                            list_item = xbmcgui.ListItem(display_title)
                            list_item.setProperty('IsPlayable', 'true')
                            list_item.setInfo('video', {'title': display_title})
                            
                            full_player_title = f"{name} - {current_episode_title}"
                            url_params = {'mode': 'play_source', 'url': video_url, 'title': full_player_title}
                            
                            context_menu_items = [('Download', f'RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(video_url)})')]
                            list_item.addContextMenuItems(context_menu_items)
                            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)
                
                elif node.name == 'a' and current_episode_title:
                     # Handle <a> tags as sources
                    source_url = node.get('href')
                    if source_url:
                        source_name = node.text.strip()
                        if not source_name or 'episodul' in source_name.lower() or 'episod' in source_name.lower():
                             pass
                        else:
                            display_title = f"{current_episode_title} - {source_name}"
                            list_item = xbmcgui.ListItem(display_title)
                            list_item.setProperty('IsPlayable', 'true')
                            list_item.setInfo('video', {'title': display_title})
                            
                            full_player_title = f"{name} - {current_episode_title}"
                            url_params = {'mode': 'play_source', 'url': source_url, 'title': full_player_title}
                            
                            context_menu_items = [('Download', f'RunPlugin({sys.argv[0]}?mode=download_source&url={urllib.parse.quote_plus(source_url)})')]
                            list_item.addContextMenuItems(context_menu_items)
                            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)

                elif isinstance(node, str): # NavigableString
                    text_val = node.strip()
                    if text_val and ('episodul' in text_val.lower() or 'episod' in text_val.lower()):
                        # Check for episode title in text nodes
                         if len(text_val) < 50:
                            parts = re.split(r'–|-', text_val)
                            if parts:
                                 current_episode_title = parts[0].strip()

    xbmcplugin.endOfDirectory(HANDLE)

def list_movies_categories():
    movies_categories = [
        {'title': 'Filme de epoca', 'url': 'https://blogul-lui-atanase.ro/categorie/nostalgia/'},
        {'title': 'Filme de Craciun', 'url': 'https://blogul-lui-atanase.ro/categorie/filme-de-craciun/'},
        {'title': 'Filme Coreene', 'url': 'https://blogul-lui-atanase.ro/categorie/filme-coreene/'},
        {'title': 'Filme Chinezesti', 'url': 'https://blogul-lui-atanase.ro/categorie/filme-chinezesti/'},
        {'title': 'Filme Japoneze', 'url': 'https://blogul-lui-atanase.ro/categorie/serialefilme-japoneze/'},
        {'title': 'Filme Indiene', 'url': 'https://blogul-lui-atanase.ro/categorie/filme-indiene/'},
        {'title': 'Filme Turcesti', 'url': 'https://blogul-lui-atanase.ro/categorie/filme-turcesti/'}
    ]

    for category in movies_categories:
        list_item = xbmcgui.ListItem(category['title'])
        icon = "https://1.bp.blogspot.com/-5utXzUd3Wk0/XcatUqtM9pI/AAAAAAAACTU/8Jbt1d8gO8Y7XVLGQnjHYYnJ9ou1_kTLACLcBGAsYHQ/s1600/www.tvnowstream.de.jpg"
        list_item.setArt({'icon': icon, 'thumb': icon})
        url_params = {
            'mode': 'list_movies',
            'url': category['url'],
            'name': category['title']
        }
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_serialecoreene_all_series(url, name, page='1'):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch all series for {name}: {e}")
        return

    container = soup.find('div', class_='movies-list movies-list-full')
    if not container:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for item in container.find_all('div', class_='ml-item'):
        link_element = item.find('a', class_='ml-mask')
        img_element = item.find('img', class_='mli-thumb')
        title_element = item.find('h2')

        if link_element and img_element and title_element:
            series_url = link_element['href']
            title = title_element.text.strip()
            thumb = img_element.get('data-original', img_element.get('src', ''))

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({'thumb': thumb, 'icon': thumb})
            list_item.setInfo('video', {'title': title})
            url_params = {'mode': 'list_serialecoreene_episodes_and_sources', 'url': series_url, 'name': title}
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Pagination
    next_page_link = soup.find('a', class_='page larger', rel='nofollow', string=str(int(page) + 1))
    if next_page_link and next_page_link.has_attr('href'):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem('Next Page >>')
        url_params = {'mode': 'list_serialecoreene_all_series', 'url': url, 'name': name, 'page': str(next_page_num)}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_serialecoreene_all_series(url, name, page='1'):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch all series for {name}: {e}")
        return

    container = soup.find('div', class_='movies-list movies-list-full')
    if not container:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for item in container.find_all('div', class_='ml-item'):
        link_element = item.find('a', class_='ml-mask')
        img_element = item.find('img', class_='mli-thumb')
        title_element = item.find('h2')

        if link_element and img_element and title_element:
            series_url = link_element['href']
            title = title_element.text.strip()
            thumb = img_element.get('data-original', img_element.get('src', ''))

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({'thumb': thumb, 'icon': thumb})
            list_item.setInfo('video', {'title': title})
            url_params = {'mode': 'list_serialecoreene_episodes_and_sources', 'url': series_url, 'name': title}
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Pagination
    next_page_link = soup.find('a', class_='page larger', rel='nofollow', string=str(int(page) + 1))
    if next_page_link and next_page_link.has_attr('href'):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem('Next Page >>')
        url_params = {'mode': 'list_serialecoreene_all_series', 'url': url, 'name': name, 'page': str(next_page_num)}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_serialecoreene_korean_series(url, name, page='1'):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch Korean series for {name}: {e}")
        return

    container = soup.find('div', class_='movies-list movies-list-full')
    if not container:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for item in container.find_all('div', class_='ml-item'):
        link_element = item.find('a', class_='ml-mask')
        img_element = item.find('img', class_='mli-thumb')
        title_element = item.find('h2')

        if link_element and img_element and title_element:
            series_url = link_element['href']
            title = title_element.text.strip()
            thumb = img_element.get('data-original', img_element.get('src', ''))

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({'thumb': thumb, 'icon': thumb})
            list_item.setInfo('video', {'title': title})
            url_params = {'mode': 'list_serialecoreene_episodes_and_sources', 'url': series_url, 'name': title}
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Pagination
    next_page_link = soup.find('a', class_='page larger', rel='nofollow', string=str(int(page) + 1))
    if next_page_link and next_page_link.has_attr('href'):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem('Next Page >>')
        url_params = {'mode': 'list_serialecoreene_korean_series', 'url': url, 'name': name, 'page': str(next_page_num)}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_serialecoreene_thai_series(url, name, page='1'):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch Thai series for {name}: {e}")
        return

    container = soup.find('div', class_='movies-list movies-list-full')
    if not container:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for item in container.find_all('div', class_='ml-item'):
        link_element = item.find('a', class_='ml-mask')
        img_element = item.find('img', class_='mli-thumb')
        title_element = item.find('h2')

        if link_element and img_element and title_element:
            series_url = link_element['href']
            title = title_element.text.strip()
            thumb = img_element.get('data-original', img_element.get('src', ''))

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({'thumb': thumb, 'icon': thumb})
            list_item.setInfo('video', {'title': title})
            url_params = {'mode': 'list_serialecoreene_episodes_and_sources', 'url': series_url, 'name': title}
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Pagination
    next_page_link = soup.find('a', class_='page larger', rel='nofollow', string=str(int(page) + 1))
    if next_page_link and next_page_link.has_attr('href'):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem('Next Page >>')
        url_params = {'mode': 'list_serialecoreene_thai_series', 'url': url, 'name': name, 'page': str(next_page_num)}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_serialecoreene_new_episodes(url, name, page='1'):
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    try:
        response = _get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch new episodes for {name}: {e}")
        return

    container = soup.find('div', class_='movies-list movies-list-full')
    if not container:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for item in container.find_all('div', class_='ml-item'):
        link_element = item.find('a', class_='ml-mask')
        img_element = item.find('img', class_='mli-thumb')
        title_element = item.find('h2')

        if link_element and img_element and title_element:
            series_url = link_element['href']
            title = title_element.text.strip()
            thumb = img_element.get('data-original', img_element.get('src', ''))

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({'thumb': thumb, 'icon': thumb})
            list_item.setInfo('video', {'title': title})
            list_item.setProperty('IsPlayable', 'true') # Mark as playable
            url_params = {'mode': 'play_serialecoreene_episode', 'url': series_url, 'name': title}
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)

    # Pagination
    next_page_link = soup.find('a', class_='page larger', rel='nofollow', string=str(int(page) + 1))
    if next_page_link and next_page_link.has_attr('href'):
        next_page_num = int(page) + 1
        list_item = xbmcgui.ListItem('Next Page >>')
        url_params = {'mode': 'list_serialecoreene_new_episodes', 'url': url, 'name': name, 'page': str(next_page_num)}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_serialecoreene_episodes_and_sources(url):
    try:
        response = _get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Failed to fetch episode page: {e}")
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    seasons_container = soup.find('div', id='seasons')
    if not seasons_container:
        xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), "Nu s-au gasit sezoane pentru acest serial.", xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Assuming each .tvseason contains a season and its episodes
    for season_div in seasons_container.find_all('div', class_='tvseason'):
        season_title_element = season_div.find('strong')
        if not season_title_element:
            continue
        season_title = season_title_element.text.strip()

        # Iterate through episode links within the current season
        for episode_link in season_div.find_all('a', href=True):
            episode_url = episode_link['href']
            episode_name = episode_link.text.strip()
            
            display_title = f"{season_title} - {episode_name}"

            list_item = xbmcgui.ListItem(display_title)
            list_item.setInfo('video', {'title': display_title})
            list_item.setProperty('IsPlayable', 'true') # Mark as playable, actual playback happens in play_serialecoreene_episode
            url_params = {'mode': 'play_serialecoreene_episode', 'url': episode_url, 'name': display_title}
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=False)
            
    xbmcplugin.endOfDirectory(HANDLE)

def list_serialecoreene_main():
    base_url = "https://serialecoreene.org/"
    icon = "https://serialecoreene.org/wp-content/uploads/2023/10/coreene-logo.png"

    # Toate Seriale
    list_item = xbmcgui.ListItem('Toate Seriale')
    list_item.setArt({'icon': icon, 'thumb': icon})
    url_params = {'mode': 'list_serialecoreene_all_series', 'url': base_url + 'series/', 'name': 'Toate Seriale'}
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Seriale Coreene
    list_item = xbmcgui.ListItem('Seriale Coreene')
    list_item.setArt({'icon': icon, 'thumb': icon})
    url_params = {'mode': 'list_serialecoreene_korean_series', 'url': base_url + 'genre/seriale-coreene/', 'name': 'Seriale Coreene'}
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Seriale Thailandeze
    list_item = xbmcgui.ListItem('Seriale Thailandeze')
    list_item.setArt({'icon': icon, 'thumb': icon})
    url_params = {'mode': 'list_serialecoreene_thai_series', 'url': base_url + 'genre/thailanda/', 'name': 'Seriale Thailandeze'}
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Episoade Noi
    list_item = xbmcgui.ListItem('Episoade Noi')
    list_item.setArt({'icon': icon, 'thumb': icon})
    url_params = {'mode': 'list_serialecoreene_new_episodes', 'url': base_url + 'episode/', 'name': 'Episoade Noi'}
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_turkish_series_categories():
    # Item for "Seriale Turcesti (Toate)"
    list_item = xbmcgui.ListItem('Seriale Turcesti (Toate)')
    turk_icon = "https://fuzzy.ro/wp-content/uploads/2023/01/seriale-turcesti.jpg"
    list_item.setArt({'icon': turk_icon, 'thumb': turk_icon})
    url_params = {
        'mode': 'list_turkish_series',
        'url': 'https://www.terasacucarti.com/n-toate-serialele-turcesti-subtitrate/'
    }
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params), listitem=list_item, isFolder=True)

    # Item for "Seriale Turcesti Finalizate"
    list_item = xbmcgui.ListItem('Seriale turcesti finalizate')
    turk_final_icon = "https://fuzzy.ro/wp-content/uploads/2023/01/seriale-turcesti.jpg"
    list_item.setArt({'icon': turk_final_icon, 'thumb': turk_final_icon})
    url_params_finished = {
        'mode': 'list_finished_turkish_series',
        'url': 'https://www.terasacucarti.com/a-seriale-turcesti-finalizate-terasa-cu-carti/'
    }
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params_finished), listitem=list_item, isFolder=True)

    # Item for "Alte Seriale"
    list_item = xbmcgui.ListItem('Alte Seriale')
    alte_icon = "https://fuzzy.ro/wp-content/uploads/2023/01/seriale-turcesti.jpg"
    list_item.setArt({'icon': alte_icon, 'thumb': alte_icon})
    url_params_alte = {
        'mode': 'list_alte_seriale',
        'url': 'https://www.terasacucarti.com/alte-seriale-subtitrate-in-romana/'
    }
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=sys.argv[0] + '?' + urllib.parse.urlencode(url_params_alte), listitem=list_item, isFolder=True)
    
    xbmcplugin.endOfDirectory(HANDLE)

def _extract_js_redirect_param(html_content, func_name):
    # Search for the function definition with flexible whitespace
    func_pattern = rf'function\s+{re.escape(func_name)}\s*\(\)\s*\{{\s*window\.location\.href\s*=\s*"([^"]+)"\s*;\s*\}}'
    match = re.search(func_pattern, html_content)
    if match:
        return match.group(1)
    return None

def play_serialecoreene_episode(url, name):
    xbmc.log(f"[{ADDON.getAddonInfo('name')}] Starting play_serialecoreene_episode for: {url}", xbmc.LOGINFO)
    try:
        # Step 1: Fetch the episode page
        response1 = _get_html_content(url)
        response1.raise_for_status()
        soup1 = BeautifulSoup(response1.text, 'html.parser')

        # Find the href from #iframeload
        iframe_load_link = soup1.find('a', id='iframeload')
        if not iframe_load_link or 'href' not in iframe_load_link.attrs:
            xbmc.log(f"[{ADDON.getAddonInfo('name')}] iframeload link not found", xbmc.LOGERROR)
            xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), "Nu s-a gasit link-ul iframeload.")
            return
        target_div_id = iframe_load_link['href'].lstrip('#') # e.g., srv1
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] Target div ID: {target_div_id}", xbmc.LOGINFO)

        # Find the div with the target ID
        target_div = soup1.find('div', id=target_div_id)
        if not target_div:
            xbmc.log(f"[{ADDON.getAddonInfo('name')}] Target div not found", xbmc.LOGERROR)
            xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), "Nu s-a gasit div-ul sursei.")
            return

        # Extract onclick function from #buttonx
        button_x = target_div.find('a', id='buttonx')
        if not button_x or 'onclick' not in button_x.attrs:
            xbmc.log(f"[{ADDON.getAddonInfo('name')}] buttonx not found or no onclick", xbmc.LOGERROR)
            xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), "Nu s-a gasit butonul de redare.")
            return
        onclick_func = button_x['onclick'].replace('()', '') # e.g., redirectPage2
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] Onclick function: {onclick_func}", xbmc.LOGINFO)

        # Extract the redirect parameter from the script
        redirect_param1 = _extract_js_redirect_param(response1.text, onclick_func)
        if not redirect_param1:
            xbmc.log(f"[{ADDON.getAddonInfo('name')}] Failed to extract redirect param 1. Func: {onclick_func}", xbmc.LOGERROR)
            # Log a snippet of the HTML around the expected function for debugging
            # regex search for function name to see what it looks like
            partial_match = re.search(rf'function\s+{re.escape(onclick_func)}', response1.text)
            if partial_match:
                start = partial_match.start()
                xbmc.log(f"[{ADDON.getAddonInfo('name')}] Snippet: {response1.text[start:start+100]}", xbmc.LOGINFO)
            else:
                xbmc.log(f"[{ADDON.getAddonInfo('name')}] Function definition not found in HTML", xbmc.LOGINFO)

            xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), "Nu s-a putut extrage primul parametru de redirect.")
            return
        
        # Construct the first redirect URL
        first_redirect_url = urllib.parse.urljoin(url, redirect_param1)
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] First redirect URL: {first_redirect_url}", xbmc.LOGINFO)

        # Step 2: Fetch the first redirect page
        response2 = _get_html_content(first_redirect_url)
        response2.raise_for_status()
        soup2 = BeautifulSoup(response2.text, 'html.parser')

        # Find the onclick for the second redirect (rdrtnow)
        # The button is often injected via JavaScript, so soup.find might fail.
        # We search for the pattern in the raw text.
        # Looking for: onclick="funcName()" potentially escaped
        rdrtnow_match = re.search(r'onclick=\\?["\']([a-zA-Z0-9_]+)\(\)\\?["\']', response2.text)
        
        if not rdrtnow_match:
            # Fallback: try to find the button if it IS in the DOM
            rdrtnow_button = soup2.find('button', onclick=re.compile(r'.+'))
            if rdrtnow_button:
                 rdrtnow_func = rdrtnow_button['onclick'].replace('()', '')
            else:
                xbmc.log(f"[{ADDON.getAddonInfo('name')}] Second redirect button/function not found in HTML or JS", xbmc.LOGERROR)
                xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), "Nu s-a gasit butonul de accesare acum (step 2).")
                return
        else:
            rdrtnow_func = rdrtnow_match.group(1)

        xbmc.log(f"[{ADDON.getAddonInfo('name')}] rdrtnow function: {rdrtnow_func}", xbmc.LOGINFO)

        # Extract the second redirect parameter
        redirect_param2 = _extract_js_redirect_param(response2.text, rdrtnow_func)
        if not redirect_param2:
            xbmc.log(f"[{ADDON.getAddonInfo('name')}] Failed to extract redirect param 2. Func: {rdrtnow_func}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), "Nu s-a putut extrage al doilea parametru de redirect.")
            return

        # Construct the second redirect URL
        final_page_url = urllib.parse.urljoin(url, redirect_param2)
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] Final page URL: {final_page_url}", xbmc.LOGINFO)

        # Step 3: Fetch the final page and find the iframe src
        response3 = _get_html_content(final_page_url)
        response3.raise_for_status()
        soup3 = BeautifulSoup(response3.text, 'html.parser')

        final_iframe = soup3.find('iframe', src=True)
        if not final_iframe or 'src' not in final_iframe.attrs:
            xbmc.log(f"[{ADDON.getAddonInfo('name')}] Final iframe not found", xbmc.LOGERROR)
            xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), "Nu s-a gasit sursa finala de redare.")
            return

        video_url = final_iframe['src']
        if video_url.startswith('//'):
            video_url = 'https:' + video_url
        
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] Video URL: {video_url}", xbmc.LOGINFO)

        # Step 4: Resolve and play the video
        resolved_url = resolve_url_wrapper(video_url)
        if resolved_url:
            xbmc.log(f"[{ADDON.getAddonInfo('name')}] Resolved URL: {resolved_url}", xbmc.LOGINFO)
            list_item = xbmcgui.ListItem(path=resolved_url)
            list_item.setInfo('video', {'title': name})
            
            # Communicate title to service
            xbmcgui.Window(10000).setProperty('VeziAici_Title', name)
            
            xbmcplugin.setResolvedUrl(HANDLE, True, list_item)
        else:
            xbmc.log(f"[{ADDON.getAddonInfo('name')}] Could not resolve URL", xbmc.LOGERROR)
            xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), "Could not resolve video URL.")

    except requests.exceptions.RequestException as e:
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] Request Error: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"Eroare la preluarea paginii: {e}")
    except Exception as e:
        xbmc.log(f"[{ADDON.getAddonInfo('name')}] Unexpected Error: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), f"A aparut o eroare neasteptata: {e}")

def download_source(url):
    resolved_url = resolve_url_wrapper(url)
    if resolved_url:
        # The most reliable way to handle downloads in Kodi for external URLs
        # is to use the Download builtin with the resolved URL
        xbmc.executebuiltin(f'Download("{resolved_url}")')
    else:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), "Could not resolve video URL for download.")

def router(paramstring):
    params = dict(urllib.parse.parse_qsl(paramstring))
    mode = params.get('mode')
    name = params.get('name')
    url = params.get('url')
    title = params.get('title') # Extract title for play_source
    shows = params.get('shows')
    episodes = params.get('episodes')
    season = params.get('season')
    latest_url = params.get('latest_url')
    page = params.get('page', '1')
    season_title = params.get('season_title')

    if mode is None:
        list_main_menu()
    elif mode == 'list_show_categories':
        list_show_categories(shows, name, latest_url)
    elif mode == 'list_latest':
        list_latest(url, name)
    elif mode == 'list_episodes':
        list_episodes(url, name)
    elif mode == 'list_episodes_for_season':
        list_episodes_for_season(episodes, season, name)
    elif mode == 'list_search_results':
        list_search_results(url)
    elif mode == 'list_sources':
        list_sources(url, name) # Pass name here
    elif mode == 'play_source':
        play_source(url, title) # Pass title here
    elif mode == 'search':
        search()
    elif mode == 'list_turkish_series_categories':
        list_turkish_series_categories()
    elif mode == 'list_turkish_series' or mode == 'list_finished_turkish_series' or mode == 'list_alte_seriale':
        list_turkish_series(url, mode, page)
    elif mode == 'list_turkish_episodes':
        list_turkish_episodes(url, name)
    elif mode == 'list_turkish_sources':
        list_turkish_sources(url, name) # Pass name
    elif mode == 'list_korean_series_categories':
        list_korean_series_categories()
    elif mode == 'list_korean_series_years':
        list_korean_series_years()
    elif mode == 'list_korean_series':
        list_korean_series(url, name, page)
    elif mode == 'list_korean_episodes_and_sources':
        list_korean_episodes_and_sources(url, name) # Pass name
    elif mode == 'list_korean_season_episodes':
        list_korean_season_episodes(url, season_title, name) # Pass name too
    elif mode == 'list_movies_categories':
        list_movies_categories()
    elif mode == 'list_serialecoreene_main':
        list_serialecoreene_main()
    elif mode == 'list_serialecoreene_all_series':
        list_serialecoreene_all_series(url, name, page)
    elif mode == 'list_serialecoreene_korean_series':
        list_serialecoreene_korean_series(url, name, page)
    elif mode == 'list_serialecoreene_thai_series':
        list_serialecoreene_thai_series(url, name, page)
    elif mode == 'list_serialecoreene_new_episodes':
        list_serialecoreene_new_episodes(url, name, page)
    elif mode == 'list_serialecoreene_episodes_and_sources':
        list_serialecoreene_episodes_and_sources(url)
    elif mode == 'list_movies':
        list_movies(url, name, page)
    elif mode == 'list_movie_sources':
        list_movie_sources(url, name) # Pass name
    elif mode == 'list_series_episodes':
        list_series_episodes(url, name)
    elif mode == 'play_serialecoreene_episode':
        play_serialecoreene_episode(url, name)
    elif mode == 'download_source':
        download_source(url)
    elif mode == 'authorize_trakt':
        TraktAPI().authorize()
    elif mode == 'revoke_trakt':
        TraktAPI().revoke_auth()

if __name__ == '__main__':
    router(sys.argv[2][1:])
