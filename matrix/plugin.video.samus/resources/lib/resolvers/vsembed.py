# -*- coding: utf-8 -*-
import re
import requests
import urllib.parse
import xbmc

_LABEL = '[VSE]'
_BASES = ['https://vsembed.ru', 'https://vsembed.su']
_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
       'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
_CDN_DOMAINS = [
    'neonhorizonworkshops.com',
    'wanderlynest.com',
    'orchidpixelgardens.com',
    'cloudnestra.com',
]
_MIN_PAGE_SIZE = 3000


def _infer_quality(url):
    u = url.lower()
    if re.search(r'(2160|4k|uhd)', u):  return '4K'
    if '1080' in u:                      return '1080p'
    if '720'  in u:                      return '720p'
    if '480'  in u:                      return '480p'
    if '360'  in u:                      return '360p'
    return 'auto'


def _session():
    s = requests.Session()
    s.headers.update({'User-Agent': _UA, 'Accept-Language': 'en-US,en;q=0.9'})
    return s


def _resolve_cdn_templates(tmpl):
    seen = set()
    results = []
    for domain in _CDN_DOMAINS:
        url = re.sub(r'\{v\d+\}', domain, tmpl)
        if url not in seen:
            seen.add(url)
            results.append(url)
    return results


def _process_server(sess, basedom, data_hash, embed_url):
    try:
        rcp_url = f'{basedom}/rcp/{data_hash}'
        r2 = sess.get(rcp_url, headers={'Referer': embed_url, 'Accept': 'text/html'},
                      timeout=15, verify=False)
        if not r2.ok or len(r2.text) < 100:
            xbmc.log(f'{_LABEL} rcp bad response: {r2.status_code}', xbmc.LOGWARNING)
            return []
        if 'turnstile' in r2.text.lower():
            xbmc.log(f'{_LABEL} Turnstile pe rcp {data_hash[:12]} — skip', xbmc.LOGWARNING)
            return []

        src_m = re.search(r"src:\s*'(/(?:prorcp|srcrcp)/[^']+)'", r2.text)
        if not src_m:
            xbmc.log(f'{_LABEL} no src in rcp (len={len(r2.text)})', xbmc.LOGWARNING)
            return []
        src = src_m.group(1)

        rcp2_url = basedom + src
        r3 = sess.get(rcp2_url, headers={'Referer': f'{basedom}/', 'Accept': '*/*'},
                      timeout=15, verify=False)
        if not r3.ok:
            xbmc.log(f'{_LABEL} rcp2 bad response: {r3.status_code}', xbmc.LOGWARNING)
            return []

        raw_file_m = re.search(r'file:\s*["\']([^"\']+)["\']', r3.text)
        if not raw_file_m:
            direct = re.findall(r'["\']?(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)["\']?', r3.text)
            return direct[:3]

        raw_urls = [u.strip() for u in raw_file_m.group(1).split(' or ')]
        direct_urls = [u for u in raw_urls if '{v' not in u and '.m3u8' in u]
        template_urls = list(dict.fromkeys(u for u in raw_urls if '{v' in u and '.m3u8' in u))

        sources = []
        seen = set()
        for url in direct_urls:
            if url not in seen:
                seen.add(url)
                sources.append(url)
        for tmpl in template_urls:
            for resolved in _resolve_cdn_templates(tmpl):
                if resolved not in seen:
                    seen.add(resolved)
                    sources.append(resolved)
        return sources

    except Exception as e:
        xbmc.log(f'{_LABEL} server error hash={data_hash[:12]}: {e}', xbmc.LOGWARNING)
        return []


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if media_type == 'tv' and (season is None or episode is None):
        return []
    try:
        sess = _session()
        r1 = None
        embed_url = None
        for base in _BASES:
            url = (f'{base}/embed/tv/{tmdb_id}/{season}/{episode}'
                   if media_type == 'tv' else f'{base}/embed/movie/{tmdb_id}')
            try:
                r = sess.get(url, headers={'Accept': 'text/html'}, timeout=15, verify=False)
                if r.ok and len(r.text) >= _MIN_PAGE_SIZE:
                    r1 = r
                    embed_url = url
                    break
            except Exception:
                pass

        if r1 is None:
            xbmc.log(f'{_LABEL} embed page fail pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []

        iframe_m = re.search(r"<iframe[^>]+src=[\"']((?:https?:)?//[^\"'> ]+)[\"']", r1.text, re.I)
        if iframe_m:
            iframe_url = iframe_m.group(1)
            if iframe_url.startswith('//'):
                iframe_url = 'https:' + iframe_url
            p = urllib.parse.urlparse(iframe_url)
            basedom = f'{p.scheme}://{p.netloc}'
        else:
            basedom = 'https://cloudnestra.com'

        hashes = re.findall(r"data-hash=[\"']([^\"']+)[\"']", r1.text)
        if not hashes:
            xbmc.log(f'{_LABEL} no data-hash pentru tmdb={tmdb_id}', xbmc.LOGWARNING)
            return []

        all_m3u8s = []
        for h in hashes:
            urls = _process_server(sess, basedom, h, embed_url)
            all_m3u8s.extend(u for u in urls if u not in all_m3u8s)

    except Exception as e:
        xbmc.log(f'{_LABEL} eroare: {e}', xbmc.LOGERROR)
        return []

    sources = []
    for url in all_m3u8s:
        sources.append({
            'url':        f'{url}|User-Agent={_UA}&Referer=https://cloudnestra.com/',
            'provider':   _LABEL,
            'quality':    '1080p',
            'title_line': 'VSEmbed',
            'direct':     True,
        })
    xbmc.log(f'{_LABEL} {len(sources)} surse pentru tmdb={tmdb_id}', xbmc.LOGINFO)
    return sources
