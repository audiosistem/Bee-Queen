# -*- coding: utf-8 -*-

import sys
import xbmc
import xbmcgui
import xbmcplugin
from urllib.parse import quote
from . import db

IMG_BASE = 'https://image.tmdb.org/t/p/w500'


def add_to_favorites(tmdb_id, media_type, title='', year='', poster='', plot=''):
    if db.add_favorite(tmdb_id, media_type, title, year, poster, plot):
        xbmcgui.Dialog().notification(
            'Samus', f'"{title}" adăugat la favorite',
            xbmcgui.NOTIFICATION_INFO, 3000
        )
    else:
        xbmcgui.Dialog().notification(
            'Samus', 'Deja în favorite sau eroare',
            xbmcgui.NOTIFICATION_WARNING, 3000
        )


def remove_from_favorites(tmdb_id, media_type, title=''):
    if db.remove_favorite(tmdb_id, media_type):
        xbmcgui.Dialog().notification(
            'Samus', f'"{title}" eliminat din favorite',
            xbmcgui.NOTIFICATION_INFO, 3000
        )
        xbmc.executebuiltin('Container.Refresh')
    else:
        xbmcgui.Dialog().notification(
            'Samus', 'Eroare la eliminare',
            xbmcgui.NOTIFICATION_ERROR, 3000
        )


def show_favorites(handle, media_type=None):
    xbmcplugin.setPluginCategory(handle, 'Favorite')
    items = db.get_favorites(media_type)

    if not items:
        xbmcgui.Dialog().notification('Samus', 'Lista de favorite este goală', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(handle)
        return

    content = 'movies' if media_type == 'movie' else 'tvshows' if media_type == 'tvshow' else 'videos'
    xbmcplugin.setContent(handle, content)

    for item in items:
        label = item['title'] or f"TMDb #{item['tmdb_id']}"
        if item['year']:
            label += f" ({item['year']})"

        li = xbmcgui.ListItem(label=label)
        poster_url = IMG_BASE + item['poster'] if item['poster'] else ''
        li.setArt({'thumb': poster_url, 'icon': poster_url, 'poster': poster_url})
        if item.get('plot'):
            info = li.getVideoInfoTag()
            info.setPlot(item['plot'])
            info.setTitle(item['title'] or label)
            if item['year']:
                try:
                    info.setYear(int(item['year']))
                except ValueError:
                    pass

        # Context menu: remove
        cm_remove = (
            'Elimină din favorite',
            f"RunPlugin({sys.argv[0]}?action=remove_favorite"
            f"&tmdb_id={item['tmdb_id']}&media_type={item['media_type']}"
            f"&title={quote(item['title'])})"
        )

        if item['media_type'] == 'movie':
            li.setProperty('IsPlayable', 'true')
            li.addContextMenuItems([cm_remove])
            url = f"{sys.argv[0]}?action=play_movie&tmdb_id={item['tmdb_id']}"
            xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=False)
        else:
            li.addContextMenuItems([cm_remove])
            url = f"{sys.argv[0]}?action=tv_details&id={item['tmdb_id']}"
            xbmcplugin.addDirectoryItem(handle, url=url, listitem=li, isFolder=True)

    xbmcplugin.endOfDirectory(handle)
