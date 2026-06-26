# -*- coding: utf-8 -*-
"""Custom xbmc.Player subclass with:
  * 10-second stall detection -> auto-fallback to next stream candidate
  * Trakt + Bingebase + SIMKL scrobble start/pause/stop hooks
  * Resume / watched bookkeeping in addon-local SQLite store
"""
import time

import xbmc
import xbmcgui

from .common import (log, notify, get_setting_bool, get_setting_int)


class VidscrPlayer(xbmc.Player):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._media_type = None
        self._info = {}
        self._art = {}
        self._streams = []
        self._idx = 0
        self._fallback_used = False
        self._started = False
        self._last_pos = -1
        self._last_change_t = 0
        self._stop_flag = False
        self._final_position = 0
        self._final_total = 0
        self._next_up_shown = False
        self._next_up_fired = False

    # ---------------------- public API ----------------------

    def play_stream_list(self, streams, info, art, media_type='movie',
                         imdb_id=None, tmdb_id=None, season=None, episode=None,
                         build_listitem_fn=None, skip_first_play=False):
        self._streams = streams or []
        self._info = info or {}
        self._art = art or {}
        self._media_type = media_type
        self._imdb = imdb_id
        self._tmdb = tmdb_id
        self._season = season
        self._episode = episode
        self._build_li = build_listitem_fn
        self._idx = 0
        # When the caller already triggered playback via setResolvedUrl(), don't
        # call self.play() for the first stream — it would interrupt / restart.
        # The monitor still observes the existing playback and fires scrobble /
        # watched-marking events normally.
        self._skip_first_play = bool(skip_first_play)
        if not self._skip_first_play:
            self._play_current()
        else:
            log('VidscrPlayer: skip_first_play=True — observing existing playback')
        self._monitor_loop()

    # ---------------------- internals ----------------------

    def _play_current(self):
        if self._idx >= len(self._streams):
            return False
        stream = self._streams[self._idx]
        # If the caller already issued setResolvedUrl() for this first stream,
        # don't call self.play() — Kodi is already starting it. Subsequent
        # fallback streams (after a stall) DO need self.play().
        if self._idx == 0 and getattr(self, '_skip_first_play', False):
            log('VidscrPlayer: skip play() for first stream (already resolved)')
            return True
        log('VidscrPlayer: playing candidate #%d -> %s' % (self._idx + 1, stream.get('label', '')[:120]))
        try:
            li = self._build_li(stream, self._info, self._art) if self._build_li else None
            if li is not None:
                self.play(stream['url'], li)
            else:
                self.play(stream['url'])
        except Exception as e:
            log('VidscrPlayer: play() failed %s' % e)
            return False
        return True

    def _try_next(self):
        if self._idx + 1 >= len(self._streams):
            log('VidscrPlayer: no more candidates to fall back to')
            return False
        self._idx += 1
        self._fallback_used = True
        self._started = False
        self._last_pos = -1
        notify('Stream stalled — trying next link (%d/%d)...'
               % (self._idx + 1, len(self._streams)), time=3000)
        try:
            self.stop()
        except Exception:
            pass
        xbmc.sleep(800)
        return self._play_current()

    def _monitor_loop(self):
        threshold = max(get_setting_int('auto_fallback_seconds', 10), 5)
        enabled = get_setting_bool('auto_fallback', True)

        # Wait up to 30 s for playback to begin.
        wait = 0
        while not self.isPlaying() and wait < 30 and not self._stop_flag:
            xbmc.sleep(500)
            wait += 0.5

        # Start scrobble (Trakt + Bingebase + SIMKL)
        try:
            from . import trakt as TR
            TR.scrobble_start(self._media_type, imdb_id=self._imdb,
                              tmdb_id=self._tmdb,
                              season=self._season, episode=self._episode,
                              progress=0.0)
        except Exception as e:
            log('Trakt scrobble_start failed: %s' % e)
        try:
            from . import bingebase as BB
            BB.scrobble_start(self._media_type, imdb_id=self._imdb,
                              tmdb_id=self._tmdb,
                              season=self._season, episode=self._episode,
                              progress=0.0,
                              duration=int(self._final_total or 0),
                              position=int(self._final_position or 0),
                              title=(self._info or {}).get('title', ''),
                              tv_show_title=(self._info or {}).get('tvshowtitle', ''))
        except Exception as e:
            log('Bingebase scrobble_start failed: %s' % e)
        try:
            from . import simkl as SK
            SK.scrobble_start(self._media_type, imdb_id=self._imdb,
                              tmdb_id=self._tmdb,
                              season=self._season, episode=self._episode,
                              progress=0.0)
        except Exception as e:
            log('SIMKL scrobble_start failed: %s' % e)

        last_check = time.time()
        self._last_change_t = time.time()

        while self.isPlaying() and not self._stop_flag:
            xbmc.sleep(1000)
            try:
                pos = int(self.getTime())
                total = int(self.getTotalTime() or 0)
            except Exception:
                pos = self._last_pos
                total = 0

            if pos != self._last_pos:
                self._last_pos = pos
                self._last_change_t = time.time()

            self._final_position = pos
            self._final_total = total

            # ---- Smart Next-Up (TV only) ----
            if (self._media_type == 'tv'
                    and not self._next_up_shown
                    and get_setting_bool('smart_next_up_enabled', True)
                    and total > 0
                    and self._started):
                lead = max(get_setting_int('smart_next_up_seconds', 90), 20)
                if (total - pos) <= lead and (total - pos) > 5:
                    self._next_up_shown = True
                    try:
                        self._offer_next_up()
                    except Exception as nue:
                        log('Next-Up failed: %s' % nue)

            # Stall detection — only before "started" state set, OR if we have
            # not progressed for `threshold` seconds while not paused.
            if enabled and not self._fallback_used:
                stalled_for = time.time() - self._last_change_t
                if not self._started and stalled_for > threshold:
                    log('VidscrPlayer: stall (no start) for %.1fs — fallback'
                        % stalled_for)
                    if self._try_next():
                        return self._monitor_loop()
                    break

        # Final scrobble stop (each tracker isolated so a failure in one does
        # NOT block local watched marking via KDB.record_progress).
        progress = 0.0
        if self._final_total:
            try:
                progress = (self._final_position / self._final_total) * 100.0
            except Exception:
                progress = 0.0
        try:
            from . import trakt as TR
            TR.scrobble_stop(self._media_type, imdb_id=self._imdb,
                             tmdb_id=self._tmdb,
                             season=self._season, episode=self._episode,
                             progress=progress)
        except Exception as e:
            log('Trakt scrobble_stop failed: %s' % e)
        try:
            from . import bingebase as BB
            BB.scrobble_stop(self._media_type, imdb_id=self._imdb,
                             tmdb_id=self._tmdb,
                             season=self._season, episode=self._episode,
                             progress=progress,
                             duration=int(self._final_total or 0),
                             position=int(self._final_position or 0),
                             title=(self._info or {}).get('title', ''),
                             tv_show_title=(self._info or {}).get('tvshowtitle', ''))
        except Exception as be:
            log('Bingebase scrobble_stop failed: %s' % be)
        try:
            from . import simkl as SK
            SK.scrobble_stop(self._media_type, imdb_id=self._imdb,
                             tmdb_id=self._tmdb,
                             season=self._season, episode=self._episode,
                             progress=progress)
        except Exception as se:
            log('SIMKL scrobble_stop failed: %s' % se)
        try:
            from . import kodi_db as KDB
            KDB.record_progress(self._media_type, imdb=self._imdb, tmdb=self._tmdb,
                                season=self._season, episode=self._episode,
                                position=self._final_position,
                                total=self._final_total)
            log('VidscrPlayer: KDB.record_progress saved (pos=%s total=%s pct=%.1f)'
                % (self._final_position, self._final_total, progress))
        except Exception as e:
            log('VidscrPlayer: KDB.record_progress failed: %s' % e)

    # ---------------------- xbmc.Player callbacks ----------------------

    def onAVStarted(self):
        self._started = True
        self._last_change_t = time.time()
        log('VidscrPlayer: AV started')

    def onPlayBackPaused(self):
        try:
            from . import trakt as TR
            progress = 0.0
            if self._final_total:
                progress = (self._final_position / self._final_total) * 100.0
            TR.scrobble_pause(self._media_type, imdb_id=self._imdb,
                              tmdb_id=self._tmdb,
                              season=self._season, episode=self._episode,
                              progress=progress)
            try:
                from . import bingebase as BB
                BB.scrobble_pause(self._media_type, imdb_id=self._imdb,
                                  tmdb_id=self._tmdb,
                                  season=self._season, episode=self._episode,
                                  progress=progress,
                                  duration=int(self._final_total or 0),
                                  position=int(self._final_position or 0),
                                  title=(self._info or {}).get('title', ''),
                                  tv_show_title=(self._info or {}).get('tvshowtitle', ''))
            except Exception:
                pass
            try:
                from . import simkl as SK
                SK.scrobble_pause(self._media_type, imdb_id=self._imdb,
                                  tmdb_id=self._tmdb,
                                  season=self._season, episode=self._episode,
                                  progress=progress)
            except Exception:
                pass
        except Exception:
            pass

    def onPlayBackResumed(self):
        try:
            from . import trakt as TR
            progress = 0.0
            if self._final_total:
                progress = (self._final_position / self._final_total) * 100.0
            TR.scrobble_start(self._media_type, imdb_id=self._imdb,
                              tmdb_id=self._tmdb,
                              season=self._season, episode=self._episode,
                              progress=progress)
            try:
                from . import bingebase as BB
                BB.scrobble_start(self._media_type, imdb_id=self._imdb,
                                  tmdb_id=self._tmdb,
                                  season=self._season, episode=self._episode,
                                  progress=progress,
                                  duration=int(self._final_total or 0),
                                  position=int(self._final_position or 0),
                                  title=(self._info or {}).get('title', ''),
                                  tv_show_title=(self._info or {}).get('tvshowtitle', ''))
            except Exception:
                pass
            try:
                from . import simkl as SK
                SK.scrobble_start(self._media_type, imdb_id=self._imdb,
                                  tmdb_id=self._tmdb,
                                  season=self._season, episode=self._episode,
                                  progress=progress)
            except Exception:
                pass
        except Exception:
            pass

    def onPlayBackEnded(self):
        self._stop_flag = True

    def onPlayBackStopped(self):
        self._stop_flag = True

    def onPlayBackError(self):
        log('VidscrPlayer: playback error — attempting fallback')
        if not self._fallback_used:
            self._try_next()
        else:
            self._stop_flag = True

    # ---------------------- Smart Next-Up (TV) ----------------------

    def _offer_next_up(self):
        """At ~90s from the end of an episode, show a non-blocking dialog
        offering to play the next episode. Auto-confirms after the countdown
        unless the user cancels.
        """
        if not self._tmdb or self._season is None or self._episode is None:
            return
        from . import tmdb as T
        try:
            season_data = T.tv_season(self._tmdb, int(self._season))
        except Exception:
            season_data = {}
        eps = season_data.get('episodes') or []
        next_s, next_e = int(self._season), int(self._episode) + 1
        has_next = any(int(e.get('episode_number') or 0) == next_e for e in eps)
        if not has_next:
            # Try first episode of next season.
            try:
                show = T.tv_details(self._tmdb)
                seasons = [int((s.get('season_number') or 0))
                           for s in (show.get('seasons') or [])]
                if (int(self._season) + 1) in seasons:
                    next_s = int(self._season) + 1
                    next_e = 1
                    has_next = True
            except Exception:
                pass
        if not has_next:
            return

        msg = 'Next: S%02dE%02d — auto-play in %ds' % (
            next_s, next_e, max(get_setting_int('smart_next_up_seconds', 90), 20))
        # Non-modal: use a short dialog with yes/no + an auto-accept timer.
        dlg = xbmcgui.Dialog()
        play_now = dlg.yesno(
            'Smart Next-Up',
            msg,
            nolabel='Cancel',
            yeslabel='Play now',
            autoclose=max(get_setting_int('smart_next_up_seconds', 90), 20) * 1000,
        )
        # Kodi returns True on yes OR on autoclose-timeout; returns False on
        # explicit cancel. So both "Play now" and "do nothing" fire the next
        # episode; only "Cancel" skips it.
        if not play_now:
            return
        if self._next_up_fired:
            return
        self._next_up_fired = True
        try:
            self.stop()
        except Exception:
            pass
        xbmc.sleep(500)
        from .common import build_url
        url = build_url(action='play_episode',
                        tmdb_id=self._tmdb,
                        season=next_s, episode=next_e,
                        title=(self._info or {}).get('tvshowtitle', ''))
        xbmc.executebuiltin('PlayMedia(%s)' % url)
