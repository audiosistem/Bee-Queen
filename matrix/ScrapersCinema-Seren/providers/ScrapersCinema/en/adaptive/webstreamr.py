# -*- coding: utf-8 -*-
from providerModules.ScrapersCinema import common
import requests
import time
import xbmcgui
import re
import json
from resources.lib.modules.exceptions import PreemptiveCancellation

class sources():
    def __init__(self):
        self.provider = "webstreamr"
        self.base_url = "https://webstreamr.hayd.uk"
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        self.language = ["en"]
        self.start_time = 0

    def log(self, message, level='debug'):
        common.log(f'{self.provider.upper()} >>> {message}', level=level)

    def _format_size(self, size_bytes):
        try:
            size_bytes = int(size_bytes)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
        except: return ""
        return ""

    def _process_item(self, item_url, simple_info):
        if simple_info.get("title"):
            release_name = f'{simple_info["title"]} ({simple_info["year"]})'
        else:
            release_name = f'{simple_info["show_title"]} ({simple_info["year"]}): {str(simple_info.get("season_number")).zfill(2)}x{str(simple_info.get("episode_number")).zfill(2)}'
        
        sources_list = []
        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(item_url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                self.log(f"Eroare HTTP: {response.status_code}")
                return []

            data = response.json()
            # Obținem lista de stream-uri. Dacă e direct listă, o folosim, altfel luăm cheia 'streams'
            streams = data.get('streams', []) if isinstance(data, dict) else data

            if not streams:
                self.log("Nu s-au găsit stream-uri în JSON.")
                return []

            for stream in streams:
                video_url = stream.get('url')
                if not video_url: continue

                # Extragem meta-datele și curățăm de linii noi
                raw_title = stream.get('title', '').replace('\n', ' ').replace('\r', ' ').strip()
                raw_name = stream.get('name', '').replace('\n', ' ').replace('\r', ' ').strip()
                title_full = (raw_title + " " + raw_name).upper()
                
                # --- Calitate ---
                quality = "1080p"
                if any(x in title_full for x in ['2160', '4K', 'UHD']): quality = '4K'
                elif '720' in title_full: quality = '720p'
                elif '480' in title_full or 'SD' in title_full: quality = 'SD'
                
                # --- Provider Display ---
                # Încercăm să scoatem numele real al sursei (ex: RD, PM, Seedr) dacă apare în nume
                p_display = raw_name.replace("WebStreamr", "").strip()
                if not p_display: p_display = "WEBSTREAMR"

                # --- Mărime ---
                size_str = ""
                size_bytes = stream.get('behaviorHints', {}).get('fileSize')
                if size_bytes:
                    size_str = self._format_size(size_bytes)
                else:
                    size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB))', title_full)
                    if size_match: size_str = size_match.group(1)

                # --- Construire Label ---
                info_label = f"[{quality}] [{p_display}]"
                if size_str: info_label += f" | {size_str}"
                
                # Verificăm dacă e HLS
                is_hls = ".m3u8" in video_url or "master" in video_url
                
                sources_list.append({
                    "release_title": f"{release_name} {info_label}",
                    "quality": quality,
                    "url": f"{video_url}|User-Agent={self.user_agent}",
                    "debrid_provider": p_display,
                    "filetype": "hls" if is_hls else "direct",
                    "info": info_label,
                    "subs": []
                })

        except Exception as e:
            self.log(f"Eroare la procesare: {str(e)}", "error")

        return sources_list

    def episode(self, simple_info, info):
        self.start_time = time.time()
        imdb_id = info["info"].get("tvshow.imdb_id") or info["info"].get("imdb_id")
        if not imdb_id: return []
        url = f"{self.base_url}/stream/series/{imdb_id}:{simple_info['season_number']}:{simple_info['episode_number']}.json"
        return self._return_results("episode", self._process_item(url, simple_info))

    def movie(self, title, year, imdb, simple_info, info):
        self.start_time = time.time()
        if not imdb: return []
        url = f"{self.base_url}/stream/movie/{imdb}.json"
        return self._return_results("movie", self._process_item(url, simple_info))

    def _return_results(self, source_type, sources, preemptive=False):
        self.log(f"Am găsit {len(sources)} surse pentru {source_type}")
        return sources

    @staticmethod
    def get_listitem(return_data):
        url = return_data["url"]
        list_item = xbmcgui.ListItem(path=url, offscreen=True)
        list_item.setProperty("isPlayable", "true")
        if return_data.get('filetype') == 'hls':
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        return list_item
