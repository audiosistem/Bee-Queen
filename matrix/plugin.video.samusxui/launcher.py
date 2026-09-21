# -*- coding: utf-8 -*-
"""Entry point for the custom UI, kept separate from plugin widget calls."""

import sys
import threading
import time

import xbmc


xbmc.log(f'[SamusXUI/launcher] pornit argv={sys.argv[1:]}', xbmc.LOGINFO)


if 'service=true' in sys.argv[1:]:
    import service

    service.main()
    raise SystemExit


import xbmcaddon
import xbmcgui


ADDON_PATH = xbmcaddon.Addon('plugin.video.samusxui').getAddonInfo('path')
_OPEN_PROPERTY = 'samusxui_custom_ui_open'
_CLOSED_PROPERTY = 'samusxui_custom_ui_closed'
_home = xbmcgui.Window(10000)


if (_home.getProperty(_OPEN_PROPERTY) == 'true' and
        xbmc.getCondVisibility('Window.IsVisible(13001)')):
    xbmc.log('[SamusXUI/launcher] interfața este deja deschisă', xbmc.LOGINFO)
    raise SystemExit

if _home.getProperty(_OPEN_PROPERTY) == 'true':
    xbmc.log('[SamusXUI/launcher] curăț indicatorul rămas fără fereastră',
             xbmc.LOGWARNING)
    _home.clearProperty(_OPEN_PROPERTY)


class _Splash(xbmcgui.WindowXML):
    pass


def _modal_active():
    """Kodi refuză ActivateWindow cât timp există un dialog modal. La lansarea
    din lista de addonuri asta e chiar dialogul lui de așteptare pentru listarea
    de plugin, care se ridică DUPĂ ce pluginul a chemat endOfDirectory."""
    return (xbmc.getCondVisibility('System.HasActiveModalDialog') or
            xbmc.getCondVisibility('Window.IsActive(busydialognocancel)') or
            xbmc.getCondVisibility('Window.IsActive(busydialog)'))


def _wait_no_modal(timeout=10.0):
    for _ in range(int(timeout * 10)):
        if not _modal_active():
            return True
        xbmc.sleep(100)
    return False


def _open_modal(win, settle=1.5):
    """Deschide fereastra; întoarce True doar dacă a fost cu adevărat afișată.

    Capcană: când Kodi refuză activarea, `doModal()` NU ridică excepție și NU se
    întoarce — rămâne blocat definitiv, iar procesul scriptului rămâne agățat cu
    indicatorul de „interfață deschisă" pus. Așa arăta „addonul nu pornește în
    interfața custom când îl lansez din My addons": fiecare încercare lăsa în
    urmă un proces blocat, iar următoarea curăța indicatorul și eșua la fel.

    Ferestrele Python primesc id-uri de la 13000 în sus, deci id-ul ferestrei
    curente spune fără ambiguitate dacă activarea a reușit sau am rămas în
    listarea de plugin (10025).
    """
    opened = []

    def _watch():
        for _ in range(int(settle * 10)):
            xbmc.sleep(100)
            if xbmcgui.getCurrentWindowId() >= 13000:
                opened.append(True)
                return
        xbmc.log('[SamusXUI/launcher] activare refuzată — deblochez doModal',
                 xbmc.LOGWARNING)
        try:
            win.close()  # eliberează doModal, altfel firul rămâne blocat
        except Exception:
            pass

    watcher = threading.Thread(target=_watch, daemon=True, name='samusxui-activare')
    watcher.start()
    win.doModal()
    watcher.join(settle + 1)
    return bool(opened)


_splash = None
_home.setProperty(_OPEN_PROPERTY, 'true')
try:
    _wait_no_modal()

    _splash = _Splash('splash.xml', ADDON_PATH, 'Default', '1080i')
    _splash.show()

    from resources.lib.home_window import HomeWindow

    win = HomeWindow('home.xml', ADDON_PATH, 'Default', '1080i')
    _splash.close()
    _splash = None

    # Dialogul de așteptare al listării poate apărea între verificarea de mai
    # sus și doModal — fereastra de cursă e de ordinul milisecundelor, deci nu
    # se închide prin așteptare, ci prin reîncercare.
    for _attempt in range(1, 6):
        _wait_no_modal()
        if _open_modal(win):
            break
        xbmc.log(f'[SamusXUI/launcher] încercarea {_attempt} a eșuat, reiau',
                 xbmc.LOGWARNING)
        xbmc.sleep(500)
    else:
        xbmc.log('[SamusXUI/launcher] nu am putut deschide interfața după 5 încercări',
                 xbmc.LOGERROR)
    del win
finally:
    if _splash is not None:
        try:
            _splash.close()
        except Exception:
            pass
    _home.clearProperty(_OPEN_PROPERTY)
    # Marcăm închiderea: rădăcina pluginului folosește ștampila ca răcire, ca
    # reinterogarea widgeturilor la revenirea în meniu să nu redeschidă interfața.
    _home.setProperty(_CLOSED_PROPERTY, str(time.time()))

xbmc.sleep(300)
xbmc.executebuiltin('ActivateWindow(home)')
