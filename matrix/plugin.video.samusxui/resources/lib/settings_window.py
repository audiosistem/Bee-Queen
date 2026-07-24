# -*- coding: utf-8 -*-
import os
import re
import threading
import xml.etree.ElementTree as ET

import xbmc
import xbmcgui
import xbmcaddon

_ADDON        = xbmcaddon.Addon('plugin.video.samusxui')
_ADDON_PATH   = _ADDON.getAddonInfo('path')
_SETTINGS_XML = os.path.join(_ADDON_PATH, 'resources', 'settings.xml')

_ID_CATEGORIES = 50
_ID_SETTINGS   = 200
_ID_CAT_TITLE  = 300

ACTION_NAV_BACK  = 10
ACTION_PREV_MENU = 92
ACTION_MOVE_UP   = 3
ACTION_MOVE_DOWN = 4


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_settings():
    categories = []
    try:
        root = ET.parse(_SETTINGS_XML).getroot()
        for cat in root.findall('category'):
            settings = []
            for s in cat.findall('setting'):
                sid = s.get('id', '')
                if not sid:
                    continue
                settings.append({
                    'id':      sid,
                    'type':    s.get('type', 'text'),
                    'label':   s.get('label', sid),
                    'default': s.get('default', ''),
                    'values':  s.get('values', ''),
                    'visible': s.get('visible', ''),
                })
            categories.append({
                'label':    cat.get('label', ''),
                'settings': settings,
            })
    except Exception as e:
        xbmc.log(f'[SamusXUI/Settings] parse: {e}', xbmc.LOGWARNING)
    return categories


def _get(sid):
    try:
        return _ADDON.getSetting(sid)
    except Exception:
        return ''


def _set(sid, value):
    try:
        _ADDON.setSetting(sid, str(value))
    except Exception as e:
        xbmc.log(f'[SamusXUI/Settings] set {sid}: {e}', xbmc.LOGWARNING)


# ── tastatura custom ─────────────────────────────────────────────────────────

class CustomKeyboard(xbmcgui.WindowXMLDialog):
    """Tastatură on-screen — suportă input de pe telecomandă ȘI tastatură fizică.

    Strategie tastatură fizică: un control Edit invizibil (id=1299) rămâne
    mereu focusat, capturând caracterele înainte ca keymap-ul global Kodi să le
    intercepteze. Un thread poller sincronizează textul Edit→display. Navigarea
    pe tastatura virtuală se face prin highlight-ul de imagine (id=1298) mutat
    din Python, fără a schimba focus-ul real.
    """

    _KEYMAP = {
        1200:'1', 1201:'2', 1202:'3', 1203:'4', 1204:'5',
        1205:'6', 1206:'7', 1207:'8', 1208:'9', 1209:'0',
        1211:'q', 1212:'w', 1213:'e', 1214:'r', 1215:'t',
        1216:'y', 1217:'u', 1218:'i', 1219:'o', 1220:'p',
        1221:'a', 1222:'s', 1223:'d', 1224:'f', 1225:'g',
        1226:'h', 1227:'j', 1228:'k', 1229:'l',
        1230:'z', 1231:'x', 1232:'c', 1233:'v', 1234:'b',
        1235:'n', 1236:'m',
        1260:'ă', 1261:'î', 1262:'â', 1263:'ș', 1264:'ț',
        1237:'.', 1238:',', 1239:'/', 1240:':', 1241:';',
        1242:"'", 1243:'-', 1244:'_', 1245:'@', 1246:'[', 1247:']',
    }
    _SHIFT_MAP = {
        1200:'!', 1201:'@', 1202:'#', 1203:'$', 1204:'%',
        1205:'^', 1206:'&', 1207:'*', 1208:'(', 1209:')',
        1237:'>', 1238:'<', 1239:'?',
        1242:'"', 1243:'+',
        1246:'{', 1247:'}',
    }
    _BKS    = 1210
    _SHIFT  = 1250
    _SPACE  = 1251
    _DONE   = 1252
    _CANCEL = 1253
    _ENTER_ACTIONS = (13, 66, 135)

    _ID_HIGHLIGHT = 1298
    _ID_EDIT      = 1299

    _ROWS = [
        [1200, 1201, 1202, 1203, 1204, 1205, 1206, 1207, 1208, 1209, 1210],
        [1211, 1212, 1213, 1214, 1215, 1216, 1217, 1218, 1219, 1220],
        [1221, 1222, 1223, 1224, 1225, 1226, 1227, 1228, 1229],
        [1230, 1231, 1232, 1233, 1234, 1235, 1236, 1260, 1261, 1262, 1263, 1264],
        [1237, 1238, 1239, 1240, 1241, 1242, 1243, 1244, 1245, 1246, 1247],
        [1250, 1251, 1252, 1253],
    ]
    _POS = {cid: (r, c)
            for r, row in enumerate(_ROWS)
            for c, cid in enumerate(row)}

    # (left, top, width, height) pentru fiecare buton — folosit de highlight
    _BTN_GEOM = {
        1200:(314,319,112,60), 1201:(432,319,112,60), 1202:(550,319,112,60),
        1203:(668,319,112,60), 1204:(786,319,112,60), 1205:(904,319,112,60),
        1206:(1022,319,112,60),1207:(1140,319,112,60),1208:(1258,319,112,60),
        1209:(1376,319,112,60),1210:(1494,319,112,60),
        1211:(373,387,112,60), 1212:(491,387,112,60), 1213:(609,387,112,60),
        1214:(727,387,112,60), 1215:(845,387,112,60), 1216:(963,387,112,60),
        1217:(1081,387,112,60),1218:(1199,387,112,60),1219:(1317,387,112,60),
        1220:(1435,387,112,60),
        1221:(432,455,112,60), 1222:(550,455,112,60), 1223:(668,455,112,60),
        1224:(786,455,112,60), 1225:(904,455,112,60), 1226:(1022,455,112,60),
        1227:(1140,455,112,60),1228:(1258,455,112,60),1229:(1376,455,112,60),
        1230:(255,523,112,60), 1231:(373,523,112,60), 1232:(491,523,112,60),
        1233:(609,523,112,60), 1234:(727,523,112,60), 1235:(845,523,112,60),
        1236:(963,523,112,60), 1260:(1081,523,112,60),1261:(1199,523,112,60),
        1262:(1317,523,112,60),1263:(1435,523,112,60),1264:(1553,523,112,60),
        1237:(314,591,112,60), 1238:(432,591,112,60), 1239:(550,591,112,60),
        1240:(668,591,112,60), 1241:(786,591,112,60), 1242:(904,591,112,60),
        1243:(1022,591,112,60),1244:(1140,591,112,60),1245:(1258,591,112,60),
        1246:(1376,591,112,60),1247:(1494,591,112,60),
        1250:(381,659,160,60), 1251:(547,659,660,60),
        1252:(1213,659,160,60),1253:(1379,659,160,60),
    }

    def __new__(cls, *a, **kw):
        return super().__new__(cls, 'keyboard.xml', _ADDON_PATH, 'Default', '1080i')

    def __init__(self, *a, **kw):
        super().__init__('keyboard.xml', _ADDON_PATH, 'Default', '1080i')
        self._title  = kw.pop('title', '')
        self._text   = kw.pop('default', '')
        self._shift  = False
        self.result  = None
        self._vcur   = 1211   # butonul virtual curent (highlight)
        self._done   = threading.Event()

    def onInit(self):
        try:
            self.getControl(1010).setLabel(self._title)
        except Exception:
            pass
        # Kodi interpretează numerele din XML ca ID-uri de string localizat →
        # setăm toate etichetele explicit din Python
        for cid, ch in self._KEYMAP.items():
            try:
                self.getControl(cid).setLabel(ch)
            except Exception:
                pass
        try:
            self.getControl(self._BKS).setLabel('DEL')
        except Exception:
            pass
        self._refresh()
        self._apply_shift()
        self._move_highlight(self._vcur)
        try:
            self.getControl(self._ID_EDIT).setText(self._text)
            self.setFocusId(self._ID_EDIT)
        except Exception:
            pass
        # Thread poller: sincronizează textul din Edit → display
        t = threading.Thread(target=self._poll_edit, daemon=True)
        t.start()
        # Edit-ul invizibil poate declanșa tastatura nativă Kodi când primește
        # ENTER/focus. O închidem cât timp tastatura custom este modală.
        threading.Thread(target=self._suppress_native_keyboard, daemon=True).start()

    def _suppress_native_keyboard(self):
        while not self._done.wait(0.12):
            try:
                xbmc.executebuiltin('Dialog.Close(virtualkeyboard, true)')
            except Exception:
                pass

    def _move_highlight(self, btn_id):
        geom = self._BTN_GEOM.get(btn_id)
        if not geom:
            return
        l, t, w, h = geom
        try:
            ctrl = self.getControl(self._ID_HIGHLIGHT)
            ctrl.setPosition(l - 3, t - 3)
            ctrl.setWidth(w + 6)
            ctrl.setHeight(h + 6)
        except Exception:
            pass

    def _poll_edit(self):
        """Sincronizează textul captat de Edit → self._text și display."""
        import time
        while not self._done.wait(0.05):
            try:
                edit_text = self.getControl(self._ID_EDIT).getText()
                if '\n' in edit_text or '\r' in edit_text:
                    edit_text = edit_text.replace('\r', '').replace('\n', '')
                    self.getControl(self._ID_EDIT).setText(edit_text)
                    self.result = edit_text
                    self._done.set()
                    self.close()
                    return
                if edit_text != self._text:
                    self._text = edit_text
                    self._refresh()
            except Exception:
                pass

    def _refresh(self):
        try:
            cursor = '[COLOR FF7B5CF4]|[/COLOR]'
            self.getControl(1000).setLabel(self._text + cursor)
        except Exception:
            pass

    def _sync_to_edit(self):
        try:
            self.getControl(self._ID_EDIT).setText(self._text)
        except Exception:
            pass

    def _apply_shift(self):
        try:
            lbl = '[COLOR FFFFAA00][B]SHIFT[/B][/COLOR]' if self._shift else 'SHIFT'
            self.getControl(self._SHIFT).setLabel(lbl)
        except Exception:
            pass
        for cid, ch in self._KEYMAP.items():
            if self._shift:
                if ch.isalpha():
                    display = ch.upper()
                elif cid in self._SHIFT_MAP:
                    display = self._SHIFT_MAP[cid]
                else:
                    display = ch
            else:
                display = ch
            try:
                self.getControl(cid).setLabel(display)
            except Exception:
                pass

    def _press(self, cid):
        """Procesează apăsarea unui buton (virtual sau click real)."""
        if cid in self._KEYMAP:
            ch = self._KEYMAP[cid]
            if self._shift:
                if ch.isalpha():
                    ch = ch.upper()
                elif cid in self._SHIFT_MAP:
                    ch = self._SHIFT_MAP[cid]
                self._shift = False
                self._apply_shift()
            self._text += ch
            self._sync_to_edit()
            self._refresh()
        elif cid == self._BKS:
            self._text = self._text[:-1]
            self._sync_to_edit()
            self._refresh()
        elif cid == self._SHIFT:
            self._shift = not self._shift
            self._apply_shift()
        elif cid == self._SPACE:
            self._text += ' '
            self._sync_to_edit()
            self._refresh()
        elif cid == self._DONE:
            self.result = self._text
            self._done.set()
            self.close()
        elif cid == self._CANCEL:
            self._done.set()
            self.close()

    def onClick(self, controlId):
        # Click real (mouse sau telecomandă dacă butonul a prins focus accidental)
        if controlId == self._ID_EDIT:
            return  # Edit-ul invizibil primește focus/input fizic; nu îl tratăm ca OK
        self._press(controlId)
        # Refocusăm Edit-ul după click
        try:
            self.setFocusId(self._ID_EDIT)
        except Exception:
            pass

    def onAction(self, action):
        aid = action.getId()
        if aid == 92:  # NAV_BACK (telecomandă) → închide
            self._done.set()
            self.close()
            return
        if aid in (10, 110):  # Backspace fizic sau ACTION_BACKSPACE
            if self._text:
                self._text = self._text[:-1]
                self._sync_to_edit()
                self._refresh()
            else:
                self._done.set()
                self.close()
            return
        if aid in self._ENTER_ACTIONS:
            # ENTER/Return de pe tastatura fizică poate ajunge la Edit-ul invizibil
            # și poate deschide dialogul nativ Kodi. Îl consumăm aici ca OK.
            self.result = self._text
            self._done.set()
            self.close()
            try:
                self.setFocusId(self._ID_EDIT)
            except Exception:
                pass
            return
        if aid == 7:  # SELECT_ITEM (OK telecomandă) → apasă butonul virtual curent
            self._press(self._vcur)
            try:
                self.setFocusId(self._ID_EDIT)
            except Exception:
                pass
            return
        if aid in (1, 2, 3, 4):
            self._nav(aid)

    def _nav(self, direction):
        if self._vcur not in self._POS:
            self._vcur = 1211
        r, c = self._POS[self._vcur]
        row = self._ROWS[r]
        if direction == 1:    # LEFT
            target = row[(c - 1) % len(row)]
        elif direction == 2:  # RIGHT
            target = row[(c + 1) % len(row)]
        elif direction == 3:  # UP
            if r == 0:
                return
            tr = self._ROWS[r - 1]
            frac = c / max(len(row) - 1, 1)
            target = tr[round(frac * (len(tr) - 1))]
        else:                 # DOWN
            if r == len(self._ROWS) - 1:
                return
            tr = self._ROWS[r + 1]
            frac = c / max(len(row) - 1, 1)
            target = tr[round(frac * (len(tr) - 1))]
        self._vcur = target
        self._move_highlight(target)
        try:
            self.setFocusId(self._ID_EDIT)
        except Exception:
            pass


# ── input dialog ─────────────────────────────────────────────────────────────

class InputDialog(xbmcgui.WindowXMLDialog):
    """Dialog custom pentru introducere text, compatibil cu stilul SamusXUI."""

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, 'dialog_input.xml', _ADDON_PATH, 'Default', '1080i')

    def __init__(self, *args, **kwargs):
        super().__init__('dialog_input.xml', _ADDON_PATH, 'Default', '1080i')
        self._title   = kwargs.pop('title', '')
        self._default = kwargs.pop('default', '')
        self.result   = None

    def onInit(self):
        try:
            self.getControl(10).setLabel(self._title)
            self.getControl(100).setText(self._default)
            self.setFocusId(100)
        except Exception as e:
            xbmc.log(f'[SamusXUI/InputDialog] onInit: {e}', xbmc.LOGWARNING)

    def onClick(self, controlId):
        if controlId == 1:
            try:
                self.result = self.getControl(100).getText()
            except Exception:
                self.result = None
            self.close()
        elif controlId == 2:
            self.close()

    def onAction(self, action):
        if action.getId() in (10, 92):
            self.close()


# ── confirm dialog ───────────────────────────────────────────────────────────

class ConfirmDialog(xbmcgui.WindowXMLDialog):
    """Dialog custom "Salvează / Ieși fără salvare". result: 0=save, 1=discard, -1=cancel."""

    ACTION_NAV_BACK  = 10
    ACTION_PREV_MENU = 92

    def __init__(self, *args, **kwargs):
        self._title  = kwargs.pop('title', 'Modificări nesalvate')
        self.result  = -1

    def onInit(self):
        try:
            self.getControl(100).setLabel(self._title)
        except Exception:
            pass

    def onClick(self, controlId):
        if controlId == 1:
            self.result = 0
        elif controlId == 2:
            self.result = 1
        self.close()

    def onAction(self, action):
        if action.getId() in (self.ACTION_NAV_BACK, self.ACTION_PREV_MENU):
            self.close()


# ── window ───────────────────────────────────────────────────────────────────

class SettingsWindow(xbmcgui.WindowXML):

    def __init__(self, *args, **kwargs):
        self._categories = []
        self._cat_idx    = 0
        self._pending    = {}   # sid → new value (nesalvat)
        self._editing    = False  # guard re-entranță onClick (selectItem poate declanșa onClick)

    def _get_val(self, sid):
        return self._pending.get(sid, _get(sid))

    def _is_visible(self, s, all_settings):
        """Evaluează condiția 'visible' a unei setări. Suportă eq(-N,value)."""
        vis = s.get('visible', '')
        if not vis:
            return True
        m = re.match(r'eq\((-\d+),(\S+?)\)', vis.replace(' ', ''))
        if not m:
            return True
        offset   = int(m.group(1))   # ex: -1, -2
        expected = m.group(2)        # ex: "0", "true", "false"
        idx      = all_settings.index(s)
        ref_idx  = idx + offset
        if ref_idx < 0 or ref_idx >= len(all_settings):
            return True
        ref_s   = all_settings[ref_idx]
        ref_val = self._get_val(ref_s['id'])
        # Normalizare: Kodi stochează labelenum ca index ("0"), dar _pending
        # stochează string-ul opțiunii ("TorrServer"). Convertim la index.
        opts = ref_s.get('values', '').split('|') if ref_s.get('values') else []
        if opts and ref_val in opts:
            ref_val = str(opts.index(ref_val))
        return str(ref_val) == str(expected)

    def _visible_settings(self, cat_idx):
        all_s = self._categories[cat_idx]['settings']
        return [s for s in all_s if self._is_visible(s, all_s)]

    def _display_value(self, s):
        val   = self._get_val(s['id'])
        stype = s['type']
        if stype == 'bool':
            return ('[COLOR FF55DD55]ON[/COLOR]'  if val == 'true'
                    else '[COLOR FF555566]OFF[/COLOR]')
        if stype in ('labelenum', 'enum') and s['values']:
            opts = s['values'].split('|')
            try:
                return opts[int(val)]
            except (ValueError, IndexError):
                if val in opts:
                    return val
                return val or s['default']
        return val or s['default']

    def _save_all(self):
        for sid, value in self._pending.items():
            _set(sid, value)
        self._pending.clear()

    def onInit(self):
        self._categories = _parse_settings()
        if not self._categories:
            xbmc.log('[SamusXUI/Settings] EROARE: categorii goale!', xbmc.LOGERROR)
            return
        self._populate_categories()
        self._populate_settings(0)
        self.setFocusId(_ID_CATEGORIES)

    # ── populate ─────────────────────────────────────────────────────────────

    def _populate_categories(self):
        ctrl = self.getControl(_ID_CATEGORIES)
        ctrl.reset()
        for cat in self._categories:
            ctrl.addItem(xbmcgui.ListItem(cat['label']))
        ctrl.selectItem(0)

    def _populate_settings(self, cat_idx, restore_focus=False):
        self._cat_idx = cat_idx
        cat = self._categories[cat_idx]
        try:
            self.getControl(_ID_CAT_TITLE).setLabel(cat['label'])
        except Exception:
            pass
        ctrl = self.getControl(_ID_SETTINGS)
        ctrl.reset()
        for s in self._visible_settings(cat_idx):
            li = xbmcgui.ListItem(s['label'])
            li.setLabel2(self._display_value(s))
            li.setProperty('sid', s['id'])
            ctrl.addItem(li)
        if self._visible_settings(cat_idx):
            ctrl.selectItem(0)
        if restore_focus:
            self.setFocusId(_ID_SETTINGS)

    def _refresh_item(self, pos):
        try:
            ctrl    = self.getControl(_ID_SETTINGS)
            vis     = self._visible_settings(self._cat_idx)
            s       = vis[pos]
            ctrl.getListItem(pos).setLabel2(self._display_value(s))
        except Exception:
            pass

    # ── edit inline (fără dialog nativ pentru enum/bool) ─────────────────────

    def _edit(self, s):
        stype = s['type']
        cur   = self._get_val(s['id'])

        if stype == 'bool':
            self._pending[s['id']] = 'false' if cur == 'true' else 'true'
            return True

        if stype == 'number':
            result = xbmcgui.Dialog().numeric(0, s['label'], cur or s['default'])
            if result:
                self._pending[s['id']] = result
                return True
            return False

        if stype == 'text':
            dlg = CustomKeyboard(title=s['label'], default=cur or s['default'])
            dlg.doModal()
            xbmc.executebuiltin('Dialog.Close(virtualkeyboard)')
            xbmc.sleep(50)
            xbmc.executebuiltin('Dialog.Close(virtualkeyboard)')
            result = dlg.result
            del dlg
            if result is not None and result != '':
                self._pending[s['id']] = result
                return True
            return False

        if stype in ('labelenum', 'enum'):
            opts = s['values'].split('|') if s['values'] else []
            if not opts:
                return False
            try:
                idx = int(cur)
            except (ValueError, TypeError):
                try:
                    idx = opts.index(cur)
                except ValueError:
                    idx = 0
            self._pending[s['id']] = opts[(idx + 1) % len(opts)]
            return True

        return False

    # ── ieșire cu confirmare ──────────────────────────────────────────────────

    def _handle_exit(self):
        if not self._pending:
            self.close()
            return
        n   = len(self._pending)
        dlg = ConfirmDialog(
            'dialog_confirm.xml', _ADDON_PATH, 'Default', '1080i',
            title=f'Setări  —  {n} modificări nesalvate',
        )
        dlg.doModal()
        choice = dlg.result
        del dlg
        if choice == 0:
            self._save_all()
            self.close()
        elif choice == 1:
            self._pending.clear()
            self.close()
        # choice == -1: rămâne în setări

    # ── events ───────────────────────────────────────────────────────────────

    def onAction(self, action):
        aid = action.getId()
        if aid in (ACTION_NAV_BACK, ACTION_PREV_MENU):
            self._handle_exit()
            return
        if self.getFocusId() == _ID_CATEGORIES and aid in (ACTION_MOVE_UP, ACTION_MOVE_DOWN):
            xbmc.sleep(80)
            try:
                idx = self.getControl(_ID_CATEGORIES).getSelectedPosition()
                if idx != self._cat_idx:
                    self._populate_settings(idx)
            except Exception:
                pass

    def onClick(self, controlId):
        if controlId == _ID_CATEGORIES:
            try:
                idx = self.getControl(_ID_CATEGORIES).getSelectedPosition()
                self._populate_settings(idx)
                self.setFocusId(_ID_SETTINGS)
            except Exception:
                pass
        elif controlId == _ID_SETTINGS:
            if self._editing:
                return
            self._editing = True
            try:
                pos = self.getControl(_ID_SETTINGS).getSelectedPosition()
                vis = self._visible_settings(self._cat_idx)
                s   = vis[pos]
                if self._edit(s):
                    new_vis = self._visible_settings(self._cat_idx)
                    if new_vis != vis:
                        self._populate_settings(self._cat_idx, restore_focus=True)
                        # Restaurăm focus pe setarea editată (dacă e încă vizibilă)
                        try:
                            new_pos = next(i for i, x in enumerate(new_vis) if x['id'] == s['id'])
                            self.getControl(_ID_SETTINGS).selectItem(new_pos)
                        except StopIteration:
                            pass
                    else:
                        self._refresh_item(pos)
            except Exception as e:
                xbmc.log(f'[SamusXUI/Settings] onClick: {e}', xbmc.LOGWARNING)
            finally:
                self._editing = False
