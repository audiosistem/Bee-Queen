import requests
import json
import time
from typing import Dict, List, Any, Optional, Iterable, TypedDict, Mapping, Callable
from dataclasses import dataclass, field

from .V2 import V2toV1Adapter, V2toV1ListAdapter, V2toV1FilesAdapter
from sys import version_info

if version_info >= (3, 0):
    from urllib.parse import urlparse, unquote_plus, quote
    from urllib.request import url2pathname
else:
    from urlparse import urlparse   # type: ignore
    from urllib import unquote_plus, url2pathname, quote # type: ignore

class PlayableItem(TypedDict):
    index: int
    name: str
    size: int

class FileItem(TypedDict):
    file_id: int
    path: str
    size: int

def _u(s):
    if version_info >= (3, 0):
        return s
    return unicode(s)   # type: ignore

def no_log(s):
    pass

def url2path(url):
    import urllib
    return url2pathname(urlparse(url).path)

def encode_url(s):
    return quote(s.encode('utf8'))

@dataclass
class BaseEngine(object):
    host: str
    port: int
    log: Callable
    auth: Optional[tuple]

    cache = []

    def make_url(self, path) -> str:
        return 'http://' + self.host + ':' + str(self.port) + path

    @property
    def is_v2(self):
        if 'version' not in self.__dict__:
            echo = self.echo()
            self.version = echo if echo else ()

        if self.version:
            return self.version >= (1, 2)

        raise Exception("Bad connection to torrsever")

    def request(self, name, method='POST', data=None, files=None, caching=False):

        if self.is_v2 and name == 'upload':
            url = self.make_url('/torrent/upload')
            data = {'save': True}
            result = requests.post(url, data=data, files=files, auth=self.auth)
            return result

        url = self.make_url('/torrents' if self.is_v2 else '/torrent/' + name)

        self.log(_u(url))

        if self.is_v2:
            if not data:
                data = {}
            data['action'] = name

        if data:
            data = json.dumps(data)

        import time
        now = time.time()

        timeout = 0.5
        if caching:
            for item in BaseEngine.cache[:]:
                (_method, _url, _data, _files, _now, _result) = item
                if _method == method and _url == url and _data == data and _files == files:
                    if now - _now < timeout:
                        return _result
                    else:
                        BaseEngine.cache.remove(item)

        if method=='POST':
            result = requests.post(url, data=data, files=files, auth=self.auth)
        else:
            result = requests.get(url, data=data, files=files, auth=self.auth)

        if result.ok:
            if caching:
                BaseEngine.cache.append((method, url, data, files, now, result))
            pass
        else:
            self.log('!!! Wrong request !!!')
            self.log('Error code {}'.format(result.status_code))

        return result

    def echo(self):
        url = self.make_url('/echo')
        try:
            r = requests.get(url, auth=self.auth)
        except requests.ConnectionError as e:
            self.log(_u(e))
            return False

        if r.status_code == requests.codes.ok:
            self.log(r.text)
            ver = r.text

            if ver.startswith('MatriX'):
                ver = ver.replace('MatriX', '2.0')

            ver = ver.replace('_', '.')
            ver = [int(n) for n in ver.split('.')[:3]]
            return tuple(ver)

        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            self.log(_u(e))
        except:
            pass

        return False

    def stat(self) -> Mapping[str, Any]:
        if self.is_v2:
            return V2toV1Adapter(self.request('get', data={'Hash': self.hash}, caching=True).json())    #type: ignore
        else:
            return self.request('stat', data={'Hash': self.hash}, caching=True).json()

    def get(self):
        if self.is_v2:
            return V2toV1Adapter(self.request('get', data={'Hash': self.hash}, caching=True).json())
        else:
            return self.request('get', data={'Hash': self.hash}, caching=True).json()

    def list(self) -> List[Mapping[str, Any]]:
        if self.is_v2:
            return [V2toV1ListAdapter(item) for item in self.request('list', caching=True).json()]  #type: ignore
        else:
            return self.request('list', caching=True).json()

    def restart(self):
        self.request('restart', method='GET')

    def rem(self):
        self.request('rem', data={'Hash': self.hash})

    def drop(self):
        self.request('drop', data={'Hash': self.hash})

    def upload_file(self, filename):
        files = {'file': open(filename, 'rb')}
        return self.request('upload', files=files)

    def add(self, uri, title=None, poster=None, data=None):
        params = {'Link': uri}
        if self.is_v2:
            params['save_to_db'] = True
            if title:
                params['title'] = title
            if poster:
                params['poster'] = poster
        else:
            params['DontSave'] = False
            info = {}
            if title:
                info['title'] = title
            if poster:
                info['poster_path'] = poster
            if info:
                params['Info'] = json.dumps(info, ensure_ascii=False)

        r = self.request('add', data=params)

        if self.is_v2:
            info = json.loads(r.content)
            self.hash = info['hash']
        else:
            self.hash = r.content

        if isinstance(self.hash, bytes):
            self.hash = self.hash.decode("utf-8")

        self.log('Engine add')
        self.log(self.hash)
        self.log(_u(r.headers))
        self.log(r.text)

        return r.status_code == requests.codes.ok

    def upload(self, name, data):
        files = {'file': (name, data)}

        r = self.request('upload', files=files)

        try:
            res = r.json()[0]
        except KeyError:
            res = r.json()

        self.hash = res['hash'] if self.is_v2 else res

        self.log('Engine upload')
        self.log(self.hash)
        self.log(_u(r.headers))
        self.log(r.text)

        return r.status_code == requests.codes.ok

    def search(self, s):
        ver = self.version
        if ver and ver >= (2, 0, 120):
            url = self.make_url('/search')
            res = requests.get(url, params={'query': s}, auth=self.auth)
            return res.json()
        return []

@dataclass
class Engine(BaseEngine):
    _playable_items:List[PlayableItem]

    m3u_cache = {}

    def _wait_for_data(self, timeout=10):
        self.log('_wait_for_data')
        READY_STATES = {'Torrent working', 'Torrent finished', 'Torrent in db'}
        for n in range(timeout*2):
            st = self.stat()
            try:
                self.log(st['TorrentStatusString'])

                if st['TorrentStatusString'] in READY_STATES:
                    break
                else:
                    time.sleep(0.5)
            except KeyError:
                self.log('"TorrentStatusString" not in stat')
                time.sleep(0.5)

    def __init__(self,
                uri=None,
                path=None,
                data=None,
                host='127.0.0.1',
                port=8090,
                log=no_log,
                hash=None,
                title=None,
                poster=None,
                auth=None):

        super(Engine, self).__init__(host, port, log, auth)

        self.uri = uri
        self.hash = hash
        self.success = True
        self.data = None
        self._playable_items = []

        echo = self.echo()
        self.version = echo if echo else ()
        if not self.version:
            self.success = False
            return

        if uri:
            if uri.startswith('magnet:') or uri.startswith('http:') or uri.startswith('https:'):
                self.add(uri, title, poster)
                self._wait_for_data()
                return

            if uri.startswith('file:'):
                path = url2path(uri)

        if path and not data:
            with open(path, 'rb') as f:
                data = f.read()

        if data:
            name = path or 'Torrserver engine'
            self.upload(name, data)
            self._wait_for_data()

    @property
    def playable_items(self) -> List[PlayableItem]:
        return self._get_playable_items()

    def _get_playable_items(self) -> List[PlayableItem]:

        if self._playable_items:
            return self._playable_items

        if not self.data:
            st = self.stat()
            if 'RealIdFileStats' not in st:
                raise NotImplementedError('magnet links not supported for torrent indexes, use sorted_index or name')
            if st.get('RealIdFileStats') is None:
                raise NotImplementedError('RealIdFileStats is disabled in TorrServer 1.1.77_6, please enable it')
            for i in st['RealIdFileStats']: #it only torrserver 1.1.77_6 with RealIdFileStats and &ind=
                self._playable_items.append({'index': i['Id'], 'name': i['Path'], 'size': i['Length']})
            return self._playable_items

        if version_info >= (3, 0):
            from .bencodepy import bdecode
            def _(name):
                return name.encode('ascii', 'ignore')
        else:
            from .bencode import bdecode
            def _(name):
                return name

        decoded = bdecode(self.data)

        info = decoded[_('info')]

        def _info_name() -> str:
            if _('name.utf-8') in info:
                return info[_('name.utf-8')]
            else:
                return info[_('name')]

        def f_path(f):
            if _('path.utf-8') in f:
                return f[_('path.utf-8')]
            else:
                return f[_('path')]

        def _name(name) -> str:
            import sys
            try:
                if sys.version_info < (3, 0) and isinstance(name, str):
                    return name.decode('utf-8')
                if sys.version_info >= (3, 0) and isinstance(name, bytes):
                    return name.decode('utf-8')
            except UnicodeDecodeError:
                import chardet      # type: ignore
                enc = chardet.detect(name)
                if enc and enc['confidence'] > 0.5:
                    try:
                        name = name.decode(enc['encoding'])
                    except UnicodeDecodeError:
                        pass
            return name # type: ignore

        info_name: str = _name(_info_name())
        try:
            if _('files') in info:
                for i, f in enumerate(info[_('files')]):
                    name = _name(_('/').join(f_path(f)))
                    name = u'/'.join([info_name, name]) #type: ignore
                    size = f[_('length')]

                    self._playable_items.append({'index': i, 'name': name, 'size': size})
            else:
                self._playable_items = [ {'index': 0, 'name': info_name, 'size': info[_('length')] } ]
        except UnicodeDecodeError:
            return []
        except BaseException as e:
            pass

        return self._playable_items

    def _magnet2data(self, magnet):
        self.log('-'*100)
        self.log('_magnet2data')

    def upload(self, name, data):
        self.data = data
        return BaseEngine.upload(self, name, data)

    def add(self, uri, title=None, poster=None, data=None):
        if uri.startswith('magnet:'):
            pass  # self.data = self._magnet2data(uri)
        else:
            r = requests.get(uri, auth=self.auth)
            if r.status_code == requests.codes.ok:
                self.data = r.content

        return BaseEngine.add(self, uri, title=title, poster=poster)

    def start_preload(self, url):
        def download_stream():
            req = requests.get(url, stream=True, allow_redirects=False, auth=self.auth)
            for chunk in req.iter_content(chunk_size=128):
                self.log('dowload chunk: 128')

        import threading
        t = threading.Thread(target=download_stream)
        t.start()

    def id_to_files_index(self, file_id):
        ts = self.torrent_stat()

        try:
            pi = self._get_playable_items()[file_id]
        except:
            return file_id

        files_index = 0
        for fl in ts['Files']:
            self.log(_u(fl['Name']))
            if pi['name'] == fl['Name']:
                return files_index
            files_index += 1

        return file_id

    def _start_v2(self, start_index: int):
        preload_url = self.make_url("/stream?link={}&index={}&preload".format(
            self.hash, start_index+1
        ))

        self.start_preload(preload_url)

    def _start_v1(self, start_index: int):
        for n in range(5):
            self.log('Try # {0}'.format(n))
            try:
                files = self.list()
                self.log(_u(files))

                for torrent in files:
                    if self.hash == torrent['Hash']:
                        file = torrent['Files'][start_index]
                        preload = file['Preload']

                        self.start_preload(self.make_url(preload))
                        return
                break
            except BaseException as e:
                self.log(e)
                time.sleep(0.5)
                continue

        self.log('Preload not started')

    def start(self, start_index=None):
        self.log('Engine start')

        if start_index is None:
            start_index = 0

        if self.is_v2:
            self._start_v2(start_index)
        else:
            self._start_v1(start_index)

    def _torrent_stat_v1(self):
        lst = self.list()

        for torr in lst:
            if self.hash == torr['Hash']:
                return torr

        return {}

    def torrent_stat(self) -> Mapping[str, Any]:
        if self.is_v2:
            return self.stat()
        else:
            return self._torrent_stat_v1()

    def file_stat(self, index, torrent_stat=None):
        if not torrent_stat:
            torrent_stat = self.torrent_stat()
        return torrent_stat['Files'][index]

    def files(self, torrent_stat=None) -> Iterable[FileItem]:
        if not torrent_stat:
            torrent_stat = self.torrent_stat()
        id = 0
        for f in torrent_stat['Files']:
            yield { 'file_id': id,
                    'path': f['path'] if self.is_v2 else f['Name'],
                    'size': f['length'] if self.is_v2 else f['Size'],
                    #'viewed': f['viewed'] if self.is_v2 else f['Viewed']
            }
            id += 1

    def get_ts_index(self, name) -> Optional[int]:
        def name_in_path(name, path):
            if '/' in name and '/' in path:
                return name == path
            else:
                return name.split('/')[-1] == path.split('/')[-1]

        for f in self.files():
            if name_in_path(name, f['path']):
                return f['file_id']

    def play_url(self, index, torrent_stat=None) -> str:
        try:
            fs = self.file_stat(index, torrent_stat)
            fs_id = fs['id']
            fs_path = fs['path']
        except (IndexError, KeyError):
            fs = None
            fs_id = index + 1
            fs_path = None

        if self.is_v2:
            cache = Engine.m3u_cache
            hash = self.hash
            if hash in cache:
                m3u = cache[hash]
            else:
                r = requests.get(self.make_url("/stream/?link={}&m3u".format(hash)), auth=self.auth)
                if r.status_code == requests.codes.ok:
                    m3u = r.text
                    cache[hash] = m3u
                else: m3u = ''

            if hash in cache:
                for line in m3u.splitlines():
                    if line.startswith('http://'):
                        find_str = "&index={}&".format(fs_id)
                        if find_str in line:
                            return line
                for line in m3u.splitlines():
                    if line.startswith('http://'):
                        return line
            if fs_path:
                quoted_path = encode_url(fs_path)
                return self.make_url("/stream/{}?link={}&index={}&play".format(
                                                quoted_path, hash, index+1))
            return self.make_url("/stream/?link={}&index={}&play".format(hash, index+1))

        return self.make_url(fs['Link'])

    def progress(self) -> int:
        info = self.stat()
        percent = float(info['downloaded']) * 100 / info['size']
        return percent

    def buffer_progress(self) -> int:
        st = self.stat()

        self.log(_u(st))

        stat_id = st.get('TorrentStatus', 0)

        # Fix zero preload size
        if self.is_v2:
            if stat_id > 2:
                return 100
            elif stat_id < 2:
                return 0

        preloadedBytes: int = st.get('PreloadedBytes', 0)
        preloadSize: int = st.get('PreloadSize', 0)
        if preloadSize > 0 and preloadedBytes > 0:
            prc = preloadedBytes * 100 / preloadSize
            if prc >= 100:
                prc = 100

            if prc > 0 and stat_id != 2: # 2 - 'Torrent preload'
                prc = 100
            return int(prc)

        return 0

    @property
    def title(self) -> Optional[str]:
        if self.is_v2:
            return self.stat().get('title')
        else:
            ts = self.torrent_stat()
            info = ts.get('Info')
            if info:
                info = json.loads(info)
                if info:
                    return info.get('title')

    @property
    def poster(self) -> Optional[str]:
        if self.is_v2:
            return self.stat().get('poster')
        else:
            ts = self.torrent_stat()
            info = ts.get('Info')
            if info:
                info = json.loads(info)
                if info:
                    return info.get('poster_path')

    @property
    def fanart(self) -> Optional[str]:
        if self.is_v2:
            return None # self.stat().get('fanart')
        else:
            ts = self.torrent_stat()
            info = ts.get('Info')
            if info:
                info = json.loads(info)
                if info:
                    return info.get('backdrop_path')

    @staticmethod
    def extract_hash_from_magnet(magnet) -> str:
        # 'magnet:?xt=urn:btih:3b68e98ec4522d7a2c3dae1614bb32d3e8a41155&dn=rutor.info&tr=udp%3A%2F%2Fopentor.org%3A2710&tr=udp%3A%2F%2Fopentor.org%3A2710&tr=http%3A%2F%2Fretracker.local%2Fannounce'
        result = magnet.replace('magnet:?xt=urn:btih:', '')
        result = result.split('&')[0]
        return result

    @staticmethod
    def extract_hash_from_play_url(url: str) -> Optional[str]:
        prefixes = ['torrent/view/', 'link=', 'xt=urn:btih:']

        import re
        for prefix in prefixes:
            m = re.search(prefix + r'(\w{40})', url)
            if m:
                return m.group(1)

    @staticmethod
    def extract_filename_from_play_url(url) -> Optional[str]:
        import re

        v1_pattern = r'/torrent/view/\w{40}/(.+)$'
        v2_pattern = r'/stream/(.+)\?'

        m = re.search(v2_pattern, url)
        if m:
            return unquote_plus(m.group(1))

        m = re.search(v1_pattern, url)
        if m:
            return unquote_plus(m.group(1))


    def get_art(self) -> Mapping[str, Any]:
        """ returns art """
        art = {}

        poster = self.poster
        if poster:
            art = {
                'thumb': poster,
                'poster': poster,
            }

        fanart = self.fanart
        if fanart:
            art['fanart'] = fanart

        return art

    def _get_video_info_v1(self):
        ts = self.torrent_stat()
        data = ts.get('Info')
        info = self._get_video_info_from_data(data)
        return info if info else {}

    def _get_video_info_v2(self):
        ts = self.stat()
        data = ts.get('data', {})
        info = self._get_video_info_from_data(data)
        return info if info else {} # {'title': self.title}

    def _get_video_info_from_data(self, data):
        info = json.loads(data) if data else None
        if not info:
            return {}

        video_info = {} # {'data': data}
        if 'title' in info:
            video_info = {'title': info['title']}
        if 'overview' in info:
            video_info['plot'] = info.get('overview', '')
        if 'year' in info:
            video_info['year'] = int(info.get('year'))
        if 'genres' in info:
            genres = []
            for g in info['genres']:
                genres.append(g['name'])
            if genres:
                video_info['genre'] = genres
        if 'original_title' in info:
            video_info['originaltitle'] = info.get('original_title')
        if 'vote_average' in info:
            video_info['rating'] = info.get('vote_average', 0.0)
        if 'origin_country' in info:
            country = ''
            for g in info.get('origin_country'):
                country += g + ', '
            if country: video_info['studio'] = country.strip(' ,')
        if 'runtime' in info:
            video_info['duration'] = info.get('runtime', 0) / 1000
        if 'imdb_id' in info:
            video_info['imdbnumber'] = info.get('imdb_id')
        if "media_type" in info:
            video_info['mediatype'] = info.get('media_type', '')
        if "seasons" in info and not video_info.get('mediatype'):
            video_info['mediatype'] = 'tvshow'

        created_by = info.get("created_by")
        if created_by:
            persons = []
            for person in created_by:
                persons.append(person["name"])
            video_info["director"] = persons

        production_companies = info.get("production_companies")
        if production_companies:
            companies = []
            for company in production_companies:
                companies.append(company["name"])
            video_info["studio"] = companies

        return video_info

    def get_video_info(self):
        """ returns video info """
        if self.is_v2:
            return self._get_video_info_v2()
        else:
            return self._get_video_info_v1()



if __name__ == '__main__':
    path = 'D:\\test.torrent'
    file_id = 2

    def log(s):
        with open('engine.log', 'a') as f:
            try:
                f.write(s.encode('utf-8'))
            except:
                f.write(s)
            f.write('\n')

    # host='192.168.1.5'
    #e = Engine(path=path, log=log)
    #e = Engine(uri='http://rutor.is/download/657889', log=log)
    #e = Engine(uri='magnet:?xt=urn:btih:a60f1bf7abf47af05ff8bd2b5f33fff65e7d7159&dn=rutor.info_%D0%9C%D0%B0%D0%BD%D0%B8%D1%84%D0%B5%D1%81%D1%82+%2F+%D0%94%D0%B5%D0%BA%D0%BB%D0%B0%D1%80%D0%B0%D1%86%D0%B8%D1%8F+%2F+Manifest+%5B01%D1%8501-11+%D0%B8%D0%B7+18%5D+%282018%29+WEB-DL+720p+%7C+LostFilm&tr=udp://opentor.org:2710&tr=udp://opentor.org:2710&tr=http://retracker.local/announce', log=log)

    e = Engine(path='/Users/vd/.kodi/temp/lazyf1.torrent')

    e.start()

    g = e.get()
    s = e.stat()

    while 'FileStats' not in s:
        time.sleep(0.5)
        s = e.stat()

    while True:
        try:
            st = e.stat()
            downloaded = int(st['LoadedSize'] / 1024 / 1024)
            print(downloaded)
            size = int(st['FileStats'][0]['Length'] / 1024 / 1024)
            print(size)
            dl_speed = int(st['DownloadSpeed'] / 1024)
            print(dl_speed)
            ul_speed = int(st['UploadSpeed'] / 1024)
            print(ul_speed)
            num_seeds =	st['ConnectedSeeders']
            print(num_seeds)
            num_peers =	st['ActivePeers']
            print(num_peers)

            if downloaded > size:
                break
        except:
            pass

    fstats = s['FileStats']
    item = fstats[0]
    size = int(item['Length'])

    for file_id in range(0, 8):
        play_url = e.play_url(file_id)
        log(play_url)
