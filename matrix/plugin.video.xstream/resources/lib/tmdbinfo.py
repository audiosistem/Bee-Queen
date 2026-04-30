# -*- coding: utf-8 -*-
# Python 3

import xbmc
import time
import xbmcgui

from resources.lib.config import cConfig
from resources.lib.tmdb import cTMDB
from datetime import date, datetime
from urllib.parse import urlencode


def WindowsBoxes(sTitle, sFileName, metaType, year=''):
    try:
        meta = cTMDB().get_meta(metaType, sFileName, tmdb_id=xbmc.getInfoLabel('ListItem.Property(TmdbId)'), year=year, advanced='true')
        try:
            meta['plot'] = str(meta['plot'].encode('latin-1'), 'utf-8')
        except Exception:
            pass
    except Exception:
        print("TMDB - error")
        pass

    if 'tmdb_id' not in meta:
        xbmc.executebuiltin("Notification(TMDB, Kein Eintrag gefunden, 1000, '')")
        return
    if 'premiered' in meta and meta['premiered']:
        releaseDate = datetime(*(time.strptime(meta['premiered'], '%Y-%m-%d')[0:6]))
        meta['releaseDate'] = releaseDate.strftime('%d/%m/%Y')
    else:
        meta['releaseDate'] = '-'
    if 'duration' in meta and meta['duration']:
        duration = meta['duration']
        durationH = duration // 60
        meta['durationH'] = durationH
        meta['durationM'] = '{:02d}'.format(int(duration - 60 * durationH))
    else:
        meta['durationH'] = 0
        meta['durationM'] = 0

    class XMLDialog(xbmcgui.WindowXMLDialog):
        def __init__(self, *args, **kwargs):
            xbmcgui.WindowXMLDialog.__init__(self)
            pass

        def onInit(self):
            self.setProperty('color', cConfig().getSetting('Color'))
            self.poster = 'https://image.tmdb.org/t/p/%s' % cConfig().getSetting('poster_tmdb')
            self.none_poster = 'https://eu.ui-avatars.com/api/?background=000&size=512&name=%s&color=FFF&font-size=0.33'
            if 'trailer' in meta:
                self.setProperty('isTrailer', 'true')
            self.setFocusId(9000)
            if 'credits' in meta and meta['credits']:
                cast = []
                crew = []
                try:
                    data = eval(str(meta['credits'].encode('latin-1'), 'utf-8'))
                except Exception:
                    data = eval(str(meta['credits']))

                listitems = []
                if 'cast' in data and data['cast']:
                    for i in data['cast']:
                        slabel = i['name']
                        slabel2 = i['character']
                        if i['profile_path']:
                            sicon = self.poster + str(i['profile_path'])
                        else:
                            sicon = self.none_poster % slabel
                        sid = i['id']
                        listitem_ = xbmcgui.ListItem(label=slabel, label2=slabel2)
                        listitem_.setProperty('id', str(sid))
                        listitem_.setArt({'icon': sicon})
                        listitems.append(listitem_)
                        cast.append(slabel.encode('ascii', 'ignore'))
                    self.getControl(50).addItems(listitems)

                listitems2 = []
                if 'crew' in data and data['crew']:
                    for i in data['crew']:
                        slabel = i['name']
                        slabel2 = i['job']
                        if i['profile_path']:
                            sicon = self.poster + str(i['profile_path'])
                        else:
                            sicon = self.none_poster % slabel
                        sid = i['id']
                        listitem_ = xbmcgui.ListItem(label=slabel, label2=slabel2)
                        listitem_.setProperty('id', str(sid))
                        listitem_.setArt({'icon': sicon})
                        listitems2.append(listitem_)
                        crew.append(slabel.encode('ascii', 'ignore'))
                    self.getControl(5200).addItems(listitems2)

            meta['title'] = sTitle
            if 'rating' not in meta or meta['rating'] == 0:
                meta['rating'] = '-'
            if 'votes' not in meta or meta['votes'] == '0':
                meta['votes'] = '-'

            for prop in meta:
                try:
                    if isinstance(meta[prop], unicode):
                        self.setProperty(prop, meta[prop].encode('utf-8'))
                    else:
                        self.setProperty(prop, str(meta[prop]))
                except Exception:
                    if isinstance(meta[prop], str):
                        self.setProperty(prop, meta[prop].encode('utf-8'))
                    else:
                        self.setProperty(prop, str(meta[prop]))

        def credit(self, meta='', control=''):
            listitems = []
            if not meta:
                meta = {}
            for i in meta:
                if 'title' in i and i['title']:
                    sTitle = i['title']
                elif 'name' in i and i['name']:
                    sTitle = i['name']
                if i['poster_path']:
                    sThumbnail = self.poster + str(i['poster_path'])
                else:
                    sThumbnail = self.none_poster % sTitle
                listitem_ = xbmcgui.ListItem(label=sTitle)
                listitem_.setArt({'icon': sThumbnail})
                listitems.append(listitem_)
            self.getControl(control).addItems(listitems)

        def onClick(self, controlId):
            if controlId == 11:
                if metaType == 'movie':
                    sUrl = 'movie/%s/videos' % str(self.getProperty('tmdb_id'))
                else:
                    sUrl = 'tv/%s/videos' % str(self.getProperty('tmdb_id'))
                meta = cTMDB().getUrl(sUrl)
                name = []
                url = []
                for result in meta['results']:
                    name.append((result['name']))
                    url.append((result['key']))
                index = xbmcgui.Dialog().select('Trailer/Teaser', name)
                if index > -1:
                    self.close()
                    YT = 'plugin://plugin.video.youtube/play/?video_id=%s' % url[index]
                    return xbmc.executebuiltin('RunPlugin(%s)' % YT)
            elif controlId == 30:
                self.close()
                return
            elif controlId == 50 or controlId == 5200:
                item = self.getControl(controlId).getSelectedItem()
                sid = item.getProperty('id')
                sUrl = 'person/' + str(sid)
                try:
                    meta = cTMDB().getUrl(sUrl, '', "append_to_response=movie_credits,tv_credits")
                    meta_credits = meta['movie_credits']['cast']
                    self.credit(meta_credits, 5215)
                    sTitle = meta['name']
                    if not meta['deathday']:
                        today = date.today()
                        try:
                            birthday = datetime(*(time.strptime(meta['birthday'], '%Y-%m-%d')[0:6]))
                            age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
                            age = '%s Jahre' % age
                        except Exception:
                            age = ''
                    else:
                        age = meta['deathday']
                    self.setProperty('Person_name', sTitle)
                    self.setProperty('Person_birthday', meta['birthday'])
                    self.setProperty('Person_place_of_birth', meta['place_of_birth'])
                    self.setProperty('Person_deathday', str(age))
                    self.setProperty('Person_biography', meta['biography'])
                    self.setFocusId(9000)
                except Exception:
                    return
                self.setProperty('xstream_menu', 'Person')
            elif controlId == 9:
                sid = self.getProperty('tmdb_id')
                if metaType == 'movie':
                    sUrl_simil = 'movie/%s/similar' % str(sid)
                    sUrl_recom = 'movie/%s/recommendations' % str(sid)
                else:
                    sUrl_simil = 'tv/%s/similar' % str(sid)
                    sUrl_recom = 'tv/%s/recommendations' % str(sid)
                try:
                    meta = cTMDB().getUrl(sUrl_simil)
                    meta = meta['results']
                    self.credit(meta, 5205)
                except Exception:
                    pass
                try:
                    meta = cTMDB().getUrl(sUrl_recom)
                    meta = meta['results']
                    self.credit(meta, 5210)
                except Exception:
                    return
            elif controlId == 5215 or controlId == 5205 or controlId == 5210:
                item = self.getControl(controlId).getSelectedItem()
                self.close()
                xbmc.executebuiltin("Container.Update(%s?function=searchTMDB&%s)" % ('plugin://plugin.video.xstream/', urlencode({'searchTitle': item.getLabel()})))
                return

        def onFocus(self, controlId):
            self.controlId = controlId

        def _close_dialog(self):
            self.close()

        def onAction(self, action):
            if action.getId() in (104, 105, 1, 2):
                return
            if action.getId() in (9, 10, 11, 30, 92, 216, 247, 257, 275, 61467, 61448):
                self.close()

# kasi
    path = 'special://home/addons/%s' % cConfig().getAddonInfo('id')   
    wd = XMLDialog('info.xml', path, 'default', '720p')
    wd.doModal()
    del wd
