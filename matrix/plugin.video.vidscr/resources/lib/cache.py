# -*- coding: utf-8 -*-
"""Tiny disk cache for HTTP JSON responses.

Stores each (url, params) pair as ``cache_<md5>.json`` inside the addon's
profile directory. Entries respect a TTL (default 1 hour, overridable per
call and globally clamped by the user's ``cache_ttl_hours`` setting).

Helpers:
  * ``prune()`` — delete every cache file older than its effective TTL.
    Cheap enough to run on every plugin invocation.
  * ``clear_all()`` — wipe every ``cache_*.json`` regardless of age (used
    by the "Clear cache now" Settings button).
"""
import os
import json
import time
import hashlib

import xbmcvfs

from .common import PROFILE_PATH, get_setting_int, log


def _key(url, params):
    raw = url + '|' + json.dumps(params or {}, sort_keys=True)
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def _max_age_seconds(ttl):
    """Clamp the requested TTL by the user's global setting (hours)."""
    user_hours = get_setting_int('cache_ttl_hours', 24)
    if user_hours <= 0:
        # User opted out of caching entirely.
        return 0
    user_seconds = user_hours * 3600
    return min(ttl or user_seconds, user_seconds)


def get(url, params=None, ttl=3600):
    max_age = _max_age_seconds(ttl)
    if max_age <= 0:
        return None
    fn = os.path.join(PROFILE_PATH, 'cache_' + _key(url, params) + '.json')
    if not xbmcvfs.exists(fn):
        return None
    try:
        if (time.time() - os.path.getmtime(fn)) > max_age:
            try:
                os.remove(fn)
            except Exception:
                pass
            return None
        with open(fn, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def put(url, params, data):
    if _max_age_seconds(3600) <= 0:
        return
    fn = os.path.join(PROFILE_PATH, 'cache_' + _key(url, params) + '.json')
    try:
        with open(fn, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass


def prune(default_ttl=3600):
    """Delete every cache_*.json older than the effective TTL.

    Runs on every plugin entry — cheap (one ``listdir`` + ``getmtime`` per
    file) and stops the addon-data folder from growing forever.
    """
    max_age = _max_age_seconds(default_ttl)
    try:
        entries = os.listdir(PROFILE_PATH)
    except Exception:
        return 0
    now = time.time()
    removed = 0
    for name in entries:
        if not name.startswith('cache_') or not name.endswith('.json'):
            continue
        path = os.path.join(PROFILE_PATH, name)
        try:
            # max_age == 0 means caching is disabled — wipe everything.
            if max_age <= 0 or (now - os.path.getmtime(path)) > max_age:
                os.remove(path)
                removed += 1
        except Exception:
            continue
    if removed:
        log('cache: pruned %d expired entries' % removed)
    return removed


def clear_all():
    """Wipe every cache_*.json regardless of age."""
    try:
        entries = os.listdir(PROFILE_PATH)
    except Exception:
        return 0
    removed = 0
    for name in entries:
        if not name.startswith('cache_') or not name.endswith('.json'):
            continue
        try:
            os.remove(os.path.join(PROFILE_PATH, name))
            removed += 1
        except Exception:
            continue
    log('cache: cleared %d entries' % removed)
    return removed
