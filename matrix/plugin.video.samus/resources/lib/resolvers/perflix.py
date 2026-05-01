# -*- coding: utf-8 -*-
from .stremio_client import get_movie_sources as _movie, get_tv_sources as _tv

_BASE = 'https://peerflix.mov'
_LABEL = '[PFX]'


def get_movie_sources(imdb_id):
    return _movie(_BASE, imdb_id, _LABEL)


def get_tv_sources(imdb_id, season, episode):
    return _tv(_BASE, imdb_id, season, episode, _LABEL)
