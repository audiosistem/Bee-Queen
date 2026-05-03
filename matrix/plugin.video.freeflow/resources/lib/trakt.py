# -*- coding: utf-8 -*-
"""Trakt.tv integration for Free Flow.

Implements OAuth Device Authentication (PIN flow), token storage in the
addon's profile dir, and thin API wrappers for the menus exposed under
"My Free Flow":
  - Trending / Popular / Anticipated / Recommendations (movies + shows)
  - Watchlist / Collection / Watched History
  - Liked Lists / My Personal Lists (with create / rename / delete)
  - Add / Remove items from watchlist, collection, history and custom lists
"""
import json
import os
import time

try:
    import xbmc
    import xbmcgui
    import xbmcaddon
    import xbmcvfs
except Exception:  # offline tests
    xbmc = xbmcgui = xbmcaddon = xbmcvfs = None

try:
    import requests
except ImportError:
    requests = None
import urllib.request
import urllib.parse

try:
    from . import debug as _dbg  # type: ignore
except Exception:
    try:
        import debug as _dbg  # type: ignore
    except Exception:
        _dbg = None


CLIENT_ID = '19849909a0f8c9dc632bc5f5c7ccafd19f3e452e2e44fee05b83fd5dc1e77675'
CLIENT_SECRET = 'b5fcd7cb5d9bb963784d11bbf8535bc0d25d46225016191eb48e50792d2155c0'

API_BASE = 'https://api.trakt.tv'
API_VERSION = '2'

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/124.0 Safari/537.36')


# ---------------- token persistence ---------------- #

def _profile_dir():
    if xbmcvfs is None:
        return os.path.join('/tmp', 'plugin.video.freeflow')
    p = xbmcvfs.translatePath(
        'special://profile/addon_data/plugin.video.freeflow/')
    if not xbmcvfs.exists(p):
        xbmcvfs.mkdirs(p)
    return p


def _token_path():
    return os.path.join(_profile_dir(), 'trakt_token.json')


def _load_token():
    p = _token_path()
    if not os.path.exists(p):
        return None
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _save_token(tok):
    try:
        with open(_token_path(), 'w', encoding='utf-8') as f:
            json.dump(tok, f)
    except Exception:
        pass


def _clear_token():
    try:
        os.remove(_token_path())
    except Exception:
        pass


def is_authenticated():
    tok = _load_token()
    return bool(tok and tok.get('access_token'))


# ---------------- HTTP helpers ---------------- #

def _http(method, url, headers=None, json_body=None, timeout=20):
    """Return (status_code, parsed_json_or_text)."""
    hdrs = {'User-Agent': UA, 'Content-Type': 'application/json'}
    if headers:
        hdrs.update(headers)
    body = None
    if json_body is not None:
        body = json.dumps(json_body).encode('utf-8')
    t0 = time.time()
    # Sanitize for logging
    log_hdrs = dict(hdrs)
    if 'Authorization' in log_hdrs:
        log_hdrs['Authorization'] = 'Bearer ***'
    log_body = ''
    if json_body is not None:
        try:
            sanitized = dict(json_body)
            for k in ('client_secret', 'refresh_token', 'token',
                      'access_token', 'code'):
                if k in sanitized:
                    sanitized[k] = '***'
            log_body = json.dumps(sanitized)[:300]
        except Exception:
            log_body = '(unloggable)'
    if _dbg is not None:
        _dbg.dlog('%s %s | hdrs=%s | body=%s' % (
            method, url, sorted(log_hdrs.keys()), log_body),
            level='DEBUG', component='trakt.req')
    try:
        if requests is not None:
            r = requests.request(method, url, headers=hdrs, data=body,
                                 timeout=timeout)
            sc = r.status_code
            if _dbg is not None:
                preview = ''
                try:
                    preview = r.text[:300]
                except Exception:
                    pass
                _dbg.dump_http(method, url, sc, headers=r.headers,
                               body_preview=preview,
                               elapsed_ms=(time.time() - t0) * 1000.0,
                               component='trakt.http')
            try:
                return sc, r.json()
            except Exception:
                return sc, r.text
        req = urllib.request.Request(url, data=body, headers=hdrs,
                                     method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            txt = resp.read().decode('utf-8', errors='ignore')
            sc = resp.status
            if _dbg is not None:
                _dbg.dump_http(method, url, sc,
                               headers=dict(resp.headers),
                               body_preview=txt[:300],
                               elapsed_ms=(time.time() - t0) * 1000.0,
                               component='trakt.http')
            try:
                return sc, json.loads(txt) if txt else {}
            except Exception:
                return sc, txt
    except urllib.request.HTTPError as e:
        try:
            txt = e.read().decode('utf-8', errors='ignore')
            if _dbg is not None:
                _dbg.dump_http(method, url, e.code,
                               body_preview=txt[:300],
                               elapsed_ms=(time.time() - t0) * 1000.0,
                               component='trakt.http')
            return e.code, json.loads(txt) if txt else {}
        except Exception:
            return e.code, {}
    except Exception as e:
        if _dbg is not None:
            _dbg.dlog('%s %s FAILED: %s' % (method, url, e),
                      level='ERROR', component='trakt.http')
        return 0, {'error': str(e)}


def _api_headers(auth=True):
    h = {
        'trakt-api-key': CLIENT_ID,
        'trakt-api-version': API_VERSION,
    }
    if auth:
        tok = _load_token()
        if tok and tok.get('access_token'):
            h['Authorization'] = 'Bearer ' + tok['access_token']
    return h


def _refresh_if_needed():
    tok = _load_token()
    if not tok:
        return False
    if tok.get('expires_at', 0) - time.time() > 600:
        return True  # still valid
    rt = tok.get('refresh_token')
    if not rt:
        return False
    sc, data = _http('POST', API_BASE + '/oauth/token',
                     json_body={
                         'refresh_token': rt,
                         'client_id': CLIENT_ID,
                         'client_secret': CLIENT_SECRET,
                         'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                         'grant_type': 'refresh_token',
                     })
    if sc == 200 and isinstance(data, dict) and data.get('access_token'):
        data['expires_at'] = int(time.time()) + int(
            data.get('expires_in', 7776000))
        _save_token(data)
        return True
    return False


def api_get(path, params=None, auth=True):
    _refresh_if_needed()
    url = API_BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    return _http('GET', url, headers=_api_headers(auth))


def api_post(path, body=None, auth=True):
    _refresh_if_needed()
    return _http('POST', API_BASE + path, headers=_api_headers(auth),
                 json_body=body or {})


def api_delete(path, auth=True):
    _refresh_if_needed()
    return _http('DELETE', API_BASE + path, headers=_api_headers(auth))


# ---------------- device auth ---------------- #

def device_authorize(progress_cb=None, abort_cb=None):
    """Run the full device-code OAuth flow with a Kodi dialog.

    progress_cb(msg) optional, abort_cb() returning True to cancel.
    Returns True on success, False otherwise.
    """
    sc, data = _http('POST', API_BASE + '/oauth/device/code',
                     json_body={'client_id': CLIENT_ID})
    if sc != 200 or not isinstance(data, dict):
        return False
    user_code = data.get('user_code', '')
    verify_url = data.get('verification_url', 'https://trakt.tv/activate')
    device_code = data.get('device_code', '')
    interval = max(1, int(data.get('interval', 5)))
    expires = int(data.get('expires_in', 600))

    if xbmcgui is None:
        return False
    pdialog = xbmcgui.DialogProgress()
    pdialog.create(
        'Trakt Authorisation',
        'On any device, open:\n[B]%s[/B]\n\nAnd enter the code:\n[B]%s[/B]'
        % (verify_url, user_code))

    deadline = time.time() + expires
    success = False
    try:
        while time.time() < deadline:
            if pdialog.iscanceled():
                break
            if abort_cb and abort_cb():
                break
            remaining = int(deadline - time.time())
            try:
                pdialog.update(
                    int((expires - remaining) * 100 / max(1, expires)),
                    'Open: [B]%s[/B]\nEnter code: [B]%s[/B]\n'
                    'Waiting %ds...' % (verify_url, user_code, remaining))
            except Exception:
                pass

            sc, tok = _http('POST', API_BASE + '/oauth/device/token',
                            json_body={
                                'code': device_code,
                                'client_id': CLIENT_ID,
                                'client_secret': CLIENT_SECRET,
                            })
            if sc == 200 and isinstance(tok, dict) and tok.get('access_token'):
                tok['expires_at'] = int(time.time()) + int(
                    tok.get('expires_in', 7776000))
                _save_token(tok)
                success = True
                break
            elif sc == 400:
                # pending - keep polling
                pass
            elif sc == 404:
                break  # invalid code
            elif sc == 409:
                break  # already used
            elif sc == 410:
                break  # expired
            elif sc == 418:
                break  # denied
            elif sc == 429:
                interval = min(interval + 1, 30)

            # sleep with abort awareness
            slept = 0.0
            while slept < interval:
                if pdialog.iscanceled():
                    break
                if abort_cb and abort_cb():
                    break
                time.sleep(0.5)
                slept += 0.5
    finally:
        try:
            pdialog.close()
        except Exception:
            pass
    return success


def sign_out():
    tok = _load_token()
    if tok and tok.get('access_token'):
        try:
            _http('POST', API_BASE + '/oauth/revoke',
                  headers=_api_headers(False),
                  json_body={'token': tok['access_token'],
                             'client_id': CLIENT_ID,
                             'client_secret': CLIENT_SECRET})
        except Exception:
            pass
    _clear_token()


def whoami():
    sc, data = api_get('/users/settings')
    if sc == 200 and isinstance(data, dict):
        u = data.get('user', {})
        return u.get('username') or u.get('name') or 'Trakt user'
    return None


# ---------------- catalogues ---------------- #

def trending(media, limit=40):
    """media: 'movies' or 'shows'."""
    return api_get('/%s/trending' % media,
                   {'limit': limit, 'extended': 'full'}, auth=False)


def popular(media, limit=40):
    return api_get('/%s/popular' % media,
                   {'limit': limit, 'extended': 'full'}, auth=False)


def anticipated(media, limit=40):
    return api_get('/%s/anticipated' % media,
                   {'limit': limit, 'extended': 'full'}, auth=False)


def recommendations(media, limit=40):
    return api_get('/recommendations/%s' % media,
                   {'limit': limit, 'extended': 'full'})


def watchlist(media):
    return api_get('/sync/watchlist/%s' % media,
                   {'extended': 'full'})


def collection(media):
    return api_get('/sync/collection/%s' % media,
                   {'extended': 'full'})


def history(media, limit=80):
    return api_get('/sync/history/%s' % media,
                   {'limit': limit, 'extended': 'full'})


# ---------------- sync (add/remove) ---------------- #

def _ids_payload(media, trakt_id):
    """Build {movies:[{ids:{trakt:N}}]} or {shows:[...]}."""
    key = 'movies' if media == 'movie' else 'shows'
    return {key: [{'ids': {'trakt': int(trakt_id)}}]}


def add_to_watchlist(media, trakt_id):
    return api_post('/sync/watchlist', _ids_payload(media, trakt_id))


def remove_from_watchlist(media, trakt_id):
    return api_post('/sync/watchlist/remove', _ids_payload(media, trakt_id))


def add_to_collection(media, trakt_id):
    return api_post('/sync/collection', _ids_payload(media, trakt_id))


def remove_from_collection(media, trakt_id):
    return api_post('/sync/collection/remove', _ids_payload(media, trakt_id))


def add_to_history(media, trakt_id):
    return api_post('/sync/history', _ids_payload(media, trakt_id))


def remove_from_history(media, trakt_id):
    return api_post('/sync/history/remove', _ids_payload(media, trakt_id))


# ---------------- personal & liked lists ---------------- #

def my_lists():
    return api_get('/users/me/lists')


def liked_lists(limit=80):
    return api_get('/users/likes/lists', {'limit': limit})


def list_items(user, list_id):
    return api_get('/users/%s/lists/%s/items' % (user, list_id),
                   {'extended': 'full'})


def create_list(name, description=''):
    return api_post('/users/me/lists',
                    {'name': name, 'description': description,
                     'privacy': 'private'})


def delete_list(list_id):
    return api_delete('/users/me/lists/%s' % list_id)


def add_to_list(list_id, media, trakt_id):
    return api_post('/users/me/lists/%s/items' % list_id,
                    _ids_payload(media, trakt_id))


def remove_from_list(list_id, media, trakt_id):
    return api_post('/users/me/lists/%s/items/remove' % list_id,
                    _ids_payload(media, trakt_id))


# ---------------- search ---------------- #

def search(query, media='movie,show', limit=50):
    return api_get('/search/%s' % media,
                   {'query': query, 'limit': limit, 'extended': 'full'},
                   auth=False)


# ---------------- normalisation ---------------- #

def normalize(entries):
    """Flatten various Trakt list shapes into a uniform list of:
    {'media': 'movie'|'show', 'title': str, 'year': int|None,
     'trakt_id': int, 'tmdb_id': int|None, 'overview': str}
    """
    out = []
    if not isinstance(entries, list):
        return out
    for e in entries:
        if not isinstance(e, dict):
            continue
        # /movies/trending wraps under 'movie'
        node = None
        media = None
        if 'movie' in e and isinstance(e['movie'], dict):
            node, media = e['movie'], 'movie'
        elif 'show' in e and isinstance(e['show'], dict):
            node, media = e['show'], 'show'
        elif e.get('type') == 'movie' and isinstance(e.get('movie'), dict):
            node, media = e['movie'], 'movie'
        elif e.get('type') == 'show' and isinstance(e.get('show'), dict):
            node, media = e['show'], 'show'
        elif 'ids' in e and ('title' in e):
            # already a flat trakt media object
            media = 'movie' if 'released' in e else 'show'
            node = e
        else:
            continue
        ids = node.get('ids', {}) or {}
        out.append({
            'media': media,
            'title': node.get('title', ''),
            'year': node.get('year'),
            'trakt_id': ids.get('trakt'),
            'tmdb_id': ids.get('tmdb'),
            'imdb_id': ids.get('imdb'),
            'slug': ids.get('slug'),
            'overview': node.get('overview', '') or '',
        })
    return out
