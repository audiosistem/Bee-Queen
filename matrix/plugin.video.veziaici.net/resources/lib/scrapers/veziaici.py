"""Scraper for veziaici.net."""

import re
import json
import urllib.parse
from bs4 import BeautifulSoup
from resources.lib.utils import (
    get_html_content,
    get_custom_image,
    log,
    log_error,
    BASE_URL_VEZIAICI,
)


def get_main_menu_items():
    """Get main menu categories from veziaici.net."""
    try:
        response = get_html_content(BASE_URL_VEZIAICI)
        response.raise_for_status()
        html_content = response.text
    except Exception as e:
        log_error(f"Failed to fetch main page: {e}")
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    categories = []

    for top_li in soup.select("ul#main-menu > li.menu-item-has-children"):
        category_title_element = top_li.find("span")
        if not category_title_element:
            continue

        category_title = category_title_element.text.strip()
        sub_menu = top_li.find("ul", class_="sub-menu")

        if category_title and sub_menu:
            shows = []
            for sub_li in sub_menu.find_all("li"):
                link = sub_li.find("a")
                if link and "href" in link.attrs:
                    title = link.text.strip()
                    url = link["href"]
                    if title and url:
                        shows.append({"title": title, "url": url})
            if shows:
                categories.append({"title": category_title, "shows": shows})

    return categories


def _scrape_page(url):
    """Helper to scrape a single page of episodes."""
    episodes = []
    try:
        response = get_html_content(url)
        if response.status_code != 200:
            return [], None
        soup = BeautifulSoup(response.text, "html.parser")
        
        for title_element in soup.find_all(["h3", "h2"], class_="entry-title"):
            link_element = title_element.find("a")
            if link_element:
                item_url = link_element.get("href")
                title = link_element.text.strip()
                if item_url and title:
                    episodes.append({"title": title, "url": item_url})
        
        next_link = soup.find("a", class_="next page-numbers")
        next_url = next_link.get("href") if next_link else None
        return episodes, next_url
    except Exception:
        return [], None


def get_episodes(url, cache_file=None, cache_expiry=86400):
    """Get all episodes from a show page with optimized parallel scraping."""
    from resources.lib.utils import parallel_map
    
    # 1. Scrape first page to get initial data and check for pagination
    first_page_episodes, next_url = _scrape_page(url)
    if not next_url:
        return first_page_episodes

    # 2. If there are more pages, detect page range or just scrape a few ahead in parallel
    # Veziaici usually has /page/2/, /page/3/ format
    all_episodes = list(first_page_episodes)
    
    # Optimized: If we have a next_url, let's try to guess the first 10 pages and fetch them in parallel
    # Most series don't exceed 10-20 pages.
    base_url = url.rstrip('/')
    page_urls = [f"{base_url}/page/{i}/" for i in range(2, 11)]
    
    results = parallel_map(lambda u: _scrape_page(u)[0], page_urls)
    for page_eps in results:
        all_episodes.extend(page_eps)
        
    return all_episodes


def parse_seasons(episodes, show_name=""):
    """Parse episodes and group by season."""
    seasons = {}
    no_season_episodes = []

    season_patterns = [
        r"(?:sezonul|sezon|season)\s*\.?\s*(\d+)",  # Sezonul 1, Sezon 1, Season 1
        r"[Ss](\d+)[Ee]\d+",  # S01E02, s1e2
        r"(\d+)x\d+",  # 1x01
    ]

    for episode in episodes:
        season_num = None
        title = episode["title"]

        for pattern in season_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                season_num = int(match.group(1))
                break

        if season_num is not None:
            if season_num not in seasons:
                seasons[season_num] = []
            seasons[season_num].append(episode)
        else:
            no_season_episodes.append(episode)

    return seasons, no_season_episodes


def get_sources(url):
    """Get video sources from an episode page."""
    try:
        response = get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch source page: {e}")
        return []

    sources = []
    seen_urls = set()

    # Cauta iframes cu data-lazy-src (lazy loading) SAU src direct
    iframes = soup.find_all("iframe")

    for iframe in iframes:
        video_url = (
            iframe.get("data-lazy-src")
            or iframe.get("data-src")
            or iframe.get("src")
            or ""
        )

        if not video_url or video_url == "about:blank":
            continue

        if video_url.startswith("//"):
            video_url = "https:" + video_url

        if video_url in seen_urls:
            continue
        seen_urls.add(video_url)

        domain = urllib.parse.urlparse(video_url).netloc.replace("www.", "")
        sources.append({"url": video_url, "domain": domain, "referer": url})

    return sources

def search(query, url=None, max_pages=4):
    """Search veziaici.net for content with multi-page support and pagination."""
    if url:
        current_url = url
    else:
        current_url = f"{BASE_URL_VEZIAICI}?s={urllib.parse.quote_plus(query)}"
        
    results = []
    page_count = 0
    next_page_url = None

    while current_url and page_count < max_pages:
        try:
            response = get_html_content(current_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            log_error(f"Failed to fetch search results page {page_count + 1}: {e}")
            break

        # Try several selector patterns for better compatibility
        entries = soup.select(".entry-title a")
        if not entries:
            # Fallback to general h2/h3 links if class is missing
            entries = soup.select("h2 a, h3 a")
            
        found_on_page = 0
        for entry in entries:
            title = entry.get("title") or entry.text.strip()
            item_url = entry.get("href")
            # Filter to avoid menu links or other non-result links
            if title and item_url and "veziaici.net" in item_url and "/category/" not in item_url:
                # Basic deduplication
                if not any(r["url"] == item_url for r in results):
                    results.append({"title": title, "url": item_url})
                    found_on_page += 1

        # Check for next page
        next_link = soup.find("a", class_="next page-numbers")
        if next_link and next_link.has_attr("href"):
            next_page_url = next_link["href"]
            current_url = next_page_url
            page_count += 1
        else:
            next_page_url = None
            current_url = None
            
        if found_on_page == 0:
            break

    return results, next_page_url


def get_latest(url, max_pages=3):
    """Get latest episodes from a category."""
    all_items = []
    current_url = url
    page_count = 0

    while current_url and page_count < max_pages:
        try:
            response = get_html_content(current_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception:
            break

        for title_element in soup.find_all(["h3", "h2"], class_="entry-title"):
            link_element = title_element.find("a")
            if link_element:
                item_url = link_element.get("href")
                title = link_element.text.strip()
                if item_url and title:
                    all_items.append({"title": title, "url": item_url})

        next_page_link = soup.find("a", class_="next page-numbers")
        if next_page_link and next_page_link.has_attr("href"):
            current_url = next_page_link["href"]
        else:
            current_url = None

        page_count += 1

    return all_items, current_url
