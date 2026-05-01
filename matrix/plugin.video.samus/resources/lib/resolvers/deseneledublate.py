# -*- coding: utf-8 -*-
import re
import base64
import requests
import urllib.parse
import xbmc

_LABEL      = '[DRO]'
_BASE       = 'https://deseneledublate.com'
_EMBED_BASE = 'https://desene.deseneledublate.com'
_UA         = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
               'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_TMDB_KEY   = '69ef972e0d191aff7ab5b8e396619cb2'


def _session():
    s = requests.Session()
    s.headers.update({'User-Agent': _UA, 'Accept-Language': 'ro-RO,ro;q=0.9'})
    return s


def _tmdb_titles(tmdb_id, media_type, sess):
    endpoint = 'movie' if media_type == 'movie' else 'tv'
    try:
        r = sess.get(
            f'https://api.themoviedb.org/3/{endpoint}/{tmdb_id}',
            params={'api_key': _TMDB_KEY, 'language': 'ro-RO'},
            timeout=10,
        )
        d = r.json()
        ro_title = d.get('title') or d.get('name') or ''
        orig_title = d.get('original_title') or d.get('original_name') or ''
        year = (d.get('release_date') or d.get('first_air_date') or '')[:4]
        return ro_title, orig_title, year
    except Exception:
        return '', '', ''


def _search(title, media_type, sess):
    """Return list of (page_url) candidates from site search."""
    r = sess.get(f'{_BASE}/?s={urllib.parse.quote(title)}', timeout=15)
    if not r.ok:
        return []
    prefix = '/desen/' if media_type == 'movie' else '/serial/'
    links = re.findall(
        rf'href="({re.escape(_BASE)}{re.escape(prefix)}[^"]+)"',
        r.text,
    )
    return list(dict.fromkeys(links))


def _page_info(url, sess):
    """Fetch page and return (post_id, nonce) or (None, None)."""
    try:
        r = sess.get(url, timeout=15)
        if not r.ok:
            return None, None
        html = r.text
        # post id — DooPlay uses data-post='{id}' on player option li
        m = re.search(r"data-post='(\d+)'", html)
        if not m:
            m = re.search(r'data-post="(\d+)"', html)
        if not m:
            return None, None
        post_id = m.group(1)
        # nonce tied to wp-admin/admin-ajax.php
        nm = re.search(r'"nonce":"([a-f0-9]+)"[^}]*"url":"[^"]*wp-adm', html)
        if not nm:
            nm = re.search(r'"nonce":"([a-f0-9]+)"', html)
        nonce = nm.group(1) if nm else ''
        return post_id, nonce
    except Exception:
        return None, None


def _server_numes(url, sess):
    """Return list of data-nume values available on a page."""
    try:
        r = sess.get(url, timeout=15)
        if not r.ok:
            return ['1']
        numes = re.findall(r"data-nume='([^']+)'", r.text)
        numes = [n for n in dict.fromkeys(numes) if n != 'trailer']
        return numes or ['1']
    except Exception:
        return ['1']


def _ajax_embed(post_id, nonce, media_type, server_num, referer, sess):
    """POST admin-ajax → embed_url."""
    dtype = 'movie' if media_type == 'movie' else 'tv'
    try:
        r = sess.post(
            f'{_BASE}/wp-admin/admin-ajax.php',
            data={
                'action': 'doo_player_ajax',
                'post':   post_id,
                'nume':   server_num,
                'type':   dtype,
                'nonce':  nonce,
            },
            headers={
                'Referer':          referer,
                'X-Requested-With': 'XMLHttpRequest',
            },
            timeout=15,
        )
        d = r.json()
        url  = d.get('embed_url') or ''
        etype = d.get('type') or ''
        return url, etype
    except Exception:
        return '', ''


def _embed_url_from_iframe_page(embed_url, sess):
    """Follow /f/ page to get the /e/{id} Netu embed URL for resolveurl."""
    try:
        r = sess.get(embed_url, headers={'Referer': _BASE + '/'}, timeout=15)
        if not r.ok:
            return None
        html = r.text

        # iframe /e/{id} — return the full embed URL for resolveurl
        m = re.search(r'<iframe[^>]+src="(/e/[^"?]+)', html, re.I)
        if m:
            return f'{_EMBED_BASE}{m.group(1)}'

        # Full URL in iframe src
        m = re.search(r'<iframe[^>]+src="(https?://[^"]+)"', html, re.I)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _urls_from_dtshcode(embed_url):
    """Decode dtshcode embed_url — DooPlay obfuscated player content.
    Returns list of embed URLs extracted from the code."""
    urls = []
    try:
        # embed_url for dtshcode is sometimes a data: blob or obfuscated JS
        # Try base64 decode to find src= URLs
        # First check if it looks like a URL
        if embed_url.startswith('http'):
            urls.append(embed_url)
            return urls

        # Try to decode base64 content
        # DooPlay sometimes encodes the iframe html as base64
        try:
            decoded = base64.b64decode(embed_url).decode('utf-8', errors='ignore')
            found = re.findall(r'src=["\']?(https?://[^"\'> ]+)["\']?', decoded)
            urls.extend(found)
        except Exception:
            pass

        # Look for atob() calls — eval(atob('...'))
        m = re.search(r"atob\(['\"]([A-Za-z0-9+/=]+)['\"]", embed_url)
        if m:
            try:
                decoded = base64.b64decode(m.group(1)).decode('utf-8', errors='ignore')
                found = re.findall(r'src=["\']?(https?://[^"\'> ]+)["\']?', decoded)
                urls.extend(found)
            except Exception:
                pass
    except Exception:
        pass
    return list(dict.fromkeys(urls))


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        sess = _session()

        ro_title, orig_title, year = _tmdb_titles(tmdb_id, media_type, sess)
        if not ro_title and not orig_title:
            xbmc.log(f'{_LABEL} titlu negăsit tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []

        page_url = None
        for title in filter(None, [ro_title, orig_title]):
            links = _search(title, media_type, sess)
            if links:
                page_url = links[0]
                break

        if not page_url:
            xbmc.log(f'{_LABEL} pagina negăsită: "{ro_title}" tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []

        post_id, nonce = _page_info(page_url, sess)
        if not post_id:
            xbmc.log(f'{_LABEL} post_id negăsit pe {page_url}', xbmc.LOGWARNING)
            return []

        numes = _server_numes(page_url, sess)

        embed_urls = []
        seen = set()

        for num in numes:
            embed_url, etype = _ajax_embed(post_id, nonce, media_type, num, page_url, sess)
            if not embed_url:
                continue
            xbmc.log(f'{_LABEL} server {num} type={etype} url={embed_url[:80]}', xbmc.LOGDEBUG)

            if etype in ('iframe', 'embed'):
                # Follow /f/ → /e/ chain to get the Netu embed URL
                netu_url = _embed_url_from_iframe_page(embed_url, sess)
                if netu_url and netu_url not in seen:
                    seen.add(netu_url)
                    embed_urls.append(netu_url)
                    xbmc.log(f'{_LABEL} netu embed: {netu_url}', xbmc.LOGDEBUG)
            elif etype == 'dtshcode':
                # Decode obfuscated player code to extract embed URL
                for url in _urls_from_dtshcode(embed_url):
                    if url not in seen:
                        seen.add(url)
                        embed_urls.append(url)
                        xbmc.log(f'{_LABEL} dtshcode embed: {url}', xbmc.LOGDEBUG)
            else:
                # Unknown type — if it looks like a URL, pass it through
                if embed_url.startswith('http') and embed_url not in seen:
                    seen.add(embed_url)
                    embed_urls.append(embed_url)

    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGERROR)
        return []

    sources = []
    for url in embed_urls:
        sources.append({
            'url':        url,
            'provider':   _LABEL,
            'quality':    '720p',
            'title_line': 'DeseneRO',
            'direct':     False,
        })

    xbmc.log(f'{_LABEL} {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return sources
