# -*- coding: utf-8 -*-
"""Simkl account, status lists, watched sync, and manager for Gratis Red.

Adapted from Red Light's Simkl stack to the Exodus-style Gratis Red architecture.
"""
from __future__ import absolute_import

import calendar
import json
import os
import pickle
import re
import time
import zlib
from threading import Lock

import requests
from six.moves.urllib_parse import quote, urljoin

from resources.lib.modules import cache
from resources.lib.modules import control
from resources.lib.modules import log_utils

try:
    from sqlite3 import Binary
except ImportError:
    from pysqlite2 import Binary

BASE_URL = 'https://api.simkl.com'
OAUTH2_DEVICE_URL = 'https://api.simkl.com/oauth2/device'
OAUTH2_TOKEN_URL = 'https://api.simkl.com/oauth2/token'
OAUTH2_REVOKE_URL = 'https://api.simkl.com/oauth2/revoke'
SIMKL_APP_NAME = 'plugin.video.gratisred'
SIMKL_V2_SCOPE = 'media:read media:write'
# V1 PIN app — existing grants stay on this.
SIMKL_CLIENT_ID = '7508fd47a5237d06eb9b27863e744763c278bc8b35c6c24c336ebbb5d66318bd'
# AUTH V2 device app (Gratis Red; existing V1 PIN grants stay on SIMKL_CLIENT_ID).
SIMKL_CLIENT_ID_V2 = '35dd10f2215509dd2574bf63e09bd397509719b965947cb79eecf2971213225a'

# Shared across plugin invokers + service timer (in-memory alone is not enough in Kodi).
_SIMKL_MIN_REQUEST_GAP = 1.5
_SIMKL_THROTTLE_PROP = 'gratisred.simkl_last_request_at'
_SIMKL_SYNC_BUSY_PROP = 'gratisred.simkl_sync_busy'
_SIMKL_SYNC_BUSY_AT_PROP = 'gratisred.simkl_sync_busy_at'
_SIMKL_ACTIVITIES_AT_PROP = 'gratisred.simkl_activities_at'
_SIMKL_ACTIVITIES_MIN_GAP = 60
_SIMKL_REFRESHING_PROP = 'gratisred.simkl_refreshing_token'
_SIMKL_REWATCH_DENIED_PROP = 'gratisred.simkl_rewatch_denied'
_SIMKL_ACTIVITIES_SETTING = 'simkl.activities_json'
_SIMKL_ID_EMPTY = ('None', None, '', 'empty_setting', 0, '0')
_SIMKL_SHOW_WATCHED_ACTIVITY_KEYS = ('watching', 'plantowatch', 'completed', 'hold', 'dropped', 'removed_from_list', 'all')
_SIMKL_MOVIE_WATCHED_ACTIVITY_KEYS = ('plantowatch', 'completed', 'dropped', 'removed_from_list', 'all')
_SIMKL_MOVIE_FULL_SYNC_KEYS = ('completed', 'removed_from_list')
_SIMKL_SHOW_FULL_SYNC_KEYS = ('removed_from_list',)
_SIMKL_TV_SYNC_QUERY = 'extended=full&episode_watched_at=yes&include_all_episodes=yes'
_SIMKL_ANIME_SYNC_QUERY = 'extended=full_anime_seasons&episode_watched_at=yes&include_all_episodes=yes'
# Bust Continue Watching seeds that defaulted to S01 when Simkl next_to_watch was ignored.
# aired_v3: parent overlay uses aired-now (not 0-of-0, not total including unaired).
_SIMKL_TV_INDICATOR_VER = 'aired_v3'
# Phase 2 multi-type: one /sync/all-items?date_from=… (shows + anime + movies).
_SIMKL_PHASE2_ALL_QUERY = 'extended=full_anime_seasons&episode_watched_at=yes&include_all_episodes=yes'

_STATUSES = ('plantowatch', 'watching', 'completed', 'hold', 'dropped')
_STATUS_LABELS = {
    'plantowatch': 'Plan to Watch',
    'watching': 'Watching',
    'completed': 'Completed',
    'hold': 'On Hold',
    'dropped': 'Dropped',
}
# List-status shelves / manager membership (hours). Cleared on list edits + activities.
_SIMKL_LIST_CACHE_HOURS = 48
_SIMKL_LIST_ACTIVITY_KEYS = ('plantowatch', 'watching', 'completed', 'hold', 'dropped', 'removed_from_list')

_request_lock = Lock()
_sync_lock = Lock()
_last_request_time = 0.0
_throttle_path = None


def _simkl_throttle_path():
    global _throttle_path
    if not _throttle_path:
        _throttle_path = os.path.join(control.dataPath, 'simkl_api_throttle')
    return _throttle_path


def _shared_last_request_at():
    last = _last_request_time
    try:
        last = max(last, float(control.window.getProperty(_SIMKL_THROTTLE_PROP) or 0))
    except Exception:
        pass
    try:
        last = max(last, os.path.getmtime(_simkl_throttle_path()))
    except Exception:
        pass
    return last


def _claim_request_slot(now):
    global _last_request_time
    _last_request_time = now
    try:
        control.window.setProperty(_SIMKL_THROTTLE_PROP, '%.3f' % now)
    except Exception:
        pass
    try:
        path = _simkl_throttle_path()
        folder = os.path.dirname(path)
        if folder and not os.path.isdir(folder):
            try:
                os.makedirs(folder)
            except Exception:
                pass
        with open(path, 'w') as handle:
            handle.write('%.3f\n' % now)
    except Exception:
        pass


def _throttle():
    """Space Simkl HTTP calls across threads and separate Kodi Python invokers."""
    with _request_lock:
        while True:
            now = time.time()
            wait = _SIMKL_MIN_REQUEST_GAP - (now - _shared_last_request_at())
            if wait <= 0:
                _claim_request_slot(now)
                return
            control.sleep(int(wait * 1000) + 25)


def _token():
    return (control.setting('simkl.token') or '').strip()


def _has_simkl_token():
    return bool(_token())


def _auth_version():
    version = str(control.setting('simkl.auth_version') or '').strip()
    if version in ('1', '2'):
        return version
    refresh = (control.setting('simkl.refresh') or '').strip()
    if refresh:
        return '2'
    token = _token()
    if str(token or '').startswith('simkl_at_'):
        return '2'
    if token:
        return '1'
    return ''


def _client_id():
    """V1 grants stay on the PIN app. New Authorise and V2 grants use the device app."""
    if _has_simkl_token() and _auth_version() == '1':
        return SIMKL_CLIENT_ID
    return SIMKL_CLIENT_ID_V2 or SIMKL_CLIENT_ID


def getSimklCredentialsInfo():
    return bool(_token() and (control.setting('simkl.user') or '').strip())


def getSimklAuthV2():
    """True when the signed-in Simkl grant is AUTH V2 (custom lists / refresh)."""
    return getSimklCredentialsInfo() and _auth_version() == '2'


def _mdblist_ok():
    try:
        from resources.lib.modules import mdblist
        return mdblist.getMdblistCredentialsInfo()
    except Exception:
        return False


def getIndicatorsProvider():
    """Return 'local', 'trakt', 'simkl', or 'mdblist' based on Indicators + credentials."""
    from resources.lib.modules import trakt
    trakt_ok = trakt.getTraktCredentialsInfo()
    simkl_ok = getSimklCredentialsInfo()
    mdblist_ok = _mdblist_ok()
    if not trakt_ok and not simkl_ok and not mdblist_ok:
        return 'local'
    val = control.setting('indicators.alt')
    if val == '1' and trakt_ok:
        return 'trakt'
    if val == '2' and simkl_ok:
        return 'simkl'
    if val == '3' and mdblist_ok:
        return 'mdblist'
    return 'local'


def getSimklIndicatorsInfo():
    return getIndicatorsProvider() == 'simkl'


_INDICATOR_LABELS = {'0': 'Gratis Red', '1': 'Trakt', '2': 'Simkl', '3': 'MDBList'}


def indicators_options():
    """Authorised Indicators choices only (0 Gratis Red, 2 Simkl, 3 MDBList, 1 Trakt)."""
    from resources.lib.modules import trakt
    opts = [('Gratis Red', '0')]
    if getSimklCredentialsInfo():
        opts.append(('Simkl', '2'))
    if _mdblist_ok():
        opts.append(('MDBList', '3'))
    if trakt.getTraktCredentialsInfo():
        opts.append(('Trakt', '1'))
    return opts


def indicators_display_name(value=None):
    if value is None:
        value = {'local': '0', 'trakt': '1', 'simkl': '2', 'mdblist': '3'}.get(getIndicatorsProvider(), '0')
    return _INDICATOR_LABELS.get(str(value), 'Gratis Red')


def sync_indicators_label(value=None):
    try:
        control.setSetting('indicators.alt.name', indicators_display_name(value))
    except Exception:
        pass


def set_bookmarks_source(value):
    """Set Resume Point Source only (0 Gratis Red, 1 Trakt, 2 Simkl, 3 MDBList)."""
    value = str(value)
    if value not in _INDICATOR_LABELS:
        value = '0'
    control.setSetting('bookmarks.source', value)


def set_watched_provider(value, notify=False):
    """Set Indicators + matching Resume Point Source (0 Gratis Red, 1 Trakt, 2 Simkl, 3 MDBList)."""
    value = str(value)
    if value not in _INDICATOR_LABELS:
        value = '0'
    control.setSetting('indicators.alt', value)
    set_bookmarks_source(value)
    sync_indicators_label(value)
    if notify:
        name = _INDICATOR_LABELS.get(value, 'Gratis Red')
        control.infoDialog('Watched Indicators & Resume: %s' % name, sound=True)


def ensure_bookmarks_valid():
    """Keep Resume Point Source aligned with Watched Indicators (no separate picker)."""
    val = control.setting('indicators.alt') or '0'
    if (control.setting('bookmarks.source') or '0') != val:
        set_bookmarks_source(val)


def ensure_indicators_valid():
    """If stored Indicators points at an unauthorised service, fall back and refresh label."""
    from resources.lib.modules import trakt
    val = control.setting('indicators.alt') or '0'
    if val == '1' and not trakt.getTraktCredentialsInfo():
        set_watched_provider('2' if getSimklCredentialsInfo() else ('3' if _mdblist_ok() else '0'))
    elif val == '2' and not getSimklCredentialsInfo():
        set_watched_provider('3' if _mdblist_ok() else ('1' if trakt.getTraktCredentialsInfo() else '0'))
    elif val == '3' and not _mdblist_ok():
        set_watched_provider('2' if getSimklCredentialsInfo() else ('1' if trakt.getTraktCredentialsInfo() else '0'))
    else:
        sync_indicators_label(val)
        ensure_bookmarks_valid()


def fallback_indicators_on_revoke(revoked):
    """revoked: 'trakt', 'simkl', or 'mdblist'. Adjust Indicators if that provider was selected."""
    from resources.lib.modules import trakt
    val = control.setting('indicators.alt') or '0'
    if revoked == 'trakt' and val == '1':
        set_watched_provider('2' if getSimklCredentialsInfo() else ('3' if _mdblist_ok() else '0'))
    elif revoked == 'simkl' and val == '2':
        set_watched_provider('3' if _mdblist_ok() else ('1' if trakt.getTraktCredentialsInfo() else '0'))
    elif revoked == 'mdblist' and val == '3':
        set_watched_provider('2' if getSimklCredentialsInfo() else ('1' if trakt.getTraktCredentialsInfo() else '0'))
    else:
        sync_indicators_label()
        ensure_bookmarks_valid()


def _provider_select(heading, current):
    opts = indicators_options()
    labels = [o[0] for o in opts]
    preselect = -1
    for i, (_label, value) in enumerate(opts):
        if value == current:
            preselect = i
            break
    try:
        select = control.dialog.select(heading, labels, preselect=preselect)
    except TypeError:
        select = control.selectDialog(labels, heading)
    if select < 0:
        return None
    return opts[select][1]


def choose_indicators(reopen_settings=False):
    ensure_indicators_valid()
    value = _provider_select('Watched Indicators', control.setting('indicators.alt') or '0')
    if value is None:
        if reopen_settings:
            control.reopen_account_settings()
        return
    set_watched_provider(value, notify=True)
    control.sleep(350)
    if reopen_settings:
        control.reopen_account_settings()


def _headers(client_id=None, access_token=None):
    cid = client_id or _client_id()
    h = {
        'Content-Type': 'application/json',
        'simkl-api-key': cid,
        'User-Agent': '%s/%s' % (SIMKL_APP_NAME, control.addonInfo('version')),
    }
    token = access_token if access_token is not None else _token()
    if token:
        h['Authorization'] = 'Bearer %s' % token
    return h


def _url(path, client_id=None):
    cid = client_id or _client_id()
    base = path if path.startswith('http') else urljoin(BASE_URL, path.lstrip('/'))
    sep = '&' if '?' in base else '?'
    return '%s%sclient_id=%s&app-name=%s&app-version=%s' % (
        base, sep, cid, SIMKL_APP_NAME, control.addonInfo('version'))


def _oauth2_url(base, client_id=None):
    cid = client_id or _client_id()
    if not cid:
        return None
    sep = '&' if '?' in base else '?'
    return '%s%sclient_id=%s&app-name=%s&app-version=%s' % (
        base, sep, cid, SIMKL_APP_NAME, control.addonInfo('version'))


def _oauth_form_headers():
    return {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': '%s/%s' % (SIMKL_APP_NAME, control.addonInfo('version')),
    }


def _store_v2_tokens(payload, client_id=None):
    if not isinstance(payload, dict):
        return False
    token = payload.get('access_token')
    if not token:
        return False
    expires_in = int(payload.get('expires_in') or 604800)
    refresh = payload.get('refresh_token') or (control.setting('simkl.refresh') or '').strip()
    control.setSetting('simkl.token', token)
    if refresh:
        control.setSetting('simkl.refresh', refresh)
    control.setSetting('simkl.expires', str(time.time() + expires_in))
    control.setSetting('simkl.auth_version', '2')
    return True


def simkl_refresh_token():
    refresh = (control.setting('simkl.refresh') or '').strip()
    if not refresh:
        return False
    if control.window.getProperty(_SIMKL_REFRESHING_PROP) == 'true':
        while control.window.getProperty(_SIMKL_REFRESHING_PROP) == 'true':
            control.sleep(250)
        return _has_simkl_token()
    control.window.setProperty(_SIMKL_REFRESHING_PROP, 'true')
    try:
        cid = _client_id()
        if not cid:
            return False
        _throttle()
        url = _oauth2_url(OAUTH2_TOKEN_URL, client_id=cid)
        resp = requests.post(url, data={
            'grant_type': 'refresh_token',
            'client_id': cid,
            'refresh_token': refresh,
        }, headers=_oauth_form_headers(), timeout=20)
        if resp.status_code == 200:
            return _store_v2_tokens(resp.json() or {}, cid)
        from resources.lib.modules.meta_auth_alerts import maybe_notify_refresh_failure
        maybe_notify_refresh_failure('simkl', resp.status_code, getattr(resp, 'text', ''))
        return False
    except Exception as e:
        log_utils.log('Simkl V2 refresh failed: %s' % e, 1)
        return False
    finally:
        try:
            control.window.clearProperty(_SIMKL_REFRESHING_PROP)
        except Exception:
            pass


def _ensure_v2_access_token():
    if _auth_version() != '2' or not (control.setting('simkl.refresh') or '').strip():
        return
    while control.window.getProperty(_SIMKL_REFRESHING_PROP) == 'true':
        control.sleep(250)
    try:
        expires_at = float(control.setting('simkl.expires') or 0)
    except Exception:
        expires_at = 0.0
    if time.time() + 86400 >= expires_at:
        simkl_refresh_token()


def call_simkl(path, data=None, method=None, _retried=False):
    _ensure_v2_access_token()
    used_token = _token()
    _throttle()
    url = _url(path)
    headers = _headers()
    try:
        if method == 'get' or (data is None and not method):
            resp = requests.get(url, headers=headers, timeout=20)
        else:
            payload = json.dumps(data) if isinstance(data, (dict, list)) else data
            resp = requests.post(url, data=payload, headers=headers, timeout=20)
        if resp.status_code in (200, 201):
            return resp.json() if resp.text else True
        if resp.status_code == 204:
            return True
        log_utils.log('Simkl HTTP %s %s' % (resp.status_code, url), 1)
        if resp.status_code == 401 and not _retried:
            if _auth_version() == '2' and simkl_refresh_token() and _token() != used_token:
                return call_simkl(path, data=data, method=method, _retried=True)
            from resources.lib.modules.meta_auth_alerts import maybe_notify_refresh_failure
            maybe_notify_refresh_failure('simkl', 401)
        elif resp.status_code == 401:
            from resources.lib.modules.meta_auth_alerts import maybe_notify_refresh_failure
            maybe_notify_refresh_failure('simkl', 401)
    except Exception as e:
        log_utils.log('Simkl Error: %s' % e, 1)
    return None


def _simkl_rewatch_denied(payload):
    return isinstance(payload, dict) and payload.get('error') == 'pro_required'


def _simkl_handle_rewatch_denied(payload):
    if not _simkl_rewatch_denied(payload):
        return False
    if control.window.getProperty(_SIMKL_REWATCH_DENIED_PROP) != 'true':
        control.window.setProperty(_SIMKL_REWATCH_DENIED_PROP, 'true')
        msg = (payload.get('message') or '').strip() or 'Simkl rewatches need PRO or VIP. Track Rewatches was turned off.'
        control.infoDialog(msg, sound=True)
        log_utils.log('Simkl rewatch denied: pro_required', 1)
        try:
            control.setSetting('simkl.track_rewatches', 'false')
        except Exception:
            pass
    return True


def _simkl_want_rewatch():
    if control.window.getProperty(_SIMKL_REWATCH_DENIED_PROP) == 'true':
        return False
    return control.setting('simkl.track_rewatches') == 'true'


def _simkl_rewatch_path(path):
    if not path or not _simkl_want_rewatch():
        return path
    if 'allow_rewatch=' in path:
        return path
    sep = '&' if '?' in path else '?'
    return '%s%sallow_rewatch=yes' % (path, sep)


def _simkl_path_without_rewatch(path):
    if not path or 'allow_rewatch=' not in path:
        return path
    base, sep, qs = path.partition('?')
    if not sep:
        return path
    parts = [p for p in qs.split('&') if p and not p.startswith('allow_rewatch=')]
    return '%s?%s' % (base, '&'.join(parts)) if parts else base


def call_simkl_rewatch(path, data=None, method=None):
    result = call_simkl(path, data=data, method=method)
    if not _simkl_handle_rewatch_denied(result):
        return result
    retry = _simkl_path_without_rewatch(path)
    if retry == path:
        return result
    return call_simkl(retry, data=data, method=method)


def _fetch_user_settings(access_token):
    """POST /users/settings — Simkl's documented profile call (GET is not the contract)."""
    _throttle()
    url = _url('/users/settings')
    headers = _headers(access_token=access_token)
    try:
        resp = requests.post(url, data=json.dumps({}), headers=headers, timeout=20)
        if resp.status_code in (200, 201) and resp.text:
            return resp.json()
        log_utils.log('Simkl HTTP %s %s' % (resp.status_code, url), 1)
    except Exception as e:
        log_utils.log('Simkl Error: %s' % e, 1)
    return None


def _save_simkl_profile(info=None):
    if info is None:
        info = call_simkl('/users/settings', data={})
    user = 'Simkl User'
    user_id = ''
    if info and isinstance(info, dict) and info.get('user'):
        u = info['user']
        user = str(u.get('name') or u.get('login') or u.get('username') or user)
        user_id = u.get('id') or u.get('user_id') or ''
        if not user_id:
            account = info.get('account') or {}
            user_id = account.get('id') or ''
    control.setSetting('simkl.user', user)
    control.setSetting('simkl.user_id', str(user_id) if user_id not in _SIMKL_ID_EMPTY else '')
    return user


def _simkl_user_id():
    user_id = (control.setting('simkl.user_id') or '').strip()
    if user_id:
        return user_id
    _save_simkl_profile()
    return (control.setting('simkl.user_id') or '').strip() or None


def _simkl_pin_auth_url(pin):
    complete = (pin or {}).get('verification_uri_complete')
    if complete and str(complete).startswith('http'):
        return str(complete).strip()
    user_code = str((pin or {}).get('user_code') or '')
    verify = ((pin or {}).get('verification_uri') or (pin or {}).get('verification_url') or 'https://simkl.com/pin').rstrip('/')
    if user_code:
        return '%s/%s' % (verify, user_code)
    return verify


def _simkl_get_device():
    cid = SIMKL_CLIENT_ID_V2
    if not cid:
        return None
    try:
        _throttle()
        url = _oauth2_url(OAUTH2_DEVICE_URL, client_id=cid)
        resp = requests.post(url, data={'client_id': cid, 'scope': SIMKL_V2_SCOPE},
                             headers=_oauth_form_headers(), timeout=20)
        if resp.status_code == 200:
            data = resp.json() or {}
            if data.get('user_code') and data.get('device_code'):
                data['_client_id'] = cid
                return data
    except Exception as e:
        log_utils.log('Simkl V2 device start failed: %s' % e, 1)
    return None


def authSimkl(reopen_settings=False):
    from resources.lib.modules import auth_utils
    progress = None
    try:
        if getSimklCredentialsInfo():
            control.infoDialog('Simkl is already authorised. Use Revoke Simkl Account to sign out.', sound=True)
            return
        progress = auth_utils.auth_progress_dialog('Simkl Authorise', '')
        progress.update('Connecting to Simkl...')
        pin = _simkl_get_device()
        if not pin or not pin.get('user_code') or not pin.get('device_code'):
            control.infoDialog('Simkl Authorisation Failed.', sound=True)
            return
        user_code = str(pin.get('user_code', ''))
        device_code = pin.get('device_code')
        cid = pin.get('_client_id') or SIMKL_CLIENT_ID_V2
        expires_in = int(pin.get('expires_in') or 900)
        interval = max(int(pin.get('interval') or 5), 1)
        auth_url = _simkl_pin_auth_url(pin)
        progress.update('Preparing QR code...')
        qr_code = auth_utils.make_qrcode(auth_url) or ''
        short_url = auth_utils.make_tinyurl(auth_url)
        auth_utils.copy2clip(auth_url)
        insert = '[CR]OR visit [B]%s[/B]' % short_url if short_url else ''
        content = ('Enter [B]%s[/B] at [B]simkl.com/pin[/B][CR]OR scan the [B]QR Code[/B]%s[CR][CR]'
                   'Waiting for authorisation...' % (user_code, insert))
        progress.update(content, qr_path=qr_code)
        token_payload = None
        start = time.time()
        token_url = _oauth2_url(OAUTH2_TOKEN_URL, client_id=cid)
        while not progress.iscanceled() and (time.time() - start) < expires_in:
            if auth_utils.auth_progress_wait(progress, interval):
                break
            try:
                resp = requests.post(token_url, data={
                    'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                    'client_id': cid,
                    'device_code': device_code,
                }, headers=_oauth_form_headers(), timeout=20)
                body = {}
                try:
                    body = resp.json() or {}
                except Exception:
                    body = {}
                if resp.status_code == 200 and body.get('access_token'):
                    token_payload = body
                    break
                error = str(body.get('error') or '')
                if error == 'slow_down':
                    interval += 5
                elif error in ('expired_token', 'invalid_client'):
                    break
            except Exception:
                pass
        canceled = progress.iscanceled()
        auth_utils.close_auth_progress_dialog(progress)
        progress = None
        if canceled:
            control.infoDialog('Simkl Authorisation Canceled.', sound=True)
            return
        if not token_payload or not _store_v2_tokens(token_payload, cid):
            control.infoDialog('Simkl Authorisation Failed.', sound=True)
            return
        info = _fetch_user_settings(token_payload.get('access_token'))
        _save_simkl_profile(info)
        control.setSetting('simkl.authed', 'yes')
        from resources.lib.modules.meta_auth_alerts import clear_alert
        clear_alert('simkl')
        if control.yesnoDialog('Set Simkl as your Watched Indicators provider?', heading='Watched Status Provider'):
            set_watched_provider('2', notify=True)
        try:
            # Same as Red Light: full pull + store /sync/activities so the next list
            # open can date_from instead of pulling movies/shows/anime again.
            syncSimklWatched(silent=True, force_update=True)
        except Exception:
            pass
        control.infoDialog('Simkl Account Authorised.', sound=True)
        control.finish_auth_ui(reopen_settings=reopen_settings)
    except Exception:
        control.infoDialog('Simkl Authorisation Failed.', sound=True)
    finally:
        if progress is not None:
            auth_utils.close_auth_progress_dialog(progress)


def revokeSimkl(reopen_settings=False):
    if not getSimklCredentialsInfo():
        control.infoDialog('No Simkl account is authorised.', sound=True)
        control.finish_auth_ui(reopen_settings=reopen_settings)
        return
    if not control.confirm_revoke('Simkl', reopen_settings):
        return
    try:
        if _auth_version() == '2':
            try:
                cid = _client_id()
                token = (control.setting('simkl.refresh') or '').strip() or _token()
                if cid and token:
                    _throttle()
                    url = _oauth2_url(OAUTH2_REVOKE_URL, client_id=cid)
                    requests.post(url, data={'client_id': cid, 'token': token},
                                  headers=_oauth_form_headers(), timeout=20)
            except Exception:
                pass
        control.setSetting('simkl.user', '')
        control.setSetting('simkl.user_id', '')
        control.setSetting('simkl.token', '')
        control.setSetting('simkl.refresh', '')
        control.setSetting('simkl.expires', '')
        control.setSetting('simkl.auth_version', '')
        control.setSetting('simkl.authed', '')
        from resources.lib.modules.meta_auth_alerts import clear_alert
        clear_alert('simkl')
        _store_cached_activities({})
        fallback_indicators_on_revoke('simkl')
        _bust_sync_cache()
        control.infoDialog('Simkl Account Revoked.', sound=True)
        control.finish_auth_ui(reopen_settings=reopen_settings)
    except Exception:
        control.infoDialog('Simkl Revoke Failed.', sound=True)


def _media_ids(item, media_kind):
    try:
        if media_kind == 'movies':
            obj = item.get('movie') or item
        else:
            obj = item.get('show') or item.get('anime') or item
        ids = obj.get('ids') or item.get('ids') or {}
        if not isinstance(ids, dict):
            ids = {}
        out = {}
        for key in ('tmdb', 'imdb', 'tvdb'):
            value = ids.get(key)
            if value in (None, '', 'None', 0, '0'):
                continue
            if key in ('tmdb', 'tvdb'):
                try:
                    value = int(value)
                except Exception:
                    pass
            out[key] = value
        return out, obj
    except Exception:
        return {}, {}


def _all_items(media_kind, status):
    # Default sync payload includes title/year (needed for shelf_sort). ids_only strips titles.
    path = '/sync/all-items/%s/%s' % (media_kind, status)
    response = call_simkl(path, method='get')
    if response is None:
        return None
    if response is True:
        return []
    if isinstance(response, list):
        return response
    if not isinstance(response, dict):
        return None
    items = response.get(media_kind)
    if items is None and media_kind in ('shows', 'anime'):
        items = response.get('shows') or response.get('anime')
    if items is None:
        items = response.get('items') or response.get('list') or []
    return items if isinstance(items, list) else []


def _normalize_list_item(item, media_kind):
    if not isinstance(item, dict) or item.get('is_rewatch'):
        return None
    ids, block = _media_ids(item, media_kind)
    if not ids:
        return None
    return {
        'ids': ids,
        'title': block.get('title', '') or '',
        'year': block.get('year') or 0,
        'collected_at': item.get('added_to_watchlist_at') or '',
    }


def _simkl_list_cache_key(media_kind, status):
    return 'simkl_list_status_%s_%s' % (media_kind, status)


def _simkl_list_cache_get(media_kind, status):
    try:
        row = cache.cache_get(_simkl_list_cache_key(media_kind, status))
        if not row or not cache._is_cache_valid(row['date'], _SIMKL_LIST_CACHE_HOURS):
            return None
        data = pickle.loads(zlib.decompress(row['value']))
        if isinstance(data, dict) and 'items' in data:
            return data['items']
        return data if isinstance(data, list) else None
    except Exception:
        return None


def _simkl_list_cache_set(media_kind, status, items):
    try:
        # Wrap so empty shelves still store (cache.get treats [] as miss).
        payload = Binary(zlib.compress(pickle.dumps({'items': items or []})))
        cache.cache_insert(_simkl_list_cache_key(media_kind, status), payload)
    except Exception:
        pass


def clear_simkl_list_status_cache(media_kind=None, status=None):
    try:
        if media_kind == 'movies':
            kinds = ('movies',)
        elif media_kind == 'anime':
            kinds = ('anime',)
        elif media_kind == 'shows':
            kinds = ('shows', 'anime')
        elif media_kind:
            kinds = (media_kind,)
        else:
            kinds = ('movies', 'shows', 'anime')
        statuses = (status,) if status else _STATUSES
        cur = cache._get_connection_cursor()
        for kind in kinds:
            for st in statuses:
                cur.execute('DELETE FROM %s WHERE key = ?' % cache.cache_table, [_simkl_list_cache_key(kind, st)])
        cur.connection.commit()
    except Exception:
        pass


def _fetch_status_live(media_kind, status):
    items = _all_items(media_kind, status)
    if items is None:
        return None
    result = []
    for item in items:
        entry = _normalize_list_item(item, media_kind)
        if entry:
            result.append(entry)
    return result


def _warm_status_caches(media_kind):
    """One /sync/all-items/{type}/all pull; fill every status bucket (avoids 5× throttle)."""
    items = _all_items(media_kind, 'all')
    if items is None:
        return False
    buckets = {st: [] for st in _STATUSES}
    unstatused = 0
    for item in items:
        if not isinstance(item, dict) or item.get('is_rewatch'):
            continue
        st = (item.get('status') or '').lower()
        if st not in buckets:
            unstatused += 1
            continue
        entry = _normalize_list_item(item, media_kind)
        if entry:
            buckets[st].append(entry)
    if unstatused and not any(buckets.values()):
        log_utils.log('Simkl list %s/all: %s items missing status; using per-status fetch' % (media_kind, unstatused))
        return False
    for st, result in buckets.items():
        _simkl_list_cache_set(media_kind, st, result)
    return True


def _fetch_status(media_kind, status):
    if not getSimklCredentialsInfo():
        return []
    cached = _simkl_list_cache_get(media_kind, status)
    if cached is not None:
        return cached
    if _warm_status_caches(media_kind):
        cached = _simkl_list_cache_get(media_kind, status)
        if cached is not None:
            return cached
    result = _fetch_status_live(media_kind, status)
    result = [] if result is None else result
    _simkl_list_cache_set(media_kind, status, result)
    return result


def _fetch_tv_status(status):
    shows = _fetch_status('shows', status)
    anime = _fetch_status('anime', status)
    if not shows and not anime:
        return []
    seen = set()
    merged = []
    for item in shows + anime:
        key = item['ids'].get('tmdb') or item['ids'].get('imdb') or item.get('title')
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _normalize_imdb(imdb):
    if not imdb or imdb in ('0', 'None'):
        return '0'
    imdb = str(imdb)
    if not imdb.startswith('tt'):
        imdb = 'tt' + re.sub(r'[^0-9]', '', imdb)
    return imdb


# Per-shelf sort for My Simkl status lists — see shelf_sort.py.


def choose_list_sort(media, status):
    from resources.lib.modules import shelf_sort
    shelf_sort.choose_list_sort('simkl', media, status, sortable=shelf_sort.SIMKL_SORTABLE)


def directory_movies(status):
    """Build Gratis Red movie list items for a Simkl status shelf."""
    from resources.lib.modules import shelf_sort
    items = _fetch_status('movies', status)
    out = []
    for item in items:
        ids = item.get('ids') or {}
        title = item.get('title') or 'Unknown'
        year = item.get('year') or '0'
        try:
            year = re.sub(r'[^0-9]', '', str(year)) or '0'
        except Exception:
            year = '0'
        imdb = _normalize_imdb(ids.get('imdb'))
        tmdb = str(ids.get('tmdb') or '0')
        out.append({
            'title': title, 'originaltitle': title, 'year': year,
            'imdb': imdb, 'tmdb': tmdb, 'tvdb': '0', 'next': '', 'paused_at': '0',
            'collected_at': item.get('collected_at') or '',
        })
    return shelf_sort.sort_items(out, 'simkl', 'movies', status, sortable=shelf_sort.SIMKL_SORTABLE)


def directory_tvshows(status):
    """Build Gratis Red TV show list items for a Simkl status shelf."""
    from resources.lib.modules import shelf_sort
    items = _fetch_tv_status(status)
    out = []
    for item in items:
        ids = item.get('ids') or {}
        title = item.get('title') or 'Unknown'
        year = item.get('year') or '0'
        try:
            year = re.sub(r'[^0-9]', '', str(year)) or '0'
        except Exception:
            year = '0'
        imdb = _normalize_imdb(ids.get('imdb'))
        tmdb = str(ids.get('tmdb') or '0')
        tvdb = str(ids.get('tvdb') or '0')
        out.append({
            'title': title, 'originaltitle': title, 'year': year,
            'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'next': '',
            'collected_at': item.get('collected_at') or '',
        })
    return shelf_sort.sort_items(out, 'simkl', 'tvshows', status, sortable=shelf_sort.SIMKL_SORTABLE)


def _simkl_premium_only(payload):
    return isinstance(payload, dict) and payload.get('error') == 'premium_only'


def _simkl_custom_cache_key(list_id=None, page=None, limit=None):
    if list_id in (None, '', 0, '0'):
        return 'simkl_custom_lists'
    if page not in (None, '', 0, '0'):
        return 'simkl_custom_list_%s_p%s_%s' % (list_id, page, limit or 0)
    return 'simkl_custom_list_%s' % list_id


def _simkl_custom_cache_get(list_id=None, page=None, limit=None):
    try:
        row = cache.cache_get(_simkl_custom_cache_key(list_id, page, limit))
        if not row or not cache._is_cache_valid(row['date'], _SIMKL_LIST_CACHE_HOURS):
            return None
        data = pickle.loads(zlib.decompress(row['value']))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _simkl_custom_cache_set(list_id, payload, page=None, limit=None):
    try:
        cache.cache_insert(_simkl_custom_cache_key(list_id, page, limit), Binary(zlib.compress(pickle.dumps(payload or {}))))
    except Exception:
        pass


def clear_simkl_custom_list_cache():
    try:
        cur = cache._get_connection_cursor()
        cur.execute('DELETE FROM %s WHERE key = ? OR key LIKE ?' % cache.cache_table,
                    ['simkl_custom_lists', 'simkl_custom_list_%'])
        cur.connection.commit()
    except Exception:
        pass


def simkl_get_custom_lists():
    """User's custom lists. AUTH V2 only. Returns {'lists': [...], 'premium_only': dict|None}."""
    empty = {'lists': [], 'premium_only': None}
    if not getSimklAuthV2():
        return empty
    cached = _simkl_custom_cache_get()
    if cached is not None:
        return cached
    user_id = _simkl_user_id()
    if not user_id:
        return empty
    lists, page, limit = [], 1, 50
    while page <= 40:
        path = '/lists/user/%s?limit=%s&page=%s&sort=name&direction=asc' % (user_id, limit, page)
        payload = call_simkl(path, method='get')
        if _simkl_premium_only(payload):
            result = {'lists': [], 'premium_only': payload}
            _simkl_custom_cache_set(None, result)
            return result
        if not isinstance(payload, dict):
            break
        chunk = payload.get('lists')
        if not isinstance(chunk, list):
            break
        lists.extend(chunk)
        pagination = payload.get('pagination') or {}
        try:
            total_pages = int(pagination.get('total_pages') or page)
        except Exception:
            total_pages = page
        if page >= total_pages or len(chunk) < limit:
            break
        page += 1
    result = {'lists': lists, 'premium_only': None}
    _simkl_custom_cache_set(None, result)
    return result


def _simkl_custom_item_type(item):
    kind = str((item or {}).get('type') or '').lower()
    if kind in ('movie', 'movies'):
        return 'movie'
    if kind in ('tv', 'show', 'shows', 'anime'):
        return 'show'
    return ''


def custom_list_media(item):
    """movies / shows / anime / mixed / '' from a /lists/user row."""
    row = item or {}
    if isinstance(row.get('list'), dict):
        row = row['list']
    kind = str(row.get('media_type') or row.get('list_type') or row.get('kind') or '').lower()
    if kind in ('movie', 'movies'):
        return 'movies'
    if kind in ('anime',):
        return 'anime'
    if kind in ('tv', 'show', 'shows'):
        return 'shows'
    counts = row.get('counts') or {}
    try:
        movies = int(counts.get('movies') or 0)
    except Exception:
        movies = 0
    try:
        shows = int(counts.get('shows') or counts.get('tv') or 0)
    except Exception:
        shows = 0
    try:
        anime = int(counts.get('anime') or 0)
    except Exception:
        anime = 0
    present = []
    if movies:
        present.append('movies')
    if shows:
        present.append('shows')
    if anime:
        present.append('anime')
    if len(present) == 1:
        return present[0]
    if len(present) > 1:
        return 'mixed'
    return ''


def _simkl_custom_media_ids(item):
    ids = (item or {}).get('ids') or {}
    if not isinstance(ids, dict):
        return {}
    media_ids = {}
    tmdb = ids.get('tmdb')
    if tmdb not in _SIMKL_ID_EMPTY:
        try:
            media_ids['tmdb'] = int(tmdb)
        except Exception:
            pass
    imdb = ids.get('imdb')
    if imdb not in _SIMKL_ID_EMPTY:
        media_ids['imdb'] = imdb
    tvdb = ids.get('tvdb')
    if tvdb not in _SIMKL_ID_EMPTY:
        try:
            media_ids['tvdb'] = int(tvdb)
        except Exception:
            media_ids['tvdb'] = tvdb
    return media_ids


def _custom_page_size():
    try:
        size = int(control.setting('items.per.page') or 20)
    except Exception:
        size = 20
    if size < 1:
        size = 20
    return min(size, 40)


def custom_list_page_ref(rest):
    """'161423' or '161423|2' from a simkl_custom_ url."""
    page = 1
    text = str(rest or '')
    if '|' in text:
        text, raw = text.split('|', 1)
        try:
            page = int(raw)
        except Exception:
            page = 1
    if page < 1:
        page = 1
    return text, page


def simkl_get_custom_list_contents(list_id, page=1):
    """One page of a custom list. AUTH V2 + PRO/VIP. Does not walk the whole list."""
    empty = {'items': [], 'premium_only': None, 'page': 1, 'total_pages': 1}
    if not getSimklAuthV2() or list_id in _SIMKL_ID_EMPTY:
        return empty
    try:
        page = int(page or 1)
    except Exception:
        page = 1
    if page < 1:
        page = 1
    limit = _custom_page_size()
    cached = _simkl_custom_cache_get(list_id, page, limit)
    if cached is not None:
        return cached
    path = '/lists/%s?limit=%s&page=%s' % (list_id, limit, page)
    payload = call_simkl(path, method='get')
    if _simkl_premium_only(payload):
        result = {'items': [], 'premium_only': payload, 'page': page, 'total_pages': 1}
        _simkl_custom_cache_set(list_id, result, page, limit)
        return result
    rows = []
    total_pages = page
    if isinstance(payload, dict):
        chunk = payload.get('items')
        if isinstance(chunk, list):
            for index, item in enumerate(chunk):
                item_type = _simkl_custom_item_type(item)
                media_ids = _simkl_custom_media_ids(item)
                if not item_type or not (media_ids.get('tmdb') or media_ids.get('imdb') or media_ids.get('tvdb')):
                    continue
                position = item.get('position')
                try:
                    order = int(position) - 1 if position not in (None, '') else index
                except Exception:
                    order = index
                rows.append({
                    'type': item_type,
                    'media_ids': media_ids,
                    'order': order,
                    'title': (item.get('title') or '').strip(),
                    'year': item.get('year') or 0,
                })
        pagination = payload.get('pagination') or {}
        try:
            total_pages = int(pagination.get('total_pages') or page)
        except Exception:
            total_pages = page
    result = {'items': rows, 'premium_only': None, 'page': page, 'total_pages': total_pages}
    _simkl_custom_cache_set(list_id, result, page, limit)
    return result


def _directory_from_custom_items(items, media, nxt=''):
    out = []
    for item in items or []:
        ids = item.get('media_ids') or {}
        title = item.get('title') or 'Unknown'
        year = item.get('year') or '0'
        try:
            year = re.sub(r'[^0-9]', '', str(year)) or '0'
        except Exception:
            year = '0'
        imdb = _normalize_imdb(ids.get('imdb'))
        tmdb = str(ids.get('tmdb') or '0')
        tvdb = str(ids.get('tvdb') or '0')
        row = {
            'title': title, 'originaltitle': title, 'year': year,
            'imdb': imdb, 'tmdb': tmdb, 'tvdb': tvdb, 'next': nxt or '',
            'collected_at': '',
        }
        if media == 'movies':
            row['paused_at'] = '0'
        out.append(row)
    return out


def _custom_list_next(list_id, payload):
    try:
        page = int((payload or {}).get('page') or 1)
        total = int((payload or {}).get('total_pages') or page)
    except Exception:
        return ''
    if page >= total:
        return ''
    return 'simkl_custom_%s|%s' % (list_id, page + 1)


def directory_custom_list_movies(list_id, page=1):
    payload = simkl_get_custom_list_contents(list_id, page)
    if payload.get('premium_only'):
        control.infoDialog(
            (payload['premium_only'].get('message') or 'Simkl PRO/VIP required for custom lists.'),
            sound=True)
        return []
    movies = [i for i in (payload.get('items') or []) if i.get('type') == 'movie']
    movies.sort(key=lambda k: k.get('order', 0))
    return _directory_from_custom_items(movies, 'movies', _custom_list_next(list_id, payload))


def directory_custom_list_tvshows(list_id, page=1):
    payload = simkl_get_custom_list_contents(list_id, page)
    if payload.get('premium_only'):
        control.infoDialog(
            (payload['premium_only'].get('message') or 'Simkl PRO/VIP required for custom lists.'),
            sound=True)
        return []
    shows = [i for i in (payload.get('items') or []) if i.get('type') == 'show']
    shows.sort(key=lambda k: k.get('order', 0))
    return _directory_from_custom_items(shows, 'tvshows', _custom_list_next(list_id, payload))


def _paused_key(paused_at):
    if not paused_at:
        return '0'
    try:
        return re.sub(r'[^0-9]+', '', str(paused_at)) or '0'
    except Exception:
        return '0'


def get_playback(media_filter=None):
    """Raw /sync/playback items. media_filter: None, 'movies', or 'episodes'."""
    if not getSimklCredentialsInfo():
        return []
    path = '/sync/playback'
    if media_filter == 'movies':
        path = '/sync/playback/movies'
    elif media_filter == 'episodes':
        path = '/sync/playback/episodes'
    data = call_simkl(path, method='get')
    if data is None:
        return []
    if data is True:
        return []
    return data if isinstance(data, list) else []


def directory_playback_movies():
    """In Progress movies from Simkl playback."""
    out = []
    for item in get_playback('movies'):
        try:
            if item.get('type') and item.get('type') != 'movie':
                continue
            if control.playback_progress_stale(item):
                continue
            movie = item.get('movie') or item
            ids = movie.get('ids') or {}
            title = movie.get('title') or 'Unknown'
            year = movie.get('year') or '0'
            try:
                year = re.sub(r'[^0-9]', '', str(year)) or '0'
            except Exception:
                year = '0'
            imdb = _normalize_imdb(ids.get('imdb'))
            tmdb = str(ids.get('tmdb') or '0')
            out.append({
                'title': title, 'originaltitle': title, 'year': year,
                'imdb': imdb, 'tmdb': tmdb, 'tvdb': '0', 'next': '',
                'paused_at': _paused_key(item.get('paused_at')),
            })
        except Exception:
            pass
    return out


def playback_episode_items():
    """Minimal episode rows for In Progress Episodes enrichment."""
    out = []
    for item in get_playback('episodes'):
        try:
            if item.get('type') and item.get('type') != 'episode':
                continue
            if control.playback_progress_stale(item):
                continue
            show = item.get('show') or {}
            ep = item.get('episode') or {}
            ids = show.get('ids') or {}
            title = show.get('title') or 'Unknown'
            year = show.get('year') or '0'
            try:
                year = re.sub(r'[^0-9]', '', str(year)) or '0'
            except Exception:
                year = '0'
            season = ep.get('season')
            episode = ep.get('number') or ep.get('episode')
            if season is None or episode is None:
                continue
            out.append({
                'title': ep.get('title') or title,
                'season': '%01d' % int(season),
                'episode': '%01d' % int(episode),
                'tvshowtitle': title,
                'year': year,
                'premiered': '0',
                'status': '0',
                'studio': [],
                'genre': [],
                'duration': '0',
                'rating': '0',
                'votes': '0',
                'mpaa': '0',
                'plot': '0',
                'imdb': _normalize_imdb(ids.get('imdb')),
                'tvdb': str(ids.get('tvdb') or '0'),
                'tmdb': str(ids.get('tmdb') or '0'),
                'poster': '0',
                'thumb': '0',
                'paused_at': _paused_key(item.get('paused_at')),
                'watched_at': '0',
            })
        except Exception:
            pass
    return out


def dropped_tmdb_ids():
    ids = set()
    for item in _fetch_tv_status('dropped'):
        tmdb = (item.get('ids') or {}).get('tmdb')
        if tmdb:
            ids.add(str(tmdb))
    return ids


def _further_se(a, b):
    if not a:
        return b
    if not b:
        return a
    return a if a >= b else b


def progress_seeds():
    """Continue Watching seeds: last watched ep per show (exclude Dropped).

    Shape matches the pre-enrichment items used by trakt_progress_list
    (snum/enum = last watched; enrichment resolves the *next* episode).
    Prefer Simkl next_to_watch so multi-season shows open the current season
    instead of defaulting to S01 when history timestamps are thin.
    Requires at least one watched episode so Plan to Watch stays on its
    Watchlist-style show list, matching Trakt / MDBList Continue Watching.
    """
    if not getSimklCredentialsInfo():
        return []
    dropped = dropped_tmdb_ids()
    indicators = cachesyncTVShows(timeout=720) or []
    by_tmdb = {}
    for row in indicators:
        try:
            tmdb, aired, watched = str(row[0]), int(row[1]), row[2] or []
        except Exception:
            continue
        extra = row[3] if len(row) > 3 and isinstance(row[3], dict) else {}
        if not tmdb or tmdb == '0' or tmdb in dropped:
            continue
        if not watched:
            continue
        last = None
        pair = sorted(watched, key=lambda se: (int(se[0]), int(se[1])))[-1]
        try:
            last = (int(pair[0]), int(pair[1]))
        except Exception:
            last = None
        nxt = extra.get('next')
        if nxt and len(nxt) == 2:
            try:
                last = _further_se(last, (int(nxt[0]), int(nxt[1]) - 1))
            except Exception:
                pass
        lw = extra.get('last')
        if lw and len(lw) == 2:
            try:
                last = _further_se(last, (int(lw[0]), int(lw[1])))
            except Exception:
                pass
        if not last:
            continue
        if aired > 0 and len(watched) >= aired and not nxt:
            continue
        by_tmdb[tmdb] = {
            'tmdb': tmdb, 'imdb': '0', 'tvdb': '0',
            'tvshowtitle': extra.get('title') or '', 'year': '0', 'studio': [], 'duration': '0',
            'mpaa': '0', 'status': '0', 'genre': [],
            'snum': str(last[0]), 'enum': str(last[1]),
            '_last_watched': '0',
        }
    # Prefer titles/ids from Watching + plantowatch shelves when available.
    meta_by_tmdb = {}
    for status in ('watching', 'plantowatch', 'hold', 'completed'):
        for item in _fetch_tv_status(status):
            ids = item.get('ids') or {}
            tmdb = str(ids.get('tmdb') or '0')
            if tmdb == '0':
                continue
            meta_by_tmdb[tmdb] = item
    for tmdb, seed in list(by_tmdb.items()):
        meta = meta_by_tmdb.get(tmdb)
        if not meta:
            continue
        ids = meta.get('ids') or {}
        seed['tvshowtitle'] = meta.get('title') or seed['tvshowtitle']
        seed['year'] = str(meta.get('year') or seed['year'] or '0')
        seed['imdb'] = _normalize_imdb(ids.get('imdb'))
        seed['tvdb'] = str(ids.get('tvdb') or '0')
    seeds = [s for s in by_tmdb.values() if s.get('tmdb') and str(s.get('tmdb')) != '0']
    limit = str(control.setting('trakt.item.limit') or '100')
    try:
        limit = int(limit)
    except Exception:
        limit = 100
    return seeds[:limit]


def _cdn_get(path):
    """Fetch a Simkl CDN JSON file (calendar / trending). Auth not required."""
    base = 'https://data.simkl.in/%s' % path.lstrip('/')
    url = _url(base)
    _throttle()
    try:
        resp = requests.get(url, headers={
            'User-Agent': '%s/%s' % (SIMKL_APP_NAME, control.addonInfo('version')),
        }, timeout=25)
        if resp.status_code != 200:
            log_utils.log('Simkl CDN HTTP %s %s' % (resp.status_code, path), 1)
            return None
        return resp.json()
    except Exception as e:
        log_utils.log('Simkl CDN Error: %s' % e, 1)
        return None


def my_show_tmdb_ids():
    """TMDb IDs for Upcoming filter: Watching / Plan to Watch / On Hold (minus Dropped)."""
    ids = set()
    for status in ('watching', 'plantowatch', 'hold'):
        for item in _fetch_tv_status(status):
            tmdb = (item.get('ids') or {}).get('tmdb')
            if tmdb:
                ids.add(str(tmdb))
    return ids - dropped_tmdb_ids()


def calendar_episode_items(mine_only=True):
    """Upcoming episodes from Simkl calendar v2 (TV + anime), optional user filter."""
    want = my_show_tmdb_ids() if mine_only else None
    if mine_only and not want:
        return []
    out = []
    seen = set()
    for catalog in ('tv', 'anime'):
        data = _cdn_get('calendar/v2/%s.json' % catalog)
        if not isinstance(data, dict):
            continue
        calendar = data.get('calendar') or []
        metadata = data.get('metadata') or {}
        for entry in calendar:
            try:
                meta = metadata.get(str(entry.get('simkl_id'))) or {}
                ids = meta.get('ids') or {}
                tmdb = str(ids.get('tmdb') or '0')
                if mine_only and tmdb not in want:
                    continue
                ep = entry.get('episode') or {}
                season = ep.get('season')
                episode = ep.get('episode')
                if episode is None:
                    continue
                if season is None:
                    season = 1
                premiered = (entry.get('date') or '')[:10] or '0'
                key = (tmdb, int(season), int(episode), premiered)
                if key in seen:
                    continue
                seen.add(key)
                title = meta.get('title') or 'Unknown'
                year = '0'
                try:
                    rd = meta.get('release_date') or ''
                    if rd:
                        year = re.sub(r'[^0-9]', '', rd)[:4] or '0'
                except Exception:
                    pass
                out.append({
                    'title': ep.get('title') or title,
                    'season': '%01d' % int(season),
                    'episode': '%01d' % int(episode),
                    'tvshowtitle': title,
                    'year': year,
                    'premiered': premiered,
                    'status': meta.get('status') or '0',
                    'studio': [meta['network']] if meta.get('network') else [],
                    'genre': meta.get('genres') or [],
                    'duration': '0',
                    'rating': '0',
                    'votes': '0',
                    'mpaa': '0',
                    'plot': '0',
                    'imdb': _normalize_imdb(ids.get('imdb')),
                    'tvdb': str(ids.get('tvdb') or '0'),
                    'tmdb': tmdb,
                    'poster': '0',
                    'thumb': '0',
                    'paused_at': '0',
                    'watched_at': '0',
                })
            except Exception:
                pass
    try:
        out = sorted(out, key=lambda k: k.get('premiered') or '', reverse=False)
    except Exception:
        pass
    limit = str(control.setting('trakt.item.limit') or '100')
    try:
        limit = int(limit)
    except Exception:
        limit = 100
    return out[: max(limit, 50)]


def _trending_file(media_kind, period):
    # media_kind: movies|tv|anime ; period: today|week|month
    return 'discover/trending/%s/%s_100.json' % (media_kind, period)


def directory_trending(media_kind, period='today', page=1):
    """Simkl Most Watched / Trending CDN list as Gratis Red movie or TV items."""
    try:
        page = int(page or 1)
    except Exception:
        page = 1
    if page < 1:
        page = 1
    kinds = (media_kind,)
    if media_kind in ('tv', 'shows', 'tvshows'):
        kinds = ('tv', 'anime')
        media_kind = 'tv'
    out = []
    seen = set()
    for kind in kinds:
        data = _cdn_get(_trending_file(kind, period))
        if data is None:
            continue
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get(kind) or data.get('items') or data.get('movies') or data.get('tv') or data.get('anime') or []
        else:
            items = []
        for item in items:
            try:
                if not isinstance(item, dict):
                    continue
                # Trending payload may nest under movie/show or be flat with ids/title.
                block = item.get('movie') or item.get('show') or item.get('anime') or item
                ids = block.get('ids') or item.get('ids') or {}
                tmdb = str(ids.get('tmdb') or '0')
                if tmdb == '0' or tmdb in seen:
                    continue
                seen.add(tmdb)
                title = block.get('title') or item.get('title') or 'Unknown'
                year = block.get('year') or item.get('year') or '0'
                try:
                    year = re.sub(r'[^0-9]', '', str(year)) or '0'
                except Exception:
                    year = '0'
                row = {
                    'title': title, 'originaltitle': title, 'year': year,
                    'imdb': _normalize_imdb(ids.get('imdb')),
                    'tmdb': tmdb,
                    'tvdb': str(ids.get('tvdb') or '0'),
                    'next': '',
                }
                if media_kind == 'movies':
                    row['paused_at'] = '0'
                out.append(row)
            except Exception:
                pass
    size = _custom_page_size()
    start = (page - 1) * size
    page_rows = out[start:start + size]
    nxt = ''
    if start + size < len(out):
        nxt = 'simkl_trending_%s|%s' % (period, page + 1)
    for row in page_rows:
        row['next'] = nxt
    return page_rows


def syncMovies(user):
    try:
        if not getSimklCredentialsInfo():
            return []
        return _fetch_movie_indicators(date_from=None)
    except Exception:
        return []


def cachesyncMovies(timeout=0):
    return cache.get(syncMovies, timeout, control.setting('simkl.user').strip() or 'simkl')


def timeoutsyncMovies():
    try:
        return cache.timeout(syncMovies, control.setting('simkl.user').strip() or 'simkl') or 0
    except Exception:
        return 0


def syncTVShows(user, _indicator_ver=None):
    """Match Trakt cachesyncTVShows shape: [(tmdb, aired_eps, [(s,e),...]), ...].

    _indicator_ver is a cache-key only (passed through cache.get); do not use it.
    """
    try:
        if not getSimklCredentialsInfo():
            return []
        indicators, _touched = _fetch_tv_indicators(date_from=None)
        return indicators
    except Exception:
        return []


def cachesyncTVShows(timeout=0):
    return cache.get(syncTVShows, timeout, control.setting('simkl.user').strip() or 'simkl', _SIMKL_TV_INDICATOR_VER)


def timeoutsyncTVShows():
    try:
        return cache.timeout(syncTVShows, control.setting('simkl.user').strip() or 'simkl', _SIMKL_TV_INDICATOR_VER) or 0
    except Exception:
        return 0


def _simkl_with_date_from(query, date_from=None):
    if not date_from:
        return query
    return '%s&date_from=%s' % (query, quote(date_from, safe=''))


def _activity_ts(ts_str):
    if not ts_str:
        return 0
    try:
        return int(calendar.timegm(time.strptime(ts_str.rstrip('Z').split('.')[0], '%Y-%m-%dT%H:%M:%S')))
    except Exception:
        return 0


def _activity_block_changed(latest_blk, cached_blk, keys):
    latest_blk = latest_blk or {}
    cached_blk = cached_blk or {}
    for key in keys:
        if _activity_ts(latest_blk.get(key, '')) > _activity_ts(cached_blk.get(key, '')):
            return True
    return False


def _simkl_activities_recent():
    try:
        at = float(control.window.getProperty(_SIMKL_ACTIVITIES_AT_PROP) or 0)
        return at > 0 and (time.time() - at) < _SIMKL_ACTIVITIES_MIN_GAP
    except Exception:
        return False


def _simkl_note_activities_poll():
    try:
        control.window.setProperty(_SIMKL_ACTIVITIES_AT_PROP, '%.3f' % time.time())
    except Exception:
        pass


def _simkl_date_from(cached_activities):
    ts = str((cached_activities or {}).get('all') or '').strip()
    if not ts:
        return None
    if ts.startswith('2020-01-01'):
        return None
    return ts


def _load_cached_activities():
    raw = (control.setting(_SIMKL_ACTIVITIES_SETTING) or '').strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _store_cached_activities(latest):
    try:
        control.setSetting(_SIMKL_ACTIVITIES_SETTING, json.dumps(latest or {}))
    except Exception:
        pass


def _read_sync_cache(function, *args):
    try:
        key = cache._hash_function(function, *args)
        row = cache.cache_get(key)
        if not row:
            return None
        return pickle.loads(zlib.decompress(row['value']))
    except Exception:
        return None


def _write_sync_cache(function, result, *args):
    try:
        key = cache._hash_function(function, *args)
        cache.cache_insert(key, Binary(zlib.compress(pickle.dumps(result))))
    except Exception as e:
        log_utils.log('Simkl cache write failed: %s' % e, 1)


def _sync_user():
    return control.setting('simkl.user').strip() or 'simkl'


def apply_local_movie_watched(imdb, watched=True):
    """Patch the movie indicator cache after mark watched/unwatched. No HTTP."""
    imdb_n = _normalize_imdb(imdb)
    if imdb_n in ('0', ''):
        return False
    try:
        user = _sync_user()
        existing = _read_sync_cache(syncMovies, user)
        if existing is None:
            return False
        out = set(existing or [])
        if watched:
            out.add(imdb_n)
        else:
            out.discard(imdb_n)
        _write_sync_cache(syncMovies, list(out), user)
        return True
    except Exception:
        return False


def apply_local_episode_watched(tmdb, season, episode, watched=True):
    """Patch the TV indicator cache after mark watched/unwatched. No HTTP."""
    tmdb_n = str(tmdb or '').strip()
    if tmdb_n in ('', '0', 'None'):
        return False
    try:
        season, episode = int(season), int(episode)
        pair = (season, episode)
    except Exception:
        return False
    try:
        user = _sync_user()
        existing = _read_sync_cache(syncTVShows, user, _SIMKL_TV_INDICATOR_VER)
        if existing is None:
            return False
        by_tmdb = {}
        for row in existing or []:
            try:
                by_tmdb[str(row[0])] = row
            except Exception:
                pass
        row = by_tmdb.get(tmdb_n)
        extra = {}
        aired = 0
        pairs = []
        if row is not None:
            try:
                aired = int(row[1] or 0)
            except Exception:
                aired = 0
            pairs = [tuple(p) for p in (row[2] or [])]
            extra = row[3] if len(row) > 3 and isinstance(row[3], dict) else {}
        if watched:
            if pair not in pairs:
                pairs.append(pair)
            # Do not treat "1 of 1" as fully watched when Simkl never gave an aired count.
        else:
            pairs = [p for p in pairs if p != pair]
        by_tmdb[tmdb_n] = (tmdb_n, aired, pairs, extra)
        _write_sync_cache(syncTVShows, list(by_tmdb.values()), user, _SIMKL_TV_INDICATOR_VER)
        return True
    except Exception:
        return False


def _fetch_movie_indicators(date_from=None):
    path = '/sync/all-items/movies/completed?%s' % _simkl_with_date_from('extended=full', date_from)
    data = call_simkl_rewatch(_simkl_rewatch_path(path), method='get') or {}
    return _movie_indicators_from_data(data, filter_status=False)


def _movie_indicators_from_data(data, filter_status=False):
    rows = (data or {}).get('movies', data if isinstance(data, list) else [])
    indicators = []
    for item in rows:
        try:
            movie = item.get('movie', item)
            imdb = movie.get('ids', {}).get('imdb')
            if not imdb:
                continue
            status = str(item.get('status') or '').lower()
            watched_at = item.get('last_watched_at') or item.get('watched_at')
            # Unified Phase 2 returns all statuses — only store completed/watched movies.
            if filter_status and not watched_at and status != 'completed':
                continue
            indicators.append(_normalize_imdb(imdb))
        except Exception:
            pass
    return indicators


def _simkl_se_pair(value):
    if value in (None, '', 0, '0'):
        return None
    if isinstance(value, dict):
        nested = value.get('episode')
        if isinstance(nested, dict):
            return _simkl_se_pair(nested)
        season = value.get('season', value.get('season_number', value.get('s')))
        episode = value.get('episode', value.get('episode_number', value.get('e')))
        if episode is None:
            episode = value.get('number')
        try:
            season, episode = int(season), int(episode)
        except (TypeError, ValueError):
            return None
        if season < 1 or episode < 1:
            return None
        return (season, episode)
    text = str(value).strip()
    match = re.search(r'[Ss](\d+)\s*[Ee](\d+)', text)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    match = re.match(r'(\d+)\s*[-xX.]\s*(\d+)$', text)
    if match:
        season, episode = int(match.group(1)), int(match.group(2))
        if season >= 1 and episode >= 1:
            return (season, episode)
    return None


def _simkl_episode_watched(ep):
    if ep.get('watched_at') or ep.get('last_watched_at'):
        return True
    return ep.get('watched') in (True, 1, '1', 'true', 'True', 'yes')


def _simkl_int(value):
    try:
        return int(value or 0)
    except Exception:
        return 0


def _simkl_first_int(maps, *keys):
    for src in maps:
        if not isinstance(src, dict):
            continue
        for key in keys:
            n = _simkl_int(src.get(key))
            if n:
                return n
    return 0


def _simkl_aired_count(item, show, watched):
    """Aired-now count for the parent overlay (Trakt uses aired_episodes the same way).

    Counts sit on the all-items row, not only nested show. Prefer aired-now so an
    up-to-date watching title ticks; do not use 0-of-0 or inflate a first episode
    to 1-of-1.
    """
    maps = (item, show)
    aired = _simkl_first_int(maps, 'aired_episodes')
    total = _simkl_first_int(maps, 'total_episodes_count', 'total_episodes')
    not_aired = _simkl_first_int(maps, 'not_aired_episodes_count', 'not_aired_count')
    if not aired and total:
        if not_aired and not_aired <= total:
            aired = total - not_aired
        else:
            aired = total
    status = str((item or {}).get('status') or '').lower()
    watched_n = len(watched or [])
    if not aired and watched_n and status == 'completed':
        aired = watched_n
    return aired


def _upsert_tv_indicator(by_tmdb, tmdb, aired, watched, extra):
    prev = by_tmdb.get(tmdb)
    extra = dict(extra or {})
    if prev is None:
        by_tmdb[tmdb] = (tmdb, int(aired), list(watched or []), extra)
        return
    merged = list({tuple(pair) for pair in (prev[2] or []) + list(watched or [])})
    prev_extra = prev[3] if len(prev) > 3 and isinstance(prev[3], dict) else {}
    combined = dict(prev_extra)
    combined.update(extra)
    combined['next'] = _further_se(prev_extra.get('next'), extra.get('next'))
    combined['last'] = _further_se(prev_extra.get('last'), extra.get('last'))
    if not combined.get('title'):
        combined['title'] = prev_extra.get('title') or extra.get('title') or ''
    # Do not raise aired to len(watched) — that marks a first episode as 1-of-1 complete.
    by_tmdb[tmdb] = (tmdb, max(int(prev[1] or 0), int(aired or 0)), merged, combined)


def _append_tv_indicator_rows(indicators, touched_ids, data, item_key):
    by_tmdb = {}
    for row in indicators:
        try:
            by_tmdb[str(row[0])] = row
        except Exception:
            pass
    items = data.get(item_key, data if isinstance(data, list) else [])
    for item in items:
        try:
            if item_key == 'anime':
                show = item.get('anime') or item.get('show') or item
            else:
                show = item.get('show') or item
            tmdb = show.get('ids', {}).get('tmdb')
            if not tmdb:
                continue
            tmdb = str(tmdb)
            if touched_ids is not None:
                touched_ids.add(tmdb)
            status = str(item.get('status') or '').lower()
            watched = []
            for season in item.get('seasons') or []:
                try:
                    snum = int(season.get('number', season.get('season')))
                except Exception:
                    continue
                for ep in season.get('episodes') or []:
                    if not _simkl_episode_watched(ep):
                        continue
                    tvdb_map = ep.get('tvdb') if isinstance(ep.get('tvdb'), dict) else None
                    try:
                        if tvdb_map and tvdb_map.get('season') is not None and tvdb_map.get('episode') is not None:
                            ep_snum = int(tvdb_map['season'])
                            epnum = int(tvdb_map['episode'])
                        else:
                            ep_snum = snum
                            epnum = int(ep.get('number', ep.get('episode')))
                    except Exception:
                        continue
                    watched.append((ep_snum, epnum))
            aired = _simkl_aired_count(item, show, watched)
            extra = {'title': show.get('title') or '', 'status': status}
            nxt = _simkl_se_pair(item.get('next_to_watch'))
            if nxt:
                extra['next'] = nxt
            last = _simkl_se_pair(item.get('last_watched'))
            if last:
                extra['last'] = last
            _upsert_tv_indicator(by_tmdb, tmdb, aired, watched, extra)
        except Exception:
            pass
    del indicators[:]
    indicators.extend(by_tmdb.values())


def _tv_indicators_from_data(data, date_from=None):
    touched_ids = set() if date_from else None
    indicators = []
    _append_tv_indicator_rows(indicators, touched_ids, data or {}, 'shows')
    _append_tv_indicator_rows(indicators, touched_ids, data or {}, 'anime')
    return indicators, touched_ids


def _fetch_tv_indicators(date_from=None):
    if date_from:
        # Phase 2: one multi-type request (shows + anime; movies ignored here).
        data = call_simkl_rewatch(_simkl_rewatch_path('/sync/all-items?%s' % _simkl_with_date_from(_SIMKL_PHASE2_ALL_QUERY, date_from)), method='get') or {}
        return _tv_indicators_from_data(data, date_from)
    # Phase 1: sequential per-type full pulls (Simkl guidance for large libraries).
    indicators = []
    shows = call_simkl_rewatch(_simkl_rewatch_path('/sync/all-items/shows?%s' % _SIMKL_TV_SYNC_QUERY), method='get') or {}
    _append_tv_indicator_rows(indicators, None, shows, 'shows')
    anime = call_simkl_rewatch(_simkl_rewatch_path('/sync/all-items/anime?%s' % _SIMKL_ANIME_SYNC_QUERY), method='get') or {}
    _append_tv_indicator_rows(indicators, None, anime, 'anime')
    return indicators, None


def _fetch_phase2_indicators(date_from):
    """Phase 2 continuous sync: one /sync/all-items?date_from= for movies + shows + anime."""
    if not date_from:
        return [], [], None
    data = call_simkl_rewatch(_simkl_rewatch_path('/sync/all-items?%s' % _simkl_with_date_from(_SIMKL_PHASE2_ALL_QUERY, date_from)), method='get') or {}
    movies = _movie_indicators_from_data(data, filter_status=True)
    tv, touched = _tv_indicators_from_data(data, date_from)
    return movies, tv, touched


def _merge_movie_indicators(existing, delta):
    out = set(existing or [])
    out.update(delta or [])
    return list(out)


def _merge_tv_indicators(existing, delta, touched_ids):
    by_tmdb = {}
    for row in existing or []:
        try:
            by_tmdb[str(row[0])] = row
        except Exception:
            pass
    delta_ids = set()
    for row in delta or []:
        try:
            tid = str(row[0])
            by_tmdb[tid] = row
            delta_ids.add(tid)
        except Exception:
            pass
    for tid in (touched_ids or set()):
        if tid not in delta_ids and tid in by_tmdb:
            old = by_tmdb[tid]
            extra = old[3] if len(old) > 3 else {}
            try:
                by_tmdb[tid] = (old[0], old[1], [], extra)
            except Exception:
                pass
    return list(by_tmdb.values())


def getWatchedActivity():
    """Latest movies/tv/anime watched activity timestamp (UTC seconds), Trakt-shaped helper."""
    try:
        latest = call_simkl('/sync/activities', method='get') or {}
        stamps = []
        for block in (latest.get('movies') or {}, latest.get('tv_shows') or {}, latest.get('anime') or {}):
            for key in ('completed', 'watching', 'all'):
                ts = _activity_ts(block.get(key, ''))
                if ts:
                    stamps.append(ts)
        stamps.append(_activity_ts(latest.get('all', '')))
        return max(stamps) if stamps else 0
    except Exception:
        return 0


def syncSeason(imdb, tmdb=None):
    """Fully watched season numbers from the local Simkl TV indicator cache."""
    try:
        rows = cachesyncTVShows(timeout=720) or []
        tmdb_s = str(tmdb or '0')
        row = None
        if tmdb_s not in ('0', '', 'None'):
            for item in rows:
                try:
                    if str(item[0]) == tmdb_s:
                        row = item
                        break
                except Exception:
                    continue
        if row is None:
            return []
        watched = row[2] or []
        by_season = {}
        for pair in watched:
            try:
                season_n, episode_n = int(pair[0]), int(pair[1])
            except Exception:
                continue
            by_season.setdefault(season_n, set()).add(episode_n)
        fully = []
        for season_n, episodes in by_season.items():
            # A watched prefix is not a finished season. Episode 1 alone used to match
            # (min 1, length 1, max 1). Season ticks use the season's episode count.
            if not episodes or len(episodes) < 2:
                continue
            if min(episodes) == 1 and len(episodes) >= max(episodes):
                fully.append('%01d' % season_n)
        return fully
    except Exception:
        return []


def _list_ids(tmdb=None, imdb=None, tvdb=None):
    ids = {}
    if tmdb and str(tmdb) not in ('0', '', 'None'):
        try:
            ids['tmdb'] = int(tmdb)
        except Exception:
            pass
    if imdb and str(imdb) not in ('0', '', 'None'):
        ids['imdb'] = _normalize_imdb(imdb)
    if tvdb and str(tvdb) not in ('0', '', 'None'):
        try:
            ids['tvdb'] = int(tvdb)
        except Exception:
            pass
    return ids


def _ids_match(item_ids, ids):
    if not isinstance(item_ids, dict) or not isinstance(ids, dict):
        return False
    for key in ('tmdb', 'imdb', 'tvdb'):
        item_value = item_ids.get(key)
        wanted_value = ids.get(key)
        if item_value in (None, '', 'None', 0, '0') or wanted_value in (None, '', 'None', 0, '0'):
            continue
        if str(item_value) == str(wanted_value):
            return True
    return False


def _item_in_status(media_kind, status, ids):
    try:
        if media_kind == 'movies':
            items = _fetch_status('movies', status)
        else:
            items = _fetch_tv_status(status)
        for item in items:
            if _ids_match(item.get('ids'), ids):
                return True
    except Exception:
        pass
    return False


def markMovieAsWatched(imdb, tmdb=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    return call_simkl_rewatch(_simkl_rewatch_path('/sync/history'), data={'movies': [{'ids': ids}]})


def markMovieAsNotWatched(imdb, tmdb=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    return call_simkl('/sync/history/remove', data={'movies': [{'ids': ids}]})


def markEpisodeAsWatched(imdb, season, episode, tmdb=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    season, episode = int(season), int(episode)
    return call_simkl_rewatch(_simkl_rewatch_path('/sync/history'), data={
        'shows': [{'ids': ids, 'seasons': [{'number': season, 'episodes': [{'number': episode}]}]}]
    })


def markEpisodeAsNotWatched(imdb, season, episode, tmdb=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    season, episode = int(season), int(episode)
    return call_simkl('/sync/history/remove', data={
        'shows': [{'ids': ids, 'seasons': [{'number': season, 'episodes': [{'number': episode}]}]}]
    })


def _history_added_episodes(result):
    if not isinstance(result, dict):
        return 0
    try:
        return int((result.get('added') or {}).get('episodes') or 0)
    except Exception:
        return 0


def _history_counts_ok(result):
    if not isinstance(result, dict):
        return False
    bucket = result.get('added') or {}
    if _history_added_episodes(result) > 0:
        return True
    for key in ('shows', 'anime'):
        val = bucket.get(key, 0)
        try:
            if int(val or 0) > 0:
                return True
        except Exception:
            pass
    return False


def _history_not_found(result):
    if not isinstance(result, dict):
        return False
    nf = result.get('not_found') or {}
    for key in ('shows', 'anime', 'episodes'):
        val = nf.get(key)
        if isinstance(val, list) and val:
            return True
        try:
            if int(val or 0) > 0:
                return True
        except Exception:
            pass
    return False


def _regular_season_numbers(tmdb):
    if not tmdb or str(tmdb) in ('0', '', 'None'):
        return []
    try:
        from resources.lib.modules import tmdb_utils
        url = '%stv/%s?api_key=%s&language=en-US' % (tmdb_utils.API_URL, int(tmdb), tmdb_utils._tmdb_api_key())
        data = requests.get(url, timeout=20).json() or {}
    except Exception:
        return []
    nums, seen = [], set()
    for item in data.get('seasons') or []:
        try:
            n = int(item.get('season_number'))
        except Exception:
            continue
        if n > 0 and n not in seen:
            seen.add(n)
            nums.append(n)
    return nums


def markTVShowAsWatched(imdb, tmdb=None):
    """Whole-show history. Simkl can move Completed without episode timestamps; Refresh Simkl Cache then drops ticks.
    If added.episodes is 0, POST each regular TMDb season number (same as Red Light 2.3.7)."""
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return False
    result = call_simkl_rewatch(_simkl_rewatch_path('/sync/history'), data={'shows': [{'ids': ids, 'status': 'completed'}]})
    if result is None:
        log_utils.log('Simkl history mark_as_watched network failure for tvshow tmdb=%s' % tmdb, 1)
        return False
    if _history_added_episodes(result) > 0:
        return True
    if _history_counts_ok(result):
        nums = _regular_season_numbers(tmdb)
        if nums:
            log_utils.log('Simkl history mark_as_watched show added.episodes=0 tmdb=%s, expanding seasons' % tmdb, 1)
            result = call_simkl_rewatch(_simkl_rewatch_path('/sync/history'), data={'shows': [{'ids': ids, 'seasons': [{'number': n} for n in nums]}]})
            if result is None:
                log_utils.log('Simkl history season-expand network failure for tvshow tmdb=%s' % tmdb, 1)
                return False
            log_utils.log('Simkl history show season-expand tmdb=%s seasons=%s added_episodes=%s' % (
                tmdb, len(nums), _history_added_episodes(result)), 1)
            if _history_added_episodes(result) > 0:
                return True
        log_utils.log('Simkl history mark_as_watched show no episode expansion tmdb=%s: %s' % (tmdb, result), 1)
        return False
    if isinstance(result, dict) and not _history_not_found(result):
        return True
    log_utils.log('Simkl history mark_as_watched failed for tvshow tmdb=%s: %s' % (tmdb, result), 1)
    return False


def markTVShowAsNotWatched(imdb, tmdb=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    return call_simkl('/sync/history/remove', data={'shows': [{'ids': ids}]})


def getSimklAddonMovieInfo():
    """True when official script.simkl should own movie scrobble (defer Gratis Red mark)."""
    try:
        addon = control.addon('script.simkl')
    except Exception:
        return False
    try:
        token = (addon.getSetting('access_token') or addon.getSetting('token') or
                 addon.getSetting('authorization') or '').strip()
    except Exception:
        token = ''
    if not token:
        return False
    for key in ('auto_scrobble', 'autoscrobble', 'scrobble_enabled', 'auto_scrobble_enabled'):
        try:
            if addon.getSetting(key) in ('true', 'True', '1'):
                return True
        except Exception:
            pass
    return False


def getSimklAddonEpisodeInfo():
    return getSimklAddonMovieInfo()


def _scrobble_payload(media_type, percent, tmdb=None, imdb=None, season=None, episode=None):
    ids = _list_ids(tmdb=tmdb, imdb=imdb)
    if not ids:
        return None
    data = {'progress': float(percent or 0)}
    if media_type == 'movie':
        data['movie'] = {'ids': ids}
    else:
        data['show'] = {'ids': ids}
        data['episode'] = {'season': int(season), 'number': int(episode)}
    return data


def simkl_scrobble(action, media_type, percent=0, tmdb=None, imdb=None, season=None, episode=None):
    """Native Simkl scrobble. Skips when Indicators != Simkl or script.simkl auto-scrobble is on."""
    if getIndicatorsProvider() != 'simkl':
        return
    if media_type == 'movie' and getSimklAddonMovieInfo():
        return
    if media_type != 'movie' and getSimklAddonEpisodeInfo():
        return
    path = {'start': '/scrobble/start', 'pause': '/scrobble/pause', 'stop': '/scrobble/stop'}.get(action)
    if not path:
        return
    payload = _scrobble_payload(media_type, percent, tmdb=tmdb, imdb=imdb, season=season, episode=episode)
    if not payload:
        return
    # allow_rewatch is stop-only. Never send it on start (Simkl rejects it) or pause.
    if action == 'stop':
        result = call_simkl_rewatch(_simkl_rewatch_path(path), data=payload)
        try:
            log_utils.log('Simkl scrobble stop %s percent=%s' % (media_type, percent))
        except Exception:
            pass
        return result
    result = call_simkl(path, data=payload)
    try:
        log_utils.log('Simkl scrobble %s %s percent=%s' % (action, media_type, percent))
    except Exception:
        pass
    return result


def syncSimklWatched(silent=True, force_update=False):
    """Refresh Simkl watched indicator caches via /sync/activities + optional date_from deltas."""
    if not getSimklCredentialsInfo():
        return False
    # Widget/list opens: one /sync/activities per minute (AUTH V2 free = 500/day).
    if not force_update and _simkl_activities_recent() and _load_cached_activities():
        return True
    if not force_update:
        try:
            if control.window.getProperty(_SIMKL_SYNC_BUSY_PROP) == 'true':
                started = float(control.window.getProperty(_SIMKL_SYNC_BUSY_AT_PROP) or 0)
                if started and (time.time() - started) < 180:
                    return False
        except Exception:
            pass
        if not _sync_lock.acquire(False):
            return False
    else:
        _sync_lock.acquire(True)
    try:
        try:
            control.window.setProperty(_SIMKL_SYNC_BUSY_PROP, 'true')
            control.window.setProperty(_SIMKL_SYNC_BUSY_AT_PROP, '%.3f' % time.time())
        except Exception:
            pass
        status = _sync_simkl_watched_body(force_update=force_update)
        if not silent and status:
            control.infoDialog('Simkl Cache Refreshed.', sound=True)
        return bool(status)
    except Exception as e:
        log_utils.log('Simkl Watched Sync Failed: %s' % e, 1)
        return False
    finally:
        try:
            control.window.setProperty(_SIMKL_SYNC_BUSY_PROP, 'false')
            control.window.clearProperty(_SIMKL_SYNC_BUSY_AT_PROP)
        except Exception:
            pass
        try:
            _sync_lock.release()
        except Exception:
            pass


def _sync_simkl_watched_body(force_update=False):
    user = control.setting('simkl.user').strip() or 'simkl'
    if force_update:
        _bust_sync_cache()
        _store_cached_activities({})
    try:
        latest = call_simkl('/sync/activities', method='get')
    except Exception:
        return False
    if not latest:
        return False
    _simkl_note_activities_poll()
    cached = _load_cached_activities()
    if not force_update and _activity_ts(latest.get('all', '')) <= _activity_ts(cached.get('all', '')):
        return True
    date_from = None if force_update else _simkl_date_from(cached)
    movies, shows = latest.get('movies', {}), latest.get('tv_shows', {})
    anime = latest.get('anime', {})
    cached_movies, cached_shows = cached.get('movies', {}), cached.get('tv_shows', {})
    cached_anime = cached.get('anime', {})
    need_movies = force_update or _activity_block_changed(movies, cached_movies, _SIMKL_MOVIE_WATCHED_ACTIVITY_KEYS)
    need_tv = force_update or _activity_block_changed(shows, cached_shows, _SIMKL_SHOW_WATCHED_ACTIVITY_KEYS) \
        or _activity_block_changed(anime, cached_anime, _SIMKL_SHOW_WATCHED_ACTIVITY_KEYS)
    if force_update or _activity_block_changed(movies, cached_movies, _SIMKL_LIST_ACTIVITY_KEYS):
        clear_simkl_list_status_cache('movies')
    if force_update or _activity_block_changed(shows, cached_shows, _SIMKL_LIST_ACTIVITY_KEYS):
        clear_simkl_list_status_cache('shows')
    if force_update or _activity_block_changed(anime, cached_anime, _SIMKL_LIST_ACTIVITY_KEYS):
        clear_simkl_list_status_cache('anime')
    if force_update or _activity_block_changed(movies, cached_movies, _SIMKL_LIST_ACTIVITY_KEYS) \
            or _activity_block_changed(shows, cached_shows, _SIMKL_LIST_ACTIVITY_KEYS) \
            or _activity_block_changed(anime, cached_anime, _SIMKL_LIST_ACTIVITY_KEYS):
        clear_simkl_custom_list_cache()
    movie_from = None if (not date_from or _activity_block_changed(movies, cached_movies, _SIMKL_MOVIE_FULL_SYNC_KEYS)) else date_from
    tv_from = None if (not date_from
        or _activity_block_changed(shows, cached_shows, _SIMKL_SHOW_FULL_SYNC_KEYS)
        or _activity_block_changed(anime, cached_anime, _SIMKL_SHOW_FULL_SYNC_KEYS)) else date_from
    if need_movies and need_tv and movie_from and tv_from and movie_from == tv_from:
        # Simkl Phase 2 multi-type: one request for movies + shows + anime.
        movie_delta, tv_delta, touched = _fetch_phase2_indicators(movie_from)
        existing_m = _read_sync_cache(syncMovies, user) or []
        _write_sync_cache(syncMovies, _merge_movie_indicators(existing_m, movie_delta), user)
        existing_t = _read_sync_cache(syncTVShows, user, _SIMKL_TV_INDICATOR_VER) or []
        _write_sync_cache(syncTVShows, _merge_tv_indicators(existing_t, tv_delta, touched), user, _SIMKL_TV_INDICATOR_VER)
    else:
        if need_movies:
            delta = _fetch_movie_indicators(date_from=movie_from)
            if movie_from:
                existing = _read_sync_cache(syncMovies, user) or []
                _write_sync_cache(syncMovies, _merge_movie_indicators(existing, delta), user)
            else:
                _write_sync_cache(syncMovies, delta, user)
        if need_tv:
            delta, touched = _fetch_tv_indicators(date_from=tv_from)
            if tv_from:
                existing = _read_sync_cache(syncTVShows, user, _SIMKL_TV_INDICATOR_VER) or []
                _write_sync_cache(syncTVShows, _merge_tv_indicators(existing, delta, touched), user, _SIMKL_TV_INDICATOR_VER)
            else:
                _write_sync_cache(syncTVShows, delta, user, _SIMKL_TV_INDICATOR_VER)
    _store_cached_activities(latest)
    return True


def _bust_sync_cache():
    user = control.setting('simkl.user').strip() or 'simkl'
    try:
        cache.remove(syncMovies, user)
    except Exception:
        pass
    try:
        cache.remove(syncTVShows, user, _SIMKL_TV_INDICATOR_VER)
    except Exception:
        pass
    clear_simkl_list_status_cache()
    clear_simkl_custom_list_cache()


def refreshSimklCache(silent=False):
    try:
        ok = syncSimklWatched(silent=True, force_update=True)
        if not silent:
            control.infoDialog('Simkl Cache Refreshed.' if ok else 'Simkl Cache Refresh Failed.', sound=True)
    except Exception:
        if not silent:
            control.infoDialog('Simkl Cache Refresh Failed.', sound=True)
    try:
        control.refresh_list()
    except Exception:
        pass


def manager(name, imdb, tmdb, content):
    try:
        if not getSimklCredentialsInfo():
            return control.infoDialog('Authorise Simkl first.', sound=True)
        is_movie = content == 'movie'
        media_kind = 'movies' if is_movie else 'shows'
        ids = _list_ids(tmdb=tmdb, imdb=imdb)
        if not ids:
            return control.infoDialog('Missing IDs for Simkl Lists Manager.', sound=True, icon='ERROR')
        choices = []
        for status in _STATUSES:
            if is_movie and status in ('watching', 'hold'):
                continue
            label = _STATUS_LABELS[status]
            if _item_in_status(media_kind, status, ids):
                choices.append(('Remove from [B]%s[/B]' % label, 'remove', status))
            else:
                choices.append(('Add to [B]%s[/B]' % label, 'add', status))
        select = control.selectDialog([c[0] for c in choices], 'Simkl Lists Manager')
        if select < 0:
            return
        _, action, status = choices[select]
        label = _STATUS_LABELS.get(status, status)
        if action == 'add':
            if is_movie:
                post = {'movies': [{'to': status, 'ids': ids}]}
            else:
                post = {'shows': [{'to': status, 'ids': ids}]}
            result = call_simkl('/sync/add-to-list', data=post)
        else:
            if not _item_in_status(media_kind, status, ids):
                return control.infoDialog('Item is not in %s.' % label, heading=str(name), sound=True, icon='ERROR')
            if is_movie:
                post = {'movies': [{'ids': ids}]}
            else:
                post = {'shows': [{'ids': ids}]}
            result = call_simkl('/sync/history/remove', data=post)
        ok = result not in (None, False)
        if not ok:
            verb = 'add to' if action == 'add' else 'remove from'
            return control.infoDialog('Could not %s %s.' % (verb, label), heading=str(name), sound=True, icon='ERROR')
        message = ('Added to %s.' if action == 'add' else 'Removed from %s.') % label
        clear_simkl_list_status_cache('movies' if is_movie else 'shows')
        control.infoDialog(message, heading=str(name), sound=True, icon=control.infoLabel('ListItem.Icon'))
        try:
            refreshSimklCache(silent=True)
        except Exception:
            pass
    except Exception:
        control.infoDialog('Simkl Lists Manager failed.', heading=str(name), sound=True, icon='ERROR')
