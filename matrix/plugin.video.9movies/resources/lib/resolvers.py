# -*- coding: utf-8 -*-
# Stream resolver helpers for 9Movies
# Author: Zeus768

import re
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

import xbmc


def fetch(url):
    try:
        import requests
        r = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': url,
        }, timeout=15, verify=False)
        return r.text
    except ImportError:
        import urllib.request
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': url,
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        xbmc.log('[9Movies Resolver] Error: %s' % str(e), xbmc.LOGERROR)
        return ''


def resolve_streamtape(url):
    html = fetch(url)
    # Streamtape obfuscates the link across two JS variables
    m1 = re.search(r"id=([a-zA-Z0-9_\-]+)&expires", html)
    m2 = re.search(r"token=([a-zA-Z0-9_\-]+)&", html)
    # Try full link pattern
    m = re.search(r'(https?://streamtape\.com/get_video\?[^"\'<>\s]+)', html)
    if m:
        return 'https:' + m.group(1) if m.group(1).startswith('//') else m.group(1)
    # Partial link concat approach
    m = re.search(r"\.substr\(2\)\s*\+\s*[\"']([^\"']+)[\"']", html)
    if m:
        return 'https://streamtape.com/get_video' + m.group(1)
    return url


def resolve_doodstream(url):
    html = fetch(url)
    m = re.search(r"'/pass_md5/([^']+)'", html)
    if not m:
        return url
    pass_path = m.group(1)
    pass_url = 'https://doodstream.com/pass_md5/' + pass_path
    pass_html = fetch(pass_url)
    # The response is the base URL; append a fake token suffix
    token_m = re.search(r"\?token=([a-zA-Z0-9]+)", html)
    token = token_m.group(1) if token_m else 'xxxxxxxxxx'
    return pass_html.strip() + '?token=' + token + '&expiry=9999999999'


def resolve_filemoon(url):
    html = fetch(url)
    m = re.search(r'sources:\s*\[\{[^}]*file:\s*["\']([^"\']+)["\']', html)
    if m:
        return m.group(1)
    return url


def resolve_streamwish(url):
    html = fetch(url)
    for pattern in [
        r'file:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'"file":\s*"([^"]+\.m3u8[^"]*)"',
    ]:
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    return url


def resolve_voe(url):
    html = fetch(url)
    m = re.search(r"'hls':\s*'([^']+)'", html)
    if m:
        return m.group(1)
    m = re.search(r'"hls":\s*"([^"]+)"', html)
    if m:
        return m.group(1)
    return url


def resolve_mixdrop(url):
    html = fetch(url)
    m = re.search(r'(?:wurl|MDCore\.wurl)\s*=\s*"([^"]+)"', html)
    if m:
        link = m.group(1)
        return 'https:' + link if link.startswith('//') else link
    return url


def resolve_uqload(url):
    html = fetch(url)
    m = re.search(r'sources:\s*\["([^"]+)"\]', html)
    if m:
        return m.group(1)
    return url


def resolve_upstream(url):
    html = fetch(url)
    m = re.search(r'file:\s*["\']([^"\']+\.mp4[^"\']*)["\']', html)
    if m:
        return m.group(1)
    return url


RESOLVERS = {
    'streamtape.com': resolve_streamtape,
    'streamtape.net': resolve_streamtape,
    'doodstream.com': resolve_doodstream,
    'dood.watch': resolve_doodstream,
    'ds2play.com': resolve_doodstream,
    'filemoon.sx': resolve_filemoon,
    'filemoon.to': resolve_filemoon,
    'streamwish.com': resolve_streamwish,
    'streamwish.to': resolve_streamwish,
    'voe.sx': resolve_voe,
    'mixdrop.co': resolve_mixdrop,
    'mixdrop.ch': resolve_mixdrop,
    'uqload.to': resolve_uqload,
    'uqload.com': resolve_uqload,
    'upstream.to': resolve_upstream,
}


def resolve(url):
    """Attempt to resolve a hosted embed URL to a direct playable stream."""
    try:
        host = urlparse(url).netloc.replace('www.', '')
        for domain, resolver in RESOLVERS.items():
            if domain in host:
                xbmc.log('[9Movies Resolver] Using %s resolver for %s' % (domain, url), xbmc.LOGDEBUG)
                return resolver(url)
    except Exception as e:
        xbmc.log('[9Movies Resolver] resolve() error: %s' % str(e), xbmc.LOGERROR)
    return url
