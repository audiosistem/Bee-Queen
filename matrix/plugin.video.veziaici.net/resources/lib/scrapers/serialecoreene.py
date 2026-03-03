"""Scraper for serialecoreene.org."""

import re
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
            "url": f"{BASE_URL_SERIALECOREENE}series/",
            "mode": "list_serialecoreene_all_series",
        },
        {
            "title": "Seriale Coreene",
            "url": f"{BASE_URL_SERIALECOREENE}genre/seriale-coreene/",
            "mode": "list_serialecoreene_korean_series",
        },
        {
            "title": "Seriale Thailandeze",
            "url": f"{BASE_URL_SERIALECOREENE}genre/thailanda/",
            "mode": "list_serialecoreene_thai_series",
        },
        {
            "title": "Episoade Noi",
            "url": f"{BASE_URL_SERIALECOREENE}episode/",
            "mode": "list_serialecoreene_new_episodes",
        },
    ]
    return menu


def get_series_list(url, page="1"):
    """Get list of series from a category."""
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    series = []
    next_page = None

    try:
        response = get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch series list: {e}")
        return series, next_page

    container = soup.find("div", class_="movies-list movies-list-full")
    if not container:
        return series, next_page

    for item in container.find_all("div", class_="ml-item"):
        link_element = item.find("a", class_="ml-mask")
        img_element = item.find("img", class_="mli-thumb")
        title_element = item.find("h2")

        if link_element and img_element and title_element:
            series_url = link_element["href"]
            title = title_element.text.strip()
            thumb = img_element.get("data-original", img_element.get("src", ""))

            series.append(
                {
                    "title": title,
                    "url": series_url,
                    "thumb": thumb,
                }
            )

    # Pagination
    next_page_link = soup.find(
        "a", class_="page larger", rel="nofollow", string=str(int(page) + 1)
    )
    if next_page_link and next_page_link.has_attr("href"):
        next_page = str(int(page) + 1)

    return series, next_page


def get_new_episodes(url, page="1"):
    """Get new episodes list."""
    page_url = f"{url}page/{page}/" if int(page) > 1 else url
    episodes = []
    next_page = None

    try:
        response = get_html_content(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch new episodes: {e}")
        return episodes, next_page

    container = soup.find("div", class_="movies-list movies-list-full")
    if not container:
        return episodes, next_page

    for item in container.find_all("div", class_="ml-item"):
        link_element = item.find("a", class_="ml-mask")
        img_element = item.find("img", class_="mli-thumb")
        title_element = item.find("h2")

        if link_element and img_element and title_element:
            episode_url = link_element["href"]
            title = title_element.text.strip()
            thumb = img_element.get("data-original", img_element.get("src", ""))

            episodes.append(
                {
                    "title": title,
                    "url": episode_url,
                    "thumb": thumb,
                }
            )

    # Pagination
    next_page_link = soup.find(
        "a", class_="page larger", rel="nofollow", string=str(int(page) + 1)
    )
    if next_page_link and next_page_link.has_attr("href"):
        next_page = str(int(page) + 1)

    return episodes, next_page


def get_episodes_and_sources(url):
    """Get episodes and sources from a series page."""
    try:
        response = get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch episode page: {e}")
        return []

    episodes = []
    seasons_container = soup.find("div", id="seasons")

    if not seasons_container:
        return episodes

    for season_div in seasons_container.find_all("div", class_="tvseason"):
        season_title_element = season_div.find("strong")
        if not season_title_element:
            continue

        season_title = season_title_element.text.strip()

        for episode_link in season_div.find_all("a", href=True):
            episode_url = episode_link["href"]
            episode_name = episode_link.text.strip()
            display_title = f"{season_title} - {episode_name}"

            episodes.append(
                {
                    "title": display_title,
                    "url": episode_url,
                }
            )

    return episodes


def extract_js_redirect_param(html_content, func_name):
    """Extract redirect parameter from JavaScript function."""
    func_pattern = rf'function\s+{re.escape(func_name)}\s*\(\)\s*\{{\s*window\.location\.href\s*=\s*"([^"]+)"\s*;\s*\}}'
    match = re.search(func_pattern, html_content)
    if match:
        return match.group(1)
    return None


def get_playable_url(episode_url):
    """Get playable video URL from episode page (handles redirects)."""
    try:
        # Step 1: Fetch the episode page
        response1 = get_html_content(episode_url)
        response1.raise_for_status()
        soup1 = BeautifulSoup(response1.text, "html.parser")

        # Find the href from #iframeload
        iframe_load_link = soup1.find("a", id="iframeload")
        if not iframe_load_link or "href" not in iframe_load_link.attrs:
            log_error("iframeload link not found")
            return None

        target_div_id = iframe_load_link["href"].lstrip("#")
        target_div = soup1.find("div", id=target_div_id)

        if not target_div:
            log_error("Target div not found")
            return None

        # Extract onclick function from #buttonx
        button_x = target_div.find("a", id="buttonx")
        if not button_x or "onclick" not in button_x.attrs:
            log_error("buttonx not found")
            return None

        onclick_func = button_x["onclick"].replace("()", "")
        redirect_param1 = extract_js_redirect_param(response1.text, onclick_func)

        if not redirect_param1:
            log_error("Failed to extract first redirect param")
            return None

        first_redirect_url = urllib.parse.urljoin(episode_url, redirect_param1)

        # Step 2: Fetch the first redirect page
        response2 = get_html_content(first_redirect_url)
        response2.raise_for_status()

        # Find the onclick for the second redirect
        rdrtnow_match = re.search(
            r'onclick=\\?["\']([a-zA-Z0-9_]+)\(\)\\?["\']', response2.text
        )

        if not rdrtnow_match:
            log_error("Second redirect button not found")
            return None

        rdrtnow_func = rdrtnow_match.group(1)
        redirect_param2 = extract_js_redirect_param(response2.text, rdrtnow_func)

        if not redirect_param2:
            log_error("Failed to extract second redirect param")
            return None

        final_page_url = urllib.parse.urljoin(episode_url, redirect_param2)

        # Step 3: Fetch the final page and find the iframe src
        response3 = get_html_content(final_page_url)
        response3.raise_for_status()
        soup3 = BeautifulSoup(response3.text, "html.parser")

        final_iframe = soup3.find("iframe", src=True)
        if not final_iframe:
            log_error("Final iframe not found")
            return None

        video_url = final_iframe["src"]
        if video_url.startswith("//"):
            video_url = "https:" + video_url

        return video_url

    except Exception as e:
        log_error(f"Error getting playable URL: {e}")
        return None
