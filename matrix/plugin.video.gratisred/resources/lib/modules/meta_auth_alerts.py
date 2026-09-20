# -*- coding: utf-8 -*-
"""Once-per-session toasts when a meta account grant is rejected.

Fire on token refresh HTTP 401 or OAuth invalid_grant. Simkl / TMDb have no
refresh step, so an authorised 401 (or TMDb session status 3/17) is the
equivalent. Timeouts and 5xx are ignored. Tokens are not cleared.
"""
from __future__ import absolute_import

import json

from resources.lib.modules import control

_PROP = 'gratisred.meta_auth_alerted.%s'
_SERVICES = {
    'trakt': 'Trakt',
    'simkl': 'Simkl',
    'mdblist': 'MDBList',
    'tmdb': 'TMDb Lists',
}


def is_dead_grant(status_code, body=None):
    try:
        if int(status_code) == 401:
            return True
    except (TypeError, ValueError):
        pass
    text = ''
    if isinstance(body, dict):
        try:
            if int(body.get('status_code')) in (3, 17):
                return True
        except (TypeError, ValueError):
            pass
        text = '%s %s' % (body.get('error') or '', body.get('error_description') or body.get('message') or '')
        try:
            text = '%s %s' % (text, json.dumps(body))
        except Exception:
            pass
    elif body:
        try:
            text = body.decode('utf-8', 'ignore') if isinstance(body, (bytes, bytearray)) else str(body)
        except Exception:
            text = str(body)
    return 'invalid_grant' in text.lower()


def _user_active(service_id):
    try:
        if service_id == 'trakt':
            from resources.lib.modules import trakt
            return bool(trakt.getTraktCredentialsInfo())
        if service_id == 'simkl':
            from resources.lib.modules import simkl
            return bool(simkl.getSimklCredentialsInfo())
        if service_id == 'mdblist':
            from resources.lib.modules import mdblist
            return bool(mdblist.getMdblistCredentialsInfo())
        if service_id == 'tmdb':
            from resources.lib.modules import tmdb_utils
            return bool(tmdb_utils.getTMDbCredentialsInfo())
    except Exception:
        return False
    return False


def clear_alert(service_id):
    try:
        control.window.clearProperty(_PROP % service_id)
    except Exception:
        pass


def maybe_notify_refresh_failure(service_id, status_code, body=None):
    if service_id not in _SERVICES:
        return
    if not is_dead_grant(status_code, body):
        return
    if not _user_active(service_id):
        return
    prop = _PROP % service_id
    if control.window.getProperty(prop) == 'true':
        return
    control.window.setProperty(prop, 'true')
    name = _SERVICES[service_id]
    control.infoDialog(
        '%s authorisation failed. Revoke and Authorise again in Account Settings.' % name,
        time=8000, sound=False)
