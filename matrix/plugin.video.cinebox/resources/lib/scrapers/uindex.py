# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import re
import urllib.request
import urllib.parse
from urllib.parse import quote_plus, unquote_plus
from ..debug_logger import logger

def scrape(imdb_id, media_type, season, episode, item_data=None, cancel_event=None):
    """UIndex Scraper for Cinebox.
    Native version (urllib) for maximum compatibility with Kodi."""
    if not item_data:
        return []

    # Attempts to obtain the series title from as many sources as possible
    title = item_data.get('tvshowtitle') or item_data.get('show_title') or item_data.get('title')
    if not title:
        return []

    # Title cleaning identical to Magneto
    title = title.replace("&", "and").replace("Special Victims Unit", "SVU").replace("/", " ").replace("$", "s")
    
    if media_type == 'tvshow':
        # For series, UIndex works best with the S01E01 format
        hdlr = "S%02dE%02d" % (int(season), int(episode))
    else:
        hdlr = item_data.get('year', '')
        
    clean_title = re.sub(r"[^A-Za-z0-9\s\.-]+", " ", title).strip()
    queries = [f"{clean_title} {hdlr}"]
    
    # Add original title if available
    original_title = item_data.get('original_title')
    if original_title and original_title != title:
        clean_orig = re.sub(r"[^A-Za-z0-9\s\.-]+", " ", original_title).strip()
        queries.append(f"{clean_orig} {hdlr}")
    
    # Add search only by title (without year/episode) if it is a movie
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
        # Add timestamp to avoid server cache
        url = f"{base_url}/search.php?search={quote_plus(query)}&t={int(time.time())}"
        
        xbmc.log(f"[UIndex] Fetching via urllib: {url}", xbmc.LOGINFO)
        
        try:
            logger.network(url, method='GET')
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                xbmc.log(f"[UIndex] Answer from {url}: Status {response.status}", xbmc.LOGINFO)
                logger.network(url, method='GET', status=response.status, response="OK" if response.status == 200 else "Error")
                if response.status != 200:
                    continue
                html = response.read().decode('utf-8', errors='ignore')
            
            # Extract rows from table
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S | re.I)
            
            if not rows:
                xbmc.log("[UIndex] No lines found in the HTML.", xbmc.LOGWARNING)
                continue

            for row in rows:
                if cancel_event and cancel_event.is_set(): break
                try:
                    # 1. Search for Magnet Link
                    magnets = re.findall(r'href=["\'](magnet:\?xt=urn:btih:[a-fA-F0-9]{40}[^"\']*)["\']', row, re.I)
                    if not magnets: continue
                    magnet_link = unquote_plus(magnets[0]).replace('&amp;', '&')
                    
                    # 2. Search for the Name
                    name_match = re.search(r'<a[^>]*href=["\']/details\.php\?id=\d+["\'][^>]*>(.*?)</a>', row, re.S | re.I)
                    if not name_match:
                        dn_match = re.search(r'dn=(.*?)&', magnet_link)
                        name = unquote_plus(dn_match.group(1)) if dn_match else "Unknown"
                    else:
                        name = re.sub(r'<[^>]*>', '', name_match.group(1)).strip()
                    
                    # 3. Search Size and Seeders
                    cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S | re.I)
                    if len(cells) < 4: continue
                    
                    # In real UIndex: td[2] is size, td[3] is seeds
                    size = re.sub(r'<[^>]*>', '', cells[2]).strip()
                    seeders_raw = re.sub(r'<[^>]*>', '', cells[3]).strip()
                    
                    try:
                        s_count = int(re.sub(r'\D', '', seeders_raw))
                    except:
                        s_count = 0
                    
                    # Extract InfoHash
                    hash_match = re.search(r'btih:([a-fA-F0-9]{40})', magnet_link, re.I)
                    if not hash_match: continue
                    info_hash = hash_match.group(1).lower()
                    
                    if info_hash in seen_hashes: continue
                    
                    # Determine quality
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
                xbmc.log(f"[UIndex] Success: {len(streams)} results found for {query}.", xbmc.LOGINFO)
                # If you already found results, you don't need to try the next query
                break
                
        except Exception as e:
            xbmc.log(f"[UIndex] Error in searching for {query}: {e}", xbmc.LOGERROR)
            continue
            
    return streams
