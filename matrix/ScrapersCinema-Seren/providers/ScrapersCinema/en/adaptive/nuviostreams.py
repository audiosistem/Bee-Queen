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
        self.provider = "nuviostreams"
        self.base_url = "https://nuviostreams.hayd.uk"
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
            headers = {
                'User-Agent': self.user_agent,
                'Referer': self.base_url
            }
            # TIMEOUT MĂRIT LA 60 SECUNDE
            response = requests.get(item_url, headers=headers, timeout=60)
            if response.status_code != 200:
                self.log(f"Eroare HTTP: {response.status_code}")
                return []
            
            data = response.json()
            streams = data.get('streams', []) if isinstance(data, dict) else data

            if not streams:
                self.log("Nu s-au găsit surse în răspunsul JSON.")
                return []

            for stream in streams:
                video_url = stream.get('url')
                if not video_url: continue

                raw_title = stream.get('title', '').replace('\n', ' ').replace('\r', ' ').strip()
                raw_name = stream.get('name', '').replace('\n', ' ').replace('\r', ' ').strip()
                title_data = (raw_title + " " + raw_name).upper()
                
                provider_display = raw_name.replace("NuvioStreams", "").strip()
                if not provider_display or any(x == provider_display.lower() for x in ["1080p", "720p", "4k", "sd"]):
                    provider_display = "NUVIO"

                quality = "1080p"
                if any(x in title_data for x in ['2160', '4K', 'UHD']): quality = '4K'
                elif '720' in title_data: quality = '720p'
                elif '480' in title_data or 'SD' in title_data: quality = 'SD'
                
                codec = ""
                if any(x in title_data for x in ['HEVC', 'H265', 'X265']): codec = "HEVC"
                elif any(x in title_data for x in ['H264', 'AVC', 'X264']): codec = "AVC"

                size_str = ""
                size_bytes = stream.get('behaviorHints', {}).get('fileSize')
                if size_bytes:
                    size_str = self._format_size(size_bytes)
                else:
                    size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB))', title_data)
                    if size_match: size_str = size_match.group(1)

                info_parts = [f"[{quality}]", f"[{provider_display}]"]
                if codec: info_parts.append(codec)
                if size_str: info_parts.append(size_str)
                
                info_label = " | ".join(info_parts)
                final_title = f"{release_name} {info_label}".replace('  ', ' ').strip()

                is_hls = ".m3u8" in video_url or "/m3u8" in video_url
                
                sources_list.append({
                    "release_title": final_title,
                    "quality": quality,
                    "url": f"{video_url}|User-Agent={self.user_agent}&Referer={self.base_url}",
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
        if not imdb_id: return []
        
        season = simple_info['season_number']
        episode = simple_info['episode_number']
        api_url = f"{self.base_url}/stream/series/{imdb_id}:{season}:{episode}.json"
        
        return self._return_results("episode", self._process_item(api_url, simple_info))

    def movie(self, title, year, imdb, simple_info, info):
        self.start_time = time.time()
        if not imdb: return []
        api_url = f"{self.base_url}/stream/movie/{imdb}.json"
        
        return self._return_results("movie", self._process_item(api_url, simple_info))

    def _return_results(self, source_type, sources, preemptive=False):
        self.log(f"NuvioStreams Total: {len(sources)} surse găsite în 2026", "info")
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
