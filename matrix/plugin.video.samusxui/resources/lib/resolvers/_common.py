import requests as _req

THRAX_KEY = "6d11ea4b6c6acc9bd2fc4f91b6be3fc06ca5e4358e344d248e8bbcb64cedd0df"
THRAX_HEADERS = {"X-Thrax-Key": THRAX_KEY}
THRAX_BASE = "https://api.derzis.xyz"


_TOKEN_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")


def _stamp_token(url, token_url, referer, cache):
    """Unele CDN-uri (vsembed) leagă tokenul de IP-ul care îl cere, deci trebuie
    luat aici, de pe IP-ul lui Kodi — un token luat de API pe server dă 403."""
    if not token_url:
        return url
    if token_url not in cache:
        cache[token_url] = ''
        try:
            h = {'User-Agent': _TOKEN_UA}
            if referer:
                h['Referer'] = referer
            t = _req.get(token_url, headers=h, timeout=10)
            if t.ok:
                cache[token_url] = t.text.strip()
        except Exception:
            pass
    token = cache[token_url]
    if not token:
        return url
    if '__TOKEN__' in url:
        return url.replace('__TOKEN__', token)
    return url + ('&' if '?' in url else '?') + 'token=' + token


def get_thrax_sources(endpoint, params, label):
    """Call a Thrax /sources endpoint and return Samus-format source list."""
    try:
        r = _req.get(f"{THRAX_BASE}/{endpoint}", params=params, headers=THRAX_HEADERS, timeout=25)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    results = []
    token_cache = {}
    for s in data.get('sources', []):
        url = s.get('url')
        if not url:
            continue
        referer = s.get('referer', '')
        url = _stamp_token(url, s.get('token_url'), referer, token_cache)
        is_direct = s.get('direct', True)
        if is_direct and referer and '|' not in url:
            url = f"{url}|Referer={referer}"
        server = s.get('title', '')
        results.append({
            'url':          url,
            'provider':     label,
            'quality':      s.get('quality', ''),
            'title_line':   server,
            'display_name': server,
            'direct':       is_direct,
            'subtitles':    s.get('subtitles', []),
        })
    return results
