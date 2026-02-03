# -*- coding: utf-8 -*-
from .stremio import scrape as stremio_scrape

def scrape(imdb_id, media_type, season, episode, item_data=None):
    """Torrent Scraper Optimized for Cinebox.
    Magneto-based configuration: Commando, BluDV, MicoLeaoDublado, YTS, NyaaSi, 1337x.
    Languages: Japanese, Portuguese, English."""
    config = "providers=comando,bludv,micoleaodublado,yts,nyaasi,1337x,tgx,rarbg,eztv,torrentgalaxy|language=japanese,portuguese,english"
    provider_url = f"https://torrentio.strem.fun/{config}"
    
    # Improvement: Pass the full item_data for better title generation
    return stremio_scrape(provider_url, False, imdb_id, media_type, season, episode, item_data)
