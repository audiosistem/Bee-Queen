# -*- coding: utf-8 -*-
import threading
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
_ID_DETAILS  = 122
_ID_POSTERS  = 131
_ID_EMPTY    = 150

ACTION_NAV_BACK   = 10
ACTION_PREV_MENU  = 92
ACTION_MOVE_LEFT  = 1
ACTION_MOVE_RIGHT = 2
ACTION_MOVE_UP    = 3
ACTION_MOVE_DOWN  = 4

_SECTION_LABEL = {'movie': 'FILME', 'tv': 'SERIALE'}


class SearchResultsWindow(xbmcgui.WindowXML):

    def __init__(self, *args, **kwargs):
        self._query        = ''
        self._media        = 'movie'
        self._items        = []
        self._hero_idx     = 0
        self._page         = 1
        self._total_pages  = 1
        self._loading_more = False

    # ------------------------------------------------------------------ init

    def onInit(self):
        section = _SECTION_LABEL.get(self._media, 'Rezultate')
        try:
            self.getControl(_ID_HEADER).setLabel(
                f'[COLOR FF7B5CF4]←[/COLOR]  {section}  •  {self._query}')
        except Exception:
            pass
        self._populate_posters()

    # ------------------------------------------------------------------ populate

    def _populate_posters(self):
        ctrl = self.getControl(_ID_POSTERS)
        ctrl.reset()
        if not self._items:
            try:
                self.getControl(_ID_EMPTY).setLabel('Niciun rezultat găsit.')
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
        for cid in (_ID_PLAY, _ID_DETAILS, _ID_POSTERS):
            try:
                self.getControl(cid).setVisible(True)
            except Exception:
                pass
        self._append_items(self._items, ctrl)
        ctrl.selectItem(0)
        self._update_hero(0)
        self.setFocusId(_ID_POSTERS)

    def _append_items(self, items, ctrl=None):
        if ctrl is None:
            ctrl = self.getControl(_ID_POSTERS)
        for m in items:
            title  = m.get('title') or m.get('name', '')
            poster = tmdb.poster_url(m.get('poster_path', ''))
            vote   = m.get('vote_average', 0)
            li = xbmcgui.ListItem(title)
            li.setArt({'thumb': poster})
            li.setLabel2(f'★ {vote:.1f}')
            li.setProperty('tmdb_id', str(m.get('id', '')))
            ctrl.addItem(li)

    # ------------------------------------------------------------------ hero

    def _update_hero(self, idx):
        if not self._items or idx >= len(self._items):
            return
        self._hero_idx = idx
        m = self._items[idx]

        title     = m.get('title') or m.get('name', '')
        yr_raw    = m.get('release_date') or m.get('first_air_date') or ''
        year      = yr_raw[:4]
        vote      = m.get('vote_average', 0)
        cnt       = m.get('vote_count', 0)
        cnt_str   = (f"{int(cnt/1000)}K voturi" if cnt >= 1000
                     else (f"{cnt} voturi" if cnt else ''))
        plot      = m.get('overview', '')
        backdrop  = tmdb.backdrop_url(m.get('backdrop_path', ''))
        genres_str = tmdb.genre_names(m.get('genre_ids', []), self._media)

        status_str = ''
        if yr_raw:
            try:
                import datetime
                if datetime.date.fromisoformat(yr_raw[:10]) > datetime.date.today():
                    status_str = 'În curând'
            except Exception:
                pass

        rating_str = f'★ {vote:.1f}' if vote else ''
        parts = [p for p in [status_str, year, genres_str, rating_str, cnt_str] if p]
        meta  = '  •  '.join(parts)

        try:
            self.getControl(_ID_LOGO).setImage('')
            self.getControl(_ID_TITLE).setLabel('')
            self.getControl(_ID_META).setLabel(meta)
            self.getControl(_ID_PLOT).setLabel(plot)
            if backdrop:
                self.getControl(_ID_BACKDROP).setImage(backdrop)
        except Exception as e:
            xbmc.log(f'[SamusXUI/Results] hero: {e}', xbmc.LOGDEBUG)

        tmdb_id = m.get('id')
        threading.Thread(target=self._fetch_logo,
                         args=(tmdb_id, idx, title), daemon=True).start()

    def _fetch_logo(self, tmdb_id, for_idx, title=''):
        logo = tmdb.logo_url(tmdb_id, self._media)
        if self._hero_idx != for_idx:
            return
        try:
            if logo:
                self.getControl(_ID_LOGO).setImage(logo)
            else:
                self.getControl(_ID_TITLE).setLabel(title)
        except Exception as e:
            xbmc.log(f'[SamusXUI/Results] logo: {e}', xbmc.LOGDEBUG)

    # ------------------------------------------------------------------ pagination

    def _trigger_load_more(self):
        if self._loading_more or self._page >= self._total_pages:
            return
        self._loading_more = True
        threading.Thread(target=self._fetch_more, daemon=True).start()

    def _fetch_more(self):
        try:
            next_page = self._page + 1
            data      = tmdb.search(self._media, self._query, next_page)
            new_items = data.get('results', [])
            if new_items:
                self._page = next_page
                self._items.extend(new_items)
                self._append_items(new_items)
        except Exception as e:
            xbmc.log(f'[SamusXUI/Results] load more: {e}', xbmc.LOGWARNING)
        finally:
            self._loading_more = False

    # ------------------------------------------------------------------ navigation

    def onAction(self, action):
        aid = action.getId()
        if aid in (ACTION_NAV_BACK, ACTION_PREV_MENU):
            self.close()
            return
        if self.getFocusId() == _ID_POSTERS and aid in (ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT):
            xbmc.sleep(60)
            self._sync_hero()
            if aid == ACTION_MOVE_RIGHT:
                try:
                    pos = self.getControl(_ID_POSTERS).getSelectedPosition()
                    if pos >= len(self._items) - 3:
                        self._trigger_load_more()
                except Exception:
                    pass

    def onClick(self, controlId):
        if controlId == _ID_PLAY:
            self._play_current()
        elif controlId == _ID_DETAILS:
            self._show_details()
        elif controlId == _ID_POSTERS:
            self._play_current()

    def onFocus(self, controlId):
        if controlId == _ID_POSTERS:
            xbmc.sleep(50)
            self._sync_hero()

    def _sync_hero(self):
        try:
            pos = self.getControl(_ID_POSTERS).getSelectedPosition()
            if 0 <= pos < len(self._items) and pos != self._hero_idx:
                self._update_hero(pos)
        except Exception:
            pass

    # ------------------------------------------------------------------ actions

    def _current_item(self):
        if not self._items:
            return None
        try:
            pos = self.getControl(_ID_POSTERS).getSelectedPosition()
            return self._items[pos] if 0 <= pos < len(self._items) else None
        except Exception:
            return self._items[self._hero_idx] if self._items else None

    def _play_current(self):
        m = self._current_item()
        if not m:
            return
        tmdb_id = m.get('id')
        if self._media == 'tv':
            self._open_seasons(tmdb_id)
        else:
            xbmc.executebuiltin(
                f'PlayMedia(plugin://plugin.video.samusxui'
                f'?action=play_movie&tmdb_id={tmdb_id})')

    def _open_seasons(self, tmdb_id):
        from .seasons_window import SeasonsWindow
        show = tmdb.tv_details(tmdb_id)
        if not show or not show.get('seasons'):
            xbmcgui.Dialog().notification('SamusXUI', 'Nu s-au găsit sezoane.', xbmcgui.NOTIFICATION_INFO)
            return
        win = SeasonsWindow('tv_seasons.xml', ADDON_PATH, 'Default', '1080i')
        win._tv_id = tmdb_id
        win._show  = show
        win.doModal()
        del win

    def _show_details(self):
        m = self._current_item()
        if not m:
            return
        tmdb_id = m.get('id')
        xbmc.executebuiltin(
            f'RunPlugin(plugin://plugin.video.samusxui'
            f'?action=show_info&tmdb_id={tmdb_id}&media_type={self._media})')
