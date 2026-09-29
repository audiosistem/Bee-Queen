# -*- coding: utf-8 -*-
import re
import os
import base64
import json
import time
import six
import traceback
import sys
import sqlite3
import urllib.parse
from kodi_six import xbmcplugin, xbmcgui, xbmcaddon, xbmcvfs, xbmc
from six.moves import urllib_request, urllib_parse, urllib_error, http_cookiejar, html_parser
from xml.sax.saxutils import escape
from xml.etree import ElementTree


class NoRedirection(urllib_error.HTTPError):
    def http_response(self, request, response):
        return response
    https_response = http_response


global gLSProDynamicCodeNumber
viewmode = None
tsdownloader = False
hlsretry = False
TRANSLATEPATH = xbmc.translatePath if six.PY2 else xbmcvfs.translatePath
LOGINFO = xbmc.LOGNOTICE if six.PY2 else xbmc.LOGINFO
resolve_url = ['180upload.com', 'allmyvideos.net', 'bestreams.net', 'clicknupload.com', 'cloudzilla.to', 'movshare.net', 'novamov.com', 'nowvideo.sx', 'videoweed.es', 'daclips.in', 'datemule.com', 'fastvideo.in', 'faststream.in', 'filehoot.com', 'filenuke.com', 'sharesix.com', 'plus.google.com', 'picasaweb.google.com', 'gorillavid.com', 'gorillavid.in', 'grifthost.com', 'hugefiles.net', 'ipithos.to', 'ishared.eu', 'kingfiles.net', 'mail.ru', 'my.mail.ru', 'videoapi.my.mail.ru', 'mightyupload.com', 'mooshare.biz', 'movdivx.com', 'movpod.net', 'movpod.in', 'movreel.com', 'mrfile.me', 'nosvideo.com', 'openload.io', 'played.to', 'bitshare.com', 'filefactory.com', 'k2s.cc', 'oboom.com', 'rapidgator.net', 'primeshare.tv', 'bitshare.com', 'filefactory.com', 'k2s.cc', 'oboom.com', 'rapidgator.net', 'sharerepo.com', 'stagevu.com', 'streamcloud.eu', 'streamin.to', 'thefile.me', 'thevideo.me', 'tusfiles.net', 'uploadc.com', 'zalaa.com', 'uploadrocket.net', 'uptobox.com', 'v-vids.com', 'veehd.com', 'vidbull.com', 'videomega.tv', 'vidplay.net', 'vidspot.net', 'vidto.me', 'vidzi.tv', 'vimeo.com', 'vk.com', 'vodlocker.com', 'xfileload.com', 'xvidstage.com', 'zettahost.tv']
g_ignoreSetResolved = ['plugin.video.f4mTester', 'plugin.video.SportsDevil', 'plugin.video.sportsdevil', 'plugin.video.ZemTV-shani']
gLSProDynamicCodeNumber = 0

try:
    addon = xbmcaddon.Addon()
except:
    addon = xbmcaddon.Addon('plugin.video.live.streamspro')

addon_name = addon.getAddonInfo('name')
addon_version = addon.getAddonInfo('version')
profile = TRANSLATEPATH(addon.getAddonInfo('profile'))
home = TRANSLATEPATH(addon.getAddonInfo('path'))
sys.path.append(os.path.join(home, 'resources', 'lib'))
favorites = os.path.join(profile, 'favorites')
history = os.path.join(profile, 'history')
REV = os.path.join(profile, 'list_revision')
icon = os.path.join(home, 'icon.png')
FANART = os.path.join(home, 'fanart.jpg')
source_file = os.path.join(profile, 'source_file')
functions_dir = profile
debug = addon.getSetting('debug')

# Căutare automată a bazei de date epg*.db din folderul Database al Kodi
def find_epg_database():
    db_path = TRANSLATEPATH("special://userdata/Database/")
    if os.path.exists(db_path):
        for file in os.listdir(db_path):
            if file.startswith("Epg") and file.endswith(".db"):
                return os.path.join(db_path, file)
    return ""

EPG_DB_FILE = find_epg_database()
EPG_CACHE_FILE = os.path.join(profile, 'epg_cache.json')

if os.path.exists(favorites):
    FAV = open(favorites).read()
else:
    FAV = []
if os.path.exists(source_file):
    SOURCES = open(source_file).read()
else:
    SOURCES = []


def addon_log(string, level=xbmc.LOGDEBUG):
    if debug == 'true':
        xbmc.log("[plugin.video.live.streamspro-{0}]: {1}".format(addon_version, string), LOGINFO)
    else:
        xbmc.log("[plugin.video.live.streamspro-{0}]: {1}".format(addon_version, string), level)


def load_epg_cache():
    try:
        if os.path.exists(EPG_CACHE_FILE):
            # Verificăm dacă fișierul este mai vechi de 1 oră (3600 secunde)
            if time.time() - os.path.getmtime(EPG_CACHE_FILE) < 3600:
                with open(EPG_CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
    except:
        pass
    return {}


def save_epg_cache(cache_data):
    try:
        with open(EPG_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)
    except:
        pass


def get_current_epg_for_channel(channel_name):
    try:
        cleaned_name = channel_name.strip()
        cache = load_epg_cache()
        
        # Dacă datele există în cache, le returnăm instant
        if cleaned_name in cache:
            title = cache[cleaned_name]
            return " [COLOR orange]({0})[/COLOR]".format(title) if title else ""

        if not EPG_DB_FILE or not os.path.exists(EPG_DB_FILE):
            return ""

        conn = sqlite3.connect(EPG_DB_FILE)
        cursor = conn.cursor()
        
        now = int(time.time())
        query = """
            SELECT t.sTitle 
            FROM epgtags t 
            JOIN epg e ON t.idEpg = e.idEpg 
            WHERE (e.sName LIKE ? OR e.sScraperName LIKE ?) 
              AND t.iStartTime <= ? AND t.iEndTime >= ? 
            LIMIT 1
        """
        search_pattern = "%{0}%".format(cleaned_name)
        cursor.execute(query, (search_pattern, search_pattern, now, now))
        row = cursor.fetchone()
        conn.close()

        epg_title = row[0] if row and row[0] else ""
        
        # Salvăm în cache
        cache[cleaned_name] = epg_title
        save_epg_cache(cache)

        if epg_title:
            return " [COLOR orange]({0})[/COLOR]".format(epg_title)
    except Exception as e:
        addon_log("Eroare interogare DB EPG Kodi: {0}".format(str(e)))
    return ""


def re_me(data, re_patten):
    match = ''
    m = re.search(re_patten, data)
    if m is not None:
        match = m.group(1)
    else:
        match = ''
    return match


def makeRequest(url, headers=None):
    try:
        if headers is None:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36'}

        if '|' in url:
            url, header_in_page = url.split('|')
            header_in_page = header_in_page.split('&')

            for h in header_in_page:
                if len(h.split('=')) == 2:
                    n, v = h.split('=')
                else:
                    vals = h.split('=')
                    n = vals[0]
                    v = '='.join(vals[1:])
                headers[n] = v

        req = urllib_request.Request(url, None, headers)
        response = urllib_request.urlopen(req)
        result = response.read()

        encoding = None
        content_type = response.headers.get('content-type', '')
        if 'charset=' in content_type:
            encoding = content_type.split('charset=')[-1]

        if encoding is None:
            epattern = r'<meta\s+http-equiv="Content-Type"\s+content="(?:.+?);\s+charset=(.+?)"'
            epattern = epattern.encode('utf8') if six.PY3 else epattern
            r = re.search(epattern, result, re.IGNORECASE)
            if r:
                encoding = r.group(1).decode('utf8') if six.PY3 else r.group(1)
            else:
                epattern = r'''<meta\s+charset=["']?([^"'>]+)'''
                epattern = epattern.encode('utf8') if six.PY3 else epattern
                r = re.search(epattern, result, re.IGNORECASE)
                if r:
                    encoding = r.group(1).decode('utf8') if six.PY3 else r.group(1)

        if encoding is not None:
            result = result.decode(encoding.lower(), errors='ignore')
            result = result.encode('utf8') if six.PY2 else result
        else:
            result = result.decode('latin-1', errors='ignore') if six.PY3 else result.encode('utf-8')
        response.close()
    except urllib_error.URLError as e:
        addon_log('URL: {0}'.format(url))
        if hasattr(e, 'code'):
            msg = 'We failed with error code - {0}'.format(e.code)
            addon_log(msg)
            xbmcgui.Dialog().notification(addon_name, msg, icon, 10000, False)
        elif hasattr(e, 'reason'):
            addon_log('We failed to reach a server.')
            addon_log('Reason: {0}'.format(e.reason))
            msg = 'We failed to reach a server. - {0}'.format(e.reason)
            xbmcgui.Dialog().notification(addon_name, msg, icon, 10000, False)

    return result


def getSources():
    try:
        if addon.getSetting("new_file_source") != "" or addon.getSetting("new_url_source") != "":
            addSource()

        if os.path.exists(favorites):
            addDir('Favorites', 'url', 4, os.path.join(home, 'resources', 'favorite.png'), FANART, '', '', '', '')
        if addon.getSetting("browse_community") == "true":
            addDir('Community Files', 'community_files', 16, icon, FANART, '', '', '', '')
        if addon.getSetting("searchotherplugins") == "true":
            addDir('Search Other Plugins', 'Search Plugins', 25, icon, FANART, '', '', '', '')
        
        if os.path.exists(source_file):
            sources = json.loads(open(source_file, "r").read())
            if len(sources) > 0:
                for i in sources:
                    try:
                        thumb = icon
                        fanart = FANART
                        desc = ''
                        date = ''
                        credits = ''
                        genre = ''
                        if isinstance(i, list):
                            title = i[0]
                            url = i[1]
                        else:
                            if 'thumbnail' in i:
                                thumb = i['thumbnail']
                            if 'fanart' in i:
                                fanart = i['fanart']
                            if 'description' in i:
                                desc = i['description']
                            if 'date' in i:
                                date = i['date']
                            if 'genre' in i:
                                genre = i['genre']
                            if 'credits' in i:
                                credits = i['credits']
                            title = i['title']
                            url = i['url']
                        
                        title = title.encode('utf-8') if six.PY2 else title
                        url = url.encode('utf-8') if six.PY2 else url
                        addDir(title, url, 1, thumb, fanart, desc, genre, date, credits, 'source')
                    except:
                        traceback.print_exc()
    except:
        traceback.print_exc()


def addSource(url=None):
    if url is None:
        if addon.getSetting("new_file_source") != "":
            source_url = addon.getSetting('new_file_source')
        elif addon.getSetting("new_url_source") != "":
            source_url = addon.getSetting('new_url_source')
        else:
            return
    else:
        source_url = url
    if source_url == '' or source_url is None:
        return
    addon_log('Adding New Source: {0}'.format(source_url))

    nameStr = ""
    if '/' in source_url:
        nameStr = source_url.split('/')[-1].split('.')[0]
    if '\\' in source_url:
        nameStr = source_url.split('\\')[-1].split('.')[0]
    if '%' in nameStr:
        nameStr = urllib_parse.unquote_plus(nameStr)
    
    keyboard = xbmc.Keyboard(nameStr, 'Displayed Name, Rename?')
    keyboard.doModal()
    if (keyboard.isConfirmed() is False):
        return
    newStr = keyboard.getText()
    if len(newStr) == 0:
        return

    source_media = {}
    source_media['title'] = newStr
    source_media['url'] = source_url
    source_media['fanart'] = FANART

    if os.path.exists(source_file) is False:
        source_list = []
        source_list.append(source_media)
        b = open(source_file, "w")
        b.write(json.dumps(source_list))
        b.close()
    else:
        try:
            sources = json.loads(open(source_file, "r").read())
        except:
            sources = []
        sources.append(source_media)
        b = open(source_file, "w")
        b.write(json.dumps(sources))
        b.close()
        
    addon.setSetting('new_url_source', "")
    addon.setSetting('new_file_source', "")
    xbmcgui.Dialog().notification(addon_name, 'New source added', icon, 5000, False)


def rmSource(name):
    sources = json.loads(open(source_file, "r").read())
    for index in range(len(sources)):
        if isinstance(sources[index], list):
            if sources[index][0] == name:
                del sources[index]
                b = open(source_file, "w")
                b.write(json.dumps(sources))
                b.close()
                break
        else:
            if sources[index]['title'] == name:
                del sources[index]
                b = open(source_file, "w")
                b.write(json.dumps(sources))
                b.close()
                break
    xbmc.executebuiltin("XBMC.Container.Refresh")


def getSoup(url, data=None):
    global viewmode, tsdownloader, hlsretry
    tsdownloader = False
    hlsretry = False
    if url.startswith('http://') or url.startswith('https://'):
        enckey = False
        if '$$TSDOWNLOADER$$' in url:
            tsdownloader = True
            url = url.replace("$$TSDOWNLOADER$$", "")
        if '$$HLSRETRY$$' in url:
            hlsretry = True
            url = url.replace("$$HLSRETRY$$", "")
        if '$$LSProEncKey=' in url:
            enckey = url.split('$$LSProEncKey=')[1].split('$$')[0]
            rp = '$$LSProEncKey={0}$$'.format(enckey)
            url = url.replace(rp, "")

        data = makeRequest(url)
        if enckey:
            import pyaes
            enckey = enckey.encode("ascii")
            missingbytes = 16 - len(enckey)
            enckey = enckey + (chr(0) * (missingbytes))
            data = base64.b64decode(data)
            decryptor = pyaes.new(enckey, pyaes.MODE_ECB, IV=None)
            data = decryptor.decrypt(data).split('\0')[0]

        if re.search("#EXTM3U", data) or 'm3u' in url:
            return data
    elif data is None:
        if xbmcvfs.exists(url):
            if url.startswith("smb://") or url.startswith("nfs://"):
                copy = xbmcvfs.copy(url, os.path.join(profile, 'temp', 'source_temp.txt'))
                if copy:
                    if six.PY2:
                        data = open(os.path.join(profile, 'temp', 'source_temp.txt'), "r").read()
                    else:
                        data = open(os.path.join(profile, 'temp', 'source_temp.txt'), "r", encoding='utf-8').read()
                    xbmcvfs.delete(os.path.join(profile, 'temp', 'source_temp.txt'))
                else:
                    addon_log("failed to copy from smb:")
            else:
                if six.PY2:
                    data = open(url, 'r').read()
                else:
                    data = open(url, 'r', encoding='utf-8').read()
                if re.match("#EXTM3U", data) or 'm3u' in url:
                    return data
        else:
            addon_log("Soup Data not found!")
            return
    if '<SetViewMode>' in data:
        try:
            viewmode = re.findall('<SetViewMode>(.*?)<', data)[0]
            xbmc.executebuiltin("Container.SetViewMode({0})".format(viewmode))
        except:
            pass

    xml = None

    try:
        xml = ElementTree.fromstring(data)
    except ElementTree.ParseError as err:
        xbmcgui.Dialog().notification(addon_name, 'Failed to parse xml: {0}'.format(err.msg), icon, 10000, False)
    except Exception as err:
        xbmcgui.Dialog().notification(addon_name, 'An error occurred: {0}'.format(err), icon, 10000, False)

    return xml


def processPyFunction(data):
    try:
        if data and len(data) > 0 and data.startswith('$pyFunction:'):
            data = doEval(data.split('$pyFunction:')[1], '', None, None)
    except:
        pass

    return data


def getData(url, fanart, data=None):
    soup = getSoup(url, data)
    channels = None
    if isinstance(soup, ElementTree.Element):
        if (soup.tag == 'channels' and len(soup) > 0 and addon.getSetting('donotshowbychannels') == 'false') or (soup.tag == 'items' and len(soup) > 0):
            channels = soup.findall('channel')
            for channel in channels:
                linkedUrl = ''
                lcount = 0
                if channel.findall('externallink'):
                    linkedUrl = channel.findall('externallink')[0].text

                if lcount > 1:
                    linkedUrl = ''

                name = channel.find('name').text
                name = processPyFunction(name)

                epg_info = get_current_epg_for_channel(name)
                if epg_info:
                    name += epg_info

                if channel.find('thumbnail') is not None:
                    thumbnail = channel.find('thumbnail').text
                else:
                    thumbnail = ''
                thumbnail = processPyFunction(thumbnail)

                if channel.find('fanart') is not None:
                    fanArt = channel.find('fanart').text
                elif addon.getSetting('use_thumb') == "true":
                    fanArt = thumbnail
                else:
                    fanArt = fanart

                if channel.find('info') is not None:
                    desc = channel.find('info').text
                else:
                    desc = ''

                if channel.find('genre') is not None:
                    genre = channel.find('genre').text
                else:
                    genre = ''

                if channel.find('date') is not None:
                    date = channel.find('date').text
                else:
                    date = ''

                if channel.find('credits') is not None:
                    credits = channel.find('credits').text
                else:
                    credits = ''

                try:
                    name = name.encode('utf-8') if six.PY2 else name
                    if linkedUrl == '':
                        url = url.encode('utf-8') if six.PY2 else url
                        addDir(name, url, 2, thumbnail, fanArt, desc, genre, date, credits, True)
                    else:
                        linkedUrl = linkedUrl.encode('utf-8') if six.PY2 else linkedUrl
                        addDir(name, linkedUrl, 1, thumbnail, fanArt, desc, genre, date, None, 'source')
                except:
                    addon_log('There was a problem adding directory from getData(): {0}'.format(name))

        if channels is None or len(channels) == 0:
            addon_log('No Channels: getItems')
            getItems(soup.findall('item'), fanart)

    else:
        parse_m3u(soup)


def parse_m3u(data):
    content = data.rstrip()
    match = re.compile(r'#EXTINF:(.+?),(.*?)[\n\r]+([^\r\n]+)').findall(content)
    total = len(match)
    for other, channel_name, stream_url in match:
        epg_info = get_current_epg_for_channel(channel_name)
        if epg_info:
            channel_name += epg_info

        if 'tvg-logo' in other:
            thumbnail = re_me(other, 'tvg-logo=[\'"](.*?)[\'"]')
            if thumbnail:
                if thumbnail.startswith('http'):
                    thumbnail = thumbnail
                elif addon.getSetting('logo-folderPath') != "":
                    logo_url = addon.getSetting('logo-folderPath')
                    thumbnail = logo_url + thumbnail
                else:
                    thumbnail = thumbnail
        else:
            thumbnail = ''

        if 'type' in other:
            mode_type = re_me(other, 'type=[\'"](.*?)[\'"]')
            if mode_type == 'yt-dl':
                stream_url = stream_url + "&mode=18"
            elif mode_type == 'regex':
                url = stream_url.split('&regexs=')
                regexs = parse_regex(getSoup('', data=url[1]))

                addLink(url[0], channel_name, thumbnail, '', '', '', '', '', None, regexs, total)
                continue
        elif tsdownloader and '.ts' in stream_url:
            stream_url = 'plugin://plugin.video.f4mTester/?url={0}&amp;streamtype=TSDOWNLOADER&name={1}'.format(urllib_parse.quote_plus(stream_url), urllib_parse.quote(channel_name))
        elif hlsretry and '.m3u8' in stream_url:
            stream_url = 'plugin://plugin.video.f4mTester/?url={0}&amp;streamtype=HLSRETRY&name={1}'.format(urllib_parse.quote_plus(stream_url), urllib_parse.quote(channel_name))
        addLink(stream_url, channel_name, thumbnail, '', '', '', '', '', None, '', total)


def getChannelItems(name, url, fanart):
    soup = getSoup(url)
    channel_list = soup.find('./channel/[name="{0}"]'.format(name))
    if channel_list.find('items') is not None:
        items = channel_list.find('items').findall('item')
    else:
        items = channel_list.findall('item')
    if channel_list.find('fanart') is not None:
        fanArt = channel_list.find('fanart').text
    else:
        fanArt = fanart
    for channel in channel_list.findall('subchannel'):
        name = channel.find('name').text
        name = processPyFunction(name)

        if channel.find('thumbnail') is not None:
            thumbnail = channel.find('thumbnail').text
            thumbnail = processPyFunction(thumbnail)
        else:
            thumbnail = ''

        if channel.find('fanart') is not None:
            fanArt = channel.find('fanart').text
        elif addon.getSetting('use_thumb') == "true":
            fanArt = thumbnail
        else:
            fanArt = ''

        if channel.find('info') is not None:
            desc = channel.find('info').text
        else:
            desc = ''

        if channel.find('genre') is not None:
            genre = channel.find('genre').text
        else:
            genre = ''

        if channel.find('date') is not None:
            date = channel.find('date').text
        else:
            date = ''

        if channel.find('credits') is not None:
            credits = channel.find('credits').text
        else:
            credits = ''

        try:
            if six.PY2:
                name = name.encode('utf-8')
                url = url.encode('utf-8')
            addDir(name, url, 3, thumbnail, fanArt, desc, genre, credits, date)
        except:
            addon_log('There was a problem adding directory - {0}'.format(name))
    getItems(items, fanArt)


def getSubChannelItems(name, url, fanart):
    soup = getSoup(url)
    channel_list = soup.find('./channel/subchannel/[name="{0}"]'.format(name))
    items = channel_list.find('subitems').findall('subitem')
    getItems(items, fanart)


def getItems(items, fanart, dontLink=False):
    total = len(items)
    add_playlist = addon.getSetting('add_playlist')
    ask_playlist_items = addon.getSetting('ask_playlist_items')
    parentalblock = addon.getSetting('parentalblocked')
    parentalblock = parentalblock == "true"
    for item in items:
        isXMLSource = False
        isJsonrpc = False

        if isinstance(item.find('parentalblock'), ElementTree.Element):
            applyblock = item.find('parentalblock').text
        else:
            applyblock = 'false'
        if applyblock == 'true' and parentalblock:
            continue

        if isinstance(item.find('title'), ElementTree.Element):
            name = item.find('title').text
            if name == '':
                name = 'unknown?'
            name = processPyFunction(name)
        else:
            addon_log('Name Error')
            name = ''

        epg_info = get_current_epg_for_channel(name)
        if epg_info:
            name += epg_info

        regexs = None
        if isinstance(item.find('regex'), ElementTree.Element):
            regexs = parse_regex(item.findall('regex'))

        try:
            url = []
            if len(item.findall('link')) > 0:
                for i in item.findall('link'):
                    if i.text is not None:
                        url.append(i.text)
            elif len(item.findall('sportsdevil')) > 0:
                for i in item.findall('sportsdevil'):
                    if i.text is not None:
                        sd_plugin = "plugin://plugin.video.SportsDevil" if six.PY2 else "plugin://plugin.video.sportsdevil"
                        sportsdevil = sd_plugin + '/?mode=1&amp;item=catcher%3dstreams%26url=' + i.text + '%26videoTitle=' + name
                        if item.find('referer'):
                            sportsdevil = sportsdevil + '%26referer=' + item.find('referer').text
                        url.append(sportsdevil)
            elif len(item.findall('yt-dl')) > 0:
                for i in item.findall('yt-dl'):
                    if i.text is not None:
                        ytdl = i.text + '&mode=18'
                        url.append(ytdl)
            elif len(item.findall('dm')) > 0:
                for i in item.findall('dm'):
                    if i.text is not None:
                        dm = "plugin://plugin.video.dailymotion_com/?mode=playVideo&url=" + i.text
                        url.append(dm)
            elif len(item.findall('dmlive')) > 0:
                for i in item.findall('dmlive'):
                    if i.text is not None:
                        dm = "plugin://plugin.video.dailymotion_com/?mode=playLiveVideo&url=" + i.text
                        url.append(dm)
            elif len(item.findall('utube')) > 0:
                for i in item.findall('utube'):
                    if i.text is not None:
                        if ' ' in i.text:
                            utube = 'plugin://plugin.video.youtube/search/?q=' + urllib_parse.quote_plus(i.text)
                            isJsonrpc = utube
                        elif len(i.text) == 11:
                            utube = 'plugin://plugin.video.youtube/play/?video_id=' + i.text
                        elif (i.text.startswith('PL') and '&order=' not in i.text) or i.text.startswith('UU'):
                            utube = 'plugin://plugin.video.youtube/play/?&order=default&playlist_id=' + i.text
                        elif i.text.startswith('PL') or i.text.startswith('UU'):
                            utube = 'plugin://plugin.video.youtube/play/?playlist_id=' + i.text
                        elif i.text.startswith('UC') and len(i.text) > 12:
                            utube = 'plugin://plugin.video.youtube/channel/' + i.text + '/'
                            isJsonrpc = utube
                        elif not i.text.startswith('UC') and not (i.text.startswith('PL')):
                            utube = 'plugin://plugin.video.youtube/user/' + i.text + '/'
                            isJsonrpc = utube
                    url.append(utube)
            elif len(item.findall('f4m')) > 0:
                for i in item.findall('f4m'):
                    if i.text is not None:
                        if '.f4m' in i.text:
                            f4m = 'plugin://plugin.video.f4mTester/?url=' + urllib_parse.quote_plus(i.text)
                        elif '.m3u8' in i.text:
                            f4m = 'plugin://plugin.video.f4mTester/?url=' + urllib_parse.quote_plus(i.text) + '&amp;streamtype=HLS'
                        else:
                            f4m = 'plugin://plugin.video.f4mTester/?url=' + urllib_parse.quote_plus(i.text) + '&amp;streamtype=SIMPLE'
                    url.append(f4m)
            elif len(item.findall('urlsolve')) > 0:
                for i in item.findall('urlsolve'):
                    if i.text is not None:
                        resolver = i.text + '&mode=19'
                        url.append(resolver)
            elif len(item.findall('inputstream')) > 0:
                for i in item.findall('inputstream'):
                    if i.text is not None:
                        istream = i.text + '&mode=20'
                        url.append(istream)
            elif len(item.findall('slproxy')) > 0:
                for i in item.findall('slproxy'):
                    if i.text is not None:
                        istream = i.text + '&mode=22'
                        url.append(istream)

            if len(url) < 1:
                raise Exception()
        except:
            addon_log('Error <link> element, Passing: {0}'.format(name.encode('utf-8') if six.PY2 else name))
            traceback.print_exc()
            continue

        if isinstance(item.find('externallink'), ElementTree.Element):
            isXMLSource = item.find('externallink').text

        if isXMLSource:
            ext_url = [isXMLSource]
            isXMLSource = True

        if isinstance(item.find('jsonrpc'), ElementTree.Element):
            isJsonrpc = item.find('jsonrpc').text

        if isJsonrpc:
            ext_url = [isJsonrpc]
            isJsonrpc = True

        if isinstance(item.find('thumbnail'), ElementTree.Element):
            thumbnail = item.find('thumbnail').text
            thumbnail = processPyFunction(thumbnail)
        else:
            thumbnail = ''

        if isinstance(item.find('fanart'), ElementTree.Element):
            fanArt = item.find('fanart').text
        elif addon.getSetting('use_thumb') == "true":
            fanArt = thumbnail
        else:
            fanArt = fanart

        if isinstance(item.find('info'), ElementTree.Element):
            desc = item.find('info').text
        else:
            desc = ''

        if isinstance(item.find('genre'), ElementTree.Element):
            genre = item.find('genre').text
        else:
            genre = ''

        if isinstance(item.find('date'), ElementTree.Element):
            date = item.find('date').text
        else:
            date = ''

        try:
            if len(url) > 1:
                alt = 0
                playlist = []
                ignorelistsetting = True if '$$LSPlayOnlyOne$$' in url[0] else False

                for i in url:
                    if add_playlist == "false" and not ignorelistsetting:
                        alt += 1
                        addLink(i, '{0}) {1}'.format(alt, name.encode('utf-8', 'ignore') if six.PY2 else name), thumbnail, fanArt, desc, genre, date, True, playlist, regexs, total)
                    elif (add_playlist == "true" and ask_playlist_items == 'true') or ignorelistsetting:
                        if regexs:
                            playlist.append(i + '&regexs=' + regexs)
                        elif any(x in i for x in resolve_url) and i.startswith('http'):
                            playlist.append(i + '&mode=19')
                        else:
                            playlist.append(i)
                    else:
                        playlist.append(i)

                if len(playlist) > 1:
                    addLink('', name.encode('utf-8') if six.PY2 else name, thumbnail, fanArt, desc, genre, date, True, playlist, regexs, total)
            else:
                if dontLink:
                    return name, url[0], regexs
                if isXMLSource:
                    if six.PY2:
                        name = name.encode('utf-8')
                        ext_url[0] = ext_url[0].encode('utf-8')
                        url[0] = url[0].encode('utf-8')
                    if regexs is not None:
                        addDir(name, ext_url[0], 1, thumbnail, fanArt, desc, genre, date, None, '!!update', regexs, url[0])
                    else:
                        addDir(name, ext_url[0], 1, thumbnail, fanArt, desc, genre, date, None, 'source', None, None)
                elif isJsonrpc:
                    addDir(name.encode('utf-8') if six.PY2 else name, ext_url[0], 53, thumbnail, fanArt, desc, genre, date, None, 'source')
                else:
                    try:
                        if '$doregex' in name and getRegexParsed is not None:
                            tname, setres = getRegexParsed(regexs, name)
                            if tname is not None:
                                name = tname
                    except:
                        pass
                    try:
                        if '$doregex' in thumbnail and getRegexParsed is not None:
                            tname, setres = getRegexParsed(regexs, thumbnail)
                            if tname is not None:
                                thumbnail = tname
                    except:
                        pass
                    addLink(url[0], name.encode('utf-8') if six.PY2 else name, thumbnail, fanArt, desc, genre, date, True, None, regexs, total)
        except:
            traceback.print_exc()
            addon_log('There was a problem adding item - {0}'.format(repr(name)))


def parse_regex(reg_items):
    reg_tags = ['name', 'expres', 'page', 'referer', 'connection', 'notplayable', 'noredirect', 'origin', 'agent',
                'accept', 'includeheaders', 'listrepeat', 'proxy', 'x-req', 'x-addr', 'x-forward', 'post', 'rawpost',
                'htmlunescape', 'readcookieonly', 'cookiejar', 'setcookie', 'appendcookie', 'ignorecache', 'thumbnail']
    regexs = {}

    if isinstance(reg_items, ElementTree.Element):
        reg_items = [reg_items]

    for reg_item in reg_items:
        rname = reg_item.find('name').text
        sregexs = {}
        for i in reg_item:
            if i.tag in reg_tags:
                sregexs.update({i.tag: i.text})
            else:
                addon_log('Unsupported tag: {0}'.format(i.tag), LOGINFO)
        if not sregexs.get('expres'):
            sregexs.update({'expres': ''})
        if not sregexs.get('cookiejar'):
            sregexs.update({'cookiejar': ''})
        regexs.update({rname: sregexs})

    regexs = urllib_parse.quote(repr(regexs))
    return regexs


def getRegexParsed(regexs, url, cookieJar=None, forCookieJarOnly=False, recursiveCall=False, cachedPages={}, rawPost=False, cookie_jar_file=None):
    if not recursiveCall:
        regexs = eval(urllib_parse.unquote(regexs))

    doRegexs = re.compile(r'\$doregex\[([^\]]*)\]').findall(url)
    setresolved = True
    for k in doRegexs:
        if k in regexs:
            m = regexs[k]
            cookieJarParam = False
            if 'cookiejar' in m:
                cookieJarParam = m['cookiejar']
                if '$doregex' in cookieJarParam:
                    cookieJar = getRegexParsed(regexs, m['cookiejar'], cookieJar, True, True, cachedPages)
                    cookieJarParam = True
                else:
                    cookieJarParam = True

            if cookieJarParam:
                if cookieJar is None:
                    cookie_jar_file = None
                    if 'open[' in m['cookiejar']:
                        cookie_jar_file = m['cookiejar'].split('open[')[1].split(']')[0]
                    cookieJar = getCookieJar(cookie_jar_file)
                    if cookie_jar_file:
                        saveCookieJar(cookieJar, cookie_jar_file)
                elif 'save[' in m['cookiejar']:
                    cookie_jar_file = m['cookiejar'].split('save[')[1].split(']')[0]
                    complete_path = os.path.join(profile, cookie_jar_file)
                    saveCookieJar(cookieJar, complete_path)
            if m['page'] and '$doregex' in m['page']:
                pg = getRegexParsed(regexs, m['page'], cookieJar, recursiveCall=True, cachedPages=cachedPages)
                if len(pg) == 0:
                    pg = 'http://regexfailed'
                m['page'] = pg

            if 'setcookie' in m and m['setcookie'] and '$doregex' in m['setcookie']:
                m['setcookie'] = getRegexParsed(regexs, m['setcookie'], cookieJar, recursiveCall=True, cachedPages=cachedPages)
            if 'appendcookie' in m and m['appendcookie'] and '$doregex' in m['appendcookie']:
                m['appendcookie'] = getRegexParsed(regexs, m['appendcookie'], cookieJar, recursiveCall=True, cachedPages=cachedPages)

            if 'post' in m and '$doregex' in m['post']:
                m['post'] = getRegexParsed(regexs, m['post'], cookieJar, recursiveCall=True, cachedPages=cachedPages)

            if 'rawpost' in m and '$doregex' in m['rawpost']:
                m['rawpost'] = getRegexParsed(regexs, m['rawpost'], cookieJar, recursiveCall=True, cachedPages=cachedPages, rawPost=True)

            link = ''
            if m['page'] and m['page'] in cachedPages and 'ignorecache' not in m and forCookieJarOnly is False:
                link = cachedPages[m['page']]
            else:
                if m['page'] and m['page'] != '' and m['page'].startswith('http'):
                    page_split = m['page'].split('|')
                    pageUrl = page_split[0]
                    header_in_page = None
                    if len(page_split) > 1:
                        header_in_page = page_split[1]

                    current_proxies = urllib_request.ProxyHandler(urllib_request.getproxies())
                    req = urllib_request.Request(pageUrl)
                    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; rv:14.0) Gecko/20100101 Firefox/14.0.1')

                    if 'referer' in m:
                        req.add_header('Referer', m['referer'])
                    if 'accept' in m:
                        req.add_header('Accept', m['accept'])
                    if 'agent' in m:
                        req.add_header('User-agent', m['agent'])

                    if cookieJar is not None:
                        cookie_handler = urllib_request.HTTPCookieProcessor(cookieJar)
                        opener = urllib_request.build_opener(cookie_handler, urllib_request.HTTPBasicAuthHandler(), urllib_request.HTTPHandler())
                        urllib_request.install_opener(opener)

                    post = None
                    if 'post' in m:
                        postData = m['post']
                        splitpost = postData.split(',')
                        post = {}
                        for p in splitpost:
                            n = p.split(':')[0]
                            v = p.split(':')[1]
                            post[n] = v
                        post = urllib_parse.urlencode(post)

                    if 'rawpost' in m:
                        post = m['rawpost']

                    try:
                        if post is not None:
                            response = urllib_request.urlopen(req, post.encode('utf-8'))
                        else:
                            response = urllib_request.urlopen(req)
                        link = response.read()
                        response.close()
                    except:
                        pass
                    cachedPages[m['page']] = link

                    if forCookieJarOnly:
                        return cookieJar

            if m['expres'] != '':
                val = ''
                if link != '':
                    reg = re.compile(m['expres']).search(link)
                    if reg:
                        val = reg.group(1).strip()
                elif m['page'] == '' or m['page'] is None:
                    val = m['expres']

                if rawPost:
                    val = urllib_parse.quote_plus(val)
                try:
                    url = url.replace("$doregex[" + k + "]", val)
                except:
                    url = url.replace("$doregex[" + k + "]", val.decode("utf-8"))
            else:
                url = url.replace("$doregex[" + k + "]", '')

    if recursiveCall:
        return url

    if url == "":
        return
    else:
        return url, setresolved


def getCookiesString(cookieJar):
    try:
        cookieString = ""
        for index, cookie in enumerate(cookieJar):
            cookieString += cookie.name + "=" + cookie.value + ";"
    except:
        pass
    return cookieString


def saveCookieJar(cookieJar, COOKIEFILE):
    try:
        complete_path = os.path.join(profile, COOKIEFILE)
        cookieJar.save(complete_path, ignore_discard=True)
    except:
        pass


def getCookieJar(COOKIEFILE):
    cookieJar = None
    if COOKIEFILE:
        try:
            complete_path = os.path.join(profile, COOKIEFILE)
            cookieJar = http_cookiejar.LWPCookieJar()
            cookieJar.load(complete_path, ignore_discard=True)
        except:
            cookieJar = None

    if not cookieJar:
        cookieJar = http_cookiejar.LWPCookieJar()

    return cookieJar


def doEval(fun_call, page_data, Cookie_Jar, m):
    global ret_val
    ret_val = ''
    globals()["page_data"] = page_data
    globals()["Cookie_Jar"] = Cookie_Jar
    globals()["m"] = m

    if functions_dir not in sys.path:
        sys.path.append(functions_dir)
    try:
        py_file = 'import ' + fun_call.split('.')[0]
        six.exec_(py_file, globals())
    except:
        pass
    six.exec_('ret_val=' + fun_call, globals())
    return six.ensure_str(ret_val)


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
            splitparams = pairsofparams[i].split('=')
            if (len(splitparams)) == 2:
                param[splitparams[0]] = splitparams[1]
    return param


def getFavorites():
    items = json.loads(open(favorites).read())
    total = len(items)
    for i in items:
        name = i[0]
        url = i[1]
        iconimage = i[2]
        try:
            fanArt = i[3]
            if fanArt is None:
                raise Exception()
        except:
            fanArt = fanart
        try:
            playlist = i[5]
        except:
            playlist = None
        try:
            regexs = i[6]
        except:
            regexs = None

        if i[4] == 0:
            addLink(url, name, iconimage, fanArt, '', '', '', 'fav', playlist, regexs, total)
        else:
            addDir(name, url, i[4], iconimage, fanart, '', '', '', '', 'fav')


def addFavorite(name, url, iconimage, fanart, mode, playlist=None, regexs=None):
    favList = []
    try:
        name = name.encode('utf-8', 'ignore') if six.PY2 else name
    except:
        pass
    if os.path.exists(favorites) is False:
        favList.append((name, url, iconimage, fanart, mode, playlist, regexs))
        a = open(favorites, "w")
        a.write(json.dumps(favList))
        a.close()
    else:
        a = open(favorites).read()
        data = json.loads(a)
        data.append((name, url, iconimage, fanart, mode, playlist, regexs))
        b = open(favorites, "w")
        b.write(json.dumps(data))
        b.close()


def rmFavorite(name):
    data = json.loads(open(favorites).read())
    for index in range(len(data)):
        if data[index][0] == name:
            del data[index]
            b = open(favorites, "w")
            b.write(json.dumps(data))
            b.close()
            break
    xbmc.executebuiltin("XBMC.Container.Refresh")


def urlsolver(url):
    try:
        import resolveurl
    except:
        import urlresolver as resolveurl

    if resolveurl.HostedMediaFile(url).valid_url():
        resolved = resolveurl.resolve(url)
    else:
        xbmcgui.Dialog().notification(addon_name, 'ResolveUrl does not support this domain.', icon, 5000, False)
        resolved = url
    return resolved


def addDir(name, url, mode, iconimage, fanart, description, genre, date, credits, showcontext=False, regexs=None, reg_url=None, allinfo={}):
    url = url + "/" if url.endswith(".xml") else url
    if regexs and len(regexs) > 0:
        u = sys.argv[0] + "?url=" + urllib_parse.quote_plus(url) + "&mode=" + str(mode) + "&name=" + urllib_parse.quote_plus(name) + "&fanart=" + urllib_parse.quote_plus(fanart) + "&regexs=" + regexs
    else:
        u = sys.argv[0] + "?url=" + urllib_parse.quote_plus(url) + "&mode=" + str(mode) + "&name=" + urllib_parse.quote_plus(name) + "&fanart=" + urllib_parse.quote_plus(fanart)

    if date == '':
        date = None
    else:
        description += '\n\nDate: %s' % date
    liz = xbmcgui.ListItem(name)
    liz.setArt({'fanart': fanart, 'thumb': iconimage, 'icon': "DefaultFolder.png"})

    if len(allinfo) < 1:
        liz.setInfo(type="Video", infoLabels={"Title": name, 'mediatype': 'video', "Plot": description, "Genre": genre, "dateadded": date, "credits": credits})
    else:
        allinfo.update({'mediatype': 'video'})
        liz.setInfo(type="Video", infoLabels=allinfo)

    liz.setProperty('IsPlayable', 'false')

    if showcontext:
        contextMenu = []
        if showcontext == 'source':
            if name in str(SOURCES):
                contextMenu.append(('Remove from Sources', 'RunPlugin(%s?mode=8&name=%s)' % (sys.argv[0], urllib_parse.quote_plus(name))))
        elif showcontext == 'fav':
            contextMenu.append(('Remove from LiveStreamsPro Favorites', 'RunPlugin(%s?mode=6&name=%s)' % (sys.argv[0], urllib_parse.quote_plus(name))))
        if name not in FAV:
            contextMenu.append(('Add to LiveStreamsPro Favorites', 'RunPlugin(%s?mode=5&name=%s&url=%s&iconimage=%s&fanart=%s&fav_mode=%s)' % (sys.argv[0], urllib_parse.quote_plus(name), urllib_parse.quote_plus(url), urllib_parse.quote_plus(iconimage), urllib_parse.quote_plus(fanart), mode)))
        liz.addContextMenuItems(contextMenu)
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=True)
    return ok


def addLink(url, name, iconimage, fanart, description, genre, date, showcontext, playlist, regexs, total, setCookie="", allinfo={}):
    contextMenu = []
    try:
        name = name.encode('utf-8') if six.PY2 else name
    except:
        pass
    isFolder = False
    if regexs:
        mode = '17'
        if 'listrepeat' in regexs:
            isFolder = True
    elif (any(x in url for x in resolve_url) and url.startswith('http')) or url.endswith('&mode=19'):
        url = url.replace('&mode=19', '')
        mode = '19'
    elif url.endswith('&mode=18'):
        url = url.replace('&mode=18', '')
        mode = '18'
    else:
        mode = '12'

    u = sys.argv[0] + "?url=" + urllib_parse.quote_plus(url) + "&mode=" + mode
    if regexs:
        u += "&regexs=" + regexs
    if iconimage and iconimage != '':
        u += "&iconimage=" + urllib_parse.quote_plus(iconimage)

    if date == '':
        date = None
    else:
        description += '\n\nDate: %s' % date
    liz = xbmcgui.ListItem(name)
    liz.setArt({'thumb': iconimage, 'fanart': fanart, 'icon': "DefaultVideo.png"})

    if allinfo is None or len(allinfo) < 1:
        liz.setInfo(type="Video", infoLabels={"Title": name, 'mediatype': 'video', "Plot": description, "Genre": genre, "dateadded": date})
    else:
        allinfo.update({'mediatype': 'video'})
        liz.setInfo(type="Video", infoLabels=allinfo)

    liz.setProperty('IsPlayable', 'true')

    if showcontext:
        if showcontext == 'fav':
            contextMenu.append(('Remove from LiveStreamsPro Favorites', 'RunPlugin(%s?mode=6&name=%s)' % (sys.argv[0], urllib_parse.quote_plus(name))))
        elif name not in FAV:
            iconimage = iconimage if iconimage else ''
            fanart = fanart if fanart else ''
            fav_params = '%s?mode=5&name=%s&url=%s&iconimage=%s&fanart=%s&fav_mode=0' % (sys.argv[0], urllib_parse.quote_plus(name), urllib_parse.quote_plus(url), urllib_parse.quote_plus(iconimage), urllib_parse.quote_plus(fanart))
            if playlist:
                fav_params += '&playlist=' + urllib_parse.quote_plus(str(playlist).replace(',', '||'))
            if regexs:
                fav_params += "&regexs=" + regexs
            contextMenu.append(('Add to LiveStreamsPro Favorites', 'RunPlugin(%s)' % fav_params))
        liz.addContextMenuItems(contextMenu)

    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, totalItems=total, isFolder=isFolder)
    return ok


def playsetresolved(url, name, iconimage, setresolved=True, reg=None):
    if url is None:
        xbmcplugin.endOfDirectory(int(sys.argv[1]))
        return

    if setresolved:
        liz = xbmcgui.ListItem(name)
        liz.setArt({'thumb': iconimage, 'icon': iconimage})
        liz.setInfo(type='Video', infoLabels={'Title': name, 'mediatype': 'video'})
        liz.setProperty("IsPlayable", "true")
        if '&mode=19' in url:
            url = urlsolver(url.replace('&mode=19', '').replace(';', ''))
        liz.setPath(url)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, liz)
    else:
        xbmc.executebuiltin('RunPlugin(' + url + ')')


xbmcplugin.setContent(int(sys.argv[1]), 'movies')

try:
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_UNSORTED)
except:
    pass

params = get_params()
url = None
name = None
mode = None
playlist = None
iconimage = None
fanart = FANART
fav_mode = None
regexs = None

try:
    url = urllib_parse.unquote_plus(params["url"])
    url = url.decode('utf-8') if six.PY2 else url
    url = url.rstrip("/") if url.endswith(".xml/") else url
except:
    pass
try:
    name = urllib_parse.unquote_plus(params["name"])
except:
    pass
try:
    iconimage = urllib_parse.unquote_plus(params["iconimage"])
except:
    pass
try:
    fanart = urllib_parse.unquote_plus(params["fanart"])
except:
    fanart = FANART
try:
    mode = int(params["mode"])
except:
    pass
try:
    regexs = params["regexs"]
except:
    pass

addon_log("Mode: {0}".format(mode))

if mode is None:
    getSources()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
elif mode == 1:
    getData(url, fanart)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
elif mode == 2:
    getChannelItems(name, url, fanart)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
elif mode == 3:
    getSubChannelItems(name, url, fanart)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
elif mode == 4:
    getFavorites()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
elif mode == 5:
    addFavorite(name, url, iconimage, fanart, fav_mode)
elif mode == 6:
    rmFavorite(name)
elif mode == 7 or mode == 11:
    addSource(url)
elif mode == 8:
    rmSource(name)
elif mode == 12:
    playsetresolved(url, name, iconimage, True)
elif mode == 17:
    url, setresolved = getRegexParsed(regexs, url)
    playsetresolved(url, name, iconimage, setresolved, regexs)