# -*- coding: utf-8 -*-
"""
Free Flow - downloads manager.

Features:
  - resolves (via resolvers + resolveurl) then downloads to the user's device
  - shows a live progress dialog with MB counter / percent
  - persists a JSON state file in the addon profile so the Downloads section
    can list, replay and delete past downloads
  - download folder is configurable in Settings (defaults to
    special://home/downloads/)
"""
import json
import os
import re
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')

try:
    import requests
except Exception:
    requests = None


UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')


# ---------------- paths ---------------- #

def _profile_dir():
    p = xbmcvfs.translatePath('special://profile/addon_data/%s/' % ADDON_ID)
    if not os.path.isdir(p):
        try:
            os.makedirs(p, exist_ok=True)
        except Exception:
            pass
    return p


def state_path():
    return os.path.join(_profile_dir(), 'downloads.json')


def get_download_folder():
    """Return the configured download folder. Ensures it exists."""
    try:
        configured = ADDON.getSetting('download_folder') or ''
    except Exception:
        configured = ''
    if not configured:
        configured = 'special://home/downloads/'
    folder = xbmcvfs.translatePath(configured)
    if not folder.endswith(os.sep) and not folder.endswith('/'):
        folder += os.sep
    try:
        if not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
    except Exception:
        pass
    return folder


# ---------------- state ---------------- #

def load_state():
    p = state_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def save_state(items):
    try:
        with open(state_path(), 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=2)
    except Exception:
        pass


def _upsert(entry):
    items = load_state()
    fp = entry.get('filepath')
    for i, e in enumerate(items):
        if e.get('filepath') == fp:
            items[i] = entry
            save_state(items)
            return
    items.insert(0, entry)
    save_state(items)


def remove_entry(filepath, delete_file=True):
    items = [e for e in load_state() if e.get('filepath') != filepath]
    save_state(items)
    if delete_file and filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception:
            pass


# ---------------- filename helpers ---------------- #

def _sanitise(name):
    name = re.sub(r'\[/?[A-Z]+[^\]]*\]', '', name or '')   # Kodi colour tags
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', '_', name).strip()
    return (name or 'download')[:180]


def _guess_ext(url, fallback='.mkv'):
    m = re.search(r'\.(mkv|mp4|avi|webm|m4v|mov|ts|flv)(?:\?|$)',
                  url or '', re.I)
    if m:
        return '.' + m.group(1).lower()
    return fallback


def _unique_path(folder, base, ext):
    p = os.path.join(folder, base + ext)
    if not os.path.exists(p):
        return p
    i = 2
    while True:
        p = os.path.join(folder, '%s (%d)%s' % (base, i, ext))
        if not os.path.exists(p):
            return p
        i += 1


# ---------------- resolving ---------------- #

def _resolve_for_download(url, log=None):
    """Try built-in resolvers first, then resolveurl. Return direct URL."""
    try:
        from resources.lib import resolvers  # package-style
    except Exception:
        try:
            import resolvers  # flat import (sys.path already includes lib/)
        except Exception:
            resolvers = None

    if resolvers is not None:
        try:
            if resolvers.can_resolve(url):
                direct = resolvers.resolve(url, log=log)
                if direct:
                    return direct
        except Exception as e:
            if log:
                log('downloads resolvers error: %s' % e)

    try:
        import resolveurl
        hmf = resolveurl.HostedMediaFile(
            url=url, include_disabled=False, include_universal=True)
        if hmf.valid_url():
            r = hmf.resolve()
            if r:
                return r
        r = resolveurl.resolve(url)
        if r:
            return r
    except Exception as e:
        if log:
            log('downloads resolveurl error: %s' % e)

    # Maybe the URL is already a direct media file
    if re.search(r'\.(mkv|mp4|avi|webm|m4v|mov|ts|flv)(?:\?|$)',
                 url or '', re.I):
        return url
    return None


# ---------------- the actual download ---------------- #

def download(source_url, title, thumb='', fanart='', log=None):
    """Blocking download with a background progress dialog.

    source_url may be a host-page URL (e.g. ddownload.com/XXXX) or a
    direct media URL; we will resolve if required.
    Returns True on success, False otherwise.
    """
    if requests is None:
        xbmcgui.Dialog().notification(
            'Free Flow', 'Download requires script.module.requests',
            xbmcgui.NOTIFICATION_ERROR, 6000)
        return False

    if log:
        log('downloads: start title=%s url=%s' % (title, source_url))

    # Resolve first
    direct = _resolve_for_download(source_url, log=log)
    if not direct:
        xbmcgui.Dialog().notification(
            'Free Flow', 'Could not resolve link for download',
            xbmcgui.NOTIFICATION_ERROR, 5000)
        return False

    folder = get_download_folder()
    base = _sanitise(title)
    ext = _guess_ext(direct)
    filepath = _unique_path(folder, base, ext)

    dlg = xbmcgui.DialogProgressBG()
    try:
        dlg.create('Free Flow', 'Starting: ' + base)
    except Exception:
        dlg = None

    started = time.time()
    done_bytes = 0
    total_bytes = 0
    ok = False

    try:
        headers = {'User-Agent': UA, 'Referer': source_url}
        r = requests.get(direct, headers=headers, stream=True, timeout=30,
                         allow_redirects=True)
        if r.status_code >= 400:
            if dlg:
                dlg.close()
            xbmcgui.Dialog().notification(
                'Free Flow', 'Download failed HTTP %d' % r.status_code,
                xbmcgui.NOTIFICATION_ERROR, 5000)
            return False
        try:
            total_bytes = int(r.headers.get('Content-Length') or 0)
        except Exception:
            total_bytes = 0
        monitor = xbmc.Monitor()
        last_ui = 0.0
        with open(filepath, 'wb') as fout:
            for chunk in r.iter_content(chunk_size=262144):
                if monitor.abortRequested():
                    if log:
                        log('downloads: abort requested')
                    break
                if not chunk:
                    continue
                fout.write(chunk)
                done_bytes += len(chunk)
                now = time.time()
                if dlg and (now - last_ui) >= 0.5:
                    last_ui = now
                    mb = done_bytes / 1048576.0
                    if total_bytes > 0:
                        pct = int(done_bytes * 100 / total_bytes)
                        tmb = total_bytes / 1048576.0
                        speed = (done_bytes / max(now - started, 0.1)
                                 ) / 1048576.0
                        dlg.update(
                            max(1, min(99, pct)), 'Free Flow',
                            '%s  %.1f / %.1f MB  (%.2f MB/s)' %
                            (base[:40], mb, tmb, speed))
                    else:
                        dlg.update(
                            0, 'Free Flow',
                            '%s  %.1f MB' % (base[:40], mb))
        ok = (total_bytes == 0 or done_bytes >= total_bytes)
    except Exception as e:
        if log:
            log('downloads exception: %s' % e)
        try:
            os.remove(filepath)
        except Exception:
            pass
        xbmcgui.Dialog().notification(
            'Free Flow', 'Download failed: %s' % str(e)[:60],
            xbmcgui.NOTIFICATION_ERROR, 6000)
        return False
    finally:
        if dlg:
            try:
                dlg.close()
            except Exception:
                pass

    entry = {
        'title': title,
        'filepath': filepath,
        'filename': os.path.basename(filepath),
        'bytes': done_bytes,
        'total_bytes': total_bytes,
        'source_url': source_url,
        'resolved_url': direct,
        'thumb': thumb,
        'fanart': fanart,
        'added': time.time(),
        'elapsed': time.time() - started,
        'completed': ok,
    }
    _upsert(entry)

    xbmcgui.Dialog().notification(
        'Free Flow',
        ('Download complete: ' if ok else 'Download stopped: ') +
        os.path.basename(filepath),
        xbmcgui.NOTIFICATION_INFO if ok
        else xbmcgui.NOTIFICATION_WARNING, 6000)
    return ok
