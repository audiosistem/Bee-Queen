# -*- coding: utf-8 -*-
from providerModules.uvScrapers import common
import re
import requests
import time
import xbmcgui
from resources.lib.modules.exceptions import PreemptiveCancellation
import json


class sources():
    def __init__(self):
        self.provider = "vixsrc"
        self.base_url = "https://vixsrc.to"
        self.language = ["en"]
        self.start_time = 0
        self.subs = []

    def log(self, message, level='debug'):
        common.log(f'{self.provider.upper()} >>> {message}', level=level)

    def _return_results(self, source_type, sources, preemptive=False):
        if preemptive:
            self.log(f"uvScrapers.{source_type}: cancellation requested", "info",)
        elif preemptive is None:
            self.log(f"uvScrapers.{source_type}: not authorized", "info",)

        self.log(f"uvScrapers.{source_type}: {len(sources)}", "info")
        self.log(f"uvScrapers.{source_type}: took {int((time.time() - self.start_time) * 1000)} ms", "info",)
        return sources

    def _make_query(self, query, year, type):
        return []

    def _process_item(self, item, simple_info):
        if simple_info.get("title"):
            release_name = f'{simple_info["title"]} ({simple_info["year"]})'
        else:
            release_name = f'{simple_info["show_title"]} ({simple_info["year"]}): {simple_info.get("season_number").zfill(2)}x{simple_info.get("episode_number").zfill(2)} {simple_info.get("episode_title")}'
        self.log(f"Processing item: {release_name}")

        base_url = item
        self.log(f"Base URL: {base_url}")
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0"

        headers = {
            "Referer": self.base_url,
            "User-Agent": user_agent,
        }

        source = []
        response = requests.get(base_url, headers=headers).text
        if response:
            self.log("Fetched page content successfully.")
            match = re.search(r"window.masterPlaylist =\s+({.+?})\s", response, flags=re.DOTALL | re.IGNORECASE)
            if match:
                data = match.group(1)
                data = data.replace("params", "'params'").replace("url", "'url'")
                data = data.replace("\r", "").replace("\n", "").replace(" ", "")
                data = data.replace(",}", '}')
                data = data.replace("'", '"')
                self.log(data)
                try:
                    jdata = json.loads(data)
                except Exception as e:
                    self.log(f"JSON decoding error: {e}")
                    return []
                self.log("Extracted JSON data from page: " + str(jdata))

                url = jdata.get("url")
                token = jdata.get("params", {}).get("token")
                expires = jdata.get("params", {}).get("expires")

                video_url = f'{url}&token={token}&expires={expires}&h=1&lang=en' if '?' in url else f'{url}?token={token}&expires={expires}&h=1&lang=en'
                self.log("Constructed video URL: " + video_url)

                try:
                    source_ = {
                        "referer": self.base_url,
                        "release_title": release_name,
                        # "info": "",
                        # "size": 0,
                        "quality": "1080p",
                        "url": video_url,
                        "debrid_provider": self.provider,
                        # "headers": "",
                        "filetype": "hls",
                        "subs": self.subs,
                    }
                    source.append(source_)
                except Exception as error:
                    self.log(f"Error processing source: {error}")
        return source

    def episode(self, simple_info, info):
        self.start_time = time.time()
        id = info["info"].get("tvshow.tmdb_id")
        # id = info["info"].get("tvshow.imdb_id")
        season_number = simple_info.get("season_number", 1)
        episode_number = simple_info.get("episode_number", 1)
        item = f"https://vixsrc.to/tv/{id}/{season_number}/{episode_number}/"

        sources = []
        try:
            source = self._process_item(item, simple_info)
            for src in source:
                if src is not None:
                    sources.append(src)
            return self._return_results("episode", sources)
        except PreemptiveCancellation:
            return self._return_results("episode", sources, preemptive=True)

    def movie(self, title, year, imdb, simple_info, info):
        self.start_time = time.time()
        id = info.get("info").get("tmdb_id")
        item = f"https://vixsrc.to/movie/{id}/"

        sources = []
        try:
            source = self._process_item(item, simple_info)
            for src in source:
                if src is not None:
                    sources.append(src)
            return self._return_results("movie", sources)
        except PreemptiveCancellation:
            return self._return_results("movie", sources, preemptive=True)

    @staticmethod
    def get_listitem(return_data):
        list_item = xbmcgui.ListItem(path=return_data["url"], offscreen=True)
        list_item.setContentLookup(False)
        list_item.setProperty("isFolder", "false")
        list_item.setProperty("isPlayable", "true")

        referer = return_data.get('referer')
        if referer:
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            list_item.setProperty('inputstream.adaptive.stream_headers', f'Referer={referer}')

        subs = return_data.get('subs', [])
        list_item.setSubtitles(subs)
        return list_item
