# -*- coding: utf-8 -*-
import re
import requests
import xbmc

_WP_API  = 'https://pandamovies.pw/wp-json/wp/v2/posts'
_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'}

# Embed hosts recognized as streamable (not download links)
_EMBED_HOSTS = re.compile(
    r'https?://(?:'
    r'doply\.net|dood(?:stream)?\.\w+|'
    r'mixdrop\.\w+|'
    r'streamtape\.\w+|'
    r'voe\.\w+|'
    r'upstream\.\w+'
    r')/', re.IGNORECASE
)


def _search(title):
    try:
        r = requests.get(_WP_API, params={
            'search':    title,
            'per_page':  5,
            '_fields':   'title,link',
        }, headers=_HEADERS, timeout=10)
        r.raise_for_status()
        posts = r.json()
        return posts[0]['link'] if posts else None
    except Exception as e:
        xbmc.log(f'[Samus/PandaMovies] search error: {e}', xbmc.LOGERROR)
        return None


def _scrape_embeds(page_url):
    try:
        r = requests.get(page_url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return re.findall(r'href=["\'](' + _EMBED_HOSTS.pattern + r'[^"\']+)["\']', r.text, re.IGNORECASE)
    except Exception as e:
        xbmc.log(f'[Samus/PandaMovies] scrape error: {e}', xbmc.LOGERROR)
        return []


def _host_label(url):
    m = re.match(r'https?://(?:www\.)?([^/]+)', url)
    if not m:
        return 'Embed'
    domain = m.group(1).split('.')[0].capitalize()
    return domain


def get_sources(title, year=None):
    query = f'{title} {year}' if year else title
    page_url = _search(query)
    if not page_url and year:
        page_url = _search(title)
    if not page_url:
        xbmc.log(f'[Samus/PandaMovies] niciun rezultat pentru: {title}', xbmc.LOGWARNING)
        return []

    xbmc.log(f'[Samus/PandaMovies] pagină găsită: {page_url}', xbmc.LOGINFO)
    embeds = _scrape_embeds(page_url)
    if not embeds:
        xbmc.log(f'[Samus/PandaMovies] niciun embed pe: {page_url}', xbmc.LOGWARNING)
        return []

    sources = []
    seen = set()
    for url in embeds:
        if url in seen:
            continue
        seen.add(url)
        sources.append({
            'url':        url,
            'quality':    '',
            'title_line': f'PandaMovies [{_host_label(url)}]',
            'size':       None,
            'direct':     False,
        })
    xbmc.log(f'[Samus/PandaMovies] {len(sources)} surse găsite pentru: {title}', xbmc.LOGINFO)
    return sources
