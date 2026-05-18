"""Scraper for serialecoreene.org."""

import re
import requests
import urllib.parse
from bs4 import BeautifulSoup
from resources.lib.utils import (
    get_html_content,
    log,
    log_error,
    BASE_URL_SERIALECOREENE,
)


def get_main_menu():
    """Get main menu items for serialecoreene.org."""
    menu = [
        {
            "title": "Toate Seriale",
            "url": f"{BASE_URL_SERIALECOREENE.rstrip('/')}/series/",
            "mode": "list_serialecoreene_all_series",
        },
        {
            "title": "Seriale Coreene",
            "url": f"{BASE_URL_SERIALECOREENE.rstrip('/')}/genre/seriale-coreene/",
            "mode": "list_serialecoreene_korean_series",
        },
        {
            "title": "Seriale Thailandeze",
            "url": f"{BASE_URL_SERIALECOREENE.rstrip('/')}/genre/thailanda/",
            "mode": "list_serialecoreene_thai_series",
        },
        {
            "title": "Episoade Noi",
            "url": f"{BASE_URL_SERIALECOREENE.rstrip('/')}/episode/",
            "mode": "list_serialecoreene_new_episodes",
        },
    ]
    return menu


def get_series_list(url, page="1"):
    """Get list of series from a category or search page."""
    try:
        page_url = url
        if int(page) > 1:
            if "?s=" in url:
                if "&paged=" in url:
                    page_url = re.sub(r"&paged=\d+", f"&paged={page}", url)
                else:
                    page_url = f"{url}&paged={page}"
            else:
                page_url = f"{url.rstrip('/')}/page/{page}/"

        response = get_html_content(page_url, cache_time=3600)
        if response.status_code != 200:
            log_error(f"Failed to fetch page: {page_url} (Status: {response.status_code})")
            return [], None
            
        soup = BeautifulSoup(response.text, "html.parser")
        series = []
        
        # Site uses 'ml-item' for both series and episodes
        items = soup.find_all("div", class_="ml-item")
        
        for item in items:
            link_tag = item.find("a", class_="ml-mask")
            if not link_tag: continue
            
            title = link_tag.get("oldtitle") or link_tag.get("title") or (item.find("h2").text if item.find("h2") else "")
            series_url = link_tag.get("href")
            
            img_tag = item.find("img")
            thumb = ""
            if img_tag:
                thumb = img_tag.get("data-original") or img_tag.get("data-src") or img_tag.get("src")
            
            if title and series_url:
                series.append({
                    "title": title.strip(),
                    "url": series_url,
                    "thumb": thumb
                })

        # Pagination
        next_page = None
        pagination = soup.find("ul", class_="pagination") or soup.find("div", class_="pagination")
        if pagination:
            # Look for "Next" link or next numeric link
            next_link = pagination.find("a", class_="next") or pagination.find("a", class_="page-numbers", string=re.compile(r"next", re.I))
            if not next_link:
                # Find the 'active' item and get the next one
                active_item = pagination.find("li", class_="active") or pagination.find("span", class_="current")
                if active_item:
                    next_item = active_item.find_next_sibling(["li", "a"])
                    if next_item:
                        next_anchor = next_item if next_item.name == "a" else next_item.find("a")
                        if next_anchor and next_anchor.get("href"):
                            next_page = str(int(page) + 1)
            elif next_link.get("href"):
                next_page = str(int(page) + 1)

        return series, next_page

    except Exception as e:
        log_error(f"Error getting series list: {e}")
        return [], None


def search(query, page="1"):
    """Search serialecoreene.org for content."""
    search_url = f"{BASE_URL_SERIALECOREENE}?s={urllib.parse.quote_plus(query)}"
    return get_series_list(search_url, page=page)


def get_new_episodes(url, page="1"):
    """Get list of new episodes from /episode/ page."""
    return get_series_list(url, page)


def get_episodes_and_sources(url):
    """Get episodes from a series page."""
    try:
        response = get_html_content(url, cache_time=3600)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        
        episodes = []
        seasons_container = soup.find("div", id="seasons")

        if seasons_container:
            for season_div in seasons_container.find_all("div", class_="tvseason"):
                season_title_tag = season_div.find(["strong", "div"], class_="les-title")
                season_num = "1"
                if season_title_tag:
                    season_num_match = re.search(r'Sezonul\s+(\d+)', season_title_tag.text)
                    if season_num_match:
                        season_num = season_num_match.group(1)
                
                content = season_div.find("div", class_="les-content")
                if content:
                    for link in content.find_all("a", href=True):
                        ep_url = link["href"]
                        ep_title = link.text.strip()
                        
                        # Formatting: S01E01 - Title
                        ep_num_match = re.search(r'Episodul\s+(\d+)', ep_title)
                        if ep_num_match:
                            display_title = f"S{season_num.zfill(2)}E{ep_num_match.group(1).zfill(2)} - {ep_title}"
                        else:
                            display_title = f"S{season_num.zfill(2)} - {ep_title}"

                        episodes.append({
                            "title": display_title,
                            "url": ep_url,
                        })
        else:
            # Fallback for simple layouts
            content_div = soup.find("div", id="content-embed") or soup.find("div", class_="les-content")
            if content_div:
                for link in content_div.find_all("a", href=True):
                    episodes.append({
                        "title": link.text.strip(),
                        "url": link["href"]
                    })

        return episodes

    except Exception as e:
        log_error(f"Error getting episodes: {e}")
        return []


def extract_js_redirect_param(html_content, func_name):
    """Extract redirect parameter from JavaScript function."""
    func_pattern = rf'function\s+{re.escape(func_name)}\s*\(\)\s*\{{\s*window\.location\.href\s*=\s*"([^"]+)"\s*;\s*\}}'
    match = re.search(func_pattern, html_content)
    if match:
        return match.group(1)
    return None


def get_playable_url(episode_url):
    """Get playable video URL from episode page (handles new shortcdn.org structure)."""
    try:
        # Step 1: Fetch the initial episode page
        response = get_html_content(episode_url, cache_time=0)
        if response.status_code != 200:
            log_error(f"Failed to fetch episode page: {response.status_code}")
            return None

        # Step 2: Look for the redirect parameter (?load=...)
        load_match = re.search(r'window\.location\.href\s*=\s*"\?load=([^"]+)"', response.text)
        
        if load_match:
            load_param = load_match.group(1)
            redirect_url = f"{episode_url}?load={load_param}"
            log(f"Following redirect to: {redirect_url}")
            response = get_html_content(redirect_url, cache_time=0)
            if response.status_code != 200:
                log_error(f"Failed to fetch redirected page: {response.status_code}")
                return None

        page_html = response.text

        # Step 3: Look for shortcdn.org API URL
        shortcdn_match = re.search(r'(https?://shortcdn\.org/[^\s"\'<>]+)', page_html)
        
        if shortcdn_match:
            shortcdn_url = shortcdn_match.group(1)
            log(f"Found shortcdn URL: {shortcdn_url}")
            return _resolve_shortcdn(shortcdn_url, episode_url)

        # Step 4: Fallback - look for iframe directly
        soup = BeautifulSoup(page_html, "html.parser")
        iframe = soup.find("iframe", src=True)
        if iframe:
            video_url = iframe["src"]
            if video_url.startswith("//"):
                video_url = "https:" + video_url
            return {"url": video_url, "referer": episode_url}

        # Step 5: Look for data-url attributes with base64 encoded sources
        sources = _extract_base64_sources(page_html)
        if sources:
            return {"url": sources[0], "referer": episode_url}

        log_error("Could not find video source in episode page")
        return None

    except Exception as e:
        log_error(f"Error getting playable URL: {e}")
        import traceback
        log_error(traceback.format_exc())
        return None


def _resolve_shortcdn(shortcdn_url, referer):
    """Resolve video sources from shortcdn.org embed page."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Referer': referer,
        }
        
        response = requests.get(shortcdn_url, headers=headers, timeout=15)
        if response.status_code != 200:
            log_error(f"shortcdn returned status {response.status_code}")
            return None

        html = response.text
        sources = _extract_base64_sources(html)
        
        if sources:
            # Return the first valid source (prefer vidmoly/filemoon over netu)
            preferred_order = ['vidmoly', 'filemoon', 'byselapuix', 'netu']
            for pref in preferred_order:
                for src in sources:
                    if pref in src.lower():
                        log(f"Selected source: {src}")
                        return {"url": src, "referer": shortcdn_url}
            
            # If no preferred match, return first source
            log(f"Using first available source: {sources[0]}")
            return {"url": sources[0], "referer": shortcdn_url}

        log_error("No sources found in shortcdn page")
        return None

    except Exception as e:
        log_error(f"Error resolving shortcdn: {e}")
        return None


def _extract_base64_sources(html):
    """Extract base64-encoded video source URLs from data-url attributes."""
    import base64
    
    sources = []
    # Find all data-url attributes with base64 values
    data_urls = re.findall(r'data-url\s*=\s*["\']([A-Za-z0-9+/=]+)["\']', html)
    
    for encoded in data_urls:
        try:
            decoded = base64.b64decode(encoded).decode('utf-8')
            # Only keep valid URLs (skip things like ?ad_level=3)
            if decoded.startswith('http'):
                sources.append(decoded)
        except Exception:
            continue
    
    return sources
