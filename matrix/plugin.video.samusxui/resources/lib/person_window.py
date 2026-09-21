# -*- coding: utf-8 -*-
import re
import unicodedata
from datetime import date

import xbmc
import xbmcgui
import xbmcaddon

from . import tmdb

ADDON_PATH = xbmcaddon.Addon('plugin.video.samusxui').getAddonInfo('path')

_ID_BACKDROP = 100
_ID_NAME = 110
_ID_META = 111
_ID_BIRTH = 112
_ID_BIO = 113
_ID_ALIASES = 114
_ID_PROFILE = 115
_ID_SOCIAL = 116
_ID_AGE = 117
_ID_PLACE = 118
_ID_KNOWN = 119
_ID_GALLERY = 120
_ID_CREDITS = 131
_ID_GALLERY_ITEMS = 132
_ID_ROLE_TABS = 141
_ID_MEDIA_TABS = 142
_ID_EMPTY = 150

_GALLERY_HEADER = 5
_GALLERY_BG = 101
_GALLERY_HERO = 100
_GALLERY_TITLE = 110
_GALLERY_META = 111
_GALLERY_LIST = 131

ACTION_NAV_BACK = 10
ACTION_PREV_MENU = 92
ACTION_MOVE_LEFT = 1
ACTION_MOVE_RIGHT = 2

_ROLE_TABS = [
    ('Actor', 'acting'), ('Regie', 'directing'), ('Scenariu', 'writing'),
    ('Producție', 'production'), ('Orice rol', 'all'),
]
_MEDIA_TABS = [('Toate', 'all'), ('Filme', 'movie'), ('Seriale', 'tv')]

_DEPARTMENTS = {
    'Acting': 'Actor', 'Directing': 'Regie', 'Writing': 'Scenariu',
    'Production': 'Producție', 'Sound': 'Sunet și muzică',
    'Camera': 'Imagine', 'Editing': 'Montaj', 'Art': 'Scenografie',
    'Costume & Make-Up': 'Costume și machiaj', 'Visual Effects': 'Efecte vizuale',
}
_JOBS = {
    'Director': 'Regie', 'Writer': 'Scenariu', 'Screenplay': 'Scenariu',
    'Teleplay': 'Scenariu', 'Story': 'Poveste', 'Characters': 'Personaje',
    'Creator': 'Creator', 'Producer': 'Producător',
    'Executive Producer': 'Producător executiv', 'Co-Producer': 'Coproducător',
    'Original Music Composer': 'Muzică', 'Director of Photography': 'Imagine',
    'Editor': 'Montaj', 'Casting': 'Casting', 'Production Design': 'Scenografie',
}


def _calc_age(birthday, deathday=None):
    try:
        born = date.fromisoformat((birthday or '')[:10])
        end = date.fromisoformat(deathday[:10]) if deathday else date.today()
        return str(end.year - born.year - ((end.month, end.day) < (born.month, born.day)))
    except Exception:
        return ''


def _display_date(value):
    try:
        return date.fromisoformat((value or '')[:10]).strftime('%d.%m.%Y')
    except Exception:
        return ''


def _unique(values, limit=None):
    result = []
    for value in values:
        value = (value or '').strip()
        if value and value not in result:
            result.append(value)
    return result[:limit] if limit else result


def _latin_alias(value):
    for char in value or '':
        if char.isalpha() and 'LATIN' not in unicodedata.name(char, ''):
            return False
    return True


def _bio_excerpt(value, limit=560):
    """Returnează numai propoziții întregi care încap în pagina principală."""
    paragraphs = [re.sub(r'\s+', ' ', part).strip()
                  for part in re.split(r'\n\s*\n', value or '') if part.strip()]
    if not paragraphs:
        return ''
    first = paragraphs[0]
    if len(first) <= limit:
        return first
    sentences = re.split(r'(?<=[.!?])\s+', first)
    excerpt = ''
    for sentence in sentences:
        candidate = f'{excerpt} {sentence}'.strip()
        if excerpt and len(candidate) > limit:
            break
        excerpt = candidate
    if not excerpt:
        excerpt = first[:limit].rsplit(' ', 1)[0].rstrip(' ,;:') + '…'
    elif len(excerpt) < len(first):
        excerpt += ' […]'
    return excerpt


class PersonWindow(xbmcgui.WindowXML):

    def __init__(self, *args, **kwargs):
        self._person_id = None
        self._person = {}
        self._credits_all = []
        self._credits = []
        self._role_filter = 'acting'
        self._media_filter = 'all'
        self._gallery_items = []
        self._gallery_mode = False
        self._profile_default = ''
        self._gallery_idx = -1

    def onInit(self):
        self._populate()

    def _populate(self):
        p = self._person
        profile_path = p.get('profile_path') or ''
        profile = tmdb.image_url(profile_path, 'original')
        self._profile_default = profile
        try:
            self.getControl(_ID_BACKDROP).setImage(profile)
            self.getControl(_ID_PROFILE).setImage(profile)
            self.getControl(_ID_GALLERY_ITEMS).setVisible(False)
        except Exception:
            pass

        name = p.get('name') or ''
        bio = p.get('biography') or ''
        if not bio and self._person_id:
            bio = tmdb._get(f'/person/{self._person_id}', language='en').get('biography') or ''
        # Pronunțiile IPA din introducerea biografiilor engleze folosesc glife
        # absente din fontul skinului; datele de naștere rămân în statisticile de sus.
        bio = re.sub(r'\s*\([^)]*/[^)]*/[^)]*\)', '', bio, count=1)
        birthday = (p.get('birthday') or '')[:10]
        deathday = (p.get('deathday') or '')[:10]
        department_raw = p.get('known_for_department') or ''
        department = _DEPARTMENTS.get(department_raw, department_raw)
        gender = {1: 'Femeie', 2: 'Bărbat', 3: 'Non-binar'}.get(p.get('gender'), '')
        meta = '  •  '.join(x for x in (department, gender) if x)

        birth = _display_date(birthday)
        if deathday:
            birth = f'{birth}–{_display_date(deathday)}' if birth else _display_date(deathday)
        age = _calc_age(birthday, deathday or None)
        if deathday and age:
            age += ' †'
        place = p.get('place_of_birth') or ''

        aliases = _unique((a for a in (p.get('also_known_as') or [])
                           if a.casefold() != name.casefold() and _latin_alias(a)), limit=4)
        aliases_text = f'Cunoscut și ca: {" / ".join(aliases)}' if aliases else ''

        ext = p.get('external_ids') or {}
        socials = []
        for label, key, prefix in (
                ('Instagram', 'instagram_id', '@'), ('X', 'twitter_id', '@'),
                ('TikTok', 'tiktok_id', '@'), ('Facebook', 'facebook_id', '')):
            if ext.get(key):
                socials.append(f'{label}: {prefix}{ext[key]}')
        social_text = '  •  '.join(socials[:4])

        try:
            self.getControl(_ID_NAME).setLabel(name)
            self.getControl(_ID_META).setLabel(meta)
            self.getControl(_ID_BIRTH).setLabel(birth or '—')
            self.getControl(_ID_AGE).setLabel(age or '—')
            self.getControl(_ID_PLACE).setLabel(place or '—')
            self.getControl(_ID_ALIASES).setLabel(aliases_text)
            self.getControl(_ID_SOCIAL).setLabel(social_text)
            self.getControl(_ID_BIO).setText(_bio_excerpt(bio))
        except Exception:
            pass

        self._build_credits(p.get('combined_credits') or {})
        known_count = len({(c.get('media_type'), c.get('id')) for c in self._credits_all})
        try:
            self.getControl(_ID_KNOWN).setLabel(str(known_count))
        except Exception:
            pass

        self._build_gallery_items()
        gallery_count = len(self._gallery_items)
        try:
            gallery = self.getControl(_ID_GALLERY)
            gallery.setLabel(f'IMAGINI  ({gallery_count})')
            gallery.setVisible(gallery_count > 0)
        except Exception:
            pass

        self._role_filter = {
            'Directing': 'directing', 'Writing': 'writing',
            'Production': 'production',
        }.get(department_raw, 'acting')
        self._setup_tabs()
        self._apply_filter()

    def _build_gallery_items(self):
        entries, seen = [], set()
        for image in (self._person.get('images') or {}).get('profiles') or []:
            path = image.get('file_path') or ''
            if path and path not in seen:
                seen.add(path)
                entries.append({
                    'path': path, 'title': 'Portret',
                    'meta': f"{image.get('width', 0)} × {image.get('height', 0)}",
                })
        for image in (self._person.get('tagged_images') or {}).get('results') or []:
            path = image.get('file_path') or ''
            if not path or path in seen:
                continue
            seen.add(path)
            media = image.get('media') or {}
            title = (media.get('title') or media.get('name') or
                     media.get('original_title') or media.get('original_name') or 'Artwork')
            raw_date = (media.get('release_date') or media.get('first_air_date') or
                        media.get('air_date') or '')
            kind = {'poster': 'Poster', 'backdrop': 'Fundal', 'still': 'Cadru'}.get(
                image.get('image_type'), 'Artwork')
            entries.append({
                'path': path, 'title': title,
                'meta': '  •  '.join(x for x in (kind, raw_date[:4]) if x),
            })
        self._gallery_items = entries
        ctrl = self.getControl(_ID_GALLERY_ITEMS)
        ctrl.reset()
        items = []
        total = len(entries)
        for idx, entry in enumerate(entries):
            thumb = tmdb.image_url(entry['path'], 'w342')
            item = xbmcgui.ListItem(entry['title'])
            item.setArt({'thumb': thumb, 'icon': thumb})
            item.setProperty('year', f'{idx + 1}/{total}')
            item.setProperty('character', entry['meta'])
            items.append(item)
        ctrl.addItems(items)
        if items:
            ctrl.selectItem(0)

    def _show_gallery(self):
        if not self._gallery_items:
            return
        self._gallery_mode = True
        self._gallery_idx = -1
        self.getControl(_ID_PROFILE).setImage(self._profile_default)
        self.getControl(_ID_CREDITS).setVisible(False)
        self.getControl(_ID_EMPTY).setVisible(False)
        self.getControl(_ID_GALLERY_ITEMS).setVisible(True)

    def _show_credits(self):
        if not self._gallery_mode:
            return
        self._gallery_mode = False
        self.getControl(_ID_GALLERY_ITEMS).setVisible(False)
        self.getControl(_ID_CREDITS).setVisible(bool(self._credits))
        self.getControl(_ID_EMPTY).setVisible(not self._credits)
        self.getControl(_ID_PROFILE).setImage(self._profile_default)

    def _sync_gallery_profile(self):
        try:
            idx = self.getControl(_ID_GALLERY_ITEMS).getSelectedPosition()
        except Exception:
            return
        if idx == self._gallery_idx or not (0 <= idx < len(self._gallery_items)):
            return
        self._gallery_idx = idx
        self.getControl(_ID_PROFILE).setImage(
            tmdb.image_url(self._gallery_items[idx]['path'], 'original'))

    def _build_credits(self, combined):
        merged = {}
        order = []

        def add(raw, role, labels):
            cid, media = raw.get('id'), raw.get('media_type')
            if not cid or media not in ('movie', 'tv'):
                return
            key = (role, media, cid)
            if key not in merged:
                row = dict(raw)
                row['_credit_role'] = role
                row['_credit_labels'] = []
                row['_episode_count'] = 0
                merged[key] = row
                order.append(key)
            row = merged[key]
            row['popularity'] = max(float(row.get('popularity') or 0),
                                    float(raw.get('popularity') or 0))
            row['_episode_count'] = max(int(row.get('_episode_count') or 0),
                                        int(raw.get('episode_count') or 0))
            for label in labels:
                if label and label not in row['_credit_labels']:
                    row['_credit_labels'].append(label)

        for credit in combined.get('cast') or []:
            add(credit, 'acting', [credit.get('character')])
        for credit in combined.get('crew') or []:
            dept = credit.get('department') or ''
            role = {'Directing': 'directing', 'Writing': 'writing',
                    'Production': 'production'}.get(dept, 'other')
            job = credit.get('job') or _DEPARTMENTS.get(dept, dept)
            add(credit, role, [_JOBS.get(job, job)])

        self._credits_all = [merged[key] for key in order]

        def score(credit):
            popularity = min(float(credit.get('popularity') or 0), 50.0)
            votes = min(int(credit.get('vote_count') or 0) / 250.0, 40.0)
            rating = float(credit.get('vote_average') or 0)
            labels = ' '.join(credit.get('_credit_labels') or []).lower()
            penalty = 100.0 if any(x in labels for x in (
                'self', 'himself', 'herself', 'archive footage')) else 0.0
            return popularity + votes + rating - penalty

        self._credits_all.sort(key=score, reverse=True)

    def _setup_tabs(self):
        self._update_role_button()
        self._update_media_button()

    def _update_role_button(self):
        label = next((label for label, filter_id in _ROLE_TABS
                      if filter_id == self._role_filter), 'Orice rol')
        self.getControl(_ID_ROLE_TABS).setLabel(f'ROL  ·  {label.upper()}')

    def _update_media_button(self):
        label = next((label for label, filter_id in _MEDIA_TABS
                      if filter_id == self._media_filter), 'Toate')
        self.getControl(_ID_MEDIA_TABS).setLabel(f'TIP  ·  {label.upper()}')

    def _apply_filter(self):
        self._credits = [c for c in self._credits_all
                         if (self._role_filter == 'all' or c.get('_credit_role') == self._role_filter)
                         and (self._media_filter == 'all' or c.get('media_type') == self._media_filter)]
        self._populate_credits()

    def _credit_role(self, credit):
        labels = list(credit.get('_credit_labels') or [])
        episodes = int(credit.get('_episode_count') or credit.get('episode_count') or 0)
        if episodes and credit.get('media_type') == 'tv':
            labels.insert(0, f'{episodes} ep.')
        return ' / '.join(_unique(labels, limit=3))

    def _populate_credits(self):
        ctrl = self.getControl(_ID_CREDITS)
        ctrl.reset()
        if not self._credits:
            try:
                self.getControl(_ID_EMPTY).setLabel('Nu există producții pentru filtrul ales.')
                self.getControl(_ID_EMPTY).setVisible(True)
                self.setFocusId(_ID_ROLE_TABS)
            except Exception:
                pass
            return
        try:
            self.getControl(_ID_EMPTY).setVisible(False)
        except Exception:
            pass

        items = []
        for credit in self._credits:
            title = credit.get('title') or credit.get('name') or ''
            poster = tmdb.poster_url(credit.get('poster_path') or '')
            raw_date = credit.get('release_date') or credit.get('first_air_date') or ''
            year = raw_date[:4]
            rating = float(credit.get('vote_average') or 0)
            item = xbmcgui.ListItem(title)
            item.setArt({'thumb': poster, 'icon': poster})
            item.setProperty('tmdb_id', str(credit.get('id') or ''))
            item.setProperty('media_type', credit.get('media_type') or 'movie')
            item.setProperty('year', year)
            item.setProperty('rating', f'★ {rating:.1f}' if rating else '')
            item.setProperty('character', self._credit_role(credit))
            items.append(item)
        ctrl.addItems(items)
        ctrl.selectItem(0)
        xbmc.sleep(50)
        self.setFocusId(_ID_CREDITS)

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (ACTION_NAV_BACK, ACTION_PREV_MENU):
            self.close()
        elif (action_id in (ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT) and
              self.getFocusId() == _ID_GALLERY_ITEMS):
            xbmc.sleep(60)
            self._sync_gallery_profile()

    def onClick(self, control_id):
        if control_id == _ID_GALLERY:
            self._show_gallery()
            if self._gallery_items:
                self.setFocusId(_ID_GALLERY_ITEMS)
        elif control_id == _ID_ROLE_TABS:
            idx = next(i for i, (_, filter_id) in enumerate(_ROLE_TABS)
                       if filter_id == self._role_filter)
            self._role_filter = _ROLE_TABS[(idx + 1) % len(_ROLE_TABS)][1]
            self._update_role_button()
            self._apply_filter()
            # Buton ciclic: focusul rămâne aici, astfel utilizatorul poate trece
            # rapid prin toate rolurile cu apăsări succesive de OK.
            try:
                self.setFocusId(_ID_ROLE_TABS)
            except Exception:
                pass
        elif control_id == _ID_MEDIA_TABS:
            idx = next(i for i, (_, filter_id) in enumerate(_MEDIA_TABS)
                       if filter_id == self._media_filter)
            self._media_filter = _MEDIA_TABS[(idx + 1) % len(_MEDIA_TABS)][1]
            self._update_media_button()
            self._apply_filter()
            try:
                self.setFocusId(_ID_MEDIA_TABS)
            except Exception:
                pass
        elif control_id == _ID_CREDITS:
            self._open_credit()
        elif control_id == _ID_GALLERY_ITEMS:
            self._sync_gallery_profile()

    def onFocus(self, control_id):
        if control_id == _ID_GALLERY:
            self._show_gallery()
        elif control_id in (_ID_ROLE_TABS, _ID_MEDIA_TABS):
            self._show_credits()
        elif control_id == _ID_GALLERY_ITEMS:
            self._sync_gallery_profile()

    def _current_credit(self):
        try:
            pos = self.getControl(_ID_CREDITS).getSelectedPosition()
            return self._credits[pos] if 0 <= pos < len(self._credits) else None
        except Exception:
            return None

    def _open_credit(self):
        credit = self._current_credit()
        if not credit:
            return
        tmdb_id = credit.get('id')
        media = credit.get('media_type') or 'movie'
        details = tmdb.tv_details(tmdb_id) if media == 'tv' else tmdb.movie_details(tmdb_id)
        if not details:
            return
        from .info_dialog import VideoInfoDialog
        dlg = VideoInfoDialog()
        dlg.set_data(details, media)
        dlg.doModal()
        navigate_to, play_action = dlg.navigate_to, dlg.play_action
        del dlg
        if navigate_to:
            self._navigate_to_person(navigate_to[0])
        elif play_action in ('play', 'sources') and media == 'movie':
            xbmc.executebuiltin(
                f'RunPlugin(plugin://plugin.video.samusxui?action=play_movie&tmdb_id={tmdb_id}&show_sources=1)')
        elif play_action in ('seasons', 'play', 'sources') and media == 'tv':
            from .seasons_window import SeasonsWindow
            win = SeasonsWindow('tv_seasons.xml', ADDON_PATH, 'Default', '1080i')
            win._tv_id, win._show = tmdb_id, details
            win.doModal()
            del win

    def _navigate_to_person(self, person_id):
        person = tmdb.person_details(person_id)
        if not person:
            return
        win = PersonWindow('person.xml', ADDON_PATH, 'Default', '1080i')
        win._person_id, win._person = person_id, person
        win.doModal()
        del win


class PersonGalleryWindow(xbmcgui.WindowXML):

    def __init__(self, *args, **kwargs):
        self._person = {}
        self._items = []
        self._hero_idx = -1

    def onInit(self):
        name = self._person.get('name') or ''
        try:
            self.getControl(_GALLERY_HEADER).setLabel(
                f'[COLOR FF7B5CF4]←[/COLOR]  {name}  •  Poze & artwork')
        except Exception:
            pass
        self._populate()

    def _populate(self):
        entries, seen = [], set()
        for image in (self._person.get('images') or {}).get('profiles') or []:
            path = image.get('file_path') or ''
            if path and path not in seen:
                seen.add(path)
                entries.append({'path': path, 'title': 'Portret',
                                'meta': f"{image.get('width', 0)} × {image.get('height', 0)}"})
        for image in (self._person.get('tagged_images') or {}).get('results') or []:
            path = image.get('file_path') or ''
            if not path or path in seen:
                continue
            seen.add(path)
            media = image.get('media') or {}
            title = (media.get('title') or media.get('name') or
                     media.get('original_title') or media.get('original_name') or 'Artwork')
            raw_date = media.get('release_date') or media.get('first_air_date') or media.get('air_date') or ''
            kind = {'poster': 'Poster', 'backdrop': 'Fundal', 'still': 'Cadru'}.get(
                image.get('image_type'), 'Artwork')
            entries.append({'path': path, 'title': title,
                            'meta': '  •  '.join(x for x in (kind, raw_date[:4]) if x)})
        self._items = entries
        ctrl = self.getControl(_GALLERY_LIST)
        ctrl.reset()
        listitems = []
        for entry in entries:
            thumb = tmdb.image_url(entry['path'], 'w342')
            item = xbmcgui.ListItem(entry['title'])
            item.setArt({'thumb': thumb, 'icon': thumb})
            listitems.append(item)
        ctrl.addItems(listitems)
        if entries:
            ctrl.selectItem(0)
            self._update_hero(0)
            self.setFocusId(_GALLERY_LIST)

    def _update_hero(self, idx):
        if not (0 <= idx < len(self._items)):
            return
        self._hero_idx = idx
        entry = self._items[idx]
        full = tmdb.image_url(entry['path'])
        try:
            self.getControl(_GALLERY_BG).setImage(full)
            self.getControl(_GALLERY_HERO).setImage(full)
            self.getControl(_GALLERY_TITLE).setLabel(entry['title'])
            self.getControl(_GALLERY_META).setLabel(
                '  •  '.join(x for x in (entry['meta'], f'{idx + 1} / {len(self._items)}') if x))
        except Exception:
            pass

    def _sync(self):
        try:
            pos = self.getControl(_GALLERY_LIST).getSelectedPosition()
            if pos != self._hero_idx:
                self._update_hero(pos)
        except Exception:
            pass

    def onAction(self, action):
        aid = action.getId()
        if aid in (ACTION_NAV_BACK, ACTION_PREV_MENU):
            self.close()
        elif aid in (ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT):
            xbmc.sleep(60)
            self._sync()

    def onFocus(self, control_id):
        if control_id == _GALLERY_LIST:
            self._sync()
