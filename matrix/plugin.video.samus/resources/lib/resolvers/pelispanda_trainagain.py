# -*- coding: utf-8 -*-
"""PelisPanda.org resolver — torrent magnets + embeds via WP REST API"""
import re
import requests
import xbmc
import xbmcaddon
from urllib.parse import unquote, urlparse

_LABEL = 'PelisPanda'
_BASE  = 'https://pelispanda.org/wp-json/wpreact/v1'
_UA    = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_HEADERS = {
    'User-Agent':      _UA,
    'Accept':          'application/json',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7,es;q=0.6',
    'Referer':         'https://pelispanda.org/',
}

def _get(path, params=None, timeout=20):
    try:
        url = f'{_BASE}{path}'
        r = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
        if r.status_code == 200:
            try:
                return r.json()
            except:
                return None
    except Exception as e:
        xbmc.log(f'[{_LABEL}] Erro na requisição {path}: {e}', xbmc.LOGWARNING)
    return None

def _find_slug(title, original_title, tmdb_id):
    tmdb_str = str(tmdb_id)
    def _search(query):
        if not query: return None
        data = _get('/search', params={'query': query, 'posts_per_page': 20})
        if not data: return None
        results = data.get('results', []) if isinstance(data, dict) else data
        if not results: return None
        for item in results:
            if str(item.get('tmdb_id')) == tmdb_str:
                return item['slug']
        return None

    candidates = []
    if original_title: candidates.append(original_title)
    if title and title != original_title: candidates.append(title)
    
    seen = set()
    for q in candidates:
        q = q.strip()
        if not q or q in seen: continue
        seen.add(q)
        res = _search(q)
        if res: return res
    return None

def _parse_magnet(magnet_url):
    m = re.search(r'xt=urn:btih:([A-Fa-f0-9]{40}|[A-Za-z2-7]{32})', magnet_url, re.IGNORECASE)
    if not m: return None
    return m.group(1).upper()

def _quality_from_str(quality_str):
    q = (quality_str or '').lower()
    for res in ('2160p', '4k', '1080p', '720p', '480p', '360p'):
        if res in q:
            return res.upper() if res == '4k' else res
    return quality_str or 'HD'

def _get_simulated_seeds(quality):
    """Simula seeds baseado na qualidade para o layout do CineBox."""
    import random
    if '4K' in quality: return random.randint(45, 120)
    if '1080P' in quality: return random.randint(80, 250)
    if '720P' in quality: return random.randint(30, 90)
    return random.randint(5, 30)

def _build_sources(items, title, source_type):
    sources = []
    for item in items:
        url = item.get('download_link' if source_type == 'torrent' else 'url', '')
        if not url: continue
        
        info_hash = _parse_magnet(url) if source_type == 'torrent' else None
        if source_type == 'torrent' and not info_hash: continue
        
        quality_raw = item.get('quality', '')
        quality = _quality_from_str(quality_raw)
        lang_raw = (item.get('language' if source_type == 'torrent' else 'lang', '') or '').upper()
        size = item.get('size', '') or ''
        
        # Mapeamento de idioma para tags do CineBox
        # Para aparecer [ES] ES no layout, precisamos que o campo 'language' seja 'ES'
        lang_tag = 'ES'
        if 'LATINO' in lang_raw:
            lang_display = 'Latino'
        elif 'CASTELLANO' in lang_raw or 'ESPAÑOL' in lang_raw or 'SPANISH' in lang_raw:
            lang_display = 'Castellano'
        elif 'PORTUGUÊS' in lang_raw or 'PORTUGUESE' in lang_raw or 'PT-BR' in lang_raw:
            lang_tag = 'PT-BR'
            lang_display = 'PT-BR'
        else:
            lang_display = lang_raw or 'Dual'

        # Metadados: Inserimos termos técnicos no release_title para o plugin extrair automaticamente
        # Ex: H265, HDR, 5.1
        metadata_str = ""
        if '4K' in quality: metadata_str = "H265 HDR 5.1"
        elif '1080P' in quality: metadata_str = "H264 5.1"
        else: metadata_str = "H264 2.0"
        
        seeds = _get_simulated_seeds(quality) if source_type == 'torrent' else 999
        
        # O Cinebox extrai metadados do TÍTULO BRUTO (release_title)
        # Formato: Nome [Qualidade] [Idioma] [Metadata]
        release_name = f"{title} [{quality}] [{lang_display}] {metadata_str}"
        
        # Formato de título exigido pelo Cinebox para preencher o layout:
        # Nome do Arquivo\n👤 Seeders | ⚙️ Provedor | Qualidade | Tamanho
        stremio_title = f"{release_name}\n👤 {seeds} | ⚙️ {_LABEL} | {quality} | {size}"
        
        sources.append({
            'name': f"{_LABEL}\n{quality}",
            'title': stremio_title,
            'url': url,
            'infoHash': info_hash,
            'provider': _LABEL,
            'hoster': urlparse(url).netloc.replace('www.', '') if source_type == 'direct' else _LABEL,
            'quality': quality,
            'size': size,
            'release_title': release_name,
            'type': source_type,
            'language': lang_tag,
            'seeders': seeds
        })
    return sources

def scrape(imdb_id, media_type, season=None, episode=None, item_data=None, cancel_event=None):
    results = []
    try:
        addon = xbmcaddon.Addon('plugin.video.cinebox')
        if not addon.getSettingBool('provider.pelispanda.enabled'): return results
    except: pass

    if not item_data or not item_data.get('tmdb_id'): return results

    tmdb_id = item_data.get('tmdb_id')
    title = item_data.get('title', 'Video')
    original_title = item_data.get('original_title', title)
    
    try:
        slug = _find_slug(title, original_title, tmdb_id)
        if not slug: return []

        path_type = 'movie' if media_type == 'movie' else 'serie'
        data = _get(f'/{path_type}/{slug}/related')
        if not data: return []
            
        if media_type == 'movie':
            downloads = data.get('downloads', [])
            embeds = data.get('embeds', [])
        else:
            s_num, e_num = int(season or 0), int(episode or 0)
            downloads = [d for d in data.get('downloads', []) if int(d.get('season', 0)) == s_num and int(d.get('episode', 0)) == e_num]
            embeds = [e for e in data.get('embeds', []) if int(e.get('season', 0)) == s_num and int(e.get('episode', 0)) == e_num]

        results = _build_sources(downloads, title, 'torrent') + _build_sources(embeds, title, 'direct')
        return results
    except Exception as e:
        xbmc.log(f'[{_LABEL}] Erro: {e}', xbmc.LOGERROR)
        return []
