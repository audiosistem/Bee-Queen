# -*- coding: utf-8 -*-
import re
import urllib.parse
import xbmc
import requests
from bs4 import BeautifulSoup
from ..debug_logger import logger

def search_comando_top(query):
    base_url = "https://comandofilmestop.site"
    search_url = f"{base_url}/?s={urllib.parse.quote_plus(query)}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        xbmc.log(f"[comando.top] Buscando por: {query}", xbmc.LOGINFO)
        logger.network(search_url, method='GET')
        response = requests.get(search_url, headers=headers, timeout=15)
        logger.network(search_url, method='GET', status=response.status_code, response=response.text if response.status_code != 200 else "OK")
        if response.status_code == 200:
            return response.content
    except Exception as e:
        xbmc.log(f"[comando.top] Erro de busca: {str(e)}", xbmc.LOGERROR)
        logger.scraper_error("ComandoTop", f"Search Error: {e}", search_url)
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


        # --- EXTRAÇÃO DOS DADOS ---
        dn_match = re.search(r'dn=([^&]+)', url)
        release_name = urllib.parse.unquote(dn_match.group(1)).replace('.', ' ') if dn_match else title

        quality = "1080p" if "1080p" in container_text else "720p" if "720p" in container_text else "4K" if "2160p" in container_text else "HD"
        audio = "Dual" if "dual" in container_text else "Dublado"
        subtitle = "Legendado" if "legendado" in container_text else "Sem legendas"
        type_label = "EP" if not any(x in container_text for x in ["volume", "completa"]) else "PACK"

        seeds = 0
        seed_match = re.search(r'(\d+)\s*SEEDS', parent_text, re.IGNORECASE)
        if seed_match:
            seeds = int(seed_match.group(1))

        size = ""
        size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB))', parent_text, re.IGNORECASE)
        if size_match:
            size = size_match.group(1)

        ep_number = ""
        if season and target_episode:
            ep_number = f"S{int(season):02d}E{int(target_episode):02d}"

        date_posted = ""
        date_tag = link.find_next("span", class_=re.compile(r"(date|post-date)"))
        if date_tag:
            date_posted = date_tag.get_text().strip()

        magnets.append({
            "url": url,
            "quality": quality,
            "type": "torrent",
            "provider": "ComandoTop",
            "release_title": release_name,
            "label": f"ComandoTop: {quality} | {audio} | {subtitle} [{type_label}] (S:{seeds})",
            "seeds": seeds,
            "size": size,
            "subtitle": subtitle,
            "episode_code": ep_number,
            "media_type": media_type,
            "date_posted": date_posted
        })
    
    return magnets


def find_content_url(html, title, year, season=None, imdb_id=None):
    if not html: 
        return None
    soup = BeautifulSoup(html, "html.parser")
    
    articles = soup.find_all("article", class_=re.compile(r"movie-card"))
    
    for article in articles:
        link_tag = article.find("a", href=True)
        if not link_tag:
            continue
        
        img_tag = link_tag.find("img")
        post_title = img_tag.get("alt", "").lower() if img_tag else ""
        
        if season:
            season_pattern = rf"{season}ª?\s*temporada"
            if not re.search(season_pattern, post_title):
                continue

        if imdb_id:
            return link_tag["href"]
        if title.lower() in post_title:
            return link_tag["href"]
            
    return None


def scrape(provider_url, item_data, season=None, episode=None, cancel_event=None):
    title = item_data.get("title")
    original_title = item_data.get("original_title")
    year = item_data.get("year")
    media_type = item_data.get("media_type", "movie")

    # --- Monta a query de busca ---
    clean_title = re.sub(r'[^\w\s]', ' ', title).strip()
    if media_type == "tvshow" and season:
        query = f"{clean_title} {season} temporada"
    else:
        query = clean_title

    # Busca no ComandoTop
    if cancel_event and cancel_event.is_set(): return []
    html_search = search_comando_top(query)

    # Encontra a URL do post correto
    if cancel_event and cancel_event.is_set(): return []
    post_url = find_content_url(html_search, title, year, season=season)
    
    # Se não achou pelo título, tenta pelo título original
    if not post_url and original_title and original_title != title:
        xbmc.log(f"[comando.top] Tentando busca por título original: {original_title}", xbmc.LOGINFO)
        if media_type == "tvshow" and season:
            query_orig = f"{original_title} {season} temporada"
        else:
            query_orig = original_title
        html_search_orig = search_comando_top(query_orig)
        post_url = find_content_url(html_search_orig, original_title, year, season=season)

    if post_url:
        if cancel_event and cancel_event.is_set(): return []
        xbmc.log(f"[comando.top] Post validado encontrado: {post_url}", xbmc.LOGINFO)
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(post_url, headers=headers, timeout=10)
        xbmc.log(f"[comando.top] Resposta do post: Status {response.status_code}", xbmc.LOGINFO)
        # Extrai os magnets filtrando pelo episódio se houver
        results = extract_magnets(response.content, title, target_episode=episode, season=season, media_type=media_type)
        xbmc.log(f"[comando.top] Encontrados {len(results)} magnets no post.", xbmc.LOGINFO)
        return results

    return []

