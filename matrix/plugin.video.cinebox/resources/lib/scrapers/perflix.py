# -*- coding: utf-8 -*-
from .stremio import scrape as stremio_scrape

def scrape(imdb_id, media_type, season, episode, item_data=None, cancel_event=None):
    """
    Scraper Perflix para Cinebox.
    Utiliza a estrutura do scraper Stremio.
    """
    provider_url = "https://peerflix.mov"
    
    # O Perflix no Magneto usa a API de Stremio padrão
    return stremio_scrape(provider_url, False, imdb_id, media_type, season, episode, item_data, cancel_event)
