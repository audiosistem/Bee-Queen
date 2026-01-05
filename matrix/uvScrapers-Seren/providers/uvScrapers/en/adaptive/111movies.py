# -*- coding: utf-8 -*-
from providerModules.uvScrapers import common
import re
import requests
import time
import xbmcgui
from resources.lib.modules.exceptions import PreemptiveCancellation
from urllib.parse import urlparse
import base64
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad


class sources():
    def __init__(self):
        self.provider = "111movies"
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
        user_agent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
        default_domain = '{uri.scheme}://{uri.netloc}/'.format(uri=urlparse(base_url))
        headers = {
            "Referer": default_domain,
            "User-Agent": user_agent,
            "Content-Type": "application/octet-stream",
            "X-Requested-With": "XMLHttpRequest"
        }

        # Utility Functions
        ''' Encodes input using Base64 with custom character mapping. '''
        def custom_encode(input):
            src = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            dst = "TuzHOxl7b0RW9o_1FPV3eGfmL4Z5pD8cahBQr2U-6yvEYwngXCdJjANtqKIMiSks"
            trans = str.maketrans(src, dst)
            b64 = base64.b64encode(input.encode()).decode().replace('+', '-').replace('/', '_').replace('=', '')
            return b64.translate(trans)

        # Fetch page content
        response = requests.get(base_url, headers=headers).text

        # Extract raw data
        match = re.search(r'{\"data\":\"(.*?)\"', response)
        if not match:
            exit(self.log("No data found!"))
        raw_data = match.group(1)
        self.log("Extracted raw data: " + raw_data)

        # AES encryption setup
        key_hex = "034bcfc6275541ff4059bffb23d6d1d23ea49b55f79ea730ac540d1213a61339"
        iv_hex = "a2e7ad865464f12105e9df84f5bdabed"
        aes_key = bytes.fromhex(key_hex)
        aes_iv = bytes.fromhex(iv_hex)

        cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
        padded_data = pad(raw_data.encode(), AES.block_size)
        aes_encrypted = cipher.encrypt(padded_data).hex()

        # XOR operation
        xor_key = bytes.fromhex("aaa27e7e3cff888285")
        xor_result = ''.join(chr(ord(char) ^ xor_key[i % len(xor_key)]) for i, char in enumerate(aes_encrypted))

        # Custom encoded string
        encoded_final = custom_encode(xor_result)
        self.log("Encoded final string: " + encoded_final)

        # Make final request
        static_path = "fcd552c4321aeac1e62c5304913b3420be75a19d390807281a425aabbb5dc4c0"
        api_servers = f"https://111movies.com/{static_path}/{encoded_final}/sr"
        self.log("API Servers URL: " + api_servers)
        try:
            response = requests.get(api_servers, headers=headers)
            response = response.json()
        except Exception as e:
            self.log(f"Error fetching API servers: {e}")
            return []
        self.log(response)
        # server = random.choice(response)['data']
        provider = ''
        for rsp in response:
            server = rsp['data']
            provider = rsp["name"] + ' - ' + rsp["description"]
            api_stream = f"https://111movies.com/{static_path}/{server}"
            self.log(api_stream)
            self.log(f"Trying server: {provider}")
            try:
                response = requests.get(api_stream, headers=headers).json()
                self.log(f"Server {rsp['name']} - Success")
                self.log(response)
                break
            except Exception as e:
                self.log(f"Error fetching API stream: {e} - {provider}")

        # try:
        #     dialog = xbmcgui.Dialog()
        #     idx = dialog.select("111MOVIES: Select a server", [s['name'] for s in response])
        #     common.log('Server selected: ' + str(idx))
        # except Exception as e:
        #     self.log(f"Error selecting server: {e}", "error")
        #     return []

        subs = []
        if "tracks" in response:
            self.subs = common.get_subs(response["tracks"], self.subs)
            subs = common.fix_subtitles(self.subs)

        # Extract video URL
        video_url = response['url']

        source = []
        try:
            source_ = {
                "referer": "https://111movies.com/",
                "release_title": release_name,
                # "info": "",
                # "size": 0,
                "quality": "1080p",
                "url": video_url,
                "debrid_provider": provider,
                # "headers": "",
                "filetype": "hls",
                "subs": subs,
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
        item = f"https://111movies.com/tv/{id}/{season_number}/{episode_number}"

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
        item = f"https://111movies.com/movie/{id}"

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
