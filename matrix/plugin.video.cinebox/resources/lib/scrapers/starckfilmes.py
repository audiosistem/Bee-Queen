# -*- coding: utf-8 -*-
"""Scraper for Starck Filmes
Extracts magnet links from films and series"""
import re
import xbmc
import requests
from bs4 import BeautifulSoup


def unshuffle_string(shuffled):
    """Decode data-u's obfuscated string
    Reverse Website JavaScript Algorithm"""
    try:
        length = len(shuffled)
        original = [''] * length
        used = [False] * length
        
        step = 3  # Original algorithm value
        index = 0
        
        for i in range(length):
            # Finds the next unused index
            while used[index]:
                index = (index + 1) % length
            
            used[index] = True
            original[i] = shuffled[index]
            index = (index + step) % length
        
        return ''.join(original)
    except Exception as e:
        xbmc.log(f"[Starck] Error unscrambling: {e}", xbmc.LOGERROR)
        return None


def extrair_magnet_links(soup):
    """Extracts ALL magnet links from the page (there can be multiple qualities)
    Returns list of dicts with {magnet, quality, size}"""
    links_encontrados = []
    
    try:
        # Find ALL download buttons
        btns = soup.find_all('span', class_='btn-down')
        
        if not btns:
            xbmc.log("[Starck] No download button found", xbmc.LOGWARNING)
            return links_encontrados
        
        xbmc.log(f"[Starck] Found {len(btns)} download buttons", xbmc.LOGINFO)
        
        for btn in btns:
            try:
                link = btn.find('a')
                if not link:
                    continue
                
                # Extract u-data
                data_u = link.get('data-u')
                if not data_u:
                    continue
                
                # Decode using unshuffle
                decoded = unshuffle_string(data_u)
                if not decoded or ('magnet:' not in decoded and not decoded.startswith('http')):
                    continue
                
                # Extract button text quality and size
                text_span = btn.find('span', class_='text')
                quality = 'HD'
                size = 'N/A'
                
                if text_span:
                    texto_completo = text_span.get_text()
                    
                    # Extract quality (1080p, 720p, 2160p, etc)
                    quality_match = re.search(r'(4K|2160p|1080p|720p|480p)', texto_completo, re.IGNORECASE)
                    if quality_match:
                        quality = quality_match.group(1).upper()
                    
                    # Extract size (3.70 GB, 11.84 GB, etc)
                    size_match = re.search(r'\(([^)]+(?:GB|MB))\)', texto_completo, re.IGNORECASE)
                    if size_match:
                        size = size_match.group(1)
                
                links_encontrados.append({
                    'magnet': decoded,
                    'quality': quality,
                    'size': size
                })
                
                xbmc.log(f"[Starck] Extracted link: {quality} - {size}", xbmc.LOGINFO)
                
            except Exception as e:
                xbmc.log(f"[Starck] Error processing button: {e}", xbmc.LOGERROR)
                continue
        
        return links_encontrados
        
    except Exception as e:
        xbmc.log(f"[Starck] Error extracting magnets: {e}", xbmc.LOGERROR)
        return links_encontrados


def extrair_informacoes_basicas(soup):
    """Extracts basic information from the film/series"""
    info = {}
    
    try:
        # Title
        titulo = soup.find('h1')
        if titulo:
            info['title'] = titulo.text.strip()
        
        # IMDB
        imdb = soup.find('span', class_='sl-imdb')
        if imdb:
            info['rating'] = imdb.text.strip()
        
        # Metadata (size, quality, etc.)
        desc_div = soup.find('div', class_='post-description')
        if desc_div:
            paragrafos = desc_div.find_all('p')
            for p in paragrafos:
                spans = p.find_all('span')
                if len(spans) >= 2:
                    chave = spans[0].text.strip(':').strip().lower()
                    valor = spans[1].text.strip()
                    
                    if 'tamanho' in chave:
                        info['size'] = valor
                    elif 'qualidade' in chave and 'video' in chave:
                        info['quality'] = valor
        
        # Meta tag quality
        meta = soup.find('span', class_='sl-quality')
        if meta:
            q = meta.text.strip()
            if q == 'FHD':
                info['quality_label'] = '1080p'
            elif q == 'HD':
                info['quality_label'] = '720p'
            elif q == 'UHD':
                info['quality_label'] = '4K'
            else:
                info['quality_label'] = q
    
    except Exception as e:
        xbmc.log(f"[Starck] Error extracting information: {e}", xbmc.LOGERROR)
    
    return info


def detectar_idioma_filme(soup):
    """Detect movie language based on download button"""
    try:
        btn = soup.find('span', class_='btn-down')
        if not btn:
            return ''
        
        text_span = btn.find('span', class_='text')
        if not text_span:
            return ''
        
        texto = text_span.get_text().lower()
        
        if 'dual' in texto or 'dual audio' in texto:
            return ' DUAL'
        elif 'dublado' in texto:
            return ' DUBLADO'
        elif 'legendado' in texto:
            return ' LEGENDADO'
        
        return ''
        
    except Exception as e:
        xbmc.log(f"[Starck] Error detecting language: {e}", xbmc.LOGERROR)
        return ''


def buscar_filme(item_data):
    """Search for a film on Starck Filmes"""
    titulo = item_data.get('title', '')
    titulo_original = item_data.get('original_title', '')
    ano = item_data.get('year', '')
    
    if not titulo:
        return []
    
    # Try searching with main title AND original title (if different)
    titulos_para_buscar = [titulo]
    if titulo_original and titulo_original.lower() != titulo.lower():
        titulos_para_buscar.append(titulo_original)
    
    # Add variations without special characters
    for t in list(titulos_para_buscar):
        clean_t = re.sub(r'[^\w\s]', ' ', t).strip()
        if clean_t != t:
            titulos_para_buscar.append(clean_t)
    
    xbmc.log(f"[Starck] Search titles: {titles_para_buscar}", xbmc.LOGINFO)
    
    sources = []
    
    for titulo_busca in titulos_para_buscar:
        try:
            # Normalize title for search
            search_query = titulo_busca.lower()
            search_query = re.sub(r'[^\w\s]', '', search_query)
            search_query = search_query.replace(' ', '+')
            
            # Search URL
            base_url = "https://www.starckfilmes-v8.com"
            search_url = f"{base_url}/?s={search_query}"
            
            xbmc.log(f"[Starck] Buscando: {search_url}", xbmc.LOGINFO)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            try:
                response = requests.get(search_url, headers=headers, timeout=15)
                xbmc.log(f"[Starck] Resposta de {search_url}: Status {response.status_code}", xbmc.LOGINFO)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                xbmc.log(f"[Starck] Network error when searching: {e}", xbmc.LOGWARNING)
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Search results
            resultados = soup.find_all('div', class_='item')
            
            for resultado in resultados[:3]:  # Limit to 3 results
                try:
                    # Movie link
                    link_tag = resultado.find('a', class_='title')
                    if not link_tag:
                        continue
                    
                    filme_url = link_tag.get('href')
                    filme_titulo = link_tag.text.strip()
                    
                    # STRICT SERIES FILTER: If the title contains series words, skip
                    # Added 'episode', 'episode', 'chapter', 'chapter'
                    if any(x in filme_titulo.lower() for x in ['temporada', 'series', 'serie', 'completa', 'episode', 'episodio', 'chapter', 'capitulo', 's0', 's1']):
                        xbmc.log(f"[Starck] Skipping series found in search of film: {filme_title}", xbmc.LOGINFO)
                        continue
                    
                    # Check if the year matches (if available)
                    year_span = resultado.find('span', class_='footer-year')
                    filme_ano = year_span.text.strip() if year_span else ''
                    
                    # If we have a year, check compatibility
                    if ano and filme_ano:
                        try:
                            if abs(int(filme_ano) - int(ano)) > 1:
                                continue
                        except:
                            pass
                    
                    xbmc.log(f"[Starck] Processando: {filme_titulo} ({filme_url})", xbmc.LOGINFO)
                    
                    # Access film page
                    try:
                        filme_response = requests.get(filme_url, headers=headers, timeout=15)
                        xbmc.log(f"[Starck] Content page response: Status {filme_response.status_code}", xbmc.LOGINFO)
                        filme_response.encoding = 'utf-8'
                        filme_soup = BeautifulSoup(filme_response.text, 'html.parser')
                    except requests.exceptions.RequestException as e:
                        xbmc.log(f"[Starck] Network error when accessing film page: {e}", xbmc.LOGWARNING)
                        continue
                    
                    # SERIES FILTER (PAGE): Check if the page contains the 'episodes' or 'episodes' div
                    if filme_soup.find('div', class_='epsodios') or filme_soup.find('div', class_='episodios') or filme_soup.find('div', id='episodios'):
                        xbmc.log(f"[Starck] Skipping series page detected: {filme_title}", xbmc.LOGINFO)
                        continue
                    
                    # ADDITIONAL FILTER: If there are many magnet links with episode names
                    magnets_raw = filme_soup.find_all('span', class_='btn-down')
                    is_series_page = False
                    for btn in magnets_raw[:5]:
                        btn_text = btn.get_text().lower()
                        if re.search(r'episode|episode|chapter|chapter|ep\s?\d+|s\d+e\d+', btn_text):
                            is_series_page = True
                            break
                    
                    if is_series_page:
                        xbmc.log(f"[Starck] Skipping page with episode links: {filme_title}", xbmc.LOGINFO)
                        continue
                    
                    # Extract ALL magnets (there can be multiple qualities)
                    magnets = extrair_magnet_links(filme_soup)
                    if not magnets:
                        continue
                    
                    # Extract basic information
                    info = extrair_informacoes_basicas(filme_soup)
                    
                    # Detect download button language (uses the first button as a reference)
                    sufixo_idioma = detectar_idioma_filme(filme_soup)
                    
                    # Create a stream for each available quality
                    for idx, mag_data in enumerate(magnets):
                        titulo_final = filme_titulo + sufixo_idioma
                        
                        # If there are multiple versions, add identifier
                        if len(magnets) > 1:
                            titulo_final += f" [{mag_data['quality']} - {mag_data['size']}]"
                        
                        # Try to extract seeders from the text if available
                        seeds = 0
                        seed_match = re.search(r'(?:seeders|seeds|sementes|s)[:\s]*(\d+)', titulo_final, re.IGNORECASE)
                        if seed_match:
                            seeds = int(seed_match.group(1))

                        stream = {
                            'url': mag_data['magnet'],
                            'title': f"{titulo_final} (S:{seeds})",
                            'quality': mag_data['quality'],
                            'size': mag_data['size'],
                            'type': 'Torrent',
                            'seeders': seeds,
                            'extras': []
                        }
                        
                        sources.append(stream)
                        xbmc.log(f"[Starck] Stream adicionado: {titulo_final}", xbmc.LOGINFO)
                    
                except Exception as e:
                    xbmc.log(f"[Starck] Error processing result: {e}", xbmc.LOGERROR)
                    continue
            
            # If you found results with this title, you don't need to try the others
            if sources:
                break
                
        except Exception as e:
            xbmc.log(f"[Starck] Error searching with'{titulo_busca}': {e}", xbmc.LOGERROR)
            continue
    
    if not sources:
        xbmc.log(f"[Starck] No results found for any of the titles", xbmc.LOGWARNING)
    
    return sources


def buscar_serie(item_data, season, episode):
    """Search for a series episode on Starck Filmes"""
    titulo = item_data.get('title', '')
    titulo_original = item_data.get('original_title', '')
    
    if not titulo or season is None or episode is None:
        return []
    
    # Try searching with main title AND original title (if different)
    titulos_para_buscar = [titulo]
    if titulo_original and titulo_original.lower() != titulo.lower():
        titulos_para_buscar.append(titulo_original)
    
    # Add variations without special characters
    for t in list(titulos_para_buscar):
        clean_t = re.sub(r'[^\w\s]', ' ', t).strip()
        if clean_t != t:
            titulos_para_buscar.append(clean_t)
    
    xbmc.log(f"[Starck] Titles for series search: {titles_para_buscar}", xbmc.LOGINFO)
    
    sources = []
    
    for titulo_busca in titulos_para_buscar:
        try:
            # Normalize title - JUST THE SERIES NAME
            search_query = titulo_busca.lower()
            search_query = re.sub(r'[^\w\s]', '', search_query)
            search_query = search_query.replace(' ', '+')
            
            # Episode formatting for filter
            s_num = int(season)
            e_num = int(episode)
            s = str(s_num).zfill(2)
            e = str(e_num).zfill(2)
            ep_pattern = f"s{s}e{e}"
            
            base_url = "https://www.starckfilmes-v8.com"
            search_url = f"{base_url}/?s={search_query}"
            
            xbmc.log(f"[Starck] Searching series: {search_url}", xbmc.LOGINFO)
            xbmc.log(f"[Starck] Procurando por: {ep_pattern}", xbmc.LOGINFO)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            try:
                response = requests.get(search_url, headers=headers, timeout=15)
                xbmc.log(f"[Starck] Resposta de {search_url}: Status {response.status_code}", xbmc.LOGINFO)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                xbmc.log(f"[Starck] Network error when searching: {e}", xbmc.LOGWARNING)
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Search results - may be full season page
            resultados = soup.find_all('div', class_='item')
            
            for resultado in resultados[:5]:  # Increase limit
                try:
                    link_tag = resultado.find('a', class_='title')
                    if not link_tag:
                        continue
                    
                    page_url = link_tag.get('href')
                    page_titulo = link_tag.text.strip()
                    
                    # Correct page title coding if necessary
                    try:
                        page_titulo_fixed = page_titulo.encode('latin1').decode('utf-8')
                    except:
                        page_titulo_fixed = page_titulo
                    
                    xbmc.log(f"[Starck] Checking page: {page_title_fixed}", xbmc.LOGINFO)
                    
                    # Access page
                    try:
                        page_response = requests.get(page_url, headers=headers, timeout=15)
                        # Force encoding to utf-8 to avoid problems with special characters
                        page_response.encoding = 'utf-8'
                        page_soup = BeautifulSoup(page_response.text, 'html.parser')
                    except requests.exceptions.RequestException as e:
                        xbmc.log(f"[Starck] Network error when accessing page: {e}", xbmc.LOGWARNING)
                        continue
                    
                    # Search by episode div
                    epsodios_div = page_soup.find('div', class_='epsodios')
                    
                    if epsodios_div:
                        # It's a season page with several episodes
                        xbmc.log("[Starck] Season page found", xbmc.LOGINFO)
                        
                        # Search for the specific episode
                        paragrafos = epsodios_div.find_all('p')
                        
                        for p in paragrafos:
                            strong = p.find('strong')
                            if not strong:
                                continue
                            
                            ep_text = strong.text.lower()
                            
                            # Patterns for finding the episode
                            # "EPISODE 01:", "EPISODES 01 AND 02:", "EPISODE 08 to 09:", etc.
                            episodio_encontrado = False
                            
                            # Method 1: Search for "episode XX" (with or without leading zero)
                            if re.search(rf'episodes?\s+0?{e_num}\b', ep_text):
                                episodio_encontrado = True
                            
                            # Method 2: Search by range "01 and 02", "08 to 09", "01 to 10"
                            if not episodio_encontrado:
                                # Search for "episode X and Y", "episode X to Y", "episode X to Y"
                                match = re.search(r'episodes?\s+0?(\d+)\s+(?:e|ao|a)\s+0?(\d+)', ep_text)
                                if match:
                                    inicio = int(match.group(1))
                                    fim = int(match.group(2))
                                    if inicio <= e_num <= fim:
                                        episodio_encontrado = True
                            
                            # Method 3: Search by number only if the paragraph is short and contains the number
                            if not episodio_encontrado and len(ep_text) < 20:
                                if re.search(rf'\b0?{e_num}\b', ep_text):
                                    episodio_encontrado = True
                            
                            if not episodio_encontrado:
                                continue
                            
                            xbmc.log(f"[Starck] Episode {e_num} found in: {ep_text}", xbmc.LOGINFO)
                            
                            # Extract episode link
                            link = p.find('a')
                            if not link:
                                xbmc.log("[Starck] Link not found in paragraph", xbmc.LOGWARNING)
                                continue
                            
                            data_u = link.get('data-u')
                            if not data_u:
                                xbmc.log("[Starck] data-u not found", xbmc.LOGWARNING)
                                continue
                            
                            # Decode magnet
                            magnet = unshuffle_string(data_u)
                            if not magnet or 'magnet:' not in magnet:
                                xbmc.log("[Starck] Invalid Magnet after decoding", xbmc.LOGWARNING)
                                continue
                            
                            # Extract basic information from the page
                            info = extrair_informacoes_basicas(page_soup)
                            
                            # Detect H3 language in the episodes div
                            sufixo_idioma = ''
                            h3 = epsodios_div.find('h3')
                            if h3:
                                h3_text = h3.get_text().lower()
                                if 'dual' in h3_text:
                                    sufixo_idioma = ' DUAL'
                                elif 'dublado' in h3_text:
                                    sufixo_idioma = ' DUBLADO'
                                elif 'legendado' in h3_text:
                                    sufixo_idioma = ' LEGENDADO'
                            
                            # Create title (use the original title of the search, not the website)
                            # ✅ FIX: Use the actual paragraph title for later validation
                            # If the paragraph does not contain SxxExx, navigation.py will discard
                            ep_titulo = f"{titulo} {ep_text.upper()}{sufixo_idioma}"
                            
                            stream = {
                                'url': magnet,
                                'title': ep_titulo,
                                'quality': info.get('quality_label', 'HD'),
                                'size': info.get('size', 'N/A'),
                                'type': 'Torrent',
                                'seeders': 0,
                                'extras': []
                            }
                            
                            sources.append(stream)
                            xbmc.log(f"[Starck] Stream adicionado: {ep_titulo}", xbmc.LOGINFO)
                            break  # You found the episode, no need to continue
                    
                    else:
                        # Individual episode page
                        if ep_pattern in page_titulo.lower():
                            xbmc.log(f"[Starck] Processing individual episode: {page_title}", xbmc.LOGINFO)
                            
                            magnets = extrair_magnet_links(page_soup)
                            if not magnets:
                                continue
                            
                            info = extrair_informacoes_basicas(page_soup)
                            sufixo_idioma = detectar_idioma_filme(page_soup)
                            
                            # Create stream for each quality (episodes rarely have multiple, but support)
                            for mag_data in magnets:
                                ep_titulo = page_titulo + sufixo_idioma
                                if len(magnets) > 1:
                                    ep_titulo += f" [{mag_data['quality']} - {mag_data['size']}]"
                                
                                stream = {
                                    'url': mag_data['magnet'],
                                    'title': ep_titulo,
                                    'quality': mag_data['quality'],
                                    'size': mag_data['size'],
                                    'type': 'Torrent',
                                    'seeders': 0,
                                    'extras': []
                                }
                                
                                sources.append(stream)
                    
                except Exception as e:
                    xbmc.log(f"[Starck] Error processing page: {e}", xbmc.LOGERROR)
                    continue
            
            # If you found results with this title, you don't need to try the others
            if sources:
                break
                
        except Exception as e:
            xbmc.log(f"[Starck] Error in searching for series with'{titulo_busca}': {e}", xbmc.LOGERROR)
            continue
    
    if not sources:
        xbmc.log(f"[Starck] No episodes {ep_pattern} found for any of the titles", xbmc.LOGWARNING)
    
    return sources


def scrape(provider_url, item_data, season=None, episode=None):
    """Scraper main function"""
    xbmc.log("[Starck] Iniciando scraper...", xbmc.LOGINFO)
    
    media_type = item_data.get('media_type')
    
    if media_type == 'movie':
        return buscar_filme(item_data)
    elif media_type == 'tvshow':
        return buscar_serie(item_data, season, episode)
    
    return []