"""Scraper for terasacucartii.net (Turkish series)."""

import re
import urllib.parse
from bs4 import BeautifulSoup
from resources.lib.utils import get_html_content, log, log_error, BASE_URL_TERASA


def get_categories():
    """Get categories from terasacucartii.net dropdown with caching."""
    categories = []

    try:
        response = get_html_content(BASE_URL_TERASA, cache_time=86400)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")

        select = soup.find("select", {"id": "cat"})

        if select:
            for option in select.find_all("option"):
                value = option.get("value")
                label = option.get_text(strip=True)

                if value and value != "-1" and label:
                    category_url = f"{BASE_URL_TERASA}/?cat={value}"
                    categories.append({"title": label, "url": category_url})

    except Exception as e:
        log_error(f"Error fetching categories: {e}")

    return categories


def get_series_list(url, page="1"):
    """Get list of series/episodes from category with caching."""
    page_url = url if page == "1" else f"{url}&paged={page}"
    episodes = []
    next_page = None

    try:
        response = get_html_content(page_url, cache_time=3600)
        if response.status_code != 200:
            return episodes, next_page
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch Turkish series: {e}")
        return episodes, next_page

    # Parse episodes from article elements
    for article in soup.find_all("article", class_="item-list"):
        title_link = article.find("h2", class_="post-box-title")
        if not title_link:
            title_link = article.find("a", class_="post-box-title")

        if title_link:
            link = title_link.find("a") or title_link
            if link and "href" in link.attrs:
                episode_url = link["href"]
                title = link.get_text(strip=True)

                thumb = ""
                thumb_link = article.find("div", class_="post-thumbnail")
                if thumb_link:
                    img = thumb_link.find("img")
                    if img and "src" in img.attrs:
                        thumb = img["src"]

                if episode_url and title:
                    episodes.append(
                        {"title": title, "url": episode_url, "thumb": thumb}
                    )

    # Check for pagination
    next_link = soup.find("a", class_="next page-numbers")
    if not next_link:
        pagination = soup.find("div", class_="pagination")
        if pagination:
            # Check for standard next link
            next_link = pagination.find("a", class_="next")
            
            # Check for tie-next-page span (used on search results)
            if not next_link:
                tie_next = pagination.find("span", id="tie-next-page")
                if tie_next:
                    next_link = tie_next.find("a")
            
            # Check for current page sibling
            if not next_link:
                current_span = pagination.find("span", class_="current")
                if current_span:
                    next_link = current_span.find_next_sibling("a")

    if next_link and next_link.has_attr("href"):
        next_page = str(int(page) + 1)

    return episodes, next_page


def search(query, page="1"):
    """Search terasacucartii.net for content."""
    search_url = f"{BASE_URL_TERASA}/?s={urllib.parse.quote_plus(query)}"
    return get_series_list(search_url, page=page)


def get_sources(url):
    """Get video sources from a Turkish episode page."""
    try:
        response = get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch source page: {e}")
        return []

    sources_found = []

    # Method 1: Look for iframes in h1 headers
    h1_headers = soup.find_all("h1")

    for h1 in h1_headers:
        h1_text = h1.get_text()
        if "sursa" in h1_text.lower():
            next_elem = h1.find_next_sibling()
            while next_elem:
                if next_elem.name == "h1":
                    break
                if next_elem.name == "iframe" and "src" in next_elem.attrs:
                    video_url = next_elem["src"]
                    if video_url.startswith("//"):
                        video_url = "https:" + video_url
                    if video_url and video_url not in sources_found:
                        sources_found.append(video_url)
                elif next_elem.name and next_elem.name not in ["h1", "script", "style"]:
                    iframes = next_elem.find_all("iframe")
                    for iframe in iframes:
                        if "src" in iframe.attrs:
                            video_url = iframe["src"]
                            if video_url.startswith("//"):
                                video_url = "https:" + video_url
                            if video_url and video_url not in sources_found:
                                sources_found.append(video_url)
                next_elem = next_elem.find_next_sibling()

    # Method 2: Find all iframes on the page
    if not sources_found:
        all_iframes = soup.find_all("iframe")
        for iframe in all_iframes:
            if "src" in iframe.attrs:
                video_url = iframe["src"]
                if video_url.startswith("//"):
                    video_url = "https:" + video_url
                if video_url and "player3.funny-cats.org" not in video_url:
                    if video_url not in sources_found:
                        sources_found.append(video_url)

    # Method 3: Look for data-encoded iframes
    if not sources_found:
        import base64

        iframe_placeholders = soup.find_all("div", class_="iframe-placeholder")
        for placeholder in iframe_placeholders:
            if "data-encoded" in placeholder.attrs:
                encoded_iframe = placeholder["data-encoded"]
                try:
                    decoded_iframe = base64.b64decode(encoded_iframe).decode("utf-8")
                    src_match = re.search(r'src="([^"]+)"', decoded_iframe)
                    if src_match:
                        video_url = src_match.group(1)
                        if video_url.startswith("//"):
                            video_url = "https:" + video_url
                        if video_url and video_url not in sources_found:
                            sources_found.append(video_url)
                except Exception:
                    continue

    # Method 4: Look for videoembed URLs
    if not sources_found:
        videoembed_links = soup.find_all("a", href=lambda x: x and "videoembed" in x)
        for link in videoembed_links:
            video_url = link.get("href")
            if video_url and video_url not in sources_found:
                sources_found.append(video_url)

    # Filter unsupported domains
    # Nota: vidmoly si filemoon au resolveri dedicati in plugin -> nu le filtram
    unsupported_domains = ["streamtape", "doodstream"]
    filtered_sources = []

    for video_url in sources_found:
        domain = urllib.parse.urlparse(video_url).netloc.replace("www.", "")
        if not any(
            unsupported in domain.lower() for unsupported in unsupported_domains
        ):
            filtered_sources.append({"url": video_url, "domain": domain, "referer": url})

    return filtered_sources
