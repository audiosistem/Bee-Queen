from resources.lib.resolvers._common import get_thrax_sources

_LABEL = '[SIMDB]'


def get_sources(imdb_id, media_type='movie', season=None, episode=None):
    params = {'imdb_id': imdb_id, 'type': media_type}
    if season: params['season'] = season
    if episode: params['episode'] = episode
    return get_thrax_sources('streamimdb/resolve', params, _LABEL)
