# -*- coding: utf-8 -*-

import copy
import os
import re
import sys
import threading
import time
import datetime
import random

import simplejson as json
import six
from six.moves import urllib_parse, zip, reduce

try:
    #from infotagger.listitem import ListItemInfoTag
    from resources.lib.modules.listitem import ListItemInfoTag
except:
    pass

from resources.lib.modules import cleantitle
from resources.lib.modules import client
from resources.lib.modules import control
from resources.lib.modules import scrape_sources
from resources.lib.modules import source_utils
from resources.lib.modules import trakt
from resources.lib.modules import workers
from resources.lib.modules import log_utils

try:
    from sqlite3 import dbapi2 as database
except:
    from pysqlite2 import dbapi2 as database
try:
    import resolveurl
except:
    pass


_skin_draws_percent = {}
_PLAY_ACTIVE = 'gratisred.play_active'


def _claim_play():
    """One play at a time. A second Enter must not start another scrape while the first is still starting."""
    token = '%s-%s' % (time.time(), threading.current_thread().ident or id(threading.current_thread()))
    try:
        if str(control.window.getProperty(_PLAY_ACTIVE) or ''):
            return None
        control.window.setProperty(_PLAY_ACTIVE, token)
        # Threads woken together can all pass the empty check. The last writer keeps the play.
        control.sleep(100)
        if str(control.window.getProperty(_PLAY_ACTIVE) or '') != token:
            return None
    except Exception:
        return token
    return token


def _release_play(token):
    try:
        if token and str(control.window.getProperty(_PLAY_ACTIVE) or '') == token:
            control.window.clearProperty(_PLAY_ACTIVE)
    except Exception:
        pass


# Kodi's progress dialog shows only a few lines of text, and skins size it for
# ordinary labels. A long release name with no spaces wraps onto three or four
# lines and pushes the rest of the label off the bottom of the box. The dialog
# copy of the label is fitted instead: the file name keeps its start and its end
# (quality tags, group and extension) with "..." in the middle, and any other
# line is capped. The results list itself keeps the full name.
_RESOLVE_NAME_CHARS = 94   # the release name line: about two lines of dialog text
_RESOLVE_LINE_CHARS = 48   # any other line under the first: about one line
_RESOLVE_TAGS = re.compile(r'^((?:\[/?[A-Z]+\])*)(.*?)((?:\[/?[A-Z]+\])*)$', re.S)


def _fit_middle(text, limit):
    if len(text) <= limit:
        return text
    keep = limit - 3
    head = int(keep * 0.6)
    tail = keep - head
    return text[:head] + '...' + text[-tail:]


def _fit_resolve_label(label):
    """The resolving dialog's copy of a results label, short enough to show whole."""
    try:
        lines = label.split('[CR]')
        fitted = [lines[0]]
        for index, line in enumerate(lines[1:], 1):
            match = _RESOLVE_TAGS.match(line)
            opening, text, closing = match.groups() if match else ('', line, '')
            limit = _RESOLVE_NAME_CHARS if index == 1 else _RESOLVE_LINE_CHARS
            fitted.append(opening + _fit_middle(text, limit) + closing)
        return '[CR]'.join(fitted)
    except Exception:
        return label


def _pause_resolving(seconds=0.5):
    """Close Kodi's Playback failed dialog as soon as a dead link opens it.

    That dialog uses the same skin as the resolving bar and eats the Enter meant for Cancel.
    Focus stays where it is. The busy-dialog flash is unchanged.
    """
    slices = int(max(1, round(float(seconds) / 0.1)))
    for _ in range(slices):
        control.dismiss_playback_failed()
        time.sleep(0.1)


def _xml_local(tag):
    if not tag:
        return ''
    return tag.rsplit('}', 1)[-1].lower()


def _skin_label_texts(root):
    texts = []
    for el in root.iter():
        if _xml_local(el.tag) == 'label' and el.text:
            texts.append(el.text)
    return texts


def _apply_include_params(node, params):
    if not params:
        return
    if node.text:
        for name, value in params.items():
            node.text = node.text.replace('$PARAM[%s]' % name, value)
    if node.tail:
        for name, value in params.items():
            node.tail = node.tail.replace('$PARAM[%s]' % name, value)
    for key, attr in list(node.attrib.items()):
        updated = attr
        for name, value in params.items():
            updated = updated.replace('$PARAM[%s]' % name, value)
        node.attrib[key] = updated
    for child in list(node):
        _apply_include_params(child, params)


def _expand_skin_includes(node, includes, depth=0, stack=None):
    if depth > 12 or node is None:
        return
    if stack is None:
        stack = set()
    while True:
        target = None
        for child in list(node):
            if child.get('_gr_done') or child.get('_gr_skip'):
                continue
            if _xml_local(child.tag) != 'include' or child.get('file'):
                child.set('_gr_done', '1')
                _expand_skin_includes(child, includes, depth + 1, stack)
                continue
            name = (child.get('content') or child.get('name') or (child.text or '')).strip()
            if not name or name not in includes or name in stack:
                child.set('_gr_skip', '1')
                continue
            target = (child, name)
            break
        if target is None:
            return
        child, name = target
        params = {}
        for param in list(child):
            if _xml_local(param.tag) == 'param' and param.get('name'):
                params[param.get('name')] = param.get('value') or ''
        definition = includes[name]
        body = None
        for sub in list(definition):
            if _xml_local(sub.tag) == 'definition':
                body = sub
                break
        source = list(body) if body is not None else list(definition)
        idx = list(node).index(child)
        clones = []
        for sub in source:
            if _xml_local(sub.tag) == 'param':
                continue
            clone = copy.deepcopy(sub)
            _apply_include_params(clone, params)
            clones.append(clone)
        node.remove(child)
        for offset, clone in enumerate(clones):
            node.insert(idx + offset, clone)
        stack.add(name)
        for clone in clones:
            _expand_skin_includes(clone, includes, depth + 1, stack)
        stack.discard(name)


def _load_named_includes(folder):
    import xml.etree.ElementTree as ET
    includes = {}
    if not folder or not os.path.isdir(folder):
        return includes
    pending = [name for name in os.listdir(folder) if name.lower().startswith('includes') and name.lower().endswith('.xml')]
    seen = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        path = name if os.path.isabs(name) else os.path.join(folder, name)
        if not os.path.exists(path):
            path = os.path.join(folder, os.path.basename(name))
        if not os.path.exists(path):
            continue
        try:
            root = ET.parse(path).getroot()
        except Exception:
            continue
        for inc in root.iter():
            if _xml_local(inc.tag) != 'include':
                continue
            inc_name = inc.get('name')
            if inc_name:
                includes[inc_name] = inc
            inc_file = inc.get('file')
            if inc_file and inc_file not in seen:
                pending.append(inc_file)
    return includes


def _load_skin_variables(folder):
    variables = {}
    if not folder or not os.path.isdir(folder):
        return variables
    names = [name for name in os.listdir(folder) if name.lower() in ('variables.xml',) or (name.lower().startswith('includes') and name.lower().endswith('.xml'))]
    pattern = re.compile(r'<variable\s+name="([^"]+)"[^>]*>(.*?)</variable>', re.I | re.S)
    for name in names:
        path = os.path.join(folder, name)
        try:
            with open(path, 'rb') as handle:
                raw = handle.read()
        except Exception:
            continue
        if not isinstance(raw, str):
            raw = raw.decode('utf-8', 'replace')
        for match in pattern.finditer(raw):
            variables[match.group(1)] = match.group(2)
    return variables


def _resolve_skin_vars(text, variables):
    if not text or '$VAR[' not in text:
        return text or ''

    def _replace(match):
        return variables.get(match.group(1), '')

    current = text
    for _ in range(5):
        updated = re.sub(r'\$VAR\[([^\]]+)\]', _replace, current)
        if updated == current:
            break
        current = updated
    return current


def _xml_draws_progress_percent(xml_text, folder, background):
    """True when a dialog label already prints the progress percentage."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        root = None
    if root is not None:
        try:
            _expand_skin_includes(root, _load_named_includes(folder))
        except Exception:
            pass
        labels = _skin_label_texts(root)
    else:
        labels = re.findall(r'<label(?:\s[^>]*)?>(.*?)</label>', xml_text or '', re.I | re.S)
    variables = _load_skin_variables(folder)
    blob = '\n'.join(_resolve_skin_vars(label, variables) for label in labels).lower()
    if 'system.progressbar' in blob:
        return True
    if background and 'control.getlabel(32)' in blob:
        return True
    return False


def _ordered_skin_folders(skin_root):
    import xml.etree.ElementTree as ET
    sw = sh = 0
    try:
        from kodi_six import xbmc
        sw = int(xbmc.getInfoLabel('System.ScreenWidth') or 0)
        sh = int(xbmc.getInfoLabel('System.ScreenHeight') or 0)
    except Exception:
        pass
    found = []
    try:
        root = ET.parse(os.path.join(skin_root, 'addon.xml')).getroot()
        for res in root.iter():
            if _xml_local(res.tag) != 'res':
                continue
            folder = res.get('folder') or ''
            try:
                width = int(res.get('width') or 0)
                height = int(res.get('height') or 0)
            except ValueError:
                width = height = 0
            default = (res.get('default') or '').lower() == 'true'
            found.append((folder, width, height, default))
    except Exception:
        found = []
    if not found:
        found = [(name, 0, 0, False) for name in ('xml', '16x9', '1080i', '21x9', '720p')]

    def _rank(item):
        folder, width, height, default = item
        if sw and sh and width and height:
            aspect = abs((float(width) / float(height)) - (float(sw) / float(sh)))
            size = abs(width - sw) + abs(height - sh)
            return (aspect, size, 0 if default else 1)
        return (0, 0, 0 if default else 1)

    found.sort(key=_rank)
    folders = []
    for folder, width, height, default in found:
        if folder not in folders:
            folders.append(folder)
    return folders


def _skin_dialog_xml(filename):
    skin_root = control.skinPath
    for folder in _ordered_skin_folders(skin_root):
        path = os.path.join(skin_root, folder, filename)
        if os.path.exists(path):
            return path
    estuary = control.transPath('special://xbmc/addons/skin.estuary/xml/%s' % filename)
    if estuary and os.path.exists(estuary):
        return estuary
    return None


def _skin_draws_progress_percent(background):
    key = 'bg' if background else 'fg'
    if key in _skin_draws_percent:
        return _skin_draws_percent[key]
    # Foreground progress is DialogConfirm.xml. Background is DialogExtendedProgressBar.xml.
    # Aeon Nox appends the bar percentage to the heading. Estuary's foreground bar does not.
    filename = 'DialogExtendedProgressBar.xml' if background else 'DialogConfirm.xml'
    shown = bool(background)
    try:
        path = _skin_dialog_xml(filename)
        if path:
            with open(path, 'rb') as handle:
                raw = handle.read()
            if not isinstance(raw, str):
                raw = raw.decode('utf-8', 'replace')
            shown = _xml_draws_progress_percent(raw, os.path.dirname(path), background)
    except Exception:
        log_utils.log('progress dialog skin check', 1)
    _skin_draws_percent[key] = shown
    return shown


def _resolving_bar(progressDialog, header, label, started, limit_seconds):
    """Move the resolving bar from the left while this link is tried."""
    try:
        elapsed = time.time() - started
        if limit_seconds <= 0:
            percent = 0
        else:
            percent = min(95, int((elapsed / float(limit_seconds)) * 100))
    except Exception:
        percent = 0
    try:
        progressDialog.update(percent, label)
    except Exception:
        try:
            progressDialog.update(percent, '%s[CR]%s' % (header, label))
        except Exception:
            pass


def _remember_resolving_clock(header, label, started, limit_seconds, background=False):
    """Player keeps this bar moving after the link is handed off."""
    try:
        control.window.setProperty('gratisred.resolving_header', header or '')
        control.window.setProperty('gratisred.resolving_label', label or '')
        control.window.setProperty('gratisred.resolving_started', str(started))
        control.window.setProperty('gratisred.resolving_limit', str(limit_seconds))
        control.window.setProperty('gratisred.resolving_bg', '1' if background else '0')
    except Exception:
        pass


def _providers_heading(percent, background):
    if _skin_draws_progress_percent(background):
        return 'Providers:'
    shown = min(100, max(0, int(percent)))
    return 'Providers: %d%%' % shown


class sources:
    def __init__(self):
        #control.moderator()
        self.getConstants()
        self.sources = []
        self.filtered_sources = []
        self.debug_resolve = control.setting('addon.debug_resolve')
        self.max_quality = control.setting('quality.max') or '0'
        self.max_quality = int(self.max_quality)
        self.min_quality = control.setting('quality.min') or '3'
        self.min_quality = int(self.min_quality)
        self.pre_emp = control.setting('preemptive.termination') or 'false'
        self.pre_emp_type = control.setting('preemptive.type') or '0'
        self.pre_emp_limit = int(control.setting('preemptive.limit'))
        self.sort_provider = control.setting('sort.provider') or 'true'
        self.sort_hoster = control.setting('sort.hoster') or 'true'
        self.remove_cam = control.setting('remove.cam') or 'false'
        self.remove_captcha = control.setting('remove.captcha') or 'false'
        self.remove_hevc = control.setting('remove.hevc') or 'false'
        self.remove_dupes = control.setting('remove.dupes') or 'true'
        self._filter_tvshowtitle = None
        self._filter_season = None
        self._filter_episode = None
        self._filter_year = None


    def errorForSources(self):
        control.abort_plugin_resolve()
        control.infoDialog('No Playable Sources', sound=False, icon='INFO')


    def getConstants(self):
        self.itemProperty = 'plugin.video.gratisred.container.items'
        self.metaProperty = 'plugin.video.gratisred.container.meta'
        self.sourceFile = control.providercacheFile
        from resources.lib.sources import sources
        self.sourceDict = sources()
        self.hostDict = self.getHostDict()
        self.hostcapDict = ['flashx.tv', 'flashx.to', 'uptobox.com', 'uptostream.com', 'vshare.eu', 'rabbitstream.net', 'dokicloud.one']
        self.hostblockDict = ['youtube.com', 'youtu.be', 'youtube-nocookie.com']
        self.hostDict = [x for x in self.hostDict if not x in self.hostblockDict]


    def getHostDict(self):
        try:
            hostDict = resolveurl.relevant_resolvers(order_matters=True)
            hostDict = [i.domains for i in hostDict if not '*' in i.domains]
            hostDict = [i.lower() for i in reduce(lambda x, y: x + y, hostDict)]
            hostDict = [x for y, x in enumerate(hostDict) if x not in hostDict[:y]]
            return hostDict
        except:
            log_utils.log('getHostDict', 1)
            return []


    def sourcesResolve(self, item, info=False):
        try:
            token = getattr(self, '_resolve_token', 0)
            self.url = None
            u = url = item['url']
            direct = item['direct']
            local = item.get('local', False)
            provider = item['provider']
            call = [i[1] for i in self.sourceDict if i[0] == provider][0]
            if getattr(self, '_resolve_token', 0) != token:
                return
            u = url = call.resolve(url)
            if getattr(self, '_resolve_token', 0) != token:
                return
            u = url = scrape_sources.prepare_link(url)
            if url == None or (not '://' in url and not local):
                raise Exception("url error")
            if not local:
                url = url[8:] if url.startswith('stack:') else url
                urls = []
                for part in url.split(' , '):
                    u = part
                    if not direct == True:
                        if control.setting('resolve.dbird') == 'true':
                            hmf = resolveurl.HostedMediaFile(url=u, include_disabled=True, include_universal=True)
                        else:
                            hmf = resolveurl.HostedMediaFile(url=u, include_disabled=True, include_universal=False)
                        if hmf.valid_url() == True:
                            if getattr(self, '_resolve_token', 0) != token:
                                return
                            part = hmf.resolve()
                    urls.append(part)
                url = 'stack://' + ' , '.join(urls) if len(urls) > 1 else urls[0]
            if url == False or url == None:
                raise Exception("url error")
            if getattr(self, '_resolve_token', 0) != token:
                return
            ext = url.split('?')[0].split('&')[0].split('|')[0].rsplit('.')[-1].replace('/', '').lower()
            if ext == 'rar':
                raise Exception("url error")
            try:
                headers = url.rsplit('|', 1)[1]
            except:
                headers = ''
            headers = urllib_parse.quote_plus(headers).replace('%3D', '=') if ' ' in headers else headers
            headers = dict(urllib_parse.parse_qsl(headers))
            if url.startswith('http') and '.m3u8' in url:
                try:
                    result = client.request(url.split('|')[0], headers=headers, output='geturl', timeout='10')
                except:
                    pass
            elif url.startswith('http'):
                try:
                    result = client.request(url.split('|')[0], headers=headers, output='chunk', timeout='10')
                except:
                    pass
            if getattr(self, '_resolve_token', 0) != token:
                return
            self.url = url
            return url
        except Exception as e:
            log_utils.log('Resolve failure: ({}) for url: {}'.format(e, item['url']))
            if self.debug_resolve == 'true':
                log_utils.log('sourcesResolve', 1)
            if info == True:
                self.errorForSources()
            return


    def sourcesDialog(self, items):
        try:
            labels = [i['label'] for i in items]
            select = control.selectDialog(labels)
            if select == -1:
                return 'close://'
            next = [y for x,y in enumerate(items) if x >= select]
            prev = [y for x,y in enumerate(items) if x < select][::-1]
            items = [items[select]]
            items = [i for i in items + next + prev]
            header = control.addonInfo('name') + ': Resolving...'
            progressDialog = control.open_progress(header, background=control.setting('progress.dialog') != '0')
            #progressDialog.update(0)
            block = None
            for i in range(len(items)):
                try:
                    if items[i]['source'] == block:
                        raise Exception()
                    w = workers.Thread(self.sourcesResolve, items[i])
                    w.daemon = True
                    w.start()
                    label = _fit_resolve_label(re.sub(r' {2,}', ' ', str(items[i]['label'])))
                    offset = 60 * 2 if items[i].get('source').lower() in self.hostcapDict else 0
                    limit_seconds = 0.5 * (31 + offset)
                    started = time.time()
                    m = ''
                    for x in range(3600):
                        try:
                            if control.monitor.abortRequested():
                                return sys.exit()
                            if progressDialog.iscanceled():
                                try:
                                    progressDialog.close()
                                except Exception:
                                    pass
                                return 'close://'
                        except:
                            pass
                        k = control.condVisibility('Window.IsActive(virtualkeyboard)')
                        if k:
                            m += '1'; m = m[-1]
                        if (w.is_alive() == False or x > 30 + offset) and not k:
                            break
                        k = control.condVisibility('Window.IsActive(yesnoDialog)')
                        if k:
                            m += '1'; m = m[-1]
                        if (w.is_alive() == False or x > 30 + offset) and not k:
                            break
                        _resolving_bar(progressDialog, header, label, started, limit_seconds)
                        time.sleep(0.5)
                    for x in range(30):
                        try:
                            if control.monitor.abortRequested():
                                return sys.exit()
                            if progressDialog.iscanceled():
                                try:
                                    progressDialog.close()
                                except Exception:
                                    pass
                                return 'close://'
                        except:
                            pass
                        if m == '':
                            break
                        if w.is_alive() == False:
                            break
                        _resolving_bar(progressDialog, header, label, started, limit_seconds)
                        time.sleep(0.5)
                    if w.is_alive() == True:
                        block = items[i]['source']
                    if self.url == None:
                        raise Exception()
                    self.selectedSource = items[i]['label']
                    try:
                        progressDialog.close()
                    except:
                        pass
                    control.execute('Dialog.Close(virtualkeyboard)')
                    control.execute('Dialog.Close(yesnoDialog)')
                    return self.url
                except:
                    pass
            try:
                progressDialog.close()
            except:
                pass
            del progressDialog
        except:
            try:
                progressDialog.close()
            except:
                pass
            del progressDialog
            log_utils.log('sourcesDialog', 1)


    def sourcesDirect(self, items):
        filter = [i for i in items if i['source'].lower() in self.hostcapDict]
        items = [i for i in items if not i in filter]
        items = [i for i in items if ('autoplay' in i and i['autoplay'] == True) or not 'autoplay' in i]
        if control.setting('autoplay.sd') == 'true':
            items = [i for i in items if not i['quality'].lower() in ['4k', '1080p', '720p', 'hd']]
        u = None
        canceled = False
        header = control.addonInfo('name') + ': Resolving...'
        try:
            control.sleep(1000)
            progressDialog = control.progressDialog if control.setting('progress.dialog') == '0' else control.progressDialogBG
            progressDialog.create(header, '')
            #progressDialog.update(0)
        except:
            pass
        for i in range(len(items)):
            label = _fit_resolve_label(re.sub(r' {2,}', ' ', str(items[i]['label'])))
            try:
                if progressDialog.iscanceled():
                    canceled = True
                    break
                progressDialog.update(int((100 / float(len(items))) * i), label)
            except:
                progressDialog.update(int((100 / float(len(items))) * i), str(header) + '[CR]' + label)
            try:
                if control.monitor.abortRequested():
                    return sys.exit()
                url = self.sourcesResolve(items[i])
                if u == None:
                    u = url
                if not url == None:
                    break
            except:
                pass
        try:
            progressDialog.close()
        except:
            pass
        del progressDialog
        if canceled:
            return 'close://'
        return u


    def prepareSources(self):
        try:
            control.makeFile(control.dataPath)
            dbcon = database.connect(self.sourceFile)
            dbcur = dbcon.cursor()
            dbcur.execute("CREATE TABLE IF NOT EXISTS rel_url (""source TEXT, ""imdb_id TEXT, ""season TEXT, ""episode TEXT, ""rel_url TEXT, ""UNIQUE(source, imdb_id, season, episode)"");")
            dbcur.execute("CREATE TABLE IF NOT EXISTS rel_src (""source TEXT, ""imdb_id TEXT, ""season TEXT, ""episode TEXT, ""hosts TEXT, ""added TEXT, ""UNIQUE(source, imdb_id, season, episode)"");")
        except:
            pass


    def getMovieSource(self, title, localtitle, aliases, year, imdb, tmdb, source, call):
        try:
            dbcon = database.connect(self.sourceFile)
            dbcur = dbcon.cursor()
        except:
            pass
        ''' Fix to stop items passed with a 0 IMDB id pulling old unrelated sources from the database. '''
        if imdb == '0':
            try:
                dbcur.execute("DELETE FROM rel_src WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
                dbcur.execute("DELETE FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
                dbcon.commit()
            except:
                pass
        ''' END '''
        try:
            sources = []
            dbcur.execute("SELECT * FROM rel_src WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
            match = dbcur.fetchone()
            t1 = int(re.sub(r'[^0-9]', '', str(match[5])))
            t2 = int(datetime.datetime.now().strftime("%Y%m%d%H%M"))
            update = abs(t2 - t1) > 60
            if update == False:
                sources = eval(six.ensure_str(match[4]))
                return self.sources.extend(sources)
        except:
            pass
        try:
            url = None
            dbcur.execute("SELECT * FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
            url = dbcur.fetchone()
            url = eval(six.ensure_str(url[4]))
        except:
            pass
        try:
            if url == None:
                url = call.movie(imdb, tmdb, title, localtitle, aliases, year)
            if url == None:
                raise Exception()
            dbcur.execute("DELETE FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
            dbcur.execute("INSERT INTO rel_url Values (?, ?, ?, ?, ?)", (source, imdb, '', '', repr(url)))
            dbcon.commit()
        except:
            pass
        try:
            sources = []
            sources = call.sources(url, self.hostDict)
            if sources == None or sources == []:
                raise Exception()
            sources = [json.loads(t) for t in set(json.dumps(d, sort_keys=True) for d in sources)]
            for i in sources:
                i.update({'provider': source})
            self.sources.extend(sources)
            dbcur.execute("DELETE FROM rel_src WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
            dbcur.execute("INSERT INTO rel_src Values (?, ?, ?, ?, ?, ?)", (source, imdb, '', '', repr(sources), datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
            dbcon.commit()
        except:
            pass


    def getEpisodeSource(self, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, localtvshowtitle, aliases, premiered, source, call):
        try:
            dbcon = database.connect(self.sourceFile)
            dbcur = dbcon.cursor()
        except:
            pass
        try:
            sources = []
            dbcur.execute("SELECT * FROM rel_src WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, season, episode))
            match = dbcur.fetchone()
            t1 = int(re.sub(r'[^0-9]', '', str(match[5])))
            t2 = int(datetime.datetime.now().strftime("%Y%m%d%H%M"))
            update = abs(t2 - t1) > 60
            if update == False:
                sources = eval(six.ensure_str(match[4]))
                return self.sources.extend(sources)
        except:
            pass
        try:
            url = None
            dbcur.execute("SELECT * FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
            url = dbcur.fetchone()
            url = eval(six.ensure_str(url[4]))
        except:
            pass
        try:
            if url == None:
                url = call.tvshow(imdb, tmdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year)
            if url == None:
                raise Exception()
            dbcur.execute("DELETE FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, '', ''))
            dbcur.execute("INSERT INTO rel_url Values (?, ?, ?, ?, ?)", (source, imdb, '', '', repr(url)))
            dbcon.commit()
        except:
            pass
        try:
            ep_url = None
            dbcur.execute("SELECT * FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, season, episode))
            ep_url = dbcur.fetchone()
            ep_url = eval(six.ensure_str(ep_url[4]))
        except:
            pass
        try:
            if url == None:
                raise Exception()
            if ep_url == None:
                ep_url = call.episode(url, imdb, tmdb, tvdb, title, premiered, season, episode)
            if ep_url == None:
                raise Exception()
            dbcur.execute("DELETE FROM rel_url WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, season, episode))
            dbcur.execute("INSERT INTO rel_url Values (?, ?, ?, ?, ?)", (source, imdb, season, episode, repr(ep_url)))
            dbcon.commit()
        except:
            pass
        try:
            sources = []
            sources = call.sources(ep_url, self.hostDict)
            if sources == None or sources == []:
                raise Exception()
            sources = [json.loads(t) for t in set(json.dumps(d, sort_keys=True) for d in sources)]
            for i in sources:
                i.update({'provider': source})
            self.sources.extend(sources)
            dbcur.execute("DELETE FROM rel_src WHERE source = '%s' AND imdb_id = '%s' AND season = '%s' AND episode = '%s'" % (source, imdb, season, episode))
            dbcur.execute("INSERT INTO rel_src Values (?, ?, ?, ?, ?, ?)", (source, imdb, season, episode, repr(sources), datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
            dbcon.commit()
        except:
            pass


    def uniqueSourcesGen(self, sources):
        uniqueURLs = set()
        for source in sources:
            url = source.get('url')
            if isinstance(url, six.string_types):
                url = url.replace('http://', 'https://')
                if url not in uniqueURLs:
                    uniqueURLs.add(url)
                    yield source
                else:
                    pass
            else:
                yield source


    def sourcesSort(self):
        random.shuffle(self.sources)
        local = [i for i in self.sources if 'local' in i and i['local'] == True]
        self.sources = [i for i in self.sources if not i in local]
        if self.sort_provider == 'true':
            self.sources = sorted(self.sources, key=lambda k: k['provider'])
        if self.sort_hoster == 'true':
            self.sources = sorted(self.sources, key=lambda k: k['source'])
        filter = []
        filter += local
        filter += [i for i in self.sources if i['quality'].lower() == '4k']
        filter += [i for i in self.sources if i['quality'].lower() == '1080p']
        filter += [i for i in self.sources if i['quality'].lower() == '720p']
        filter += [i for i in self.sources if i['quality'].lower() == 'hd']
        filter += [i for i in self.sources if i['quality'].lower() == 'sd']
        filter += [i for i in self.sources if i['quality'].lower() in ['scr', 'cam']]
        self.sources = filter
        self.sources = self.sources[:4000]
        double_line = control.setting('sourcelist.linesplit') == '1'
        simple = control.setting('sourcelist.linesplit') == '2'
        single_line = control.setting('sourcelist.linesplit') == '0'
        for i in range(len(self.sources)):
            u = self.sources[i]['url']
            p = self.sources[i]['provider'].replace('_', '.')
            q = self.sources[i]['quality']
            s = self.sources[i]['source']
            try:
                # A tag is one token. A line break is a description pasted onto the tags, not another row line.
                bits = []
                for info in self.sources[i].get('info', '').split('|'):
                    info = info.strip()
                    if not info or info == '0' or '\n' in info or '\r' in info:
                        continue
                    bits.append(info)
                f = ' / '.join(bits)
            except:
                f = ''
            name = ' '.join((self.sources[i].get('name') or '').split())
            if not name:
                name = source_utils.display_filename(u)
            name = ' '.join(name.split())
            if double_line:
                label = '%03d | [B]%s[/B] | %s | [B]%s[/B][CR]%s[CR]%s' % (
                    int(i + 1), q, p, s,
                    ('[I]%s[/I]' % name) if name else '',
                    ('[I]%s[/I]' % f) if f else '')
            elif simple:
                label = '%03d' % (int(i+1))
                label += ' | [B]%s[/B] | %s | [B]%s[/B]' % (q, p, s)
            else:
                label = '%03d' % (int(i+1))
                if f:
                    label += ' | [B]%s[/B] | %s | [B]%s[/B] | [I]%s[/I]' % (q, p, s, f)
                else:
                    label += ' | [B]%s[/B] | %s | [B]%s[/B] |' % (q, p, s)
            label = label.replace('[I]%s /[/I]' % f, '[I]%s[/I]' % f).replace('[I] /[/I]', '').replace('| 0 |', '|').replace(' |  |', ' |').replace('/ 0 /', '/').replace(' /  /', ' /')
            self.sources[i]['label'] = '[UPPERCASE]' + label + '[/UPPERCASE]'
        self.sources = [i for i in self.sources if 'label' in i]
        return self.sources


    def sourcesFilter(self, _content, sort=False):
        stotal = self.sources
        for i in self.sources:
            i_quality = i['quality'].lower()
            if i_quality == 'hd':
                i.update({'quality': '720p'})
            if _content == 'episode' and i_quality in ['scr', 'cam']:
                i.update({'quality': 'sd'})
            if i_quality == '4k':
                i.update({'q_filter': 0})
            elif i_quality == '1080p':
                i.update({'q_filter': 1})
            elif i_quality == '720p':
                i.update({'q_filter': 2})
            else:
                i.update({'q_filter': 3})
        self.sources = [i for i in self.sources if self.max_quality <= i.get('q_filter', 3) <= self.min_quality]
        if self.remove_cam == 'true':
            self.sources = [i for i in self.sources if not i_quality in ['scr', 'cam']]
        try:
            if self.remove_dupes == 'true' and len(self.sources) > 1:
                self.sources = list(self.uniqueSourcesGen(self.sources))
        except:
            pass
        if _content == 'episode' and self._filter_tvshowtitle:
            kept = []
            for i in self.sources:
                if (i.get('provider') or '') != 'hdhub_stremio':
                    kept.append(i)
                    continue
                hay = ' '.join(str(i.get(k) or '') for k in ('info', 'url', 'label'))
                if source_utils.episode_release_matches(
                        hay, self._filter_tvshowtitle, self._filter_season, self._filter_episode, self._filter_year):
                    kept.append(i)
            self.sources = kept
        if self.remove_hevc == 'true':
            self.sources = [i for i in self.sources if not any(x in i['url'].lower() for x in ['hevc', 'h265', 'x265', 'h.265', 'x.265']) and not any(x in i.get('info', '').lower() for x in ['hevc', 'h265', 'x265', 'h.265', 'x.265'])]
        if self.remove_captcha == 'true':
            self.sources = [i for i in self.sources if not i['source'].lower() in self.hostcapDict]
        filtered_out = [i for i in stotal if not i in self.sources]
        self.filtered_sources.extend(filtered_out)
        if sort == True:
            self.sourcesSort()
        return self.sources


    def getSources(self, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, quality='720p', timeout=30):
        self._scrape_cancelled = False
        background = control.setting('progress.dialog') != '0'
        if background:
            control.idle()
        progressDialog = control.open_progress(_providers_heading(0, background), background=background)
        self.prepareSources()
        sourceDict = self.sourceDict
        progressDialog.update(0, 'Preparing Sources...')
        content = 'movie' if tvshowtitle == None else 'episode'
        self._filter_tvshowtitle = None
        self._filter_season = None
        self._filter_episode = None
        self._filter_year = None
        if content == 'movie':
            sourceDict = [(i[0], i[1], getattr(i[1], 'movie', None)) for i in sourceDict]
            genres = trakt.getGenre('movie', 'imdb', imdb)
        else:
            sourceDict = [(i[0], i[1], getattr(i[1], 'tvshow', None)) for i in sourceDict]
            genres = trakt.getGenre('show', 'tmdb', tmdb)
        sourceDict = [(i[0], i[1], i[2]) for i in sourceDict if not hasattr(i[1], 'genre_filter') or not i[1].genre_filter or any(x in i[1].genre_filter for x in genres)]
        sourceDict = [(i[0], i[1]) for i in sourceDict if not i[2] == None]
        try:
            sourceDict = [(i[0], i[1], control.setting('provider.' + i[0])) for i in sourceDict]
        except:
            sourceDict = [(i[0], i[1], 'true') for i in sourceDict]
        sourceDict = [(i[0], i[1]) for i in sourceDict if not i[2] == 'false']
        random.shuffle(sourceDict)
        threads = []
        if content == 'movie':
            title, imdb, year = cleantitle.scene_title(title, imdb, year)
            localtitle = self.getLocalTitle(title, imdb, content)
            aliases = self.getAliasTitles(imdb, localtitle, content)
            if not any(i.get('title', '').lower() == title.lower() for i in aliases):
                aliases.append({'country': 'us', 'title': title})
            if not any(i.get('title', '').lower() == localtitle.lower() for i in aliases):
                aliases.append({'country': 'us', 'title': localtitle})
            log_utils.log('Source Searching Info = [ movie_title: ' + title + ' | localtitle: ' + localtitle + ' | year: ' + year + ' | imdb: ' + imdb + ' ]')
            #log_utils.log('Source Searching Info = [ aliases: ' + repr(aliases) + ' ]')
            for i in sourceDict:
                threads.append(workers.Thread(self.getMovieSource, title, localtitle, aliases, year, imdb, tmdb, i[0], i[1]))
        else:
            tvshowtitle, imdb, year, season, episode = cleantitle.scene_tvtitle(tvshowtitle, imdb, year, season, episode)
            self._filter_tvshowtitle = tvshowtitle
            self._filter_season = season
            self._filter_episode = episode
            self._filter_year = year
            localtvshowtitle = self.getLocalTitle(tvshowtitle, imdb, content)
            aliases = self.getAliasTitles(imdb, localtvshowtitle, content)
            if not any(i.get('title', '').lower() == tvshowtitle.lower() for i in aliases):
                aliases.append({'country': 'us', 'title': tvshowtitle})
            if not any(i.get('title', '').lower() == localtvshowtitle.lower() for i in aliases):
                aliases.append({'country': 'us', 'title': localtvshowtitle})
            log_utils.log('Source Searching Info = [ tvshow_title: ' + tvshowtitle + ' | localtvshowtitle: ' + localtvshowtitle + ' | year: ' + year + ' | imdb: ' + imdb + ' | season: ' + season + ' | episode: ' + episode + ' ]')
            #log_utils.log('Source Searching Info = [ aliases: ' + repr(aliases) + ' ]')
            for i in sourceDict:
                threads.append(workers.Thread(self.getEpisodeSource, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, localtvshowtitle, aliases, premiered, i[0], i[1]))
        s = [i[0] + (i[1],) for i in zip(sourceDict, threads)]
        s = [(i[2].getName(), i[0]) for i in s]
        sourcelabelDict = dict([(i[0], i[1].upper()) for i in s])
        [i.start() for i in threads]
        try:
            _timeout = int(control.setting('providers.timeout'))
        except:
            _timeout = timeout
        start_time = time.time()
        end_time = start_time + _timeout
        string3 = 'Remaining Providers: %s'
        source_4k = source_1080 = source_720 = source_sd = total = source_filtered_out = 0
        line1 = line2 = ""
        total_format = '[COLOR %s][B]%s[/B][/COLOR]'
        pdiag_format = ' 4K: %s | 1080P: %s | 720P: %s | SD: %s [CR] Total: %s | Filtered: %s' if not progressDialog == control.progressDialogBG else ' 4K: %s | 1080P: %s | 720P: %s | SD: %s | T: %s (F: -%s)'
        scrape_cancelled = False
        for i in range(0, 4 * _timeout):
            try:
                if control.monitor.abortRequested():
                    return sys.exit()
                try:
                    if progressDialog.iscanceled():
                        scrape_cancelled = True
                        break
                except:
                    pass
                try:
                    if progressDialog.isFinished():
                        break
                except:
                    pass
                if self.sources:
                    self.sourcesFilter(content)
                    if self.min_quality == 0:
                        source_4k = len([e for e in self.sources if e['quality'].lower() == '4k'])
                    elif self.min_quality == 1:
                        source_1080 = len([e for e in self.sources if e['quality'].lower() == '1080p'])
                        if self.max_quality == 0:
                            source_4k = len([e for e in self.sources if e['quality'].lower() == '4k'])
                    elif self.min_quality == 2:
                        source_720 = len([e for e in self.sources if e['quality'].lower() in ['720p', 'hd']])
                        if self.max_quality == 0:
                            source_4k = len([e for e in self.sources if e['quality'].lower() == '4k'])
                            source_1080 = len([e for e in self.sources if e['quality'].lower() == '1080p'])
                        elif self.max_quality == 1:
                            source_1080 = len([e for e in self.sources if e['quality'].lower() == '1080p'])
                    elif self.min_quality == 3:
                        source_sd = len([e for e in self.sources if e['quality'].lower() in ['sd', 'scr', 'cam']])
                        if self.max_quality == 0:
                            source_4k = len([e for e in self.sources if e['quality'].lower() == '4k'])
                            source_1080 = len([e for e in self.sources if e['quality'].lower() == '1080p'])
                            source_720 = len([e for e in self.sources if e['quality'].lower() in ['720p', 'hd']])
                        elif self.max_quality == 1:
                            source_1080 = len([e for e in self.sources if e['quality'].lower() == '1080p'])
                            source_720 = len([e for e in self.sources if e['quality'].lower() in ['720p', 'hd']])
                        elif self.max_quality == 2:
                            source_720 = len([e for e in self.sources if e['quality'].lower() in ['720p', 'hd']])
                    total = source_4k + source_1080 + source_720 + source_sd
                    if self.pre_emp == 'true':
                        if self.pre_emp_type == '1':
                            if total >= self.pre_emp_limit:
                                break
                        else:
                            if self.max_quality == 0:
                                if source_4k >= self.pre_emp_limit:
                                    break
                            elif self.max_quality == 1:
                                if source_1080 >= self.pre_emp_limit:
                                    break
                            elif self.max_quality == 2:
                                if source_720 >= self.pre_emp_limit:
                                    break
                            elif self.max_quality == 3:
                                if source_sd >= self.pre_emp_limit:
                                    break
                    source_filtered_out = len([e for e in self.filtered_sources])
                source_4k_label = total_format % ('darkorange', source_4k) if source_4k == 0 else total_format % ('lime', source_4k)
                source_1080_label = total_format % ('darkorange', source_1080) if source_1080 == 0 else total_format % ('lime', source_1080)
                source_720_label = total_format % ('darkorange', source_720) if source_720 == 0 else total_format % ('lime', source_720)
                source_sd_label = total_format % ('darkorange', source_sd) if source_sd == 0 else total_format % ('lime', source_sd)
                source_total_label = total_format % ('darkorange', total) if total == 0 else total_format % ('lime', total)
                source_filtered_out_label = total_format % ('darkorange', source_filtered_out) if source_filtered_out == 0 else total_format % ('lime', source_filtered_out)
                try:
                    info = [sourcelabelDict[x.getName()] for x in threads if x.is_alive() == True]
                    line1 = pdiag_format % (source_4k_label, source_1080_label, source_720_label, source_sd_label, source_total_label, source_filtered_out_label)
                    if len(info) > 5:
                        line2 = 'Remaining Providers: %s' % (str(len(info)))
                    elif len(info) > 0:
                        line2 = 'Remaining Providers: %s' % (', '.join(info).upper().replace('_', '.'))
                    else:
                        line2 = ''
                    current_time = time.time()
                    current_progress = current_time - start_time
                    percent = int((current_progress / float(_timeout)) * 100)
                    shown = min(100, max(1, percent))
                    heading = _providers_heading(shown, background)
                    stats_line = line1 if not line2 else (line1 + '[CR]' + line2)
                    if not background:
                        progressDialog.update(shown, stats_line)
                        # update() cannot change the heading. create() on a dialog
                        # that is already open only refreshes it.
                        if heading != 'Providers:':
                            progressDialog.create(heading, stats_line)
                    else:
                        progressDialog.update(shown, heading, stats_line)
                    if not info:
                        break
                    if end_time < current_time:
                        break
                except:
                    log_utils.log('getSources', 1)
                    break
                control.sleep(250)
            except:
                log_utils.log('getSources', 1)
                pass
        if progressDialog == control.progressDialogBG:
            progressDialog.close()
            if not scrape_cancelled:
                self.sourcesFilter(content, sort=True)
        else:
            if not scrape_cancelled:
                self.sourcesFilter(content, sort=True)
            progressDialog.close()
        if scrape_cancelled:
            self._scrape_cancelled = True
            control.idle()
            return []
        if self.pre_emp == 'true':
            self.sourcesFilter(content, sort=True)
        del progressDialog
        del threads
        control.idle()
        #log_utils.log('getSources self.sources: \n' + repr(self.sources))
        return self.sources


    def addItem(self, title):
        def sourcesDirMeta(metadata):
            if metadata == None:
                return metadata
            allowed = ['icon', 'poster', 'fanart', 'thumb', 'clearlogo', 'clearart', 'discart', 'title', 'year', 'tvshowtitle', 'season', 'episode', 'rating', 'plot', 'trailer', 'mediatype']
            return {k: v for k,v in six.iteritems(metadata) if k in allowed}
        control.playlist.clear()
        items = control.window.getProperty(self.itemProperty)
        items = json.loads(items)
        if items == None or len(items) == 0:
            control.idle() ; sys.exit()
        meta = control.window.getProperty(self.metaProperty)
        meta = json.loads(meta)
        meta = sourcesDirMeta(meta)
        sysaddon = sys.argv[0]
        syshandle = int(sys.argv[1])
        downloads = True if control.setting('downloads') == 'true' and not (control.setting('movie.download.path') == '' or control.setting('tv.download.path') == '') else False
        try:
            systitle = sysname = urllib_parse.quote_plus(title)
        except:
            systitle = sysname = urllib_parse.quote_plus(meta['title'])
        if 'tvshowtitle' in meta and 'season' in meta and 'episode' in meta:
            sysname += urllib_parse.quote_plus(' S%02dE%02d' % (int(meta['season']), int(meta['episode'])))
        elif 'year' in meta:
            sysname += urllib_parse.quote_plus(' (%s)' % meta['year'])
        poster = meta.get('poster') or control.addonPoster()
        thumb = meta.get('thumb') or poster
        sysimage = urllib_parse.quote_plus(six.ensure_str(poster))
        for i in range(len(items)):
            try:
                try:
                    thumb = str(items[i]['thumb'])
                except:
                    thumb = thumb
                label = str(items[i]['label'])
                syssource = urllib_parse.quote_plus(json.dumps([items[i]]))
                sysurl = '%s?action=play_item&title=%s&source=%s' % (sysaddon, systitle, syssource)
                cm = []
                if downloads == True:
                    cm.append(('DownLoad', 'RunPlugin(%s?action=download&name=%s&image=%s&source=%s)' % (sysaddon, sysname, sysimage, syssource)))
                try:
                    item = control.item(label=label, offscreen=True)
                except:
                    item = control.item(label=label)
                item.addContextMenuItems(control.context_menu_items(cm))
                item.setArt({'thumb': thumb})
                info_tag = ListItemInfoTag(item, 'video')
                info_tag.set_info({})
                control.addItem(handle=syshandle, url=sysurl, listitem=item, isFolder=False)
            except:
                pass
        control.content(syshandle, 'files')
        control.directory(syshandle, cacheToDisc=True)


    def play(self, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select):
        token = _claim_play()
        if not token:
            return
        try:
            self._play(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select)
        finally:
            _release_play(token)


    def _play(self, title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered, meta, select):
        try:
            control.clear_resolve_state()
            url = None
            items = self.getSources(title, year, imdb, tmdb, tvdb, season, episode, tvshowtitle, premiered)
            select = control.setting('hosts.mode') if select == None else select
            title = tvshowtitle if not tvshowtitle == None else title
            title = cleantitle.normalize(title)
            if getattr(self, '_scrape_cancelled', False):
                control.abort_plugin_resolve()
                return
            if len(items) > 0:
                if select == '1':
                    control.window.clearProperty(self.itemProperty)
                    control.window.setProperty(self.itemProperty, json.dumps(items))
                    control.window.clearProperty(self.metaProperty)
                    control.window.setProperty(self.metaProperty, meta)
                    control.idle()
                    return self.sourceResults(title)
                elif select == '0':
                    url = self.sourcesDialog(items)
                else:
                    url = self.sourcesDirect(items)
            if url == 'close://':
                self.url = url
                control.abort_plugin_resolve()
                return
            if url == None:
                self.url = url
                return self.errorForSources()
            try:
                meta = json.loads(meta)
            except:
                pass
            from resources.lib.modules.player import player
            player().run(title, year, season, episode, imdb, tmdb, tvdb, url, meta)
        except:
            log_utils.log('play', 1)
            control.abort_plugin_resolve()
            pass


    def playItem(self, title, source):
        token = _claim_play()
        if not token:
            return
        try:
            self._play_item(title, source)
        finally:
            _release_play(token)


    def _play_item(self, title, source):
        try:
            control.clear_resolve_state()
            meta = control.window.getProperty(self.metaProperty)
            meta = json.loads(meta)
            next = []
            prev = []
            total = []
            for i in range(1,1000):
                try:
                    u = control.infoLabel('ListItem(%s).FolderPath' % str(i))
                    if u in total:
                        raise Exception()
                    total.append(u)
                    u = dict(urllib_parse.parse_qsl(u.replace('?','')))
                    u = json.loads(u['source'])[0]
                    next.append(u)
                except:
                    break
            for i in range(-1000,0)[::-1]:
                try:
                    u = control.infoLabel('ListItem(%s).FolderPath' % str(i))
                    if u in total:
                        raise Exception()
                    total.append(u)
                    u = dict(urllib_parse.parse_qsl(u.replace('?','')))
                    u = json.loads(u['source'])[0]
                    prev.append(u)
                except:
                    break
            items = json.loads(source)
            items = [i for i in items+next+prev]
            self._resolve_and_play(title, items, meta)
        except:
            control.abort_plugin_resolve()
            pass


    def sourceResults(self, title):
        try:
            items = json.loads(control.window.getProperty(self.itemProperty) or '[]')
            meta = json.loads(control.window.getProperty(self.metaProperty) or '{}')
            if not items:
                return
            from resources.lib.modules.source_results import choose_source
            preselect = 0
            pending = []

            def _attempt(index, on_started, should_abort, on_stopped):
                ordered = [i for i in items[index:] + items[:index]]
                self._resolve_and_play(title, ordered, meta, on_started=on_started, should_abort=should_abort, on_stopped=on_stopped)

            try:
                while True:
                    control.idle()
                    chosen, early_stop, worker = choose_source(items, meta, title, preselect=preselect, on_select=_attempt)
                    if worker is not None:
                        pending.append(worker)
                    if chosen is None:
                        control.abort_plugin_resolve()
                        return
                    if early_stop:
                        preselect = chosen
                        continue
                    return
            finally:
                for pending_worker in pending:
                    pending_worker.join()
        except:
            log_utils.log('sourceResults', 1)
            control.abort_plugin_resolve()


    def _invalidate_resolve(self):
        self._resolve_token = getattr(self, '_resolve_token', 0) + 1
        self.url = None


    def _resolve_and_play(self, title, items, meta, on_started=None, should_abort=None, on_stopped=None):
        try:
            self._invalidate_resolve()
            year = meta['year'] if 'year' in meta else None
            season = meta['season'] if 'season' in meta else None
            episode = meta['episode'] if 'episode' in meta else None
            imdb = meta['imdb'] if 'imdb' in meta else None
            tvdb = meta['tvdb'] if 'tvdb' in meta else None
            tmdb = meta['tmdb'] if 'tmdb' in meta else None
            header = control.addonInfo('name') + ' : Resolving...'
            background = control.setting('progress.dialog') != '0'
            progressDialog = control.open_progress(header, background=background)
            block = None

            def _cancelled():
                # Drop the link. A slow host can keep working in the background, and
                # the token stops it from playing. The bar closes now and the list is usable.
                self._invalidate_resolve()
                try:
                    progressDialog.close()
                except Exception:
                    pass
                control.dismiss_playback_failed()
                return False

            for i in range(len(items)):
                try:
                    try:
                        if control.condVisibility('Window.IsActive(okdialog)'):
                            control.execute('Dialog.Close(okdialog)')
                    except Exception:
                        pass
                    try:
                        progress_open = control.condVisibility('Window.IsActive(progressdialog)') or control.condVisibility('Window.IsActive(progressdialogbg)')
                    except Exception:
                        progress_open = True
                    if not progress_open:
                        progressDialog.create(header, '')
                        if not background:
                            control.focus_progress_cancel()
                    label = _fit_resolve_label(re.sub(r' {2,}', ' ', str(items[i]['label'])))
                    if items[i]['source'] == block:
                        raise Exception()
                    w = workers.Thread(self.sourcesResolve, items[i])
                    # Cancel returns without this host. A non-daemon thread keeps
                    # the play script alive until the host finishes (a captcha
                    # can sit there for a while) and the next folder stays busy.
                    w.daemon = True
                    w.start()
                    offset = 60 * 2 if items[i].get('source').lower() in self.hostcapDict else 0
                    limit_seconds = 0.5 * (31 + offset)
                    started = time.time()
                    _remember_resolving_clock(header, label, started, limit_seconds, progressDialog == control.progressDialogBG)
                    m = ''
                    for x in range(3600):
                        if not background:
                            control.focus_progress_cancel()
                        stop = False
                        try:
                            if control.monitor.abortRequested():
                                return sys.exit()
                            stop = progressDialog.iscanceled() or (should_abort and should_abort())
                        except:
                            pass
                        if stop:
                            return _cancelled()
                        k = control.condVisibility('Window.IsActive(virtualkeyboard)')
                        if k:
                            m += '1'; m = m[-1]
                        if (w.is_alive() == False or x > 30 + offset) and not k:
                            break
                        k = control.condVisibility('Window.IsActive(yesnoDialog)')
                        if k:
                            m += '1'; m = m[-1]
                        if (w.is_alive() == False or x > 30 + offset) and not k:
                            break
                        _resolving_bar(progressDialog, header, label, started, limit_seconds)
                        _pause_resolving()
                    for x in range(30):
                        stop = False
                        try:
                            if control.monitor.abortRequested():
                                return sys.exit()
                            stop = progressDialog.iscanceled() or (should_abort and should_abort())
                        except:
                            pass
                        if stop:
                            return _cancelled()
                        if m == '':
                            break
                        if w.is_alive() == False:
                            break
                        _resolving_bar(progressDialog, header, label, started, limit_seconds)
                        _pause_resolving()
                    if w.is_alive() == True:
                        block = items[i]['source']
                    if self.url == None:
                        raise Exception()
                    control.execute('Dialog.Close(virtualkeyboard)')
                    control.execute('Dialog.Close(yesnoDialog)')
                    from resources.lib.modules.player import player
                    # No picture (resolve URL that Kodi cannot play) tries the next source.
                    # A picture that starts stays on that source.
                    if player().run(title, year, season, episode, imdb, tmdb, tvdb, self.url, meta, on_started=on_started, should_abort=should_abort, on_stopped=on_stopped):
                        self.url = None
                        raise Exception()
                    try:
                        progressDialog.close()
                    except Exception:
                        pass
                    return False
                except:
                    pass
            canceled = False
            try:
                canceled = progressDialog.iscanceled()
            except:
                pass
            if canceled or (should_abort and should_abort()):
                return _cancelled()
            try:
                progressDialog.close()
            except:
                pass
            del progressDialog
            # Kodi's Playback failed notice opens just after the last dead link.
            # Close that, then show this, so the end of the run is the notice that stays.
            # Do not ask IsActive here. That lookup can sit until the results window closes.
            for _ in range(12):
                try:
                    control.execute('Dialog.Close(okdialog,true)')
                    control.execute('Dialog.Close(notification,true)')
                except Exception:
                    pass
                control.sleep(100)
            control.infoDialog('No Playable Sources', sound=False, icon='INFO')
            return False
        except:
            control.abort_plugin_resolve()
            pass


    def getLocalTitle(self, title, imdb, content):
        t = trakt.getMovieTranslation(imdb, 'en') if content == 'movie' else trakt.getTVShowTranslation(imdb, 'en')
        return t or title


    def getAliasTitles(self, imdb, localtitle, content):
        try:
            t = trakt.getMovieAliases(imdb) if content == 'movie' else trakt.getTVShowAliases(imdb)
            if not t: # Ghetto fix for when the results are none so the scrape process can still be ran.
                t = []
            #t = [i for i in t if i.get('country', '').lower() in ['en', '', 'us'] and i.get('title', '').lower() != localtitle.lower()]
            # Ditched t2 so the match alias def will work how i want it lol.
            return t
        except:
            return []


    def alterSources(self, url, meta):
        try:
            if control.setting('hosts.mode') == '2':
                url += '&select=1'
            else:
                url += '&select=2'
            control.execute('RunPlugin(%s)' % url)
        except:
            pass


    def enableAll(self):
        try:
            sourceDict = self.sourceDict
            for i in sourceDict:
                source_setting = 'provider.' + i[0]
                control.setSetting(source_setting, 'true')
        except:
            pass
        control.openSettings(query='4.1')


    def disableAll(self):
        try:
            sourceDict = self.sourceDict
            for i in sourceDict:
                source_setting = 'provider.' + i[0]
                control.setSetting(source_setting, 'false')
        except:
            pass
        control.openSettings(query='4.2')


    def getProviderDomains(self):
        try:
            list = []
            text = ''
            sourceDict = sorted(self.sourceDict, key=lambda i: i[0].lower())
            log_provider_domains = control.setting('addon.log_providerdomains') or 'false'
            for i in sourceDict:
                try:
                    provider = i[0]
                    call = i[1]
                    domains = getattr(call, 'domains', None) or []
                    domains = [domain for domain in domains][:3]
                    domains_label = '[CR]-Last 3 Domains :  %s[CR]' % domains if domains else '[CR]'
                    base_link = getattr(call, 'base_link', '') or ''
                    if not base_link and domains:
                        base_link = domains[0] if str(domains[0]).startswith('http') else 'https://%s' % domains[0]
                    notes = getattr(call, 'notes', '') or ''
                    notes_label = '-Notes :  %s[CR]' % notes if notes else ''
                    scraper_label = '[B]%s :[/B]  %s%s%s' % (provider, base_link, domains_label, notes_label)
                    list.append(scraper_label)
                except:
                    continue
            for i in range(len(list)):
                text += "[CR][" + str(i+1) + "] " + list[i]
            if log_provider_domains == 'true':
                text2 = text.replace('[CR]', '\n').replace('[B]', '').replace('[/B]', '')
                log_utils.log('Provider Domains List: \n' + text2)
            control.textViewer2(text, 'Provider Domains')
        except:
            log_utils.log('getProviderDomains', 1)
            pass


