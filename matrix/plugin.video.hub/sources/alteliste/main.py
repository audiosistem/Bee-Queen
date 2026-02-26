import sys
import xbmcgui
import xbmcplugin
import requests
import re
from urllib.parse import parse_qsl, urlencode
import gzip
import json
import xbmc
from . import ro_md, iptv_org, world, tvrplus, freetv, iptv_zilla

xbmc.log("alteliste/main.py: Script started", level=xbmc.LOGINFO)

_BASE_URL = 'plugin://plugin.video.hub/'
_HANDLE = int(sys.argv[1])

def add_dir(name, params, icon=None):
    """Add a directory item."""
    url = f'{_BASE_URL}?{urlencode(params)}'
    list_item = xbmcgui.ListItem(label=name)
    if icon:
        list_item.setArt({'thumb': icon, 'icon': icon, 'fanart': icon})
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=list_item, isFolder=True)

def add_item(name, params, thumb=None, fanart=None, plot=None):
    """Add a playable item to the directory."""
    url = f'{_BASE_URL}?{urlencode(params)}'
    list_item = xbmcgui.ListItem(label=name)
    info_labels = {'Title': name}
    if plot:
        info_labels['plot'] = plot
    list_item.setInfo(type='Video', infoLabels=info_labels)
    list_item.setProperty('IsPlayable', 'true')
    if thumb:
        list_item.setArt({'thumb': thumb, 'icon': thumb, 'fanart': fanart})
    xbmcplugin.addDirectoryItem(handle=_HANDLE, url=url, listitem=list_item, isFolder=False)

def end_of_directory():
    """End of directory listing."""
    xbmcplugin.endOfDirectory(_HANDLE)

def world_router(params):
    """Router for world channels."""
    world.router(params)

def tvrplus_router(params):
    """Router for TVR+ channels."""
    tvrplus.router(params)

def freetv_router(params):
    """Router for Free TV channels."""
    freetv.router(params)

def iptv_zilla_router(params):
    """Router for IPTV Zilla channels."""
    iptv_zilla.router(params)

def router(params):
    """Router function"""
    mode = params.get('mode')

    if mode is None:
        add_dir("RO-MD List", {'action': 'alteliste', 'mode': 'ro-md'})
        add_dir("IPTV-ORG", {'action': 'alteliste', 'mode': 'iptv-org'})
        add_dir("World", {'action': 'alteliste', 'mode': 'world'})
        add_dir("TVR Plus", {'action': 'alteliste', 'mode': 'tvrplus'})
        add_dir("Free TV", {'action': 'alteliste', 'mode': 'freetv'})
        add_dir("IPTV Zilla", {'action': 'alteliste', 'mode': 'iptv_zilla'})
        end_of_directory()
    elif mode == 'ro-md':
        ro_md.list_channels(params)
    elif mode == 'iptv-org':
        iptv_org.router(params)
    elif mode == 'world':
        world_router(params)
    elif mode == 'tvrplus':
        tvrplus_router(params)
    elif mode == 'freetv':
        freetv_router(params)
    elif mode == 'iptv_zilla':
        iptv_zilla_router(params)
    elif mode == 'freetv_list_channels':
        freetv.list_channels(params)
    elif mode == 'freetv_play':
        freetv.play_channel(params)
    elif mode == 'iptv_zilla_list_channels':
        iptv_zilla.list_channels(params)
    elif mode == 'iptv_zilla_play':
        iptv_zilla.play_channel(params)
    elif mode == 'tvrplus_play':
        tvrplus.play_channel(params)
    elif mode == 'play':
        provider = params.get('provider')
        if provider == 'ro_md':
            ro_md.play_channel(params)
        elif provider == 'iptv_org':
            iptv_org.play_channel(params)
        elif provider == 'world':
            world.play_channel(params)

if __name__ == '__main__':
    router(dict(parse_qsl(sys.argv[2][1:])))