# -*- coding: utf-8 -*-
try:
    import urllib2
    import urllib
    import HTMLParser as htmlparser
    py3 = False
except:
    py3 = True
    import urllib.request as urllib2
    import urllib.parse as urllib
    import html.parser as htmlparser
from resources.lib import requests
import re
import socket
import datetime
import time
import sys
import os
import json

import xbmcplugin
import xbmcgui
import xbmc
import xbmcaddon
import xbmcvfs

try: from sqlite3 import dbapi2 as database
except: from pysqlite2 import dbapi2 as database

__settings__ = xbmcaddon.Addon()
__language__ = __settings__.getLocalizedString
__scriptname__ = __settings__.getAddonInfo('name')
ROOT = __settings__.getAddonInfo('path')
USERAGENT = "Mozilla/5.0 (Windows NT 6.1; rv:5.0) Gecko/20100101 Firefox/5.0"
__addonpath__ = __settings__.getAddonInfo('path')
icon = os.path.join(__addonpath__, 'icon.png')
__version__ = __settings__.getAddonInfo('version')
__plugin__ = __scriptname__ + " v." + __version__
if py3: dataPath = xbmcvfs.translatePath(__settings__.getAddonInfo("profile"))
else: dataPath = xbmc.translatePath(__settings__.getAddonInfo("profile")).decode("utf-8")
addonCache = os.path.join(dataPath,'cache.db')
media = sys.modules["__main__"].__media__
search_icon = os.path.join(media,'search.png')
next_icon = os.path.join(media,'next.png')


def md5(string):
    try:
        from hashlib import md5
    except ImportError:
        from md5 import md5
    hasher = hashlib.md5()
    try:
        hasher.update(string)
    except:
        hasher.update(string.encode('utf-8', 'ignore'))
    return hasher.hexdigest()


def log(msg):
    loginfo = xbmc.LOGINFO if py3 else xbmc.LOGNOTICE
    try:
        xbmc.log("### [%s]: %s" % (__plugin__,msg,), level=loginfo )
    except UnicodeEncodeError:
        xbmc.log("### [%s]: %s" % (__plugin__,msg.encode("utf-8", "ignore"),), level=loginfo )
    except:
        xbmc.log("### [%s]: %s" % (__plugin__,'ERROR LOG',), level=loginfo )


def get_params():
    param = []
    paramstring = sys.argv[2]
    if len(paramstring) >= 2:
        params = sys.argv[2]
        cleanedparams = params.replace('?', '')
        if (params[len(params) - 1] == '/'):
            params = params[0:len(params) - 2]
        pairsofparams = cleanedparams.split('&')
        param = {}
        for i in range(len(pairsofparams)):
            splitparams = {}
            splitparams = pairsofparams[i].split('=')
            if (len(splitparams)) == 2:
                param[splitparams[0]] = splitparams[1]
    return param


def get_url(cookie, url):
    headers = {'User-Agent': 'XBMC',
               'Content-Type': 'application/x-www-form-urlencoded',
               'Cookie': cookie}
    try:
        conn = urllib2.urlopen(urllib2.Request(url, urllib.urlencode({}), headers))
        array = conn.read()
        # debug('[get_url]: arr"'+str(array)+'"')
        if array == '':
            # debug('[get_url][2]: arr=""')
            array = True
        return array
    except urllib2.HTTPError as e:
        # debug('[get_url]: HTTPError, e.code='+str(e.code))
        if e.code == 401:
            debug('[get_url]: Denied! Wrong login or api is broken!')
            return
        elif e.code in [503]:
            debug('[get_url]: Denied, HTTP Error, e.code=' + str(e.code))
            return
        else:
            showMessage('HTTP Error', str(e.code))
            debug('[get_url]: HTTP Error, e.code=' + str(e.code))
            xbmc.sleep(2000)
            return
    except:
        return False

def get_redirect(url):
    try:
        a = urllib2.urlopen(url)
        return a.geturl()
    except: return url
    

def fetchData(url, referer=None, data={}, redirect=None, rtype=None, headers={}, cookies={}, timeout=None, api=None):
    from resources.lib.requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    timeout = timeout if timeout else 10
    headers = headers
    if referer != None:
        headers['Referer'] = referer
    headers['User-Agent'] = USERAGENT
    if api: headers = {'User-Agent' : USERAGENT}
    try:
        if data: get = requests.post(url, headers=headers, data=data, verify=False, timeout=timeout)
        else: get = requests.get(url, headers=headers, verify=False, timeout=timeout, cookies=cookies)
        if redirect: result = get.url
        else: 
            if rtype: 
                if rtype == 'json': result = get.json()
                else:
                    if py3: result = get.text
                    else:
                        try: result = get.text.decode('utf-8')
                        except: result = get.text.decode('latin-1')
            else:
                try: result = get.content.decode('utf-8')
                except: result = get.content.decode('latin-1')
        return (result)
    except BaseException as e:
        log("fetchData(%s) exception: %s" % (url,e))
        return

def striphtml(data):
        p = re.compile('<.*?>')
        cleanp = re.sub(p, '', data)
        return cleanp

def stripdata(data):
    p = re.compile('\[.*?\]')
    cleanp = re.sub(p, '', data)
    return cleanp

def unquote(string, ret=None):
    try:
        return urllib.unquote_plus(string)
    except:
        if ret:
            return ret
        else:
            return string
        
def quote(string, ret=None):
    try:
        return urllib.quote_plus(string)
    except:
        if ret:
            return ret
        else:
            return string


def create_tables():
    try:
        if xbmcvfs.exists(dataPath) == 0: xbmcvfs.mkdir(dataPath)
    except BaseException as e: log(u"localdb.create_tables makedir ##Error: %s" % str(e))
    try:
        dbcon = database.connect(addonCache)
        dbcur = dbcon.cursor()
        dbcur.execute("CREATE TABLE IF NOT EXISTS watched (""title TEXT, ""label TEXT, ""overlay TEXT, ""UNIQUE(title)"");")
        dbcur.execute("CREATE TABLE IF NOT EXISTS favorites (""url TEXT, ""title TEXT, ""info TEXT, ""UNIQUE(url)"");")
        dbcur.execute("CREATE TABLE IF NOT EXISTS search (""search TEXT"");")
        dbcon.commit()
    except BaseException as e: log(u"localdb.create_tables ##Error: %s" % str(e))

def get_watched(title):
    try:
        dbcon = database.connect(addonCache)
        dbcur = dbcon.cursor()
        dbcur.execute("SELECT overlay FROM watched WHERE title = '%s'" % (title))
        found = dbcur.fetchone()
        return True if found else False
    except BaseException as e: log(u"localdb.get_watched ##Error: %s" % str(e))
    
def list_watched():
    try:
        dbcon = database.connect(addonCache)
        dbcur = dbcon.cursor()
        dbcur.execute("SELECT * FROM watched")
        found = dbcur.fetchall()
        return found
    except BaseException as e: log(u"localdb.list_watched ##Error: %s" % str(e))

def save_watched(title, info, norefresh=None):
    try:
        overlay = '7'
        label = get_time()
        dbcon = database.connect(addonCache)
        dbcon.text_factory = str
        dbcur = dbcon.cursor()
        dbcur.execute("DELETE FROM watched WHERE title = '%s'" % (title))
        dbcur.execute("INSERT INTO watched Values (?, ?, ?)", (title, str(info), overlay))
        dbcur.execute("VACUUM")
        dbcon.commit()
        if not norefresh:
            xbmc.executebuiltin("Container.Refresh")
    except BaseException as e: log(u"localdb.save_watched ##Error: %s" % str(e))

def update_watched(title, label, overlay):
    try:
        dbcon = database.connect(addonCache)
        dbcon.text_factory = str
        dbcon.execute("UPDATE watched SET overlay = '%s' WHERE title = '%s'" % (overlay, title))
        dbcon.commit()
    except BaseException as e: log(u"localdb.update_watched ##Error: %s" % str(e))

def delete_watched(url=None):
    try:
        dbcon = database.connect(addonCache)
        dbcur = dbcon.cursor()
        if url: dbcur.execute("DELETE FROM watched WHERE title = '%s'" % (url))
        else: dbcur.execute("DELETE FROM watched")
        dbcur.execute("VACUUM")
        dbcon.commit()
        xbmc.executebuiltin("Container.Refresh")
    except BaseException as e: log(u"localdb.delete_watched ##Error: %s" % str(e))
    
def save_fav(title, url, info, norefresh=None):
    try:
        dbcon = database.connect(addonCache)
        dbcon.text_factory = lambda x: unicode(x, "utf-8", "ignore")
        dbcur = dbcon.cursor()
        dbcur.execute("DELETE FROM favorites WHERE url = '%s'" % (url))
        dbcur.execute("INSERT INTO favorites Values (?, ?, ?)", (url, title, str(info)))
        dbcur.execute("VACUUM")
        dbcon.commit()
        xbmc.executebuiltin('Notification(%s,%s)' % (__scriptname__, 'Salvat în Favorite'))
        if not norefresh:
            xbmc.executebuiltin("Container.Refresh")
    except BaseException as e: log("localdb.save_fav ##Error: %s" % str(e))

def get_fav(url=None):
    try:
        dbcon = database.connect(addonCache)
        dbcur = dbcon.cursor()
        if url:
            dbcur.execute("SELECT title FROM favorites WHERE url = '%s'" % (url))
        else:
            dbcur.execute("SELECT * FROM favorites")
        found = dbcur.fetchall()
        return found
    except BaseException as e: log(u"localdb.get_fav ##Error: %s" % str(e))

def del_fav(url, norefresh=None):
    try:
        dbcon = database.connect(addonCache)
        dbcur = dbcon.cursor()
        dbcur.execute("DELETE FROM favorites WHERE url = '%s'" % (url))
        dbcur.execute("VACUUM")
        dbcon.commit()
        xbmc.executebuiltin('Notification(%s,%s)' % (__scriptname__, 'Șters din favorite'))
        if not norefresh:
            xbmc.executebuiltin("Container.Refresh")
    except BaseException as e: log(u"localdb.del_fav ##Error: %s" % str(e))

def save_search(cautare):
    try:
        dbcon = database.connect(addonCache)
        dbcon.text_factory = str
        dbcur = dbcon.cursor()
        dbcur.execute("DELETE FROM search WHERE search = '%s'" % (cautare))
        dbcur.execute("INSERT INTO search (search) Values (?)", (cautare,))
        dbcur.execute("VACUUM")
        dbcon.commit()
    except BaseException as e: log(u"localdb.save_search ##Error: %s" % str(e))

def del_search(text):
    try:
        dbcon = database.connect(addonCache)
        dbcon.text_factory = lambda x: unicode(x, "utf-8", "ignore")
        dbcur = dbcon.cursor()
        dbcur.execute("DELETE FROM search WHERE search = '%s'" % (text))
        dbcur.execute("VACUUM")
        dbcon.commit()
        xbmc.executebuiltin('Notification(%s,%s)' % (__scriptname__, 'Șters din Căutări'))
        xbmc.executebuiltin("Container.Refresh")
    except BaseException as e: log(u"localdb.del_search ##Error: %s" % str(e))

def get_search():
    try:
        dbcon = database.connect(addonCache)
        dbcur = dbcon.cursor()
        dbcur.execute("SELECT search FROM search")
        found = dbcur.fetchall()
        return found
    except BaseException as e: log(u"localdb.get_search ##Error: %s" % str(e))

def get_time():
    return int(time.time())

def playTrailer(params):
        get = params.get
        nume = get('nume')
        link = get('link')
        liz = xbmcgui.ListItem(nume)
        liz.setArt({'thumb': get('poster')})
        liz.setInfo(type="Video", infoLabels={'Title':nume, 'Plot': get('plot')})
        import urlresolver
        try:
            hmf = urlresolver.HostedMediaFile(url=link, include_disabled=True, include_universal=False)
            xbmc.Player().play(hmf.resolve(), liz, False)
        except Exception as e: 
            xbmc.executebuiltin('XBMC.Notification("Eroare", "%s")' % e)

def get_links(content):
    import urlparse
    links = []
    for link in content:
        if link and type(link) is tuple:
            name = link[0]
            link = link[1]
        else: name = None
        if link.startswith("//"):
            link = 'http:' + link #//ok.ru fix
        if 'goo.gl' in link:
            try:
                link = fetchData(link, redirect='1')
            except: pass
        if "hqq.tv/player/hash" in link:
            try:
                regex_code = '''unescape\(['"](.+?)['"]'''
                code = re.findall(regex_code, fetchData(hash_link), re.IGNORECASE | re.DOTALL)[0]
                vid_regex = '''vid = ['"]([0-9a-zA-Z]+)['"]'''
                vid_id = re.findall(vid_regex, urllib.unquote(code), re.IGNORECASE | re.DOTALL)[0]
                link = 'http://hqq.tv/player/embed_player.php?vid=%s' % vid_id
            except: pass
        parsed_url1 = urlparse.urlparse(link)
        if parsed_url1.scheme:
            try: import urlresolver
            except: pass
            hmf = urlresolver.HostedMediaFile(url=link, include_disabled=True, include_universal=True)
            if hmf.valid_url() == True:
                host = link.split('/')[2].replace('www.', '').capitalize()
                if name: host = name + ': ' + host
                links.append((host, link))
    return links

def clean_cat(cat):
    import unicodedata
    import codecs
    cat = unicode(cat.strip(codecs.BOM_UTF8), 'utf-8')
    cat = ''.join(c for c in unicodedata.normalize('NFKD', cat)
                       if unicodedata.category(c) != 'Mn').encode('utf-8')
    return cat

def get_threads(threads, text=None, progress=None):
    if progress:
        current = 0
        dp = xbmcgui.DialogProgress()
        dp.create(__scriptname__, '%s...' % text if text else 'Căutare...')
        total = len(threads)
    [i.start() for i in threads]
    for i in threads:
        if progress:
            dp.update(1, 'Căutare in:', str(i.getName()))
            current += 1
            percent = int((current * 100) / total)
            dp.update(percent, "", str(i.getName()), "")
            if (dp.iscanceled()): break
        i.join()
    if progress:
        dp.close()

def get_item():
    item = xbmcgui.ListItem(
        path='',
        label=xbmc.getInfoLabel("ListItem.Label"),
        label2=xbmc.getInfoLabel("ListItem.label2"),
        thumbnailImage=xbmc.getInfoLabel("ListItem.Art(thumb)"))
    _infoLabels = {
        "Title": xbmc.getInfoLabel("ListItem.Title"),
        "OriginalTitle": xbmc.getInfoLabel("ListItem.OriginalTitle"),
        "TVShowTitle": xbmc.getInfoLabel("ListItem.TVShowTitle"),
        "Season": xbmc.getInfoLabel("ListItem.Season"),
        "Episode": xbmc.getInfoLabel("ListItem.Episode"),
        "Premiered": xbmc.getInfoLabel("ListItem.Premiered"),
        "Plot": xbmc.getInfoLabel("ListItem.Plot"),
        # "Date": xbmc.getInfoLabel("ListItem.Date"),
        "VideoCodec": xbmc.getInfoLabel("ListItem.VideoCodec"),
        "VideoResolution": xbmc.getInfoLabel("ListItem.VideoResolution"),
        "VideoAspect": xbmc.getInfoLabel("ListItem.VideoAspect"),
        "DBID": xbmc.getInfoLabel("ListItem.DBID"),
        "DBTYPE": xbmc.getInfoLabel("ListItem.DBTYPE"),
        "Writer": xbmc.getInfoLabel("ListItem.Writer"),
        "Director": xbmc.getInfoLabel("ListItem.Director"),
        "Rating": xbmc.getInfoLabel("ListItem.Rating"),
        "Votes": xbmc.getInfoLabel("ListItem.Votes"),
        "IMDBNumber": xbmc.getInfoLabel("ListItem.IMDBNumber"),
    }
    infoLabels = {}
    for key, value in _infoLabels.iteritems():
        if value:
            infoLabels[key] = value

    poster = xbmc.getInfoLabel("ListItem.Art(poster)")
    if not poster:
        poster = xbmc.getInfoLabel("ListItem.Art(tvshow.poster)")

    item.setArt({
        "poster": poster,
        "banner": xbmc.getInfoLabel("ListItem.Art(banner)"),
        "fanart": xbmc.getInfoLabel("ListItem.Art(fanart)")
    })

    item.setInfo(type='Video', infoLabels=infoLabels)
    return item
