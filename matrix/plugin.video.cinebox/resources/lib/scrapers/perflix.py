# -*- coding: utf-8 -*-
from .stremio import scrape as stremio_scrape

def scrape(imdb_id, media_type, season, episode, item_data=None, cancel_event=None):
    """Perflix Scraper for Cinebox.
    It uses the Stremio scraper framework."""
    provider_url = "https://peerflix.mov"
    
    # Perflix on Magneto uses the standard Stremio API
    return stremio_scrape(provider_url, False, imdb_id, media_type, season, episode, item_data, cancel_event)
