# -*- coding: utf-8 -*-
import re
import requests
import xbmc

_LABEL    = '[YFX]'
_API      = 'https://enc-dec.app/api'
_DB_API   = 'https://enc-dec.app/db/flix'
_AJAX     = 'https://yflix.to/ajax'
_UA       = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
             'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36')
_HEADERS  = {'User-Agent': _UA, 'Connection': 'keep-alive'}


def _sess():
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


def _encrypt(sess, text):
    r = sess.get(f'{_API}/enc-movies-flix', params={'text': text}, timeout=10)
    r.raise_for_status()
    return r.json()['result']


def _decrypt(sess, text):
    r = sess.post(f'{_API}/dec-movies-flix', json={'text': text}, timeout=10)
    r.raise_for_status()
    return r.json()['result']


def _parse_html(sess, html):
    r = sess.post(f'{_API}/parse-html', json={'text': html}, timeout=10)
    r.raise_for_status()
    return r.json()['result']


def _dec_rapid(sess, text):
    r = sess.post(f'{_API}/dec-rapid', json={'text': text, 'agent': _UA}, timeout=15)
    r.raise_for_status()
    return r.json()['result']


def _find_db(sess, tmdb_id, media_type):
    t = 'movie' if media_type == 'movie' else 'tv'
    r = sess.get(f'{_DB_API}/find', params={'tmdb_id': tmdb_id, 'type': t}, timeout=10)
    r.raise_for_status()
    results = r.json()
    return results[0] if results else None


def _rapid_sources(sess, embed_url):
    media_url = re.sub(r'/e2?/', '/media/', embed_url)
    r = sess.get(media_url, timeout=15)
    r.raise_for_status()
    encrypted = r.json().get('result', '')
    if not encrypted:
        return []
    rapid = _dec_rapid(sess, encrypted)
    if not isinstance(rapid, dict):
        return []
    return [s['file'] for s in rapid.get('sources', []) if s.get('file')]


def _servers_for_eid(sess, eid):
    enc_eid = _encrypt(sess, eid)
    r = sess.get(f'{_AJAX}/links/list', params={'eid': eid, '_': enc_eid}, timeout=15)
    r.raise_for_status()
    raw_html = r.json().get('result', '')
    parsed = _parse_html(sess, raw_html)
    lids = []
    for stype, sdict in parsed.items():
        for skey, sval in sdict.items():
            lid = sval.get('lid')
            if lid:
                lids.append(lid)
    return lids


def _resolve_lid(sess, lid):
    enc_lid = _encrypt(sess, lid)
    r = sess.get(f'{_AJAX}/links/view', params={'id': lid, '_': enc_lid}, timeout=15)
    r.raise_for_status()
    enc_embed = r.json().get('result', '')
    decrypted = _decrypt(sess, enc_embed)
    if not isinstance(decrypted, dict):
        return []
    url = decrypted.get('url', '')
    if 'rapidshare' in url:
        return _rapid_sources(sess, url)
    return []


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        sess = _sess()

        db = _find_db(sess, tmdb_id, media_type)
        if not db:
            xbmc.log(f'{_LABEL} nu în DB pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []

        info = db.get('info', {})
        episodes = db.get('episodes', {})

        s_key = str(season or 1)
        e_key = str(episode or 1)
        ep_data = (episodes.get(s_key) or {}).get(e_key)
        if not ep_data:
            xbmc.log(f'{_LABEL} episod S{season}E{episode} negăsit pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []

        eid = ep_data.get('eid')
        if not eid:
            return []

        lids = _servers_for_eid(sess, eid)
        m3u8s = []
        seen = set()
        for lid in lids:
            try:
                for url in _resolve_lid(sess, lid):
                    if url not in seen:
                        seen.add(url)
                        m3u8s.append(url)
            except Exception as e:
                xbmc.log(f'{_LABEL} lid={lid} eroare: {e}', xbmc.LOGWARNING)

    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGERROR)
        return []

    sources = []
    for url in m3u8s:
        sources.append({
            'url':        f'{url}|User-Agent={_UA}',
            'provider':   _LABEL,
            'quality':    '1080p',
            'title_line': 'YFlix',
            'direct':     True,
        })

    xbmc.log(f'{_LABEL} {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return sources
