# -*- coding: utf-8 -*-
import re
import time
import js2py
import requests
from core import httptools, scrapertools
from platformcode import logger, config

count = 5
forced_proxy_opt = 'ProxySSL'

# Variabili globali per memorizzare lo stato tra le funzioni
data = None
redir = None
host = None

kwargs = {
    'set_tls': True,
    'set_tls_min': True,
    'retries_cloudflare': 0,
    'CF': False,
    'cf_assistant': False,
    'ignore_response_code': True,
    'verify': False  # Disattiva la verifica SSL
}

def download_page_with_retry(url, max_retries=3):
    """Tenta il download di una pagina con meccanismo di riprova"""
    for i in range(max_retries):
        try:
            response = requests.get(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'DNT': '1',
                    'Upgrade-Insecure-Requests': '1'
                },
                timeout=10,
                verify=False  # Ignora gli errori del certificato
            )
            return response
        except Exception as e:
            logger.error(f"Errore nel download (tentativo {i+1}/{max_retries}): {str(e)}")
            time.sleep(2)
    return None

def test_video_exists(page_url):
    """Verifica se il video esiste sul server"""
    global data, redir, host
    logger.info("(page_url='%s')" % page_url)
    
    # Gestione speciale per i domini dood.*
    if 'dood.' in page_url:
        response = download_page_with_retry(page_url)
        if not response or response.status_code != 200:
            return False, config.get_localized_string(70449) % 'DooD Stream'
        
        # Aggiorna URL se c'è una redirezione
        if response.history:
            page_url = response.url
            redir = page_url
        
        # Ottieni host e dominio
        server = scrapertools.get_domain_from_url(page_url)
        host = "https://%s" % server
        
        # Gestione degli iframe incorporati
        html = response.text
        if '/d/' in page_url and scrapertools.find_single_match(html, ' <iframe src="([^"]+)"'):
            iframe_url = scrapertools.find_single_match(html, ' <iframe src="([^"]+)"')
            if iframe_url.startswith('/'):
                iframe_url = host + iframe_url
            response = download_page_with_retry(iframe_url)
            if not response:
                return False, config.get_localized_string(70449) % 'DooD Stream'
            html = response.text
            redir = iframe_url
        
        # Cerca la funzione JavaScript critica
        if re.search(r"(function\s?makePlay.*?;})", html):
            data = html
            return True, ""
        
        return False, config.get_localized_string(70449) % 'DooD Stream'
    
    # Codice originale per altri domini
    response = httptools.downloadpage(page_url, follow_redirects=False, **kwargs)
    if 'location' in response.headers:
        page_url = response.headers['location']
        redir = page_url
    
    server = scrapertools.get_domain_from_url(page_url)
    host = "https://%s" % server
    
    for i in range(count + 1):
        try:
            response = httptools.downloadpage(page_url, **kwargs)
            if response.code == 404 or "Video not found" in response.data:
                return False, config.get_localized_string(70449) % 'DooD Stream'
            
            html = response.data
            if '/d/' in page_url and scrapertools.find_single_match(html, ' <iframe src="([^"]+)"'):
                iframe_url = scrapertools.find_single_match(html, ' <iframe src="([^"]+)"')
                page_url = "%s%s" % (host, iframe_url)
                response = httptools.downloadpage(page_url, **kwargs)
                html = response.data
                redir = page_url
            
            if re.search(r"(function\s?makePlay.*?;})", html):
                data = html
                return True, ""
                
            if i < count:
                logger.debug("Riprova %d/%d" % (i + 1, count))
                time.sleep(3)
                
        except Exception as e:
            logger.error("Errore: %s" % str(e))
            if i < count:
                time.sleep(3)
    
    return False, config.get_localized_string(70449) % 'DooD Stream'


def get_video_url(page_url, premium=False, user="", password="", video_password=""):
    """Ottiene l'URL reale del video per la riproduzione"""
    global data, redir, host
    logger.info("url=" + page_url)
    video_urls = []
    
    if not data:
        return video_urls
    
    try:
        # Estrai il codice JavaScript
        js_code = scrapertools.find_single_match(data, r"(function\s?makePlay.*?})")
        if not js_code:
            return video_urls
        
        # Elabora il codice JavaScript
        js_code = re.sub(r"\s+\+\s+Date\.now\(\)", '', js_code)
        js = js2py.eval_js(js_code)
        makeplay = js() + str(int(time.time() * 1000))
        
        # Cerca l'URL base
        base_url = scrapertools.find_single_match(data, r"\$.get\('(/pass[^']+)'")
        if not base_url:
            return video_urls
        
        # Scarica l'URL finale
        if 'dood.' in host:
            response = download_page_with_retry(host + base_url)
            if not response:
                return video_urls
            video_data = response.text
        else:
            video_data = httptools.downloadpage(
                host + base_url,
                add_referer=True,
                **kwargs
            ).data
        
        # Costruisci l'URL del video
        if "X-Amz-" in video_data:
            video_url = video_data
        else:
            video_url = video_data + makeplay + "|Referer=%s" % redir
        
        # Ottieni la qualità
        label = scrapertools.find_single_match(data, r'type:\s*"video/([^"]+)"') or 'mp4'
        
        video_urls.append(['%s [doodstream]' % label, video_url])
        
    except Exception as e:
        logger.error("Errore in get_video_url: %s" % str(e))
    
    return video_urls
