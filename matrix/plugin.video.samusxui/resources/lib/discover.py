# -*- coding: utf-8 -*-
"""Tag-uri tematice pentru secțiunea Descoperă.

De ce nu folosim `/recommendations`: pentru teme de nișă e slab — măsurat pe
TMDB, un film ca „Carol" întoarce 0 titluri cu aceeași tematică din primele 20,
„Portret cu o tânără în flăcări" doar 1. Recomandările TMDB vin din
comportamentul agregat al utilizatorilor, deci converg spre titluri populare.

Etichetele (keywords) sunt semnalul precis: o singură interogare
`discover?with_keywords=<id>` sortată după numărul de voturi dă rezultate
practic 100% pe temă. Modulul de față deduce ce tag-uri să-ți propună din ce ai
văzut și ce ai la favorite, ca lista să reflecte gusturile tale, nu o listă
fixă întreținută de noi.

Două filtre s-au dovedit necesare la selecția tag-urilor:
  * **etichetele de stare** („adoring", „complex", „wistful"…) — TMDB le pune pe
    mii de titluri fără legătură între ele; fără excluderea lor, zgomotul domină;
  * **banda de raritate** — sub ~20 de filme eticheta e prea specifică ca să
    producă o listă („santa hat": 3 filme), peste ~2000 e prea generică
    („lgbt": 7047, „based on novel or book": 8265).
"""

from concurrent.futures import ThreadPoolExecutor

import xbmc
import xbmcaddon

from . import db
from . import tmdb

_ADDON = xbmcaddon.Addon('plugin.video.samusxui')

# Vocabular TMDB de „mood", nu de temă.
_MOOD = {
    'adoring', 'compassionate', 'wistful', 'exuberant', 'ambiguous', 'complex',
    'melodramatic', 'empathetic', 'awestruck', 'bitter', 'admiring', 'emotional',
    'intense', 'heartfelt', 'gritty', 'quirky', 'suspenseful', 'uplifting',
    'absorbing', 'poignant', 'tender', 'sentimental', 'somber', 'steamy romance',
    'feel-good', 'dark', 'humorous', 'thought-provoking', 'entertaining',
}

_BAND_LO, _BAND_HI = 20, 2000

_TAGS_TTL  = 6 * 3600
_KW_TTL    = 30 * 24 * 3600
_COUNT_TTL = 30 * 24 * 3600

_MAX_SEEDS    = 25
_MAX_CANDID   = 40
_WORKERS      = 6


def _title_keywords(seed):
    """[(id, nume)] pentru un titlu, cu cache pe disc (etichetele nu se schimbă)."""
    tmdb_id, media = seed
    key = f'kw_{media}_{tmdb_id}'
    cached = db.cache_get(key, _KW_TTL)
    if cached is not None:
        return [(int(k[0]), k[1]) for k in cached]
    try:
        rows = [(k['id'], k['name']) for k in tmdb.keywords(tmdb_id, media) if k.get('name')]
    except Exception as e:
        xbmc.log(f'[SamusXUI/discover] keywords {media}/{tmdb_id}: {e}', xbmc.LOGWARNING)
        return []
    db.cache_set(key, rows)
    return rows


def _keyword_count(kid, media='movie'):
    """Câte titluri poartă eticheta — proxy de raritate, cache lung."""
    key = f'kwcount_{media}_{kid}'
    cached = db.cache_get(key, _COUNT_TTL)
    if cached is not None:
        return int(cached)
    try:
        n = tmdb.keyword_total(kid, media)
    except Exception:
        n = 0
    db.cache_set(key, n)
    return n


def user_tags(limit=14, media='movie'):
    """Tag-urile deduse din istoric + favorite, ordonate după cât de des apar."""
    cache_key = f'discover_tags_{media}_{limit}'
    cached = db.cache_get(cache_key, _TAGS_TTL)
    if cached is not None:
        return [(t[0], int(t[1])) for t in cached]

    seeds = db.get_seed_titles(_MAX_SEEDS)
    if not seeds:
        return []

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        per_seed = list(pool.map(_title_keywords, seeds))

    freq, names = {}, {}
    for rows in per_seed:
        for kid, name in rows:
            if name.lower() in _MOOD:
                continue
            freq[kid] = freq.get(kid, 0) + 1
            names[kid] = name

    if not freq:
        return []

    # Numărăm doar candidații plauzibili — un apel per etichetă, cache 30 de zile.
    candidates = sorted(freq, key=lambda k: -freq[k])[:_MAX_CANDID]
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        counts = dict(zip(candidates, pool.map(lambda k: _keyword_count(k, media), candidates)))

    kept = [k for k in candidates if _BAND_LO <= counts.get(k, 0) <= _BAND_HI]
    kept.sort(key=lambda k: (-freq[k], counts[k]))

    tags = [(names[k][:1].upper() + names[k][1:], k) for k in kept[:limit]]
    db.cache_set(cache_key, tags)
    xbmc.log(f'[SamusXUI/discover] {len(tags)} tag-uri din {len(seeds)} titluri', xbmc.LOGINFO)
    return tags


def _setting(key, fallback=''):
    try:
        return _ADDON.getSetting(key) or fallback
    except Exception:
        return fallback


_TAB_SLOTS = 50


def _tab_names():
    """Numele scrise în Setări → Descoperă, câte unul per tab, în ordine.

    Slot-uri separate (nu un singur câmp cu virgule) fiindcă editarea se face de
    pe telecomandă: schimbi tab-ul 3 fără să rescrii toată lista."""
    names = []
    for i in range(1, _TAB_SLOTS + 1):
        val = _setting(f'discover_tab{i}').strip()
        if val and val not in names:
            names.append(val)
    return names


def custom_tags():
    """Tag-urile definite de utilizator, rezolvate la id-uri TMDb.

    Numele se caută cu /search/keyword; potrivirea exactă are prioritate, altfel
    se ia prima sugestie (așa „time loop" merge chiar dacă TMDb are și
    „time loop paradox"). Perechea nume→id se ține în cache 30 de zile."""
    out = []
    for name in _tab_names():
        key = f'kwname_{name.lower()}'
        kid = db.cache_get(key, _COUNT_TTL)
        if kid is None:
            try:
                hits = tmdb.search_keyword(name)
            except Exception:
                hits = []
            exact = next((h for h in hits if h.get('name', '').lower() == name.lower()), None)
            chosen = exact or (hits[0] if hits else None)
            kid = chosen['id'] if chosen else 0
            db.cache_set(key, kid)
        if kid:
            out.append((name[:1].upper() + name[1:], int(kid)))
        else:
            xbmc.log(f'[SamusXUI/discover] tag necunoscut la TMDb: {name}', xbmc.LOGWARNING)
    return out


def tag_bar(media='movie'):
    """Tag-urile afișate în bară, după preferința din setări."""
    mode = _setting('discover_tags_mode', 'Din gusturile mele')
    try:
        limit = int(_setting('discover_tags_count', '14'))
    except ValueError:
        limit = 14

    mine = custom_tags()
    if mode == 'Doar ale mele':
        return mine
    auto = user_tags(limit=limit, media=media)
    if mode == 'Amândouă':
        seen = {kid for _, kid in mine}
        return mine + [t for t in auto if t[1] not in seen]
    return auto


_SORTS = {
    'Cele mai votate':   'vote_count.desc',
    'Cele mai populare': 'popularity.desc',
    'Cele mai noi':      None,   # depinde de tipul de conținut, vezi mai jos
}


def by_tag(keyword_id, media='movie', page=1):
    """Titlurile care poartă eticheta, în ordinea aleasă din setări."""
    choice = _setting('discover_sort', 'Cele mai votate')
    sort = _SORTS.get(choice, 'vote_count.desc')
    if sort is None:
        sort = 'primary_release_date.desc' if media == 'movie' else 'first_air_date.desc'
    data = tmdb.discover_keyword(media, keyword_id, page=page, sort=sort) or {}
    for r in data.get('results', []):
        r['media_type'] = media
    return data
