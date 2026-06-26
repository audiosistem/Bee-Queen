# -*- coding: utf-8 -*-
"""Vidscr bundle / downloads / gofile helpers.

Provides four things used by the Settings → Debug actions:

  1. downloads_dir()       — best-effort cross-platform path to the device
                             "Downloads" folder (Android, Windows, macOS,
                             Linux, iOS, Apple TV, Fire TV / Nvidia Shield).
  2. make_addon_zip(dest)  — zip the currently installed addon directory
                             exactly as Kodi installed it, ready to re-install
                             on another device.
  3. make_debug_zip(dest)  — bundle the latest diagnostic report + debug log
                             + a JSON settings dump into a support zip.
  4. upload_gofile(path)   — upload any file to gofile.io and return the
                             public share URL.

All four helpers try very hard to succeed across devices (Android / iOS
restricted sandbox, Kodi on Fire TV, etc.) by falling back through
several candidate directories and by using xbmcvfs where native
filesystem access is blocked.
"""
import os
import sys
import json
import time
import zipfile
import datetime
import traceback

try:
    import xbmc
    import xbmcvfs
    import xbmcgui
except Exception:  # pragma: no cover
    xbmc = xbmcvfs = xbmcgui = None

from . import common as C


# ---------------------------------------------------------------------------
# 1. Downloads folder detection
# ---------------------------------------------------------------------------

def _expand(p):
    try:
        return os.path.abspath(os.path.expanduser(os.path.expandvars(p)))
    except Exception:
        return p


def is_writable(path):
    try:
        if not path or not os.path.isdir(path):
            return False
        testf = os.path.join(path, '.vidscr_write_test')
        with open(testf, 'w') as f:
            f.write('ok')
        os.remove(testf)
        return True
    except Exception:
        return False


def _android_candidates():
    # Android / Fire TV / Nvidia Shield — external storage paths.
    # Note: on modern Android (10+) scoped storage usually still allows
    # the public "Download" directory from a sideloaded Kodi.
    return [
        '/storage/emulated/0/Download',
        '/storage/emulated/0/Downloads',
        '/sdcard/Download',
        '/sdcard/Downloads',
        '/storage/self/primary/Download',
        '/mnt/sdcard/Download',
        # Fire TV internal user-visible downloads
        '/storage/emulated/0/Android/data/org.xbmc.kodi/files/Download',
    ]


def downloads_dir():
    """Return a usable Downloads folder for the current device.

    Order of preference:
      1. User override setting ``downloads_dir`` (if set + writable)
      2. Platform-specific standard paths
      3. Kodi ``special://home/Downloads`` (works everywhere incl. iOS)
      4. Kodi profile / Downloads (last resort — always writable)
    """
    # 1. User override
    try:
        override = (C.ADDON.getSetting('downloads_dir') or '').strip()
    except Exception:
        override = ''
    if override and is_writable(override):
        return override

    candidates = []

    # 2. Platform-specific
    home = os.environ.get('HOME') or os.environ.get('USERPROFILE') or ''
    osname = (sys.platform or '').lower()

    # Android/Fire TV — detect via env vars or /system path
    if os.environ.get('ANDROID_DATA') or os.environ.get('ANDROID_ROOT') \
            or os.path.exists('/system/build.prop'):
        candidates.extend(_android_candidates())

    if 'win' in osname and 'darwin' not in osname:  # Windows
        if home:
            candidates.append(os.path.join(home, 'Downloads'))
        up = os.environ.get('USERPROFILE')
        if up:
            candidates.append(os.path.join(up, 'Downloads'))
    elif 'darwin' in osname or osname == 'mac':     # macOS
        if home:
            candidates.append(os.path.join(home, 'Downloads'))
    elif 'linux' in osname:                          # Linux desktop / LibreELEC
        if home:
            candidates.append(os.path.join(home, 'Downloads'))
            candidates.append(os.path.join(home, 'downloads'))
        candidates.append('/storage/downloads')      # LibreELEC
        candidates.append('/var/media/Downloads')    # CoreELEC
    else:                                            # iOS / tvOS / unknown
        if home:
            candidates.append(os.path.join(home, 'Downloads'))

    # 3. Kodi's own special://home/Downloads (creates cross-platform)
    try:
        if xbmcvfs:
            special = xbmcvfs.translatePath('special://home/Downloads')
            candidates.append(special)
    except Exception:
        pass

    # 4. Addon profile Downloads — always writable
    profile_dl = os.path.join(C.PROFILE_PATH, 'Downloads')
    candidates.append(profile_dl)

    for c in candidates:
        c = _expand(c)
        if is_writable(c):
            return c
        # try to create it
        try:
            os.makedirs(c, exist_ok=True)
            if is_writable(c):
                return c
        except Exception:
            continue

    # absolute last resort — profile dir itself
    return C.PROFILE_PATH


# ---------------------------------------------------------------------------
# 2. Addon source zip packager
# ---------------------------------------------------------------------------

def _walk(path):
    for dirpath, dirnames, filenames in os.walk(path):
        # Skip pyc cache & hidden dirs — not needed in a portable install zip
        dirnames[:] = [d for d in dirnames
                       if d not in ('__pycache__', '.git', '.svn', '.idea')]
        for fn in filenames:
            if fn.endswith('.pyc'):
                continue
            yield os.path.join(dirpath, fn)


def make_addon_zip(dest_dir=None, progress=None):
    """Zip up the installed addon folder (e.g. .../addons/plugin.video.vidscr)
    into ``dest_dir`` under the canonical name ``plugin.video.vidscr-<ver>.zip``.

    The structure inside the zip mirrors what Kodi expects when installing
    from a .zip — the top-level folder is ``plugin.video.vidscr/``.
    Returns the absolute path of the created zip.
    """
    addon_root = C.ADDON_PATH
    addon_id = C.ADDON.getAddonInfo('id')
    version = C.ADDON.getAddonInfo('version')
    if not dest_dir:
        dest_dir = downloads_dir()
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, '%s-%s.zip' % (addon_id, version))

    files = list(_walk(addon_root))
    total = max(1, len(files))
    C.log('bundle: zipping %d files from %s → %s' % (total, addon_root, dest))

    # Build to a temp name first so a partial zip never clobbers an old one
    tmp_dest = dest + '.part'
    with zipfile.ZipFile(tmp_dest, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for i, fpath in enumerate(files, 1):
            try:
                rel = os.path.relpath(fpath, os.path.dirname(addon_root))
                # Normalise to forward slashes (works on every OS)
                arc = rel.replace('\\', '/')
                z.write(fpath, arc)
            except Exception as e:
                C.log('bundle: skip %s (%s)' % (fpath, e))
            if progress and (i % 10 == 0 or i == total):
                pct = int(i * 100 / total)
                try:
                    progress.update(min(90, pct), 'Zipping %d / %d files…' % (i, total))
                except Exception:
                    pass
    os.replace(tmp_dest, dest)
    C.log('bundle: wrote %s (%d bytes)' % (dest, os.path.getsize(dest)))
    return dest


# ---------------------------------------------------------------------------
# 3. Debug support bundle
# ---------------------------------------------------------------------------

def make_debug_zip(dest_dir=None):
    """Create a support zip containing:
        * diagnostic_report.txt
        * vidscr_debug.log (addon-local rolling log)
        * settings_redacted.json
        * environment.json (env vars + sys.path — secrets removed)
    """
    from . import debug as D
    if not dest_dir:
        dest_dir = downloads_dir()
    os.makedirs(dest_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    dest = os.path.join(dest_dir, 'vidscr-debug-%s.zip' % stamp)

    report_text = D.build_report()
    settings = D._settings_dump()
    env = {
        'sys_path':      sys.path,
        'python':        sys.version,
        'platform':      sys.platform,
        'env_whitelist': {k: v for k, v in os.environ.items()
                          if k in ('HOME', 'USERPROFILE', 'ANDROID_DATA',
                                   'ANDROID_ROOT', 'KODI_HOME')},
    }

    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('diagnostic_report.txt', report_text)
        z.writestr('settings_redacted.json', json.dumps(settings, indent=2))
        z.writestr('environment.json', json.dumps(env, indent=2, default=str))
        try:
            if os.path.exists(C.DEBUG_LOG_PATH):
                z.write(C.DEBUG_LOG_PATH, 'vidscr_debug.log')
        except Exception as e:
            z.writestr('vidscr_debug.log', 'could not read: %s' % e)
    C.log('bundle: wrote debug zip %s' % dest)
    return dest


# ---------------------------------------------------------------------------
# 4. GoFile upload
# ---------------------------------------------------------------------------

def upload_gofile(filepath, progress=None):
    """Upload ``filepath`` to gofile.io. Returns ('ok', url) or ('err', msg)."""
    try:
        import requests
    except Exception as e:
        return ('err', 'requests module missing: %s' % e)
    if not os.path.exists(filepath):
        return ('err', 'file does not exist: %s' % filepath)
    try:
        # Pick the best upload server
        if progress:
            try: progress.update(5, 'Selecting gofile server…')
            except Exception: pass
        srv_res = requests.get('https://api.gofile.io/servers', timeout=15)
        srv_res.raise_for_status()
        srv_json = srv_res.json() or {}
        server = None
        servers = (srv_json.get('data') or {}).get('servers') or []
        if servers:
            server = servers[0].get('name')
        if not server:
            server = 'store1'  # reasonable fallback

        url = 'https://%s.gofile.io/uploadFile' % server
        if progress:
            try: progress.update(20, 'Uploading to %s…' % server)
            except Exception: pass
        size = os.path.getsize(filepath)
        C.log('bundle: uploading %s (%d bytes) to %s' % (filepath, size, url))
        with open(filepath, 'rb') as fh:
            files = {'file': (os.path.basename(filepath), fh)}
            r = requests.post(url, files=files, timeout=300)
        r.raise_for_status()
        data = r.json() or {}
        if data.get('status') != 'ok':
            return ('err', 'gofile status: %s' % data)
        link = ((data.get('data') or {}).get('downloadPage')
                or (data.get('data') or {}).get('downloadUrl')
                or '')
        if not link:
            return ('err', 'gofile returned no link: %s' % data)
        C.log('bundle: gofile upload OK → %s' % link)
        return ('ok', link)
    except Exception as e:
        C.log('bundle: gofile upload FAILED: %s\n%s' % (e, traceback.format_exc()))
        return ('err', '%s: %s' % (type(e).__name__, e))
