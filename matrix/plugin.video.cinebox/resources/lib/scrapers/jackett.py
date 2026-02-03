# -*- coding: utf-8 -*-
import requests
import xbmc
import re
import urllib.parse
from .session import USER_AGENT
from ..debug_logger import logger

def scrape(imdb_id, media_type, season, episode, item_data=None, cancel_event=None):
    """Jackett/Prowlarr Scraper for Cinebox.
    Search public instances and improve coverage."""
    if not item_data:
        return []

    title = item_data.get('title')
    original_title = item_data.get('original_title')
    year = item_data.get('year')
    
    if not title:
        return []

    streams = []
    seen_hashes = set()
    
    # List of public instances of Jackett/Prowlarr or similar aggregators
    # As we don't have a user API key, we will focus on using Torrentio
    # with a more aggressive text search configuration.
    
    from .stremio import scrape as stremio_scrape
    
    # Torrentio with all possible providers
    config = "providers=comando,bludv,micoleaodublado,yts,nyaasi,1337x,tgx,rarbg,eztv,torrentgalaxy,magnetdl,horriblesubs,piratebay,kickasstorrents|language=japanese,portuguese,english"
    provider_url = f"https://torrentio.strem.fun/{config}"
    
    # 1. Try normal search by ID
    results = stremio_scrape(provider_url, False, imdb_id, media_type, season, episode, item_data, cancel_event)
    streams.extend(results)
    
    # 2. If there are no results and we have an original title, try text search on Torrentio
    if not streams and original_title and original_title != title:
        xbmc.log(f"[Jackett-Scraper] No results by ID, trying to search by original title: {original_title}", xbmc.LOGINFO)
        # Torrentio supports text search via the /stream/movie/query.json endpoint
        if media_type == 'tvshow':
            query = f"{original_title} S{int(season):02d}E{int(episode):02d}"
        else:
            year = item_data.get('year', '')
            query = f"{original_title} {year}"
        
        # Simulates an item_data without IMDB to force text search in modified stremio.py
        fake_item_data = item_data.copy()
        # Remove IMDB to force title search in stremio.py
        results = stremio_scrape(provider_url, False, None, media_type, season, episode, fake_item_data, cancel_event)
        streams.extend(results)

    return streams
