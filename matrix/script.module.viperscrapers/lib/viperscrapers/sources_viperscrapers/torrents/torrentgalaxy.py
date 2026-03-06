# -*- coding: utf-8 -*-
# Updated 2025-10-07 for new TorrentGalaxy JSON endpoint with mirror fallbacks
"""
   fenomscrapers Project
"""

import re
import json
from urllib.parse import quote_plus
from time import time
from viperscrapers.modules import cfscrape, source_utils, workers, log_utils


class source:
    priority = 2
    pack_capable = True
    hasMovies = True
    hasEpisodes = True

    def __init__(self):
        self.language = ["en"]
        # Main + fallback mirrors
        self.base_links = [
            "https://torrentgalaxy.one",
            "https://torrentgalaxy.space",
            "https://torrentgalaxy.info",
        ]
        self.search_link = "/get-posts/keywords:%s:format:json/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0"
        }
        self.item_totals = {"4K": 0, "1080p": 0, "720p": 0, "SD": 0, "CAM": 0}
        self.min_seeders = 0
        self.base_link = self.base_links[0]  # default

    def _size_from_bytes(self, size_bytes):
        try:
            sb = int(size_bytes)
        except:
            return 0, ""
        if sb <= 0:
            return 0, ""
        if sb >= 1024 ** 3:
            size_str = f"{sb / (1024.0 ** 3):.2f} GB"
        else:
            size_str = f"{sb / (1024.0 ** 2):.2f} MB"
        return source_utils._size(size_str)

    def sources(self, data, hostDict):
        sources = []
        if not data:
            return sources
        sources_append = sources.append

        try:
            startTime = time()
            scraper = cfscrape.create_scraper()
            aliases = data.get("aliases", [])
            year = data.get("year")
            imdb = data.get("imdb")
            episode_title = data.get("title")

            if "tvshowtitle" in data:
                title = (
                    data["tvshowtitle"]
                    .replace("&", "and")
                    .replace("/", " ")
                    .replace("$", "s")
                )
                hdlr = "S%02dE%02d" % (int(data["season"]), int(data["episode"]))
                clean_title = re.sub(r"[^A-Za-z0-9\s\.-]+", "", title)
                query = f"{clean_title} {hdlr}"
                search_term = quote_plus(query)
                years = None
            else:
                title = (
                    data["title"].replace("&", "and").replace("/", " ").replace("$", "s")
                )
                hdlr = year
                years = [str(int(year) - 1), str(year), str(int(year) + 1)]
                search_term = imdb if imdb else quote_plus(title)

            posts = []
            for base in self.base_links:
                try:
                    url = f"{base.rstrip('/')}{self.search_link % search_term}"
                    result = scraper.get(url, headers=self.headers, timeout=10).text
                    data_json = json.loads(result)
                    posts = data_json.get("results", []) or data_json.get("data", [])
                    self.base_link = base  # keep the working mirror
                    break  # success
                except Exception as e:
                    log_utils.log(f"TGX mirror failed ({base}): {e}")
                    continue

            if not posts:
                log_utils.log("TGX: No JSON posts found.")
                return sources

            undesirables = source_utils.get_undesirables()
            check_foreign_audio = source_utils.check_foreign_audio()

        except Exception as e:
            log_utils.log(f"TGX main fetch failed: {e}")
            source_utils.scraper_error("TORRENTGALAXY")
            return sources

        for post in posts:
            try:
                name = post.get("n") or ""
                hash_str = post.get("h") or ""
                seeders = int(post.get("se", 0))
                size_bytes = int(post.get("s", 0))

                if not name or not hash_str:
                    continue
                if seeders < self.min_seeders:
                    continue

                magnet = f"magnet:?xt=urn:btih:{hash_str}"
                dsize, isize = self._size_from_bytes(size_bytes)

                if not source_utils.check_title(title, aliases, name, hdlr, year, years):
                    continue

                name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
                if source_utils.remove_lang(name_info, check_foreign_audio):
                    continue
                if undesirables and source_utils.remove_undesirables(name_info, undesirables):
                    continue

                quality, info = source_utils.get_release_quality(name_info, magnet)
                if isize:
                    info.insert(0, isize)
                info = " | ".join(info)

                sources_append(
                    {
                        "provider": "torrentgalaxy",
                        "source": "torrent",
                        "seeders": seeders,
                        "hash": hash_str,
                        "name": name,
                        "name_info": name_info,
                        "quality": quality,
                        "language": "en",
                        "url": magnet,
                        "info": info,
                        "direct": False,
                        "debridonly": True,
                        "size": dsize,
                    }
                )
                self.item_totals[quality] += 1

            except Exception as e:
                log_utils.log(f"TGX parse error: {e}")
                source_utils.scraper_error("TORRENTGALAXY")

        logged = False
        for quality in self.item_totals:
            if self.item_totals[quality] > 0:
                logged = True
                log_utils.log(
                    f"#STATS - TORRENTGALAXY found {self.item_totals[quality]} {quality}"
                )
        if not logged:
            log_utils.log("#STATS - TORRENTGALAXY found nothing")

        endTime = time()
        log_utils.log(f"#STATS - TORRENTGALAXY took {(endTime - startTime):.2f}s")
        return sources

    def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
        self.sources = []
        if not data:
            return self.sources
        self.sources_append = self.sources.append
        try:
            startTime = time()
            scraper = cfscrape.create_scraper()
            self.search_series = search_series
            self.total_seasons = total_seasons
            self.bypass_filter = bypass_filter

            self.title = (
                data["tvshowtitle"]
                .replace("&", "and")
                .replace("/", " ")
                .replace("$", "s")
            )
            self.aliases = data["aliases"]
            self.imdb = data["imdb"]
            self.year = data["year"]
            self.season_x = str(data["season"])
            self.season_xx = self.season_x.zfill(2)
            self.undesirables = source_utils.get_undesirables()
            self.check_foreign_audio = source_utils.check_foreign_audio()

            query = re.sub(r"[^A-Za-z0-9\s\.-]+", "", self.title)
            if search_series:
                queries = [
                    self.search_link % quote_plus(query + " Season"),
                    self.search_link % quote_plus(query + " Complete"),
                ]
            else:
                queries = [
                    self.search_link % quote_plus(query + f" S{self.season_xx}"),
                    self.search_link % quote_plus(query + f" Season {self.season_x}"),
                ]

            threads = []
            for url in queries:
                link = self.base_link.rstrip("/") + url
                threads.append(workers.Thread(self.get_sources_packs, link))
            [i.start() for i in threads]
            [i.join() for i in threads]

            logged = False
            for quality in self.item_totals:
                if self.item_totals[quality] > 0:
                    logged = True
                    log_utils.log(
                        f"#STATS - TORRENTGALAXY(pack) found {self.item_totals[quality]} {quality}"
                    )
            if not logged:
                log_utils.log("#STATS - TORRENTGALAXY(pack) found nothing")

            endTime = time()
            log_utils.log(
                f"#STATS - TORRENTGALAXY(pack) took {(endTime - startTime):.2f}s"
            )
            return self.sources

        except Exception as e:
            log_utils.log(f"TGX pack fetch failed: {e}")
            source_utils.scraper_error("TORRENTGALAXY")
            return self.sources

    def get_sources_packs(self, link):
        try:
            scraper = cfscrape.create_scraper()
            result = scraper.get(link, headers=self.headers, timeout=10).text
            if not result:
                return
            data_json = json.loads(result)
            posts = data_json.get("results", []) or data_json.get("data", [])
            if not posts:
                return
        except Exception as e:
            log_utils.log(f"TGX pack list fetch failed: {e}")
            source_utils.scraper_error("TORRENTGALAXY")
            return

        for post in posts:
            try:
                name = post.get("n") or ""
                hash_str = post.get("h") or ""
                seeders = int(post.get("se", 0))
                size_bytes = int(post.get("s", 0))
                if not name or not hash_str:
                    continue
                if seeders < self.min_seeders:
                    continue

                magnet = f"magnet:?xt=urn:btih:{hash_str}"
                dsize, isize = self._size_from_bytes(size_bytes)

                if not self.bypass_filter:
                    if self.search_series:
                        valid, last_season = source_utils.filter_show_pack(
                            self.title, self.aliases, self.imdb, self.year, self.season_x, name, self.total_seasons
                        )
                        if not valid:
                            continue
                        package = "show"
                    else:
                        valid, episode_start, episode_end = source_utils.filter_season_pack(
                            self.title, self.aliases, self.year, self.season_x, name
                        )
                        if not valid:
                            continue
                        package = "season"
                else:
                    package = "show" if self.search_series else "season"

                name_info = source_utils.info_from_name(name, self.title, self.year, season=self.season_x, pack=package)
                if source_utils.remove_lang(name_info, self.check_foreign_audio):
                    continue
                if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables):
                    continue

                quality, info = source_utils.get_release_quality(name_info, magnet)
                if isize:
                    info.insert(0, isize)
                info = " | ".join(info)

                item = {
                    "provider": "torrentgalaxy",
                    "source": "torrent",
                    "seeders": seeders,
                    "hash": hash_str,
                    "name": name,
                    "name_info": name_info,
                    "quality": quality,
                    "language": "en",
                    "url": magnet,
                    "info": info,
                    "direct": False,
                    "debridonly": True,
                    "size": dsize,
                    "package": package,
                }
                self.sources_append(item)
                self.item_totals[quality] += 1

            except Exception as e:
                log_utils.log(f"TGX pack parse error: {e}")
                source_utils.scraper_error("TORRENTGALAXY")
