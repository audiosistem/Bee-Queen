# -*- coding: utf-8 -*-
from providerModules.ScrapersCinema import common
from providerModules.ScrapersCinema.core.uvs import ScrapersCinema
import requests
import time
import xbmcgui
import re
import json
from resources.lib.modules.exceptions import PreemptiveCancellation

class sources():
    def __init__(self):
        self.provider = "rogflix"
        # Adresa nouă actualizată
        self.base_url = "https://rogflix.vflix.life"
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

    def _return_results(self, source_type, sources, preemptive=False):
        if preemptive:
            self.log(f"ScrapersCinema.{source_type}: cancellation requested", "info")
        self.log(f"ScrapersCinema.{source_type}: found {len(sources)} sources")
        self.log(f"ScrapersCinema.{source_type}: took {int((time.time() - self.start_time) * 1000)} ms", "info")
        return sources

    def _process_item(self, item_url, simple_info):
        if simple_info.get("title"):
            release_name = f'{simple_info["title"]} ({simple_info["year"]})'
        else:
            release_name = f'{simple_info["show_title"]} ({simple_info["year"]}): {str(simple_info.get("season_number")).zfill(2)}x{str(simple_info.get("episode_number")).zfill(2)}'
        
        sources_list = []
        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(item_url, headers=headers, timeout=15)
            if response.status_code != 200: return []

            data = response.json()
            streams = data.get('streams', []) if isinstance(data, dict) else data

            for stream in streams:
                video_url = stream.get('url')
                if not video_url: continue

                raw_title = stream.get('title', '').replace('\n', ' ').replace('\r', ' ').strip()
                raw_name = stream.get('name', '').replace('\n', ' ').replace('\r', ' ').strip()
                title_full = (raw_title + " " + raw_name).upper()
                
                # --- Calitate ---
                quality = "1080p"
                if any(x in title_full for x in ['2160', '4K', 'UHD']): quality = '4K'
                elif '720' in title_full: quality = '720p'
                elif '480' in title_full or 'SD' in title_full: quality = 'SD'
                
                # --- Provider Display ---
                # Extragem RD, PM, Seedr sau alte tag-uri din nume
                p_display = raw_name.replace("Rogflix", "").replace("WebStreamr", "").strip()
                if not p_display: p_display = "ROGFLIX"

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
            self.log(f"Error: {str(e)}", "error")

        return sources_list

    def episode(self, simple_info, info):
        self.start_time = time.time()
        imdb_id = info["info"].get("tvshow.imdb_id") or info["info"].get("imdb_id")
        if not imdb_id: return []
        # URL pentru Rogflix Series
        url = f"{self.base_url}/stremio/stream/series/{imdb_id}:{simple_info['season_number']}:{simple_info['episode_number']}.json"
        try:
            return self._return_results("episode", self._process_item(url, simple_info))
        except PreemptiveCancellation:
            return self._return_results("episode", [], preemptive=True)

    def movie(self, title, year, imdb, simple_info, info):
        self.start_time = time.time()
        if not imdb: return []
        # URL pentru Rogflix Movie conform cerintei
        url = f"{self.base_url}/stremio/stream/movie/{imdb}.json"
        try:
            return self._return_results("movie", self._process_item(url, simple_info))
        except PreemptiveCancellation:
            return self._return_results("movie", [], preemptive=True)

    @staticmethod
    def get_listitem(return_data):
        list_item = xbmcgui.ListItem(path=return_data["url"], offscreen=True)
        list_item.setContentLookup(False)
        list_item.setProperty("isPlayable", "true")
        if return_data.get('filetype') == 'hls':
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        return list_item
