# -*- coding: utf-8 -*-

import re
import time

import requests
from requests.compat import json, str
#import simplejson as json
from six import ensure_str, ensure_text
from six.moves.urllib_parse import urljoin, quote_plus

from resources.lib.modules import cache
from resources.lib.modules import cleandate
from resources.lib.modules import client
from resources.lib.modules import client_utils
from resources.lib.modules import control
from resources.lib.modules import log_utils


# ---------------------------------------------------------------------------
# PAGINATION HELPER
# ---------------------------------------------------------------------------
# Why: several Trakt endpoints the add-on uses (``/users/me/favorites/*``,
# ``/users/me/collection/*``, some legacy callers) and the local SQLite
# favorites DB return the *entire* collection in a single payload.  With
# large accounts that means the directory freezes Kodi for several
# seconds while every row is rendered, even though the user only ever
# looks at the first page.  This helper produces the current page slice
# and a ``next_page`` integer (or None) that callers can turn into a
# "Next Page" directory entry - exact same UX the existing server-side
# paginated views already have.  Keeping it here (rather than copying
# the logic into every indexer) means it can be reused from movies.py,
# tvshows.py, episodes.py and modules.favorites consistently.
def paginate(items, page=1, page_size=None):
    """Slice ``items`` for directory pagination.

    Returns (page_items, next_page_number_or_None).  ``page`` is 1-based
    to match Trakt's own ``page=1`` convention.  ``page_size`` defaults to
    the add-on's "items.per.page" setting (falling back to 40 if unset /
    invalid) so the directory behaviour matches the rest of the add-on.
    """
    try:
        page = int(page) if page else 1
    except Exception:
        page = 1
    if page < 1:
        page = 1
    if not page_size:
        try:
            page_size = int(control.setting('items.per.page'))
        except Exception:
            page_size = 0
        if not page_size or page_size <= 0:
            page_size = 40
    items = items or []
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    next_page = page + 1 if end < len(items) else None
    return page_items, next_page

BASE_URL = 'https://api.trakt.tv'
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
V2_API_KEY = '33ea6bfa2b06c9cfa3e408fc6b4cc30484f31b90733df3508fd09ce512f47982'
CLIENT_SECRET = '4a294afdab95894be977dc79c9715224dc87a4a88d74944507945ca58bf719b2'
# Trakt API max per-page limit (reduced to 250; see trakt-api discussions #681 / #775)
TRAKT_PAGE_LIMIT = 250
# extended=progress on watched/shows is capped at 100 per page
TRAKT_WATCHED_PROGRESS_PAGE_LIMIT = 100
TRAKT_REFRESH_PROPERTY = 'gratisred.trakt_refreshing_token'


def _trakt_page_limit(query_params):
    ext = str((query_params or {}).get('extended') or '').lower()
    if 'progress' in ext:
        return TRAKT_WATCHED_PROGRESS_PAGE_LIMIT
    return TRAKT_PAGE_LIMIT


def _set_trakt_expires(expires_in):
    try:
        control.setSetting('trakt.expires', str(time.time() + int(expires_in)))
    except Exception:
        pass


def _refreshTraktToken():
    try:
        control.window.setProperty(TRAKT_REFRESH_PROPERTY, 'true')
        oauth = urljoin(BASE_URL, '/oauth/token')
        headers = {'Content-Type': 'application/json', 'trakt-api-key': V2_API_KEY, 'trakt-api-version': '2'}
        opost = {'client_id': V2_API_KEY, 'client_secret': CLIENT_SECRET, 'redirect_uri': REDIRECT_URI,
                 'grant_type': 'refresh_token', 'refresh_token': control.setting('trakt.refresh')}
        result = requests.post(oauth, data=json.dumps(opost), headers=headers, timeout=30).json()
        token, refresh = result['access_token'], result['refresh_token']
        control.setSetting('trakt.token', token)
        control.setSetting('trakt.refresh', refresh)
        _set_trakt_expires(result.get('expires_in', 7200))
        return token
    except Exception as e:
        log_utils.log('Trakt token refresh failed: %s' % e)
        return None
    finally:
        control.window.clearProperty(TRAKT_REFRESH_PROPERTY)


def _ensureTraktTokenFresh():
    if not getTraktCredentialsInfo():
        return
    while control.window.getProperty(TRAKT_REFRESH_PROPERTY) == 'true':
        time.sleep(0.25)
    try:
        expires_at = float(control.setting('trakt.expires') or '0')
    except Exception:
        expires_at = 0.0
    if expires_at > 0 and time.time() >= expires_at:
        _refreshTraktToken()


def valid_trakt_activities(data):
    return isinstance(data, dict) and 'all' in data and isinstance(data.get('movies'), dict) and isinstance(data.get('episodes'), dict)


def getTraktCredentialsInfo():
    user = control.setting('trakt.user').strip()
    token = control.setting('trakt.token')
    refresh = control.setting('trakt.refresh')
    if (user == '' or token == '' or refresh == ''):
        return False
    return True


def __getTraktALT(url, post=None):
    try:
        url = urljoin(BASE_URL, url) if not url.startswith(BASE_URL) else url
        post = json.dumps(post) if post else None
        headers = {'Content-Type': 'application/json', 'trakt-api-key': V2_API_KEY, 'trakt-api-version': '2'}
        if getTraktCredentialsInfo():
            headers.update({'Authorization': 'Bearer %s' % control.setting('trakt.token')})
        result = client.request(url, post=post, headers=headers, output='extended', error=True)
        result = client_utils.byteify(result)
        resp_code = result[1]
        resp_header = result[2]
        result = result[0]
        if resp_code in ['423', '500', '502', '503', '504', '520', '521', '522', '524']:
            log_utils.log('Trakt Error: %s' % str(resp_code))
            control.infoDialog('Trakt Error: ' + str(resp_code), sound=True)
            return
        elif resp_code in ['429']:
            log_utils.log('Trakt Rate Limit Reached: %s' % str(resp_code))
            control.infoDialog('Trakt Rate Limit Reached: ' + str(resp_code), sound=True)
            return
        elif resp_code in ['404']:
            log_utils.log('Trakt Object Not Found : %s' % str(resp_code))
            return
        if resp_code not in ['401', '405', '403']:
            return result, resp_header
        oauth = urljoin(BASE_URL, '/oauth/token')
        opost = {'client_id': V2_API_KEY, 'client_secret': CLIENT_SECRET, 'redirect_uri': REDIRECT_URI, 'grant_type': 'refresh_token', 'refresh_token': control.setting('trakt.refresh')}
        result = client.request(oauth, post=json.dumps(opost), headers=headers)
        result = client_utils.json_loads_as_str(result)
        token, refresh = result['access_token'], result['refresh_token']
        control.setSetting('trakt.token', token)
        control.setSetting('trakt.refresh', refresh)
        headers['Authorization'] = 'Bearer %s' % token
        result = client.request(url, post=post, headers=headers, output='extended', error=True)
        result = client_utils.byteify(result)
        return result[0], result[2]
    except:
        pass


def __getTrakt(url, post=None):
    # ---------------------------------------------------------------------
    # FIX (Trakt lists missing): the original implementation returned a bare
    # ``None`` on any server / rate-limit / transport error.  Every caller in
    # this module (e.g. ``getTraktAsJson``) immediately unpacks the result
    # with ``r, res_headers = __getTrakt(url)`` which raises a
    # ``TypeError: cannot unpack non-iterable NoneType object`` the moment
    # Trakt hiccups.  That exception is then swallowed by the caller's own
    # blanket ``try/except`` and the user just sees an *empty* directory –
    # i.e. the "block" symptom where lists silently fail to load.
    #
    # We now ALWAYS return a 2-tuple ``(body_or_None, headers_dict)`` so
    # tuple-unpacking never blows up.  Transient 5xx / 429 are logged only
    # (no more spammy "Trakt Error 502" pop-up that previously discouraged
    # the caller from retrying).  A single short retry with the server's
    # ``Retry-After`` value is attempted on 429 before giving up.
    # ---------------------------------------------------------------------
    try:
        url = urljoin(BASE_URL, url) if not url.startswith(BASE_URL) else url
        post = json.dumps(post) if post else None
        headers = {'Content-Type': 'application/json', 'trakt-api-key': V2_API_KEY, 'trakt-api-version': '2'}
        if getTraktCredentialsInfo():
            _ensureTraktTokenFresh()
            headers.update({'Authorization': 'Bearer %s' % control.setting('trakt.token')})
        if not post:
            r = requests.get(url, headers=headers, timeout=30)
        else:
            r = requests.post(url, data=post, headers=headers, timeout=30)
        r.encoding = 'utf-8'
        resp_code = str(r.status_code)
        resp_header = r.headers
        result = r.text
        if resp_code in ['423', '500', '502', '503', '504', '520', '521', '522', '524']:
            # Log only - popping a modal for every transient gateway error
            # was both noisy and, combined with the old ``return`` below,
            # caused list views to appear empty.
            log_utils.log('Trakt Error: %s on %s' % (str(resp_code), url))
            return None, resp_header
        elif resp_code in ['429']:
            # Rate-limited.  Trakt sends a ``Retry-After`` header (seconds).
            # Do one polite short wait + retry so large list enumerations
            # (which legitimately hit the API many times) don't terminate
            # prematurely and drop the remaining pages.
            wait = 2
            try:
                wait = max(1, min(10, int(resp_header.get('Retry-After', '2'))))
            except Exception:
                wait = 2
            log_utils.log('Trakt Rate Limit %s - sleeping %ss then retrying %s' % (resp_code, wait, url))
            time.sleep(wait)
            if not post:
                r = requests.get(url, headers=headers, timeout=30)
            else:
                r = requests.post(url, data=post, headers=headers, timeout=30)
            r.encoding = 'utf-8'
            if str(r.status_code) == '200':
                return r.text, r.headers
            return None, r.headers
        elif resp_code in ['404']:
            log_utils.log('Trakt Object Not Found : %s' % str(resp_code))
            return None, resp_header
        if resp_code not in ['401', '405', '403']:
            return result, resp_header
        # 401/403/405 => access token expired, try refreshing once and replay.
        token = _refreshTraktToken()
        if not token:
            return None, resp_header
        headers['Authorization'] = 'Bearer %s' % token
        if not post:
            r = requests.get(url, headers=headers, timeout=30)
        else:
            r = requests.post(url, data=post, headers=headers, timeout=30)
        r.encoding = 'utf-8'
        return r.text, r.headers
    except Exception as e:
        # Network / DNS / SSL failure: still return a well-formed tuple so
        # that downstream ``r, res_headers = __getTrakt(...)`` never explodes.
        log_utils.log('Trakt request failed for %s : %s' % (url, e))
        return None, {}


def _released_key(item):
    if 'released' in item:
        return item['released'] or '0'
    elif 'first_aired' in item:
        return item['first_aired'] or '0'
    else:
        return '0'


def sort_list(sort_key, sort_direction, list_data):
    reverse = False if sort_direction == 'asc' else True
    if sort_key == 'rank':
        return sorted(list_data, key=lambda x: x['rank'], reverse=reverse)
    elif sort_key == 'added':
        return sorted(list_data, key=lambda x: x['listed_at'], reverse=reverse)
    elif sort_key == 'title':
        return sorted(list_data, key=lambda x: x[x['type']].get('title'), reverse=reverse)
    elif sort_key == 'released':
        return sorted(list_data, key=lambda x: _released_key(x[x['type']]), reverse=reverse)
    elif sort_key == 'runtime':
        return sorted(list_data, key=lambda x: x[x['type']].get('runtime', 0), reverse=reverse)
    elif sort_key == 'popularity':
        return sorted(list_data, key=lambda x: x[x['type']].get('votes', 0), reverse=reverse)
    elif sort_key == 'percentage':
        return sorted(list_data, key=lambda x: x[x['type']].get('rating', 0), reverse=reverse)
    elif sort_key == 'votes':
        return sorted(list_data, key=lambda x: x[x['type']].get('votes', 0), reverse=reverse)
    else:
        return list_data


def getTraktAsJson(url, post=None):
    try:
        r, res_headers = __getTrakt(url, post)
        # ``__getTrakt`` may now legitimately return ``(None, headers)`` on
        # 404/5xx; guard the JSON decode so callers get ``None`` rather than
        # a silently-swallowed exception (which previously looked to users
        # like "Trakt isn't returning all my lists").
        if not r:
            return None
        r = client_utils.json_loads_as_str(r)
        if 'X-Sort-By' in res_headers and 'X-Sort-How' in res_headers:
            r = sort_list(res_headers['X-Sort-By'], res_headers['X-Sort-How'], r)
        return r
    except:
        pass


def getTraktAsJsonPaged(url, page_size=None):
    """
    Fetch a Trakt endpoint that supports pagination and return *all* results
    concatenated, following every page reported by the ``X-Pagination-Page-Count``
    response header.

    WHY THIS FUNCTION EXISTS
    ------------------------
    Trakt paginates almost every "list" endpoint (``/users/me/lists``,
    ``/users/likes/lists``, ``/users/me/watchlist/*``, ``/users/me/history/*``
    etc.).  The maximum allowed ``limit`` per page is now **250** (100 when
    ``extended=progress``).  Without walking the pages you only ever see the
    first chunk, which is exactly the user-visible bug ("Trakt doesn't get
    all its lists – some kind of block").

    The helper:
      * forces a sane ``limit`` (250 default, 100 for progress endpoints),
      * starts at ``page=1`` and increments until
        ``X-Pagination-Page-Count`` is reached (or the server stops
        returning items),
      * merges every page's JSON array into one flat list,
      * preserves Trakt's server-side sort when only a single page is
        returned (so behaviour is unchanged for small accounts),
      * hard-caps at 50 pages as a safety belt in case a buggy server
        sends absurd header values.
    """
    try:
        # Build the URL with explicit limit/page.  We respect any query
        # string the caller already provided so things like
        # ``?extended=full`` or ``?type=list`` survive untouched.
        split = url.split('?', 1)
        base = split[0]
        existing = dict()
        if len(split) == 2 and split[1]:
            for kv in split[1].split('&'):
                if '=' in kv:
                    k, v = kv.split('=', 1)
                    existing[k] = v
        # Remove legacy out-of-range limits (e.g. limit=1000000) and use
        # Trakt's current per-page maximum for this endpoint.
        page_limit = _trakt_page_limit(existing)
        if page_size is None:
            page_size = page_limit
        try:
            limit = int(existing.get('limit', str(page_size)))
            if limit <= 0 or limit > page_limit:
                limit = page_size
        except Exception:
            limit = page_size
        existing['limit'] = str(min(int(limit), page_limit))

        merged = []
        current_page = 1
        max_pages = 50  # safety belt, see docstring
        while current_page <= max_pages:
            existing['page'] = str(current_page)
            qs = '&'.join('%s=%s' % (k, v) for k, v in existing.items())
            page_url = '%s?%s' % (base, qs)

            r, res_headers = __getTrakt(page_url, None)
            if not r:
                # Transport/5xx error on this page: stop but return what we
                # already have rather than dropping the whole enumeration.
                break
            try:
                data = client_utils.json_loads_as_str(r)
            except Exception:
                break
            if not isinstance(data, list):
                # Unexpected payload (e.g. an error dict); bail.
                return data
            merged.extend(data)

            # Determine total pages from Trakt's response headers.  If the
            # endpoint doesn't paginate (``/users/me/lists`` for example,
            # which is non-paginated on most accounts) the header will be
            # missing and we stop after the first page – exactly the old
            # behaviour.
            try:
                total_pages = int(res_headers.get('X-Pagination-Page-Count', '1'))
            except Exception:
                total_pages = 1
            if current_page >= total_pages:
                break
            if len(data) < limit:
                # Server returned fewer items than we asked for => we've
                # hit the end regardless of what the header claims.
                break
            current_page += 1

        # Honour Trakt's sort hints only when the server returned a single
        # page; for multi-page merges the per-page order is already
        # consistent and re-sorting would discard the natural order of
        # "most recently liked first" etc.
        if current_page == 1 and res_headers and 'X-Sort-By' in res_headers and 'X-Sort-How' in res_headers:
            merged = sort_list(res_headers['X-Sort-By'], res_headers['X-Sort-How'], merged)
        return merged
    except Exception as e:
        log_utils.log('getTraktAsJsonPaged failed for %s : %s' % (url, e))
        return []


def revokeTrakt(reopen_settings=False):
    """Revoke tokens at Trakt and clear local credentials."""
    if not getTraktCredentialsInfo():
        control.infoDialog('No Trakt account is authorised.', sound=True)
        return
    try:
        token = (control.setting('trakt.token') or '').strip()
        refresh = (control.setting('trakt.refresh') or '').strip()
        revoke_token = token or refresh
        if revoke_token:
            try:
                client.request(
                    urljoin(BASE_URL, '/oauth/revoke'),
                    post=json.dumps({
                        'token': revoke_token,
                        'client_id': V2_API_KEY,
                        'client_secret': CLIENT_SECRET,
                    }),
                    headers={'Content-Type': 'application/json'},
                    timeout='15',
                )
            except Exception as e:
                log_utils.log('Trakt revoke API call failed: %s' % e, 1)
        control.setSetting('trakt.user', '')
        control.setSetting('trakt.authed', '')
        control.setSetting('trakt.token', '')
        control.setSetting('trakt.refresh', '')
        control.setSetting('trakt.expires', '')
        control.infoDialog('Trakt Account Revoked.', sound=True)
        control.finish_auth_ui(reopen_settings=reopen_settings)
    except Exception:
        control.infoDialog('Trakt Revoke Failed.', sound=True)


def authTrakt(reopen_settings=False):
    from resources.lib.modules import auth_utils
    progress = None
    try:
        if getTraktCredentialsInfo():
            control.infoDialog('Trakt is already authorised. Use Revoke Trakt Account to sign out.', sound=True)
            return
        progress = auth_utils.auth_progress_dialog('Trakt Authorise', '')
        progress.update('Connecting to Trakt...')
        result = getTraktAsJson('/oauth/device/code', {'client_id': V2_API_KEY})
        if not result or not result.get('device_code'):
            control.infoDialog('Trakt Authorisation Failed.', sound=True)
            return
        user_code = str(result.get('user_code', ''))
        device_code = result['device_code']
        expires_in = int(result.get('expires_in', 600))
        interval = max(int(result.get('interval', 5)), 1)
        auth_url = 'https://trakt.tv/activate?code=%s' % user_code
        progress.update('Preparing QR code...')
        qr_code = auth_utils.make_qrcode(auth_url) or ''
        short_url = auth_utils.make_tinyurl(auth_url)
        auth_utils.copy2clip(auth_url)
        insert = '[CR]OR visit [B]%s[/B]' % short_url if short_url else ''
        verify_display = (result.get('verification_url') or 'trakt.tv/activate').replace('https://', '')
        content = ('Enter [B]%s[/B] at [B]%s[/B][CR]OR scan the [B]QR Code[/B][CR]Link copied to clipboard%s[CR][CR]'
                   'Waiting for authorisation...' % (user_code, verify_display, insert))
        progress.update(content, qr_path=qr_code)
        token_result = None
        start = time.time()
        while not progress.iscanceled() and (time.time() - start) < expires_in:
            if auth_utils.auth_progress_wait(progress, interval):
                break
            try:
                r = getTraktAsJson('/oauth/device/token', {
                    'client_id': V2_API_KEY,
                    'client_secret': CLIENT_SECRET,
                    'code': device_code,
                })
                if isinstance(r, dict) and r.get('access_token'):
                    token_result = r
                    break
            except Exception:
                pass
        canceled = progress.iscanceled()
        auth_utils.close_auth_progress_dialog(progress)
        progress = None
        if canceled or not token_result:
            control.infoDialog('Trakt Authorisation Canceled.' if canceled else 'Trakt Authorisation Failed.', sound=True)
            return
        token, refresh = token_result['access_token'], token_result['refresh_token']
        headers = {'Content-Type': 'application/json', 'trakt-api-key': V2_API_KEY, 'trakt-api-version': '2', 'Authorization': 'Bearer %s' % token}
        result = client.request(urljoin(BASE_URL, '/users/me'), headers=headers)
        result = client_utils.json_loads_as_str(result)
        user = result.get('username', '')
        authed = '' if user == '' else str('yes')
        control.setSetting('trakt.user', user)
        control.setSetting('trakt.authed', authed)
        control.setSetting('trakt.token', token)
        control.setSetting('trakt.refresh', refresh)
        _set_trakt_expires(token_result.get('expires_in', 7200))
        control.infoDialog('Trakt Account Authorised.', sound=True)
        control.finish_auth_ui(reopen_settings=reopen_settings)
    except Exception:
        control.infoDialog('Trakt Authorisation Failed.', sound=True)
    finally:
        if progress is not None:
            auth_utils.close_auth_progress_dialog(progress)


def getTraktIndicatorsInfo():
    indicators = control.setting('indicators') if getTraktCredentialsInfo() == False else control.setting('indicators.alt')
    indicators = True if indicators == '1' else False
    return indicators


def getTraktAddonMovieInfo():
    try:
        scrobble = control.addon('script.trakt').getSetting('scrobble_movie')
    except:
        scrobble = ''
    try:
        ExcludeHTTP = control.addon('script.trakt').getSetting('ExcludeHTTP')
    except:
        ExcludeHTTP = ''
    try:
        authorization = control.addon('script.trakt').getSetting('authorization')
    except:
        authorization = ''
    if scrobble == 'true' and ExcludeHTTP == 'false' and not authorization == '':
        return True
    else:
        return False


def getTraktAddonEpisodeInfo():
    try:
        scrobble = control.addon('script.trakt').getSetting('scrobble_episode')
    except:
        scrobble = ''
    try:
        ExcludeHTTP = control.addon('script.trakt').getSetting('ExcludeHTTP')
    except:
        ExcludeHTTP = ''
    try:
        authorization = control.addon('script.trakt').getSetting('authorization')
    except:
        authorization = ''
    if scrobble == 'true' and ExcludeHTTP == 'false' and not authorization == '':
        return True
    else:
        return False


def slug(name):
    name = name.strip()
    name = name.lower()
    name = re.sub(r'[^a-z0-9_]', '-', name)
    name = re.sub(r'--+', '-', name)
    if name.endswith('-'):
        name = name.rstrip('-')
    return name


def _trakt_probe_list_types(username, list_slug, limit=8):
    types = set()
    try:
        probe_url = '/users/%s/lists/%s/items?limit=%s' % (username, list_slug, int(limit))
        items = getTraktAsJson(probe_url) or []
        for item in items:
            if item.get('movie'):
                types.add('movie')
            if item.get('show'):
                types.add('show')
            if item.get('episode'):
                types.add('episode')
            if item.get('season'):
                types.add('season')
    except:
        pass
    return types


def _trakt_userlist_action(menu_type, item_types, item_count=0):
    if not menu_type:
        return 'movies'
    if item_count == 0:
        if menu_type == 'movie':
            return 'movies'
        if menu_type == 'tvshow':
            return 'tvshows'
        return 'calendar'
    if menu_type == 'movie':
        return 'movies' if 'movie' in item_types else None
    if menu_type == 'tvshow':
        return 'tvshows' if item_types & {'show', 'season'} else None
    if menu_type == 'episode':
        if 'episode' in item_types:
            return 'calendar'
        if item_types & {'show', 'season'}:
            return 'tvshows'
        return None
    return 'movies'


def build_user_list_directory(url, trakt_list_link, menu_type=None, image='trakt.png'):
    entries = []
    items = getTraktAsJsonPaged(url) or []
    for item in items:
        try:
            try:
                name = item['list']['name']
                username = slug(item['list']['user']['username'])
                list_slug = item['list']['ids']['slug']
                item_count = int(item['list'].get('item_count') or item.get('item_count') or 0)
            except:
                name = item['name']
                username = 'me'
                list_slug = item['ids']['slug']
                item_count = int(item.get('item_count') or 0)
            name = client_utils.replaceHTMLCodes(name)
            list_url = trakt_list_link % (username, list_slug)
            item_types = _trakt_probe_list_types(username, list_slug) if menu_type and item_count else set()
            action = _trakt_userlist_action(menu_type, item_types, item_count)
            if menu_type and action is None:
                continue
            entries.append({'name': name, 'url': list_url, 'context': list_url, 'image': image, 'action': action or 'movies'})
        except:
            pass
    return entries


def user_list_directory_movie(url, trakt_list_link, user=None):
    return build_user_list_directory(url, trakt_list_link, menu_type='movie')


def user_list_directory_tvshow(url, trakt_list_link, user=None):
    return build_user_list_directory(url, trakt_list_link, menu_type='tvshow')


def user_list_directory_episode(url, trakt_list_link, user=None):
    return build_user_list_directory(url, trakt_list_link, menu_type='episode')


def manager(name, imdb, tmdb, content):
    try:
        post = {"movies": [{"ids": {"imdb": imdb}}]} if content == 'movie' else {"shows": [{"ids": {"tmdb": tmdb}}]}
        items = [('Add to [B]Collection[/B]', '/sync/collection')]
        items += [('Remove from [B]Collection[/B]', '/sync/collection/remove')]
        items += [('Add to [B]Watchlist[/B]', '/sync/watchlist')]
        items += [('Remove from [B]Watchlist[/B]', '/sync/watchlist/remove')]
        items += [('Add to [B]new List[/B]', '/users/me/lists/%s/items')]
        result = getTraktAsJsonPaged('/users/me/lists') or []
        lists = [(i['name'], i['ids']['slug']) for i in result]
        lists = [lists[i//2] for i in range(len(lists)*2)]
        for i in range(0, len(lists), 2):
            lists[i] = ((ensure_str('Add to [B]%s[/B]' % lists[i][0])), '/users/me/lists/%s/items' % lists[i][1])
        for i in range(1, len(lists), 2):
            lists[i] = ((ensure_str('Remove from [B]%s[/B]' % lists[i][0])), '/users/me/lists/%s/items/remove' % lists[i][1])
        items += lists
        select = control.selectDialog([i[0] for i in items], 'Trakt Manager')
        if select == -1:
            return
        elif select == 4:
            t = 'Add to [B]new List[/B]'
            k = control.keyboard('', t) ; k.doModal()
            new = k.getText() if k.isConfirmed() else None
            if (new == None or new == ''):
                return
            result = __getTrakt('/users/me/lists', post={"name": new, "privacy": "private"})[0]
            try:
                slug = client_utils.json_loads_as_str(result)['ids']['slug']
            except:
                return control.infoDialog('Trakt Manager', heading=str(name), sound=True, icon='ERROR')
            result = __getTrakt(items[select][1] % slug, post=post)[0]
        else:
            result = __getTrakt(items[select][1], post=post)[0]
        icon = control.infoLabel('ListItem.Icon') if not result == None else 'ERROR'
        control.infoDialog('Trakt Manager', heading=str(name), sound=True, icon=icon)
    except:
        return


def getPlaybackEpisodes():
    return getTraktAsJsonPaged('/sync/playback/episodes?extended=full') or []


def getPlaybackMovies():
    return getTraktAsJsonPaged('/sync/playback/movies?extended=full') or []


def getActivity():
    try:
        i = getTraktAsJson('/sync/last_activities')
        if not valid_trakt_activities(i):
            return
        activity = []
        activity.append(i['movies']['collected_at'])
        activity.append(i['episodes']['collected_at'])
        activity.append(i['movies']['watchlisted_at'])
        activity.append(i['shows']['watchlisted_at'])
        activity.append(i['seasons']['watchlisted_at'])
        activity.append(i['episodes']['watchlisted_at'])
        activity.append(i['lists']['updated_at'])
        activity.append(i['lists']['liked_at'])
        activity = [int(cleandate.iso_2_utc(i)) for i in activity]
        activity = sorted(activity, key=int)[-1]
        return activity
    except:
        pass


def getWatchedActivity():
    try:
        i = getTraktAsJson('/sync/last_activities')
        if not valid_trakt_activities(i):
            return
        activity = []
        activity.append(i['movies']['watched_at'])
        activity.append(i['episodes']['watched_at'])
        activity = [int(cleandate.iso_2_utc(i)) for i in activity]
        activity = sorted(activity, key=int)[-1]
        return activity
    except:
        pass


def syncMovies(user):
    try:
        if getTraktCredentialsInfo() == False:
            return
        indicators = getTraktAsJsonPaged('/users/me/watched/movies') or []
        indicators = [i['movie']['ids'] for i in indicators]
        indicators = [str(i['imdb']) for i in indicators if 'imdb' in i]
        return indicators
    except:
        pass


def cachesyncMovies(timeout=0):
    indicators = cache.get(syncMovies, timeout, control.setting('trakt.user').strip())
    return indicators


def timeoutsyncMovies():
    timeout = cache.timeout(syncMovies, control.setting('trakt.user').strip())
    return timeout


def syncTVShows(user):
    try:
        if getTraktCredentialsInfo() == False:
            return
        indicators = getTraktAsJsonPaged('/users/me/watched/shows?extended=full') or []
        indicators = [(i['show']['ids']['tmdb'], i['show']['aired_episodes'], sum([[(s['number'], e['number']) for e in s['episodes']] for s in i['seasons']], [])) for i in indicators]
        indicators = [(str(i[0]), int(i[1]), i[2]) for i in indicators]
        return indicators
    except:
        pass


def cachesyncTVShows(timeout=0):
    indicators = cache.get(syncTVShows, timeout, control.setting('trakt.user').strip())
    return indicators


def timeoutsyncTVShows():
    timeout = cache.timeout(syncTVShows, control.setting('trakt.user').strip())
    if not timeout:
        timeout = 0
    return timeout


def syncSeason(imdb):
    try:
        if getTraktCredentialsInfo() == False:
            return
        indicators = getTraktAsJson('/shows/%s/progress/watched?specials=false&hidden=false' % imdb)
        indicators = indicators['seasons']
        indicators = [(i['number'], [x['completed'] for x in i['episodes']]) for i in indicators]
        indicators = ['%01d' % int(i[0]) for i in indicators if not False in i[1]]
        return indicators
    except:
        pass


def markMovieAsWatched(imdb):
    if not imdb.startswith('tt'):
        imdb = 'tt' + imdb
    return __getTrakt('/sync/history', {"movies": [{"ids": {"imdb": imdb}}]})[0]


def markMovieAsNotWatched(imdb):
    if not imdb.startswith('tt'):
        imdb = 'tt' + imdb
    return __getTrakt('/sync/history/remove', {"movies": [{"ids": {"imdb": imdb}}]})[0]


def markTVShowAsWatched(imdb):
    return __getTrakt('/sync/history', {"shows": [{"ids": {"imdb": imdb}}]})[0]


def markTVShowAsNotWatched(imdb):
    return __getTrakt('/sync/history/remove', {"shows": [{"ids": {"imdb": imdb}}]})[0]


def markEpisodeAsWatched(imdb, season, episode):
    season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
    return __getTrakt('/sync/history', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": imdb}}]})[0]


def markEpisodeAsNotWatched(imdb, season, episode):
    season, episode = int('%01d' % int(season)), int('%01d' % int(episode))
    return __getTrakt('/sync/history/remove', {"shows": [{"seasons": [{"episodes": [{"number": episode}], "number": season}], "ids": {"imdb": imdb}}]})[0]


def getMovieTranslation(id, lang, full=False):
    url = '/movies/%s/translations/%s' % (id, lang)
    try:
        item = getTraktAsJson(url)[0]
        return item if full else item.get('title')
    except:
        pass


def getTVShowTranslation(id, lang, season='', episode='', full=False):
    if season and episode:
        url = '/shows/%s/seasons/%s/episodes/%s/translations/%s' % (id, season, episode, lang)
    else:
        url = '/shows/%s/translations/%s' % (id, lang)
    try:
        item = getTraktAsJson(url)[0]
        return item if full else item.get('title')
    except:
        pass


def getMovieAliases(id):
    try:
        return getTraktAsJson('/movies/%s/aliases' % id)
    except:
        return []


def getTVShowAliases(id):
    try:
        return getTraktAsJson('/shows/%s/aliases' % id)
    except:
        return []


def getMovieSummary(id, full=False):
    try:
        url = '/movies/%s' % id
        if full:
            url += '?extended=full'
        return getTraktAsJson(url)
    except:
        return


def getTVShowSummary(id, full=False):
    try:
        url = '/shows/%s' % id
        if full:
            url += '?extended=full'
        return getTraktAsJson(url)
    except:
        return


def getSeasonsSummary(id, full=False, episodes=False):  #Uses imdb_id, full or episodes but not both.
    try:
        url = '/shows/%s/seasons' % id
        if full:
            url += '?extended=full'
        if episodes:
            url += '?extended=episodes'
        return getTraktAsJson(url)
    except:
        return


def getEpisodeSummary(id, season, episode='', full=False):
    try:
        if not episode:
            url = '/shows/%s/seasons/%s' % (id, season)
            #url += '?translations=en'
        else:
            url = '/shows/%s/seasons/%s/episodes/%s' % (id, season, episode)
        if full:
            url += '?extended=full'
        return getTraktAsJson(url)
    except:
        return


#/shows/game-of-thrones/seasons/1/people
#/shows/game-of-thrones/seasons/1/people?extended=guest_stars

#/shows/game-of-thrones/seasons/1/episodes/1/people
#/shows/game-of-thrones/seasons/1/episodes/1/people?extended=guest_stars


def getPeople(id, content_type, full=False): #Uses imdb_id
    try:
        url = '/%s/%s/people' % (content_type, id)
        if full:
            url += '?extended=full'
        return getTraktAsJson(url)
    except:
        return


def getStudio(id, content_type): #Uses imdb_id
    try:
        url = '/%s/%s/studios' % (content_type, id)
        return getTraktAsJson(url)
    except:
        return


def getGenre(content, type, type_id):
    try:
        r = getTraktAsJson('/search/%s/%s?type=%s&extended=full' % (type, type_id, content))
        return r[0].get(content, {}).get('genres', [])
    except:
        return []


def SearchMovie(title, year='', full=False):
    try:
        url = '/search/movie?query=%s' % quote_plus(title)
        if year:
            url += '&year=%s' % year
        if full:
            url += '&extended=full'
        return getTraktAsJson(url)
    except:
        return


def SearchTVShow(title, year='', full=False):
    try:
        url = '/search/show?query=%s' % quote_plus(title)
        if year:
            url += '&year=%s' % year
        if full:
            url += '&extended=full'
        return getTraktAsJson(url)
    except:
        return


def SearchEpisode(title, season, episode, full=False):
    try:
        url = '/search/%s/seasons/%s/episodes/%s' % (title, season, episode)
        if full:
            url += '&extended=full'
        return getTraktAsJson(url)
    except:
        return


def SearchAll(title, year='', full=False):
    try:
        return SearchMovie(title, year, full) + SearchTVShow(title, year, full)
    except:
        return


