from providerModules.ScrapersCinema import common
import re
import requests
import time
import xbmcgui
from resources.lib.modules.exceptions import PreemptiveCancellation
from urllib.parse import urlparse, quote_plus


class ScrapersCinema:
    def __init__(self):
        common.log("Initializing sources")
        self.user_agent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
        self.decode_url = "https://script.google.com/macros/s/AKfycbxHbYHbrGMXYD2-bC-C43D3njIbU-wGiYQuJL61H4vyy6YVXkybMNNEPJNPPuZrD1gRVA/exec"
        self.key_url = "https://raw.githubusercontent.com/yogesh-hacker/MegacloudKeys/refs/heads/main/keys.json"

        self.provider = ""
        self.language = ["en"]
        self.base_link = ""
        self.search_link = "ajax/search"
        self.query_link = f"{self.base_link}{self.search_link}"
        self.start_time = 0
        self.subs = []
        self.client_key = ""

    def log(self, message, level='debug'):
        common.log(f'{self.provider.upper()} >>> {message}', level=level)

    def _return_results(self, source_type, sources, preemptive=False):
        if preemptive:
            self.log(f"ScrapersCinema.{source_type}: cancellation requested", "info",)
        elif preemptive is None:
            self.log(f"ScrapersCinema.{source_type}: not authorized", "info",)

        self.log(f"ScrapersCinema.{source_type}: {len(sources)}", "info")
        self.log(f"ScrapersCinema.{source_type}: took {int((time.time() - self.start_time) * 1000)} ms", "info",)
        return sources

    def _make_query(self, query, year, type):
        self.log('Query: ' + query + ' year: ' + str(year) + ' type: ' + type)
        data = f"keyword={quote_plus(query)}"
        user_agent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
        headers = {
            "Referer": self.base_link,
            "User-Agent": user_agent,
            "Origin": self.base_link,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }

        search_results = requests.post(self.query_link, headers=headers, data=data).text
        results = re.split(r'</div>\s*</a>', search_results)

        exact_matches = []
        matches = []
        for result in results:
            match = re.search(r'<a\s+href="/([^"]+)"', result, flags=re.DOTALL | re.IGNORECASE)
            if match:
                video_url = self.base_link + match.group(1)
            else:
                continue

            match = re.search(r'<span>(TV|Movie)</span>', result, flags=re.DOTALL | re.IGNORECASE)
            qtype = match.group(1) if match else ''
            self.log('qtype: ' + qtype + ' type: ' + type)

            if qtype.lower() != type.lower():
                continue

            qyear = ''
            if type == 'Movie':
                match = re.search(r'<div class="film-infor">\s*<span>(\d+)</span>', result, flags=re.DOTALL | re.IGNORECASE)
                if match:
                    qyear = match.group(1)
                    if year != qyear:
                        continue

            match = re.search('title="([^"]+)"', result, flags=re.DOTALL | re.IGNORECASE)
            title = match.group(1) if match else ''

            if query.lower() == title.lower():
                exact_matches.append({'title': title, 'video_url': video_url, 'year': qyear if type == 'Movie' else year})
            else:
                matches.append({'title': title, 'video_url': video_url, 'year': qyear if type == 'Movie' else year})

        self.log(matches)
        self.log(exact_matches)

        results = []
        if len(exact_matches) == 1:
            results.append(exact_matches[0])
        elif len(exact_matches) > 1:
            for video in exact_matches:
                video_page = requests.get(video['video_url']).text
                match = re.search(r'Released:\D+(\d{4})\D', video_page)
                if match:
                    released = match.group(1)
                    if released != year:
                        continue
                results.append(video)

        if len(results) == 0:
            results = matches

        self.log(f"ScrapersCinema: MAKE QUERY END {int((time.time() - self.start_time) * 1000)} ms", "info",)
        return results

    def _process_item(self, item, simple_info):
        self.log('Processing item: ' + str(item))
        season = simple_info.get('season_number')
        episode = simple_info.get('episode_number')
        self.log('season: ' + str(season) + ' episode: ' + str(episode))
        url = item['video_url']
        id = url.split('-')[-1]
        self.log('video id: ' + id)

        if season:
            seasonsurl = self.base_link + 'ajax/season/list/' + id
            self.log('seasonsurl: ' + seasonsurl)
            seasonshtml = requests.get(seasonsurl).text
            match = re.compile(rf'href="#ss-episodes-(\d+)">Season\s*{season}', re.DOTALL | re.IGNORECASE).findall(seasonshtml)
            if not match:
                return
            seasonid = match[0]
            self.log('seasonid: ' + seasonid)
            season = f'S{season}'

            episodeurl = self.base_link + 'ajax/season/episodes/' + seasonid
            episodeurl = self.base_link + 'ajax/season/episodes/' + seasonid
            self.log('episodeurl: ' + episodeurl)
            episodehtml = requests.get(episodeurl).text
            match = re.compile(rf'data-id="(\d+)"[^_]+?alt="Episode\s*0*{episode}"', re.DOTALL | re.IGNORECASE).findall(episodehtml) or re.compile(rf'data-id="(\d+)"[^>]+?title="Eps\s*0*{episode}', re.DOTALL | re.IGNORECASE).findall(episodehtml)

            if not match:
                return
            id = match[0]
            self.log('server id: ' + str(match[0]))

        serverurl = self.base_link + 'ajax/episode/list/' + id if '/movie/' in url else self.base_link + 'ajax/episode/servers/' + id
        self.log('serverurl: ' + serverurl)
        serverhtml = requests.get(serverurl).text

        match = re.compile(r'(?:data-linkid|data-id)="(\d+)".+?<span>([^<]+)<', re.DOTALL | re.IGNORECASE).findall(serverhtml)
        self.log('match: ' + str(match))
        if not match:
            return

        source = []
        self.subs = []

        response = requests.get(self.key_url).json()
        if not response:
            self.log("Failed to retrieve keys from the key URL", "error")
            return []
        key = response['vidstr']

        for serverid, servername in match:
            self.log('\n\nservername: ' + servername + ' serverid: ' + serverid + '\n')
            if servername not in ('UpCloud', 'MegaCloud', 'Vidcloud', 'AKCloud'):
                self.log(f"Skipping server: {servername}", "info")
                continue

            provider_url = self.base_link + 'ajax/episode/sources/' + serverid
            self.log('provider_url: ' + provider_url)

            base_url = requests.get(provider_url).json()['link']
            self.log('base_url: ' + base_url)

            parsed_url = urlparse(base_url)
            default_domain = f"{parsed_url.scheme}://{parsed_url.netloc}/"
            headers = {
                "Accept": "*/*",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": default_domain,
                "User-Agent": self.user_agent
            }
            response = requests.get(base_url, headers=headers).text

            match = re.search(r'player" data-id="(\w+)"', response)
            if match:
                file_id = match.group(1)
            else:
                self.log(f"Skipping server {servername} due to missing file_id", "info")
                self.log('Response: ' + response)
                continue

            match = re.search(r'\b[a-zA-Z0-9]{48}\b', response) or re.search(r'\b([a-zA-Z0-9]{16})\b.*?\b([a-zA-Z0-9]{16})\b.*?\b([a-zA-Z0-9]{16})\b', response)
            if not match:
                self.log(f"Skipping server {servername} due to missing nonce", "info")
                continue
            nonce = ''.join(match.groups()) if match and match.lastindex == 3 else match.group() if match else None
            if not nonce:
                self.log(f"Skipping server {servername} due to missing nonce", "info")
                continue
            embed_link = f'{default_domain}embed-1/v3/e-1/getSources?id={file_id}&_k={nonce}'
            self.log('embed_link: ' + embed_link)

            embed_response = requests.get(embed_link, headers=headers).json()
            encrypted = embed_response.get('encrypted')
            self.log('encrypted: ' + str(encrypted))

            # Extract video URL
            if encrypted:
                # Get required values to decode
                encrypted_data = quote_plus(embed_response['sources'])
                nonce_encoded = quote_plus(nonce)
                key_encoded = quote_plus(key)

                # Decoding is handled on the server side to avoid PRNG-related issues in Python
                # Original server-side implementation reference: https://github.com/yogesh-hacker/yogesh-hacker/blob/main/js/videostr.js
                decode_url = f"{self.decode_url}?encrypted_data={encrypted_data}&nonce={nonce_encoded}&secret={key_encoded}"
                self.log('decode_url: ' + decode_url)
                response = requests.get(decode_url, allow_redirects=True).text
                match = re.search(r'\"file\":\"(.*?)\"', response)
                video_url = match.group(1) if match else None
            else:
                video_url = embed_response['sources'][0]['file']

            if video_url:
                try:
                    if simple_info.get("title"):
                        release_name = f'{item["title"]} ({item.get("year", "")})'
                    else:
                        release_name = f'{item["title"]} ({item.get("year", "")}): {simple_info.get("season_number").zfill(2)}x{simple_info.get("episode_number").zfill(2)} {simple_info.get("episode_title", "")}'
                    self.log('release_name: ' + release_name)

                    subs = []
                    if "tracks" in embed_response:
                        self.subs = common.get_subs(embed_response["tracks"], self.subs)
                        subs = common.fix_subtitles(self.subs)

                    referer = default_domain
                    debrid_provider = f'{servername} - {parsed_url.netloc}'
                    self.log('debrid_provider: ' + debrid_provider)

                    if servername == 'UpCloud':
                        video_url = video_url + '|referer=' + referer
                        referer = None
                    self.log('video_url:' + video_url)

                    source_ = {
                        "referer": referer,
                        "scraper": self.provider,
                        "release_title": release_name,
                        # "info": "",
                        # "size": 0,
                        "quality": "1080p",
                        "url": video_url,
                        "debrid_provider": debrid_provider,
                        # "headers": "",
                        "filetype": "hls",
                        "subs": subs,
                    }
                    self.log('*** source_: ' + str(source_))
                    source.append(source_)
                except Exception as error:
                    self.log(f"Error processing source: {error}")
                    continue
        return source

    def episode(self, simple_info, info):
        self.start_time = time.time()
        sources = []

        query = simple_info["show_title"]
        try:
            results = self._make_query(query, simple_info['year'], 'TV')
            self.log('Results: ' + str(results))
            for item in results:
                source = self._process_item(item, simple_info)
                for ss in source:
                    sources.append(ss)
            return self._return_results("episode", sources)
        except PreemptiveCancellation:
            return self._return_results("episode", sources, preemptive=True)

    def movie(self, title, year, imdb, simple_info, info):
        self.start_time = time.time()
        sources = []

        year = simple_info["year"]
        query = simple_info["title"]
        try:
            results = self._make_query(query, year, 'Movie')
            for item in results:
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
