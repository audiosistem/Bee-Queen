# -*- coding: utf-8 -*-
"""Optional bridge to script.module.resolveurl.

ResolveURL is Kodi's standard library for cracking file-host URLs
(Filemoon, Voe, Mixdrop, Doodstream, Streamtape, Streamwish, etc.) into
playable direct video URLs. We make it an OPTIONAL import so a missing
install never breaks the addon — file-host streams just stay non-playable
with a clear notification telling the user how to install it.

Design rules:
  * NEVER raise at import time even if resolveurl is missing or broken.
  * NEVER touch the existing source modules (vidsrc / stigstream / vidnest
    et al.) — they return direct .m3u8 / .mp4 URLs that don't need
    resolveurl at all. Only streams with ``needs_resolveurl=True`` (set
    exclusively by ``filehosts.py`` scrapers) flow through this bridge.
  * Fast preflight: ``can_resolve(url)`` returns False instantly for any
    host RU doesn't recognise, so the scrapers can drop unsupported
    hosters before they ever appear in the picker.
"""
from __future__ import annotations

from .common import log, notify

_resolveurl = None
_import_attempted = False


def _ensure_loaded():
    """Lazy-import resolveurl on first use. Cache the (module|None) result."""
    global _resolveurl, _import_attempted
    if _import_attempted:
        return _resolveurl
    _import_attempted = True
    try:
        import resolveurl as _ru
        _resolveurl = _ru
        log('resolveurl_bridge: script.module.resolveurl loaded successfully')
    except ImportError:
        _resolveurl = None
        log('resolveurl_bridge: script.module.resolveurl NOT installed - '
            'file-host streams will be skipped in the picker. Install via '
            'Kodi -> Add-ons -> Install from repository -> Kodi add-on '
            'repository -> Add-on libraries -> ResolveURL.')
    except Exception as e:
        _resolveurl = None
        log('resolveurl_bridge: resolveurl import error - %s' % e)
    return _resolveurl


def is_available():
    """True if script.module.resolveurl is importable on this device."""
    return _ensure_loaded() is not None


def can_resolve(url):
    """Fast check: does ResolveURL recognise this URL's host?

    Used at scrape time to drop unsupported hosts before they reach the
    picker — keeps the file-host source list clean."""
    ru = _ensure_loaded()
    if ru is None or not url:
        return False
    try:
        hmf = ru.HostedMediaFile(url=url)
        return bool(hmf.valid_url())
    except Exception as e:
        log('resolveurl_bridge: can_resolve(%s) error %s' % (url[:80], e))
        return False


def resolve(url):
    """Resolve a file-host URL → playable direct URL.

    Returns the resolved URL string on success, or None on failure /
    missing ResolveURL. Never raises — callers can treat None as
    "couldn't resolve, skip this stream and try the next one"."""
    ru = _ensure_loaded()
    if ru is None:
        notify('Install script.module.resolveurl',
               'File-host streams need ResolveURL. Install it from the '
               'Kodi add-on repository.')
        return None
    if not url:
        return None
    try:
        hmf = ru.HostedMediaFile(url=url)
        if not hmf.valid_url():
            log('resolveurl_bridge: %s is not supported by RU' % url[:120])
            return None
        resolved = hmf.resolve()
        if not resolved:
            log('resolveurl_bridge: RU returned empty for %s' % url[:120])
            return None
        if isinstance(resolved, bool):
            # RU returns False on captcha/abort
            return None
        return resolved
    except Exception as e:
        log('resolveurl_bridge: resolve(%s) raised %s' % (url[:80], e))
        return None


def host_label(url):
    """Pretty hoster name for the picker label. Falls back to URL host."""
    ru = _ensure_loaded()
    if ru is not None:
        try:
            hmf = ru.HostedMediaFile(url=url)
            label = hmf.get_host_and_id()
            if isinstance(label, tuple) and label and label[0]:
                return label[0]
        except Exception:
            pass
    # Fallback: extract host from URL.
    try:
        from urllib.parse import urlparse
        h = urlparse(url).netloc
        return h.split('.')[-2].capitalize() if '.' in h else h
    except Exception:
        return 'Unknown'
