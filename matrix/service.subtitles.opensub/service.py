# -*- coding: utf-8 -*-
import os, sys, xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs, requests, threading
from urllib.parse import unquote, urlencode, parse_qsl

__addon__ = xbmcaddon.Addon()
__id__ = __addon__.getAddonInfo('id')
lib_path = xbmcvfs.translatePath(os.path.join(__addon__.getAddonInfo('path'), 'resources', 'lib'))
sys.path.append(lib_path)

try: import robot
except: xbmc.log("ROBOT LIB NOT FOUND", xbmc.LOGERROR)

try: import loader
except: xbmc.log("LOADER LIB NOT FOUND", xbmc.LOGERROR)

HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else 0

def search():
    imdb_id = xbmc.getInfoLabel("VideoPlayer.IMDBNumber") or xbmc.getInfoLabel("ListItem.Property(imdb_id)")
    season = xbmc.getInfoLabel("VideoPlayer.Season")
    episode = xbmc.getInfoLabel("VideoPlayer.Episode")
    
    if not imdb_id: 
        xbmc.log("OPENSUBS: No IMDB ID found", xbmc.LOGERROR)
        return

    langs = ["ro", "en", "es", "fr", "de", "it", "hu", "pt", "ru", "tr", "bg", "el", "pl", "cs", "nl"]
    iso_mapping = {"ro": "rum", "en": "eng", "es": "spa", "fr": "fre", "de": "ger", "it": "ita", "hu": "hun", "pt": "por", "ru": "rus", "tr": "tur", "bg": "bul", "el": "ell", "pl": "pol", "cs": "cze", "nl": "dut"}
    
    idx = __addon__.getSettingInt('subs_languages')
    l_code = langs[idx]
    robot_activat = __addon__.getSettingBool('robot_activat')

    all_results = []
    clean_imdb = imdb_id.replace('tt','')

    # --- CONSTRUIRE QUERY CONFORM CERINTEI TALE ---
    if season and episode:
        query_path = f"episode-{episode}/imdbid-{clean_imdb}/season-{season}"
    else:
        query_path = f"imdbid-{clean_imdb}"

    targets = [l_code]
    if l_code != "en" and robot_activat:
        targets.append("en")

    for target_lang in targets:
        try:
            long_lang = iso_mapping.get(target_lang, "eng")
            os_url = f"https://rest.opensubtitles.org/search/{query_path}/sublanguageid-{long_lang}"
            
            r = requests.get(os_url, headers={'User-Agent': 'HotSubtitlesV1'}, timeout=10)
            if r.ok:
                for item in r.json():
                    t_code = item.get('ISO639', 'en')
                    # MODIFICARE: Folosim link-ul de Stremio cu IDSubtitleFile
                    sub_id = item.get('IDSubtitleFile')
                    stremio_url = f"https://subs5.strem.io/en/download/subencoding-stremio-utf8/src-api/file/{sub_id}"
                    
                    all_results.append({
                        'label': f"[{item.get('LanguageName')}] {item.get('SubFileName')}",
                        'url': stremio_url,
                        'l_code': t_code, 
                        'api_filename': item.get('SubFileName'), 
                        'is_chosen': (t_code == l_code)
                    })
        except Exception as e:
            xbmc.log(f"OPENSUBS ERROR: {str(e)}", xbmc.LOGERROR)

    # --- FALLBACK ---
    if not all_results and robot_activat:
        try:
            os_url = f"https://rest.opensubtitles.org/search/{query_path}"
            r = requests.get(os_url, headers={'User-Agent': 'HotSubtitlesV1'}, timeout=10)
            if r.ok:
                for item in r.json():
                    t_code = item.get('ISO639', 'en')
                    sub_id = item.get('IDSubtitleFile')
                    stremio_url = f"https://subs5.strem.io/en/download/subencoding-stremio-utf8/src-api/file/{sub_id}"
                    all_results.append({
                        'label': f"[OS:ALL] {item.get('SubFileName')}",
                        'url': stremio_url,
                        'l_code': t_code, 
                        'api_filename': item.get('SubFileName'), 
                        'is_chosen': False
                    })
        except: pass

    all_results.sort(key=lambda x: (not x['is_chosen'], x['l_code']))

    for res in all_results:
        li = xbmcgui.ListItem(label=res['label'])
        li.setArt({'thumb': res['l_code']})
        d_params = {'action': 'download', 'url': res['url'], 'l_code': res['l_code'], 'api_filename': res['api_filename']}
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=f"{sys.argv[0]}?{urlencode(d_params)}", listitem=li)

    xbmcplugin.endOfDirectory(HANDLE)

def download(params):
    try:
        url = unquote(params.get('url', ''))
        l_code = params.get('l_code', 'ro')
        raw_name = params.get('api_filename') or 'subtitle'
        if raw_name.lower().endswith(".srt"): raw_name = raw_name[:-4]
        api_filename = f"{raw_name}.{l_code}.srt"

        chosen_lang = ["ro", "en", "es", "fr", "de", "it", "hu", "pt", "ru", "tr", "bg", "el", "pl", "cs", "nl"][__addon__.getSettingInt('subs_languages')]
        
        dest_dir = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))
        if not xbmcvfs.exists(dest_dir): xbmcvfs.mkdirs(dest_dir)
        
        _, files = xbmcvfs.listdir(dest_dir)
        for f in files: 
            if f.endswith(".srt"): xbmcvfs.delete(os.path.join(dest_dir, f))

        dest_path = os.path.join(dest_dir, api_filename)
        
        # Descarcă de pe subs5.strem.io
        r = requests.get(url, timeout=20)
        if r.ok:
            with open(dest_path, 'wb') as f:
                f.write(r.content)
            
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=dest_path, listitem=xbmcgui.ListItem(label=api_filename))
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True)
            xbmc.Player().setSubtitles(dest_path)
            
            if l_code != chosen_lang:
                threading.Thread(target=robot.run_translation, args=(__id__,)).start()
            else:
                threading.Thread(target=loader.run_false, args=(__id__,)).start()
                
    except Exception as e:
        xbmc.log(f"DL ERROR: {str(e)}", xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)

if __name__ == '__main__':
    p = dict(parse_qsl(sys.argv[2].lstrip('?'))) if len(sys.argv) > 2 else {}
    if p.get('action') == 'download': download(p)
    else: search()
