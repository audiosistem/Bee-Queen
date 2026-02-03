# -*- coding: utf-8 -*-
import re
import urllib.parse
import xbmc
import requests
from bs4 import BeautifulSoup
from ..debug_logger import logger

def search_baixarfilmes(query):
    base_url = "https://baixafilmestorrent.org"
    search_url = f"{base_url}/?s={urllib.parse.quote_plus(query)}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        xbmc.log(f"[baixarfilmes] Buscando por: {query}", xbmc.LOGINFO)
        logger.network(search_url, method='GET')
        response = requests.get(search_url, headers=headers, timeout=15)
        logger.network(search_url, method='GET', status=response.status_code, response=response.text if response.status_code != 200 else "OK")
        if response.status_code == 200:
            return response.content
    except Exception as e:
        xbmc.log(f"[download movies] Search error: {str(e)}", xbmc.LOGERROR)
        logger.scraper_error("BaixarFilmes", f"Search Error: {e}", search_url)
    return None

def extract_magnets(html, title, target_episode=None, season=None, media_type="movie"):
    magnets = []
    if not html: 
        return magnets
    
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=re.compile(r"^magnet:\?"))
    
    for link in links:
        url = link['href']
        parent = link.find_parent()
        parent_text = parent.get_text() if parent else ""
        container_text = parent_text.lower()

        # --- DATA EXTRACTION ---
        dn_match = re.search(r'dn=([^&]+)', url)
        release_name = urllib.parse.unquote(dn_match.group(1)).replace('.', ' ') if dn_match else title

        quality = "1080p" if "1080p" in container_text else "720p" if "720p" in container_text else "4K" if "2160p" in container_text else "HD"
        audio = "Dual" if "dual" in container_text or "dublado" in container_text else "Subtitled" if "legendado" in container_text else "Dubbed"
        
        # Extraction of Seeders (Seeds)
        seeds = 0
        # Try to find patterns like "Seeders: 10", "S: 10", "10 seeds", etc.
        seed_match = re.search(r'(?:seeders|seeds|sementes|s)[:\s]*(\d+)', parent_text, re.IGNORECASE)
        if seed_match:
            seeds = int(seed_match.group(1))
        else:
            # Try to find only the number if it is close to keywords
            keyword_match = re.search(r'(\d+)\s*(?:seeders|seeds|sementes)', parent_text, re.IGNORECASE)
            if keyword_match:
                seeds = int(keyword_match.group(1))

        size = ""
        size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB))', parent_text, re.IGNORECASE)
        if size_match:
            size = size_match.group(1)

        ep_number = ""
        if season and target_episode:
            ep_number = f"S{int(season):02d}E{int(target_episode):02d}"

        magnets.append({
            "url": url,
            "quality": quality,
            "type": "torrent",
            "provider": "BaixarFilmes",
            "release_title": release_name,
            "label": f"BaixarFilmes: {quality} | {audio} | {size} (S:{seeds})",
            "seeds": seeds,
            "size": size,
            "media_type": media_type,
            "episode_code": ep_number
        })
    
    return magnets

def find_content_url(html, title, year, season=None):
    if not html: 
        return None
    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all(["div", "article"], class_=re.compile(r"(item|post|column)"))
    
    for item in items:
        link_tag = item.find("a", href=True)
        if not link_tag: continue
        
        post_title = link_tag.get("title", "").lower() or link_tag.get_text().lower()
        
        if title.lower() in post_title:
            if season:
                season_pattern = rf"{season}ª?\s*temporada|s{int(season):02d}"
                if not re.search(season_pattern, post_title):
                    continue
            return link_tag["href"]
            
    return None

def scrape(provider_url, item_data, season=None, episode=None, cancel_event=None):
    title = item_data.get("title")
    year = item_data.get("year")
    media_type = item_data.get("media_type", "movie")

    clean_title = re.sub(r'[^\w\s]', ' ', title).strip()
    query = f"{clean_title} {year}" if media_type == "movie" else f"{clean_title} {season} temporada"

    if cancel_event and cancel_event.is_set(): return []
    html_search = search_baixarfilmes(query)
    
    post_url = find_content_url(html_search, title, year, season=season)
    
    if post_url:
        if cancel_event and cancel_event.is_set(): return []
        response = requests.get(post_url, timeout=10)
        return extract_magnets(response.content, title, target_episode=episode, season=season, media_type=media_type)

    return []
