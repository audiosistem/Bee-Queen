# -*- coding: utf-8 -*-
import json
import sys
import threading

from kodi_six import xbmcgui
from six.moves import urllib_parse

from resources.lib.modules import control


class SourceResultsDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args)
        self._items = kwargs.get('items') or []
        self._meta = kwargs.get('meta') or {}
        self._title = kwargs.get('title') or ''
        self._downloads = kwargs.get('downloads') or False
        self._download_name = kwargs.get('download_name') or self._title
        self._preselect = int(kwargs.get('preselect') or 0)
        self._on_select = kwargs.get('on_select')
        self._busy = False
        self._play_gen = 0
        self._abort = False
        self._worker = None
        self._reopen = False
        self._stopped_event = threading.Event()
        self._in_init = False
        self.selected = None

    def onInit(self):
        # setFocus from the player thread re-enters this and overflows the stack.
        if self._in_init:
            return
        self._in_init = True
        try:
            self._on_init()
        finally:
            self._in_init = False

    def _on_init(self):
        control.idle()
        poster = self._meta.get('poster') or control.addonPoster()
        fanart = ''
        if control.setting('show.fanart') == 'true':
            fanart = self._meta.get('fanart') or ''
        clearlogo = _clearlogo(self._meta)
        self.setProperty('poster', poster or '')
        self.setProperty('fanart', fanart or '')
        self.setProperty('clearlogo', clearlogo)
        self.setProperty('heading', _results_heading(self._meta, self._title))
        self.setProperty('episode_label', _episode_label(self._meta))
        self.setProperty('total_results', str(len(self._items)))
        control.window.setProperty('gratisred.results_hold', 'true')
        control.window.clearProperty('gratisred.playback_fullscreen')
        self.clearProperty('gratisred.playback_fullscreen')
        listitems = []
        for entry in self._items:
            label = str(entry.get('label') or '')
            parts = label.split('[CR]')
            line1 = _plain_line(parts[0])
            line2 = _plain_line(parts[1]) if len(parts) > 1 else ''
            line3 = _plain_line(parts[2]) if len(parts) > 2 else ''
            try:
                item = control.item(label=line1, offscreen=True)
            except Exception:
                item = control.item(label=line1)
            item.setProperty('line2', line2)
            item.setProperty('line3', line3)
            listitems.append(item)
        try:
            self.getControl(2000).reset()
            self.getControl(2000).addItems(listitems)
            if 0 < self._preselect < len(listitems):
                self.getControl(2000).selectItem(self._preselect)
            self.setFocusId(2000)
        except Exception:
            from resources.lib.modules import log_utils
            log_utils.log('source results list', 1)

    def close(self):
        try:
            control.window.clearProperty('gratisred.results_hold')
            control.window.clearProperty('gratisred.playback_fullscreen')
        except Exception:
            pass
        xbmcgui.WindowXMLDialog.close(self)

    def onClick(self, controlId):
        if controlId == 2000:
            self._choose()

    def onAction(self, action):
        action_id = action.getId() if not isinstance(action, int) else action
        back = action_id in (9, 10, 92, 216)
        # The picture hides this window. Until then a file can already count as
        # playing, and Back has to leave. Once the picture is up, Stop and Back
        # belong to the player. A second stop from here crashes Kodi.
        if action_id == 13:
            # Stop. The play thread can still be closing the file. The next
            # choice has to resolve without waiting for that.
            self._busy = False
            self._stopped_event.set()
        if self.getProperty('gratisred.playback_fullscreen') == 'true' and control.condVisibility('Player.HasVideo'):
            # The results dialog stays open above the video, so it receives the
            # key before the fullscreen keymap. Hand it on: the on-screen
            # controls while they are open, otherwise the player's own seek.
            # The window stays open so an early stop returns here.
            osd_open = control.condVisibility('Window.IsVisible(videoosd)')
            if action_id in (9, 10, 92, 216):
                if osd_open:
                    control.execute('Dialog.Close(videoosd)')
                    return
                self._busy = False
                self._stopped_event.set()
                control.execute('PlayerControl(Stop)')
                return
            if osd_open:
                osd_action = {
                    1: 'Left',
                    2: 'Right',
                    3: 'Up',
                    4: 'Down',
                    7: 'Select',
                }.get(action_id)
                if osd_action:
                    control.execute('Action(%s,videoosd)' % osd_action)
                    return
            if action_id in (7, 24, 100, 117, 123, 163, 243, 401):
                if not osd_open:
                    control.execute('ActivateWindow(videoosd)')
                return
            # These already reached the player. Sending them again would seek twice.
            if action_id in (20, 21, 22, 23, 76, 97, 98):
                return
            # Arrows arrive as directions. The player keymap uses a step for
            # left and right, and a chapter or large jump for up and down.
            # Action() with no window lets the player handle it. The step
            # actions come back through here and stop at the check above.
            seek_action = {
                1: 'StepBack',
                2: 'StepForward',
                3: 'ChapterOrBigStepForward',
                4: 'ChapterOrBigStepBack',
            }.get(action_id)
            if seek_action:
                control.execute('Action(%s)' % seek_action)
                return
            if action_id == 13:
                return
            # Pause and play already reach the player. A second play toggles
            # them straight back, so the picture only blips.
            if action_id in (12, 79, 229):
                return
            builtin = {
                77: 'PlayerControl(Forward)',
                78: 'PlayerControl(Rewind)',
            }.get(action_id)
            if builtin:
                control.execute(builtin)
            return
        if not control.condVisibility('Player.HasVideo'):
            try:
                if self.getProperty('gratisred.playback_fullscreen') == 'true':
                    self.clearProperty('gratisred.playback_fullscreen')
            except Exception:
                pass
        if back:
            self.selected = None
            self._abort = True
            self._stop_resolve()
            self.close()
            return
        if action_id in (7, 100):
            try:
                focused = self.getFocusId()
            except Exception:
                focused = 0
            if focused == 2000:
                self._choose()
            return
        if action_id == 117:
            self._context_menu()

    def _stop_resolve(self):
        dialog = control.progressDialogBG if control.setting('progress.dialog') != '0' else control.progressDialog
        try:
            dialog.close()
        except Exception:
            pass
        # The play thread stops the file when it sees _abort. Stopping here as
        # well starts a second CloseFile. Only a file left behind after that
        # thread has finished is stopped from here.
        worker = self._worker
        if worker is not None and worker.is_alive():
            return
        try:
            if control.condVisibility('Player.HasVideo'):
                control.player.stop()
        except Exception:
            pass

    def _choose(self):
        if self._busy:
            return
        try:
            pos = self.getControl(2000).getSelectedPosition()
        except Exception:
            pos = -1
        if pos is None or pos < 0:
            return
        if not self._on_select:
            self.selected = pos
            self.close()
            return
        self._play_gen = getattr(self, '_play_gen', 0) + 1
        play_gen = self._play_gen
        self._busy = True
        self._abort = False
        self._reopen = False
        self._stopped_event = threading.Event()
        try:
            control.window.clearProperty('gratisred.playback_fullscreen')
            self.clearProperty('gratisred.playback_fullscreen')
        except Exception:
            pass

        def _started():
            # Stay open. Closing this window makes stop step back to the movie
            # list until a new one can open. The skin reads this window's own
            # property. The home-window copy does not hide these controls.
            self.selected = pos
            try:
                if not control.condVisibility('Window.IsActive(fullscreenvideo)'):
                    control.execute('ActivateWindow(fullscreenvideo)')
            except Exception:
                pass
            try:
                self.setProperty('gratisred.playback_fullscreen', 'true')
            except Exception:
                pass

        def _stopped(early):
            # Called only after onPlayBackStopped has returned. setFocus from
            # here, or Action(Back) during CloseFile, crashes Kodi.
            # Unlock before any dialog call. clearProperty on this window from
            # the play thread can sit until the dialog closes, and Enter does
            # nothing for that whole time. A newer choice owns the list.
            if play_gen != self._play_gen:
                return
            self._busy = False
            self._stopped_event.set()
            try:
                control.window.clearProperty('gratisred.playback_fullscreen')
            except Exception:
                pass
            if early:
                return
            self.selected = pos
            try:
                self.clearProperty('gratisred.playback_fullscreen')
                self.close()
            except Exception:
                pass

        worker_box = {}

        def _work():
            try:
                self._on_select(pos, _started, lambda: self._abort, _stopped)
            except Exception:
                from resources.lib.modules import log_utils
                log_utils.log('source results play', 1)
            finally:
                if self._worker is worker_box.get('thread'):
                    self._busy = False
                self._stopped_event.set()

        from resources.lib.modules import workers
        thread = workers.Thread(_work)
        worker_box['thread'] = thread
        self._worker = thread
        thread.start()

    def _selected_position(self):
        try:
            pos = self.getControl(2000).getSelectedPosition()
        except Exception:
            return -1
        if pos is None or pos < 0 or pos >= len(self._items):
            return -1
        return pos

    def _context_menu(self):
        if self._busy:
            return
        pos = self._selected_position()
        if pos < 0:
            return
        choices = []
        actions = []
        if self._downloads:
            choices.append('[B]Download[/B]')
            actions.append('download')
        choices.append('[B]Play[/B]')
        actions.append('play')
        choices.append('Add to favourites')
        actions.append('favourite')
        picked = control.contextmenuDialog(choices)
        if picked is None or picked < 0 or picked >= len(actions):
            return
        action = actions[picked]
        if action == 'download':
            self._download()
        elif action == 'play':
            self._choose()
        else:
            self._add_favourite(pos)

    def _source_plugin_url(self, pos):
        source = urllib_parse.quote_plus(json.dumps([self._items[pos]]))
        title = urllib_parse.quote_plus(self._title or self._download_name)
        return '%s?action=play_item&title=%s&source=%s' % (sys.argv[0], title, source)

    def _add_favourite(self, pos):
        label = _plain_line(str(self._items[pos].get('label') or '').split('[CR]')[0]) or self._download_name
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'Favourites.AddFavourite',
            'params': {
                'title': label,
                'type': 'media',
                'path': self._source_plugin_url(pos),
                'thumbnail': self.getProperty('poster') or '',
            },
        }
        try:
            from kodi_six import xbmc
            xbmc.executeJSONRPC(json.dumps(payload))
            control.infoDialog('Added to favourites', sound=False)
        except Exception:
            from resources.lib.modules import log_utils
            log_utils.log('source results favourite', 1)

    def _download(self):
        pos = self._selected_position()
        if pos < 0:
            return
        source = urllib_parse.quote_plus(json.dumps([self._items[pos]]))
        name = urllib_parse.quote_plus(self._download_name)
        image = urllib_parse.quote_plus(self.getProperty('poster') or '')
        control.execute('RunPlugin(%s?action=download&name=%s&image=%s&source=%s)' % (sys.argv[0], name, image, source))


def _plain_line(text):
    text = str(text or '')
    for tag in ('[UPPERCASE]', '[/UPPERCASE]', '[LOWERCASE]', '[/LOWERCASE]', '[CAPITALIZE]', '[/CAPITALIZE]'):
        text = text.replace(tag, '')
    return ' '.join(text.split())


def _clearlogo(meta):
    logo = (meta or {}).get('clearlogo') or ''
    if str(logo) in ('', '0', 'false', 'None'):
        logo = ''
    if logo:
        return logo
    for label in (
        'ListItem.Art(clearlogo)',
        'Container.ListItem.Art(clearlogo)',
        'ListItem.Art(tvshow.clearlogo)',
        'Container.ListItem.Art(tvshow.clearlogo)',
    ):
        try:
            value = control.infoLabel(label) or ''
        except Exception:
            value = ''
        if value and value not in ('0', 'false', 'None'):
            return value
    return ''


def _episode_label(meta):
    meta = meta or {}
    if meta.get('season') in (None, '') or meta.get('episode') in (None, ''):
        return ''
    if meta.get('mediatype') == 'season':
        return ''
    try:
        label = 'S%02dE%02d' % (int(meta['season']), int(meta['episode']))
    except Exception:
        return ''
    show = str(meta.get('tvshowtitle') or '').strip()
    name = str(meta.get('title') or meta.get('label') or '').strip()
    if name and show and name.lower() == show.lower():
        name = ''
    if name:
        label = '%s - %s' % (label, name)
    return label


def _results_heading(meta, title):
    meta = meta or {}
    name = meta.get('tvshowtitle') or meta.get('title') or title or ''
    name = str(name).strip()
    year = meta.get('year')
    if year and name and str(year) not in name:
        name = '%s (%s)' % (name, year)
    return name


def _download_name(meta, title):
    meta = meta or {}
    try:
        if meta.get('tvshowtitle') not in (None, '') and meta.get('season') not in (None, '') and meta.get('episode') not in (None, ''):
            return '%s S%02dE%02d' % (meta.get('tvshowtitle') or title, int(meta['season']), int(meta['episode']))
    except Exception:
        pass
    name = meta.get('title') or title or ''
    year = meta.get('year')
    if year and name and str(year) not in str(name):
        return '%s (%s)' % (name, year)
    return str(name or title or '')


def choose_source(items, meta, title, preselect=0, on_select=None):
    downloads = control.setting('downloads') == 'true' and not (control.setting('movie.download.path') == '' or control.setting('tv.download.path') == '')
    dialog = SourceResultsDialog(
        'sources_results.xml', control.addonPath, 'Default', '1080i',
        items=items, meta=meta or {}, title=title or '',
        downloads=downloads, download_name=_download_name(meta, title),
        preselect=preselect, on_select=on_select)
    dialog.doModal()
    worker = dialog._worker
    # Picture started: dialog is closed, playback is still running. Wait for the
    # stop decision, then return before scrobble so an early stop can reopen.
    if worker is not None and dialog.selected is not None:
        dialog._stopped_event.wait()
    selected = dialog.selected
    reopen = bool(dialog._reopen)
    if worker is not None and not reopen:
        worker.join()
        worker = None
    lingering = worker
    del dialog
    return selected, reopen, lingering
