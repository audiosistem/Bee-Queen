# -*- coding: utf-8 -*-
"""Shared helpers for Free Flow: feed parsing, HTTP, TMDB, state files."""
import os
import re
import json
import time
import urllib.parse as urlparse

try:
    import xbmcvfs
    import xbmcaddon
except Exception:  # allow standalone import for offline tests
    xbmcvfs = None
    xbmcaddon = None

try:
    import requests
except ImportError:
    requests = None
import urllib.request

try:
    from . import debug as _dbg  # type: ignore
except Exception:
    try:
        import debug as _dbg  # type: ignore
    except Exception:
        _dbg = None


ROOT_URL = 'https://thechains24.com/1/MAIN%20DIR.txt'
TMDB_API_KEY = '653bb8af90162bd98fc7ee32bcbbfb3d'
TMDB_IMG_BASE = 'https://image.tmdb.org/t/p/w600_and_h900_bestv2'
TMDB_FANART_BASE = 'https://image.tmdb.org/t/p/w1280'

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/124.0 Safari/537.36')

MAX_DEPTH = 6
NEW_WINDOW_SECONDS = 24 * 3600  # how long an item stays in "What's New"


# ---------------- state paths ---------------- #

def _profile_dir():
    if xbmcvfs is None or xbmcaddon is None:
        return os.path.join('/tmp', 'plugin.video.freeflow')
    p = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.freeflow/')
    if not xbmcvfs.exists(p):
        xbmcvfs.mkdirs(p)
    return p


def known_path():
    return os.path.join(_profile_dir(), 'known.json')


def new_path():
    return os.path.join(_profile_dir(), 'new.json')


def cache_path():
    return os.path.join(_profile_dir(), 'http_cache.json')


def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_json(path, data):
    try:
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except Exception:
        pass


# ---------------- HTTP ---------------- #

def http_get(url, timeout=20, headers=None):
    hdrs = {'User-Agent': UA}
    if headers:
        hdrs.update(headers)
    t0 = time.time()
    try:
        if requests is not None:
            r = requests.get(url, headers=hdrs, timeout=timeout)
            if _dbg is not None:
                _dbg.dump_http('GET', url, r.status_code,
                               headers=r.headers,
                               body_preview=(r.text or '')[:200],
                               elapsed_ms=(time.time() - t0) * 1000.0,
                               component='feed.http')
            return r.status_code, r.text, dict(r.headers)
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode('utf-8', errors='ignore')
            if _dbg is not None:
                _dbg.dump_http('GET', url, resp.status,
                               headers=dict(resp.headers),
                               body_preview=text[:200],
                               elapsed_ms=(time.time() - t0) * 1000.0,
                               component='feed.http')
            return resp.status, text, dict(resp.headers)
    except Exception as e:
        if _dbg is not None:
            _dbg.dlog('GET %s FAILED: %s' % (url, e),
                      level='WARN', component='feed.http')
        return 0, '', {}


def http_get_json(url, timeout=15):
    code, txt, _ = http_get(url, timeout=timeout)
    if code != 200 or not txt:
        return None
    try:
        return json.loads(txt)
    except Exception:
        return None


# ---------------- feed parser ---------------- #

BLOCK_RE = re.compile(r'<(dir|item)>(.*?)</\1>', re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r'<(title|link|sublink|thumbnail|fanart|summary)>(.*?)</\1>',
                    re.DOTALL | re.IGNORECASE)
SUBLINK_RE = re.compile(r'<sublink>(.*?)</sublink>', re.DOTALL | re.IGNORECASE)


def parse_feed(text):
    if not text:
        return []
    out = []
    for m in BLOCK_RE.finditer(text):
        kind = m.group(1).lower()
        body = m.group(2)
        entry = {'kind': kind, 'sublinks': []}
        for tm in TAG_RE.finditer(body):
            tag = tm.group(1).lower()
            val = (tm.group(2) or '').strip()
            if tag == 'sublink':
                if val:
                    entry['sublinks'].append(val)
            else:
                entry[tag] = val
        if not entry['sublinks']:
            for sm in SUBLINK_RE.finditer(body):
                v = (sm.group(1) or '').strip()
                if v:
                    entry['sublinks'].append(v)
        out.append(entry)
    return out


# ---------------- title cleaning + TMDB ---------------- #

def clean_title(raw):
    if not raw:
        return ''
    t = raw
    t = re.sub(r'\[/?[A-Z]+(?:[^\]]*)\]', '', t, flags=re.IGNORECASE)
    t = re.sub(
        r'\(\s*(HDTS|HDCAM|TS|CAM|TELESYNC|HDRIP|WEB[- ]?DL|WEBRIP|BDRIP|BLURAY|1080p|720p|480p|4K|UHD|HDR|SCREENER|DVDRIP)[^)]*\)',
        '', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(S\d{1,2}E\d{1,2}|Season\s*\d+|Episode\s*\d+)\b.*$',
               '', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(19|20)\d{2}\b', '', t)
    t = re.sub(r'\s{2,}', ' ', t).strip(' -|·.')
    return t


def tmdb_lookup(title):
    if not title:
        return (None, None, None)
    q = urlparse.quote_plus(title)
    url = ('https://api.themoviedb.org/3/search/multi?api_key=%s&query=%s'
           '&include_adult=false&language=en-US' % (TMDB_API_KEY, q))
    data = http_get_json(url)
    if not data or not data.get('results'):
        return (None, None, None)
    for res in data['results']:
        if res.get('media_type') in ('movie', 'tv'):
            poster = res.get('poster_path')
            backdrop = res.get('backdrop_path')
            overview = res.get('overview') or ''
            return (
                (TMDB_IMG_BASE + poster) if poster else None,
                (TMDB_FANART_BASE + backdrop) if backdrop else None,
                overview,
            )
    return (None, None, None)


# ---------------- recursive walker (for service + search) ---------------- #

def walk_tree(root_url=ROOT_URL, max_depth=MAX_DEPTH, http_cache=None,
              cache_ttl=25, on_progress=None, abort_check=None):
    """Walk all dirs from root and return a list of item dicts.

    http_cache: optional dict persisted on disk to avoid refetching unchanged
                pages within the same scan window.
    abort_check: callable returning True to stop early (Kodi service abort).
    """
    if http_cache is None:
        http_cache = {}
    items = []
    visited = set()
    stack = [(root_url, 'Main', 0)]
    while stack:
        if abort_check and abort_check():
            break
        url, parent_title, depth = stack.pop(0)
        if depth > max_depth or url in visited:
            continue
        visited.add(url)

        now = time.time()
        cached = http_cache.get(url)
        text = None
        if cached and (now - cached.get('ts', 0)) < cache_ttl:
            text = cached.get('text')
        if text is None:
            code, body, _ = http_get(url, timeout=15)
            if code == 200 and body:
                text = body
                http_cache[url] = {'ts': now, 'text': body}
            else:
                continue

        entries = parse_feed(text)
        for e in entries:
            if e['kind'] == 'item':
                subs = list(e.get('sublinks', []) or [])
                if not subs and e.get('link'):
                    subs = [e.get('link')]
                items.append({
                    'title': e.get('title', ''),
                    'parent_title': parent_title,
                    'parent_url': url,
                    'sublinks': subs,
                    'thumbnail': e.get('thumbnail', ''),
                    'fanart': e.get('fanart', ''),
                    'plot': e.get('summary', ''),
                })
            elif e['kind'] == 'dir':
                sub_url = e.get('link', '')
                sub_title = e.get('title', '') or parent_title
                if sub_url:
                    stack.append((sub_url, sub_title, depth + 1))
        if on_progress:
            try:
                on_progress(len(visited), len(items))
            except Exception:
                pass
    return items


def item_key(it):
    return (it.get('parent_url', '') + '::' + it.get('title', '')).strip()


# ---------------- link checker ---------------- #

DEAD_PATTERNS = [
    'video not found', 'file not found', 'video deleted', 'file deleted',
    'video has been removed', 'file has been removed', 'no longer available',
    'video does not exist', 'video unavailable', 'file unavailable',
    'media not found', '<title>404', 'page not found', 'this file was deleted',
    'this video was deleted', 'video was removed', 'sorry, this video',
    'we can\'t find', "we couldn't find",
]


def host_of(url):
    try:
        h = urlparse.urlparse(url).netloc.lower()
        if h.startswith('www.'):
            h = h[4:]
        return h or url
    except Exception:
        return url


def check_link(url, timeout=12):
    """Return (alive: bool, reason: str). Best-effort detection of dead
    file-host pages even when the host returns HTTP 200 with a "not found"
    body (streamtape, doodstream, etc.)."""
    if not url:
        return False, 'empty url'
    headers = {'User-Agent': UA, 'Accept': '*/*'}
    # 1) HEAD
    try:
        if requests is not None:
            r = requests.head(url, headers=headers, timeout=timeout,
                              allow_redirects=True)
            sc = r.status_code
        else:
            req = urllib.request.Request(url, headers=headers, method='HEAD')
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                sc = resp.status
        if sc in (404, 410):
            return False, 'HTTP %d' % sc
        if sc >= 500 and sc not in (501,):
            return False, 'HTTP %d' % sc
    except Exception as e:
        # some hosts disallow HEAD; fall through to GET
        msg = str(e)
        if 'timed out' in msg.lower() or 'timeout' in msg.lower():
            return False, 'timeout (HEAD)'
        # else continue

    # 2) Partial GET to inspect body for dead-page markers
    try:
        get_headers = dict(headers)
        get_headers['Range'] = 'bytes=0-16384'
        if requests is not None:
            r2 = requests.get(url, headers=get_headers, timeout=timeout,
                              allow_redirects=True, stream=True)
            sc = r2.status_code
            body = (r2.text or '')[:16384].lower()
            r2.close()
        else:
            req = urllib.request.Request(url, headers=get_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                sc = resp.status
                body = resp.read(16384).decode('utf-8', errors='ignore').lower()
        if sc in (404, 410):
            return False, 'HTTP %d' % sc
        if sc >= 500:
            return False, 'HTTP %d' % sc
        for p in DEAD_PATTERNS:
            if p in body:
                return False, 'dead page: "%s"' % p
        return True, 'ok'
    except Exception as e:
        msg = str(e)[:80]
        if 'timed out' in msg.lower() or 'timeout' in msg.lower():
            return False, 'timeout'
        return False, msg


def report_path():
    return os.path.join(_profile_dir(), 'link_report.txt')


def report_json_path():
    return os.path.join(_profile_dir(), 'link_report.json')


def write_text_report(results):
    """results: list of dicts {title, parent_title, parent_url, host, url, alive, reason}"""
    total = len(results)
    dead = [r for r in results if not r['alive']]
    lines = []
    lines.append('Free Flow - Link Health Report')
    lines.append('Generated: ' + time.strftime('%Y-%m-%d %H:%M:%S'))
    lines.append('Total checked: %d' % total)
    lines.append('Dead: %d  /  Alive: %d' % (len(dead), total - len(dead)))
    lines.append('=' * 60)
    if not dead:
        lines.append('No dead links found.')
    else:
        # group by parent_title for readability
        by_section = {}
        for r in dead:
            by_section.setdefault(r['parent_title'] or 'Unknown', []).append(r)
        for sec in sorted(by_section.keys()):
            lines.append('')
            lines.append('### Section: %s' % sec)
            for r in by_section[sec]:
                lines.append('  [DEAD] ' + r['title'])
                lines.append('    Host   : ' + r['host'])
                lines.append('    Reason : ' + r['reason'])
                lines.append('    Link   : ' + r['url'])
                lines.append('    Feed   : ' + r['parent_url'])
    text = '\n'.join(lines)
    try:
        with open(report_path(), 'w', encoding='utf-8') as f:
            f.write(text)
    except Exception:
        pass
    try:
        with open(report_json_path(), 'w', encoding='utf-8') as f:
            json.dump(results, f)
    except Exception:
        pass
    return text
