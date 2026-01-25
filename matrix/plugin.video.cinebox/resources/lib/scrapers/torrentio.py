# -*- coding: utf-8 -*-
from .stremio import scrape as stremio_scrape

def scrape(imdb_id, media_type, season, episode, item_data=None):
    """
    Scraper Torrentio Otimizado para Cinebox.
    Configuração baseada no Magneto: Comando, BluDV, MicoLeaoDublado, YTS, NyaaSi, 1337x.
    Idiomas: Japanese, Portuguese, English.
    """
    config = "providers=comando,bludv,micoleaodublado,yts,nyaasi,1337x,tgx,rarbg,eztv,torrentgalaxy|language=japanese,portuguese,english"
    provider_url = f"https://torrentio.strem.fun/{config}"
    
    # Melhoria: Passar o item_data completo para melhor geração de títulos
    return stremio_scrape(provider_url, False, imdb_id, media_type, season, episode, item_data)
