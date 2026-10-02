# -*- coding: utf-8 -*-

import sys
import threading
import time

from kodi_six import xbmc
import simplejson as json
import six
from six.moves import urllib_parse

try:
    #from infotagger.listitem import ListItemInfoTag
    from resources.lib.modules.listitem import ListItemInfoTag
except:
    pass

from resources.lib.modules import bookmarks
from resources.lib.modules import control
from resources.lib.modules import cleantitle
from resources.lib.modules import playcount
from resources.lib.modules import subtitles as subtitle_service
from resources.lib.modules import simkl
from resources.lib.modules import mdblist
from resources.lib.modules import trakt

try:
    import resolveurl
except:
    pass

kodi_version = control.getKodiVersion()


def playItem(url):
    try:
        if resolveurl.HostedMediaFile(url):
            url = resolveurl.resolve(url)
        item = control.item(path=url)
        item.setProperty('IsPlayable', 'true')
        control.player.play(url, item)
    except:
        control.infoDialog('Error : No Stream Available.', sound=False, icon='INFO')
        return


def playMedia(url):
    try:
        if resolveurl.HostedMediaFile(url):
            url = resolveurl.resolve(url)
        control.execute('PlayMedia(%s)' % url)
    except:
        control.infoDialog('Error : No Stream Available.', sound=False, icon='INFO')
        return


class player(xbmc.Player):
    def __init__ (self):
        xbmc.Player.__init__(self)


    def run(self, title, year, season, episode, imdb, tmdb, tvdb, url, meta, on_started=None, should_abort=None, on_stopped=None):
        try:
            self._reopen_results = False
            self._playback_failed_fast = False
            self._resolve_cancelled = False
            self._av_started = False
            self._playback_ended = False
            self._stop_callback_done = False
            self._player_closing = False
            self._stop_lock = threading.Lock()
            self._playback_released = False
            self._notified_stopped = False
            self._on_started = on_started
            self._on_stopped = on_stopped
            self._should_abort = should_abort
            control.sleep(200)
            self.totalTime = 0
            self.currentTime = 0
            self.content = 'movie' if season == None or episode == None else 'episode'
            self.title = title
            self.year = year
            self.name = urllib_parse.quote_plus(title) + urllib_parse.quote_plus(' (%s)' % year) if self.content == 'movie' else urllib_parse.quote_plus(title) + urllib_parse.quote_plus(' S%01dE%01d' % (int(season), int(episode)))
            self.name = urllib_parse.unquote_plus(self.name)
            self.season = '%01d' % int(season) if self.content == 'episode' else None
            self.episode = '%01d' % int(episode) if self.content == 'episode' else None
            self.DBID = None
            self.imdb = imdb if not imdb == None else '0'
            self.tmdb = tmdb if not tmdb == None else '0'
            self.tvdb = tvdb if not tvdb == None else '0'
            self.ids = {'imdb': self.imdb, 'tmdb': self.tmdb, 'tvdb': self.tvdb}
            self.ids = dict((k,v) for k, v in six.iteritems(self.ids) if not v == '0')
            self._meta_duration = 0
            shelf = 0
            try:
                if isinstance(meta, dict):
                    self._meta_duration = float(meta.get('duration') or 0)
                    shelf = bookmarks.shelf_progress(meta.get('progress'))
            except Exception:
                self._meta_duration = 0
                shelf = 0
            # In Progress carries the pause on the row. That wins over a bookmark
            # from a different account. Other lists still use the bookmark.
            self._resume_from_shelf = bool(shelf)
            if shelf:
                self.offset, self.resume_percent = 0, shelf
            else:
                self.offset, self.resume_percent = bookmarks.get_resume(self.content, imdb, season, episode, tmdb=self.tmdb)
            self._simkl_scrobble_started = False
            self._mdblist_scrobble_started = False
            self._trakt_scrobble_started = False
            self._trakt_scrobble_finalized = False
            self._simkl_scrobble_finalized = False
            self._mdblist_scrobble_finalized = False
            self._trakt_pending_stop_percent = None
            self._simkl_pending_action = None
            self._simkl_pending_percent = None
            self._mdblist_pending_action = None
            self._mdblist_pending_percent = None
            # Do not seed from bookmark — failed/zero-time stops must not scrobble at stale resume %.
            self._last_percent = 0.0
            poster, thumb, fanart, clearlogo, clearart, discart, meta = self.getMeta(meta)
            if not self._meta_duration:
                try:
                    self._meta_duration = float((meta or {}).get('duration') or 0)
                except Exception:
                    pass
            item = control.item(path=url)
            if self.content == 'movie':
                item.setArt({'icon': thumb, 'thumb': thumb, 'poster': poster, 'fanart': fanart, 'clearlogo': clearlogo, 'clearart': clearart, 'discart': discart})
            else:
                item.setArt({'icon': thumb, 'thumb': thumb, 'tvshow.poster': poster, 'season.poster': poster, 'fanart': fanart, 'clearlogo': clearlogo, 'clearart': clearart})
            info_tag = ListItemInfoTag(item, 'video')
            info_tag.set_info(control.metadataClean(meta))
            # Prefer setResolvedUrl when the plugin handle expects it (Kodi 22 widgets /
            # PlayMedia). Player().play() from a plugin is unsupported and can leave the
            # original plugin:// item unresolved → "One or more items failed to play".
            played_via_resolve = False
            try:
                handle = control.plugin_handle()
                # One play click accepts one setResolvedUrl. A retry from the results window plays directly.
                already = control.window.getProperty(control.PROP_RESOLVE_DONE) == 'true'
                if handle > 0 and not already:
                    control.resolve(handle, True, item)
                    control.mark_resolve_sent()
                    played_via_resolve = True
            except Exception:
                pass
            if not played_via_resolve:
                self.play(url, item)
            control.window.setProperty('script.trakt.ids', json.dumps(self.ids))
            self.keepPlaybackAlive()
            # onPlayBackStopped only sets flags. Wait until that returns before any
            # addon/settings/window call — those deadlock CloseFile.
            if self._wait_for_stop_callback():
                self._finish_stopped_playback()
            try:
                control.window.clearProperty('script.trakt.ids')
            except Exception:
                pass
            if self._resolve_cancelled:
                return False
            return bool(self._reopen_results)
        except:
            try:
                self._simkl_scrobble_finalize()
            except Exception:
                pass
            try:
                self._mdblist_scrobble_finalize()
            except Exception:
                pass
            try:
                self._trakt_scrobble_finalize()
            except Exception:
                pass
            self._close_resolving_dialog()
            control.abort_plugin_resolve()
            return


    def getMeta(self, meta):
        try:
            poster = meta.get('poster', '') or control.addonPoster()
            thumb = meta.get('thumb', '') or poster
            fanart = meta.get('fanart', '') or control.addonFanart()
            clearlogo = meta.get('clearlogo', '') or ''
            clearart = meta.get('clearart', '') or ''
            discart = meta.get('discart', '') or ''
            return poster, thumb, fanart, clearlogo, clearart, discart, meta
        except:
            pass
        try:
            if not self.content == 'movie':
                raise Exception()
            meta = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"filter":{"or": [{"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties" : ["title", "originaltitle", "year", "genre", "studio", "country", "runtime", "rating", "votes", "mpaa", "director", "writer", "plot", "plotoutline", "tagline", "thumbnail", "file"]}, "id": 1}' % (self.year, str(int(self.year)+1), str(int(self.year)-1)))
            meta = six.ensure_text(meta, errors='ignore')
            meta = json.loads(meta)['result']['movies']
            t = cleantitle.get(self.title)
            meta = [i for i in meta if self.year == str(i['year']) and (t == cleantitle.get(i['title']) or t == cleantitle.get(i['originaltitle']))][0]
            for k, v in six.iteritems(meta):
                if type(v) == list:
                    try:
                        meta[k] = str(' / '.join([six.ensure_str(i) for i in v]))
                    except:
                        meta[k] = ''
                else:
                    try:
                        meta[k] = str(six.ensure_str(v))
                    except:
                        meta[k] = str(v)
            if not 'plugin' in control.infoLabel('Container.PluginName'):
                self.DBID = meta['movieid']
            poster = thumb = meta['thumbnail']
            return poster, thumb, '', '', '', '', meta
        except:
            pass
        try:
            if not self.content == 'episode':
                raise Exception()
            meta = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": {"filter":{"or": [{"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}, {"field": "year", "operator": "is", "value": "%s"}]}, "properties" : ["title", "year", "thumbnail", "file"]}, "id": 1}' % (self.year, str(int(self.year)+1), str(int(self.year)-1)))
            meta = six.ensure_text(meta, errors='ignore')
            meta = json.loads(meta)['result']['tvshows']
            t = cleantitle.get(self.title)
            meta = [i for i in meta if self.year == str(i['year']) and t == cleantitle.get(i['title'])][0]
            tvshowid = meta['tvshowid'] ; poster = meta['thumbnail']
            meta = control.jsonrpc('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params":{ "tvshowid": %d, "filter":{"and": [{"field": "season", "operator": "is", "value": "%s"}, {"field": "episode", "operator": "is", "value": "%s"}]}, "properties": ["title", "season", "episode", "showtitle", "firstaired", "runtime", "rating", "director", "writer", "plot", "thumbnail", "file"]}, "id": 1}' % (tvshowid, self.season, self.episode))
            meta = six.ensure_text(meta, errors='ignore')
            meta = json.loads(meta)['result']['episodes'][0]
            for k, v in six.iteritems(meta):
                if type(v) == list:
                    try:
                        meta[k] = str(' / '.join([six.ensure_str(i) for i in v]))
                    except:
                        meta[k] = ''
                else:
                    try:
                        meta[k] = str(six.ensure_str(v))
                    except:
                        meta[k] = str(v)
            if not 'plugin' in control.infoLabel('Container.PluginName'):
                self.DBID = meta['episodeid']
            thumb = meta['thumbnail']
            return poster, thumb, '', '', '', '', meta
        except:
            pass
        poster, thumb, fanart, clearlogo, clearart, discart, meta = '', '', '', '', '', '', {'title': self.name}
        return poster, thumb, fanart, clearlogo, clearart, discart, meta


    def keepPlaybackAlive(self):
        pname = '%s.player.overlay' % control.addonInfo('id')
        control.window.clearProperty(pname)
        self._tick_resolving_while_opening()
        if self.content == 'movie':
            overlay = playcount.getMovieOverlay(playcount.getMovieIndicators(), self.imdb)
        elif self.content == 'episode':
            overlay = playcount.getEpisodeOverlay(playcount.getTVShowIndicators(), self.imdb, self.tmdb, self.season, self.episode)
        else:
            overlay = '6'
        for i in range(0, 75):
            if self._playback_wait_done():
                break
            self._tick_resolving_while_opening()
            xbmc.sleep(200)
        if not self._resolve_cancelled and not self._playback_failed_fast and not (self.isPlayingVideo() and self._av_started):
            for i in range(0, 225):
                if self._playback_wait_done():
                    break
                self._tick_resolving_while_opening()
                xbmc.sleep(1000)
        # No picture: leave the resolving bar up so the next source can continue.
        # Cancel, or a picture that did start, closes it.
        unplayable = (not self._resolve_cancelled) and (self._playback_failed_fast or not self._av_started)
        if unplayable:
            self._reopen_results = True
            try:
                if control.condVisibility('Window.IsActive(busydialog)'):
                    control.execute('Dialog.Close(busydialog)')
                if control.condVisibility('Window.IsActive(busydialognocancel)'):
                    control.execute('Dialog.Close(busydialognocancel)')
                control.dismiss_playback_failed()
            except Exception:
                pass
            self._stop_opened_file()
            return
        self._close_resolving_dialog()
        if self._resolve_cancelled or not (self.isPlayingVideo() and self._av_started):
            if self._resolve_cancelled:
                self._dismiss_cancelled_playback_dialog()
            else:
                control.dismiss_playback_failed()
            self._stop_opened_file()
            return
        started = getattr(self, '_on_started', None)
        if started:
            try:
                started()
            except Exception:
                pass
        # Backup if onAVStarted never ran on this Player instance.
        if self.isPlayingVideo():
            self._ensure_live_scrobble_start()
        if overlay == '7':
            while self._playback_still_open():
                try:
                    self._sample_playback_times()
                except:
                    pass
                if not self._sleep_while_playing(2):
                    break
        elif self.content == 'movie':
            while self._playback_still_open():
                try:
                    self._sample_playback_times()
                    total = self._total_seconds()
                    watcher = total > 0 and (self.currentTime / total >= .92)
                    property = control.window.getProperty(pname)
                    if watcher == True and not property == '7':
                        control.window.setProperty(pname, '7')
                        playcount.markMovieDuringPlayback(self.imdb, '7', self.tmdb)
                except:
                    pass
                if not self._sleep_while_playing(2):
                    break
        elif self.content == 'episode':
            while self._playback_still_open():
                try:
                    self._sample_playback_times()
                    total = self._total_seconds()
                    watcher = total > 0 and (self.currentTime / total >= .92)
                    property = control.window.getProperty(pname)
                    if watcher == True and not property == '7':
                        control.window.setProperty(pname, '7')
                        playcount.markEpisodeDuringPlayback(self.imdb, self.tmdb, self.season, self.episode, '7', self.tvdb)
                except:
                    pass
                if not self._sleep_while_playing(2):
                    break


    def _sample_playback_times(self):
        if not self.isPlayingVideo():
            return
        try:
            t = self.getTotalTime()
            if t:
                self.totalTime = t
        except Exception:
            pass
        if not self.totalTime:
            self.totalTime = float(getattr(self, '_meta_duration', 0) or 0)
        if not self.isPlayingVideo():
            return
        try:
            c = self.getTime()
            if c:
                self.currentTime = c
        except Exception:
            pass
        self._update_last_percent()


    def _total_seconds(self):
        try:
            total = float(self.totalTime or 0)
        except Exception:
            total = 0
        if total <= 0 and self.isPlayingVideo():
            try:
                total = float(self.getTotalTime() or 0)
            except Exception:
                total = 0
        if total <= 0:
            total = float(getattr(self, '_meta_duration', 0) or 0)
        return total


    def _update_last_percent(self):
        try:
            total = self._total_seconds()
            current = float(self.currentTime or 0)
            if total > 0:
                self._last_percent = max(0, min(100, (current / total) * 100.0))
        except Exception:
            pass


    def _ensure_live_scrobble_start(self):
        start_pct = float(getattr(self, '_last_percent', 0) or 0) or self._playback_percent()
        if not getattr(self, '_simkl_scrobble_started', False):
            self._simkl_scrobble_started = True
            self._simkl_scrobble('start', percent=start_pct)
        if not getattr(self, '_mdblist_scrobble_started', False):
            self._mdblist_scrobble_started = True
            self._mdblist_scrobble('start', percent=start_pct)
        if not getattr(self, '_trakt_scrobble_started', False):
            self._trakt_scrobble_started = True
            self._trakt_scrobble('start', percent=start_pct)

    def _playback_folder_is_sources(self):
        """True when the visible plugin folder is the sources / play container."""
        try:
            folder = control.infoLabel('Container.FolderPath') or ''
            return any(x in folder for x in (
                'action=add_item', 'action=play_item', 'action=play_', 'action=sources'
            ))
        except Exception:
            return False


    def _refresh_after_playback_mark(self):
        """Refresh a content list after auto-mark — never the sources folder.

        After play, FolderPath is usually add_item (sources). Refreshing that
        races two listings and blanks the screen (or hard-crashes with Update).
        Episode/Library checkmarks update when the user returns to those lists.
        """
        try:
            if control.window.getProperty(playcount.PLAYBACK_MARKED_PROPERTY) != 'true':
                return
            control.window.clearProperty(playcount.PLAYBACK_MARKED_PROPERTY)
            if control.window.getProperty('gratisred.results_hold') == 'true':
                return
            if self._playback_folder_is_sources():
                return
            control.refresh()
        except Exception:
            pass


    def libForPlayback(self):
        try:
            if self.DBID == None:
                raise Exception()
            if self.content == 'movie':
                rpc = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": {"movieid" : %s, "playcount" : 1 }, "id": 1 }' % str(self.DBID)
            elif self.content == 'episode':
                rpc = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": {"episodeid" : %s, "playcount" : 1 }, "id": 1 }' % str(self.DBID)
            control.jsonrpc(rpc)
            if control.window.getProperty('gratisred.results_hold') == 'true':
                return
            if not self._playback_folder_is_sources():
                control.refresh()
        except:
            pass


    def _enter_fullscreen(self):
        try:
            if self.isPlayingVideo() and not control.condVisibility('Window.IsActive(fullscreenvideo)'):
                control.execute('ActivateWindow(fullscreenvideo)')
        except Exception:
            pass


    def idleForPlayback(self):
        for i in range(0, 400):
            if control.condVisibility('Window.IsActive(busydialog)') == 1 or control.condVisibility('Window.IsActive(busydialognocancel)') == 1:
                control.idle()
            else:
                control.idle()
                break
            control.sleep(100)


    def _resume_offset(self):
        offset = float(getattr(self, 'offset', 0) or 0)
        if offset > 120:
            return offset
        percent = float(getattr(self, 'resume_percent', 0) or 0)
        if not (1 < percent < 92):
            return 0
        total = self._total_seconds()
        if total <= 120:
            return 0
        return (percent / 100.0) * total


    def _resume_source_label(self):
        if getattr(self, '_resume_from_shelf', False):
            return ''
        source = control.setting('bookmarks.source')
        if source == '1' and trakt.getTraktCredentialsInfo() == True:
            return '[CR]  (Trakt)'
        if source == '2' and simkl.getSimklCredentialsInfo():
            return '[CR]  (Simkl)'
        return ''


    def _playback_percent(self):
        try:
            total = self._total_seconds()
            current = float(self.currentTime or 0)
            if current <= 0 and self.isPlayingVideo():
                try:
                    current = float(self.getTime() or 0)
                except Exception:
                    current = 0
            if total <= 0:
                return 0
            return max(0, min(100, (current / total) * 100.0))
        except Exception:
            return 0


    def _simkl_scrobble(self, action, percent=None, sync=False):
        if simkl.getIndicatorsProvider() != 'simkl':
            return
        if percent is None:
            percent = self._playback_percent()
        media_type = 'movie' if self.content == 'movie' else 'episode'
        args = (action, media_type, percent)
        kwargs = {
            'tmdb': self.tmdb if self.tmdb not in (None, '0') else None,
            'imdb': self.imdb if self.imdb not in (None, '0') else None,
            'season': self.season,
            'episode': self.episode,
        }
        try:
            if sync:
                simkl.simkl_scrobble(*args, **kwargs)
            else:
                threading.Thread(target=simkl.simkl_scrobble, args=args, kwargs=kwargs).start()
        except Exception:
            pass


    def _mdblist_scrobble(self, action, percent=None, sync=False):
        if simkl.getIndicatorsProvider() != 'mdblist':
            return
        if percent is None:
            percent = self._playback_percent()
        media_type = 'movie' if self.content == 'movie' else 'episode'
        args = (action, media_type, percent)
        kwargs = {
            'tmdb': self.tmdb if self.tmdb not in (None, '0') else None,
            'imdb': self.imdb if self.imdb not in (None, '0') else None,
            'season': self.season,
            'episode': self.episode,
        }
        try:
            if sync:
                mdblist.mdblist_scrobble(*args, **kwargs)
            else:
                threading.Thread(target=mdblist.mdblist_scrobble, args=args, kwargs=kwargs).start()
        except Exception:
            pass


    def _trakt_scrobble(self, action, percent=None, sync=False):
        if not trakt.getTraktIndicatorsInfo():
            return
        if percent is None:
            percent = self._playback_percent()
        # Trakt 422 on stop below 1% leaves Playing now stuck — clamp for stop.
        if action == 'stop':
            try:
                percent = float(percent or 0)
            except Exception:
                percent = 0
            if percent < 1:
                percent = 1
        media_type = 'movie' if self.content == 'movie' else 'episode'
        args = (action, media_type, percent)
        kwargs = {
            'tmdb': self.tmdb if self.tmdb not in (None, '0') else None,
            'imdb': self.imdb if self.imdb not in (None, '0') else None,
            'tvdb': self.tvdb if self.tvdb not in (None, '0') else None,
            'season': self.season,
            'episode': self.episode,
        }
        try:
            if sync:
                trakt.trakt_scrobble(*args, **kwargs)
            else:
                threading.Thread(target=trakt.trakt_scrobble, args=args, kwargs=kwargs).start()
        except Exception:
            pass


    def _trakt_scrobble_finalize(self):
        """Clear Playing now after the player has closed (safe to block briefly)."""
        if getattr(self, '_trakt_scrobble_finalized', False):
            return
        self._trakt_scrobble_finalized = True
        # Always attempt stop when Indicators=Trakt for this playback — even if start
        # callback was missed, a prior start (or stuck Playing now) still needs clearing.
        if not trakt.getTraktIndicatorsInfo():
            return
        pct = getattr(self, '_trakt_pending_stop_percent', None)
        if pct is None:
            pct = getattr(self, '_last_percent', None)
        if pct is None:
            try:
                pct = float(self._playback_percent() or 0)
            except Exception:
                pct = 1
        try:
            pct = float(pct or 0)
        except Exception:
            pct = 1
        if pct < 1:
            pct = 1
        self._trakt_scrobble('stop', percent=pct, sync=True)


    def _pending_stop_action(self, action, pct):
        if not action:
            try:
                pct = float(getattr(self, '_last_percent', 0) or 0)
            except Exception:
                pct = 0
            if pct >= 92:
                return 'stop', 100
            if pct >= 1:
                return 'pause', pct
            return None, 0
        try:
            pct = float(pct or 0)
        except Exception:
            pct = 0
        if action == 'pause' and pct < 1:
            return None, 0
        if action == 'stop' and pct < 1:
            pct = 100
        return action, pct


    def _simkl_scrobble_finalize(self):
        if getattr(self, '_simkl_scrobble_finalized', False):
            return
        self._simkl_scrobble_finalized = True
        if simkl.getIndicatorsProvider() != 'simkl':
            return
        action, pct = self._pending_stop_action(
            getattr(self, '_simkl_pending_action', None),
            getattr(self, '_simkl_pending_percent', None))
        if not action:
            return
        self._simkl_scrobble(action, percent=pct, sync=True)


    def _mdblist_scrobble_finalize(self):
        if getattr(self, '_mdblist_scrobble_finalized', False):
            return
        self._mdblist_scrobble_finalized = True
        if simkl.getIndicatorsProvider() != 'mdblist':
            return
        action, pct = self._pending_stop_action(
            getattr(self, '_mdblist_pending_action', None),
            getattr(self, '_mdblist_pending_percent', None))
        if not action:
            return
        self._mdblist_scrobble(action, percent=pct, sync=True)


    def _offer_resume(self, offset):
        if control.setting('bookmarks') != 'true' or offset <= 120 or not self.isPlayingVideo():
            return
        if control.setting('bookmarks.auto') == 'true':
            self.seekTime(float(offset))
            return
        self.pause()
        minutes, seconds = divmod(float(offset), 60)
        hours, minutes = divmod(minutes, 60)
        label = '%02d:%02d:%02d' % (hours, minutes, seconds)
        label = control.lang2(12022).format(label)
        label += self._resume_source_label()
        if kodi_version < 18:
            label = six.ensure_str(label)
        yes = control.yesnoDialog(label, heading=control.lang2(13404))
        if yes:
            self.seekTime(float(offset))
        control.sleep(1000)
        self.pause()


    def onAVStarted(self):
        if getattr(self, '_playback_released', False):
            return
        should_abort = getattr(self, '_should_abort', None)
        if getattr(self, '_resolve_cancelled', False) or (should_abort and should_abort()):
            self._resolve_cancelled = True
            self._stop_opened_file()
            return
        self._av_started = True
        # Fullscreen while the results window is still up, then let that
        # window hide. It stays open so stop does not land on the movie list.
        self._enter_fullscreen()
        xbmc.sleep(200)
        try:
            control.window.setProperty('gratisred.playback_fullscreen', 'true')
        except Exception:
            pass
        started = getattr(self, '_on_started', None)
        if started:
            try:
                started()
            except Exception:
                pass
        self._close_resolving_dialog()
        offset = self._resume_offset()
        self._offer_resume(offset)
        self._ensure_live_scrobble_start()
        subtitle_service.subtitles().get(self.imdb, self.season, self.episode, year=self.year, title=self.title)
        self.idleForPlayback()
        self._enter_fullscreen()


    def _resolving_cancelled(self):
        dialog = control.progressDialogBG if control.window.getProperty('gratisred.resolving_bg') == '1' else control.progressDialog
        try:
            return bool(dialog.iscanceled())
        except Exception:
            return False


    def _playback_wait_done(self):
        should_abort = getattr(self, '_should_abort', None)
        if should_abort and should_abort():
            self._resolve_cancelled = True
            self._stop_opened_file()
            return True
        if self._resolving_cancelled():
            self._resolve_cancelled = True
            self._stop_opened_file()
            return True
        if self._playback_failed_fast:
            return True
        return bool(self.isPlayingVideo() and self._av_started)


    def _tick_resolving_while_opening(self):
        """Keep the resolving bar moving while Kodi opens the file.

        OnPlayBackStarted puts DialogBusy over that bar until the picture starts.
        Once the picture is up, or the player is already closing, leave the dialog alone.
        """
        if self._av_started or self._player_closing:
            return
        try:
            busy = control.condVisibility('Window.IsActive(busydialog)') or control.condVisibility('Window.IsActive(busydialognocancel)')
            if control.condVisibility('Window.IsActive(busydialog)'):
                control.execute('Dialog.Close(busydialog)')
            if control.condVisibility('Window.IsActive(busydialognocancel)'):
                control.execute('Dialog.Close(busydialognocancel)')
            if busy:
                xbmc.sleep(50)
        except Exception:
            pass
        control.focus_progress_cancel()
        control.dismiss_playback_failed()
        try:
            started = float(control.window.getProperty('gratisred.resolving_started') or 0)
            limit = float(control.window.getProperty('gratisred.resolving_limit') or 0)
        except Exception:
            return
        if started <= 0 or limit <= 0:
            return
        percent = min(95, int(((time.time() - started) / limit) * 100))
        header = control.window.getProperty('gratisred.resolving_header') or ''
        label = control.window.getProperty('gratisred.resolving_label') or header
        dialog = control.progressDialogBG if control.window.getProperty('gratisred.resolving_bg') == '1' else control.progressDialog
        try:
            dialog.update(percent, label)
        except Exception:
            try:
                dialog.update(percent, '%s[CR]%s' % (header, label))
            except Exception:
                pass


    def _close_resolving_dialog(self):
        for prop in ('gratisred.resolving_header', 'gratisred.resolving_label', 'gratisred.resolving_started', 'gratisred.resolving_limit', 'gratisred.resolving_bg'):
            try:
                control.window.clearProperty(prop)
            except Exception:
                pass
        # Do not ask IsActive(progressdialog) here. After Stop that lookup sits
        # until the results window closes, and the next choice does nothing.
        for dialog in (control.progressDialog, control.progressDialogBG):
            try:
                dialog.close()
            except Exception:
                pass
        try:
            control.execute('Dialog.Close(busydialog)')
            control.execute('Dialog.Close(busydialognocancel)')
        except Exception:
            pass


    def _wait_for_stop_callback(self):
        """CloseFile owns the GUI thread for a moment. Stay out of Kodi until
        that has finished, then pump so onPlayBackStopped is delivered.

        A plain sleep never pumps that callback, so fullscreen sat on the last
        frame until the wait gave up (about five seconds).
        """
        if self._resolve_cancelled:
            return True
        time.sleep(0.25)
        for _ in range(40):
            if self._stop_callback_done:
                return True
            if self._playback_failed_fast and not self._av_started:
                return True
            xbmc.sleep(50)
        return self._stop_callback_done


    def _dismiss_cancelled_playback_dialog(self):
        """Close Kodi's Playback failed dialog after Cancel.

        It opens a moment after the file is stopped. Unlock the results first.
        Stay on this thread: a second thread querying windows left Stop unable
        to resolve again.
        """
        callback = getattr(self, '_on_stopped', None)
        if callback and not self._notified_stopped:
            self._notified_stopped = True
            try:
                callback(True)
            except Exception:
                pass
        for _ in range(15):
            try:
                control.execute('Dialog.Close(okdialog,true)')
            except Exception:
                pass
            xbmc.sleep(100)


    def _stop_opened_file(self):
        """Stop once. A second CloseFile while the first is still closing crashes Kodi."""
        lock = getattr(self, '_stop_lock', None)
        if lock is None:
            lock = threading.Lock()
            self._stop_lock = lock
        with lock:
            if self._player_closing or getattr(self, '_playback_released', False):
                return
            try:
                playing = self.isPlayingVideo()
            except Exception:
                playing = False
            if not playing:
                return
            self._player_closing = True
        try:
            self.stop()
        except Exception:
            pass


    def _playback_still_open(self):
        return (not getattr(self, '_playback_released', False)) and self.isPlayingVideo()


    def _sleep_while_playing(self, seconds):
        remaining = int(seconds * 1000)
        while remaining > 0:
            if not self._playback_still_open():
                return False
            should_abort = getattr(self, '_should_abort', None)
            if should_abort and should_abort():
                self._resolve_cancelled = True
                self._stop_opened_file()
                return False
            step = 200 if remaining > 200 else remaining
            xbmc.sleep(step)
            remaining -= step
        return self._playback_still_open()


    def _finish_stopped_playback(self):
        """Bookmarks, scrobble, and the results window. Never from onPlayBackStopped.

        Unlock the results list before scrobble. The next choice can resolve
        while those calls run, and this player ignores that later file.
        """
        self._notify_stopped()
        try:
            control.window.clearProperty('%s.player.overlay' % control.addonInfo('id'))
        except Exception:
            pass
        try:
            if self._av_started and not self._playback_failed_fast and not self._resolve_cancelled:
                percent = float(getattr(self, '_last_percent', 0) or 0)
                total = float(self.totalTime or 0) or float(getattr(self, '_meta_duration', 0) or 0)
                try:
                    bookmarks.reset(self.currentTime, total, self.content, self.imdb, self.season, self.episode)
                except Exception:
                    pass
                if percent >= 92 or self._playback_ended:
                    self.libForPlayback()
                if not getattr(self, '_on_stopped', None):
                    self._refresh_after_playback_mark()
                    if control.setting('crefresh') == 'true' and control.window.getProperty('gratisred.results_hold') != 'true' and not self._playback_folder_is_sources():
                        control.refresh()
        except Exception:
            pass
        self._simkl_scrobble_finalize()
        self._mdblist_scrobble_finalize()
        self._trakt_scrobble_finalize()


    def _notify_stopped(self):
        if self._notified_stopped:
            return
        self._notified_stopped = True
        stopped = getattr(self, '_on_stopped', None)
        if not stopped or not self._av_started or self._playback_failed_fast:
            return
        percent = float(getattr(self, '_last_percent', 0) or 0)
        ended = bool(self._playback_ended)
        try:
            stopped((not ended) and percent < 92)
        except Exception:
            pass


    def onPlayBackStarted(self):
        if getattr(self, '_playback_released', False):
            return
        if kodi_version < 18:
            self._av_started = True
            control.execute('Dialog.Close(all,true)')
            offset = self._resume_offset()
            self._offer_resume(offset)
            self._ensure_live_scrobble_start()
            subtitle_service.subtitles().get(self.imdb, self.season, self.episode, year=self.year, title=self.title)
            self.idleForPlayback()
        else:
            pass
            #self.onAVStarted()


    def onPlayBackPaused(self):
        if getattr(self, '_playback_released', False):
            return
        try:
            self._sample_playback_times()
        except Exception:
            pass
        percent = self._playback_percent() or getattr(self, '_last_percent', 0) or 0
        if 1 <= percent < 92:
            self._simkl_scrobble('pause', percent=percent)
            self._mdblist_scrobble('pause', percent=percent)
            self._trakt_scrobble('pause', percent=percent)


    def onPlayBackStopped(self):
        # Flags only. Settings, bookmarks, scrobble, and the results window run
        # from _finish_stopped_playback after this returns. Anything else here
        # runs inside CloseFile and freezes or crashes Kodi.
        # A later file must not reach this player. Kodi delivers those events
        # to every Player that is still alive.
        if getattr(self, '_playback_released', False):
            return
        self._playback_released = True
        self._player_closing = True
        try:
            if not getattr(self, '_av_started', False):
                self._playback_failed_fast = True
                return
            percent = float(getattr(self, '_last_percent', 0) or 0)
            if percent >= 92:
                self._trakt_pending_stop_percent = 100
                self._simkl_pending_action = 'stop'
                self._simkl_pending_percent = 100
                self._mdblist_pending_action = 'stop'
                self._mdblist_pending_percent = 100
            elif percent >= 1:
                self._trakt_pending_stop_percent = percent
                self._simkl_pending_action = 'pause'
                self._simkl_pending_percent = percent
                self._mdblist_pending_action = 'pause'
                self._mdblist_pending_percent = percent
            else:
                # Failed open / zero progress — clear Playing now at 1%, never bookmark resume %.
                self._trakt_pending_stop_percent = 1
        finally:
            self._stop_callback_done = True


    def onPlayBackEnded(self):
        if getattr(self, '_playback_released', False):
            return
        self._playback_ended = True
        try:
            if not self.totalTime:
                self.totalTime = float(getattr(self, '_meta_duration', 0) or 0)
            self.currentTime = self.totalTime
            self._last_percent = 100.0
        except Exception:
            pass
        self.onPlayBackStopped()

