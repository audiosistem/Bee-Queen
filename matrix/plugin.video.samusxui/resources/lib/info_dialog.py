import xbmc
import xbmcgui
import xbmcaddon

_ADDON    = xbmcaddon.Addon('plugin.video.samusxui')
_PATH     = _ADDON.getAddonInfo('path')
IMG_BASE  = 'https://image.tmdb.org/t/p/w500'
IMG_PROF  = 'https://image.tmdb.org/t/p/w185'
IMG_FAN   = 'https://image.tmdb.org/t/p/original'

CAST_PANEL  = 400
TAB_CAST    = 390
TAB_CREW    = 391
PLOT_BOX    = 11
BTN_PRIMARY = 500   # Redă / Sezoane
BTN_SOURCES = 501
BTN_TRAILER = 502
BTN_SIMILAR = 504

_CREW_JOBS = {
    'Director': 'Regie', 'Writer': 'Scenariu', 'Screenplay': 'Scenariu',
    'Teleplay': 'Scenariu', 'Story': 'Poveste', 'Characters': 'Personaje',
    'Creator': 'Creator', 'Executive Producer': 'Producător executiv',
    'Producer': 'Producător', 'Co-Producer': 'Coproducător',
    'Original Music Composer': 'Muzică', 'Director of Photography': 'Imagine',
    'Editor': 'Montaj', 'Casting': 'Casting', 'Production Design': 'Scenografie',
}


class VideoInfoDialog(xbmcgui.WindowXMLDialog):
    """
    Kodi's C++ WindowXMLDialog.__new__ expects (xmlFilename, scriptPath, ...) as
    the first args at object creation time.  We pass those via __new__ and keep our
    own data out of the constructor signature entirely.
    """

    def __new__(cls, *_args, **_kwargs):
        return super().__new__(cls, 'dialog_info.xml', _PATH, 'Default', '1080i')

    def __init__(self, *_args, **_kwargs):
        super().__init__('dialog_info.xml', _PATH, 'Default', '1080i')
        # real data set via set_data() before doModal()
        self._item       = {}
        self._media_type = 'movie'
        self._cast       = []
        self._people     = []
        self._raw_cast   = []
        self._raw_crew   = []
        self._people_mode = 'cast'
        self.navigate_to   = None   # (person_id, person_name)
        self.play_action   = None   # 'play' | 'seasons' | 'trailer' | 'collection' | 'similar'
        self.collection_id = None

    def set_data(self, item_data, media_type='movie'):
        self._item       = item_data
        self._media_type = media_type

    # ─── populare ────────────────────────────────────────────────────────────

    def onInit(self):
        item = self._item

        title     = item.get('title') or item.get('name') or ''
        year      = (item.get('release_date') or item.get('first_air_date') or '')[:4]
        rating    = item.get('vote_average') or 0
        runtime   = item.get('runtime') or 0
        plot      = item.get('overview') or ''
        poster    = (IMG_BASE  + item['poster_path'])   if item.get('poster_path')   else ''
        fanart    = (IMG_FAN   + item['backdrop_path'])  if item.get('backdrop_path')  else ''
        genres    = ' / '.join(g.get('name', '') for g in item.get('genres', []))

        meta_parts = []
        if year:
            meta_parts.append(year)
        if rating:
            meta_parts.append(f'★ {rating:.1f}')
        if runtime:
            meta_parts.append(f'{runtime} min')
        if self._media_type in ('tv', 'tvshow'):
            n = item.get('number_of_seasons', 0)
            if n:
                meta_parts.append(f'{n} sez.')
            status = item.get('status', '')
            if status:
                meta_parts.append(status)

        self.setProperty('title',  title)
        self.setProperty('meta',   '  ·  '.join(meta_parts))
        self.setProperty('genres', genres)
        self.setProperty('poster', poster)
        self.setProperty('fanart', fanart)

        try:
            self.getControl(PLOT_BOX).setText(plot)
        except Exception as exc:
            xbmc.log(f'[Samus] InfoDialog plot error: {exc}', xbmc.LOGWARNING)

        # Etichetă buton principal
        try:
            label = 'Sezoane' if self._media_type in ('tv', 'tvshow') else 'Redă'
            self.getControl(BTN_PRIMARY).setLabel(label)
        except Exception:
            pass

        # Colecție — vizibil doar pentru filme care aparțin unei colecții
        coll = item.get('belongs_to_collection') if self._media_type == 'movie' else None
        if coll and coll.get('id'):
            self.collection_id = coll['id']
            self.setProperty('info.has_collection', '1')
        else:
            self.collection_id = None
            self.clearProperty('info.has_collection')

        credits = item.get('credits') or {}
        if self._media_type in ('tv', 'tvshow') and item.get('aggregate_credits'):
            credits = item.get('aggregate_credits') or credits
        self._raw_cast = credits.get('cast') or []
        self._raw_crew = credits.get('crew') or []
        self._populate_people('cast')
        try:
            self.setFocus(self.getControl(BTN_PRIMARY))
        except Exception:
            pass

    @staticmethod
    def _wrap_name(name):
        if len(name) <= 12 or ' ' not in name:
            return name
        mid   = len(name) // 2
        left  = name.rfind(' ', 0, mid)
        right = name.find(' ', mid)
        if left == -1:
            split = right
        elif right == -1:
            split = left
        else:
            split = left if (mid - left) <= (right - mid) else right
        return name[:split] + '[CR]' + name[split + 1:]

    @staticmethod
    def _unique_join(values, limit=3):
        unique = []
        for value in values:
            value = (value or '').strip()
            if value and value not in unique:
                unique.append(value)
        text = ' / '.join(unique[:limit])
        return text + (f' +{len(unique) - limit}' if len(unique) > limit else '')

    def _cast_subtitle(self, person):
        roles = person.get('roles') or []
        if roles:
            characters = self._unique_join(r.get('character') for r in roles)
            episodes = int(person.get('total_episode_count') or
                           sum(int(r.get('episode_count') or 0) for r in roles))
            return '  •  '.join(x for x in (f'{episodes} ep.' if episodes else '', characters) if x)
        return person.get('character') or ''

    def _crew_subtitles(self, person):
        jobs = person.get('jobs') or []
        raw_jobs = [j.get('job') for j in jobs] if jobs else [person.get('job')]
        return [_CREW_JOBS[j] for j in raw_jobs if j in _CREW_JOBS]

    def _populate_people(self, mode):
        try:
            panel = self.getControl(CAST_PANEL)
            panel.reset()
            self._people_mode = mode
            raw_people = self._raw_cast if mode == 'cast' else self._raw_crew
            merged, order = {}, []
            for person in raw_people:
                name = (person.get('name') or '').strip()
                if not name:
                    continue
                subtitles = ([self._cast_subtitle(person)] if mode == 'cast'
                             else self._crew_subtitles(person))
                subtitles = [s for s in subtitles if s]
                if mode == 'crew' and not subtitles:
                    continue
                key = person.get('id') or name
                if key not in merged:
                    merged[key] = {'person': person, 'subtitles': []}
                    order.append(key)
                for subtitle in subtitles:
                    if subtitle not in merged[key]['subtitles']:
                        merged[key]['subtitles'].append(subtitle)
            self._people = []
            for key in order:
                entry = merged[key]
                person = entry['person']
                name = (person.get('name') or '').strip()
                subtitle = self._unique_join(entry['subtitles'])
                profile = person.get('profile_path')
                thumb     = (IMG_PROF + profile) if profile else ''
                li = xbmcgui.ListItem(label=self._wrap_name(name), label2=subtitle)
                li.setArt({'thumb': thumb, 'icon': thumb})
                panel.addItem(li)
                self._people.append(person)
            self._cast = self._people
            self.getControl(TAB_CAST).setLabel(
                '[B]Distribuție[/B]' if mode == 'cast' else 'Distribuție')
            self.getControl(TAB_CREW).setLabel(
                '[B]Echipă[/B]' if mode == 'crew' else 'Echipă')
        except Exception as exc:
            xbmc.log(f'[Samus] InfoDialog people error: {exc}', xbmc.LOGWARNING)

    # ─── interacțiune ────────────────────────────────────────────────────────

    def onClick(self, controlId):
        if controlId in (TAB_CAST, TAB_CREW):
            self._populate_people('cast' if controlId == TAB_CAST else 'crew')
            try:
                self.setFocus(self.getControl(CAST_PANEL))
            except Exception:
                pass
        elif controlId == CAST_PANEL:
            try:
                pos = self.getControl(CAST_PANEL).getSelectedPosition()
                if 0 <= pos < len(self._people):
                    actor = self._people[pos]
                    pid   = actor.get('id')
                    name  = (actor.get('name') or '').strip()
                    if pid and name:
                        self.navigate_to = (pid, name)
                        self.close()
            except Exception as exc:
                xbmc.log(f'[Samus] InfoDialog onClick error: {exc}', xbmc.LOGWARNING)
        elif controlId == BTN_PRIMARY:
            self.play_action = 'seasons' if self._media_type in ('tv', 'tvshow') else 'play'
            self.close()
        elif controlId == BTN_SOURCES:
            self.play_action = 'sources'
            self.close()
        elif controlId == BTN_TRAILER:
            self.play_action = 'trailer'
            self.close()
        elif controlId == 503:
            self.play_action = 'collection'
            self.close()
        elif controlId == BTN_SIMILAR:
            self.play_action = 'similar'
            self.close()

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.close()
