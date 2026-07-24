import xbmc
import xbmcgui
import xbmcaddon

_ADDON    = xbmcaddon.Addon('plugin.video.samusxui')
_PATH     = _ADDON.getAddonInfo('path')
IMG_BASE  = 'https://image.tmdb.org/t/p/w500'
IMG_PROF  = 'https://image.tmdb.org/t/p/w185'
IMG_FAN   = 'https://image.tmdb.org/t/p/original'

CAST_PANEL  = 400
PLOT_BOX    = 11
BTN_PRIMARY = 500   # Redă / Sezoane
BTN_SOURCES = 501
BTN_TRAILER = 502


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
        self.navigate_to   = None   # (person_id, person_name)
        self.play_action   = None   # 'play' | 'seasons' | 'trailer' | 'collection'
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

        self._populate_cast(item.get('credits', {}).get('cast', []))
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

    def _populate_cast(self, raw_cast):
        try:
            panel = self.getControl(CAST_PANEL)
            panel.reset()
            self._cast = []
            for actor in raw_cast[:20]:
                name = (actor.get('name') or '').strip()
                if not name:
                    continue
                character = actor.get('character') or ''
                profile   = actor.get('profile_path')
                thumb     = (IMG_PROF + profile) if profile else ''
                li = xbmcgui.ListItem(label=self._wrap_name(name), label2=character)
                li.setArt({'thumb': thumb, 'icon': thumb})
                panel.addItem(li)
                self._cast.append(actor)
        except Exception as exc:
            xbmc.log(f'[Samus] InfoDialog cast error: {exc}', xbmc.LOGWARNING)

    # ─── interacțiune ────────────────────────────────────────────────────────

    def onClick(self, controlId):
        if controlId == CAST_PANEL:
            try:
                pos = self.getControl(CAST_PANEL).getSelectedPosition()
                if 0 <= pos < len(self._cast):
                    actor = self._cast[pos]
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

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.close()
