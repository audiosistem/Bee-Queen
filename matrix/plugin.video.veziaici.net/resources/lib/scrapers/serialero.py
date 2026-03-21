"""Scraper for serialero.net."""

import re
import urllib.parse
from bs4 import BeautifulSoup
from resources.lib.utils import get_html_content, log, log_error

BASE_URL = "https://serialero.net"

def get_menu():
    """Get main menu for serialero.net."""
    # Based on HTML in New Text Document.txt
    menu = [
        {"title": "Toate Seriale", "url": f"{BASE_URL}/genre-tv/tvshows"},
        {"title": "Seriale Românești", "url": f"{BASE_URL}/gen-seriale/seriale"},
        {"title": "Seriale Turcești", "url": f"{BASE_URL}/genre-tv/turkey"},
        {"title": "Seriale Spaniole", "url": f"{BASE_URL}/genre-tv/spain"},
        {"title": "Seriale Coreene", "url": f"{BASE_URL}/genre-tv/korea"},
        {"title": "Seriale Chinezești", "url": f"{BASE_URL}/genre-tv/china"},
        {"title": "Seriale Indiene", "url": f"{BASE_URL}/genre-tv/india"},
        {"title": "Toate Filme", "url": f"{BASE_URL}/genre-movies/movies"},
        {"title": "Filme Românești", "url": f"{BASE_URL}/gen-filme/filme"},
        {"title": "Episoade Noi", "url": f"{BASE_URL}/episodes"},
        {"title": "Desene", "url": f"{BASE_URL}/genre/desene-animate"},
        {"title": "Dublate", "url": f"{BASE_URL}/genre/dublate"},
    ]
    return menu

def get_series_list(url, page="1"):
    """Get list of series from a category."""
    if page and int(page) > 1:
        # Check if URL already has query params
        if "?" in url:
            page_url = f"{url}&page={page}"
        else:
            page_url = f"{url}?page={page}"
    else:
        page_url = url
        
    series = []
    next_page = None

    try:
        response = get_html_content(page_url)
        if response.status_code != 200:
            return series, next_page
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch series list: {e}")
        return series, next_page

    items = soup.find_all("div", class_="package-item")
    if not items:
        # Fallback for other page structures
        items = soup.find_all("div", class_=re.compile(r"col-"))

    for item in items:
        link_tag = item.find_parent("a") or item.find("a")
        if not link_tag:
            continue
            
        href = link_tag.get("href", "")
        if not href:
            continue
            
        if href.startswith("../"):
            series_url = f"{BASE_URL}/{href.replace('../', '')}"
        elif href.startswith("/"):
            series_url = f"{BASE_URL}{href}"
        elif not href.startswith("http"):
            series_url = f"{BASE_URL}/{href}"
        else:
            series_url = href

        img_tag = item.find("img")
        thumb = img_tag.get("src", "") if img_tag else ""
        
        # Extract title, year, genre from hvrbox-text
        title = ""
        year = ""
        genre = ""
        
        title_h5 = item.find("h5")
        if title_h5:
            title = title_h5.text.strip()
            
        hvr_text = item.find("div", class_="hvrbox-text")
        if hvr_text:
            h3 = hvr_text.find("h3")
            if h3:
                title = h3.text.strip()
            
            # Find "An: 2017"
            year_match = re.search(r"An[:\s]+(\d+)", hvr_text.text)
            if year_match:
                year = year_match.group(1)
                
            # Find "Gen: Comedie"
            genre_match = re.search(r"Gen[:\s]+([^<\n]+)", hvr_text.text)
            if genre_match:
                genre = genre_match.group(1).strip()

        if title:
            display_title = title
            if year:
                display_title += f" ({year})"
            
            series.append({
                "title": display_title,
                "url": series_url,
                "thumb": thumb,
                "description": f"Gen: {genre}" if genre else "",
                "is_movie": "/film-online/" in series_url
            })

    # Pagination
    paginations = soup.find_all(class_=re.compile(r"pagination"))
    for pagination in paginations:
        # Standard Bootstrap pagination with li.active
        current_li = pagination.find("li", class_="active")
        if current_li:
            next_li = current_li.find_next_sibling("li")
            if next_li and next_li.find("a"):
                next_page = str(int(page) + 1)
                break
                
        # Simple a-tag based pagination (like paginationbot)
        # Find the anchor that is currently active or matching current page
        active_a = pagination.find("a", class_="active")
        if not active_a:
            # Fallback: find by text matching current page
            active_a = pagination.find("a", string=str(page))
        
        if active_a:
            next_a = active_a.find_next_sibling("a")
            if next_a and next_a.get("href"):
                href = next_a.get("href")
                page_match = re.search(r"page=(\d+)", href)
                if page_match:
                    next_page = page_match.group(1)
                    break

    return series, next_page

def search(query, page="1"):
    """Search serialero.net for content."""
    search_url = f"{BASE_URL}/cautare.php?search={urllib.parse.quote_plus(query)}"
    
    # Check if page is provided and not 1, append it.
    # On cautare.php, the pagination param is usually page=X
    if page and int(page) > 1:
        search_url = f"{search_url}&page={page}"
        
    return get_series_list(search_url, page=page)

def get_seasons_and_episodes(url, force_episodes=False):
    """Get seasons and episodes from a series page."""
    try:
        response = get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch series page: {e}")
        return [], []

    # 1. Check for seasons via explicit links (like Sezonul 1, Sezonul 2)
    # Sometimes serialero links to different pages for different seasons
    seasons = []
    season_links = soup.find_all("a", href=True)
    seen_seasons = set()
    
    # Try to find a container with season links, usually class 'pagiseasons' or similar
    # or just look for links containing the series slug but ending in -s[number]
    url_base = url.split('/')[-1].rsplit('-s', 1)[0] # Extract 'ai-nostri' from 'ai-nostri-s1'
    
    for link in season_links:
        href = link.get("href")
        text = link.text.strip()
        
        # Check if it looks like a season link
        if ("sezonul" in text.lower() or "season" in text.lower()) and url_base in href:
            if not href.startswith("http"):
                href = f"{BASE_URL}/seriale-online/{href.lstrip('/')}" if "seriale-online" not in href else f"{BASE_URL}/{href.lstrip('/')}"
            
            if href not in seen_seasons:
                seasons.append({
                    "title": text,
                    "url": href,
                    "id": href  # Using URL as ID for these linked seasons
                })
                seen_seasons.add(href)
    
    # If we found separate pages for seasons, return them to be handled by Kodi folders
    # Unless there's only 1 season, then we can just show its episodes directly
    # ALSO, if force_episodes is True, we skip returning seasons and jump straight to scraping episodes from THIS page.
    if len(seasons) > 1 and not force_episodes:
        # Sort seasons by title (Sezonul 1, Sezonul 2, etc.)
        try:
            seasons.sort(key=lambda x: int(re.search(r'\d+', x["title"]).group()) if re.search(r'\d+', x["title"]) else 0)
        except:
            pass
        return seasons, []

    # 2. Check for JS array-based episodes (common on serialero for direct links)
    episodes = []
    scripts = soup.find_all("script")
    js_urls = []
    for s in scripts:
        if s.string and 'function change(id)' in s.string:
            match = re.search(r'var\s+\w+\s*=\s*\[(.*?)\];', s.string, re.DOTALL)
            if match:
                urls_text = match.group(1)
                parts = urls_text.split(',')
                for p in parts:
                    cleaned = p.strip()
                    if cleaned and (cleaned.startswith('"') or cleaned.startswith("'")):
                        js_urls.append(cleaned.strip('"\''))
            break

    if js_urls:
        ep_links = soup.find_all("a", href="#vidbox")
        for ep in ep_links:
            ep_id = ep.get("id")
            if ep_id and ep_id.isdigit():
                idx = int(ep_id) - 1
                if 0 <= idx < len(js_urls):
                    title = ep.text.strip()
                    ep_url = js_urls[idx]
                    if ep_url.startswith("../"):
                        ep_url = f"{BASE_URL}/{ep_url.replace('../', '')}"
                    elif ep_url.startswith("/"):
                        ep_url = f"{BASE_URL}{ep_url}"
                    elif not ep_url.startswith("http"):
                        ep_url = f"{BASE_URL}/{ep_url}"
                        
                    # Skip 'Error!' links
                    if "Error" not in ep_url:
                        episodes.append({
                            "title": title,
                            "url": ep_url
                        })
        if episodes:
            return [], episodes

    # 3. Check for seasons tabs/divs on the same page
    season_tabs = soup.find_all("a", class_="nav-link", id=re.compile(r"tab-\d+"))
    if season_tabs and not force_episodes:
        for tab in season_tabs:
            title = tab.text.strip()
            seasons.append({
                "title": title,
                "id": tab.get("id", "").replace("tab-", "")
            })
        return seasons, []

    # 4. If no seasons and no JS, look for episodes directly
    ep_links = soup.find_all("a", href=re.compile(r"/episodul-"))
    for ep in ep_links:
        title = ep.text.strip() or ep.get("title", "")
        if not title:
            # Try to find title in parent or child
            title = ep.find_next("span").text.strip() if ep.find_next("span") else "Episod"
            
        ep_url = ep["href"]
        if not ep_url.startswith("http"):
            ep_url = f"{BASE_URL}/{ep_url.lstrip('/')}"
            
        episodes.append({
            "title": title,
            "url": ep_url
        })
        
    # 5. Handle movie pages (no episodes found, but it might be a movie)
    if not seasons and not episodes:
        # Check if it has sources directly on the page
        sources = get_sources(url)
        if sources:
            episodes.append({
                "title": "Vezi Film",
                "url": url
            })
        
    return seasons, episodes

def get_season_episodes(url, season_id):
    """Get episodes for a specific season."""
    try:
        response = get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch season episodes: {e}")
        return []

    episodes = []
    # Find the div matching the season_id
    season_div = soup.find("div", id=f"season-{season_id}")
    if not season_div:
        # Try finding by tab content relation if any
        season_div = soup.find("div", class_="tab-pane", id=re.compile(f".*{season_id}.*"))

    if season_div:
        ep_links = season_div.find_all("a", href=True)
        for ep in ep_links:
            title = ep.text.strip()
            ep_url = ep["href"]
            if not ep_url.startswith("http"):
                ep_url = f"{BASE_URL}/{ep_url.lstrip('/')}"
            
            if "/episodul-" in ep_url:
                episodes.append({
                    "title": title,
                    "url": ep_url
                })
                
    return episodes

def get_sources(url):
    """Get sources from an episode or movie page."""
    try:
        response = get_html_content(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log_error(f"Failed to fetch source page: {e}")
        return []

    sources = []
    
    # 1. Parse javascript switch cases for sources
    scripts = soup.find_all("script")
    for s in scripts:
        if s.string and "switch" in s.string and "case" in s.string and 'src =' in s.string:
            matches = re.finditer(r'case\s+\d+:\s*src\s*=\s*["\']([^"\']+)["\']', s.string)
            for match in matches:
                src = match.group(1)
                if src:
                    if src.startswith("//"):
                        src = "https:" + src
                    if not src.startswith("http"):
                        src = f"{BASE_URL}/{src.lstrip('/')}"
                    
                    if "serialero.net" in src and ("/zsrv/" in src or "movie_srv" in src):
                        # Recursive call for internal pages
                        sources.extend(get_sources(src))
                    elif src.startswith("http"):
                        domain = urllib.parse.urlparse(src).netloc.replace("www.", "")
                        sources.append({"url": src, "domain": domain, "referer": url})
    
    # Check for iframes
    iframes = soup.find_all("iframe")
    for iframe in iframes:
        src = iframe.get("src") or iframe.get("data-src")
        if src and "onclickmov" not in src:
            if src.startswith("//"):
                src = "https:" + src
            if not src.startswith("http"):
                src = f"{BASE_URL}/{src.lstrip('/')}"
            
            if "serialero.net" in src and ("/zsrv/" in src or "movie_srv" in src):
                # Recursive call for internal pages
                sources.extend(get_sources(src))
            elif src.startswith("http"):
                domain = urllib.parse.urlparse(src).netloc.replace("www.", "")
                sources.append({"url": src, "domain": domain, "referer": url})
            
    # Check for source buttons/links
    source_links = soup.find_all("a", class_=re.compile(r"btn-source|source-link"))
    for link in source_links:
        src = link.get("href")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            if not src.startswith("http"):
                src = f"{BASE_URL}/{src.lstrip('/')}"
            
            if "serialero.net" in src and ("/zsrv/" in src or "movie_srv" in src):
                # Recursive call for internal pages
                sources.extend(get_sources(src))
            elif src.startswith("http"):
                domain = urllib.parse.urlparse(src).netloc.replace("www.", "")
                sources.append({"url": src, "domain": domain, "referer": url})
            
    # Check for video players in scripts or other tags
    tabs = soup.find_all("div", class_="tab-pane")
    for tab in tabs:
        iframe = tab.find("iframe")
        if iframe:
            src = iframe.get("src") or iframe.get("data-src")
            if src and "onclickmov" not in src:
                if src.startswith("//"):
                    src = "https:" + src
                if not src.startswith("http"):
                    src = f"{BASE_URL}/{src.lstrip('/')}"
                
                if "serialero.net" in src and ("/zsrv/" in src or "movie_srv" in src):
                    sources.extend(get_sources(src))
                elif src.startswith("http"):
                    domain = urllib.parse.urlparse(src).netloc.replace("www.", "")
                    sources.append({"url": src, "domain": domain, "referer": url})

    # Filter out duplicates while preserving order
    seen = set()
    unique_sources = []
    for source in sources:
        if source["url"] not in seen:
            seen.add(source["url"])
            unique_sources.append(source)

    return unique_sources
