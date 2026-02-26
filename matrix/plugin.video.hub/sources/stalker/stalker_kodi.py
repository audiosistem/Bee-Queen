import requests
import hashlib
import time
from collections import OrderedDict
from urllib.parse import quote, urlencode, urlparse
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Callable
from threading import Lock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StalkerPortal:
    def __init__(self, portal_url, mac, serial=None, num_threads=10, progress_callback=None):
        self.portal_url = portal_url.rstrip("/")
        self.mac = mac.strip()
        self.serial = serial
        self.session = requests.Session()
        self.token = None
        self.bearer_token = None
        self.last_handshake = 0
        self.token_expiry = 3600  # 1 hour default
        self.num_threads = num_threads
        self.progress_callback = progress_callback
        self.progress_lock = Lock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def report_progress(self, progress: int):
        if self.progress_callback:
            with self.progress_lock:
                progress = min(max(progress, 0), 100)
                self.progress_callback(progress)
                logger.debug(f"Reported progress: {progress}%")

    def make_request_with_retries(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None, cookies: Optional[Dict] = None, retries=3, backoff_factor=0.5, timeout=10) -> Optional[requests.Response]:
        for attempt in range(1, retries + 1):
            try:
                logger.debug(f"Attempt {attempt}: GET {url} with params={params}")
                response = self.session.get(url, params=params, headers=headers, cookies=cookies, timeout=timeout)
                response.raise_for_status()
                logger.debug(f"Received response: {response.status_code}")
                return response
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt} failed for URL {url}: {e}")
                if attempt < retries:
                    time.sleep(backoff_factor * (2 ** (attempt - 1)))
        logger.error(f"All {retries} attempts failed for URL {url}")
        return None

    def safe_json_parse(self, response: Optional[requests.Response]) -> Optional[Dict]:
        if not response: return None
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError):
            logger.error("Failed to decode JSON.", exc_info=True)
            logger.debug("Response text: " + response.text)
            return None

    def ensure_valid_token(self):
        current_time = time.time()
        if not self.token or (current_time - self.last_handshake) > (self.token_expiry - 300):
            logger.debug("Token expired or missing, performing handshake.")
            self.handshake()

    def get_headers(self):
        headers = {
            'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3',
            'Referer': f'{self.portal_url}/stalker_portal/c/index.html',
            'X-User-Agent': 'Model: MAG250; Link: WiFi',
            'Host': urlparse(self.portal_url).netloc
        }
        if self.bearer_token:
            headers['Authorization'] = f'Bearer {self.bearer_token}'
        return headers

    def get_cookies(self):
        cookies = {'mac': self.mac, 'stb_lang': 'en', 'timezone': 'Europe/Paris'}
        if self.token:
            cookies['token'] = self.token
        return cookies

    def handshake(self):
        url = f"{self.portal_url}/portal.php?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        try:
            response = self.session.get(url, headers=self.get_headers(), cookies={'mac': self.mac}, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.token = data.get('js', {}).get('token')
            self.bearer_token = self.token
            self.last_handshake = time.time()
            logger.debug(f"Handshake successful, token: {self.token}")
        except Exception as e:
            logger.error(f"Handshake failed: {e}", exc_info=True)
            raise ConnectionError("Failed to perform handshake")

    def fetch_all_pages(self, category_type: str, category_id: str) -> List[Dict]:
        self.ensure_valid_token()
        base_url = f"{self.portal_url}/portal.php"
        
        type_map = {"IPTV": "itv", "VOD": "vod", "Series": "series"}
        param_key_map = {"IPTV": "genre", "VOD": "category", "Series": "category"}
        
        type_param = type_map.get(category_type)
        param_key = param_key_map.get(category_type)
        if not type_param:
            logger.error(f"Unknown category_type: {category_type}")
            return []

        # 1. Fetch initial page to get total pages
        initial_params = {"type": type_param, "action": "get_ordered_list", param_key: category_id, "JsHttpRequest": "1-xml", "p": 1}
        logger.debug(f"Fetching initial page for {category_type} {category_id}.")
        response = self.make_request_with_retries(base_url, params=initial_params, headers=self.get_headers(), cookies=self.get_cookies())
        if not response:
            return []

        json_response = self.safe_json_parse(response)
        if not json_response: return []

        js_data = json_response.get("js", {})
        try:
            total_items = int(js_data.get("total_items", "0"))
        except (ValueError, TypeError): total_items = 0
        
        data_list = js_data.get("data", [])
        if not data_list: return [] # No items on first page

        items_per_page = len(data_list)
        total_pages = (total_items + items_per_page - 1) // items_per_page if total_items > 0 else 1
        logger.debug(f"Total items: {total_items}, Items per page: {items_per_page}, Total pages: {total_pages}")

        items = data_list
        if total_pages <= 1:
            return items

        # 2. Fetch remaining pages concurrently
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            future_to_page = {executor.submit(self.make_request_with_retries, base_url, params={"type": type_param, "action": "get_ordered_list", param_key: category_id, "JsHttpRequest": "1-xml", "p": p}, headers=self.get_headers(), cookies=self.get_cookies()): p for p in range(2, total_pages + 1)}
            
            for future in as_completed(future_to_page):
                page = future_to_page[future]
                try:
                    resp = future.result()
                    if resp:
                        json_resp = self.safe_json_parse(resp)
                        if json_resp:
                            page_data = json_resp.get("js", {}).get("data", [])
                            items.extend(page_data)
                            logger.debug(f"Fetched page {page} with {len(page_data)} items.")
                except Exception:
                    logger.exception(f"Exception on page {page}")

        unique = {i['id']: i for i in items if 'id' in i}
        final_list = list(unique.values())
        final_list.sort(key=lambda x: x.get("name", ""))
        logger.info(f"Fetched {len(final_list)} unique items for category {category_id}")
        return final_list

    def get_itv_categories(self):
        self.ensure_valid_token()
        url = f"{self.portal_url}/portal.php?type=itv&action=get_genres&JsHttpRequest=1-xml"
        response = self.make_request_with_retries(url, headers=self.get_headers(), cookies=self.get_cookies())
        return self.safe_json_parse(response).get('js', []) if response else []

    def get_channels_in_category(self, category_id):
        return self.fetch_all_pages("IPTV", category_id)

    def get_vod_categories(self):
        self.ensure_valid_token()
        url = f"{self.portal_url}/portal.php?type=vod&action=get_categories&JsHttpRequest=1-xml"
        response = self.make_request_with_retries(url, headers=self.get_headers(), cookies=self.get_cookies())
        return self.safe_json_parse(response).get('js', []) if response else []

    def get_vod_in_category(self, category_id):
        return self.fetch_all_pages("VOD", category_id)

    def get_series_categories(self):
        self.ensure_valid_token()
        url = f"{self.portal_url}/portal.php?type=series&action=get_categories&JsHttpRequest=1-xml"
        response = self.make_request_with_retries(url, headers=self.get_headers(), cookies=self.get_cookies())
        return self.safe_json_parse(response).get('js', []) if response else []

    def get_series_in_category(self, category_id):
        return self.fetch_all_pages("Series", category_id)

    def get_seasons(self, movie_id):
        self.ensure_valid_token()
        url = f"{self.portal_url}/portal.php?type=series&action=get_ordered_list&movie_id={movie_id}&JsHttpRequest=1-xml"
        response = self.make_request_with_retries(url, headers=self.get_headers(), cookies=self.get_cookies())
        return self.safe_json_parse(response).get('js', {}).get('data', []) if response else []

    def get_episodes(self, movie_id, season_id):
        self.ensure_valid_token()
        url = f"{self.portal_url}/portal.php?type=series&action=get_ordered_list&movie_id={movie_id}&season_id={season_id}&JsHttpRequest=1-xml"
        response = self.make_request_with_retries(url, headers=self.get_headers(), cookies=self.get_cookies())
        return self.safe_json_parse(response).get('js', {}).get('data', []) if response else []

    def search_itv(self, query):
        self.ensure_valid_token()
        url = f"{self.portal_url}/portal.php?type=itv&action=search&q={quote(query)}&JsHttpRequest=1-xml"
        response = self.make_request_with_retries(url, headers=self.get_headers(), cookies=self.get_cookies())
        return self.safe_json_parse(response).get('js', {}).get('data', []) if response else []

    def search_vod(self, query):
        self.ensure_valid_token()
        url = f"{self.portal_url}/portal.php?type=vod&action=search&q={quote(query)}&JsHttpRequest=1-xml"
        response = self.make_request_with_retries(url, headers=self.get_headers(), cookies=self.get_cookies())
        return self.safe_json_parse(response).get('js', {}).get('data', []) if response else []

    def search_series(self, query):
        self.ensure_valid_token()
        url = f"{self.portal_url}/portal.php?type=series&action=search&q={quote(query)}&JsHttpRequest=1-xml"
        response = self.make_request_with_retries(url, headers=self.get_headers(), cookies=self.get_cookies())
        return self.safe_json_parse(response).get('js', {}).get('data', []) if response else []

    def get_stream_link(self, cmd, stream_id):
        self.ensure_valid_token()
        stream_cmd = cmd.strip()
        if re.match(r'(?i)^ffmpeg\s*(.*)', stream_cmd):
            stream_cmd = re.sub(r'(?i)^ffmpeg\s*', '', stream_cmd).strip()
        
        url = f"{self.portal_url}/portal.php?type=itv&action=create_link&cmd={quote(stream_cmd)}&JsHttpRequest=1-xml"
        response = self.make_request_with_retries(url, headers=self.get_headers(), cookies=self.get_cookies())
        if not response: return None
            
        data = self.safe_json_parse(response)
        if not data: return None

        returned_cmd = data.get('js', {}).get('cmd')
        if returned_cmd:
            try:
                play_token = returned_cmd.split('play_token=')[1].split('&')[0]
                return f"{self.portal_url}/play/live.php?mac={self.mac}&stream={stream_id}&extension=ts&play_token={play_token}"
            except IndexError:
                return returned_cmd
        return None

    def get_vod_stream_url(self, movie_id):
        self.ensure_valid_token()
        cmd = f"movie {movie_id}"
        url = f"{self.portal_url}/portal.php?type=vod&action=create_link&cmd={quote(cmd)}&JsHttpRequest=1-xml"
        response = self.make_request_with_retries(url, headers=self.get_headers(), cookies=self.get_cookies())
        if not response: return None
            
        data = self.safe_json_parse(response)
        if not data: return None

        returned_url = data.get('js', {}).get('cmd')
        if returned_url:
            try:
                play_token = returned_url.split('play_token=')[1].split('&')[0]
                return f"{self.portal_url}/play/movie.php?mac={self.mac}&stream={movie_id}.mkv&play_token={play_token}&type=movie"
            except IndexError:
                return self.get_stream_link(returned_url, movie_id) # Fallback
        return None

    def get_series_stream_url(self, cmd, episode_num):
        self.ensure_valid_token()
        url = f"{self.portal_url}/portal.php?type=vod&action=create_link&cmd={quote(cmd)}&series={episode_num}&JsHttpRequest=1-xml"
        response = self.make_request_with_retries(url, headers=self.get_headers(), cookies=self.get_cookies())
        if not response: return None

        data = self.safe_json_parse(response)
        if not data: return None

        stream_url = data.get('js', {}).get('cmd')
        if stream_url and stream_url.startswith('ffmpeg '):
            return stream_url.split(' ', 1)[1]
        return stream_url
