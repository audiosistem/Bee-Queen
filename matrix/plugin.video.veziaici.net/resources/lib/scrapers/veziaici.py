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


def get_episodes(url, cache_file=None, cache_expiry=86400):
    """Get all episodes from a show page with pagination."""
    import os
    import time
    from resources.lib.utils import CACHE_DIR

    all_episodes = []

    # Check cache if enabled
    if cache_file:
        cache_path = os.path.join(CACHE_DIR, cache_file.replace(" ", "_") + ".json")
        if (
            os.path.exists(cache_path)
            and (time.time() - os.path.getmtime(cache_path)) < cache_expiry
        ):
            with open(cache_path, "r") as f:
                return json.load(f)

    # Scrape all pages
    current_url = url
    while current_url:
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
                    all_episodes.append({"title": title, "url": item_url})

        next_page_link = soup.find("a", class_="next page-numbers")
        if next_page_link and next_page_link.has_attr("href"):
            current_url = next_page_link["href"]
        else:
            current_url = None

    # Save to cache
    if cache_file and all_episodes:
        cache_path = os.path.join(CACHE_DIR, cache_file.replace(" ", "_") + ".json")
        with open(cache_path, "w") as f:
            json.dump(all_episodes, f)

    return all_episodes


def parse_seasons(episodes, show_name=""):
    """Parse episodes and group by season."""
    seasons = {}
    no_season_episodes = []

    for episode in episodes:
        match = re.search(
            r"sez(?:onul|on|\\.)\\s*(\\d+)", episode["title"], re.IGNORECASE
        )
        if match:
            season_num = int(match.group(1))
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
    iframes = soup.find_all("iframe", attrs={"data-lazy-src": True})

    for iframe in iframes:
        video_url = iframe["data-lazy-src"]

        if "player3.funny-cats.org" in video_url:
            continue

        if video_url.startswith("//"):
            video_url = "https:" + video_url

        domain = urllib.parse.urlparse(video_url).netloc.replace("www.", "")
        sources.append({"url": video_url, "domain": domain})

    return sources


def search(query):
    """Search veziaici.net for content."""
    search_url = f"{BASE_URL_VEZIAICI}?s={urllib.parse.quote_plus(query)}"
    results = []

    try:
        response = get_html_content(search_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch search results: {e}")
        return results

    for item in soup.select("div.rb-p20-gutter.rb-col-m12.rb-col-t4"):
        title_element = item.select_one("h3.entry-title a.p-url")
        if title_element:
            title = title_element.get("title")
            item_url = title_element.get("href")
            if title and item_url:
                results.append({"title": title, "url": item_url})

    return results


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
