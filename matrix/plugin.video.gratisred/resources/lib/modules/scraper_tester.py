# -*- coding: utf-8 -*-
"""
Scraper Tester
--------------
Lightweight reachability tester for the 'working' scrapers shipped with the
addon. For each scraper, we import the module, instantiate its `source` class
and HTTP-GET its `base_link` (falling back to any entry in `self.domains` if
the primary base is unreachable). Results are presented in a Kodi dialog.

Triggered from:
  - Settings > Provider Settings > "Test All Scrapers"
  - Settings > Provider Settings > "Test a Single Scraper"
  - Context-menu action `scraper_test` / `scraper_test_one`
"""

import importlib
import os
import time

from kodi_six import xbmcgui

from resources.lib.modules import control
from resources.lib.modules import log_utils

try:
    # The addon's own client is preferred (honors cookies, UA, FlareSolverr, etc.).
    from resources.lib.modules import client as _client
except Exception:
    _client = None

try:
    import requests as _requests
except Exception:
    _requests = None


WORKING_DIR = os.path.join(control.addonPath, 'resources', 'lib', 'sources', 'working')
_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/122.0 Safari/537.36')

# Cloudflare providers that rely on FlareSolverr during real scrapes.
FLARESOLVERR_SCRAPERS = frozenset({
    'bstsrs_one',
    'projectfreetv_cyou',
    'projectfreetv_lol',
    'watchseries_cyou',
})


def _flaresolverr_configured():
    try:
        return bool((control.setting('flaresolverr.url') or '').strip())
    except Exception:
        return False


def _list_working_scrapers():
    """Return a sorted list of scraper module names present in sources/working/."""
    names = []
    try:
        for fn in sorted(os.listdir(WORKING_DIR)):
            if fn.endswith('.py') and fn != '__init__.py':
                names.append(fn[:-3])
    except Exception:
        log_utils.log('scraper_tester: failed to list working dir', 1)
    return names


def _probe(url, timeout=8, use_flaresolverr=False):
    """HEAD/GET the url. Return (ok, status_code_or_err, elapsed_ms)."""
    started = time.time()
    # FlareSolverr scrapers: use scrapePage so the probe matches real behaviour.
    if use_flaresolverr and _client is not None:
        try:
            page = _client.scrapePage(url, timeout=timeout)
            elapsed = int((time.time() - started) * 1000)
            if page is None:
                return False, 'NO-RESP', elapsed
            code = str(getattr(page, 'status_code', '') or '')
            ok = code.startswith('2') or code.startswith('3')
            return ok, code or 'NO-CODE', elapsed
        except Exception as e:
            return False, type(e).__name__, int((time.time() - started) * 1000)

    # Try the addon's own client first - it mirrors the real scraper behaviour.
    if _client is not None:
        try:
            resp = _client.request(url, output='response', timeout=str(timeout), error=True)
            elapsed = int((time.time() - started) * 1000)
            if resp and isinstance(resp, tuple) and len(resp) >= 1:
                code = str(resp[0])
                ok = code.startswith('2') or code.startswith('3')
                return ok, code, elapsed
        except Exception as e:
            log_utils.log('scraper_tester: client.request failed %s: %s' % (url, e))

    # Fallback: plain requests GET.
    if _requests is not None:
        try:
            r = _requests.get(url, headers={'User-Agent': _UA}, timeout=timeout,
                              allow_redirects=True)
            elapsed = int((time.time() - started) * 1000)
            return (r.status_code < 400), str(r.status_code), elapsed
        except Exception as e:
            return False, type(e).__name__, int((time.time() - started) * 1000)

    return False, 'no-http-client', 0


def _load_scraper(name):
    """Import a scraper module and instantiate its source class. Returns (mod, instance) or (None,None)."""
    try:
        mod = importlib.import_module('resources.lib.sources.working.%s' % name)
        inst = mod.source()
        return mod, inst
    except Exception as e:
        log_utils.log('scraper_tester: import failed %s: %s' % (name, e), 1)
        return None, None


def _test_one(name):
    """Run probe for a single scraper; returns a result dict."""
    result = {
        'name': name,
        'ok': False,
        'cf': False,
        'status': 'LOAD-FAIL',
        'base': '-',
        'used': '-',
        'ms': 0,
    }
    mod, inst = _load_scraper(name)
    if inst is None:
        return result

    base = getattr(inst, 'probe_link', None) or getattr(inst, 'base_link', None) or ''
    domains = list(getattr(inst, 'domains', []) or [])
    result['base'] = base or '(no base_link)'

    fs_scraper = name in FLARESOLVERR_SCRAPERS
    use_fs = fs_scraper and _flaresolverr_configured()

    tried = []
    candidates = []
    if base:
        candidates.append(base)
    for d in domains:
        if not d:
            continue
        if d in base:
            continue
        candidates.append('https://' + d.lstrip('/'))

    for url in candidates:
        tried.append(url)
        ok, code, ms = _probe(url, use_flaresolverr=use_fs)
        if ok:
            result.update(ok=True, cf=False, status=code, used=url, ms=ms)
            return result
        # CF / FlareSolverr providers: a failed probe is not grounds to treat as dead.
        if fs_scraper and code in ('403', '503', 'ConnectionError', 'NO-RESP', 'NO-CODE'):
            tag = ('CF-%s' % code) if code in ('403', '503') else ('FS-%s' % code)
            result.update(ok=False, cf=True, status=tag, used=url, ms=ms)
            return result
        result.update(ok=False, cf=False, status=code, used=url, ms=ms)

    if not tried:
        result['status'] = 'NO-URL'
    return result


def _format_line(r):
    if r.get('cf'):
        icon = '[COLOR yellow]CF[/COLOR]'
    elif r['ok']:
        icon = '[COLOR lime]OK[/COLOR]'
    else:
        icon = '[COLOR red]DEAD[/COLOR]'
    fs_note = ' [I](FlareSolverr)[/I]' if r.get('fs') else ''
    return '[B]%s[/B]  %s  [I]%s[/I]  (%s, %dms)%s' % (r['name'], icon, r['status'], r['used'], r['ms'], fs_note)


def test_all():
    """Test every scraper in sources/working/ with a progress dialog."""
    names = _list_working_scrapers()
    if not names:
        control.okDialog('No scrapers found in sources/working/.', 'Scraper Tester')
        return

    pd = xbmcgui.DialogProgress()
    pd.create('Gratis Red - Scraper Tester', 'Testing providers...')

    results = []
    alive = 0
    cf = 0
    total = len(names)
    for i, name in enumerate(names):
        if pd.iscanceled():
            break
        pd.update(int((i / float(total)) * 100),
                  'Testing [B]%s[/B]  (%d / %d)' % (name, i + 1, total))
        r = _test_one(name)
        r['fs'] = name in FLARESOLVERR_SCRAPERS
        if r['ok']:
            alive += 1
        elif r.get('cf'):
            cf += 1
        results.append(r)

    pd.close()

    dead = len(results) - alive - cf
    header = ('[B]Scraper Tester Report[/B]  -  '
              '[COLOR lime]%d alive[/COLOR] / '
              '[COLOR yellow]%d CF[/COLOR] / '
              '[COLOR red]%d dead[/COLOR] (of %d)' % (alive, cf, dead, len(results)))
    lines = [header, '']
    if cf and not _flaresolverr_configured():
        lines.append('[COLOR yellow]CF[/COLOR] = Cloudflare block — configure FlareSolverr in Playback Settings.')
        lines.append('')
    elif cf:
        lines.append('[COLOR yellow]CF[/COLOR] = FlareSolverr provider — probe failed but may still work during playback.')
        lines.append('')
    lines.extend(_format_line(r) for r in results)
    body = '\n'.join(lines)

    try:
        xbmcgui.Dialog().textviewer('Gratis Red - Scraper Tester', body)
    except Exception:
        control.okDialog(body, 'Gratis Red - Scraper Tester')

    try:
        out = os.path.join(control.dataPath, 'scraper_tester_last.txt')
        with open(out, 'w') as f:
            f.write('Gratis Red Scraper Tester - %s\n' % time.strftime('%Y-%m-%d %H:%M:%S'))
            for r in results:
                tag = 'OK' if r['ok'] else ('CF' if r.get('cf') else 'DEAD')
                f.write('%s\t%s\t%s\t%s\t%dms\n' % (
                    r['name'], tag, r['status'], r['used'], r['ms']))
    except Exception:
        pass


def test_one():
    """Show a picker of scrapers, test the chosen one, show a dialog."""
    names = _list_working_scrapers()
    if not names:
        control.okDialog('No scrapers found in sources/working/.', 'Scraper Tester')
        return

    idx = xbmcgui.Dialog().select('Gratis Red - Select a Scraper to Test', names)
    if idx is None or idx < 0:
        return

    name = names[idx]
    pd = xbmcgui.DialogProgressBG()
    try:
        pd.create('Gratis Red', 'Testing %s...' % name)
    except Exception:
        pd = None

    r = _test_one(name)
    r['fs'] = name in FLARESOLVERR_SCRAPERS

    try:
        if pd is not None:
            pd.close()
    except Exception:
        pass

    msg = _format_line(r)
    if r.get('cf') and not _flaresolverr_configured():
        msg += '[CR][CR][COLOR yellow]Cloudflare-protected — set FlareSolverr URL in Playback Settings.[/COLOR]'
    try:
        xbmcgui.Dialog().textviewer('Gratis Red - Scraper Tester', msg)
    except Exception:
        control.okDialog(msg, 'Gratis Red - Scraper Tester')
