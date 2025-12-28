import requests
import re
import urllib.parse
from urllib.parse import urlparse
import xbmcgui
import xbmcplugin

BASE_URL = "https://api.themoviedb.org/3"
API_KEY = "8ad3c21a92a64da832c559d58cc63ab4"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}

def get_json(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        return r.json()
    except: return {}

def get_ids(content_type, tmdb_id):
    url = f"{BASE_URL}/{content_type}/{tmdb_id}/external_ids?api_key={API_KEY}"
    return get_json(url)

import json # Adăugat pentru manipularea datelor brute

def get_all_sources(imdb_id, content_type, season=None, episode=None):
    providers = [
        {"name": "Vflix", "url": "https://vidzee.vflix.life"},    
        {"name": "Nuviostream", "url": "https://nuviostreams.hayd.uk/stream"},
        {"name": "WebStream", "url": "https://webstreamr.hayd.uk/stream"},   
    ]
    
    found_sources = []
    
    for srv in providers:
        try:
            if content_type == 'movie':
                api_url = f"{srv['url']}/movie/{imdb_id}.json"
            else:
                api_url = f"{srv['url']}/series/{imdb_id}:{season}:{episode}.json"
            
            r = requests.get(api_url, headers=HEADERS, timeout=15)
            data = r.json() 
            streams = data.get('streams', [])
            
            for index, stream in enumerate(streams):
                url_raw = stream.get('url')
                if not url_raw: continue
                
                # Extragem calitatea din 'title' sau 'name' folosind Regex
                # Aceste API-uri pun de obicei "1080p" sau "720p" în descriere
                stream_info = stream.get('title', '') + " " + stream.get('name', '')
                quality_match = re.search(r'(\d{3,4}p)', stream_info)
                quality = quality_match.group(1) if quality_match else "HD"
                
                # Identificăm providerul real (ex: Vix, UpToBox, etc.) din text
                provider_detail = stream.get('name', srv['name']).replace('\n', ' ')
                
                clean_url = url_raw.replace('\\/', '/')
                domain = urlparse(clean_url).netloc.replace('www.', '')
                
                # Construim eticheta astfel încât să fie numerotată și clară
                label = f"[{quality}] {srv['name']} - Sursa {index + 1} ({domain})"
                
                final_link = clean_url + "|User-Agent=" + urllib.parse.quote(HEADERS['User-Agent'])
                
                found_sources.append({
                    'label': label,
                    'path': final_link,
                    'quality_val': int(quality.replace('p', '')) if quality.replace('p', '').isdigit() else 0
                })
                
        except Exception as e:
            print(f"Eroare la {srv['name']}: {str(e)}")
            continue
            
    # Sortăm sursele după calitate (cele mai bune primele)
    found_sources.sort(key=lambda x: x['quality_val'], reverse=True)
    
    return found_sources

def play_item(params, handle):
    tmdb_id = params.get('tmdb_id')
    c_type = params.get('type')
    progress = xbmcgui.DialogProgress()
    progress.create("Căutare surse", "Scanăm serverele...")
    
    ids = get_ids(c_type, tmdb_id)
    imdb_id = ids.get('imdb_id')
    
    if not imdb_id:
        progress.close()
        xbmcgui.Dialog().ok("Eroare", "ID IMDb lipsă.")
        return

    sources = get_all_sources(imdb_id, c_type, params.get('season'), params.get('episode'))
    progress.close()
    
    if not sources:
        xbmcgui.Dialog().ok("Eroare", "Nu am găsit link-uri.")
        return

    sources.sort(key=lambda x: 0 if 'vix' in x['label'].lower() or 'vix' in x['path'].lower() else 1)
    
    labels = [s['label'] for s in sources]
    selection = xbmcgui.Dialog().select("Alege un server", labels)
    
    if selection != -1:
        selected_source = sources[selection]['path']
        play_li = xbmcgui.ListItem(params.get('title'), path=selected_source)
        
        video_info = {
            'title': params.get('title'),
            'imdbnumber': imdb_id,
            'code': imdb_id
        }
        
        if c_type == 'tv':
            video_info.update({
                'season': int(params.get('season')),
                'episode': int(params.get('episode')),
                'mediatype': 'episode'
            })
        else:
            video_info.update({'mediatype': 'movie'})

        play_li.setInfo('video', video_info)
        xbmcplugin.setResolvedUrl(handle, True, listitem=play_li)
