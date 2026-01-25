# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import re
import urllib.request
import urllib.parse
from urllib.parse import quote_plus, unquote_plus
from ..debug_logger import logger

def scrape(imdb_id, media_type, season, episode, item_data=None, cancel_event=None):
    """
    Scraper UIndex para Cinebox.
    Versão Nativa (urllib) para máxima compatibilidade com o Kodi.
    """
    if not item_data:
        return []

    # Tenta obter o título da série de várias fontes possíveis
    title = item_data.get('tvshowtitle') or item_data.get('show_title') or item_data.get('title')
    if not title:
        return []

    # Limpeza de título idêntica ao Magneto
    title = title.replace("&", "and").replace("Special Victims Unit", "SVU").replace("/", " ").replace("$", "s")
    
    if media_type == 'tvshow':
        # Para séries, o UIndex funciona melhor com o formato S01E01
        hdlr = "S%02dE%02d" % (int(season), int(episode))
    else:
        hdlr = item_data.get('year', '')
        
    clean_title = re.sub(r"[^A-Za-z0-9\s\.-]+", " ", title).strip()
    queries = [f"{clean_title} {hdlr}"]
    
    # Adiciona título original se disponível
    original_title = item_data.get('original_title')
    if original_title and original_title != title:
        clean_orig = re.sub(r"[^A-Za-z0-9\s\.-]+", " ", original_title).strip()
        queries.append(f"{clean_orig} {hdlr}")
    
    # Adiciona busca apenas pelo título (sem ano/episódio) se for filme
    if media_type == 'movie':
        queries.append(clean_title)
        if original_title and original_title != title:
            queries.append(clean_orig)

    import time
    base_url = "https://uindex.org"
    streams = []
    seen_hashes = set()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

    for query in queries:
        if cancel_event and cancel_event.is_set(): break
        # Adiciona timestamp para evitar cache do servidor
        url = f"{base_url}/search.php?search={quote_plus(query)}&t={int(time.time())}"
        
        xbmc.log(f"[UIndex] Buscando via urllib: {url}", xbmc.LOGINFO)
        
        try:
            logger.network(url, method='GET')
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                xbmc.log(f"[UIndex] Resposta de {url}: Status {response.status}", xbmc.LOGINFO)
                logger.network(url, method='GET', status=response.status, response="OK" if response.status == 200 else "Error")
                if response.status != 200:
                    continue
                html = response.read().decode('utf-8', errors='ignore')
            
            # Extrair linhas da tabela
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S | re.I)
            
            if not rows:
                xbmc.log("[UIndex] Nenhuma linha encontrada no HTML.", xbmc.LOGWARNING)
                continue

            for row in rows:
                if cancel_event and cancel_event.is_set(): break
                try:
                    # 1. Buscar o Magnet Link
                    magnets = re.findall(r'href=["\'](magnet:\?xt=urn:btih:[a-fA-F0-9]{40}[^"\']*)["\']', row, re.I)
                    if not magnets: continue
                    magnet_link = unquote_plus(magnets[0]).replace('&amp;', '&')
                    
                    # 2. Buscar o Nome
                    name_match = re.search(r'<a[^>]*href=["\']/details\.php\?id=\d+["\'][^>]*>(.*?)</a>', row, re.S | re.I)
                    if not name_match:
                        dn_match = re.search(r'dn=(.*?)&', magnet_link)
                        name = unquote_plus(dn_match.group(1)) if dn_match else "Unknown"
                    else:
                        name = re.sub(r'<[^>]*>', '', name_match.group(1)).strip()
                    
                    # 3. Buscar Tamanho e Seeders
                    cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S | re.I)
                    if len(cells) < 4: continue
                    
                    # No UIndex real: td[2] é tamanho, td[3] é seeders
                    size = re.sub(r'<[^>]*>', '', cells[2]).strip()
                    seeders_raw = re.sub(r'<[^>]*>', '', cells[3]).strip()
                    
                    try:
                        s_count = int(re.sub(r'\D', '', seeders_raw))
                    except:
                        s_count = 0
                    
                    # Extrair InfoHash
                    hash_match = re.search(r'btih:([a-fA-F0-9]{40})', magnet_link, re.I)
                    if not hash_match: continue
                    info_hash = hash_match.group(1).lower()
                    
                    if info_hash in seen_hashes: continue
                    
                    # Determinar qualidade
                    quality = '720p'
                    if any(x in name.lower() for x in ['2160p', '4k', 'uhd']): quality = '4K'
                    elif any(x in name.lower() for x in ['1080p', 'fhd']): quality = '1080p'
                    
                    streams.append({
                        'name': name,
                        'title': f"{name}\n[COLOR red]SIZE:[/COLOR] {size} | [COLOR red]S:[/COLOR] {s_count} | [COLOR red]HOSTER:[/COLOR] UIndex",
                        'url': magnet_link,
                        'infoHash': info_hash,
                        'quality': quality,
                        'provider': 'UIndex',
                        'release_title': name,
                        'seeders': s_count,
                        'size': size,
                        'type': 'torrent'
                    })
                    seen_hashes.add(info_hash)
                except:
                    continue
                    
            if streams:
                xbmc.log(f"[UIndex] Sucesso: {len(streams)} resultados encontrados para {query}.", xbmc.LOGINFO)
                # Se já encontrou resultados, não precisa tentar a próxima query
                break
                
        except Exception as e:
            xbmc.log(f"[UIndex] Erro na busca por {query}: {e}", xbmc.LOGERROR)
            continue
            
    return streams
