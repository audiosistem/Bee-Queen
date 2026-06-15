# created by luc_kodi for jacksparrowscrapers
"""
jacksparrowscrapers Project
Fuente: Peerflix (Stremio add-on: com.keopps.peerflix)

Formato real del stream object (verificado en Stremio):
  name:  "Peerflix 🇪🇸 1080p"          → language flag + quality
  title: "Titulo humano (año) [tags]\n  → línea 0: título legible (opcional)
          Filename.mkv\n               → línea 1: fichero real con extensión
          👤 3 💾 1.37 GB 🌐 Proveedor"  → última línea: seeders, tamaño, fuente

Configuración Kodi (settings.xml):
  peerflix.language       → 0=en  1=es  2=en+es (parallel)
  peerflix.qualityfilter  → exclusiones de calidad enviadas a la API
  peerflix.min.seeders    → mínimo de seeders para incluir resultado
"""
from json import loads as jsloads
import re
from resources.lib.jacksparrow import client
from resources.lib.jacksparrow import source_utils
from resources.lib.jacksparrow import workers
from resources.lib.jacksparrow.control import setting as getSetting

# ── Regex helpers ──────────────────────────────────────────────────────────────
_META_RE   = re.compile(r'[👤💾🌐]')
_VIDEO_EXT = re.compile(r'\.(mkv|avi|mp4|mov|m4v|ts|m2ts|wmv)$', re.IGNORECASE)
_SIZE_RE   = re.compile(r'([\d]+(?:[.,]\d+)?\s*(?:GB|GiB|Gb|MB|MiB|Mb))', re.IGNORECASE)
_FLAG_RE   = re.compile('[\U0001F1E6-\U0001F1FF]{2}')
_MULTI_RE  = re.compile(r'\b(multi|dual|dl)\b', re.IGNORECASE)

# ── Flag → idioma ISO-639-1 ────────────────────────────────────────────────────
_FLAG_LANG = {
    '🇪🇸': 'es', '🇲🇽': 'es', '🇦🇷': 'es', '🇨🇴': 'es', '🇵🇪': 'es',
    '🇬🇧': 'en', '🇺🇸': 'en',
    '🇫🇷': 'fr', '🇧🇪': 'fr',
    '🇩🇪': 'de', '🇦🇹': 'de',
    '🇮🇹': 'it',
    '🇵🇹': 'pt', '🇧🇷': 'pt',
    '🇷🇺': 'ru',
    '🇯🇵': 'ja', '🇰🇷': 'ko', '🇨🇳': 'zh',
    '🇳🇱': 'nl', '🇵🇱': 'pl', '🇹🇷': 'tr',
}

# ── Opciones de qualityfilter (índice → valor para la API) ─────────────────────
_QF_MAP = {
    '0': '',                                   # Sin filtro
    '1': 'screener,vhs,cam',                   # Excluir CAM/Screener
    '2': 'screener,vhs,cam,sd',                # + SD
    '3': 'screener,vhs,cam,sd,480p',           # + 480p
    '4': 'screener,vhs,cam,sd,480p,540p',      # + 540p
}


def _parse_stream(file):
    """
    Parsea un objeto stream de Peerflix y devuelve un dict con los campos
    necesarios para construir el item de fuente.
    """
    name_field  = file.get('name') or ''
    title_field = (file.get('title') or '').replace('┈➤', '\n')

    lines = [l.strip() for l in title_field.split('\n') if l.strip()]

    meta_line     = ''
    content_lines = []
    for line in lines:
        if _META_RE.search(line):
            meta_line = line
        else:
            content_lines.append(line)

    # Filename: línea con extensión de vídeo; fallback → última línea de contenido
    filename = ''
    for line in reversed(content_lines):
        if _VIDEO_EXT.search(line):
            filename = line
            break
    if not filename:
        filename = content_lines[-1] if content_lines else ''

    # Provider desde "🌐 Wolfmax4k"
    m_prov   = re.search(r'🌐\s*(\S+)', meta_line)
    provider = m_prov.group(1) if m_prov else 'peerflix'

    # Seeders desde "👤 3"
    m_seed  = re.search(r'👤\s*(\d+)', meta_line)
    seeders = int(m_seed.group(1)) if m_seed else 0

    # Tamaño: behaviorHints > "💾 X GB" en meta_line > "[1.37GB]" en contenido
    size_str   = ''
    hints      = file.get('behaviorHints') or {}
    video_size = int(hints.get('videoSize') or 0)
    if video_size > 0:
        size_str = '%.2f GB' % (video_size / 1073741824)
    else:
        m_size = re.search(r'💾\s*' + _SIZE_RE.pattern, meta_line, re.IGNORECASE)
        if m_size:
            size_str = m_size.group(1)
        else:
            for line in content_lines:
                m_br = re.search(r'\[(' + _SIZE_RE.pattern[1:-1] + r')\]', line, re.IGNORECASE)
                if m_br:
                    size_str = m_br.group(1)
                    break
            if not size_str:
                m_any = _SIZE_RE.search(meta_line)
                if m_any:
                    size_str = m_any.group(1)

    # Idioma desde flag en name_field ("Peerflix 🇪🇸 1080p")
    lang        = 'en'
    flag_match  = re.search('[\U0001F1E6-\U0001F1FF]{2}', name_field)
    if flag_match:
        lang = _FLAG_LANG.get(flag_match.group(0), file.get('language') or 'en')
    elif file.get('language'):
        lang = file['language'].lower()

    # ── Todos los idiomas detectados (client-side filter, v1.0.31) ─────────────
    # Un stream multi-audio puede traer varias flags; las recogemos todas de
    # name + title, más el campo 'language' si existe, más la marca MULTI/DUAL.
    langs    = set()
    all_text = '%s %s' % (name_field, title_field)
    for flag in _FLAG_RE.findall(all_text):
        code = _FLAG_LANG.get(flag)
        if code:
            langs.add(code)
    if file.get('language'):
        langs.add(str(file['language']).lower())
    is_multi = bool(_MULTI_RE.search(all_text))
    if is_multi:
        langs.add('multi')
    if not langs:
        # Sin flag ni campo language: release scene típica -> asumimos inglés
        langs.add('en')

    return {
        'filename'    : filename,
        'all_names'   : content_lines,
        'provider'    : provider,
        'seeders'     : seeders,
        'lang'        : lang,
        'langs'       : langs,
        'is_multi'    : is_multi,
        'size_str'    : size_str,
    }


class source:
    timeout    = 10
    priority   = 2
    pack_capable = False
    hasMovies  = True
    hasEpisodes = True

    DEFAULT_CANDIDATES = (
        'https://peerflix.mov',
        'https://addon.peerflix.mov',
    )

    def __init__(self):
        # ── Settings ──────────────────────────────────────────────────────────
        lang_idx = int(getSetting('peerflix.language') or '0')
        # 0=en  1=es  2=en+es
        self._langs = {0: ['en'], 1: ['es'], 2: ['en', 'es']}.get(lang_idx, ['en'])
        # Conjunto para el filtro client-side (v1.0.31). Los streams MULTI/DUAL
        # siempre pasan porque pueden contener el idioma deseado.
        self._lang_set = set(self._langs)

        qf_idx = getSetting('peerflix.qualityfilter') or '0'
        self._qualityfilter = _QF_MAP.get(qf_idx, '')

        try:
            self.min_seeders = int(getSetting('peerflix.min.seeders') or '0')
        except Exception:
            self.min_seeders = 0

        self._default_headers = {
            'Accept'    : 'application/json',
            'Referer'   : 'https://peerflix.mov',
            'User-Agent': 'jacksparrowscrapers/peerflix (+https://peerflix.mov)',
        }
        self._bases = [b.rstrip('/') for b in self.DEFAULT_CANDIDATES]

    def _headers(self):
        return dict(self._default_headers)

    def _build_path(self, lang, is_tv, imdb, season=None, episode=None):
        """Construye la ruta con language= y qualityfilter= opcionales."""
        parts = ['language=%s' % lang]
        if self._qualityfilter:
            parts.append('qualityfilter=%s' % self._qualityfilter)
        # Formato: /language=en|qualityfilter=.../stream/...
        cfg = '|'.join(parts)
        if is_tv:
            return '/%s/stream/series/%s:%s:%s.json' % (cfg, imdb, season, episode)
        return '/%s/stream/movie/%s.json' % (cfg, imdb)

    def _fetch_streams(self, path):
        """GET sobre todas las bases candidatas. Devuelve (payload, base_url).

        v1.0.31: se mantiene client.request() (es lo que funcionaba en 1.0.11)
        pero se añade logging para diagnosticar fallos. La reescritura a rutas
        estáticas de v1.0.28 fue un error de diagnóstico: el backend de
        peerflix.mov SIGUE siendo dinámico y acepta el prefijo
        /language=..|qualityfilter=../stream/.. — restaurado.
        """
        from resources.lib.jacksparrow import log_utils
        last_exc = None
        for base in self._bases:
            url = base + path
            try:
                res = client.request(url, headers=self._headers(), timeout=self.timeout)
                if not res:
                    log_utils.log('PEERFLIX: respuesta vacía/None de %s' % url, level=log_utils.LOGDEBUG)
                    continue
                try:
                    payload = jsloads(res)
                except Exception:
                    log_utils.log('PEERFLIX: respuesta no-JSON de %s -- %s'
                                  % (url, str(res)[:160]), level=log_utils.LOGWARNING)
                    continue
                if isinstance(payload, dict) and 'streams' in payload:
                    n = len(payload.get('streams') or [])
                    log_utils.log('PEERFLIX: %d streams de %s' % (n, url), level=log_utils.LOGDEBUG)
                    return payload, base
                else:
                    log_utils.log('PEERFLIX: JSON sin clave "streams" de %s (keys=%s)'
                                  % (url, list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__),
                                  level=log_utils.LOGWARNING)
            except Exception as e:
                last_exc = e
                continue
        if last_exc:
            source_utils.scraper_error('PEERFLIX (sin payload): %s' % last_exc)
        else:
            log_utils.log('PEERFLIX: ninguna base devolvió payload para %s' % path, level=log_utils.LOGDEBUG)
        return None, None

    def _collect_streams(self, lang, is_tv, imdb, season, episode, results, idx):
        """Hilo: fetcha streams para un idioma y guarda en results[idx]."""
        path    = self._build_path(lang, is_tv, imdb, season, episode)
        payload, base = self._fetch_streams(path)
        results[idx] = (payload, base)

    def sources(self, data, hostDict):
        sources = []
        if not data:
            return sources
        append = sources.append

        try:
            title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
            title = title.replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ')
            aliases       = data.get('aliases', [])
            episode_title = data['title'] if 'tvshowtitle' in data else None
            total_seasons = data.get('total_seasons') if 'tvshowtitle' in data else None
            year  = data['year']
            imdb  = data['imdb']
            if not imdb:
                return sources

            if 'tvshowtitle' in data:
                season  = int(data['season'])
                episode = int(data['episode'])
                hdlr    = 'S%02dE%02d' % (season, episode)
                is_tv   = True
            else:
                season = episode = None
                hdlr   = year
                is_tv  = False

            # ── Fetch en paralelo para cada idioma configurado ─────────────────
            results = [None] * len(self._langs)
            if len(self._langs) == 1:
                self._collect_streams(self._langs[0], is_tv, imdb, season, episode, results, 0)
            else:
                threads = [
                    workers.Thread(self._collect_streams, lang, is_tv, imdb, season, episode, results, i)
                    for i, lang in enumerate(self._langs)
                ]
                [t.start() for t in threads]
                [t.join() for t in threads]

            # ── Fusionar streams deduplicando por infoHash ─────────────────────
            all_files  = []
            seen_hashes = set()
            base_used  = None
            for payload, base in results:
                if not payload:
                    continue
                if base_used is None:
                    base_used = base
                for f in payload.get('streams', []):
                    h = (f.get('infoHash') or f.get('infohash') or f.get('hash') or '').lower()
                    if h:
                        if h in seen_hashes:
                            continue
                        seen_hashes.add(h)
                    all_files.append(f)

            if not all_files:
                return sources

            undesirables        = source_utils.get_undesirables()
            check_foreign_audio = source_utils.check_foreign_audio()
        except Exception as e:
            source_utils.scraper_error('PEERFLIX: %s' % e)
            return sources

        for file in all_files:
            try:
                package, episode_start = None, 0

                # ── infoHash / magnet ──────────────────────────────────────────
                info_hash = file.get('infoHash') or file.get('infohash') or file.get('hash')
                magnet    = None
                if not info_hash:
                    raw_magnet = file.get('url') or file.get('magnet') or ''
                    if raw_magnet.startswith('magnet:?'):
                        m = re.search(r'btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})', raw_magnet)
                        if m:
                            info_hash = m.group(1)
                        magnet = raw_magnet
                else:
                    magnet = 'magnet:?xt=urn:btih:%s' % info_hash

                if not magnet:
                    continue

                # ── Parseo multi-línea ─────────────────────────────────────────
                parsed    = _parse_stream(file)

                # ── Filtro de idioma client-side (v1.0.31) ─────────────────────
                # Los MULTI/DUAL siempre pasan (pueden incluir el idioma deseado).
                # El resto solo pasa si alguno de sus idiomas está en la selección.
                if not parsed['is_multi'] and not (parsed['langs'] & self._lang_set):
                    continue

                filename  = parsed['filename']
                all_names = parsed['all_names']
                name      = source_utils.clean_name(filename) if filename else source_utils.clean_name(title)

                # check_title: probamos filename y después resto de líneas
                title_ok = source_utils.check_title(title, aliases, name, hdlr, year)
                if not title_ok:
                    for candidate in all_names:
                        alt = source_utils.clean_name(candidate)
                        if alt != name and source_utils.check_title(title, aliases, alt, hdlr, year):
                            name     = alt
                            title_ok = True
                            break

                if not title_ok:
                    if not is_tv:
                        continue
                    valid, last_season = source_utils.filter_show_pack(
                        title, aliases, imdb, year, season, name, total_seasons
                    )
                    if not valid:
                        valid, episode_start, episode_end = source_utils.filter_season_pack(
                            title, aliases, year, season, name
                        )
                        if not valid:
                            continue
                        package = 'season'
                    else:
                        package = 'show'

                name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
                if source_utils.remove_lang(name_info, check_foreign_audio):
                    continue
                if undesirables and source_utils.remove_undesirables(name_info, undesirables):
                    continue

                # ── Seeders ────────────────────────────────────────────────────
                seeders = parsed['seeders'] or int(file.get('seed', 0) or 0)
                if self.min_seeders > seeders:
                    continue

                # ── Calidad e info ─────────────────────────────────────────────
                quality, info = source_utils.get_release_quality(name_info, magnet)
                # Tags codec/HDR/DV/HDR10+/Atmos extraídos del nombre crudo
                # (info_from_name() suprime '+' y otros chars necesarios para
                # detectar HDR10+, AV1, etc.). Sin esto los filtros remove.hdr/
                # hevc/dolby.vision no afectan a fuentes de Peerflix y el
                # _smart_autoplay_sort no aplica el bonus correspondiente.
                info += [t for t in source_utils.get_extra_tags(name) if t not in info]

                # ── Tamaño ─────────────────────────────────────────────────────
                dsize = 0
                try:
                    if parsed['size_str']:
                        dsize, isize = source_utils._size(parsed['size_str'])
                        if isize:
                            info.insert(0, isize)
                except Exception:
                    pass

                info_str = ' | '.join(info)
                item = {
                    'source'    : 'torrent',
                    'language'  : parsed['lang'],
                    'direct'    : False,
                    'debridonly': True,
                    'provider'  : parsed['provider'],
                    'url'       : magnet,
                    'hash'      : info_hash or '',
                    'name'      : name,
                    'name_info' : name_info,
                    'quality'   : quality,
                    'info'      : info_str,
                    'size'      : dsize,
                    'seeders'   : seeders,
                }

                if package:
                    item['package'] = package
                if package == 'show':
                    item.update({'last_season': last_season})
                if episode_start:
                    item.update({'episode_start': episode_start, 'episode_end': episode_end})

                append(item)
            except Exception as e:
                source_utils.scraper_error('PEERFLIX (item): %s' % e)

        return sources
