from resources.lib.resolvers._common import get_thrax_sources

_LABEL = '[VSE]'


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    params = {'tmdb_id': tmdb_id, 'type': media_type}
    if season: params['season'] = season
    if episode: params['episode'] = episode
    return get_thrax_sources('vsembed/sources', params, _LABEL)
