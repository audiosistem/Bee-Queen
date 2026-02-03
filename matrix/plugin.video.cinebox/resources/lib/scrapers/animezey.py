# CORRECTED VERSION - ORIGINAL_TITLE FOR SERIES

import re
import requests
import json
import xbmc
import traceback
import threading
import unicodedata
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlencode, parse_qs

# --- Package Imports ---
from .session import USER_AGENT
from .utils import guess_quality_from_name, get_anime_search_codes, format_size, normalize_for_compare
from ..debug_logger import logger

# --- Custom Settings and Exceptions ---
class AnimeZeyScraperError(Exception):
    """Base exception for AnimeZey scraper"""
    pass

class ScraperConfig:
    """Centralized scraper settings"""
    MAX_THREADS = 8
    REQUEST_TIMEOUT = 25
    MAX_RETRIES = 3
    RETRY_DELAY = 1
    STOP_WORDS = {
        'a', 'an', 'the', 'e', 'o', 'as', 'os', 'um', 'uma', 'uns', 'umas',
        'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
        'por', 'para', 'com', 'sem', 'sob', 'sobre', 'to', 'of', 'in', 'on',
        'at', 'for', 'from', 'with', 'by', 'and', 'or', 'but', 'until'
    }

# --- Decorators for Retry ---
def with_retry(max_retries=3, delay=1):
    """Decorator for automatic retry on network failures"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.Timeout, 
                       requests.exceptions.ConnectionError,
                       requests.exceptions.ChunkedEncodingError) as e:
                    if attempt == max_retries - 1:
                        raise
                    xbmc.log(f"🔄 Tentativa {attempt + 1}/{max_retries} falhou, aguardando {delay}s...", xbmc.LOGWARNING)
                    time.sleep(delay * (attempt + 1))
                except Exception as e:
                    raise
            return None
        return wrapper
    return decorator

# --- Auxiliary Functions ---
@with_retry(max_retries=ScraperConfig.MAX_RETRIES, delay=ScraperConfig.RETRY_DELAY)
def _post_to_animezey(url, payload):
    """Improved function for POST requests with retry"""
    headers = {
        "accept": "*/*",
        "accept-language": "pt-BR,pt;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,mt;q=0.5",
        "content-type": "application/json",
        "sec-ch-ua": "\"Microsoft Edge\";v=\"141\", \"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"141\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "Referer": url,
        "User-Agent": USER_AGENT
    }
    
    try:
        headers.pop("Cookie", None)
        logger.network(url, method='POST')
        response = requests.post(url, headers=headers, json=payload, 
                               timeout=ScraperConfig.REQUEST_TIMEOUT)
        logger.network(url, method='POST', status=response.status_code, response=response.text if response.status_code != 200 else "OK")
        response.raise_for_status()
        
        try:
            return response.json()
        except json.JSONDecodeError as e:
            xbmc.log(f"[animezey] ❌ Response is not JSON from {url}: {e}", xbmc.LOGERROR)
            logger.scraper_error("AnimeZey", f"Invalid JSON: {e}", url)
            return None
            
    except requests.exceptions.HTTPError as http_err:
        status = getattr(http_err.response, 'status_code', 'N/A')
        text = getattr(http_err.response, 'text', str(http_err))[:500]
        xbmc.log(f"[animezey] ⚠️ HTTP Error {status} em {url}: {text}", xbmc.LOGWARNING)
        logger.scraper_error("AnimeZey", f"HTTP Error {status}: {text}", url)
        return None
    except requests.exceptions.RequestException as e:
        xbmc.log(f"[animezey] ⚠️ Request Error em {url}: {str(e)}", xbmc.LOGWARNING)
        logger.scraper_error("AnimeZey", f"Request Error: {e}", url)
        return None
    except Exception as e:
        xbmc.log(f"[animezey] ❌ General Error in {url}: {str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)
        logger.scraper_error("AnimeZey", f"General Error: {e}", url)
        return None

def remove_accents(input_str):
    """Safely remove accents"""
    if not input_str:
        return ""
    try:
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    except Exception:
        return input_str

def extract_year_from_filename(filename):
    """Extract year from file name (1900-2099)"""
    if not filename:
        return None
    
    filename_lower = filename.lower()
    
    # Pattern 1: Between periods, spaces, underscores or hyphens
    match = re.search(r'[\.\s_\-\(](19\d{2}|20\d{2})[\.\s_\-\)]', filename_lower)
    if match:
        return int(match.group(1))
    
    # Pattern 2: At the beginning or end of the name
    match = re.search(r'^(19\d{2}|20\d{2})[\.\s_\-]|[\.\s_\-](19\d{2}|20\d{2})$', filename_lower)
    if match:
        year = match.group(1) or match.group(2)
        return int(year)
    
    return None

def remove_articles(text):
    """Remove articles from the beginning of the text (The, A, An, O, A, Os, As)"""
    if not text:
        return text
    
    # Remove articles in English and Portuguese from the HOME
    text = re.sub(r'^(the|a|an|o|a|os|as)\s+', '', text, flags=re.IGNORECASE)
    return text.strip()

def calculate_title_similarity(file_name, target_title, original_title=None, media_type='movie'):
    """Calculates similarity between the file name and the searched titles.
    For MOVIES: Requires the title to be AT THE BEGINNING of the file name.
    For SERIES: More flexible, accepts title OR original_title in ANY PART of the name.
    Returns score from 0 to 100."""
    file_norm = normalize_for_compare(file_name)
    target_norm = normalize_for_compare(target_title)
    
    # Remove year from titles for fair comparison
    target_norm_clean = re.sub(r'\d{4}', '', target_norm).strip()
    
    # NEW: Removes articles for better comparison
    target_norm_no_article = remove_articles(target_norm_clean)
    
    # For movies: only take the first 100 characters
    # For series: use the full name
    file_search = file_norm[:100] if media_type == 'movie' else file_norm
    
    score = 0
    matched_title = None
    
    # SERIES: More flexible search (accepts title anywhere)
    if media_type == 'tvshow':
        # Try to match with target_title (with and without article)
        if target_norm_clean and target_norm_clean in file_search:
            score = 100
            matched_title = target_title
        elif target_norm_no_article and target_norm_no_article in file_search:
            score = 100
            matched_title = target_title
        
        # If you don't find it, try with original_title
        if original_title and score < 100:
            original_norm = normalize_for_compare(original_title)
            original_norm_clean = re.sub(r'\d{4}', '', original_norm).strip()
            original_norm_no_article = remove_articles(original_norm_clean)
            
            if original_norm_clean and original_norm_clean in file_search:
                score = 100
                matched_title = original_title
            elif original_norm_no_article and original_norm_no_article in file_search:
                score = 100
                matched_title = original_title
    
    # MOVIES: More flexible search
    else:
        # 1. MATCH AT THE BEGINNING OR ANY PART (Threshold 100 if at the start, 80 if contained)
        if target_norm_clean:
            pattern = r'^[^\w]{0,5}' + re.escape(target_norm_clean) + r'[^\w]+'
            if re.search(pattern, file_search) or file_search.startswith(target_norm_clean):
                score = 100
                matched_title = target_title
            elif target_norm_clean in file_search:
                score = 85
                matched_title = target_title
        
        # Try without an article too
        if score < 85 and target_norm_no_article:
            pattern = r'^[^\w]{0,5}' + re.escape(target_norm_no_article) + r'[^\w]+'
            if re.search(pattern, file_search) or file_search.startswith(target_norm_no_article):
                score = 100
                matched_title = target_title
            elif target_norm_no_article in file_search:
                score = 85
                matched_title = target_title
        
        # 2. Test with original title (also at the beginning)
        if original_title and score < 100:
            original_norm = normalize_for_compare(original_title)
            original_norm_clean = re.sub(r'\d{4}', '', original_norm).strip()
            original_norm_no_article = remove_articles(original_norm_clean)
            
            if original_norm_clean and original_norm_clean != target_norm_clean:
                pattern = r'^[^\w]{0,5}' + re.escape(original_norm_clean) + r'[^\w]+'
                if re.search(pattern, file_search):
                    score = 100
                    matched_title = original_title
                elif file_search.startswith(original_norm_clean):
                    score = 100
                    matched_title = original_title
            
            # Try without article
            if score < 100 and original_norm_no_article:
                pattern = r'^[^\w]{0,5}' + re.escape(original_norm_no_article) + r'[^\w]+'
                if re.search(pattern, file_search):
                    score = 100
                    matched_title = original_title
                elif file_search.startswith(original_norm_no_article):
                    score = 100
                    matched_title = original_title
    
    return score

# --- Scraper Main Class ---
class AnimeZeyScraper:
    """AnimeZey Scraper optimized with strict matching"""
    
    def __init__(self, provider_url, item_data, cancel_event=None):
        self.provider_url = provider_url
        self.item_data = item_data
        self.cancel_event = cancel_event
        self.log_prefix = "[animezey.scraper]"
        self.found_files = []
        self.processed_files = set()
        self.lock = threading.Lock()
        
        # Settings
        self.setup_domains()
        self.setup_item_data()
        
    def setup_domains(self):
        """Robustly configures domains"""
        try:
            parsed = urlparse(self.provider_url)
            self.search_domain = parsed.netloc or "1.animezey23112022.workers.dev"
            self.download_domain = "animezey16082023.animezey16082023.workers.dev"
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ⚠️ Error configuring domains: {e}", xbmc.LOGWARNING)
            self.search_domain = "1.animezey23112022.workers.dev"
            self.download_domain = "animezey16082023.animezey16082023.workers.dev"
    
    def setup_item_data(self):
        """Prepares and validates item data"""
        self.title = self.item_data.get('title', '').strip()
        self.original_title = self.item_data.get('original_title', '').strip()
        self.media_type = self.item_data.get('media_type', '').lower()
        try:
            self.year = int(self.item_data.get('year'))
        except (ValueError, TypeError):
            self.year = None
        
        if not self.title:
            raise AnimeZeyScraperError("Item data sem 'title'")
            
        # Prepare episode data if series
        self.season = self.episode = None
        if self.media_type == 'tvshow':
            try:
                self.season = int(self.item_data.get('season', 1))
                self.episode = int(self.item_data.get('episode', 1))
            except (ValueError, TypeError):
                raise AnimeZeyScraperError("Invalid season/episode")
    
    def _get_base_titles(self):
        """Gets base titles for searching"""
        titles = []
        
        # Remove year from title
        title_no_year = re.sub(r'\s*\(\d{4}\)$', '', self.title).strip()
        if title_no_year:
            titles.append(title_no_year)
            
        if self.original_title:
            original_no_year = re.sub(r'\s*\(\d{4}\)$', '', self.original_title).strip()
            if (original_no_year and title_no_year and 
                original_no_year.lower() != title_no_year.lower()):
                titles.append(original_no_year)
            elif not title_no_year and original_no_year:
                titles.append(original_no_year)
                
        return titles
    
    def generate_search_variations(self):
        """Generates simplified search variations (only searches main titles)"""
        variations = []
        
        base_titles = self._get_base_titles()
        
        for title in base_titles:
            if not title:
                continue
            
            # Original
            variations.append(title)
            
            # No accents
            no_accent = remove_accents(title)
            if no_accent and no_accent != title:
                variations.append(no_accent)
        
        return list(set(filter(None, variations)))
    
    def _fetch_page(self, search_query):
        """Search for an individual page"""
        try:
            search_url = f"https://{self.search_domain}/1:search"
            payload = {"q": search_query}
            
            response = _post_to_animezey(search_url, payload)
            
            if response and 'data' in response and 'files' in response['data']:
                files = response['data'].get('files', [])
                return files
                
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ❌ Error fetching'{search_query}': {e}", xbmc.LOGERROR)
        
        return []
    
    def _add_new_files(self, files):
        """Add new files to the global list"""
        new_files = []
        for file_data in files:
            file_id = file_data.get('id')
            if file_id and file_id not in self.processed_files:
                self.processed_files.add(file_id)
                new_files.append(file_data)
                self.found_files.append(file_data)
        return new_files
    
    def generate_search_queries(self, search_names):
        """Generates search queries based on media type"""
        queries = set()
        
        if self.media_type == 'tvshow':
            ep_codes = get_anime_search_codes(self.season, self.episode)
            
            for search_name in search_names:
                for ep_code in ep_codes:
                    queries.add(f"{search_name} {ep_code}")
                        
        else:  # movie
            for search_name in search_names:
                # Search with year
                if self.year:
                    queries.add(f"{search_name} {self.year}")
                # Yearless search too
                queries.add(search_name)
        
        return list(queries)
    
    def parallel_search(self, queries):
        """Parallel fetching using ThreadPoolExecutor"""
        start_time = time.time()
        
        def process_query(query):
            if self.cancel_event and self.cancel_event.is_set():
                return 0
            try:
                files = self._fetch_page(query)
                if files:
                    with self.lock:
                        new_files = self._add_new_files(files)
                return len(files)
            except Exception as e:
                xbmc.log(f"{self.log_prefix} ❌ Error in'{query}': {e}", xbmc.LOGERROR)
                return 0
        
        total_files = 0
        with ThreadPoolExecutor(max_workers=ScraperConfig.MAX_THREADS) as executor:
            future_to_query = {executor.submit(process_query, query): query for query in queries}
            
            for future in as_completed(future_to_query):
                if self.cancel_event and self.cancel_event.is_set():
                    # Attempts to cancel remaining futures
                    for f in future_to_query:
                        f.cancel()
                    break
                try:
                    file_count = future.result()
                    total_files += file_count
                except Exception as exc:
                    xbmc.log(f"{self.log_prefix} ❌ Exception: {exc}", xbmc.LOGERROR)
        
        return total_files
    
    def _check_episode_match(self, file_name, file_norm):
        """Checks if the episode matches (for series).
        STRICT: Only accepts the EXACT episode requested."""
        # A) Wrong Season Lock
        current_s_tag = f"s{str(self.season).zfill(2)}"
        other_seasons = [f"s{str(i).zfill(2)}" for i in range(1, 50) if i != self.season]
        
        for s_tag in other_seasons:
            if s_tag in file_norm:
                return False, f"temporada errada: {s_tag}"
        
        # B) Look for ACCURATE episode patterns
        episode_patterns = [
            # S01E02, s01e02
            rf's{str(self.season).zfill(2)}e{str(self.episode).zfill(2)}',
            # S1E2, s1e2 (no leading zero)
            rf's{self.season}e{self.episode}\b',
            # 1x02, 01x02
            rf'{str(self.season).zfill(2)}x{str(self.episode).zfill(2)}',
            rf'{self.season}x{str(self.episode).zfill(2)}',
            # - 02 -, .02., _02_ (isolated episode, VERY CAREFUL)
            rf'[\.\-_\s]0*{self.episode}[\.\-_\s]',
        ]
        
        for pattern in episode_patterns:
            if re.search(pattern, file_norm, re.IGNORECASE):
                # EXTRA VALIDATION: Ensure it is NOT another episode
                # Ex: S01E02 should not accept S01E21 or S01E12
                
                # Search all episode patterns by name
                all_ep_matches = re.findall(r's\d+e(\d+)', file_norm, re.IGNORECASE)
                if all_ep_matches:
                    # Get the first episode found
                    first_ep = int(all_ep_matches[0])
                    if first_ep == self.episode:
                        return True, f"correct episode: E{self.episode:02d}"
                    else:
                        return False, f"wrong episode: E{first_ep:02d} != E{self.episode:02d}"
                else:
                    # Didn't find pattern S01E02, but found another pattern
                    return True, f"pattern match: {pattern}"
        
        return False, f"episode {self.episode} not found"
    
    def matches_filters(self, file_name):
        """ULTRA STRICT matching function.
        For MOVIES: Requires title at the beginning + EXACT year.
        For SERIES: Accepts title/original_title anywhere + EXACT episode."""
        if not file_name:
            return False, 0
        
        file_norm = normalize_for_compare(file_name)
        
        # DEBUG LOG: Show what is being compared
        if self.media_type == 'tvshow':
            xbmc.log(
                f"{self.log_prefix} 🔍 Comparando: '{file_norm[:80]}' com '{self.title}' e '{self.original_title}'",
                xbmc.LOGDEBUG
            )
        
        # 1. CALCULATE TITLE SIMILARITY
        similarity = calculate_title_similarity(
            file_name, 
            self.title, 
            self.original_title,
            self.media_type  # NEW: pass the media type
        )
        
        # For MOVIES: Threshold reduced to 80 to accept titles that are not at the beginning
        if self.media_type == 'movie':
            if similarity < 80:
                xbmc.log(
                    f"{self.log_prefix} ❌ Rejeitado (similaridade baixa {similarity}): {file_name[:80]}", 
                    xbmc.LOGDEBUG
                )
                return False, similarity
            
            # 2. ULTRA RIGOROUS YEAR VALIDATION
            if self.year:
                file_year = extract_year_from_filename(file_name)
                
                # If you didn't find the year in the file, REJECT
                if not file_year:
                    xbmc.log(
                        f"{self.log_prefix} ❌ Rejeitado (sem ano no nome): {file_name[:80]}", 
                        xbmc.LOGDEBUG
                    )
                    return False, similarity
                
                # Year must be close (tolerance of ±1 to handle New Year releases)
                if abs(file_year - self.year) > 1:
                    xbmc.log(
                        f"{self.log_prefix} ❌ Rejeitado (ano {file_year} longe de {self.year}): {file_name[:80]}", 
                        xbmc.LOGDEBUG
                    )
                    return False, similarity
                
                # Correct year: bonus
                similarity += 10
            else:
                # If you don't have a year to validate, accept but without bonus
                xbmc.log(
                    f"{self.log_prefix} ⚠️ Aviso: filme sem ano para validar - {file_name[:80]}", 
                    xbmc.LOGWARNING
                )
        
        elif self.media_type == 'tvshow':
            # For series: threshold 70 (more flexible with original_title)
            if similarity < 70:
                xbmc.log(
                    f"{self.log_prefix} ❌ Rejeitado por baixa similaridade ({similarity:.0f}%): {file_name[:80]}", 
                    xbmc.LOGDEBUG
                )
                return False, similarity
            
            # Check episode
            ep_match, ep_reason = self._check_episode_match(file_name, file_norm)
            
            if not ep_match:
                xbmc.log(
                    f"{self.log_prefix} ❌ Rejeitado: {ep_reason} - {file_name[:80]}", 
                    xbmc.LOGDEBUG
                )
                return False, similarity
            
            similarity += 20
        
        # 3. I ACCEPT!
        xbmc.log(
            f"{self.log_prefix} ✅ Aceito (score {similarity:.0f}%): {file_name[:80]}", 
            xbmc.LOGINFO
        )
        
        return True, similarity
    
    def build_download_link(self, link_part):
        """Build full download link"""
        if not link_part or not link_part.startswith('/'):
            return None
            
        try:
            path_part, query_string = link_part.split('?', 1)
            params = parse_qs(query_string)
            
            file_id = params.get('file', [None])[0]
            if not file_id:
                return None
                
            query_params = {'file': file_id}
            
            # Add optional parameters
            for param in ['expiry', 'mac']:
                value = params.get(param, [None])[0]
                if value:
                    query_params[param] = value
            
            encoded_query = urlencode(query_params)
            return f"https://{self.download_domain}{path_part}?{encoded_query}"
            
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ⚠️ Error building link: {e}", xbmc.LOGWARNING)
            return None
    
    def _detect_language_from_filename(self, file_name):
        """Detect file language"""
        if not file_name:
            return 'PT-BR'
        
        fn = file_name.lower()
        
        # DUAL (maximum priority)
        if any(w in fn for w in ['dual', 'multi']):
            return 'DUAL'
        
        # Explicit dubbed
        if any(w in fn for w in ['dublado', 'dub ', 'pt-br', 'ptbr']):
            return 'PT-BR'
        
        # Explicit subtitles
        if any(w in fn for w in ['legendado', '[leg]', 'subs', '[eng]', 'subbed', 'english only']):
            return 'LEG'
        
        # International groups
        if any(w in fn for w in ['subsplease', 'erai-raws', 'yify', 'rarbg', 'nyaa', '[judas]']):
            return 'LEG'
        
        # Fallback: AnimeZey is BR by default
        return 'PT-BR'
    
    def filter_and_process_files(self):
        """Filters and processes found files"""
        matched_results = []
        seen_links = set()
        valid_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts')
        
        xbmc.log(f"{self.log_prefix} 🔍 Iniciando filtro de {len(self.found_files)} arquivos...", xbmc.LOGINFO)
        
        # LOG: Show title and episode searched
        if self.media_type == 'tvshow':
            xbmc.log(
                f"{self.log_prefix} 🎯 BUSCANDO: '{self.title}' (original: '{self.original_title}') S{self.season:02d}E{self.episode:02d}", 
                xbmc.LOGINFO
            )
        else:
            xbmc.log(
                f"{self.log_prefix} 🎯 BUSCANDO: '{self.title}' ({self.year})", 
                xbmc.LOGINFO
            )
        
        for file_data in self.found_files:
            file_name = file_data.get('name', '').strip()
            
            # DEBUG LOG: Show ALL files found (for series)
            if self.media_type == 'tvshow':
                xbmc.log(
                    f"{self.log_prefix} 📄 Testando: {file_name[:100]}", 
                    xbmc.LOGDEBUG
                )
            
            # Skip if not valid video
            if (not file_name or 
                file_data.get('mimeType') == 'application/vnd.google-apps.folder' or
                not any(file_name.lower().endswith(ext) for ext in valid_extensions)):
                continue
            
            # Apply COM SCORE filters
            matches, score = self.matches_filters(file_name)
            if not matches:
                continue
            
            # Build download link
            link_part = file_data.get('link')
            download_link = self.build_download_link(link_part)
            
            if download_link and download_link not in seen_links:
                seen_links.add(download_link)
                
                # Detect language
                detected_language = self._detect_language_from_filename(file_name)
                
                # Prepare metadata
                quality = guess_quality_from_name(file_name) or "HD"
                
                matched_results.append({
                    'url': download_link,
                    'quality': quality,
                    'type': 'Direct',
                    'title': file_name,  # Full name for language detection
                    'release_title': file_name,
                    'label': f"{file_name} [{quality}]",
                    'size': format_size(file_data.get('size', 0)) or '',
                    'peers': 'N/A',
                    'seeders': 'N/A', 
                    'provider': 'AnimeZey',
                    'languages': detected_language,
                    '_score': score  # Internal score for sorting
                })
        
        xbmc.log(f"{self.log_prefix} 📊 Filter completed: {len(matched_results)} accepted files", xbmc.LOGINFO)
        return matched_results

    
    
    def scrape(self):
        """Scraper main method"""
        start_time = time.time()
        
        try:
            # 1. Generate search variations
            search_names = self.generate_search_variations()
            
            search_suffix = f" S{self.season:02d}E{self.episode:02d}" if self.media_type == 'tvshow' else f" ({self.year})" if self.year else ""
            xbmc.log(f"{self.log_prefix} 🔎 Buscando '{self.title}'{search_suffix} - {len(search_names)} variations", xbmc.LOGINFO)
            
            # 2. Generate search queries
            queries = self.generate_search_queries(search_names)
            xbmc.log(f"{self.log_prefix} 📊 {len(queries)} unique queries generated", xbmc.LOGINFO)
            
            # 3. Parallel search
            self.parallel_search(queries)
            
            if not self.found_files:
                xbmc.log(f"{self.log_prefix} ⚠️ Nenhum arquivo encontrado", xbmc.LOGINFO)
                return []
            
            xbmc.log(f"{self.log_prefix} 🔍 {len(self.found_files)} unique files found", xbmc.LOGINFO)
            
            # 4. STRICT filtering
            matched_results = self.filter_and_process_files()
            
            # 5. Sort by score + quality
            if matched_results:
                quality_order = {'4K': 0, '1080p': 1, '720p': 2, 'HD': 3, 'SD': 4}
                matched_results.sort(
                    key=lambda x: (-x.get('_score', 0), quality_order.get(x['quality'], 99))
                )
                
                # Remove internal score field
                for result in matched_results:
                    result.pop('_score', None)
                
                result_suffix = f" S{self.season:02d}E{self.episode:02d}" if self.media_type == 'tvshow' else ""
                xbmc.log(f"{self.log_prefix} ✅ {len(matched_results)} valid links for'{self.title}'{result_suffix}", xbmc.LOGINFO)
            else:
                xbmc.log(f"{self.log_prefix} ❌ Nenhum arquivo correspondeu aos filtros", xbmc.LOGINFO)
            
            return matched_results
            
        except AnimeZeyScraperError as e:
            xbmc.log(f"{self.log_prefix} ❌ Scraper Error: {e}", xbmc.LOGERROR)
            return []
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ❌ General Error: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
            return []

# --- Interface Function ---
def scrape(provider_url, item_data, cancel_event=None):
    """Interface for compatibility"""
    try:
        scraper = AnimeZeyScraper(provider_url, item_data, cancel_event)
        return scraper.scrape()
    except Exception as e:
        xbmc.log(f"[animezey.scrape] ❌ Error: {e}", xbmc.LOGERROR)
        return []