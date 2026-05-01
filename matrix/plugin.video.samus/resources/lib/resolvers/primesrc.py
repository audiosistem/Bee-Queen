# -*- coding: utf-8 -*-
import re
import requests
import xbmc

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)
_CDN_DOMAINS = [
    'neonhorizonworkshops.com',
    'wanderlynest.com',
    'orchidpixelgardens.com',
    'cloudnestra.com',
]
# Dimensiunea minimă a unui răspuns cloudnestra valid (rate-limit → ~2100b)
_MIN_RCP_SIZE = 3000


def get_primesrc_sources(tmdb_id):
    return _extract('movie', tmdb_id)


def get_primesrc_tv_sources(tmdb_id, season, episode):
    return _extract('tv', tmdb_id, season, episode)


def _session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': _UA,
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
    })
    return s


def _extract(media_type, tmdb_id, season=None, episode=None):
    sess = _session()
    try:
        # Step 1: vidsrcme.ru embed page
        vidsrc_url = f'https://vidsrcme.ru/embed/{media_type}/{tmdb_id}'
        if media_type == 'tv':
            vidsrc_url += f'?s={season}&e={episode}'

        r1 = sess.get(
            vidsrc_url,
            headers={'Accept': 'text/html', 'Referer': 'https://primesrc.me/'},
            timeout=15,
            verify=False,
        )
        if not r1.ok:
            xbmc.log(f'[PrimeSrc] vidsrcme.ru {r1.status_code}', xbmc.LOGERROR)
            return []

        # Step 2: cloudnestra iframe
        iframe_m = re.search(r'<iframe[^>]*\ssrc=["\']([^"\']+)["\']', r1.text, re.I)
        if not iframe_m:
            xbmc.log('[PrimeSrc] Nu s-a găsit iframe', xbmc.LOGWARNING)
            return []

        iframe_url = iframe_m.group(1)
        if iframe_url.startswith('//'):
            iframe_url = 'https:' + iframe_url
        if 'cloudnestra' not in iframe_url:
            xbmc.log(f'[PrimeSrc] iframe necunoscut: {iframe_url}', xbmc.LOGWARNING)
            return []

        r2 = sess.get(
            iframe_url,
            headers={'Accept': 'text/html', 'Referer': 'https://vidsrcme.ru/'},
            timeout=15,
            verify=False,
        )
        if len(r2.text) < _MIN_RCP_SIZE:
            xbmc.log(
                f'[PrimeSrc] cloudnestra rate-limit (size={len(r2.text)}b)',
                xbmc.LOGWARNING,
            )
            return []

        # Step 3: prorcp token
        prorcp_m = re.search(r'["\'/]prorcp/([^"\'>\s]+)', r2.text)
        if not prorcp_m:
            xbmc.log('[PrimeSrc] Nu s-a găsit prorcp', xbmc.LOGWARNING)
            return []

        r3 = sess.get(
            f'https://cloudnestra.com/prorcp/{prorcp_m.group(1)}',
            headers={'Accept': 'text/html', 'Referer': r2.url},
            timeout=15,
            verify=False,
        )

        # Step 4: găsim m3u8-urile
        m3u8s = list(dict.fromkeys(
            re.findall(r'https?://[^\s"\'<>)]+\.m3u8[^\s"\'<>)]*', r3.text)
        ))
        direct_urls  = [u for u in m3u8s if '{v' not in u]
        template_urls = [u for u in m3u8s if '{v' in u]

        # Step 5: verificăm URL-urile directe
        for url in direct_urls:
            try:
                rv = sess.get(
                    url,
                    headers={'Referer': 'https://cloudnestra.com/'},
                    timeout=8,
                    verify=False,
                )
                if rv.ok and '#EXTM3U' in rv.text:
                    xbmc.log(f'[PrimeSrc] Direct HLS: {url}', xbmc.LOGINFO)
                    return [{'label': 'PrimeSrc', 'url': url, 'quality': '1080p'}]
            except Exception:
                pass

        # Step 6: rezolvăm template-urile CDN
        for tmpl in template_urls:
            for domain in _CDN_DOMAINS:
                resolved = re.sub(r'\{v\d+\}', domain, tmpl)
                try:
                    rv = sess.get(
                        resolved,
                        headers={'Referer': 'https://cloudnestra.com/'},
                        timeout=8,
                        verify=False,
                    )
                    if rv.ok and '#EXTM3U' in rv.text:
                        xbmc.log(f'[PrimeSrc] CDN HLS: {resolved}', xbmc.LOGINFO)
                        return [{'label': 'PrimeSrc', 'url': resolved, 'quality': '1080p'}]
                except Exception:
                    pass

        xbmc.log(
            f'[PrimeSrc] Niciun stream găsit (m3u8={len(m3u8s)})',
            xbmc.LOGWARNING,
        )
        return []

    except Exception as exc:
        xbmc.log(f'[PrimeSrc] Eroare: {exc}', xbmc.LOGERROR)
        return []
