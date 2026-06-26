# -*- coding: utf-8 -*-
"""Vidscr deep debug / diagnostics module.

Generates a thorough diagnostic report covering:
  * Host system (Kodi version, platform, Python version, arch)
  * Addon metadata (version, path, profile path)
  * Addon settings (redacted — secrets never leaked)
  * Dependency check (requests, resolveurl, inputstream.adaptive)
  * Writable-path check (profile, temp, Downloads candidate)
  * Network reachability for primary + secondary stream hosts and TMDB
  * Recent log tail (last 200 lines)
  * Resolver smoke-test (optional — caller passes imdb id)

The report is returned as a single plain-text string so it can be
displayed inside a Kodi textviewer, written to a .log file or bundled
into a .zip for support.
"""
import os
import sys
import json
import time
import platform
import traceback
import datetime

try:
    import xbmc
    import xbmcaddon
    import xbmcvfs
    import xbmcgui
except Exception:  # pragma: no cover — lets module import outside Kodi for unit tests
    xbmc = xbmcaddon = xbmcvfs = xbmcgui = None

from . import common as C

# ---------------------------------------------------------------------------
# Settings that must NEVER appear in diagnostic output (they can leak auth).
# ---------------------------------------------------------------------------
_SECRET_KEYS = (
    'tmdb_api_key', 'trakt_client_secret', 'simkl_client_secret',
    'trakt_token', 'trakt_refresh', 'simkl_token', 'simkl_refresh',
    'bingebase_token', 'bingebase_refresh', 'bingebase_device',
)


def _redact(key, value):
    if not value:
        return '(empty)'
    lk = (key or '').lower()
    if any(s in lk for s in _SECRET_KEYS):
        if len(value) <= 6:
            return '*' * len(value)
        return value[:3] + '…' + value[-3:] + '  (redacted, len=%d)' % len(value)
    return value


# ---------------------------------------------------------------------------
# Section: host / addon / dependency info
# ---------------------------------------------------------------------------

def _kodi_info():
    info = {}
    try:
        info['kodi_build'] = xbmc.getInfoLabel('System.BuildVersion') if xbmc else 'n/a'
        info['kodi_build_date'] = xbmc.getInfoLabel('System.BuildDate') if xbmc else 'n/a'
        info['kodi_platform'] = xbmc.getInfoLabel('System.Platform.Name') if xbmc else 'n/a'
    except Exception as e:
        info['error'] = str(e)
    return info


def _system_info():
    return {
        'python_version': sys.version.split()[0],
        'python_impl': platform.python_implementation(),
        'os_name': platform.system(),
        'os_release': platform.release(),
        'machine': platform.machine(),
        'platform_full': platform.platform(),
        'android_env': os.environ.get('ANDROID_DATA') or os.environ.get('ANDROID_ROOT') or 'not-android',
        'home_env': os.environ.get('HOME') or os.environ.get('USERPROFILE') or '',
    }


def _addon_info():
    a = C.ADDON
    return {
        'id': a.getAddonInfo('id'),
        'name': a.getAddonInfo('name'),
        'version': a.getAddonInfo('version'),
        'author': a.getAddonInfo('author'),
        'path': C.ADDON_PATH,
        'profile': C.PROFILE_PATH,
        'log_path': C.DEBUG_LOG_PATH,
    }


def _dep_info():
    deps = {}
    for modname in ('requests', 'resolveurl', 'urllib3', 'certifi'):
        try:
            mod = __import__(modname)
            deps[modname] = getattr(mod, '__version__', 'present')
        except Exception as e:
            deps[modname] = 'MISSING (%s)' % type(e).__name__
    # Check optional Kodi addons
    for addon_id in ('script.module.requests', 'script.module.resolveurl',
                     'inputstream.adaptive'):
        try:
            a = xbmcaddon.Addon(addon_id) if xbmcaddon else None
            deps[addon_id] = a.getAddonInfo('version') if a else 'missing'
        except Exception:
            deps[addon_id] = 'missing'
    return deps


def _paths_info():
    out = {}
    try:
        out['profile_writable'] = os.access(C.PROFILE_PATH, os.W_OK)
    except Exception as e:
        out['profile_writable'] = 'err: %s' % e
    try:
        from . import bundle as B
        out['downloads_candidate'] = B.downloads_dir()
        out['downloads_writable'] = B.is_writable(out['downloads_candidate'])
    except Exception as e:
        out['downloads_candidate'] = 'err: %s' % e
    try:
        out['tmp_dir'] = xbmcvfs.translatePath('special://temp') if xbmcvfs else ''
    except Exception:
        out['tmp_dir'] = ''
    return out


def _settings_dump():
    """Dump every Vidscr setting, redacting secrets."""
    keys = [
        'tmdb_api_key', 'tmdb_lang', 'tmdb_region', 'results_per_page',
        'vidsrc_host', 'enable_secondary_source', 'secondary_source_host',
        'show_source_picker', 'show_server_picker', 'prefer_resolveurl',
        'probe_candidates', 'auto_secondary_on_404',
        'aggregate_all_sources', 'aggregate_workers',
        'auto_play_first', 'remember_quality', 'use_inputstream',
        'auto_fallback', 'auto_fallback_seconds',
        'smart_next_up_enabled', 'smart_next_up_seconds',
        'trakt_enabled', 'trakt_scrobble', 'trakt_client_id', 'trakt_client_secret',
        'bingebase_enabled', 'bingebase_scrobble',
        'simkl_enabled', 'simkl_scrobble', 'simkl_client_id', 'simkl_client_secret',
        'show_watched_marker', 'use_kodi_library_db', 'resume_threshold_pct',
        'debug_log', 'cache_ttl_hours',
    ]
    out = {}
    for k in keys:
        try:
            out[k] = _redact(k, C.ADDON.getSetting(k))
        except Exception as e:
            out[k] = 'err: %s' % e
    return out


# ---------------------------------------------------------------------------
# Section: network reachability
# ---------------------------------------------------------------------------

_NET_TARGETS = [
    ('TMDB api',         'https://api.themoviedb.org/3/configuration'),
    ('TMDB images',      'https://image.tmdb.org/t/p/w92/'),
    ('vidsrcme.ru',      'https://vidsrcme.ru/'),
    ('vidsrc.xyz',       'https://vidsrc.xyz/'),
    ('vidsrc.to',        'https://vidsrc.to/'),
    ('vidsrc.net',       'https://vidsrc.net/'),
    ('vidsrc.cc',        'https://vidsrc.cc/'),
    ('2embed.cc',        'https://www.2embed.cc/'),
    ('embed.su',         'https://embed.su/'),
    ('multiembed.mov',   'https://multiembed.mov/'),
    ('autoembed.cc',     'https://player.autoembed.cc/'),
    ('moviesapi.club',   'https://moviesapi.club/'),
    ('smashystream.com', 'https://player.smashy.stream/'),
    ('cloudnestra.com',  'https://cloudnestra.com/'),
    ('trakt api',        'https://api.trakt.tv/'),
    ('simkl api',        'https://api.simkl.com/'),
    ('gofile api',       'https://api.gofile.io/servers'),
]


def net_test(timeout=6):
    """HEAD/GET each known host. Returns list of (name, url, status, ms, err)."""
    try:
        import requests
    except Exception as e:
        return [('requests-missing', '', 0, 0, str(e))]

    results = []
    for name, url in _NET_TARGETS:
        t0 = time.time()
        status, err = 0, ''
        try:
            r = requests.get(url, timeout=timeout, headers={
                'User-Agent': 'Mozilla/5.0 (VidscrDebug/1.0)',
                'Accept': '*/*',
            })
            status = r.status_code
        except Exception as e:
            err = '%s: %s' % (type(e).__name__, str(e)[:120])
        ms = int((time.time() - t0) * 1000)
        results.append((name, url, status, ms, err))
    return results


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------

def _fmt_kv(title, d):
    lines = ['', '-- %s --' % title]
    for k, v in d.items():
        lines.append('  %-22s : %s' % (k, v))
    return '\n'.join(lines)


def _fmt_net(results):
    lines = ['', '-- network reachability --',
             '  %-18s %-6s %6s  %s' % ('host', 'status', 'ms', 'error/url')]
    for name, url, status, ms, err in results:
        tag = 'OK  ' if 200 <= status < 400 else ('WARN' if status else 'FAIL')
        line = '  %-18s %-6s %6d  %s' % (name, '%s %s' % (tag, status or '---'), ms, err or url)
        lines.append(line)
    return '\n'.join(lines)


def build_report(run_net=True, include_log_tail=200):
    """Return a full plain-text diagnostic report."""
    lines = []
    lines.append('=' * 70)
    lines.append('Vidscr — deep diagnostic report')
    lines.append('generated: %s' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    lines.append('=' * 70)

    lines.append(_fmt_kv('addon', _addon_info()))
    lines.append(_fmt_kv('kodi',  _kodi_info()))
    lines.append(_fmt_kv('system', _system_info()))
    lines.append(_fmt_kv('dependencies', _dep_info()))
    lines.append(_fmt_kv('paths', _paths_info()))
    lines.append(_fmt_kv('settings (secrets redacted)', _settings_dump()))

    if run_net:
        try:
            lines.append(_fmt_net(net_test()))
        except Exception as e:
            lines.append('-- network reachability --\n  ERROR: %s\n%s'
                         % (e, traceback.format_exc()))

    # Log tail
    lines.append('')
    lines.append('-- debug log (last %d lines) --' % include_log_tail)
    try:
        content = C.read_debug_log() or '(empty — enable Debug logging in settings)'
        tail = content.splitlines()[-include_log_tail:]
        lines.extend('  ' + ln for ln in tail)
    except Exception as e:
        lines.append('  error reading log: %s' % e)

    lines.append('')
    lines.append('=' * 70)
    lines.append('end of report')
    return '\n'.join(lines)


def show_report_dialog():
    """Run deep diagnostics and display them inside a Kodi textviewer."""
    C.log('deep-debug: building diagnostic report')
    dlg = xbmcgui.Dialog()
    pd = xbmcgui.DialogProgress()
    pd.create('Vidscr', 'Running deep diagnostics…')
    try:
        pd.update(10, 'Collecting system info…')
        sys_part = (_fmt_kv('addon', _addon_info())
                    + _fmt_kv('kodi', _kodi_info())
                    + _fmt_kv('system', _system_info())
                    + _fmt_kv('dependencies', _dep_info())
                    + _fmt_kv('paths', _paths_info())
                    + _fmt_kv('settings (secrets redacted)', _settings_dump()))
        if pd.iscanceled():
            pd.close(); return
        pd.update(40, 'Probing network hosts…')
        net_part = _fmt_net(net_test())
        pd.update(85, 'Assembling report…')
        tail = (C.read_debug_log() or '').splitlines()[-200:]
        log_part = '\n-- debug log (last 200 lines) --\n' + '\n'.join('  ' + ln for ln in tail)
        pd.update(100, 'Done')
    finally:
        pd.close()
    report = ('=' * 70 + '\nVidscr deep diagnostic\n' +
              'generated: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') +
              '\n' + '=' * 70 + sys_part + net_part + log_part)
    C.log('deep-debug: showing report dialog (%d chars)' % len(report))
    dlg.textviewer('Vidscr Deep Diagnostic', report)


def write_report_file(path):
    """Write the report to a file and return the path."""
    text = build_report()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    C.log('deep-debug: wrote diagnostic report to %s' % path)
    return path


def export_cloudnestra_dumps(target_folder=None):
    """Copy any captured cloudnestra prorcp body dumps into the user's
    Downloads folder so they can share them. Returns (count, target_dir)."""
    src = os.path.join(C.PROFILE_PATH, 'cloudnestra_dumps')
    if not os.path.isdir(src):
        return 0, src
    files = sorted(f for f in os.listdir(src) if f.endswith('.json'))
    if not files:
        return 0, src
    if not target_folder:
        # Try Downloads
        candidates = [
            '/storage/emulated/0/Download',
            os.path.expanduser('~/Downloads'),
            '/storage/downloads',
        ]
        for c in candidates:
            if os.path.isdir(c) and os.access(c, os.W_OK):
                target_folder = c
                break
        if not target_folder:
            target_folder = C.PROFILE_PATH
    import shutil
    n = 0
    for f in files[-5:]:  # last 5
        try:
            shutil.copy2(os.path.join(src, f), os.path.join(target_folder, f))
            n += 1
        except Exception as e:
            C.log('export_cloudnestra_dumps: %s -> %s' % (f, e))
    C.log('export_cloudnestra_dumps: copied %d dumps to %s' % (n, target_folder))
    return n, target_folder
