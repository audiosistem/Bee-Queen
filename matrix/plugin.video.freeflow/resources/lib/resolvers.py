# -*- coding: utf-8 -*-
"""
Free Flow - built-in link resolvers.

Handles hosts that script.module.resolveurl does not cover (or covers
unreliably). Currently implemented:

  - ddownload.com (free slot, 2-step form, countdown)

Each resolver returns a direct playable/downloadable URL string on success,
or None on failure. Public entry points:

  can_resolve(url) -> bool
  resolve(url)     -> direct_url or None
"""
import re
import time

try:
    import requests
except Exception:
    requests = None


UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')


# ---------------- helpers ---------------- #

def _new_session(referer=None):
    if requests is None:
        return None
    s = requests.Session()
    s.headers.update({
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    if referer:
        s.headers.update({'Referer': referer})
    return s


def _extract_form(html):
    """Return the first <form method=post ...> as dict of name->value."""
    if not html:
        return None
    m = re.search(r'<form[^>]*method=["\']?post["\']?[^>]*>(.*?)</form>',
                  html, re.I | re.S)
    if not m:
        return None
    body = m.group(1)
    fields = {}
    for im in re.finditer(r'<input\b[^>]*>', body, re.I):
        tag = im.group(0)
        nm = re.search(r'name=["\']([^"\']+)["\']', tag, re.I)
        vl = re.search(r'value=["\']([^"\']*)["\']', tag, re.I)
        if nm:
            fields[nm.group(1)] = vl.group(1) if vl else ''
    return fields if fields else None


def _find_countdown(html):
    if not html:
        return 0
    # Visible countdown span, e.g. <span id="countdown_str">Wait <span class="seconds">30</span> seconds</span>
    m = re.search(r'countdown[^<>]*?>\s*.*?(\d{1,3})\s*</span>', html,
                  re.I | re.S)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    m = re.search(r'var\s+(?:secs|countdown)\s*=\s*(\d{1,3})\s*;', html, re.I)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    return 0


_SAMEHOST_PAGE_RX = re.compile(
    r'^https?://(?:www\.)?ddownload\.com/[A-Za-z0-9]{8,}/',
    re.I)


def _find_direct_media(html):
    """Look for a direct media URL in page source.

    Rejects the page URL itself (e.g. ddownload.com/<hash>/file.mkv) and
    HTML-entity-encoded URLs.
    """
    if not html:
        return None

    def _accept(u):
        if not u:
            return False
        if '&#' in u or '&amp;' in u:
            return False
        if _SAMEHOST_PAGE_RX.search(u):
            return False
        return True

    for m in re.finditer(
            r'https?://[^\s"\'<>]+?\.(?:mkv|mp4|avi|webm|m4v|mov|ts|flv)'
            r'(?:\?[^\s"\'<>]*)?',
            html, re.I):
        u = m.group(0)
        if _accept(u):
            return u
    # "Click here to start your download" style anchor
    m = re.search(
        r'<a[^>]+href=["\'](https?://[^"\']+)["\'][^>]*>\s*'
        r'(?:Click here to (?:start|download)[^<]*|Direct Download[^<]*|'
        r'Download file)\s*</a>',
        html, re.I)
    if m:
        return m.group(1)
    # Anchor with id btn_download / downloadbtn
    m = re.search(
        r'<a[^>]+id=["\'](?:btn_download|downloadbtn|direct_link)["\'][^>]+'
        r'href=["\']([^"\']+)["\']',
        html, re.I)
    if m:
        return m.group(1)
    m = re.search(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]+id=["\']'
        r'(?:btn_download|downloadbtn|direct_link)["\']',
        html, re.I)
    if m:
        return m.group(1)
    return None


# ---------------- ddownload.com ---------------- #

_DDL_RX = re.compile(r'//(?:www\.)?ddownload\.com/', re.I)


def _is_ddownload(url):
    return bool(url) and bool(_DDL_RX.search(url))


def _ddownload_filecode(url):
    """Return the file_code from a ddownload URL (e.g. ti4wzjmvpxn1)."""
    m = re.search(r'ddownload\.com/(?:embed-|d/)?([A-Za-z0-9]{8,})', url or '',
                  re.I)
    return m.group(1) if m else None


def _ddownload_api_key():
    try:
        import xbmcaddon
        return (xbmcaddon.Addon('plugin.video.freeflow')
                .getSetting('ddl_api_key') or '').strip()
    except Exception:
        return ''


def _resolve_ddownload_api(file_code, api_key, log=None):
    """Use ddownload premium API to get a direct link (no captcha)."""
    if not file_code or not api_key or requests is None:
        return None
    api = ('https://api.ddownload.com/api/file/direct_link'
           '?key=%s&file_code=%s' % (api_key, file_code))
    try:
        r = requests.get(api, headers={'User-Agent': UA}, timeout=20)
        data = r.json() if r.status_code == 200 else {}
    except Exception as e:
        if log:
            log('ddownload API error: %s' % e)
        return None
    if not isinstance(data, dict):
        return None
    if data.get('status') != 200:
        if log:
            log('ddownload API status=%s msg=%s' %
                (data.get('status'), data.get('msg')))
        return None
    result = data.get('result') or {}
    if isinstance(result, list) and result:
        result = result[0]
    return result.get('url') if isinstance(result, dict) else None


def resolve_ddownload(url, log=None):
    """Resolve a ddownload.com page URL to a direct media URL.

    Strategy:
      1) If user has set a premium API key in add-on settings, use the
         official API (instant, no captcha, always works).
      2) Otherwise, walk the free-download form. ddownload free slots are
         now protected by Cloudflare Turnstile - we detect that and fail
         with a clear log so the UI can tell the user to add a premium
         API key (or use a different host).
    """
    if requests is None:
        if log:
            log('resolvers: requests module missing')
        return None

    # 1) Premium API path
    api_key = _ddownload_api_key()
    file_code = _ddownload_filecode(url)
    if api_key and file_code:
        direct = _resolve_ddownload_api(file_code, api_key, log=log)
        if direct:
            return direct
        if log:
            log('ddownload API did not return a direct URL; '
                'falling back to free scrape')

    s = _new_session(referer=url)
    if s is None:
        return None

    try:
        r = s.get(url, timeout=25, allow_redirects=True)
    except Exception as e:
        if log:
            log('ddownload GET failed: %s' % e)
        return None

    html = r.text or ''
    direct = _find_direct_media(html)
    if direct:
        return direct

    form = _extract_form(html)
    if not form or 'op' not in form:
        if log:
            log('ddownload: no first form found')
        return None

    form.setdefault('method_free', 'Free Download >>')
    form.pop('method_premium', None)
    time.sleep(1)
    try:
        r2 = s.post(url, data=form, timeout=30, allow_redirects=True)
    except Exception as e:
        if log:
            log('ddownload stage1 POST failed: %s' % e)
        return None
    html2 = r2.text or ''

    # Cloudflare Turnstile / captcha check - free tier is blocked here
    if re.search(
            r'(cf-turnstile|challenges\.cloudflare\.com/turnstile'
            r'|Wrong\s*captcha|data-sitekey)', html2, re.I):
        if log:
            log('ddownload: Cloudflare Turnstile captcha - free slot '
                'cannot be solved headlessly. Set premium API key in '
                'Free Flow settings to bypass.')
        return None

    direct = _find_direct_media(html2)
    if direct:
        return direct

    form2 = _extract_form(html2)
    if not form2 or 'op' not in form2:
        if log:
            log('ddownload: no second form; maybe captcha/premium only')
        return None

    wait = _find_countdown(html2)
    time.sleep(min(wait + 1, 65) if wait > 0 else 3)

    form2.setdefault('method_free', 'Free Download >>')
    form2.pop('method_premium', None)
    try:
        r3 = s.post(url, data=form2, timeout=30, allow_redirects=True)
    except Exception as e:
        if log:
            log('ddownload stage2 POST failed: %s' % e)
        return None
    html3 = r3.text or ''

    if re.search(
            r'(cf-turnstile|challenges\.cloudflare\.com/turnstile'
            r'|Wrong\s*captcha)', html3, re.I):
        if log:
            log('ddownload: captcha on stage2 - free slot blocked')
        return None

    direct = _find_direct_media(html3)
    if direct:
        return direct

    final = r3.url or ''
    if re.search(r'\.(mkv|mp4|avi|webm|m4v|mov|ts|flv)', final, re.I) \
            and not _SAMEHOST_PAGE_RX.search(final):
        return final

    if log:
        log('ddownload: exhausted without direct link')
    return None


# ---------------- public API ---------------- #

def can_resolve(url):
    return _is_ddownload(url)


def resolve(url, log=None):
    if not url:
        return None
    try:
        if _is_ddownload(url):
            return resolve_ddownload(url, log=log)
    except Exception as e:
        if log:
            log('resolvers.resolve exception: %s' % e)
        return None
    return None
