import xbmcaddon
import requests

_THRAX_KEY_DEFAULT = "7d9f4987bcd1a2026e6a422931bd7dbff0060977d189f37fa5727d9288b4abbb"

_addon = xbmcaddon.Addon()
_BASE  = _addon.getSetting("thrax_base").strip() or "https://api.derzis.xyz"
_KEY   = _addon.getSetting("thrax_key").strip() or _THRAX_KEY_DEFAULT
_HEADERS = {"X-Thrax-Key": _KEY, "Accept-Encoding": "gzip, deflate"}

TIMEOUT = 20

# Rezolvarea Byse are doi pași lenți la origine: pasul `attest`, cu latență
# deliberată (~40s din 2026-07-30, era ~7.5s), plus un proof-of-work anti-bot
# rulat pe server (~5s pe mai multe procese). Total măsurat: ~50s. Cu TIMEOUT-ul
# obișnuit de 20s tăiam exact apelul care reușea, iar clientul cădea inutil pe
# rezolvarea on-device, și mai lentă. Serverul ține rezultatul 10 minute, deci
# reluarea aceleiași redări e instantanee.
TIMEOUTS = {
    "/byse/resolve": 90,
}


def _get(path, **params):
    url = _BASE.rstrip("/") + path
    try:
        r = requests.get(url, params={k: v for k, v in params.items() if v is not None},
                         headers=_HEADERS, timeout=TIMEOUTS.get(path, TIMEOUT))
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None  # 404 = site nu suporta endpoint-ul, nu e eroare
        import xbmc
        xbmc.log(f"[Sarmis/api] Eroare {path}: {e}", xbmc.LOGWARNING)
        return None
    except Exception as e:
        import xbmc
        xbmc.log(f"[Sarmis/api] Eroare {path}: {e}", xbmc.LOGWARNING)
        return None


def categories(site):
    return _get("/sites/categories", site=site) or []


def browse(site, url, page=1):
    return _get("/sites/browse", site=site, url=url, page=page) or {}


def search(site, query, page=1):
    return _get("/sites/search", site=site, q=query, page=page) or {}


def search_all(query, enabled_sites):
    """Caută pe toate site-urile activate simultan (un singur call server-side paralel)."""
    sites_param = ",".join(enabled_sites)
    return _get("/sites/search_all", q=query, sites=sites_param) or {}


def item(site, url):
    return _get("/sites/item", site=site, url=url) or {}


def episodes(site, url, ep_page=1):
    return _get("/sites/episodes", site=site, url=url, ep_page=ep_page)


def episode_sources(site, url):
    return _get("/sites/episode_sources", site=site, url=url) or []


def resolve_vsembed(embed_url):
    data = _get("/vsembed/resolve", url=embed_url)
    return data  # {"url": ..., "referer": ..., "sources": [...]}


def resolve_loom(embed_url):
    data = _get("/loom/resolve", url=embed_url)
    return (data or {}).get("url")
