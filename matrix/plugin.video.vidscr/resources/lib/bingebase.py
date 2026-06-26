# -*- coding: utf-8 -*-
"""Bingebase integration — device-code authorization + webhook scrobble + sync.

Mirrors the official Bingebase Kodi addon (script.bingebase) endpoints:
  POST https://bingebase.com/api/v1/kodi/device/code   -> { device_code, user_code, expires_in, interval }
  POST https://bingebase.com/api/v1/kodi/device/token  -> { access_token }   (body: {"device_code": ...})
  POST https://bingebase.com/webhooks/kodi/<token>     scrobble payload (no auth header — token is in path)
  POST https://bingebase.com/api/v1/kodi/import        Bearer  body: {movies:[...], episodes:[...]}
  GET  https://bingebase.com/api/v1/kodi/export        Bearer  ?since=ISO-8601

Activation page shown to user: https://bingebase.com/activate
"""
import json
import os
import time

import requests
import xbmc
import xbmcgui

from .common import (ADDON, PROFILE_PATH, log, notify, get_setting, get_setting_bool)

BASE_URL = 'https://bingebase.com'
DEVICE_CODE_URL = '%s/api/v1/kodi/device/code' % BASE_URL
DEVICE_TOKEN_URL = '%s/api/v1/kodi/device/token' % BASE_URL
IMPORT_URL = '%s/api/v1/kodi/import' % BASE_URL
EXPORT_URL = '%s/api/v1/kodi/export' % BASE_URL

TOKEN_FILE = os.path.join(PROFILE_PATH, 'bingebase_token.json')
SETTING_KEY = 'bingebase_authorization'
USER_AGENT = 'Vidscr/1.4.8 (script.bingebase-compatible)'


# ---------- token storage ----------

def _load_token():
    """Load the auth token. Tries the addon setting first (most reliable on
    Android), then falls back to the local JSON file."""
    raw = ADDON.getSetting(SETTING_KEY)
    if raw:
        try:
            return json.loads(raw)
        except Exception as e:
            log('Bingebase: setting payload corrupt (%s) — falling back to file' % e)
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
        log('Bingebase: load token from file failed: %s' % e)
    return None


def _save_token(tok):
    """Persist token to BOTH the addon setting (primary) and the JSON file
    (backup). Returns True on success."""
    if not tok or not tok.get('access_token'):
        log('Bingebase: refusing to save empty token')
        return False
    payload = json.dumps(tok)
    ok_setting = False
    try:
        ADDON.setSetting(SETTING_KEY, payload)
        roundtrip = ADDON.getSetting(SETTING_KEY)
        ok_setting = bool(roundtrip) and 'access_token' in roundtrip
        log('Bingebase: setting save %s (len=%d)' %
            ('OK' if ok_setting else 'FAILED', len(roundtrip) if roundtrip else 0))
    except Exception as e:
        log('Bingebase: setting save exception: %s' % e)
    ok_file = False
    try:
        try:
            os.makedirs(PROFILE_PATH, exist_ok=True)
        except Exception:
            pass
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            f.write(payload)
        ok_file = os.path.exists(TOKEN_FILE) and os.path.getsize(TOKEN_FILE) > 0
        log('Bingebase: file save %s (path=%s)' %
            ('OK' if ok_file else 'FAILED', TOKEN_FILE))
    except Exception as e:
        log('Bingebase: file save exception: %s' % e)
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


def _access_token():
    tok = _load_token()
    return (tok or {}).get('access_token')


def _webhook_url():
    tok = _load_token() or {}
    if tok.get('webhook_url'):
        return tok['webhook_url']
    at = tok.get('access_token')
    return '%s/webhooks/kodi/%s' % (BASE_URL, at) if at else None


def is_authenticated():
    return bool(_access_token())


# ---------- HTTP helpers ----------

def _headers(auth=False):
    h = {
        'Content-Type': 'application/json',
        'User-Agent': USER_AGENT,
    }
    if auth:
        at = _access_token()
        if at:
            h['Authorization'] = 'Bearer %s' % at
    return h


def _post(url, payload=None, auth=False, timeout=20):
    try:
        r = requests.post(url, headers=_headers(auth=auth),
                          data=json.dumps(payload).encode('utf-8') if payload is not None else b'',
                          timeout=timeout)
        if r.status_code in (200, 201, 204):
            try:
                return r.json()
            except Exception:
                return {}
        log('Bingebase POST %s -> %s' % (url, r.status_code))
    except Exception as e:
        log('Bingebase POST %s failed: %s' % (url, e))
    return None


def _get(url, params=None, auth=True, timeout=20):
    try:
        r = requests.get(url, headers=_headers(auth=auth), params=params or {}, timeout=timeout)
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                return {}
        log('Bingebase GET %s -> %s' % (url, r.status_code))
    except Exception as e:
        log('Bingebase GET %s failed: %s' % (url, e))
    return None


# ---------- device-code auth ----------

def authenticate():
    """Start Bingebase device-code flow. Shows code to enter at bingebase.com/activate."""
    log('Bingebase: starting device-code authentication')
    try:
        r = requests.post(DEVICE_CODE_URL, headers=_headers(), data=b'', timeout=20)
        log('Bingebase: device/code -> %s' % r.status_code)
        if r.status_code != 200:
            log('Bingebase: device/code body=%s' % r.text[:300])
            notify('Bingebase: device code request failed (%s)' % r.status_code)
            return
        data = r.json()
    except Exception as e:
        log('Bingebase: device/code exception: %s' % e)
        notify('Bingebase error: %s' % e)
        return

    user_code = data.get('user_code')
    device_code = data.get('device_code')
    expires_in = int(data.get('expires_in', 600))
    interval = int(data.get('interval', 5))
    verify_url = 'bingebase.com/activate'
    log('Bingebase: device code obtained (user_code=%s expires_in=%d interval=%d)' %
        (user_code, expires_in, interval))

    msg = ('Open [B]%s[/B] in any browser and enter the code:\n\n[B]%s[/B]\n\n'
           'Waiting for authorisation... (this dialog will auto-close)') % (verify_url, user_code)

    pd = xbmcgui.DialogProgress()
    pd.create('Bingebase — device authorization', msg)

    elapsed = 0
    poll_interval = max(interval, 3)
    while elapsed < expires_in:
        if pd.iscanceled():
            pd.close()
            log('Bingebase: user cancelled authentication')
            return
        xbmc.sleep(poll_interval * 1000)
        elapsed += poll_interval
        try:
            pr = requests.post(DEVICE_TOKEN_URL, headers=_headers(),
                               data=json.dumps({'device_code': device_code}).encode('utf-8'),
                               timeout=15)
        except Exception as e:
            log('Bingebase poll exception: %s' % e)
            continue

        if pr.status_code == 200:
            try:
                tok = pr.json() or {}
            except Exception:
                tok = {}
            access_token = tok.get('access_token')
            if access_token:
                tok.setdefault('webhook_url',
                               '%s/webhooks/kodi/%s' % (BASE_URL, access_token))
                tok['saved_at'] = time.time()
                log('Bingebase: AUTHORISED — saving token')
                saved = _save_token(tok)
                pd.close()
                if saved:
                    try:
                        ADDON.setSetting('bingebase_status', 'Authenticated')
                        ADDON.setSetting('bingebase_enabled', 'true')
                    except Exception as e:
                        log('Bingebase: setSetting status/enabled failed: %s' % e)
                    if is_authenticated():
                        notify('Bingebase: authentication successful')
                        log('Bingebase: token verified — is_authenticated()=True')
                    else:
                        notify('Bingebase: token saved but not readable — try again')
                        log('Bingebase: WARNING — token saved but is_authenticated() is False')
                else:
                    notify('Bingebase: token NOT saved — check logs / disk space')
                    log('Bingebase: ERROR — _save_token returned False')
                return
            # 200 but no token — keep polling
            continue
        elif pr.status_code == 400:
            # Could be "authorization_pending" or "expired_token" — try to detect.
            try:
                err = pr.json()
                if err.get('error') == 'expired_token':
                    pd.close()
                    log('Bingebase: device code expired')
                    notify('Bingebase: device code expired — please retry')
                    return
            except Exception:
                pass
            # otherwise keep polling
            continue
        elif pr.status_code in (404, 410, 418, 429, 409):
            pd.close()
            log('Bingebase: poll status %s' % pr.status_code)
            notify('Bingebase: device code denied / rate-limited (%s)' % pr.status_code)
            return
        else:
            log('Bingebase: unexpected poll status %s body=%s' %
                (pr.status_code, pr.text[:200]))

    pd.close()
    log('Bingebase: authentication timed out (%ds)' % expires_in)
    notify('Bingebase: authentication timed out')


def logout():
    _clear_token()
    try:
        ADDON.setSetting('bingebase_status', 'Not authenticated')
    except Exception:
        pass
    notify('Bingebase: signed out')
    log('Bingebase: signed out (setting + file cleared)')


def show_token_status():
    """Diagnostic action — display where the token lives and whether it works."""
    setting_present = bool(ADDON.getSetting(SETTING_KEY))
    file_present = os.path.exists(TOKEN_FILE)
    file_size = os.path.getsize(TOKEN_FILE) if file_present else 0
    tok = _load_token() or {}
    has_access = bool(tok.get('access_token'))
    is_auth = is_authenticated()
    lines = [
        'Bingebase — token status',
        '=' * 40,
        'Setting payload : %s' % ('present (%d chars)' % len(ADDON.getSetting(SETTING_KEY))
                                  if setting_present else 'MISSING'),
        'File payload    : %s' % ('present (%d bytes)' % file_size
                                  if file_present else 'MISSING'),
        'Access token    : %s' % ('YES (%s...)' % tok.get('access_token', '')[:8]
                                  if has_access else 'NO'),
        'Webhook URL     : %s' % (_webhook_url() or '(none)'),
        'is_authenticated: %s' % is_auth,
        'Profile path    : %s' % PROFILE_PATH,
        'Token file path : %s' % TOKEN_FILE,
        '',
        'If is_authenticated is False but the access token is present,',
        'try Settings → Bingebase → Sign out, then re-authenticate.',
    ]
    xbmcgui.Dialog().textviewer('Bingebase — token status', '\n'.join(lines))


# ---------- scrobble ----------

def _scrobble_payload(event, media_type, imdb_id=None, tmdb_id=None,
                      season=None, episode=None, progress_pct=0.0,
                      duration=0, position=0, title='', tv_show_title=''):
    payload = {
        'event': event,                     # 'start' | 'pause' | 'stop' | 'end'
        'mediaType': 'movie' if media_type == 'movie' else 'episode',
        'title': title or '',
        'uniqueIds': {
            'tmdb': str(tmdb_id) if tmdb_id else '',
            'imdb': str(imdb_id) if imdb_id else '',
        },
        'duration': int(duration or 0),
        'progress': {
            'time': int(position or 0),
            'percent': round(float(progress_pct or 0.0), 1),
        },
    }
    if media_type != 'movie':
        payload['tvShowTitle'] = tv_show_title or title or ''
        payload['season'] = int(season or 0)
        payload['episode'] = int(episode or 0)
        payload['showUniqueIds'] = {
            'tmdb': str(tmdb_id) if tmdb_id else '',
            'imdb': str(imdb_id) if imdb_id else '',
        }
    return payload


def _send_scrobble(event, media_type, **kw):
    if not (get_setting_bool('bingebase_enabled') and get_setting_bool('bingebase_scrobble')):
        return
    url = _webhook_url()
    if not url:
        return
    payload = _scrobble_payload(event, media_type, **kw)
    try:
        # Webhook does NOT require Authorization header — token is in the path.
        requests.post(url, headers=_headers(auth=False),
                      data=json.dumps(payload).encode('utf-8'), timeout=15)
    except Exception as e:
        log('Bingebase scrobble (%s) failed: %s' % (event, e))


def scrobble_start(media_type, imdb_id=None, tmdb_id=None, season=None, episode=None,
                   progress=0.0, duration=0, position=0, title='', tv_show_title=''):
    _send_scrobble('start', media_type, imdb_id=imdb_id, tmdb_id=tmdb_id,
                   season=season, episode=episode, progress_pct=progress,
                   duration=duration, position=position,
                   title=title, tv_show_title=tv_show_title)


def scrobble_pause(media_type, imdb_id=None, tmdb_id=None, season=None, episode=None,
                   progress=0.0, duration=0, position=0, title='', tv_show_title=''):
    _send_scrobble('pause', media_type, imdb_id=imdb_id, tmdb_id=tmdb_id,
                   season=season, episode=episode, progress_pct=progress,
                   duration=duration, position=position,
                   title=title, tv_show_title=tv_show_title)


def scrobble_stop(media_type, imdb_id=None, tmdb_id=None, season=None, episode=None,
                  progress=0.0, duration=0, position=0, title='', tv_show_title=''):
    # Bingebase distinguishes 'stop' (early) from 'end' (completed). We pick
    # based on percent — the server then decides what to mark watched.
    event = 'end' if (progress or 0) >= 80 else 'stop'
    _send_scrobble(event, media_type, imdb_id=imdb_id, tmdb_id=tmdb_id,
                   season=season, episode=episode, progress_pct=progress,
                   duration=duration, position=position,
                   title=title, tv_show_title=tv_show_title)


# ---------- mark-watched / sync ----------

def mark_watched(media_type, imdb_id=None, tmdb_id=None,
                 season=None, episode=None, title='', tv_show_title=''):
    """Force a single mark-as-watched scrobble (used by context menu)."""
    if not is_authenticated():
        notify('Bingebase: please authenticate first')
        return False
    _send_scrobble('end', media_type, imdb_id=imdb_id, tmdb_id=tmdb_id,
                   season=season, episode=episode, progress_pct=100.0,
                   duration=0, position=0,
                   title=title, tv_show_title=tv_show_title)
    return True


def _format_movie(it):
    return {
        'title': it.get('title') or '',
        'year': int(it.get('year') or 0),
        'playcount': int(it.get('playcount') or 1),
        'lastplayed': it.get('lastplayed') or '',
        'uniqueIds': {
            'tmdb': str(it.get('tmdb') or ''),
            'imdb': str(it.get('imdb') or ''),
        },
    }


def _format_episode(it):
    return {
        'title': it.get('title') or '',
        'tvShowTitle': it.get('show_title') or it.get('tvshowtitle') or '',
        'season': int(it.get('season') or 0),
        'episode': int(it.get('episode') or 0),
        'playcount': int(it.get('playcount') or 1),
        'lastplayed': it.get('lastplayed') or '',
        'uniqueIds': {
            'tmdb': str(it.get('tmdb') or ''),
            'imdb': str(it.get('imdb') or ''),
        },
        'showUniqueIds': {
            'tmdb': str(it.get('show_tmdb') or it.get('tmdb') or ''),
            'imdb': str(it.get('show_imdb') or it.get('imdb') or ''),
        },
    }


def import_history(movies, episodes):
    """Push the addon-local watched store to Bingebase."""
    if not is_authenticated():
        return None
    payload = {
        'movies': [_format_movie(m) for m in movies],
        'episodes': [_format_episode(e) for e in episodes],
    }
    return _post(IMPORT_URL, payload, auth=True)


def export_history(since=None):
    """Pull Bingebase watched history. Returns dict {movies:[...], episodes:[...]}."""
    if not is_authenticated():
        return None
    params = {'since': since} if since else None
    return _get(EXPORT_URL, params=params, auth=True)


def sync_history():
    """Two-way sync between Bingebase and the addon-local watched store."""
    if not is_authenticated():
        notify('Bingebase: not authenticated')
        return
    from . import kodi_db as KDB

    notify('Bingebase: syncing watched history...', time=2000)
    pushed_m = pushed_e = 0
    pulled_m = pulled_e = 0

    # ---- push (addon -> bingebase) ----
    if get_setting_bool('bingebase_sync_push', True):
        try:
            movies = KDB.export_watched_movies() if hasattr(KDB, 'export_watched_movies') else []
            episodes = KDB.export_watched_episodes() if hasattr(KDB, 'export_watched_episodes') else []
            if movies or episodes:
                import_history(movies, episodes)
                pushed_m, pushed_e = len(movies), len(episodes)
        except Exception as e:
            log('Bingebase push failed: %s' % e)

    # ---- pull (bingebase -> addon) ----
    if get_setting_bool('bingebase_sync_pull', True):
        try:
            since = get_setting('bingebase_last_sync') or None
            data = export_history(since=since)
            if data:
                bb_movies = data.get('movies', []) or []
                bb_eps = data.get('episodes', []) or []
                # Convert into the set / dict format kodi_db.bulk_mark_* expects.
                movie_keys = set()
                for m in bb_movies:
                    uids = m.get('uniqueIds') or {}
                    imdb = uids.get('imdb') or m.get('imdb_id')
                    tmdb = uids.get('tmdb') or m.get('tmdb_id')
                    if imdb:
                        movie_keys.add(imdb)
                    if tmdb:
                        movie_keys.add('tmdb:%s' % tmdb)
                show_map = {}
                for ep in bb_eps:
                    sids = ep.get('showUniqueIds') or {}
                    imdb = sids.get('imdb') or ep.get('show_imdb_id')
                    tmdb = sids.get('tmdb') or ep.get('show_tmdb_id')
                    key = imdb or ('tmdb:%s' % tmdb) if tmdb else None
                    if not key:
                        continue
                    sn = int(ep.get('season') or 0)
                    en = int(ep.get('episode') or 0)
                    show_map.setdefault(key, {}).setdefault(sn, set()).add(en)
                if hasattr(KDB, 'bulk_mark_watched_movies'):
                    KDB.bulk_mark_watched_movies(movie_keys)
                if hasattr(KDB, 'bulk_mark_watched_episodes'):
                    KDB.bulk_mark_watched_episodes(show_map)
                pulled_m = len(movie_keys)
                pulled_e = sum(len(eps) for sns in show_map.values() for eps in sns.values())
        except Exception as e:
            log('Bingebase pull failed: %s' % e)

    ADDON.setSetting('bingebase_last_sync',
                     time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    notify('Bingebase: pushed %d/%d, pulled %d/%d (movies/episodes)'
           % (pushed_m, pushed_e, pulled_m, pulled_e))
