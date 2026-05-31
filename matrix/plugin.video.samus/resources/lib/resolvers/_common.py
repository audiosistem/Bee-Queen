import requests as _req

THRAX_KEY = "7d9f4987bcd1a2026e6a422931bd7dbff0060977d189f37fa5727d9288b4abbb"
THRAX_HEADERS = {"X-Thrax-Key": THRAX_KEY}
THRAX_BASE = "https://api.derzis.xyz"


def get_thrax_sources(endpoint, params, label):
    """Call a Thrax /sources endpoint and return Samus-format source list."""
    try:
        r = _req.get(f"{THRAX_BASE}/{endpoint}", params=params, headers=THRAX_HEADERS, timeout=25)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    results = []
    for s in data.get('sources', []):
        url = s.get('url')
        if not url:
            continue
        referer = s.get('referer', '')
        is_direct = s.get('direct', True)
        if is_direct and referer and '|' not in url:
            url = f"{url}|Referer={referer}"
        results.append({
            'url':        url,
            'provider':   label,
            'quality':    s.get('quality', ''),
            'title_line': s.get('title', ''),
            'direct':     is_direct,
            'subtitles':  s.get('subtitles', []),
        })
    return results
