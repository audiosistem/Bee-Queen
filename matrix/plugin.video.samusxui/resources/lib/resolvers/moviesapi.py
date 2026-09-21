from resources.lib.resolvers._common import get_thrax_sources

_LABEL = '[MAP]'


def get_sources(tmdb_id, media_type='movie', season=None, episode=None, imdb_id=None):
    """MoviesAPI — API pe id TMDb, deci nu are nevoie de imdb_id."""
    params = {'tmdb_id': tmdb_id, 'type': media_type}
    if season: params['season'] = season
    if episode: params['episode'] = episode
    return get_thrax_sources('moviesapi/sources', params, _LABEL)
