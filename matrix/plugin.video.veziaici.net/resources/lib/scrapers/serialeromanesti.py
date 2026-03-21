"""Scraper for serialeromanesti.net."""

import re
import urllib.parse
from bs4 import BeautifulSoup
from resources.lib.utils import (
    get_html_content,
    log,
    log_error,
)

BASE_URL_SERIALEROMANESTI = "https://serialeromanesti.net"


def get_menu():
    """Get main categories."""
    menu = [
        {"title": "Seriale Romanesti", "url": f"{BASE_URL_SERIALEROMANESTI}/seriale-romanesti-online-sezoane-si-episoade-integrale/"},
        {"title": "Emisiuni Romanesti", "url": f"{BASE_URL_SERIALEROMANESTI}/emisiuni-romanesti-online-sezoane-si-episoade-integrale/"},
    ]
    return menu


def get_series_list(url, page="1", target_count=12):
    """Get list of posts from category or search, concatenating pages until target_count is met."""
    series = []
    current_page = int(page)
    next_page = None
    seen_urls = set()

    # Check if it's an index page (directory listing) - these don't paginate usually
    if "online-sezoane-si-episoade-integrale" in url:
        try:
            response = get_html_content(url, cache_time=3600)
            if response.status_code != 200:
                return [], None
            soup = BeautifulSoup(response.text, "html.parser")
            content = soup.find("div", class_="entry-content")
            if content:
                # We iterate through children to maintain context of which season belongs to which show
                current_show_name = "Serial"
                current_show_thumb = ""
                
                # Find all links but try to group them
                links = content.find_all("a", href=True)
                seen_urls = set()
                
                for a in links:
                    href = a.get('href')
                    if not href or href == url or href in seen_urls or "#" in href:
                        continue
                    
                    if any(x in href.lower() for x in ["/terms-", "/privacy-", "/dmca-", "/contact-", "/disclaimer-"]):
                        continue
                    
                    text = a.get_text(strip=True)
                    img = a.find("img")
                    
                    is_season = any(kw in text.upper() for kw in ["SEZONUL", "SEZON", "EPISOADE"])
                    
                    if img:
                        # This is the main show entry (usually has an image)
                        title = img.get("alt") or text
                        # Clean up common suffixes
                        title = re.sub(r' (sezonul|online|serial|emisiune|episoade).*', '', title, flags=re.IGNORECASE).strip()
                        current_show_name = title
                        current_show_thumb = img.get("data-src") or img.get("src") or img.get("data-lazy-src")
                        
                        series.append({
                            "title": title.upper(),
                            "url": href,
                            "thumb": current_show_thumb,
                            "is_main": True
                        })
                        seen_urls.add(href)
                    elif text:
                        if is_season:
                            # It's a season link. We only add it if it's not pointing to the same place as the main show
                            # and we rename it for clarity: "SHOW NAME - Sezon 1"
                            display_title = f"{current_show_name} - {text}"
                            series.append({
                                "title": display_title,
                                "url": href,
                                "thumb": current_show_thumb
                            })
                            seen_urls.add(href)
                        else:
                            # It's a text link that might be a new show name
                            # If it's the same as current_show_name, it's just a duplicate text link
                            if text.upper() == current_show_name.upper():
                                continue
                            
                            # Otherwise treat as a potential show
                            series.append({
                                "title": text.upper(),
                                "url": href,
                                "thumb": current_show_thumb # Carry over thumb if it looks related
                            })
                            seen_urls.add(href)
                            current_show_name = text
            return series, None
        except Exception as e:
            log_error(f"Failed to fetch index page: {e}")
            return [], None

    # For categories and search, concatenate pages
    while len(series) < target_count:
        if current_page > 1:
            if "?s=" in url:
                if "&paged=" in url:
                    page_url = re.sub(r"&paged=\d+", f"&paged={current_page}", url)
                else:
                    page_url = f"{url}&paged={current_page}"
            else:
                base = url.rstrip('/')
                page_url = f"{base}/page/{current_page}/"
        else:
            page_url = url

        try:
            response = get_html_content(page_url, cache_time=3600)
            if response.status_code != 200:
                break
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            log_error(f"Failed to fetch page {current_page}: {e}")
            break

        # Find entry titles strictly in the main content area to avoid widgets
        main_area = soup.select_one(".rbc-content, .site-main, #content")
        if not main_area:
            main_area = soup # Fallback
            
        entries = main_area.select(".entry-title")
        
        found_on_page = 0
        for entry in entries:
            # Verify entry is NOT inside a widget even if main_area selector was broad
            is_in_widget = False
            curr = entry
            while curr and curr != main_area:
                if curr.get('class') and any(c for c in curr.get('class') if 'widget' in c.lower()):
                    is_in_widget = True
                    break
                curr = curr.parent
            if is_in_widget:
                continue

            link = entry.find("a")
            if link:
                title = link.get("title") or link.text.strip()
                item_url = link.get("href")
                if title and item_url and item_url not in seen_urls:
                    # Find closest thumbnail
                    thumb = ""
                    container = entry.find_parent("article") or entry.find_parent("div", class_=re.compile(r"p-wrap|post"))
                    if container:
                        img = container.find("img")
                        if img:
                            thumb = img.get("data-src") or img.get("src") or img.get("data-lazy-src", "")
                    
                    series.append({"title": title, "url": item_url, "thumb": thumb})
                    seen_urls.add(item_url)
                    found_on_page += 1

        if found_on_page == 0:
            break

        # Check for next page link to see if more exists
        next_link = soup.find("a", class_="next page-numbers")
        if not next_link:
            pagination = soup.find("div", class_="pagination") or soup.find(class_="nav-links")
            if pagination:
                next_link = pagination.find("a", class_="next")
        
        if next_link:
            current_page += 1
            next_page = str(current_page)
        else:
            next_page = None
            break

    return series, next_page


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
        
    # Check JS switches just in case
    scripts = soup.find_all("script")
    for s in scripts:
        if s.string and "switch" in s.string and "case" in s.string and 'src =' in s.string:
            matches = re.finditer(r'case\s+\d+:\s*src\s*=\s*["\']([^"\']+)["\']', s.string)
            for match in matches:
                src = match.group(1)
                if src:
                    if src.startswith("//"):
                        src = "https:" + src
                    if src not in seen_urls:
                        domain = urllib.parse.urlparse(src).netloc.replace("www.", "")
                        sources.append({"url": src, "domain": domain, "referer": url})
                        seen_urls.add(src)

    return sources


def search(query, page="1"):
    """Search serialeromanesti.net for content."""
    search_url = f"{BASE_URL_SERIALEROMANESTI}/?s={urllib.parse.quote_plus(query)}"
    return get_series_list(search_url, page=page)
