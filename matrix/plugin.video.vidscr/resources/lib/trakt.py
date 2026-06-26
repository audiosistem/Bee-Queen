# -*- coding: utf-8 -*-
"""Trakt integration — device-code OAuth + scrobble + history sync.

v1.4.8:
  * Token is now persisted to BOTH the addon settings (``trakt_authorization``)
    and the local JSON file. The setting is the primary source of truth; the
    file is a redundant backup. This fixes the "Authorises but token never
    saved (keeps asking)" bug on Android where the JSON file could vanish
    between plugin invocations.
  * Detailed logging at every step of the device-code flow so the addon's
    debug log makes it obvious where authentication failed.
  * HTTP 409 ("already used") is now handled correctly.
  * Token integrity is verified after writing — if the round-trip fails the
    user is warned with a notification instead of silently giving up.

Get your own client_id/secret at:  https://trakt.tv/oauth/applications
(Or leave the addon-bundled defaults in place — the user authenticates
through the universal trakt.tv/activate code flow either way.)
"""
import json
import os
import time

import requests
import xbmc
import xbmcgui

from .common import (ADDON, PROFILE_PATH, log, notify,
                     get_setting, get_setting_bool)

API = 'https://api.trakt.tv'

# Default app credentials (community Trakt app for device code flow).
# Users can override in settings -> Trakt -> Custom Trakt client ID/secret.
DEFAULT_CLIENT_ID = 'c126f684dfaf737638e14c5515bab08b98fad26feba74a3fcb09ebb29f09b41a'
DEFAULT_CLIENT_SECRET = '7c5f32152e2ba2043156b4de989438cb8ae1269c7bcb9237475920e79d28b533'

TOKEN_FILE = os.path.join(PROFILE_PATH, 'trakt_token.json')
SETTING_KEY = 'trakt_authorization'


def _client_id():
    return get_setting('trakt_client_id') or DEFAULT_CLIENT_ID


def _client_secret():
    return get_setting('trakt_client_secret') or DEFAULT_CLIENT_SECRET


def _headers(auth=False):
    h = {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': _client_id(),
        'User-Agent': 'Vidscr/1.4.8',
    }
    if auth:
        tok = _load_token()
        if tok and tok.get('access_token'):
            h['Authorization'] = 'Bearer %s' % tok['access_token']
    return h


def _load_token():
    """Load the auth token. Tries the addon setting first (most reliable on
    Android), then falls back to the local JSON file."""
    # 1. Try addon setting
    raw = ADDON.getSetting(SETTING_KEY)
    if raw:
        try:
            return json.loads(raw)
        except Exception as e:
            log('Trakt: setting payload corrupt (%s) — falling back to file' % e)
    # 2. Try the JSON file
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                tok = json.load(f)
            # If we got a token from the file but the setting was empty, mirror
            # it to the setting so future reads succeed even if the file vanishes.
            try:
                ADDON.setSetting(SETTING_KEY, json.dumps(tok))
            except Exception:
                pass
            return tok
    except Exception as e:
        log('Trakt: load token from file failed: %s' % e)
    return None


def _save_token(tok):
    """Persist token to BOTH the addon setting (primary) and the JSON file
    (backup). Returns True on success."""
    if not tok or not tok.get('access_token'):
        log('Trakt: refusing to save empty token')
        return False
    payload = json.dumps(tok)
    ok_setting = False
    try:
        ADDON.setSetting(SETTING_KEY, payload)
        # Verify round-trip
        roundtrip = ADDON.getSetting(SETTING_KEY)
        ok_setting = bool(roundtrip) and 'access_token' in roundtrip
        log('Trakt: setting save %s (len=%d)' %
            ('OK' if ok_setting else 'FAILED', len(roundtrip) if roundtrip else 0))
    except Exception as e:
        log('Trakt: setting save exception: %s' % e)
    ok_file = False
    try:
        # Make sure the profile dir exists (xbmcvfs created it at import time
        # but on Android the path can be flaky).
        try:
            os.makedirs(PROFILE_PATH, exist_ok=True)
        except Exception:
            pass
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            f.write(payload)
        ok_file = os.path.exists(TOKEN_FILE) and os.path.getsize(TOKEN_FILE) > 0
        log('Trakt: file save %s (path=%s)' %
            ('OK' if ok_file else 'FAILED', TOKEN_FILE))
    except Exception as e:
        log('Trakt: file save exception: %s' % e)
    return ok_setting or ok_file


def is_authenticated():
    tok = _load_token()
    if not tok or not tok.get('access_token'):
        return False
    if tok.get('expires_at', 0) < time.time() + 60:
        log('Trakt: token expired or expiring soon — attempting refresh')
        return _refresh_token(tok)
    return True


def _refresh_token(tok):
    if not tok.get('refresh_token'):
        log('Trakt: no refresh_token available — must re-authenticate')
        _wipe_token('no refresh_token')
        return False
    try:
        r = requests.post(API + '/oauth/token', headers=_headers(),
                          data=json.dumps({
                              'refresh_token': tok['refresh_token'],
                              'client_id': _client_id(),
                              'client_secret': _client_secret(),
                              'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                              'grant_type': 'refresh_token',
                          }), timeout=20)
        if r.status_code == 200:
            data = r.json()
            data['expires_at'] = time.time() + int(data.get('expires_in', 7776000))
            _save_token(data)
            log('Trakt: token refreshed successfully')
            return True
        log('Trakt refresh failed: %s body=%s' % (r.status_code, r.text[:300]))
        # 401/403 = refresh token is dead; wipe and force re-auth so the user
        # gets a clear "please re-authenticate" notification instead of silent
        # failure on every subsequent scrobble / list call.
        if r.status_code in (400, 401, 403):
            _wipe_token('refresh HTTP %s' % r.status_code)
            notify('Trakt: session expired — please re-authenticate', time=6000)
    except Exception as e:
        log('Trakt refresh exception: %s' % e)
    return False


def _wipe_token(reason=''):
    """Drop the stored token so the next is_authenticated() returns False and
    the user is prompted to re-authenticate."""
    try:
        ADDON.setSetting(SETTING_KEY, '')
    except Exception:
        pass
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
    except Exception:
        pass
    try:
        ADDON.setSetting('trakt_status', 'Session expired — re-authenticate')
    except Exception:
        pass
    log('Trakt: token wiped (%s)' % reason)


def authenticate():
    """Device-code OAuth flow. Shows a code + URL to enter at trakt.tv/activate."""
    log('Trakt: starting device-code authentication')
    log('Trakt: client_id=%s... custom=%s' %
        (_client_id()[:6], bool(get_setting('trakt_client_id'))))

    try:
        r = requests.post(API + '/oauth/device/code', headers=_headers(),
                          data=json.dumps({'client_id': _client_id()}), timeout=20)
        log('Trakt: device/code -> %s' % r.status_code)
        if r.status_code != 200:
            log('Trakt: device/code body=%s' % r.text[:400])
            notify('Trakt: device code request failed (%s)' % r.status_code)
            return
        data = r.json()
    except Exception as e:
        log('Trakt: device/code exception: %s' % e)
        notify('Trakt error: %s' % e)
        return

    user_code = data.get('user_code')
    verify_url = data.get('verification_url', 'https://trakt.tv/activate')
    interval = int(data.get('interval', 5))
    expires_in = int(data.get('expires_in', 600))
    device_code = data.get('device_code')
    log('Trakt: device code obtained (user_code=%s expires_in=%d interval=%d)' %
        (user_code, expires_in, interval))

    msg = ('Open [B]%s[/B] in any browser and enter the code:\n\n[B]%s[/B]\n\n'
           'Waiting for authorisation... (this dialog will auto-close)') % (verify_url, user_code)

    pd = xbmcgui.DialogProgress()
    pd.create('Trakt — device authentication', msg)

    elapsed = 0
    poll_interval = max(interval, 3)
    while elapsed < expires_in:
        if pd.iscanceled():
            pd.close()
            log('Trakt: user cancelled authentication')
            return
        xbmc.sleep(poll_interval * 1000)
        elapsed += poll_interval
        try:
            pr = requests.post(API + '/oauth/device/token', headers=_headers(),
                               data=json.dumps({
                                   'code': device_code,
                                   'client_id': _client_id(),
                                   'client_secret': _client_secret(),
                               }), timeout=20)
        except Exception as e:
            log('Trakt poll exception: %s' % e)
            continue

        if pr.status_code == 200:
            try:
                tok = pr.json()
            except Exception as e:
                log('Trakt: failed to parse token JSON: %s body=%s' %
                    (e, pr.text[:300]))
                pd.close()
                notify('Trakt: bad token response')
                return
            tok['expires_at'] = time.time() + int(tok.get('expires_in', 7776000))
            log('Trakt: AUTHORISED — saving token (expires_in=%s)' %
                tok.get('expires_in'))
            saved = _save_token(tok)
            pd.close()
            if saved:
                try:
                    ADDON.setSetting('trakt_status', 'Authenticated')
                    ADDON.setSetting('trakt_enabled', 'true')
                except Exception as e:
                    log('Trakt: setSetting status/enabled failed: %s' % e)
                # Confirm by reading back
                if is_authenticated():
                    notify('Trakt: authentication successful')
                    log('Trakt: token verified — is_authenticated()=True')
                else:
                    notify('Trakt: token saved but not readable — try again')
                    log('Trakt: WARNING — token saved but is_authenticated() is False')
            else:
                notify('Trakt: token NOT saved — check logs / disk space')
                log('Trakt: ERROR — _save_token returned False')
            return
        elif pr.status_code == 400:
            # Pending — keep polling
            continue
        elif pr.status_code in (404, 410, 418, 429, 409):
            pd.close()
            reasons = {404: 'invalid code', 409: 'code already used',
                       410: 'expired', 418: 'denied', 429: 'rate limited'}
            r_msg = reasons.get(pr.status_code, 'error')
            log('Trakt: poll status %s — %s' % (pr.status_code, r_msg))
            notify('Trakt: %s (%s)' % (r_msg, pr.status_code))
            return
        else:
            log('Trakt: unexpected poll status %s body=%s' %
                (pr.status_code, pr.text[:200]))

    pd.close()
    log('Trakt: authentication timed out (%ds)' % expires_in)
    notify('Trakt: authentication timed out')


def logout():
    try:
        ADDON.setSetting(SETTING_KEY, '')
    except Exception:
        pass
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
    except Exception:
        pass
    try:
        ADDON.setSetting('trakt_status', 'Not authenticated')
    except Exception:
        pass
    notify('Trakt: signed out')
    log('Trakt: signed out (setting + file cleared)')


def show_token_status():
    """Diagnostic action — display where the token lives and whether it works."""
    setting_present = bool(ADDON.getSetting(SETTING_KEY))
    file_present = os.path.exists(TOKEN_FILE)
    file_size = os.path.getsize(TOKEN_FILE) if file_present else 0
    tok = _load_token() or {}
    has_access = bool(tok.get('access_token'))
    expires_at = tok.get('expires_at', 0)
    if expires_at:
        secs = int(expires_at - time.time())
        if secs > 0:
            d, rem = divmod(secs, 86400)
            h, _ = divmod(rem, 3600)
            expiry_human = '%dd %dh remaining' % (d, h)
        else:
            expiry_human = 'EXPIRED %d s ago' % -secs
    else:
        expiry_human = '(none)'

    is_auth = is_authenticated()
    lines = [
        'Trakt — token status',
        '=' * 40,
        'Setting payload : %s' % ('present (%d chars)' % len(ADDON.getSetting(SETTING_KEY))
                                  if setting_present else 'MISSING'),
        'File payload    : %s' % ('present (%d bytes)' % file_size
                                  if file_present else 'MISSING'),
        'Access token    : %s' % ('YES (%s...)' % tok.get('access_token', '')[:8]
                                  if has_access else 'NO'),
        'Refresh token   : %s' % ('YES' if tok.get('refresh_token') else 'NO'),
        'Expires         : %s' % expiry_human,
        'is_authenticated: %s' % is_auth,
        'Profile path    : %s' % PROFILE_PATH,
        'Token file path : %s' % TOKEN_FILE,
        'Custom client_id: %s' % bool(get_setting('trakt_client_id')),
        '',
        'If is_authenticated is False but the access token is present,',
        'try Settings → Trakt → Sign out, then re-authenticate.',
    ]
    xbmcgui.Dialog().textviewer('Trakt — token status', '\n'.join(lines))


def _post(path, payload):
    if not is_authenticated():
        log('Trakt POST %s skipped: not authenticated' % path)
        return None
    try:
        r = requests.post(API + path, headers=_headers(auth=True),
                          data=json.dumps(payload), timeout=20)
        if r.status_code in (200, 201, 204):
            try:
                body = r.json()
                # An empty / 204 response is still a success.
                return body if body else True
            except Exception:
                return True
        # On 401 wipe the token so the user gets a clear "re-auth" prompt
        # instead of silent failure forever after.
        if r.status_code == 401:
            log('Trakt %s -> 401 unauthorised body=%s' % (path, r.text[:300]))
            _wipe_token('POST 401')
            notify('Trakt: session expired — please re-authenticate', time=6000)
            return None
        log('Trakt %s -> %s body=%s' % (path, r.status_code, r.text[:300]))
    except Exception as e:
        log('Trakt POST %s failed: %s' % (path, e))
    return None


def _get(path, params=None):
    if not is_authenticated():
        log('Trakt GET %s skipped: not authenticated' % path)
        return None
    try:
        r = requests.get(API + path, headers=_headers(auth=True),
                         params=params or {}, timeout=20)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 401:
            log('Trakt GET %s -> 401 unauthorised body=%s' % (path, r.text[:300]))
            _wipe_token('GET 401')
            notify('Trakt: session expired — please re-authenticate', time=6000)
            return None
        log('Trakt GET %s -> %s body=%s' % (path, r.status_code, r.text[:300]))
    except Exception as e:
        log('Trakt GET %s failed: %s' % (path, e))
    return None


def get_all_paginated(path, params=None, per_page=100, hard_cap=5000):
    """Auto-paginate a Trakt list endpoint until we've gathered everything.

    Trakt's pagination contract: every list endpoint accepts ``limit`` and
    ``page`` query params; the response is always a top-level JSON array
    (not wrapped). We page until either we hit ``hard_cap`` or the server
    returns fewer items than ``per_page`` (the last page).

    Note: ``per_page`` defaults to 100, which is the Trakt-recommended
    maximum. Larger values (1000) sometimes work but get silently capped
    at 100 on many list endpoints (watchlist / collection / favorites /
    personal list items), which is exactly the bug rogermae hit: passing
    ``limit=500`` returned only ~100 items per call. Honest pagination
    with limit=100 + auto-loop gets everything.
    """
    if not is_authenticated():
        return []
    out = []
    page = 1
    p = dict(params or {})
    p['limit'] = per_page
    while True:
        p['page'] = page
        try:
            r = requests.get(API + path, headers=_headers(auth=True),
                             params=p, timeout=25)
        except Exception as e:
            log('Trakt paginated GET %s failed: %s' % (path, e))
            break
        if r.status_code == 401:
            log('Trakt paginated GET %s -> 401' % path)
            _wipe_token('paginated 401')
            notify('Trakt: session expired — please re-authenticate', time=6000)
            return out
        if r.status_code != 200:
            log('Trakt paginated GET %s -> %s body=%s'
                % (path, r.status_code, r.text[:200]))
            break
        try:
            chunk = r.json() or []
        except Exception:
            chunk = []
        if not isinstance(chunk, list):
            # Some endpoints (sync/last_activities) return objects — bail.
            return chunk
        if not chunk:
            break
        out.extend(chunk)
        # If the server returned fewer than per_page items, we're done.
        if len(chunk) < per_page:
            break
        # Server-reported pagination via headers — bail if we've hit it.
        try:
            total_pages = int(r.headers.get('X-Pagination-Page-Count', '0'))
            if total_pages and page >= total_pages:
                break
        except Exception:
            pass
        if len(out) >= hard_cap:
            log('Trakt paginated GET %s hit hard_cap=%d' % (path, hard_cap))
            break
        page += 1
    return out


# ---------- Scrobble ----------

def _scrobble_payload(media_type, ids, season=None, episode=None, progress=0.0):
    if media_type == 'movie':
        return {'movie': {'ids': ids}, 'progress': float(progress)}
    return {
        'show': {'ids': ids},
        'episode': {'season': int(season or 0), 'number': int(episode or 0)},
        'progress': float(progress),
    }


def scrobble_start(media_type, imdb_id=None, tmdb_id=None, season=None, episode=None, progress=0.0):
    if not (get_setting_bool('trakt_enabled') and get_setting_bool('trakt_scrobble')):
        return
    ids = {}
    if imdb_id:
        ids['imdb'] = imdb_id
    if tmdb_id:
        ids['tmdb'] = int(tmdb_id) if str(tmdb_id).isdigit() else tmdb_id
    if not ids:
        return
    _post('/scrobble/start', _scrobble_payload(media_type, ids, season, episode, progress))


def scrobble_pause(media_type, imdb_id=None, tmdb_id=None, season=None, episode=None, progress=0.0):
    if not (get_setting_bool('trakt_enabled') and get_setting_bool('trakt_scrobble')):
        return
    ids = {}
    if imdb_id:
        ids['imdb'] = imdb_id
    if tmdb_id:
        ids['tmdb'] = int(tmdb_id) if str(tmdb_id).isdigit() else tmdb_id
    if not ids:
        return
    _post('/scrobble/pause', _scrobble_payload(media_type, ids, season, episode, progress))


def scrobble_stop(media_type, imdb_id=None, tmdb_id=None, season=None, episode=None, progress=0.0):
    if not (get_setting_bool('trakt_enabled') and get_setting_bool('trakt_scrobble')):
        return
    ids = {}
    if imdb_id:
        ids['imdb'] = imdb_id
    if tmdb_id:
        ids['tmdb'] = int(tmdb_id) if str(tmdb_id).isdigit() else tmdb_id
    if not ids:
        return
    _post('/scrobble/stop', _scrobble_payload(media_type, ids, season, episode, progress))


# ---------- History sync ----------

def get_watched_movies():
    """Return a set of IMDB ids of movies the user has marked as watched on Trakt."""
    data = _get('/sync/watched/movies') or []
    out = set()
    for it in data:
        ids = (it.get('movie') or {}).get('ids') or {}
        if ids.get('imdb'):
            out.add(ids['imdb'])
        if ids.get('tmdb'):
            out.add('tmdb:%s' % ids['tmdb'])
    return out


def get_watched_shows():
    """Return dict { imdb_or_tmdb_key: { season: set(episodes_watched) } }."""
    data = _get('/sync/watched/shows') or []
    out = {}
    for it in data:
        show_ids = (it.get('show') or {}).get('ids') or {}
        key = show_ids.get('imdb') or ('tmdb:%s' % show_ids['tmdb']) if show_ids.get('tmdb') else None
        if not key:
            continue
        seasons = {}
        for s in it.get('seasons', []):
            sn = s.get('number')
            seasons[sn] = set(e.get('number') for e in s.get('episodes', []) if e.get('number'))
        out[key] = seasons
    return out


def sync_history():
    """Pull Trakt watched lists and persist to addon-local watched store."""
    if not is_authenticated():
        notify('Trakt: not authenticated')
        return
    from . import kodi_db as KDB
    notify('Trakt: syncing watched history...', time=2000)
    movies = get_watched_movies()
    shows = get_watched_shows()
    KDB.bulk_mark_watched_movies(movies)
    KDB.bulk_mark_watched_episodes(shows)

    # Also pull active resume points so Continue Watching is populated.
    pb_movies = _get('/sync/playback/movies') or []
    pb_eps = _get('/sync/playback/episodes') or []
    KDB.bulk_record_resume_movies(pb_movies)
    KDB.bulk_record_resume_episodes(pb_eps)

    notify('Trakt: synced %d movies, %d shows, %d resume points'
           % (len(movies), len(shows), len(pb_movies) + len(pb_eps)))


# ---------- Add / remove from lists ----------

def _ids_payload(media_type, tmdb_id=None, imdb_id=None):
    ids = {}
    if imdb_id:
        ids['imdb'] = imdb_id
    if tmdb_id:
        ids['tmdb'] = int(tmdb_id) if str(tmdb_id).isdigit() else tmdb_id
    if not ids:
        return None
    key = 'movies' if media_type == 'movie' else 'shows'
    return {key: [{'ids': ids}]}


def add_to_list(list_name, media_type, tmdb_id=None, imdb_id=None):
    """list_name: 'watchlist' | 'collection' | 'favorites'"""
    if not is_authenticated():
        notify('Trakt: not authenticated')
        return False
    payload = _ids_payload(media_type, tmdb_id=tmdb_id, imdb_id=imdb_id)
    if not payload:
        return False
    if list_name == 'favorites':
        path = '/users/me/favorites'
    else:
        path = '/sync/%s' % list_name
    return bool(_post(path, payload))


def remove_from_list(list_name, media_type, tmdb_id=None, imdb_id=None):
    if not is_authenticated():
        notify('Trakt: not authenticated')
        return False
    payload = _ids_payload(media_type, tmdb_id=tmdb_id, imdb_id=imdb_id)
    if not payload:
        return False
    if list_name == 'favorites':
        path = '/users/me/favorites/remove'
    else:
        path = '/sync/%s/remove' % list_name
    return bool(_post(path, payload))


def add_to_personal_list(slug, media_type, tmdb_id=None, imdb_id=None):
    """Add a movie / show to one of the user's personal Trakt lists."""
    if not is_authenticated():
        notify('Trakt: not authenticated')
        return False
    payload = _ids_payload(media_type, tmdb_id=tmdb_id, imdb_id=imdb_id)
    if not payload:
        return False
    return bool(_post('/users/me/lists/%s/items' % slug, payload))


def remove_from_personal_list(slug, media_type, tmdb_id=None, imdb_id=None):
    """Remove a movie / show from one of the user's personal Trakt lists."""
    if not is_authenticated():
        notify('Trakt: not authenticated')
        return False
    payload = _ids_payload(media_type, tmdb_id=tmdb_id, imdb_id=imdb_id)
    if not payload:
        return False
    return bool(_post('/users/me/lists/%s/items/remove' % slug, payload))


def get_personal_lists():
    """Return the user's personal Trakt lists (id, name, slug)."""
    if not is_authenticated():
        return []
    return _get('/users/me/lists') or []
