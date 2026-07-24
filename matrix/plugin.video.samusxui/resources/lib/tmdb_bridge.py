# -*- coding: utf-8 -*-
# Compatibility bridge: expune interfața tmdb/movies + tmdb/tv din samus
# pentru a fi utilizată de player.py fără a modifica structura modulului tmdb.
from resources.lib import tmdb as _t


class movies:
    @staticmethod
    def get_movie_details(tmdb_id):
        return _t.movie_details(tmdb_id)


class tv:
    @staticmethod
    def get_tv_details(tv_id):
        return _t.tv_details(tv_id)

    @staticmethod
    def get_season(tv_id, season):
        return _t.season_details(tv_id, season)


def get_external_ids(tmdb_id, media_type='movie'):
    return _t.get_external_ids(tmdb_id, media_type)


def get_english_title(tmdb_id, media='movie'):
    """Returnează titlul în engleză (lightweight, fără append_to_response)."""
    return _t.text_en(tmdb_id, media)
