# -*- coding: utf-8 -*-
"""Meniu „Continuă vizionarea" — filme și episoade neterminate."""

import sys
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode
from resources.lib import db
from resources.lib.utils import get_icon_path

handle = int(sys.argv[1])
IMG    = 'https://image.tmdb.org/t/p/w500'


def show_continue_watching():
    items = db.history_get_all(limit=50)
    if not items:
        xbmcgui.Dialog().notification('Samus', 'Niciun titlu neterminat.', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(handle)
        return

    xbmcplugin.setPluginCategory(handle, 'Continuă')

    for h in items:
        tmdb_id    = h['tmdb_id']
        media_type = h['media_type']
        title      = h['title'] or str(tmdb_id)
        poster     = IMG + h['poster'] if h.get('poster') else get_icon_path('movies')
        percent    = int(h.get('percent') or 0)
        season     = h.get('season')
        episode    = h.get('episode')

        if media_type == 'tv' and season is not None and episode is not None:
            label = f"{title}  S{season:02d}E{episode:02d}  ({percent}%)"
            url   = f"{sys.argv[0]}?{urlencode({'action': 'play_episode', 'tv_id': tmdb_id, 'season': season, 'episode': episode})}"
            is_folder = False
        else:
            label = f"{title}  ({percent}%)"
            url   = f"{sys.argv[0]}?{urlencode({'action': 'play_movie', 'tmdb_id': tmdb_id})}"
            is_folder = False

        li = xbmcgui.ListItem(label=label)
        li.setProperty('IsPlayable', 'true')
        li.setArt({'thumb': poster, 'poster': poster})
        if h.get('plot'):
            info = li.getVideoInfoTag()
            info.setPlot(h['plot'])
            info.setTitle(title)
        li.addContextMenuItems([
            ('Șterge din istoric',
             f"RunPlugin({sys.argv[0]}?action=history_remove&tmdb_id={tmdb_id}&media_type={media_type})"),
        ])
        xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=is_folder)

    xbmcplugin.endOfDirectory(handle)
