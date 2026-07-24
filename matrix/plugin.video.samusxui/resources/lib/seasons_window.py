# -*- coding: utf-8 -*-
import threading
import xbmc
import xbmcgui
import xbmcaddon

from . import tmdb

ADDON_PATH = xbmcaddon.Addon('plugin.video.samusxui').getAddonInfo('path')

_ID_HEADER  = 5
_ID_BACKDROP = 100
_ID_LOGO    = 115
_ID_TITLE   = 110
_ID_META    = 111
_ID_PLOT    = 113
_ID_PLAY    = 120
_ID_DETAILS = 122
_ID_POSTERS = 131
_ID_EMPTY   = 150

ACTION_NAV_BACK   = 10
ACTION_PREV_MENU  = 92
ACTION_MOVE_LEFT  = 1
ACTION_MOVE_RIGHT = 2


class SeasonsWindow(xbmcgui.WindowXML):

    def __init__(self, *args, **kwargs):
        self._tv_id    = None
        self._show     = {}
        self._seasons  = []
        self._hero_idx = 0
        self._logo_set = False

    def onInit(self):
        show_name = self._show.get('name', '')
        try:
            self.getControl(_ID_HEADER).setLabel(
                f'[COLOR FF7B5CF4]←[/COLOR]  {show_name}')
        except Exception:
            pass
        self._populate()

    # ------------------------------------------------------------------ populate

    def _populate(self):
        self._seasons = self._show.get('seasons', [])
        ctrl = self.getControl(_ID_POSTERS)
        ctrl.reset()
        if not self._seasons:
            try:
                self.getControl(_ID_EMPTY).setLabel('Nu s-au găsit sezoane.')
                self.getControl(_ID_EMPTY).setVisible(True)
            except Exception:
                pass
            for cid in (_ID_PLAY, _ID_DETAILS, _ID_POSTERS):
                try:
                    self.getControl(cid).setVisible(False)
                except Exception:
                    pass
            return
        try:
            self.getControl(_ID_EMPTY).setVisible(False)
        except Exception:
            pass
        for s in self._seasons:
            poster = tmdb.poster_url(s.get('poster_path', ''))
            name = s.get('name') or f"Sezonul {s.get('season_number', '')}"
            li = xbmcgui.ListItem(name)
            li.setArt({'thumb': poster})
            ctrl.addItem(li)
        ctrl.selectItem(0)
        self._update_hero(0)
        self.setFocusId(_ID_POSTERS)
        if self._tv_id:
            threading.Thread(
                target=self._fetch_logo, args=(self._tv_id,), daemon=True).start()

    # ------------------------------------------------------------------ hero

    def _update_hero(self, idx):
        if not self._seasons or idx >= len(self._seasons):
            return
        self._hero_idx = idx
        s = self._seasons[idx]

        name     = s.get('name') or f"Sezonul {s.get('season_number', '')}"
        ep_count = s.get('episode_count', 0)
        year     = (s.get('air_date') or '')[:4]
        vote     = s.get('vote_average', 0)
        overview = s.get('overview') or self._show.get('overview', '')
        backdrop = tmdb.backdrop_url(self._show.get('backdrop_path', ''))

        parts = [p for p in [
            year,
            f'{ep_count} episoade' if ep_count else '',
            f'★ {vote:.1f}' if vote else '',
        ] if p]
        meta = '  •  '.join(parts)

        try:
            if not self._logo_set:
                self.getControl(_ID_TITLE).setLabel(name)
            self.getControl(_ID_META).setLabel(meta)
            self.getControl(_ID_PLOT).setLabel(overview)
            if backdrop:
                self.getControl(_ID_BACKDROP).setImage(backdrop)
        except Exception as e:
            xbmc.log(f'[SamusXUI/Seasons] hero: {e}', xbmc.LOGDEBUG)

    def _fetch_logo(self, tv_id):
        logo = tmdb.logo_url(tv_id, 'tv')
        try:
            if logo:
                self.getControl(_ID_LOGO).setImage(logo)
                self.getControl(_ID_TITLE).setLabel('')
                self._logo_set = True
            else:
                self.getControl(_ID_TITLE).setLabel(self._show.get('name', ''))
        except Exception as e:
            xbmc.log(f'[SamusXUI/Seasons] logo: {e}', xbmc.LOGDEBUG)

    # ------------------------------------------------------------------ navigation

    def onAction(self, action):
        aid = action.getId()
        if aid in (ACTION_NAV_BACK, ACTION_PREV_MENU):
            self.close()
            return
        if self.getFocusId() == _ID_POSTERS and aid in (ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT):
            xbmc.sleep(60)
            self._sync_hero()

    def onClick(self, controlId):
        if controlId in (_ID_PLAY, _ID_POSTERS):
            self._open_episodes()
        elif controlId == _ID_DETAILS:
            self._show_info()

    def onFocus(self, controlId):
        if controlId == _ID_POSTERS:
            xbmc.sleep(50)
            self._sync_hero()

    def _sync_hero(self):
        try:
            pos = self.getControl(_ID_POSTERS).getSelectedPosition()
            if 0 <= pos < len(self._seasons) and pos != self._hero_idx:
                self._update_hero(pos)
        except Exception:
            pass

    # ------------------------------------------------------------------ actions

    def _current_season(self):
        try:
            pos = self.getControl(_ID_POSTERS).getSelectedPosition()
            return self._seasons[pos] if 0 <= pos < len(self._seasons) else None
        except Exception:
            return self._seasons[self._hero_idx] if self._seasons else None

    def _open_episodes(self):
        from .episodes_window import EpisodesWindow
        s = self._current_season()
        if not s:
            return
        season_num = s.get('season_number', 1)
        try:
            season_data = tmdb.season_details(self._tv_id, season_num)
        except Exception as e:
            xbmc.log(f'[SamusXUI/Seasons] season fetch: {e}', xbmc.LOGWARNING)
            season_data = {}
        win = EpisodesWindow('tv_episodes.xml', ADDON_PATH, 'Default', '1080i')
        win._tv_id         = self._tv_id
        win._season_number = season_num
        win._season_name   = s.get('name') or f"Sezonul {season_num}"
        win._show          = self._show
        win._episodes      = season_data.get('episodes', [])
        win.doModal()
        del win

    def _show_info(self):
        if self._tv_id:
            xbmc.executebuiltin(
                f'RunPlugin(plugin://plugin.video.samusxui'
                f'?action=show_info&tmdb_id={self._tv_id}&media_type=tv)')
