# subtitles.py
import os
import requests
import xbmcaddon
import xbmcvfs
import xbmc

addon = xbmcaddon.Addon()
profile_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
subs_path = os.path.join(profile_path, 'subs')

SUB_LANGUAGES = addon.getSetting('subs_languages') or 'ro'
SUB_FORMAT = addon.getSetting('subs_format') or 'srt'
SUB_ENCODING = addon.getSetting('subs_encoding') or 'utf-8'

_WYZIE_URL    = 'https://sub.wyzie.io/search'
_WYZIE_KEY    = 'wyzie-9c717eeb19ce0aed4df716f2e3d4fea6'
_VDRK_BASE    = 'https://sub.vdrk.site'
_VDRK_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Referer': 'https://vidrock.net/', 'Origin': 'https://vidrock.net', 'Accept-Encoding': 'gzip, deflate'}

_LANG_NAME_MAP = {
    'ro': ('romanian', 'română', 'romana'),
    'en': ('english',),
    'fr': ('french', 'français', 'franceza'),
    'de': ('german', 'deutsch', 'germana'),
    'it': ('italian', 'italiano'),
    'es': ('spanish', 'español', 'spaniola'),
    'pt': ('portuguese', 'português'),
    'ru': ('russian', 'rusă', 'rusa'),
    'hu': ('hungarian', 'hungarian'),
    'pl': ('polish', 'polish'),
    'cs': ('czech',),
    'sk': ('slovak',),
    'bg': ('bulgarian',),
    'hr': ('croatian',),
    'sr': ('serbian',),
    'nl': ('dutch',),
    'tr': ('turkish',),
    'zh': ('chinese', 'mandarin'),
    'ja': ('japanese',),
    'ko': ('korean',),
    'ar': ('arabic',),
}


def _lang_matches(label, lang_code):
    label_lower = (label or '').lower()
    for name in _LANG_NAME_MAP.get(lang_code, ()):
        if name in label_lower:
            return True
    return False


def _vdrk_fetch(url):
    try:
        r = requests.get(url, headers=_VDRK_HEADERS, timeout=7)
        return r.json() if r.ok else []
    except Exception as e:
        xbmc.log(f'[Samus/vdrk] {e}', xbmc.LOGERROR)
        return []


def search_vdrk(tmdb_id, season=None, episode=None):
    """Fetch subtitle URLs from sub.vdrk.site (v1+v2). Returns direct URLs, preferred langs first."""
    languages = [lang.strip() for lang in SUB_LANGUAGES.split(',') if lang.strip()]

    if season and episode:
        path = f'/tv/{tmdb_id}/{season}/{episode}'
    else:
        path = f'/movie/{tmdb_id}'

    import threading
    results = [[], []]

    def _fetch(idx, version):
        results[idx] = _vdrk_fetch(f'{_VDRK_BASE}/v{version}{path}')

    threads = [threading.Thread(target=_fetch, args=(i, v), daemon=True) for i, v in enumerate([1, 2])]
    for t in threads: t.start()
    for t in threads: t.join(timeout=8)

    seen, preferred, rest = set(), [], []
    for items in results:
        for it in items or []:
            url = it.get('file') or it.get('url') or it.get('src')
            if not url or url in seen:
                continue
            seen.add(url)
            label = it.get('label') or it.get('name') or ''
            if any(_lang_matches(label, lang) for lang in languages):
                preferred.append(url)
            else:
                rest.append(url)

    all_urls = preferred + rest
    xbmc.log(f'[Samus/vdrk] {len(all_urls)} subtitrări ({len(preferred)} preferred) pentru tmdb_id={tmdb_id}', xbmc.LOGINFO)
    return all_urls


def search_subtitles(imdb_id, season=None, episode=None):
    subtitles = []
    languages = [lang.strip() for lang in SUB_LANGUAGES.split(',') if lang.strip()]

    for lang in languages:
        params = {
            'id': imdb_id,
            'language': lang,
            'format': SUB_FORMAT,
            'encoding': SUB_ENCODING,
            'key': _WYZIE_KEY,
        }
        if season and episode:
            params['season'] = season
            params['episode'] = episode

        try:
            response = requests.get(_WYZIE_URL, params=params, timeout=10)
            if response.ok:
                data = response.json()
                if isinstance(data, dict):
                    subtitles.append(data)
                elif isinstance(data, list):
                    subtitles.extend(data)
            else:
                xbmc.log(f'[WyzieSub] Eroare HTTP: {response.status_code}', xbmc.LOGERROR)
        except Exception as e:
            xbmc.log(f'[WyzieSub] Excepție: {e}', xbmc.LOGERROR)

    return subtitles


def download_subtitle(sub, folder_path):
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
    except Exception as e:
        xbmc.log(f'[Subtitles] Eroare creare folder subtitrări: {e}', xbmc.LOGERROR)
        return ''

    url = sub['url']
    filename = f"{sub['media']}.{sub['language']}.{sub['format']}"
    safe_filename = ''.join(c for c in filename if c not in r'\/:*?"<>|')
    path = os.path.join(folder_path, safe_filename)

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        with open(path, 'wb') as f:
            f.write(r.content)
        return path
    except Exception as e:
        xbmc.log(f'[Subtitles] Eroare descărcare: {e}', xbmc.LOGERROR)
        return ''
