# -*- coding: utf-8 -*-
from providerModules.ScrapersCinema import common
import requests
import time
import xbmcgui
import re
import json
from urllib.parse import quote
from resources.lib.modules.exceptions import PreemptiveCancellation

class sources():
    def __init__(self):
        self.provider = "sooti"
        # Configurația StremThru
        self.stremthru_config = '{"DebridServices":[{"provider":"httpstreaming","http4khdhub":true,"httpHDHub4u":true,"httpUHDMovies":true,"httpMoviesDrive":true,"httpMKVCinemas":true}],"Languages":[],"Scrapers":[],"IndexerScrapers":["stremthru"],"minSize":0,"maxSize":200,"ShowCatalog":true,"DebridProvider":"httpstreaming"}'
        
        # Baza URL folosind configurația encodată
        self.base_url = f"https://sooti.info/{quote(self.stremthru_config)}"
        
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
            release_name = f'{simple_info["show_title"]} ({simple_info["year"]}): {simple_info.get("season_number").zfill(2)}x{simple_info.get("episode_number").zfill(2)}'
        
        sources_list = []
        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(item_url, headers=headers, timeout=15)
            data = response.json()

            for stream in data.get('streams', []):
                video_url = stream.get('url')
                if not video_url: continue

                # ELIMINARE LINII NOI: Înlocuim \n și \r cu spațiu pentru a păstra totul pe o singură linie
                raw_title = stream.get('title', '').replace('\n', ' ').replace('\r', ' ').strip()
                raw_name = stream.get('name', '').replace('\n', ' ').replace('\r', ' ').strip()
                
                title_data = (raw_title + " " + raw_name).upper()
                
                # --- Extragere Provider ---
                provider_display = ""
                if "🔗" in raw_title:
                    after_link = raw_title.split("🔗")[-1].split("  ")[0].strip()
                    if " FROM " in after_link.upper():
                        provider_display = after_link.upper().split(" FROM ")[-1].strip()
                    else:
                        provider_display = after_link
                
                if not provider_display:
                    provider_display = raw_name if raw_name else "STREMTHRU"

                # --- Detecție Detalii Avansate ---
                quality = stream.get('quality', '1080p')
                if '2160' in title_data or '4K' in title_data: quality = '4K'
                
                codec = ""
                if any(x in title_data for x in ['HEVC', 'H265', 'X265']): codec = "HEVC"
                elif any(x in title_data for x in ['H264', 'AVC', 'X264']): codec = "AVC"

                audio = ""
                if 'ATMOS' in title_data: audio = "ATMOS"
                elif '7.1' in title_data: audio = "7.1"
                elif '5.1' in title_data or 'DDP5' in title_data: audio = "5.1"

                hdr = ""
                if 'DOLBY VISION' in title_data or ' DV ' in title_data: hdr = "DV"
                elif 'HDR' in title_data: hdr = "HDR"

                size_str = ""
                size_bytes = stream.get('behaviorHints', {}).get('fileSize')
                if size_bytes:
                    size_str = self._format_size(size_bytes)
                else:
                    size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB))', title_data)
                    if size_match: size_str = size_match.group(1)

                # --- Construire Label ---
                info_label = f"[{quality}] [{provider_display}]"
                if hdr: info_label += f" | {hdr}"
                if codec: info_label += f" | {codec}"
                if audio: info_label += f" | {audio}"
                if size_str: info_label += f" | {size_str}"

                # Curățare finală release_title (fără dublu spațiu sau linii noi)
                final_title = f"{release_name} {info_label}".replace('  ', ' ').strip()

                kodi_url = f"{video_url}|Referer=sooti.info{self.user_agent}"
                is_hls = video_url.endswith('.m3u8') or '/m3u8' in video_url
                
                sources_list.append({
                    "release_title": final_title,
                    "quality": quality,
                    "url": kodi_url,
                    "debrid_provider": provider_display,
                    "filetype": "hls" if is_hls else "direct",
                    "info": info_label,
                    "subs": []
                })

        except Exception as e:
            self.log(f"Error in _process_item: {e}", "error")

        return sources_list

    def episode(self, simple_info, info):
        self.start_time = time.time()
        imdb_id = info["info"].get("tvshow.imdb_id") or info["info"].get("imdb_id")
        item = f"{self.base_url}/stream/series/{imdb_id}:{simple_info['season_number']}:{simple_info['episode_number']}.json"
        try:
            return self._return_results("episode", self._process_item(item, simple_info))
        except: return []

    def movie(self, title, year, imdb, simple_info, info):
        self.start_time = time.time()
        item = f"{self.base_url}/stream/movie/{imdb}.json"
        try:
            return self._return_results("movie", self._process_item(item, simple_info))
        except: return []

    def _return_results(self, source_type, sources, preemptive=False):
        self.log(f"StremThru Scraper: {len(sources)} sources found", "info")
        return sources

    @staticmethod
    def get_listitem(return_data):
        url = return_data["url"]
        list_item = xbmcgui.ListItem(path=url, offscreen=True)
        list_item.setInfo('video', {})
        list_item.setProperty("isPlayable", "true")
        if return_data.get('filetype') == 'hls':
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
            if '|' in url:
                headers = url.split('|')[1]
                list_item.setProperty('inputstream.adaptive.stream_headers', headers)
        return list_item
