"""Scraper for blogul-lui-atanase.ro (Korean/Asian series and movies)."""

import re
import urllib.parse
from bs4 import BeautifulSoup
from resources.lib.utils import get_html_content, log, log_error, BASE_URL_BLOGUL


def get_korean_categories():
    """Get Korean series categories."""
    # Nota: "Dupa Ani" este adaugat hardcodat in addon.py -> nu il includem aici
    categories = [
        {
            "title": "Seriale Coreene de Familie",
            "url": f"{BASE_URL_BLOGUL}categorie/seriale-coreene-de-familie-50-ep/",
        },
        {
            "title": "Seriale Coreene Contemporane",
            "url": f"{BASE_URL_BLOGUL}categorie/seriale-coreene-contemporane/",
        },
        {
            "title": "Seriale Coreene Istorice",
            "url": f"{BASE_URL_BLOGUL}categorie/seriale-coreene-istorice/",
        },
        {
            "title": "Mini-Seriale Coreene",
            "url": f"{BASE_URL_BLOGUL}categorie/miniseriale-coreene/",
        },
    ]
    return categories


def get_years():
    """Get Korean series years from menu."""
    years = []

    try:
        response = get_html_content(BASE_URL_BLOGUL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        menu_item = soup.find("li", id="menu-item-15749")
        if menu_item:
            sub_menu = menu_item.find("ul", class_="sub-menu")
            if sub_menu:
                for item in sub_menu.find_all("li"):
                    link = item.find("a")
                    if link and link.has_attr("href"):
                        title = link.text.strip()
                        url = link["href"]
                        years.append({"title": title, "url": url})

    except Exception as e:
        log_error(f"Failed to fetch years: {e}")

    return years


def get_series_list(url, page="1"):
    """Get list of series from a category with optimized parallel loading."""
    from resources.lib.utils import parallel_map
    
    # If we are on first page, let's pre-load page 2 in parallel for speed if user navigates next
    # For now, let's just optimize single page fetching with cache
    if int(page) > 1:
        # Avoid appending /page/x/ if it's already a search URL with /page/x/?s=...
        if "?s=" in url and "/page/" in url:
            page_url = url
        else:
            # Handle both slash-ended and non-slash-ended URLs
            base = url.rstrip('/')
            page_url = f"{base}/page/{page}/"
    else:
        page_url = url
    series = []
    next_page = None

    try:
        response = get_html_content(page_url, cache_time=3600)
        if response.status_code != 200:
            return series, next_page
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch series: {e}")
        return series, next_page

    items = soup.find_all("div", class_="post-col")
    if not items:
        items = soup.find_all("article")

    for item in items:
        title_h2 = item.find(["h2", "h3"], class_=["entry-title", "post-title", "cm-entry-title"])
        thumb_figure = item.find("figure", class_="post-featured-image")
        thumb_div = item.find("div", class_=["post-thumb", "cm-featured-image"])
        description_div = item.find("div", class_=["entry-content", "cm-entry-summary", "post-content"])

        if not title_h2:
            # Last ditch effort: find any link that looks like a title
            title_h2 = item.find("a", rel="bookmark")

        if title_h2:
            title_link = title_h2 if title_h2.name == "a" else title_h2.find("a")
            if title_link:
                series_url = title_link["href"]
                title = title_link.get("title") or title_link.text.strip()

                thumb = ""
                # Priority 1: Figure with background style
                if thumb_figure:
                    a_thumb = thumb_figure.find("a", class_="mnp-post-image")
                    if a_thumb and "style" in a_thumb.attrs:
                        style = a_thumb["style"]
                        match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style)
                        if match:
                            thumb = match.group(1)
                
                # Priority 2: Direct img inside figure or div
                if not thumb:
                    container = thumb_figure or thumb_div or item
                    img = container.find("img")
                    if img:
                        thumb = img.get("data-src") or img.get("src") or img.get("data-lazy-src", "")

                description = description_div.text.strip() if description_div else ""

                series.append(
                    {
                        "title": title,
                        "url": series_url,
                        "thumb": thumb,
                        "description": description,
                    }
                )

    # Pagination
    next_page_link = None
    pagination = soup.find("div", id="post-navigator")
    if pagination:
        current_page_span = pagination.find("span", class_="current")
        if current_page_span:
            next_page_link = current_page_span.find_next_sibling("a")

    if not next_page_link:
        next_page_link = soup.find("a", class_="next page-numbers")

    if next_page_link and next_page_link.has_attr("href"):
        next_page = str(int(page) + 1)

    return series, next_page


def search(query, page="1"):
    """Search blogul-lui-atanase.ro for content."""
    # WordPress search URL format
    search_url = f"{BASE_URL_BLOGUL}?s={urllib.parse.quote_plus(query)}"
    
    # If a page is requested, WordPress uses /page/X/?s=query
    if page and int(page) > 1:
        search_url = f"{BASE_URL_BLOGUL}page/{page}/?s={urllib.parse.quote_plus(query)}"
        
    return get_series_list(search_url, page=page)


def get_episodes_and_sources(url, show_name=""):
    """Get episodes and sources from a series page."""
    try:
        response = get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch episode page: {e}")
        return [], []

    content = soup.find("div", class_="entry-content")
    if not content:
        content = soup.find("div", class_="cm-entry-summary")
    if not content:
        content = soup.find("article")

    if not content:
        return [], []

    # Check for season headers
    season_headers = content.find_all(
        ["h2", "h3", "h4"], string=re.compile(r"SEZONUL", re.IGNORECASE)
    )

    if season_headers:
        seasons = []
        for header in season_headers:
            seasons.append({"title": header.text.strip(), "header": header})
        return seasons, []

    # Parse episodes without seasons
    episodes = []
    all_links = content.find_all("a", href=True)

    # Check for direct episode links
    for link in all_links:
        link_text = link.text.strip()
        if re.search(r"ep(?:isodul|\.|\s*)?\s*\d+", link_text, re.IGNORECASE):
            episodes.append(
                {
                    "title": link_text,
                    "url": link["href"],
                    "type": "link",
                }
            )

    # If no direct links, parse iframe-based structure
    if not episodes:
        current_episode_title = ""
        for node in content.descendants:
            if node.name == "iframe":
                if current_episode_title:
                    video_url = (
                        node.get("src")
                        or node.get("data-src")
                        or node.get("data-lazy-src")
                    )
                    if video_url and video_url != "about:blank":
                        if video_url.startswith("//"):
                            video_url = "https:" + video_url
                        episodes.append(
                            {
                                "title": current_episode_title,
                                "url": video_url,
                                "type": "iframe",
                            }
                        )
            elif node.name == "a" and current_episode_title:
                source_url = node.get("href")
                if source_url:
                    source_name = node.text.strip()
                    if source_name and "episodul" not in source_name.lower():
                        if episodes and episodes[-1]["url"] == source_url:
                            prev_name = episodes[-1]["title"].replace(f"{current_episode_title} - ", "")
                            episodes[-1]["title"] = f"{current_episode_title} - {prev_name}{source_name}"
                        else:
                            episodes.append(
                                {
                                    "title": f"{current_episode_title} - {source_name}",
                                    "url": source_url,
                                    "type": "link",
                                }
                            )
            elif isinstance(node, str):
                text_val = node.strip()
                if text_val and (
                    "episodul" in text_val.lower() or "episod" in text_val.lower()
                ):
                    if len(text_val) < 50:
                        parts = re.split(r"–|-", text_val)
                        if parts:
                            current_episode_title = parts[0].strip()

    return [], episodes


def get_season_episodes(url, season_title, show_name=""):
    """Get episodes for a specific season."""
    try:
        response = get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch season page: {e}")
        return []

    content = soup.find("div", class_="entry-content")
    if not content:
        content = soup.find("div", class_="cm-entry-summary")
    if not content:
        content = soup.find("article")

    if not content:
        return []

    start_element = content.find(
        ["h2", "h3", "h4"], string=re.compile(season_title, re.IGNORECASE)
    )
    if not start_element:
        return []

    episodes = []
    current_episode_title = ""

    # Get elements within this season
    elements_in_season = []
    for element in start_element.find_next_siblings():
        if element.name in ["h2", "h3", "h4"] and "SEZONUL" in element.text.upper():
            break
        elements_in_season.append(element)

    for element_container in elements_in_season:
        for node in element_container.descendants:
            if node.name == "iframe":
                if current_episode_title:
                    video_url = (
                        node.get("src")
                        or node.get("data-src")
                        or node.get("data-lazy-src")
                    )
                    if video_url and video_url != "about:blank":
                        if video_url.startswith("//"):
                            video_url = "https:" + video_url
                        domain = urllib.parse.urlparse(video_url).netloc.replace(
                            "www.", ""
                        )
                        episodes.append(
                            {
                                "title": f"{current_episode_title} - {domain}",
                                "url": video_url,
                            }
                        )
            elif node.name == "a" and current_episode_title:
                source_url = node.get("href")
                if source_url:
                    source_name = node.text.strip()
                    if source_name and "episodul" not in source_name.lower():
                        if episodes and episodes[-1]["url"] == source_url:
                            prev_name = episodes[-1]["title"].replace(f"{current_episode_title} - ", "")
                            episodes[-1]["title"] = f"{current_episode_title} - {prev_name}{source_name}"
                        else:
                            episodes.append(
                                {
                                    "title": f"{current_episode_title} - {source_name}",
                                    "url": source_url,
                                }
                            )
            elif isinstance(node, str):
                text_val = node.strip()
                if text_val and (
                    "episodul" in text_val.lower() or "episod" in text_val.lower()
                ):
                    if len(text_val) < 50:
                        parts = re.split(r"–|-", text_val)
                        if parts:
                            current_episode_title = parts[0].strip()

    return episodes


def get_movie_sources(url):
    """Get sources from a movie page."""
    supported_hosts = [
        "netu.ac", "vidmoly", "waaw", "streamtape", "ok.ru",
        "uqload", "vk.com", "vkvideo", "sibnet.ru", "my.mail.ru",
        "filemoon", "hqq",
    ]
    if any(host in url for host in supported_hosts):
        domain = urllib.parse.urlparse(url).netloc.replace("www.", "")
        return [{"url": url, "domain": domain}]

    try:
        response = get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch movie page: {e}")
        return []

    sources = []

    # Find sources in <a> tags
    for a_tag in soup.find_all("a", href=True):
        video_url = a_tag["href"]
        if video_url.startswith("//"):
            video_url = "https:" + video_url

        supported_hosts = [
            "netu.ac",
            "vidmoly",
            "waaw",
            "streamtape",
            "ok.ru",
            "uqload",
            "vk.com",
            "vkvideo",
            "sibnet.ru",
            "my.mail.ru",
            "filemoon",
            "hqq",
        ]

        if any(host in video_url for host in supported_hosts):
            domain = urllib.parse.urlparse(video_url).netloc.replace("www.", "")
            sources.append({"url": video_url, "domain": domain})

    # Find sources in <iframe> tags
    for iframe in soup.find_all("iframe"):
        if iframe.has_attr("src"):
            video_url = iframe["src"]
            if video_url.startswith("//"):
                video_url = "https:" + video_url

            domain = urllib.parse.urlparse(video_url).netloc.replace("www.", "")
            sources.append({"url": video_url, "domain": domain, "referer": url})

    return sources
