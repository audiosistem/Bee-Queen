# -*- coding: utf-8 -*-
"""SIMKL integration — PIN device-code OAuth + scrobble + history sync.

Mirrors the Trakt module so SIMKL works alongside Trakt/Bingebase.

Get your own client_id/secret at:  https://simkl.com/settings/developer/new/
(Or leave the addon-bundled default in place — the user authenticates
through the universal simkl.com/pin code flow either way.)

Endpoints (https://simkl.docs.apiary.io):
  POST  https://api.simkl.com/oauth/pin?client_id=...        -> { user_code, device_code, verification_url, expires_in, interval }
  GET   https://api.simkl.com/oauth/pin/{user_code}?client_id=...  -> { result:'OK', access_token } when authorized
  POST  /scrobble/start | /scrobble/pause | /scrobble/stop   Bearer + simkl-api-key
  POST  /sync/history                                        Bearer + simkl-api-key  (mark items watched)
  GET   /sync/all-items?extended=full&episode_watched_at=yes Bearer + simkl-api-key  (full library)
  GET   /sync/playback/movie  /  /sync/playback/episode      Bearer + simkl-api-key  (continue watching)
"""
import json
import os
import time

import requests
import xbmc
import xbmcgui

from .common import (ADDON, PROFILE_PATH, log, notify, get_setting, get_setting_bool)

API = 'https://api.simkl.com'

# Default app credentials (community SIMKL app — used out-of-the-box).
# Users can override in settings -> SIMKL -> Custom SIMKL client ID/secret.
DEFAULT_CLIENT_ID = 'c8188d4a9dc6e247ffe2113b6ec70ac90168ecc5a79e09ab7f8e6a4cf3992fa7'
DEFAULT_CLIENT_SECRET = '168c6acd0d0533f15c6c6f1133bb1b00a765bd3ea74249f7e1e6b1900210edd9'

TOKEN_FILE = os.path.join(PROFILE_PATH, 'simkl_token.json')
SETTING_KEY = 'simkl_authorization'
USER_AGENT = 'Vidscr/1.4.8'


# ---------- credentials ----------

def _client_id():
    return get_setting('simkl_client_id') or DEFAULT_CLIENT_ID


def _client_secret():
    return get_setting('simkl_client_secret') or DEFAULT_CLIENT_SECRET


def _have_client_id():
    return bool(_client_id())


# ---------- token storage ----------

def _load_token():
    """Load the auth token. Tries the addon setting first (most reliable on
    Android), then falls back to the local JSON file."""
    raw = ADDON.getSetting(SETTING_KEY)
    if raw:
        try:
            return json.loads(raw)
        except Exception as e:
            log('SIMKL: setting payload corrupt (%s) — falling back to file' % e)
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                tok = json.load(f)
            try:
                ADDON.setSetting(SETTING_KEY, json.dumps(tok))
            except Exception:
                pass
            return tok
    except Exception as e:
        log('SIMKL: load token from file failed: %s' % e)
    return None


def _save_token(tok):
    """Persist token to BOTH the addon setting (primary) and the JSON file
    (backup). Returns True on success."""
    if not tok or not tok.get('access_token'):
        log('SIMKL: refusing to save empty token')
        return False
    payload = json.dumps(tok)
    ok_setting = False
    try:
        ADDON.setSetting(SETTING_KEY, payload)
        roundtrip = ADDON.getSetting(SETTING_KEY)
        ok_setting = bool(roundtrip) and 'access_token' in roundtrip
        log('SIMKL: setting save %s (len=%d)' %
            ('OK' if ok_setting else 'FAILED', len(roundtrip) if roundtrip else 0))
    except Exception as e:
        log('SIMKL: setting save exception: %s' % e)
    ok_file = False
    try:
        try:
            os.makedirs(PROFILE_PATH, exist_ok=True)
        except Exception:
            pass
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            f.write(payload)
        ok_file = os.path.exists(TOKEN_FILE) and os.path.getsize(TOKEN_FILE) > 0
        log('SIMKL: file save %s (path=%s)' %
            ('OK' if ok_file else 'FAILED', TOKEN_FILE))
    except Exception as e:
        log('SIMKL: file save exception: %s' % e)
    return ok_setting or ok_file


def _clear_token():
    try:
        ADDON.setSetting(SETTING_KEY, '')
    except Exception:
        pass
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
    except Exception:
        pass


def is_authenticated():
    tok = _load_token()
    return bool(tok and tok.get('access_token'))


# ---------- HTTP helpers ----------

def _headers(auth=False):
    h = {
        'Content-Type': 'application/json',
        'simkl-api-key': _client_id(),
        'User-Agent': USER_AGENT,
    }
    if auth:
        tok = _load_token() or {}
        if tok.get('access_token'):
            h['Authorization'] = 'Bearer %s' % tok['access_token']
    return h


def _post(path, payload, auth=True, timeout=20):
    if auth and not is_authenticated():
        log('SIMKL POST %s skipped: not authenticated' % path)
        return None
    if not _have_client_id():
        return None
    try:
        r = requests.post(API + path, headers=_headers(auth=auth),
                          data=json.dumps(payload).encode('utf-8'),
                          timeout=timeout)
        if r.status_code in (200, 201, 204):
            try:
                body = r.json()
                return body if body else True
            except Exception:
                return True
        log('SIMKL POST %s -> %s body=%s' % (path, r.status_code, r.text[:300]))
    except Exception as e:
        log('SIMKL POST %s failed: %s' % (path, e))
    return None


def _get(path, params=None, auth=True, timeout=20):
    if auth and not is_authenticated():
        log('SIMKL GET %s skipped: not authenticated' % path)
        return None
    if not _have_client_id():
        return None
    try:
        r = requests.get(API + path, headers=_headers(auth=auth),
                         params=params or {}, timeout=timeout)
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                return {}
        log('SIMKL GET %s -> %s body=%s' % (path, r.status_code, r.text[:300]))
    except Exception as e:
        log('SIMKL GET %s failed: %s' % (path, e))
    return None


# ---------- PIN device-code auth ----------

def authenticate():
    """SIMKL PIN flow. Shows a code + URL to enter at simkl.com/pin."""
    log('SIMKL: starting PIN authentication')
    log('SIMKL: client_id=%s... custom=%s' %
        (_client_id()[:6], bool(get_setting('simkl_client_id'))))
    if not _have_client_id():
        xbmcgui.Dialog().ok(
            'SIMKL — client ID required',
            'You need to register a SIMKL app to use this integration.\n\n'
            '1. Sign up free at [B]simkl.com[/B]\n'
            '2. Open [B]simkl.com/settings/developer/new/[/B]\n'
            '3. Create an app (any name; use [B]urn:ietf:wg:oauth:2.0:oob[/B] as redirect URI)\n'
            '4. Copy the [B]API Key (client_id)[/B]\n'
            '5. Paste it into Vidscr settings -> SIMKL -> "Custom SIMKL client ID"\n\n'
            'Then come back here and tap "Authenticate with SIMKL" again.')
        return

    try:
        r = requests.post(API + '/oauth/pin',
                          headers=_headers(),
                          params={'client_id': _client_id(),
                                  'redirect': 'urn:ietf:wg:oauth:2.0:oob'},
                          data=b'',
                          timeout=20)
        log('SIMKL: /oauth/pin -> %s' % r.status_code)
        if r.status_code != 200:
            log('SIMKL: /oauth/pin body=%s' % r.text[:300])
            notify('SIMKL: PIN request failed (%s)' % r.status_code)
            return
        data = r.json()
    except Exception as e:
        log('SIMKL: /oauth/pin exception: %s' % e)
        notify('SIMKL error: %s' % e)
        return

    user_code = data.get('user_code')
    verify_url = data.get('verification_url') or 'https://simkl.com/pin'
    interval = int(data.get('interval', 5))
    expires_in = int(data.get('expires_in', 900))
    log('SIMKL: pin obtained (user_code=%s expires_in=%d interval=%d)' %
        (user_code, expires_in, interval))

    if not user_code:
        notify('SIMKL: no user_code in response')
        return

    msg = ('Open [B]%s[/B] in any browser and enter the code:\n\n[B]%s[/B]\n\n'
           'Waiting for authorisation... (this dialog will auto-close)') % (verify_url, user_code)

    pd = xbmcgui.DialogProgress()
    pd.create('SIMKL — PIN authentication', msg)

    elapsed = 0
    poll_interval = max(interval, 3)
    while elapsed < expires_in:
        if pd.iscanceled():
            pd.close()
            log('SIMKL: user cancelled authentication')
            return
        xbmc.sleep(poll_interval * 1000)
        elapsed += poll_interval
        try:
            pr = requests.get(API + '/oauth/pin/' + str(user_code),
                              headers=_headers(),
                              params={'client_id': _client_id()},
                              timeout=15)
        except Exception as e:
            log('SIMKL poll exception: %s' % e)
            continue

        if pr.status_code == 200:
            try:
                payload = pr.json() or {}
            except Exception:
                payload = {}
            # SIMKL returns either {'result':'KO'} (still pending) or
            # {'result':'OK','access_token':'...'} on success.
            if payload.get('result') == 'OK' and payload.get('access_token'):
                tok = {
                    'access_token': payload['access_token'],
                    'saved_at': time.time(),
                }
                log('SIMKL: AUTHORISED — saving token')
                saved = _save_token(tok)
                pd.close()
                if saved:
                    try:
                        ADDON.setSetting('simkl_status', 'Authenticated')
                        ADDON.setSetting('simkl_enabled', 'true')
                    except Exception as e:
                        log('SIMKL: setSetting status/enabled failed: %s' % e)
                    if is_authenticated():
                        notify('SIMKL: authentication successful')
                        log('SIMKL: token verified — is_authenticated()=True')
                    else:
                        notify('SIMKL: token saved but not readable — try again')
                        log('SIMKL: WARNING — token saved but is_authenticated() is False')
                else:
                    notify('SIMKL: token NOT saved — check logs / disk space')
                    log('SIMKL: ERROR — _save_token returned False')
                return
            # KO / pending -> keep polling
            continue
        elif pr.status_code in (400, 404, 410, 418, 429):
            pd.close()
            log('SIMKL: poll status %s' % pr.status_code)
            notify('SIMKL: PIN expired / denied (%s)' % pr.status_code)
            return
        else:
            log('SIMKL: unexpected poll status %s body=%s' %
                (pr.status_code, pr.text[:200]))

    pd.close()
    log('SIMKL: authentication timed out (%ds)' % expires_in)
    notify('SIMKL: authentication timed out')


def logout():
    _clear_token()
    try:
        ADDON.setSetting('simkl_status', 'Not authenticated')
    except Exception:
        pass
    notify('SIMKL: signed out')
    log('SIMKL: signed out (setting + file cleared)')


def show_token_status():
    """Diagnostic action — display where the token lives and whether it works."""
    setting_present = bool(ADDON.getSetting(SETTING_KEY))
    file_present = os.path.exists(TOKEN_FILE)
    file_size = os.path.getsize(TOKEN_FILE) if file_present else 0
    tok = _load_token() or {}
    has_access = bool(tok.get('access_token'))
    is_auth = is_authenticated()
    lines = [
        'SIMKL — token status',
        '=' * 40,
        'Setting payload : %s' % ('present (%d chars)' % len(ADDON.getSetting(SETTING_KEY))
                                  if setting_present else 'MISSING'),
        'File payload    : %s' % ('present (%d bytes)' % file_size
                                  if file_present else 'MISSING'),
        'Access token    : %s' % ('YES (%s...)' % tok.get('access_token', '')[:8]
                                  if has_access else 'NO'),
        'is_authenticated: %s' % is_auth,
        'Profile path    : %s' % PROFILE_PATH,
        'Token file path : %s' % TOKEN_FILE,
        'Custom client_id: %s' % bool(get_setting('simkl_client_id')),
        '',
        'If is_authenticated is False but the access token is present,',
        'try Settings → SIMKL → Sign out, then re-authenticate.',
    ]
    xbmcgui.Dialog().textviewer('SIMKL — token status', '\n'.join(lines))


# ---------- Scrobble ----------

def _scrobble_payload(media_type, ids, season=None, episode=None, progress=0.0):
    if media_type == 'movie':
        return {'movie': {'ids': ids}, 'progress': float(progress)}
    return {
        'show': {'ids': ids},
        'episode': {'season': int(season or 0), 'number': int(episode or 0)},
        'progress': float(progress),
    }


def _ids_dict(imdb_id=None, tmdb_id=None):
    ids = {}
    if imdb_id:
        ids['imdb'] = imdb_id
    if tmdb_id:
        ids['tmdb'] = int(tmdb_id) if str(tmdb_id).isdigit() else tmdb_id
    return ids


def scrobble_start(media_type, imdb_id=None, tmdb_id=None, season=None, episode=None, progress=0.0):
    if not (get_setting_bool('simkl_enabled') and get_setting_bool('simkl_scrobble')):
        return
    ids = _ids_dict(imdb_id, tmdb_id)
    if not ids:
        return
    _post('/scrobble/start', _scrobble_payload(media_type, ids, season, episode, progress))


def scrobble_pause(media_type, imdb_id=None, tmdb_id=None, season=None, episode=None, progress=0.0):
    if not (get_setting_bool('simkl_enabled') and get_setting_bool('simkl_scrobble')):
        return
    ids = _ids_dict(imdb_id, tmdb_id)
    if not ids:
        return
    _post('/scrobble/pause', _scrobble_payload(media_type, ids, season, episode, progress))


def scrobble_stop(media_type, imdb_id=None, tmdb_id=None, season=None, episode=None, progress=0.0):
    if not (get_setting_bool('simkl_enabled') and get_setting_bool('simkl_scrobble')):
        return
    ids = _ids_dict(imdb_id, tmdb_id)
    if not ids:
        return
    _post('/scrobble/stop', _scrobble_payload(media_type, ids, season, episode, progress))


# ---------- Mark watched (context menu) ----------

def mark_watched(media_type, imdb_id=None, tmdb_id=None, season=None, episode=None):
    """Force a single mark-as-watched via /sync/history."""
    if not is_authenticated():
        notify('SIMKL: please authenticate first')
        return False
    ids = _ids_dict(imdb_id, tmdb_id)
    if not ids:
        return False
    if media_type == 'movie':
        payload = {'movies': [{'ids': ids}]}
    else:
        payload = {'shows': [{
            'ids': ids,
            'seasons': [{
                'number': int(season or 0),
                'episodes': [{'number': int(episode or 0)}],
            }],
        }]}
    return bool(_post('/sync/history', payload))


# ---------- History sync ----------

def get_watched_movies():
    """Return a set of IMDB / tmdb keys for watched movies."""
    data = _get('/sync/all-items/movies', params={'extended': 'full'}) or {}
    out = set()
    for it in (data.get('movies') or []):
        m = it.get('movie') or {}
        ids = m.get('ids') or {}
        if ids.get('imdb'):
            out.add(ids['imdb'])
        if ids.get('tmdb'):
            out.add('tmdb:%s' % ids['tmdb'])
        # Only count items the user has actually completed.
        # (SIMKL may return plantowatch / dropped too.)
    return out


def get_watched_shows():
    """Return dict { imdb_or_tmdb_key: { season: set(episodes_watched) } }."""
    data = _get('/sync/all-items/shows', params={'extended': 'full',
                                                 'episode_watched_at': 'yes'}) or {}
    out = {}
    for category in ('shows', 'anime'):
        for it in (data.get(category) or []):
            show = it.get('show') or it.get('anime') or {}
            ids = show.get('ids') or {}
            key = ids.get('imdb') or (('tmdb:%s' % ids['tmdb']) if ids.get('tmdb') else None)
            if not key:
                continue
            seasons = {}
            for s in (it.get('seasons') or []):
                sn = s.get('number')
                if sn is None:
                    continue
                seasons[sn] = set(int(e['number']) for e in (s.get('episodes') or [])
                                  if e.get('number') is not None)
            if seasons:
                out[key] = seasons
    return out


def get_playback_movies():
    """Return list of paused movie playbacks (continue watching)."""
    return _get('/sync/playback/movie') or []


def get_playback_episodes():
    """Return list of paused episode playbacks (continue watching)."""
    return _get('/sync/playback/episode') or []


def sync_history():
    """Pull SIMKL watched lists and persist to addon-local watched store."""
    if not is_authenticated():
        notify('SIMKL: not authenticated')
        return
    from . import kodi_db as KDB
    notify('SIMKL: syncing watched history...', time=2000)

    movies = get_watched_movies()
    shows = get_watched_shows()
    if hasattr(KDB, 'bulk_mark_watched_movies'):
        KDB.bulk_mark_watched_movies(movies)
    if hasattr(KDB, 'bulk_mark_watched_episodes'):
        KDB.bulk_mark_watched_episodes(shows)

    # Resume points (paused playbacks). Convert to the same shape Trakt uses
    # so kodi_db.bulk_record_resume_* can store them.
    pb_movies = []
    for it in get_playback_movies():
        m = it.get('movie') or {}
        progress = it.get('progress', 0)
        pb_movies.append({
            'movie': m,
            'progress': progress,
            'paused_at': it.get('paused_at') or it.get('updated_at'),
        })
    pb_eps = []
    for it in get_playback_episodes():
        ep = it.get('episode') or {}
        show = it.get('show') or {}
        progress = it.get('progress', 0)
        pb_eps.append({
            'show': show,
            'episode': {
                'season': ep.get('season') or it.get('season'),
                'number': ep.get('number') or it.get('number'),
                'ids': ep.get('ids') or {},
            },
            'progress': progress,
            'paused_at': it.get('paused_at') or it.get('updated_at'),
        })
    if hasattr(KDB, 'bulk_record_resume_movies'):
        KDB.bulk_record_resume_movies(pb_movies)
    if hasattr(KDB, 'bulk_record_resume_episodes'):
        KDB.bulk_record_resume_episodes(pb_eps)

    notify('SIMKL: synced %d movies, %d shows, %d resume points'
           % (len(movies), len(shows), len(pb_movies) + len(pb_eps)))


# ---------- Add / remove from lists ----------

def _list_payload(media_type, tmdb_id=None, imdb_id=None, status=None):
    ids = _ids_dict(imdb_id, tmdb_id)
    if not ids:
        return None
    entry = {'ids': ids}
    if status:
        entry['to'] = status
    key = 'movies' if media_type == 'movie' else 'shows'
    return {key: [entry]}


def add_to_list(status, media_type, tmdb_id=None, imdb_id=None):
    """status: 'plantowatch' | 'watching' | 'completed' | 'hold' | 'dropped'"""
    if not is_authenticated():
        notify('SIMKL: not authenticated')
        return False
    if status == 'completed':
        return mark_watched(media_type, tmdb_id=tmdb_id, imdb_id=imdb_id)
    payload = _list_payload(media_type, tmdb_id=tmdb_id, imdb_id=imdb_id, status=status)
    if not payload:
        return False
    return bool(_post('/sync/add-to-list', payload))


def remove_from_list(status, media_type, tmdb_id=None, imdb_id=None):
    """Removes an item from SIMKL. 'completed' uses /sync/history/remove,
    all other statuses use /sync/remove-from-list."""
    if not is_authenticated():
        notify('SIMKL: not authenticated')
        return False
    payload = _list_payload(media_type, tmdb_id=tmdb_id, imdb_id=imdb_id)
    if not payload:
        return False
    path = '/sync/history/remove' if status == 'completed' else '/sync/remove-from-list'
    return bool(_post(path, payload))
