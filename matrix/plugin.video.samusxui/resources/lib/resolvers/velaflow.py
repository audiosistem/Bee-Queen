# -*- coding: utf-8 -*-
import requests
import xbmc
from resources.lib.resolvers._common import THRAX_BASE, THRAX_HEADERS


def _get(imdb_id, type, season=None, episode=None):
    params = {"imdb_id": imdb_id, "type": type}
    if season:  params["season"]  = season
    if episode: params["episode"] = episode
    try:
        r = requests.get(f"{THRAX_BASE}/velaflow/sources", params=params,
                         headers=THRAX_HEADERS, timeout=20)
        r.raise_for_status()
        return r.json().get("sources", [])
    except Exception as e:
        xbmc.log(f"[VelaFlow] {imdb_id}: {e}", xbmc.LOGERROR)
        return []

def get_movie_sources(imdb_id):          return _get(imdb_id, "movie")
def get_tv_sources(imdb_id, s, e):       return _get(imdb_id, "tv", s, e)
