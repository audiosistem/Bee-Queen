# -*- coding: utf-8 -*-

import os
import re

import requests

from resources.lib.modules import control

BASE_URL = 'https://api.opensubtitles.com/api/v1'
TIMEOUT = 20.0
_DEFAULT_API_KEY = 'GpubxF50wjXZXtRlq83Heh9serfjCFyI'


def _setting(key, default=''):
    value = control.setting(key)
    if value in (None, '', '0', 'empty_setting'):
        return default
    return str(value).strip()


def effective_api_key():
    key = _setting('opensubs.api_key')
    return key or _DEFAULT_API_KEY


def _username():
    return _setting('opensubs.username')


def _password():
    return _setting('opensubs.password')


def _token():
    return _setting('opensubs.token')


def configured():
    return bool(_username()) and bool(_password())


def _headers(token=None):
    headers = {
        'Content-Type': 'application/json',
        'Api-Key': effective_api_key(),
        'User-Agent': 'GratisRed/%s' % control.addonInfo('version'),
    }
    if token:
        headers['Authorization'] = token
    return headers


def _save_token(token):
    if token:
        control.setSetting('opensubs.token', token)


def _normalize_imdb(imdb_id):
    if not imdb_id:
        return ''
    imdb_id = str(imdb_id).strip()
    return imdb_id if imdb_id.startswith('tt') else 'tt%s' % imdb_id


def _imdb_as_int(imdb_id):
    if not imdb_id:
        return None
    text = str(imdb_id).strip().lower()
    if text.startswith('tt'):
        text = text[2:]
    try:
        return int(text)
    except Exception:
        return None


def _parse_feature_imdb(feature_imdb):
    if feature_imdb in (None, ''):
        return None
    try:
        text = str(feature_imdb).strip().lower()
        if text.startswith('tt'):
            text = text[2:]
        return int(text)
    except Exception:
        return None


def authorized():
    if not configured():
        return False
    token = _token()
    if token:
        try:
            response = requests.get('%s/infos/user' % BASE_URL, headers=_headers(token), timeout=TIMEOUT)
            if response.status_code == 200:
                return True
        except Exception:
            pass
    try:
        response = requests.post(
            '%s/login' % BASE_URL,
            headers=_headers(),
            json={'username': _username(), 'password': _password()},
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            return False
        token = response.json().get('token')
        if not token:
            return False
        _save_token(token)
        return True
    except Exception:
        return False


def _title_query(title, season=None, episode=None):
    if not title:
        return ''
    title = str(title).strip()
    if season not in (None, '') and episode not in (None, ''):
        return '%s S%02dE%02d' % (title, int(season), int(episode))
    return title


def _base_search_params(imdb_id, year, season, episode, languages):
    params = {'languages': languages or 'en'}
    if imdb_id:
        params['imdb_id'] = _normalize_imdb(imdb_id)
    if season not in (None, ''):
        params['season_number'] = int(season)
        params['episode_number'] = int(episode)
    elif year not in (None, ''):
        try:
            params['year'] = int(year)
        except Exception:
            pass
    return params


def _parse_search_result(item, expected_imdb_int=None):
    attrs = item.get('attributes') or {}
    parsed_imdb = _parse_feature_imdb((attrs.get('feature_details') or {}).get('imdb_id'))
    if parsed_imdb is not None and expected_imdb_int is not None and parsed_imdb != expected_imdb_int:
        return None
    files = attrs.get('files') or []
    if not files:
        return None
    file_info = files[0]
    file_id, file_name = file_info.get('file_id'), file_info.get('file_name')
    if not file_id or not file_name:
        return None
    return {
        'file_id': file_id,
        'file_name': file_name,
        'moviehash_match': bool(attrs.get('moviehash_match')),
        'language': attrs.get('language'),
    }


def _search_subtitles_request(params, expected_imdb_int=None, filter_imdb=True):
    token = _token()
    if not token and not authorized():
        return []
    try:
        response = requests.get(
            '%s/subtitles' % BASE_URL,
            headers=_headers(token or _token()),
            params=params,
            timeout=TIMEOUT,
        )
        if response.status_code == 401 and authorized():
            response = requests.get(
                '%s/subtitles' % BASE_URL,
                headers=_headers(_token()),
                params=params,
                timeout=TIMEOUT,
            )
        if response.status_code != 200:
            return []
        imdb_filter = expected_imdb_int if filter_imdb else None
        results = []
        for item in response.json().get('data') or []:
            try:
                parsed = _parse_search_result(item, imdb_filter)
                if parsed:
                    results.append(parsed)
            except Exception:
                continue
        return results
    except Exception:
        return []


def _search_subtitles(imdb_id, year, season, episode, languages, title=None):
    expected_imdb_int = _imdb_as_int(imdb_id)
    imdb_params = _base_search_params(imdb_id, year, season, episode, languages)
    results = _search_subtitles_request(imdb_params, expected_imdb_int, filter_imdb=True)
    if results:
        return results
    query = _title_query(title, season, episode)
    if not query:
        return []
    enriched = dict(imdb_params)
    enriched['query'] = query
    results = _search_subtitles_request(enriched, expected_imdb_int, filter_imdb=True)
    if results:
        return results
    title_params = {'languages': languages or 'en', 'query': query}
    if season not in (None, ''):
        title_params['season_number'] = int(season)
        title_params['episode_number'] = int(episode)
    elif year not in (None, ''):
        try:
            title_params['year'] = int(year)
        except Exception:
            pass
    return _search_subtitles_request(title_params, expected_imdb_int, filter_imdb=False)


def _episode_in_filename(season, episode, filename):
    if not filename:
        return False
    lower = filename.lower()
    patterns = (
        r's%02de%02d' % (int(season), int(episode)),
        r's%d[eexx]%d' % (int(season), int(episode)),
        r'%dx%d' % (int(season), int(episode)),
    )
    return any(re.search(pattern, lower) for pattern in patterns)


def _pick_best_subtitle(results, season=None, episode=None):
    if not results:
        return None
    filtered = []
    for item in results:
        file_name = item.get('file_name') or ''
        if season not in (None, '') and episode not in (None, '') and not _episode_in_filename(season, episode, file_name):
            continue
        filtered.append(item)
    pool = filtered or list(results)
    pool.sort(key=lambda item: 1 if item.get('moviehash_match') else 0, reverse=True)
    return pool[0]


def _download_subtitle_content(file_id):
    token = _token()
    if not token and not authorized():
        return None
    try:
        response = requests.post(
            '%s/download' % BASE_URL,
            headers=_headers(token or _token()),
            json={'file_id': file_id},
            timeout=TIMEOUT,
        )
        if response.status_code == 401 and authorized():
            response = requests.post(
                '%s/download' % BASE_URL,
                headers=_headers(_token()),
                json={'file_id': file_id},
                timeout=TIMEOUT,
            )
        if response.status_code != 200:
            return None
        link = response.json().get('link')
        if not link:
            return None
        file_response = requests.get(link, timeout=TIMEOUT)
        if file_response.status_code != 200:
            return None
        try:
            content = file_response.text
        except Exception:
            content = file_response.content
        if isinstance(content, bytes):
            try:
                content = content.decode('utf-8', 'ignore')
            except Exception:
                return None
        return content
    except Exception:
        return None


def _looks_like_subtitle_content(content):
    if not content or not isinstance(content, str):
        return False
    sample = content.lstrip()[:512].lower()
    if '-->' in sample:
        return True
    if sample.startswith('webvtt'):
        return True
    if '[script info]' in sample or '[events]' in sample:
        return True
    return False


def fetch_playback_subtitle(imdb_id, season=None, episode=None, year=None, languages='en', title=None):
    if not configured():
        return None, None
    results = _search_subtitles(imdb_id, year, season, episode, languages, title=title)
    match = _pick_best_subtitle(results, season, episode)
    if not match:
        return None, None
    content = _download_subtitle_content(match.get('file_id'))
    if not _looks_like_subtitle_content(content):
        return None, None
    return content, match.get('file_name') or 'subtitle.srt'


def _fetch_user_quota(token=None):
    token = token or _token()
    if not token:
        return None, None
    try:
        response = requests.get('%s/infos/user' % BASE_URL, headers=_headers(token), timeout=TIMEOUT)
        if response.status_code == 401 and authorized():
            response = requests.get('%s/infos/user' % BASE_URL, headers=_headers(_token()), timeout=TIMEOUT)
        if response.status_code != 200:
            return None, None
        info = response.json().get('data') or {}
        return info.get('remaining_downloads'), info.get('allowed_downloads')
    except Exception:
        return None, None


def check_account(reopen_settings=False):
    if not configured():
        control.okDialog('Enter your OpenSubtitles username and password first.', heading='OpenSubtitles')
        if reopen_settings:
            control.reopen_settings_category(3, 0)
        return
    try:
        response = requests.post(
            '%s/login' % BASE_URL,
            headers=_headers(),
            json={'username': _username(), 'password': _password()},
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            control.okDialog('Login failed. Check your OpenSubtitles username and password.', heading='OpenSubtitles')
            if reopen_settings:
                control.reopen_settings_category(3, 0)
            return
        data = response.json()
        token = data.get('token')
        if token:
            _save_token(token)
        user = data.get('user') or {}
        remaining = user.get('remaining_downloads')
        allowed = user.get('allowed_downloads')
        info_remaining, info_allowed = _fetch_user_quota(token)
        if info_remaining is not None:
            remaining = info_remaining
        if info_allowed is not None:
            allowed = info_allowed
        if remaining is not None and allowed is not None:
            text = 'Account: %s[CR][CR]Downloads remaining (24h): %s of %s' % (_username(), remaining, allowed)
        elif allowed is not None:
            text = 'Account: %s[CR][CR]Daily download limit (24h): %s' % (_username(), allowed)
        else:
            text = 'Account: %s[CR][CR]Download quota: unknown' % _username()
        control.okDialog(text, heading='OpenSubtitles')
    except Exception:
        control.okDialog('Error checking OpenSubtitles account. Check your username and password.', heading='OpenSubtitles')
    if reopen_settings:
        control.reopen_settings_category(3, 0)
