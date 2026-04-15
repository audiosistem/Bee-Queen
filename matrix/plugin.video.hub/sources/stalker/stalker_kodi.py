import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StalkerPortal:
    _auth_cache: Dict[str, Dict[str, Any]] = {}
    _auth_cache_ttl = 3600

    def __init__(self, portal_url, mac, serial=None, num_threads=10, progress_callback=None):
        self.portal_url = portal_url.rstrip("/")
        self.mac = mac.strip()
        self.serial = serial
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.token = None
        self.bearer_token = None
        self.last_handshake = 0
        self.token_expiry = self._auth_cache_ttl
        self.num_threads = num_threads
        self.progress_callback = progress_callback
        self.progress_lock = Lock()
        self._load_cached_auth()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def report_progress(self, progress: int):
        if self.progress_callback:
            with self.progress_lock:
                progress = min(max(progress, 0), 100)
                self.progress_callback(progress)
                logger.debug("Reported progress: %s%%", progress)

    def _get_cache_key(self) -> str:
        return "%s|%s" % (self.portal_url, self.mac)

    def _load_cached_auth(self):
        cached = self._auth_cache.get(self._get_cache_key())
        if not cached:
            return

        cache_age = time.time() - cached.get("timestamp", 0)
        if cache_age >= self._auth_cache_ttl:
            self._auth_cache.pop(self._get_cache_key(), None)
            return

        token = cached.get("token")
        if token:
            self.token = token
            self.bearer_token = token
            self.last_handshake = cached.get("timestamp", 0)
            logger.debug("Using cached Stalker token for %s", self.portal_url)

    def _save_cached_auth(self):
        if not self.token:
            return
        self._auth_cache[self._get_cache_key()] = {
            "token": self.token,
            "timestamp": self.last_handshake,
        }

    def _clear_cached_auth(self):
        self._auth_cache.pop(self._get_cache_key(), None)
        self.token = None
        self.bearer_token = None
        self.last_handshake = 0

    def _get_portal_endpoint(self) -> str:
        return "%s/portal.php" % self.portal_url

    def _build_params(self, request_type: str, action: str, **extra) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "type": request_type,
            "action": action,
            "JsHttpRequest": "1-xml",
        }
        if self.token:
            params["token"] = self.token
        for key, value in extra.items():
            if value is not None and value != "":
                params[key] = value
        return params

    def _clean_json_text(self, raw_text: str) -> str:
        if not raw_text:
            return ""

        cleaned = raw_text.strip()
        if not cleaned:
            return ""

        if cleaned[0] in "{[" and cleaned[-1] in "}]":
            return cleaned

        start_candidates = [pos for pos in (cleaned.find("{"), cleaned.find("[")) if pos != -1]
        end_candidates = [pos for pos in (cleaned.rfind("}"), cleaned.rfind("]")) if pos != -1]
        if not start_candidates or not end_candidates:
            return cleaned

        start_pos = min(start_candidates)
        end_pos = max(end_candidates)
        if end_pos >= start_pos:
            return cleaned[start_pos : end_pos + 1]
        return cleaned

    def _extract_js_payload(self, data: Any) -> Any:
        if isinstance(data, dict):
            return data.get("js", {})
        if isinstance(data, list):
            return data
        return None

    def _extract_list_payload(self, data: Any) -> List[Dict[str, Any]]:
        js_data = self._extract_js_payload(data)
        if isinstance(js_data, list):
            return js_data
        if not isinstance(js_data, dict):
            return []

        for key in ("data", "genres", "categories"):
            payload = js_data.get(key)
            if isinstance(payload, list):
                return payload
            if isinstance(payload, dict):
                nested = payload.get("data")
                if isinstance(nested, list):
                    return nested
        return []

    def _extract_cmd(self, data: Any) -> Optional[str]:
        js_data = self._extract_js_payload(data)
        if isinstance(js_data, dict):
            cmd = js_data.get("cmd")
            if isinstance(cmd, str):
                return cmd.strip()
        return None

    def _extract_play_token(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        match = re.search(r"play_token=([A-Za-z0-9]+)", value)
        return match.group(1) if match else None

    def _normalize_stream_value(self, value: Optional[str]) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        cleaned = value.strip()
        if cleaned.lower().startswith("ffmpeg "):
            cleaned = cleaned.split(" ", 1)[1].strip()
        return cleaned or None

    def _resolve_stream_id(self, stream_id: Optional[str], *candidates: Any) -> Optional[str]:
        if stream_id not in (None, ""):
            return str(stream_id)

        for candidate in candidates:
            if not candidate:
                continue
            candidate_text = str(candidate)
            stream_match = re.search(r"stream=(\d+)", candidate_text)
            if stream_match:
                return stream_match.group(1)
            numeric_candidate = candidate_text.strip()
            if numeric_candidate.isdigit():
                return numeric_candidate
        return None

    def _extract_total_items(self, data: Any) -> int:
        js_data = self._extract_js_payload(data)
        if not isinstance(js_data, dict):
            return 0
        try:
            return int(js_data.get("total_items", 0))
        except (TypeError, ValueError):
            return 0

    def _dedupe_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: Dict[str, Dict[str, Any]] = {}
        ordered: List[Dict[str, Any]] = []

        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            item_name = item.get("name") or item.get("title") or ""
            item_key = str(item_id) if item_id not in (None, "") else "%s|%s" % (item_name, item.get("cmd", ""))
            if item_key in deduped:
                continue
            deduped[item_key] = item
            ordered.append(item)

        ordered.sort(key=lambda entry: (entry.get("name") or entry.get("title") or "").lower())
        return ordered

    def make_request_with_retries(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        retries=3,
        backoff_factor=0.5,
        timeout=10,
    ) -> Optional[requests.Response]:
        for attempt in range(1, retries + 1):
            try:
                logger.debug("Attempt %s: GET %s with params=%s", attempt, url, params)
                self.session.cookies.clear()
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    cookies=cookies,
                    timeout=timeout,
                )

                if response.status_code in (401, 403) and attempt < retries:
                    logger.warning("Auth rejected for %s, refreshing token.", url)
                    self._clear_cached_auth()
                    self.handshake()
                    headers = self.get_headers()
                    cookies = self.get_cookies()
                    continue

                response.raise_for_status()
                logger.debug("Received response: %s", response.status_code)
                return response
            except requests.exceptions.RequestException as exc:
                logger.warning("Attempt %s failed for URL %s: %s", attempt, url, exc)
                if attempt < retries:
                    time.sleep(backoff_factor * (2 ** (attempt - 1)))

        logger.error("All %s attempts failed for URL %s", retries, url)
        return None

    def safe_json_parse(self, response: Optional[requests.Response]) -> Optional[Any]:
        if not response:
            return None

        try:
            return response.json()
        except (json.JSONDecodeError, ValueError):
            cleaned_text = self._clean_json_text(response.text or "")
            if not cleaned_text:
                logger.error("Failed to decode JSON and response text was empty.")
                return None

            try:
                return json.loads(cleaned_text)
            except (json.JSONDecodeError, ValueError):
                logger.error("Failed to decode JSON.", exc_info=True)
                logger.debug("Response text: %s", response.text)
                return None

    def ensure_valid_token(self):
        self._load_cached_auth()
        current_time = time.time()
        if not self.token or (current_time - self.last_handshake) > (self.token_expiry - 300):
            logger.debug("Token expired or missing, performing handshake.")
            self.handshake()

    def get_headers(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
            "Referer": "%s/stalker_portal/c/index.html" % self.portal_url,
            "X-User-Agent": "Model: MAG250; Link: WiFi",
            "Host": urlparse(self.portal_url).netloc,
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip, deflate",
        }
        if self.bearer_token:
            headers["Authorization"] = "Bearer %s" % self.bearer_token
        return headers

    def get_cookies(self):
        cookies = {"mac": self.mac, "stb_lang": "en", "timezone": "Europe/Paris"}
        if self.token:
            cookies["token"] = self.token
        return cookies

    def handshake(self):
        url = self._get_portal_endpoint()
        params = {
            "type": "stb",
            "action": "handshake",
            "token": "",
            "JsHttpRequest": "1-xml",
        }

        try:
            self.session.cookies.clear()
            response = self.session.get(
                url,
                params=params,
                headers=self.get_headers(),
                cookies={"mac": self.mac},
                timeout=10,
            )
            response.raise_for_status()
            data = self.safe_json_parse(response)
            js_data = self._extract_js_payload(data)

            token = js_data.get("token") if isinstance(js_data, dict) else None
            if not token:
                raise ConnectionError("Handshake response did not contain a token")

            self.token = token
            self.bearer_token = token
            self.last_handshake = time.time()
            self._save_cached_auth()
            logger.debug("Handshake successful for %s", self.portal_url)
        except Exception as exc:
            self._clear_cached_auth()
            logger.error("Handshake failed: %s", exc, exc_info=True)
            raise ConnectionError("Failed to perform handshake")

    def fetch_all_pages(self, category_type: str, category_id: str) -> List[Dict]:
        self.ensure_valid_token()
        base_url = self._get_portal_endpoint()

        type_map = {"IPTV": "itv", "VOD": "vod", "Series": "series"}
        param_key_map = {"IPTV": "genre", "VOD": "category", "Series": "category"}

        type_param = type_map.get(category_type)
        param_key = param_key_map.get(category_type)
        if not type_param:
            logger.error("Unknown category_type: %s", category_type)
            return []

        initial_params = self._build_params(type_param, "get_ordered_list", p=1, **{param_key: category_id})
        logger.debug("Fetching initial page for %s %s.", category_type, category_id)
        response = self.make_request_with_retries(
            base_url,
            params=initial_params,
            headers=self.get_headers(),
            cookies=self.get_cookies(),
        )
        if not response:
            return []

        json_response = self.safe_json_parse(response)
        if not json_response:
            return []

        items = self._extract_list_payload(json_response)
        if not items:
            return []

        total_items = self._extract_total_items(json_response)
        items_per_page = len(items)
        total_pages = (total_items + items_per_page - 1) // items_per_page if total_items > 0 else 1
        logger.debug(
            "Total items: %s, Items per page: %s, Total pages: %s",
            total_items,
            items_per_page,
            total_pages,
        )
        if total_pages <= 1:
            return self._dedupe_items(items)

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            future_to_page = {
                executor.submit(
                    self.make_request_with_retries,
                    base_url,
                    params=self._build_params(type_param, "get_ordered_list", p=page, **{param_key: category_id}),
                    headers=self.get_headers(),
                    cookies=self.get_cookies(),
                ): page
                for page in range(2, total_pages + 1)
            }

            for future in as_completed(future_to_page):
                page = future_to_page[future]
                try:
                    page_response = future.result()
                    if not page_response:
                        continue

                    page_json = self.safe_json_parse(page_response)
                    page_items = self._extract_list_payload(page_json)
                    if page_items:
                        items.extend(page_items)
                        logger.debug("Fetched page %s with %s items.", page, len(page_items))
                except Exception:
                    logger.exception("Exception on page %s", page)

        final_list = self._dedupe_items(items)
        logger.info("Fetched %s unique items for category %s", len(final_list), category_id)
        return final_list

    def get_itv_categories(self):
        self.ensure_valid_token()
        response = self.make_request_with_retries(
            self._get_portal_endpoint(),
            params=self._build_params("itv", "get_genres"),
            headers=self.get_headers(),
            cookies=self.get_cookies(),
        )
        return self._extract_list_payload(self.safe_json_parse(response))

    def get_channels_in_category(self, category_id):
        return self.fetch_all_pages("IPTV", category_id)

    def get_vod_categories(self):
        self.ensure_valid_token()
        response = self.make_request_with_retries(
            self._get_portal_endpoint(),
            params=self._build_params("vod", "get_categories"),
            headers=self.get_headers(),
            cookies=self.get_cookies(),
        )
        return self._extract_list_payload(self.safe_json_parse(response))

    def get_vod_in_category(self, category_id):
        return self.fetch_all_pages("VOD", category_id)

    def get_series_categories(self):
        self.ensure_valid_token()
        response = self.make_request_with_retries(
            self._get_portal_endpoint(),
            params=self._build_params("series", "get_categories"),
            headers=self.get_headers(),
            cookies=self.get_cookies(),
        )
        return self._extract_list_payload(self.safe_json_parse(response))

    def get_series_in_category(self, category_id):
        return self.fetch_all_pages("Series", category_id)

    def get_seasons(self, movie_id):
        self.ensure_valid_token()
        response = self.make_request_with_retries(
            self._get_portal_endpoint(),
            params=self._build_params("series", "get_ordered_list", movie_id=movie_id),
            headers=self.get_headers(),
            cookies=self.get_cookies(),
        )
        return self._extract_list_payload(self.safe_json_parse(response))

    def get_episodes(self, movie_id, season_id):
        self.ensure_valid_token()
        response = self.make_request_with_retries(
            self._get_portal_endpoint(),
            params=self._build_params("series", "get_ordered_list", movie_id=movie_id, season_id=season_id),
            headers=self.get_headers(),
            cookies=self.get_cookies(),
        )
        return self._extract_list_payload(self.safe_json_parse(response))

    def _search(self, request_type: str, query: str) -> List[Dict[str, Any]]:
        self.ensure_valid_token()
        response = self.make_request_with_retries(
            self._get_portal_endpoint(),
            params=self._build_params(request_type, "search", q=query),
            headers=self.get_headers(),
            cookies=self.get_cookies(),
        )
        if response:
            results = self._extract_list_payload(self.safe_json_parse(response))
            if results:
                return results

        if request_type not in ("vod", "series"):
            return []

        logger.info("Falling back to get_ordered_list search for %s", request_type)
        fallback_response = self.make_request_with_retries(
            self._get_portal_endpoint(),
            params=self._build_params(request_type, "get_ordered_list", search=query),
            headers=self.get_headers(),
            cookies=self.get_cookies(),
        )
        if not fallback_response:
            return []
        return self._extract_list_payload(self.safe_json_parse(fallback_response))

    def search_itv(self, query):
        return self._search("itv", query)

    def search_vod(self, query):
        return self._search("vod", query)

    def search_series(self, query):
        return self._search("series", query)

    def _create_link(self, request_type: str, **extra) -> Optional[str]:
        self.ensure_valid_token()
        response = self.make_request_with_retries(
            self._get_portal_endpoint(),
            params=self._build_params(request_type, "create_link", **extra),
            headers=self.get_headers(),
            cookies=self.get_cookies(),
            timeout=15,
        )
        if not response:
            return None

        return self._normalize_stream_value(self._extract_cmd(self.safe_json_parse(response)))

    def get_stream_link(self, cmd, stream_id):
        stream_cmd = self._normalize_stream_value(cmd)
        if not stream_cmd:
            return None

        returned_cmd = self._create_link("itv", cmd=stream_cmd)
        if not returned_cmd:
            return None

        play_token = self._extract_play_token(returned_cmd)
        resolved_stream_id = self._resolve_stream_id(stream_id, returned_cmd, stream_cmd)
        if play_token and resolved_stream_id:
            return "%s/play/live.php?mac=%s&stream=%s&extension=ts&play_token=%s" % (
                self.portal_url,
                self.mac,
                resolved_stream_id,
                play_token,
            )
        return returned_cmd

    def get_vod_stream_url(self, movie_id):
        returned_url = self._create_link("vod", cmd="movie %s" % movie_id)
        if not returned_url:
            return None

        play_token = self._extract_play_token(returned_url)
        if play_token:
            return "%s/play/movie.php?mac=%s&stream=%s.mkv&play_token=%s&type=movie" % (
                self.portal_url,
                self.mac,
                movie_id,
                play_token,
            )
        return returned_url

    def get_series_stream_url(self, cmd, episode_num):
        return self._create_link("vod", cmd=str(cmd), series=episode_num)
