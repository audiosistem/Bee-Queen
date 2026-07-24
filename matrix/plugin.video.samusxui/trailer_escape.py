# -*- coding: utf-8 -*-
"""Stop a background trailer on Escape without changing normal navigation."""
import xbmc
import xbmcgui


window = xbmcgui.Window(10000)
trailer_properties = ('widget_trailer_playing', 'myprime_trailer_playing')

if any(window.getProperty(name) for name in trailer_properties):
    xbmc.Player().stop()
    for name in trailer_properties:
        window.clearProperty(name)
else:
    xbmc.executebuiltin('Action(Back)')
