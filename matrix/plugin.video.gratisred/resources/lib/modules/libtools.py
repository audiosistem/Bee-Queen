# -*- coding: utf-8 -*-

import re
import os
import sys
import shutil
import datetime

import simplejson as json
import six
from six.moves import urllib_parse

from resources.lib.modules import cleantitle
from resources.lib.modules import control

try:
    from sqlite3 import dbapi2 as database
except:
    from pysqlite2 import dbapi2 as database


class lib_tools:
    @staticmethod
    def create_folder(folder):
        try:
            folder = control.legalFilename(folder)
            control.makeFile(folder)
            try:
                if not 'ftp://' in folder:
                    raise Exception()
                from ftplib import FTP
                ftparg = re.compile(r'ftp://(.+?):(.+?)@(.+?):?(\d+)?/(.+/?)').findall(folder)
                ftp = FTP(ftparg[0][2], ftparg[0][0], ftparg[0][1])
                try:
                    ftp.cwd(ftparg[0][4])
                except:
                    ftp.mkd(ftparg[0][4])
                ftp.quit()
            except:
                pass
        except:
            pass


    @staticmethod
    def write_file(path, content):
        try:
            path = control.legalFilename(path)
            if not isinstance(content, six.string_types):
                content = str(content)
            file = control.openFile(path, 'w')
            file.write(str(content))
            file.close()
        except Exception as e:
            pass


    @staticmethod
    def nfo_url(media_string, ids):
        imdb_url = 'https://www.imdb.com/title/%s/'
        tmdb_url = 'https://www.themoviedb.org/%s/%s'
        tvdb_url = 'https://thetvdb.com/?tab=series&id=%s'
        if 'imdb' in ids:
            return imdb_url % (str(ids['imdb']))
        elif 'tmdb' in ids:
            return tmdb_url % (media_string, str(ids['tmdb']))
        elif 'tvdb' in ids:
            return tvdb_url % (str(ids['tvdb']))
        else:
            return ''


    @staticmethod
    def legal_filename(filename):
        try:
            filename = filename.strip()
            filename = re.sub(r'(?!%s)[^\w\-_\.]', '.', filename)
            filename = re.sub(r'\.+', '.', filename)
            filename = re.sub(re.compile(r'(CON|PRN|AUX|NUL|COM\d|LPT\d)\.', re.I), '\\1_', filename)
            control.legalFilename(filename)
            return filename
        except:
            return filename


    @staticmethod
    def normalize_folder_title(title):
        try:
            transtitle = title.translate(None, r'\/:*?"<>|')
        except:
            transtitle = title.translate(str.maketrans('', '', r'\/:*?"<>|'))
        return cleantitle.normalize(transtitle)


    @staticmethod
    def make_path(base_path, title, year='', season=''):
        show_folder = re.sub(r'[^\w\-_\. ]', '_', title)
        show_folder = '%s (%s)' % (show_folder, year) if year else show_folder
        path = os.path.join(base_path, show_folder)
        if season:
            path = os.path.join(path, 'Season %s' % season)
        return path


class libmovies:
    def __init__(self):
        self.library_folder = os.path.join(control.transPath(control.setting('library.movie')), '')
        self.library_setting = control.setting('library.update') or 'true'
        self.dupe_setting = control.setting('library.check') or 'true'
        self.silentDialog = False
        self.infoDialog = False


    def add(self, name, title, year, imdb, range=False):
        if not control.condVisibility('Window.IsVisible(infodialog)') and not control.condVisibility('Player.HasVideo') and self.silentDialog is False:
            control.infoDialog('Adding to library...', time=10000000)
            self.infoDialog = True
        try:
            if not self.dupe_setting == 'true':
                raise Exception()
            id = imdb
            lib = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"filter":{"or": [{"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties" : ["imdbnumber", "title", "year"]}, "id": 1}' % (year, str(int(year)+1), str(int(year)-1)))
            lib = six.ensure_text(lib, errors='ignore')
            lib = json.loads(lib)['result']['movies']
            lib = [i for i in lib if str(i['imdbnumber']) in id or (six.ensure_str(i['title']) == title and str(i['year']) == year)][0]
        except:
            lib = []
        files_added = 0
        try:
            if not lib == []:
                raise Exception()
            self.strmFile({'name': name, 'title': title, 'year': year, 'imdb': imdb})
            files_added += 1
        except:
            pass
        if range == True:
            return
        if self.infoDialog == True:
            control.infoDialog('Process Complete', time=1)
        if self.library_setting == 'true' and not control.condVisibility('Library.IsScanningVideo') and files_added > 0:
            control.execute('UpdateLibrary(video)')


    def silent(self, url):
        control.idle()
        if not control.condVisibility('Window.IsVisible(infodialog)') and not control.condVisibility('Player.HasVideo'):
            control.infoDialog('Adding to library...', time=10000000)
            self.infoDialog = True
            self.silentDialog = True
        from resources.lib.indexers import movies
        items = movies.movies().get(url, idx=False)
        if items == None:
            items = []
        for i in items:
            try:
                if control.monitor.abortRequested():
                    return sys.exit()
                self.add('%s (%s)' % (i['title'], i['year']), i['title'], i['year'], i['imdb'], range=True)
            except:
                pass
        if self.infoDialog == True:
            self.silentDialog = False
            control.infoDialog("Trakt Movies Sync Complete", time=1)


    def range(self, url):
        control.idle()
        yes = control.yesnoDialog('Are you sure?')
        if not yes:
            return
        if not control.condVisibility('Window.IsVisible(infodialog)') and not control.condVisibility('Player.HasVideo'):
            control.infoDialog('Adding to library...', time=10000000)
            self.infoDialog = True
        from resources.lib.indexers import movies
        items = movies.movies().get(url, idx=False)
        if items == None:
            items = []
        for i in items:
            try:
                if control.monitor.abortRequested():
                    return sys.exit()
                self.add('%s (%s)' % (i['title'], i['year']), i['title'], i['year'], i['imdb'], range=True)
            except:
                pass
        if self.infoDialog == True:
            control.infoDialog('Process Complete', time=1)
        if self.library_setting == 'true' and not control.condVisibility('Library.IsScanningVideo'):
            control.execute('UpdateLibrary(video)')


    def strmFile(self, i):
        try:
            name, title, year, imdb = i['name'], i['title'], i['year'], i['imdb']
            sysname, systitle = urllib_parse.quote_plus(name), urllib_parse.quote_plus(title)
            transtitle = lib_tools.normalize_folder_title(title)
            content = '%s?action=play&name=%s&title=%s&year=%s&imdb=%s' % (sys.argv[0], sysname, systitle, year, imdb)
            folder = lib_tools.make_path(self.library_folder, transtitle, year)
            lib_tools.create_folder(folder)
            lib_tools.write_file(os.path.join(folder, lib_tools.legal_filename(transtitle) + '.' + year + '.strm'), content)
            lib_tools.write_file(os.path.join(folder, lib_tools.legal_filename(transtitle) + '.' + year + '.nfo'), lib_tools.nfo_url('movie', i))
        except:
            pass


    def folder_path(self, title, year):
        try:
            transtitle = lib_tools.normalize_folder_title(title)
            return lib_tools.make_path(self.library_folder, transtitle, year)
        except:
            return None


    def has(self, title, year, imdb=None):
        try:
            folder = self.folder_path(title, year)
            if not folder or not os.path.isdir(folder):
                return False
            _, files = control.listDir(folder)
            return any(str(f).endswith('.strm') for f in files)
        except:
            return False


    def _remove_kodi_movie(self, title, year, imdb):
        try:
            imdb = 'tt' + re.sub(r'[^0-9]', '', str(imdb))
            safe_title = title.replace('\\', '\\\\').replace('"', '\\"')
            lib = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"filter":{"or": [{"field": "imdbnumber", "operator": "is", "value": "%s"}, {"field": "title", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties": ["title"]}, "id": 1}' % (imdb, safe_title, year))
            lib = six.ensure_text(lib, errors='ignore')
            movies = json.loads(lib).get('result', {}).get('movies') or []
            for movie in movies:
                control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.RemoveMovie", "params": {"movieid": %s, "deletefile": true}, "id": 1}' % int(movie['movieid']))
        except:
            pass


    def remove(self, title, year, imdb):
        if not self.has(title, year, imdb):
            control.infoDialog('Not in your local library.', sound=True)
            return
        if not control.yesnoDialog('Remove "%s (%s)" from your local library?' % (title, year)):
            return
        folder = self.folder_path(title, year)
        self._remove_kodi_movie(title, year, imdb)
        try:
            if folder and os.path.isdir(folder):
                shutil.rmtree(folder, ignore_errors=True)
        except:
            pass
        control.infoDialog('Removed from library.', sound=True)
        if self.library_setting == 'true' and not control.condVisibility('Library.IsScanningVideo'):
            control.execute('CleanLibrary(video)')


    def refresh(self, name, title, year, imdb):
        if not self.has(title, year, imdb):
            self.add(name, title, year, imdb)
            return
        if not control.condVisibility('Window.IsVisible(infodialog)') and not control.condVisibility('Player.HasVideo'):
            control.infoDialog('Updating library item...', time=3000)
        self.strmFile({'name': name, 'title': title, 'year': year, 'imdb': imdb})
        control.infoDialog('Library item updated.', sound=True)
        if self.library_setting == 'true' and not control.condVisibility('Library.IsScanningVideo'):
            control.execute('UpdateLibrary(video)')


    def scan_local_items(self):
        items = []
        try:
            for folder in control.listDir(self.library_folder)[0]:
                folder_path = os.path.join(self.library_folder, folder)
                try:
                    files = control.listDir(folder_path)[1]
                except:
                    continue
                strms = [f for f in files if str(f).endswith('.strm')]
                if not strms:
                    continue
                try:
                    file = control.openFile(os.path.join(folder_path, strms[0]))
                    read = six.ensure_str(file.read())
                    file.close()
                    if not read.startswith(sys.argv[0]):
                        raise Exception()
                    params = dict(urllib_parse.parse_qsl(read.replace('?', '')))
                    title = params.get('title') or params.get('name') or folder
                    title = urllib_parse.unquote_plus(title)
                    year = params.get('year') or '0'
                    imdb = params.get('imdb') or '0'
                    tmdb = params.get('tmdb') or '0'
                    items.append({'title': title, 'originaltitle': title, 'year': year, 'imdb': imdb, 'tmdb': tmdb, 'tvdb': '0', 'next': ''})
                except:
                    pass
        except:
            pass
        items.sort(key=lambda k: k['title'].lower())
        return items


class libtvshows:
    def __init__(self):
        self.library_folder = os.path.join(control.transPath(control.setting('library.tv')),'')
        self.version = control.version()
        self.include_unknown = control.setting('library.include_unknown') or 'true'
        self.include_special = control.setting('library.include_special')
        self.library_setting = control.setting('library.update') or 'true'
        self.dupe_setting = control.setting('library.check') or 'true'
        self.datetime = datetime.datetime.utcnow()
        if control.setting('library.importdelay') != 'true':
            self.date = self.datetime.strftime('%Y%m%d')
        else:
            self.date = (self.datetime - datetime.timedelta(hours=24)).strftime('%Y%m%d')
        self.silentDialog = False
        self.infoDialog = False
        self.block = False


    def add(self, tvshowtitle, year, imdb, tmdb, range=False):
        if not control.condVisibility('Window.IsVisible(infodialog)') and not control.condVisibility('Player.HasVideo') and self.silentDialog is False:
            control.infoDialog('Adding to library...', time=10000000)
            self.infoDialog = True
        from resources.lib.indexers import episodes
        seasons = episodes.seasons().get(tvshowtitle, year, imdb, tmdb, meta=None, idx=False)
        seasons = [i['season'] for i in seasons]
        for s in seasons:
            items = episodes.episodes().get(tvshowtitle, year, imdb, tmdb, meta=None, season=s, idx=False)
            try:
                items = [{'title': i['title'], 'year': i['year'], 'imdb': i['imdb'], 'tvdb': i['tvdb'], 'tmdb': i['tmdb'], 'season': i['season'], 'episode': i['episode'], 'tvshowtitle': i['tvshowtitle'], 'premiered': i['premiered']} for i in items]
            except:
                items = []
            try:
                if not self.dupe_setting == 'true':
                    raise Exception()
                if items == []:
                    raise Exception()
                id = [items[0]['imdb'], items[0]['tmdb']]
                lib = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": {"properties" : ["imdbnumber", "title", "year"]}, "id": 1}')
                lib = six.ensure_text(lib, errors='ignore')
                lib = json.loads(lib)['result']['tvshows']
                lib = [six.ensure_str(i['title']) for i in lib if str(i['imdbnumber']) in id or (six.ensure_str(i['title']) == items[0]['tvshowtitle'] and str(i['year']) == items[0]['year'])][0]
                lib = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"filter":{"and": [{"field": "tvshow", "operator": "is", "value": "%s"}]}, "properties": ["season", "episode"]}, "id": 1}' % lib)
                lib = six.ensure_text(lib, errors='ignore')
                lib = json.loads(lib)['result']['episodes']
                lib = ['S%02dE%02d' % (int(i['season']), int(i['episode'])) for i in lib]
                items = [i for i in items if not 'S%02dE%02d' % (int(i['season']), int(i['episode'])) in lib]
                if self.include_special == 'false':
                    items = [i for i in items if not str(i['season']) == '0']
            except:
                pass
            files_added = 0
            for i in items:
                try:
                    if control.monitor.abortRequested():
                        return sys.exit()
                    premiered = i.get('premiered', '0')
                    if (premiered != '0' and int(re.sub(r'[^0-9]', '', str(premiered))) > int(self.date)) or (premiered == '0' and not self.include_unknown):
                        continue
                    self.strmFile(i)
                    files_added += 1
                except:
                    pass
        if range == True:
            return
        if self.infoDialog is True:
            control.infoDialog('Process Complete', time=1)
        if self.library_setting == 'true' and not control.condVisibility('Library.IsScanningVideo') and files_added > 0:
            control.execute('UpdateLibrary(video)')


    def silent(self, url):
        control.idle()
        if not control.condVisibility('Window.IsVisible(infodialog)') and not control.condVisibility('Player.HasVideo'):
            control.infoDialog('Auto Syncing Trakt Library', time=10000000)
            self.infoDialog = True
            self.silentDialog = True
        from resources.lib.indexers import tvshows
        items = tvshows.tvshows().get(url, idx=False)
        if items == None:
            items = []
        for i in items:
            try:
                if control.monitor.abortRequested():
                    return sys.exit()
                self.add(i['title'], i['year'], i['imdb'], i['tmdb'], range=True)
            except:
                pass
        if self.infoDialog is True:
            self.silentDialog = False
            control.infoDialog("Trakt TV Show Sync Complete", time=1)


    def range(self, url):
        control.idle()
        yes = control.yesnoDialog('Are you sure?')
        if not yes:
            return
        if not control.condVisibility('Window.IsVisible(infodialog)') and not control.condVisibility('Player.HasVideo'):
            control.infoDialog('Adding to library...', time=10000000)
            self.infoDialog = True
        from resources.lib.indexers import tvshows
        items = tvshows.tvshows().get(url, idx=False)
        if items == None:
            items = []
        for i in items:
            try:
                if control.monitor.abortRequested():
                    return sys.exit()
                self.add(i['title'], i['year'], i['imdb'], i['tmdb'], range=True)
            except:
                pass
        if self.infoDialog == True:
            control.infoDialog('Process Complete', time=1)
        if self.library_setting == 'true' and not control.condVisibility('Library.IsScanningVideo'):
            control.execute('UpdateLibrary(video)')


    def strmFile(self, i):
        try:
            title, year, imdb, tmdb, season, episode, tvshowtitle, premiered = i['title'], i['year'], i['imdb'], i['tmdb'], i['season'], i['episode'], i['tvshowtitle'], i['premiered']
            episodetitle = urllib_parse.quote_plus(cleantitle.normalize(title))
            systitle, syspremiered = urllib_parse.quote_plus(cleantitle.normalize(tvshowtitle)), urllib_parse.quote_plus(premiered)
            try:
                transtitle = tvshowtitle.translate(None, r'\/:*?"<>|')
            except:
                transtitle = tvshowtitle.translate(str.maketrans('', '', r'\/:*?"<>|'))
            transtitle = cleantitle.normalize(transtitle)
            content = '%s?action=play&title=%s&year=%s&imdb=%s&tmdb=%s&season=%s&episode=%s&tvshowtitle=%s&date=%s' % (sys.argv[0], episodetitle, year, imdb, tmdb, season, episode, systitle, syspremiered)
            folder = lib_tools.make_path(self.library_folder, transtitle, year)
            if not os.path.isfile(os.path.join(folder, 'tvshow.nfo')):
                lib_tools.create_folder(folder)
                lib_tools.write_file(os.path.join(folder, 'tvshow.nfo'), lib_tools.nfo_url('tv', i))
            folder = lib_tools.make_path(self.library_folder, transtitle, year, season)
            lib_tools.create_folder(folder)
            lib_tools.write_file(os.path.join(folder, lib_tools.legal_filename('%s S%02dE%02d' % (transtitle, int(season), int(episode))) + '.strm'), content)
        except:
            pass


    def folder_path(self, tvshowtitle, year):
        try:
            transtitle = lib_tools.normalize_folder_title(tvshowtitle)
            return lib_tools.make_path(self.library_folder, transtitle, year)
        except:
            return None


    def has(self, tvshowtitle, year, imdb=None, tmdb=None):
        try:
            folder = self.folder_path(tvshowtitle, year)
            if not folder or not os.path.isdir(folder):
                return False
            for root, dirs, files in os.walk(folder):
                if any(str(f).endswith('.strm') for f in files):
                    return True
            return False
        except:
            return False


    def _remove_kodi_tvshow(self, tvshowtitle, year, imdb, tmdb):
        try:
            imdb = 'tt' + re.sub(r'[^0-9]', '', str(imdb or ''))
            safe_title = tvshowtitle.replace('\\', '\\\\').replace('"', '\\"')
            lib = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": {"filter":{"or": [{"field": "imdbnumber", "operator": "is", "value": "%s"}, {"field": "title", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties": ["title"]}, "id": 1}' % (imdb, safe_title, year))
            lib = six.ensure_text(lib, errors='ignore')
            shows = json.loads(lib).get('result', {}).get('tvshows') or []
            for show in shows:
                control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.RemoveTVShow", "params": {"tvshowid": %s, "deletefile": true}, "id": 1}' % int(show['tvshowid']))
        except:
            pass


    def _clear_tvshow_cache(self, imdb):
        try:
            control.makeFile(control.dataPath)
            dbcon = database.connect(control.libcacheFile)
            dbcur = dbcon.cursor()
            dbcur.execute("DELETE FROM tvshows WHERE id = '%s'" % ('tt' + re.sub(r'[^0-9]', '', str(imdb))))
            dbcon.commit()
            dbcon.close()
        except:
            pass


    def remove(self, tvshowtitle, year, imdb, tmdb):
        if not self.has(tvshowtitle, year, imdb, tmdb):
            control.infoDialog('Not in your local library.', sound=True)
            return
        if not control.yesnoDialog('Remove "%s (%s)" from your local library?' % (tvshowtitle, year)):
            return
        folder = self.folder_path(tvshowtitle, year)
        self._remove_kodi_tvshow(tvshowtitle, year, imdb, tmdb)
        self._clear_tvshow_cache(imdb)
        try:
            if folder and os.path.isdir(folder):
                shutil.rmtree(folder, ignore_errors=True)
        except:
            pass
        control.infoDialog('Removed from library.', sound=True)
        if self.library_setting == 'true' and not control.condVisibility('Library.IsScanningVideo'):
            control.execute('CleanLibrary(video)')


    def refresh(self, tvshowtitle, year, imdb, tmdb):
        if not self.has(tvshowtitle, year, imdb, tmdb):
            self.add(tvshowtitle, year, imdb, tmdb)
            return
        self._clear_tvshow_cache(imdb)
        self.add(tvshowtitle, year, imdb, tmdb)
        control.infoDialog('Library item updated.', sound=True)


    def scan_local_items(self):
        items = []
        seen = set()
        try:
            for folder in control.listDir(self.library_folder)[0]:
                show_path = os.path.join(self.library_folder, folder)
                strm_path = None
                try:
                    for root, dirs, files in os.walk(show_path):
                        for filename in files:
                            if str(filename).endswith('.strm'):
                                strm_path = os.path.join(root, filename)
                                break
                        if strm_path:
                            break
                except:
                    pass
                if not strm_path:
                    continue
                try:
                    file = control.openFile(strm_path)
                    read = six.ensure_str(file.read())
                    file.close()
                    if not read.startswith(sys.argv[0]):
                        raise Exception()
                    params = dict(urllib_parse.parse_qsl(read.replace('?', '')))
                    tvshowtitle = params.get('tvshowtitle') or params.get('show') or folder
                    tvshowtitle = urllib_parse.unquote_plus(tvshowtitle)
                    year = params.get('year') or '0'
                    imdb = params.get('imdb') or '0'
                    tmdb = params.get('tmdb') or '0'
                    key = (tvshowtitle.lower(), str(year), str(imdb))
                    if key in seen:
                        continue
                    seen.add(key)
                    items.append({'title': tvshowtitle, 'year': year, 'imdb': imdb, 'tmdb': tmdb, 'tvdb': '0', 'status': 'N/A', 'next': ''})
                except:
                    pass
        except:
            pass
        items.sort(key=lambda k: k['title'].lower())
        return items


class libepisodes:
    def __init__(self):
        self.library_folder = os.path.join(control.transPath(control.setting('library.tv')),'')
        self.library_setting = control.setting('library.update') or 'true'
        self.include_unknown = control.setting('library.include_unknown') or 'true'
        self.include_special = control.setting('library.include_special')
        self.property = '%s_service_property' % control.addonInfo('name').lower()
        self.datetime = datetime.datetime.utcnow()
        if control.setting('library.importdelay') != 'true':
            self.date = self.datetime.strftime('%Y%m%d')
        else:
            self.date = (self.datetime - datetime.timedelta(hours=24)).strftime('%Y%m%d')
        self.infoDialog = False


    def update(self, query=None, info='true'):
        manual = query is not None
        if manual:
            control.idle()
        try:
            items = []
            season, episode = [], []
            show = [os.path.join(self.library_folder, i) for i in control.listDir(self.library_folder)[0]]
            for s in show:
                try:
                    season += [os.path.join(s, i) for i in control.listDir(s)[0]]
                except:
                    pass
            for s in season:
                try:
                    episode.append([os.path.join(s, i) for i in control.listDir(s)[1] if i.endswith('.strm')][-1])
                except:
                    pass
            for file in episode:
                try:
                    file = control.openFile(file)
                    read = file.read()
                    read = six.ensure_str(read)
                    file.close()
                    if not read.startswith(sys.argv[0]):
                        raise Exception()
                    params = dict(urllib_parse.parse_qsl(read.replace('?','')))
                    try:
                        tvshowtitle = params['tvshowtitle']
                    except:
                        tvshowtitle = None
                    try:
                        tvshowtitle = params['show']
                    except:
                        pass
                    if tvshowtitle == None or tvshowtitle == '':
                        raise Exception()
                    year, imdb, tmdb = params['year'], params['imdb'], params.get('tmdb', '0')
                    imdb = 'tt' + re.sub(r'[^0-9]', '', str(imdb))
                    items.append({'tvshowtitle': tvshowtitle, 'year': year, 'imdb': imdb, 'tmdb': tmdb})
                except:
                    pass
            items = [i for x, i in enumerate(items) if i not in items[x+1:]]
            if len(items) == 0:
                raise Exception()
        except:
            if manual:
                control.infoDialog('No TV library .strm files found to update.', sound=True)
                if self.library_setting == 'true' and not control.condVisibility('Library.IsScanningVideo'):
                    control.execute('UpdateLibrary(video)')
            return
        try:
            lib = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": {"properties" : ["imdbnumber", "title", "year"]}, "id": 1}')
            lib = six.ensure_text(lib, errors='ignore')
            lib = json.loads(lib)['result']['tvshows']
        except:
            if manual:
                control.infoDialog('Could not read the Kodi video library.', sound=True)
            return
        if info == 'true' and not control.condVisibility('Window.IsVisible(infodialog)') and not control.condVisibility('Player.HasVideo'):
            control.infoDialog('Updating TV shows...', time=10000000)
            self.infoDialog = True
        try:
            control.makeFile(control.dataPath)
            dbcon = database.connect(control.libcacheFile)
            dbcur = dbcon.cursor()
            dbcur.execute("CREATE TABLE IF NOT EXISTS tvshows (""id TEXT, ""items TEXT, ""UNIQUE(id)"");")
        except:
            return
        try:
            from resources.lib.indexers import episodes
        except:
            return
        files_added = 0
        self.datetime = datetime.datetime.utcnow()
        if control.setting('library.importdelay') != 'true':
            self.date = self.datetime.strftime('%Y%m%d')
        else:
            self.date = (self.datetime - datetime.timedelta(hours=24)).strftime('%Y%m%d')
        for item in items:
            it = None
            if control.monitor.abortRequested():
                return sys.exit()
            if not manual:
                try:
                    dbcur.execute("SELECT * FROM tvshows WHERE id = '%s'" % item['imdb'])
                    fetch = dbcur.fetchone()
                    it = eval(six.ensure_str(fetch[1]))
                except:
                    pass
            try:
                if not manual and not it == None:
                    raise Exception()
                seasons = episodes.seasons().get(item['tvshowtitle'], item['year'], item['imdb'], item['tmdb'], meta=None, idx=False)
                season = [i['season'] for i in seasons]
                status = (seasons[0].get('status') or '').lower() if seasons else ''
                it = []
                for s in season:
                    eps = episodes.episodes().get(item['tvshowtitle'], item['year'], item['imdb'], item['tmdb'], meta=None, season=s, idx=False) or []
                    it.extend([{'title': i['title'], 'year': i['year'], 'imdb': i['imdb'], 'tmdb': i['tmdb'], 'season': i['season'], 'episode': i['episode'], 'tvshowtitle': i['tvshowtitle'], 'premiered': i['premiered']} for i in eps])
                if not it:
                    raise Exception()
                if not manual and status in ['continuing', 'returning series']:
                    raise Exception()
                if not manual:
                    dbcur.execute("INSERT INTO tvshows Values (?, ?)", (item['imdb'], repr(it)))
                    dbcon.commit()
            except:
                pass
            try:
                id = [item['imdb'], item['tmdb']]
                ep = [six.ensure_str(x['title']) for x in lib if str(x['imdbnumber']) in id or (six.ensure_str(x['title']) == item['tvshowtitle'] and str(x['year']) == item['year'])][0]
                ep = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"filter":{"and": [{"field": "tvshow", "operator": "is", "value": "%s"}]}, "properties": ["season", "episode"]}, "id": 1}' % ep)
                ep = json.loads(ep).get('result', {}).get('episodes', {})
                ep = [{'season': int(i['season']), 'episode': int(i['episode'])} for i in ep]
                ep = sorted(ep, key=lambda x: (x['season'], x['episode']))[-1]
                num = [x for x,y in enumerate(it) if str(y['season']) == str(ep['season']) and str(y['episode']) == str(ep['episode'])][-1]
                it = [y for x,y in enumerate(it) if x > num]
                if len(it) == 0:
                    continue
            except:
                continue
            for i in it:
                try:
                    if control.monitor.abortRequested():
                        return sys.exit()
                    premiered = i.get('premiered', '0')
                    if (premiered != '0' and int(re.sub(r'[^0-9]', '', premiered)) > int(self.date)) or (premiered == '0' and not self.include_unknown):
                    #if (premiered != '0' and int(re.sub(r'[^0-9]', '', str(premiered))) > int(self.date)) or (premiered == '0' and not self.include_unknown):
                        continue
                    if i.get('season') == '0' and self.include_special == 'false':
                    #if str(i.get('season')) == '0' and self.include_special == 'false':
                        continue
                    libtvshows().strmFile(i)
                    files_added += 1
                except:
                    pass
        if self.infoDialog == True:
            control.infoDialog('Process Complete' if files_added else 'Library is up to date.', time=3000)
        elif manual:
            control.infoDialog('Added %s new episode(s).' % files_added if files_added else 'Library is up to date.', sound=True)
        if self.library_setting == 'true' and not control.condVisibility('Library.IsScanningVideo') and (files_added > 0 or manual):
            control.execute('UpdateLibrary(video)')


    def service(self):
        try:
            lib_tools.create_folder(os.path.join(control.transPath(control.setting('library.movie')), ''))
            lib_tools.create_folder(os.path.join(control.transPath(control.setting('library.tv')), ''))
        except:
            pass
        try:
            control.makeFile(control.dataPath)
            dbcon = database.connect(control.libcacheFile)
            dbcur = dbcon.cursor()
            dbcur.execute("CREATE TABLE IF NOT EXISTS service (""setting TEXT, ""value TEXT, ""UNIQUE(setting)"");")
            dbcur.execute("SELECT * FROM service WHERE setting = 'last_run'")
            fetch = dbcur.fetchone()
            if fetch == None:
                serviceProperty = "1970-01-01 23:59:00.000000"
                dbcur.execute("INSERT INTO service Values (?, ?)", ('last_run', serviceProperty))
                dbcon.commit()
            else:
                serviceProperty = str(fetch[1])
            dbcon.close()
        except:
            try:
                return dbcon.close()
            except:
                return
        try:
            control.window.setProperty(self.property, serviceProperty)
        except:
            return
        while not control.monitor.abortRequested():
            try:
                serviceProperty = control.window.getProperty(self.property)
                t1 = datetime.timedelta(hours=6)
                t2 = datetime.datetime.strptime(serviceProperty, '%Y-%m-%d %H:%M:%S.%f')
                t3 = datetime.datetime.now()
                check = abs(t3 - t2) > t1
                if check == False:
                    raise Exception()
                if (control.player.isPlaying() or control.condVisibility('Library.IsScanningVideo')):
                    raise Exception()
                serviceProperty = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                control.window.setProperty(self.property, serviceProperty)
                try:
                    dbcon = database.connect(control.libcacheFile)
                    dbcur = dbcon.cursor()
                    dbcur.execute("CREATE TABLE IF NOT EXISTS service (""setting TEXT, ""value TEXT, ""UNIQUE(setting)"");")
                    dbcur.execute("DELETE FROM service WHERE setting = 'last_run'")
                    dbcur.execute("INSERT INTO service Values (?, ?)", ('last_run', serviceProperty))
                    dbcon.commit()
                    dbcon.close()
                except:
                    try:
                        dbcon.close()
                    except:
                        pass
                if not control.setting('library.service.update') == 'true':
                    raise Exception()
                info = control.setting('library.service.notification') or 'true'
                self.update(info=info)
            except:
                pass
            control.sleep(10000)


def append_movie_library_cm(cm, sysaddon, lib, name, title, year, imdb, tmdb='0'):
    systitle = urllib_parse.quote_plus(title)
    if lib.has(title, year, imdb):
        cm.append(('Update in Library', 'RunPlugin(%s?action=movie_refresh_library&name=%s&title=%s&year=%s&imdb=%s)' % (sysaddon, name, systitle, year, imdb)))
        cm.append(('Remove from Library', 'RunPlugin(%s?action=movie_from_library&title=%s&year=%s&imdb=%s)' % (sysaddon, systitle, year, imdb)))
    else:
        cm.append(('Add to Library', 'RunPlugin(%s?action=movie_to_library&name=%s&title=%s&year=%s&imdb=%s&tmdb=%s)' % (sysaddon, name, systitle, year, imdb, tmdb)))


def append_tvshow_library_cm(cm, sysaddon, lib, tvshowtitle, year, imdb, tmdb):
    systitle = urllib_parse.quote_plus(tvshowtitle)
    if lib.has(tvshowtitle, year, imdb, tmdb):
        cm.append(('Update in Library', 'RunPlugin(%s?action=tvshow_refresh_library&tvshowtitle=%s&year=%s&imdb=%s&tmdb=%s)' % (sysaddon, systitle, year, imdb, tmdb)))
        cm.append(('Remove from Library', 'RunPlugin(%s?action=tvshow_from_library&tvshowtitle=%s&year=%s&imdb=%s&tmdb=%s)' % (sysaddon, systitle, year, imdb, tmdb)))
    else:
        cm.append(('Add to Library', 'RunPlugin(%s?action=tvshow_to_library&tvshowtitle=%s&year=%s&imdb=%s&tmdb=%s)' % (sysaddon, systitle, year, imdb, tmdb)))

