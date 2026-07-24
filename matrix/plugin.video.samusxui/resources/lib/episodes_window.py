# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcaddon

from . import tmdb

ADDON_PATH = xbmcaddon.Addon('plugin.video.samusxui').getAddonInfo('path')

_ID_HEADER   = 5
_ID_BACKDROP = 100
_ID_LOGO     = 115
_ID_TITLE    = 110
_ID_META     = 111
_ID_PLOT     = 113
_ID_PLAY     = 120
_ID_SOURCES  = 121
_ID_EPISODES = 131
_ID_EMPTY    = 150

ACTION_NAV_BACK   = 10
ACTION_PREV_MENU  = 92
ACTION_MOVE_LEFT  = 1
ACTION_MOVE_RIGHT = 2


class EpisodesWindow(xbmcgui.WindowXML):

    def __init__(self, *args, **kwargs):
        self._tv_id         = None
        self._season_number = 1
        self._season_name   = ''
        self._show          = {}
        self._episodes      = []
        self._hero_idx      = 0

    def onInit(self):
        show_name = self._show.get('name', '')
        try:
            self.getControl(_ID_HEADER).setLabel(
                f'[COLOR FF7B5CF4]←[/COLOR]  {show_name}  •  {self._season_name}')
        except Exception:
            pass
        try:
            self.getControl(_ID_LOGO).setImage('')
        except Exception:
            pass
        self._populate()

    # ------------------------------------------------------------------ populate

    def _populate(self):
        ctrl = self.getControl(_ID_EPISODES)
        ctrl.reset()
        if not self._episodes:
            try:
                self.getControl(_ID_EMPTY).setLabel('Nu s-au găsit episoade.')
                self.getControl(_ID_EMPTY).setVisible(True)
            except Exception:
                pass
            for cid in (_ID_PLAY, _ID_EPISODES):
                try:
                    self.getControl(cid).setVisible(False)
                except Exception:
                    pass
            return
        try:
            self.getControl(_ID_EMPTY).setVisible(False)
        except Exception:
            pass
        for cid in (_ID_PLAY, _ID_EPISODES):
            try:
                self.getControl(cid).setVisible(True)
            except Exception:
                pass
        for ep in self._episodes:
            ep_num = ep.get('episode_number', 0)
            name   = f"{ep_num:02d}. {ep.get('name', '')}"
            still  = tmdb.still_url(ep.get('still_path', ''))
            li = xbmcgui.ListItem(name)
            li.setArt({'thumb': still})
            ctrl.addItem(li)
        ctrl.selectItem(0)
        self._update_hero(0)
        self.setFocusId(_ID_EPISODES)

    # ------------------------------------------------------------------ hero

    def _update_hero(self, idx):
        if not self._episodes or idx >= len(self._episodes):
            return
        self._hero_idx = idx
        ep = self._episodes[idx]

        ep_num   = ep.get('episode_number', 0)
        name     = ep.get('name') or f"Episodul {ep_num}"
        plot     = ep.get('overview', '')
        vote     = ep.get('vote_average', 0)
        runtime  = ep.get('runtime', 0)
        air_date = (ep.get('air_date') or '')[:10]

        still_path = ep.get('still_path', '')
        backdrop = (tmdb.backdrop_url(still_path)
                    if still_path
                    else tmdb.backdrop_url(self._show.get('backdrop_path', '')))

        parts = [p for p in [
            f"S{self._season_number:02d}E{ep_num:02d}",
            air_date,
            f'★ {vote:.1f}' if vote else '',
            f'{runtime} min' if runtime else '',
        ] if p]
        meta = '  •  '.join(parts)

        try:
            self.getControl(_ID_TITLE).setLabel(name)
            self.getControl(_ID_META).setLabel(meta)
            self.getControl(_ID_PLOT).setLabel(plot)
            if backdrop:
                self.getControl(_ID_BACKDROP).setImage(backdrop)
        except Exception as e:
            xbmc.log(f'[SamusXUI/Episodes] hero: {e}', xbmc.LOGDEBUG)

    # ------------------------------------------------------------------ navigation

    def onAction(self, action):
        aid = action.getId()
        if aid in (ACTION_NAV_BACK, ACTION_PREV_MENU):
            self.close()
            return
        if self.getFocusId() == _ID_EPISODES and aid in (ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT):
            xbmc.sleep(60)
            self._sync_hero()

    def onClick(self, controlId):
        if controlId in (_ID_PLAY, _ID_EPISODES):
            self._play_current()
        elif controlId == _ID_SOURCES:
            self._show_sources()

    def onFocus(self, controlId):
        if controlId == _ID_EPISODES:
            xbmc.sleep(50)
            self._sync_hero()

    def _sync_hero(self):
        try:
            pos = self.getControl(_ID_EPISODES).getSelectedPosition()
            if 0 <= pos < len(self._episodes) and pos != self._hero_idx:
                self._update_hero(pos)
        except Exception:
            pass

    # ------------------------------------------------------------------ actions

    def _current_episode(self):
        try:
            pos = self.getControl(_ID_EPISODES).getSelectedPosition()
            return self._episodes[pos] if 0 <= pos < len(self._episodes) else None
        except Exception:
            return self._episodes[self._hero_idx] if self._episodes else None

    def _play_current(self):
        ep = self._current_episode()
        if not ep:
            return
        ep_num = ep.get('episode_number', 1)
        xbmc.executebuiltin(
            f'PlayMedia(plugin://plugin.video.samusxui'
            f'?action=play_episode&tv_id={self._tv_id}'
            f'&season={self._season_number}&episode={ep_num})')

    def _show_sources(self):
        ep = self._current_episode()
        if not ep:
            return
        ep_num = ep.get('episode_number', 1)
        xbmc.executebuiltin(
            f'PlayMedia(plugin://plugin.video.samusxui'
            f'?action=play_episode&tv_id={self._tv_id}'
            f'&season={self._season_number}&episode={ep_num}&show_sources=1)')
