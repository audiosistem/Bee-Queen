# -*- coding: utf-8 -*-
import requests
import xbmc
import re
import urllib.parse
from .session import USER_AGENT
from ..debug_logger import logger

def scrape(imdb_id, media_type, season, episode, item_data=None, cancel_event=None):
    """
    Scraper Jackett/Prowlarr para Cinebox.
    Busca em instâncias públicas e melhora a cobertura.
    """
    if not item_data:
        return []

    title = item_data.get('title')
    original_title = item_data.get('original_title')
    year = item_data.get('year')
    
    if not title:
        return []

    streams = []
    seen_hashes = set()
    
    # Lista de instâncias públicas de Jackett/Prowlarr ou agregadores similares
    # Como não temos uma API key do usuário, vamos focar em usar o Torrentio 
    # com uma configuração mais agressiva de busca por texto.
    
    from .stremio import scrape as stremio_scrape
    
    # Torrentio com todos os provedores possíveis
    config = "providers=comando,bludv,micoleaodublado,yts,nyaasi,1337x,tgx,rarbg,eztv,torrentgalaxy,magnetdl,horriblesubs,piratebay,kickasstorrents|language=japanese,portuguese,english"
    provider_url = f"https://torrentio.strem.fun/{config}"
    
    # 1. Tenta busca normal por ID
    results = stremio_scrape(provider_url, False, imdb_id, media_type, season, episode, item_data, cancel_event)
    streams.extend(results)
    
    # 2. Se não houver resultados e tivermos título original, tenta busca por texto no Torrentio
    if not streams and original_title and original_title != title:
        xbmc.log(f"[Jackett-Scraper] Sem resultados por ID, tentando busca por título original: {original_title}", xbmc.LOGINFO)
        # O Torrentio suporta busca por texto via endpoint /stream/movie/query.json
        if media_type == 'tvshow':
            query = f"{original_title} S{int(season):02d}E{int(episode):02d}"
        else:
            year = item_data.get('year', '')
            query = f"{original_title} {year}"
        
        # Simula um item_data sem IMDB para forçar a busca por texto no stremio.py modificado
        fake_item_data = item_data.copy()
        # Remove o IMDB para forçar a busca por título no stremio.py
        results = stremio_scrape(provider_url, False, None, media_type, season, episode, fake_item_data, cancel_event)
        streams.extend(results)

    return streams
