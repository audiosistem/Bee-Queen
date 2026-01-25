# -*- coding: utf-8 -*-
# resources/lib/scrapers/stremio.py - VERSÃO OTIMIZADA

import requests
import xbmc
import urllib.parse
from .session import USER_AGENT
from .utils import get_anime_search_patterns
from ..debug_logger import logger

def scrape(provider_url, is_configurable, imdb_id, media_type, season, episode, item_data=None, cancel_event=None):
    """
    Scraper Stremio unificado e otimizado.
    """
    
    # ========================================
    # 1. VALIDAÇÃO E NORMALIZAÇÃO
    # ========================================
    if not provider_url:
        return []
    
    # Normaliza a URL base (remove manifest.json se presente)
    base_url = provider_url.replace('/manifest.json', '').rstrip('/')
    
    # Normaliza season/episode APENAS se não forem None
    season = _safe_int(season)
    episode = _safe_int(episode)
    
    # Valida requisitos mínimos
    if not imdb_id and "animezey" not in base_url.lower():
        xbmc.log(f"[Stremio] Sem IMDB ID para {base_url}", xbmc.LOGDEBUG)
        return []
    
    # ========================================
    # 2. CONSTRUÇÃO DE ENDPOINTS
    # ========================================
    endpoints = _build_endpoints(media_type, imdb_id, season, episode)
    
    # Se não temos IMDB, tentamos busca por texto se o provedor suportar (ex: Jackett/Torrentio via search)
    # Mas a maioria dos addons Stremio exige ID. 
    # Vamos adicionar suporte a busca por título original se o IMDB falhar ou como complemento.
    
    if not endpoints and not item_data:
        xbmc.log(f"[Stremio] Nenhum endpoint válido para {media_type}", xbmc.LOGWARNING)
        return []
    
    # ========================================
    # 3. CONFIGURAÇÃO TORRENTIO
    # ========================================
    config_prefix = ""
    if is_configurable:
        try:
            from ..utils import build_torrentio_config_string
            config_prefix = build_torrentio_config_string()
        except Exception as e:
            xbmc.log(f"[Stremio] Config error: {e}", xbmc.LOGDEBUG)
    
    # ========================================
    # 4. BUSCA E DEDUPLICAÇÃO
    # ========================================
    streams = []
    seen_ids = set()
    
    # Adicionar busca por título se for Torrentio e não tivermos resultados por ID
    if "torrentio" in base_url.lower() and not endpoints:
        search_query = item_data.get('original_title') or item_data.get('title')
        if search_query:
            if media_type == 'tvshow':
                query = f"{search_query} S{int(season):02d}E{int(episode):02d}"
            else:
                year = item_data.get('year', '')
                query = f"{search_query} {year}"
            endpoints.append(f"/stream/{media_type}/{urllib.parse.quote(query)}.json")

    for endpoint in endpoints:
        if cancel_event and cancel_event.is_set():
            break
            
        if config_prefix:
            url = f"{base_url}/{config_prefix}{endpoint}"
        else:
            url = f"{base_url}{endpoint}"
        
        # Correção para URLs duplas de barra
        url = url.replace('//stream', '/stream')
        
        found = _fetch_streams(url)
        if not found:
            continue
        
        # Deduplica e adiciona release_title
        for stream in found:
            stream_id = stream.get('url') or stream.get('infoHash')
            
            if stream_id and stream_id in seen_ids:
                continue
            
            # Adiciona título de lançamento se não existir
            if 'release_title' not in stream:
                # Tenta extrair o título real do arquivo do campo 'title' ou 'description' do Stremio
                raw_title = stream.get('title', '') or stream.get('description', '')
                if raw_title:
                    # Pega a primeira linha, que geralmente é o nome do arquivo
                    file_name = raw_title.split('\n')[0].strip()
                    if file_name and len(file_name) > 5:
                        stream['release_title'] = file_name
                
                # Fallback se não conseguiu extrair um nome de arquivo válido
                if 'release_title' not in stream:
                    stream['release_title'] = _generate_release_title(
                        item_data, media_type, season, episode
                    )
            
            streams.append(stream)
            
            if stream_id:
                seen_ids.add(stream_id)
    
    provider_name = base_url.split('/')[2]
    xbmc.log(f"[Stremio] {len(streams)} streams de {provider_name}", xbmc.LOGINFO)
    logger.scraper_sources(provider_name, len(streams), streams[:3] if streams else [])
    return streams


# ============================================
# FUNÇÕES AUXILIARES (INTERNAS)
# ============================================

def _safe_int(value):
    """Converte para int de forma segura."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        xbmc.log(f"[Stremio] Conversão inválida: {value}", xbmc.LOGDEBUG)
        return None


def _build_endpoints(media_type, imdb_id, season, episode):
    """
    Constrói lista de endpoints para tentar.
    """
    endpoints = []
    
    if media_type == 'movie':
        if imdb_id:
            endpoints.append(f"/stream/movie/{imdb_id}.json")
    
    elif media_type == 'tvshow':
        if season is None or episode is None:
            return []
        
        if not imdb_id:
            return []
        
        # Usa padrões de busca de anime (ex: S01:E01, S1:E1)
        from .utils import get_anime_search_patterns
        patterns = get_anime_search_patterns(season, episode)
        
        for s, e in patterns:
            endpoints.append(f"/stream/series/{imdb_id}:{s}:{e}.json")
    
    return endpoints


def _fetch_streams(url):
    """
    Faz request e retorna lista de streams.
    """
    provider_name = url.split('/')[2]
    try:
        xbmc.log(f"[Stremio] Requisitando: {url}", xbmc.LOGINFO)
        logger.network(url, method='GET')
        response = requests.get(
            url, 
            headers={'User-Agent': USER_AGENT}, 
            timeout=10
        )
        logger.network(url, method='GET', status=response.status_code, response=response.text if response.status_code != 200 else "OK")
        xbmc.log(f"[Stremio] Resposta de {url}: Status {response.status_code}", xbmc.LOGINFO)
        response.raise_for_status()
        
        data = response.json()
        streams = data.get('streams', [])
        
        if streams:
            xbmc.log(f"[Stremio] ✓ {len(streams)} em {url.split('/')[-1]}", xbmc.LOGDEBUG)
        
        return streams
        
    except requests.Timeout:
        xbmc.log(f"[Stremio] Timeout: {url}", xbmc.LOGWARNING)
        logger.scraper_error(provider_name, "Timeout", url)
    except requests.RequestException as e:
        xbmc.log(f"[Stremio] Erro HTTP: {e}", xbmc.LOGDEBUG)
        logger.scraper_error(provider_name, f"HTTP Error: {e}", url)
    except ValueError:
        xbmc.log(f"[Stremio] JSON inválido: {url}", xbmc.LOGWARNING)
        logger.scraper_error(provider_name, "Invalid JSON", url)
    except Exception as e:
        xbmc.log(f"[Stremio] Erro inesperado: {e}", xbmc.LOGERROR)
        logger.scraper_error(provider_name, f"Unexpected Error: {e}", url)
    
    return []


def _generate_release_title(item_data, media_type, season, episode):
    """
    Gera título de lançamento padrão.
    """
    if not item_data:
        if media_type == 'tvshow' and season is not None and episode is not None:
            return f"S{season:02d}E{episode:02d}"
        return "Desconhecido"
    
    title = item_data.get('title', 'Desconhecido')
    
    if media_type == 'tvshow' and season is not None and episode is not None:
        return f"{title} S{season:02d}E{episode:02d}"
    
    return title
