# -*- coding: utf-8 -*-
import threading
from datetime import date

import xbmc
import xbmcgui
import xbmcaddon

from . import tmdb

ADDON_PATH = xbmcaddon.Addon('plugin.video.samusxui').getAddonInfo('path')

_ID_HEADER      = 5
_ID_BACKDROP    = 100
_ID_CARD_TITLE  = 202
_ID_CARD_YEAR   = 203
_ID_CARD_CHAR   = 204
_ID_PROFILE     = 115
_ID_NAME        = 110
_ID_META        = 111
_ID_BIO         = 113
_ID_TABS        = 141
_ID_CREDITS     = 131
_ID_EMPTY       = 150

ACTION_NAV_BACK   = 10
ACTION_PREV_MENU  = 92
ACTION_MOVE_LEFT  = 1
ACTION_MOVE_RIGHT = 2
ACTION_MOVE_UP    = 3
ACTION_MOVE_DOWN  = 4

_TABS = [('Toate', 'all'), ('Filme', 'movie'), ('Seriale', 'tv')]


def _calc_age(birthday_str, deathday_str=None):
    if not birthday_str:
        return ''
    try:
        bday = date.fromisoformat(birthday_str[:10])
        end  = date.fromisoformat(deathday_str[:10]) if deathday_str else date.today()
        age  = end.year - bday.year - ((end.month, end.day) < (bday.month, bday.day))
        return str(age)
    except Exception:
        return ''


class PersonWindow(xbmcgui.WindowXML):

    def __init__(self, *args, **kwargs):
        self._person_id    = None
        self._person       = {}
        self._credits_all  = []
        self._credits      = []   # filtrate curent
        self._filter       = 'all'
        self._hero_idx     = 0

    def onInit(self):
        name = self._person.get('name', '')
        try:
            self.getControl(_ID_HEADER).setLabel(
                f'[COLOR FF7B5CF4]←[/COLOR]  {name}')
        except Exception:
            pass
        self._populate()

    # ------------------------------------------------------------------ populate

    def _populate(self):
        p = self._person

        profile = tmdb.profile_url(p.get('profile_path', ''), size='w500')
        try:
            self.getControl(_ID_PROFILE).setImage(profile)
        except Exception:
            pass

        name     = p.get('name', '')
        bio      = p.get('biography', '') or ''
        if not bio and self._person_id:
            en_p = tmdb._get(f'/person/{self._person_id}', language='en')
            bio  = en_p.get('biography', '') or ''
        bday     = (p.get('birthday') or '')[:10]
        dday     = (p.get('deathday') or '')
        dept     = p.get('known_for_department', '')
        place    = p.get('place_of_birth', '')
        age      = _calc_age(bday, dday if dday else None)

        year_range = bday[:4] if bday else ''
        if dday:
            year_range = f'{bday[:4]}–{dday[:4]}' if bday else dday[:4]

        age_str = f'†{age} ani' if dday and age else (f'{age} ani' if age else '')
        parts   = [x for x in [year_range, place, dept, age_str] if x]
        meta    = '  •  '.join(parts)

        try:
            self.getControl(_ID_NAME).setLabel(name)
            self.getControl(_ID_META).setLabel(meta)
            self.getControl(_ID_BIO).setText(bio)
        except Exception:
            pass

        credits_raw = p.get('combined_credits', {}).get('cast', [])
        seen, self._credits_all = set(), []
        for c in sorted(credits_raw, key=lambda x: x.get('popularity', 0), reverse=True):
            cid = c.get('id')
            if cid and cid not in seen and c.get('poster_path'):
                seen.add(cid)
                self._credits_all.append(c)

        self._setup_tabs()
        self._apply_filter()

    def _setup_tabs(self):
        ctrl = self.getControl(_ID_TABS)
        ctrl.reset()
        items = []
        for label, fid in _TABS:
            item = xbmcgui.ListItem(label)
            item.setProperty('filter_id', fid)
            items.append(item)
        ctrl.addItems(items)
        active_idx = next(i for i, (_, fid) in enumerate(_TABS) if fid == self._filter)
        ctrl.selectItem(active_idx)
        self._mark_active_tab(active_idx)

    def _mark_active_tab(self, idx):
        ctrl = self.getControl(_ID_TABS)
        for i in range(len(_TABS)):
            try:
                ctrl.getListItem(i).setProperty('active', '1' if i == idx else '')
            except Exception:
                pass

    def _apply_filter(self):
        if self._filter == 'movie':
            self._credits = [c for c in self._credits_all if c.get('media_type') == 'movie']
        elif self._filter == 'tv':
            self._credits = [c for c in self._credits_all if c.get('media_type') == 'tv']
        else:
            self._credits = list(self._credits_all)
        self._populate_credits()

    def _populate_credits(self):
        ctrl = self.getControl(_ID_CREDITS)
        ctrl.reset()

        if not self._credits:
            try:
                self.getControl(_ID_EMPTY).setLabel('Nu s-a găsit filmografie.')
                self.getControl(_ID_EMPTY).setVisible(True)
            except Exception:
                pass
            return

        try:
            self.getControl(_ID_EMPTY).setVisible(False)
        except Exception:
            pass

        items = []
        for c in self._credits:
            title     = c.get('title') or c.get('name', '')
            poster    = tmdb.poster_url(c.get('poster_path', ''))
            character = c.get('character', '')
            raw_date  = c.get('release_date') or c.get('first_air_date') or ''
            year      = raw_date[:4] if raw_date else ''
            rating    = c.get('vote_average', 0)
            rating_str = f'★ {rating:.1f}' if rating else ''

            li = xbmcgui.ListItem(title)
            li.setArt({'thumb': poster})
            li.setProperty('tmdb_id',   str(c.get('id', '')))
            li.setProperty('media_type', c.get('media_type', 'movie'))
            li.setProperty('character', character)
            li.setProperty('year',      year)
            li.setProperty('rating',    rating_str)
            items.append(li)

        ctrl.addItems(items)
        ctrl.selectItem(0)
        self._hero_idx = 0
        self._update_hero(0)
        xbmc.sleep(50)
        self.setFocusId(_ID_CREDITS)

    # ------------------------------------------------------------------ hero

    def _update_hero(self, idx):
        if not self._credits or idx >= len(self._credits):
            return
        self._hero_idx = idx
        c = self._credits[idx]

        bp = c.get('backdrop_path', '')
        try:
            self.getControl(_ID_BACKDROP).setImage(tmdb.backdrop_url(bp) if bp else '-')
        except Exception:
            pass

        media     = c.get('media_type', 'movie')
        title     = c.get('title') or c.get('name', '')
        raw_date  = c.get('release_date') or c.get('first_air_date') or ''
        year      = raw_date[:4] if raw_date else ''
        character = c.get('character', '')

        media_lbl = 'Serial' if media == 'tv' else 'Film'
        year_lbl  = f'An: {year}' if year else ''
        char_lbl  = f'Rol: {character}' if character else ''
        try:
            self.getControl(_ID_CARD_TITLE).setLabel(f'{media_lbl}: {title}')
            self.getControl(_ID_CARD_YEAR).setLabel(year_lbl)
            self.getControl(_ID_CARD_CHAR).setLabel(char_lbl)
        except Exception:
            pass

    def _sync_hero(self):
        try:
            pos = self.getControl(_ID_CREDITS).getSelectedPosition()
            if 0 <= pos < len(self._credits) and pos != self._hero_idx:
                self._update_hero(pos)
        except Exception:
            pass

    # ------------------------------------------------------------------ navigation

    def onAction(self, action):
        aid = action.getId()
        if aid in (ACTION_NAV_BACK, ACTION_PREV_MENU):
            self.close()
            return
        fid = self.getFocusId()
        if fid == _ID_CREDITS and aid in (ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT):
            xbmc.sleep(60)
            self._sync_hero()

    def onFocus(self, controlId):
        if controlId == _ID_CREDITS:
            xbmc.sleep(50)
            self._sync_hero()

    def onClick(self, controlId):
        if controlId == _ID_TABS:
            self._handle_tab_click()
        elif controlId == _ID_CREDITS:
            self._open_credit()

    # ------------------------------------------------------------------ tab filter

    def _handle_tab_click(self):
        ctrl = self.getControl(_ID_TABS)
        idx  = ctrl.getSelectedPosition()
        self._filter = _TABS[idx][1]
        self._mark_active_tab(idx)
        self._apply_filter()

    # ------------------------------------------------------------------ credit actions

    def _current_credit(self):
        try:
            pos = self.getControl(_ID_CREDITS).getSelectedPosition()
            return self._credits[pos] if 0 <= pos < len(self._credits) else None
        except Exception:
            return self._credits[self._hero_idx] if self._credits else None

    def _open_credit(self):
        c = self._current_credit()
        if not c:
            return
        tmdb_id = c.get('id')
        media   = c.get('media_type', 'movie')

        details = tmdb.tv_details(tmdb_id) if media == 'tv' else tmdb.movie_details(tmdb_id)

        if not details:
            return

        from .info_dialog import VideoInfoDialog
        dlg = VideoInfoDialog()
        dlg.set_data(details, media)
        dlg.doModal()

        navigate_to  = dlg.navigate_to
        play_action  = dlg.play_action
        del dlg

        if navigate_to:
            self._navigate_to_person(navigate_to[0])
        elif play_action in ('play', 'sources') and media == 'movie':
            xbmc.executebuiltin(
                f'RunPlugin(plugin://plugin.video.samusxui'
                f'?action=play_movie&tmdb_id={tmdb_id}&show_sources=1)')
        elif play_action in ('seasons', 'play', 'sources') and media == 'tv':
            from .seasons_window import SeasonsWindow
            win = SeasonsWindow('tv_seasons.xml', ADDON_PATH, 'Default', '1080i')
            win._tv_id = tmdb_id
            win._show  = details
            win.doModal()
            del win

    def _navigate_to_person(self, person_id):
        person = tmdb.person_details(person_id)
        if not person:
            return
        win = PersonWindow('person.xml', ADDON_PATH, 'Default', '1080i')
        win._person_id = person_id
        win._person    = person
        win.doModal()
        del win
