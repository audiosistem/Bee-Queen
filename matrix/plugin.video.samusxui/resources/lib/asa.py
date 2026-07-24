# -*- coding: utf-8 -*-
import requests
import xbmc

_BASE = 'https://asa.00696900.xyz'
_PAGE_SIZE = 30

_SESS = requests.Session()
_SESS.headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'


def _get(path, **params):
    try:
        r = _SESS.get(f'{_BASE}{path}', params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        xbmc.log(f'[SamusXUI/ASA] {path}: {e}', xbmc.LOGWARNING)
        return {}


def catalog(catalog_id='recent', skip=0, **extra):
    params = {'skip': skip}
    params.update(extra)
    metas = _get(f'/catalog/porn/{catalog_id}.json', **params).get('metas', [])
    return [_normalize(m) for m in metas]


def stream(asa_id):
    return _get(f'/stream/movie/{asa_id}.json').get('streams', [])


def _normalize(m):
    return {
        'id':            m.get('id', ''),
        'media_type':    'adult',
        'title':         m.get('name', ''),
        'poster_path':   m.get('poster', ''),
        'backdrop_path': m.get('background', '') or m.get('poster', ''),
        'overview':      m.get('description', ''),
        'vote_average':  0,
        'vote_count':    0,
        'genre_ids':     [],
        'genres':        m.get('genres', []),
        'release_date':  m.get('releaseInfo', ''),
        'runtime':       m.get('runtime', ''),
        'cast':          m.get('cast', []),
        'studio':        m.get('studio', ''),
    }
