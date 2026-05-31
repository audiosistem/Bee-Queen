from resources.lib.resolvers._common import get_thrax_sources

_LABEL = '[HHD]'


def get_sources(tmdb_id, media_type='movie', season=None, episode=None, imdb_id=None):
    params = {'tmdb_id': tmdb_id, 'type': media_type}
    if season: params['season'] = season
    if episode: params['episode'] = episode
    if imdb_id: params['imdb_id'] = imdb_id
    return get_thrax_sources('hydrahd/sources', params, _LABEL)
