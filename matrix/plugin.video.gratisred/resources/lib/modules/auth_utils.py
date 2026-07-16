# -*- coding: utf-8 -*-
import os
import sys
import time

import requests
from kodi_six import xbmcgui

from resources.lib.modules import control

DEFAULT_TMDB_READ_TOKEN = (
    'eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJhMGJmMjA3YzVmZjZjMGNhYWJhYzAzMjdlMzliMWNkMiIsIm5iZiI6MTUwMzk0ODAxMC43NTQsInN1YiI6IjU5YTQ2Y2U4YzNhMzY4MGIxMjAwMjgxYiIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.'
    '2pYaMVzWy-TNg2SBlkP_CrYWpaxcU7LZIZLPdgJp9jw'
)


def tmdb_read_token():
    token = control.setting('tmdb.lists_read_token') or ''
    if not token:
        token = DEFAULT_TMDB_READ_TOKEN
    return token


def tmdb_read_headers():
    return {
        'accept': 'application/json',
        'content-type': 'application/json',
        'Authorization': 'Bearer %s' % tmdb_read_token(),
    }


def copy2clip(txt):
    if not txt:
        return
    txt = txt.strip()
    platform = sys.platform
    try:
        if platform == 'win32':
            from subprocess import Popen, PIPE
            p = Popen(['clip'], stdin=PIPE)
            p.communicate(input=txt.encode('utf-8'))
            return
        if platform == 'darwin':
            from subprocess import Popen, PIPE
            p = Popen(['pbcopy'], stdin=PIPE)
            p.communicate(input=txt.encode('utf-8'))
            return
        from subprocess import Popen, PIPE
        p = Popen(['xsel', '-pi'], stdin=PIPE)
        p.communicate(input=txt.encode('utf-8'))
    except Exception:
        pass


def make_tinyurl(url):
    if not url:
        return ''
    try:
        response = requests.get('https://tinyurl.com/api-create.php', params={'url': url}, timeout=3)
        if response.status_code != 200:
            return ''
        short_url = (response.text or '').strip()
        if short_url.lower().startswith('http'):
            return short_url
    except Exception:
        pass
    return ''


def _ensure_segno_path():
    lib_path = os.path.join(control.addonPath, 'resources', 'lib')
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)


def _ensure_profile():
    profile = control.dataPath
    if not os.path.exists(profile):
        try:
            os.makedirs(profile)
        except Exception:
            try:
                control.makeFile(profile)
            except Exception:
                pass
    return profile


def make_qrcode(url):
    if not url:
        return ''
    try:
        _ensure_segno_path()
        import segno
        from hashlib import sha1
        profile = _ensure_profile()
        qr_id = sha1(url.encode('utf-8')).hexdigest()[:12]
        stamp = int(time.time() * 1000)
        art_path = os.path.join(profile, 'qr_%s_%s.png' % (qr_id, stamp))
        segno.make(url, micro=False).save(art_path, scale=14)
        if os.path.exists(art_path):
            return control.transPath(art_path)
    except Exception:
        pass
    return ''


def auth_progress_wait(dialog, interval_sec):
    if not dialog or dialog.iscanceled():
        return True
    target_ms = int(max(float(interval_sec), 0.25) * 1000)
    waited = 0
    while waited < target_ms:
        if dialog.iscanceled() or control.monitor.abortRequested():
            return True
        slice_ms = min(100, target_ms - waited)
        control.sleep(slice_ms)
        waited += slice_ms
    return dialog.iscanceled()


class AuthProgressDialog(xbmcgui.WindowXMLDialog):
    closing_actions = (9, 10, 13, 92, 216)

    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, args)
        self._heading = kwargs.get('heading', '') or ''
        self._qr_path = kwargs.get('qr_path', '') or ''
        self.is_canceled = False

    def _action_id(self, action):
        if isinstance(action, int):
            return action
        try:
            return action.getId()
        except Exception:
            return -1

    def onInit(self):
        try:
            self.getControl(2000).setLabel(self._heading)
            self.getControl(2001).setLabel('')
            if self._qr_path:
                self.setProperty('qr_visible', 'true')
                self.getControl(200).setImage(self._qr_path)
            else:
                self.setProperty('qr_visible', 'false')
        except Exception:
            pass
        self.setProperty('auth_progress_ready', 'true')

    def iscanceled(self):
        return self.is_canceled

    def onAction(self, action):
        if self._action_id(action) in self.closing_actions:
            self.is_canceled = True
            self.close()

    def update(self, content='', qr_path=''):
        try:
            self.getControl(2001).setLabel(content or '')
            path = qr_path or self._qr_path
            if path:
                self._qr_path = path
                self.setProperty('qr_visible', 'true')
                self.getControl(200).setImage(path)
            else:
                self.setProperty('qr_visible', 'false')
        except Exception:
            pass


def auth_progress_dialog(heading='', icon=None):
    dialog = AuthProgressDialog('auth_progress.xml', control.addonPath, heading=heading, qr_path=icon or '')
    dialog.show()
    for _ in range(80):
        try:
            if dialog.getProperty('auth_progress_ready') == 'true':
                break
        except Exception:
            pass
        control.sleep(50)
    return dialog


def close_auth_progress_dialog(dialog):
    if not dialog:
        return
    try:
        dialog.is_canceled = True
        dialog.close()
    except Exception:
        pass
