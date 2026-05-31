from resources.lib.resolvers._common import get_thrax_sources

_LABEL = '[V]'


def _fetch(tmdb_id, media_type, season=None, episode=None):
    params = {'tmdb_id': tmdb_id, 'type': media_type}
    if season: params['season'] = season
    if episode: params['episode'] = episode
    return get_thrax_sources('vidify/sources', params, _LABEL)


def get_vidify_movie_sources(tmdb_id, imdb_id=None):
    return _fetch(tmdb_id, 'movie')


def get_vidify_tv_episode_sources(tmdb_id, imdb_id, season, episode):
    return _fetch(tmdb_id, 'tv', season, episode)
