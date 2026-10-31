# -*- coding: utf-8 -*-
"""Desenefaine catalog pagination and film-only Byse presence filtering."""
import base64
import html
import os
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


class Tags(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.feed(text or '')

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag.lower(), dict(attrs)))


def clean(text):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', text or ''))).strip()


def byse_option(page, base):
    for match in re.finditer(r'<a\b([^>]*)>([\s\S]*?)</a>', page or '', re.I):
        attrs = dict(Tags('<a ' + match.group(1) + '>').tags[0][1])
        encoded = attrs.get('data-src', '')
        if not encoded or not re.search(r'\bbyse(?:wihe)?\b', clean(match.group(2)), re.I):
            continue
        try:
            candidate = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode('utf-8')
        except (ValueError, UnicodeError):
            candidate = html.unescape(encoded)
        if candidate.startswith(('http://', 'https://', '/')):
            return urljoin(base, candidate)
    return ''


def next_page(text, current_url, current_page):
    """Use the site's real SEO next link, including attribute-order variants."""
    candidates = []
    current = urlparse(current_url)
    scope = re.sub(r'/page/\d+/?$', '/', current.path).rstrip('/')
    for tag, attrs in Tags(text).tags:
        if tag not in ('a', 'link') or not attrs.get('href'):
            continue
        target = urljoin(current_url, attrs['href'])
        parsed = urlparse(target)
        if parsed.hostname != current.hostname:
            continue
        match = re.search(r'/page/(\d+)/?$', parsed.path)
        if not match or int(match.group(1)) <= current_page:
            continue
        if re.sub(r'/page/\d+/?$', '/', parsed.path).rstrip('/') != scope:
            continue
        priority = 0 if 'next' in (attrs.get('rel') or '').lower().split() else 1
        candidates.append((priority, int(match.group(1)), target))
    if candidates:
        _, number, target = min(candidates)
        return number, target
    return None


def cards(text, base):
    seen = set()
    for article in re.findall(r'<article\b[\s\S]*?</article>', text or '', re.I):
        tags = Tags(article).tags
        target = ''
        for tag, attrs in tags:
            candidate = urljoin(base, attrs.get('href') or '')
            parsed = urlparse(candidate)
            if tag == 'a' and parsed.hostname in ('desenefaine.com', 'www.desenefaine.com') and re.match(
                    r'^/(?:film|serial|epi|documentar|telenovela)/[^/]+/?$', parsed.path, re.I):
                target = candidate.split('#', 1)[0].split('?', 1)[0]
                break
        if not target or target in seen:
            continue
        seen.add(target)
        title = re.search(r'<h[1-4]\b[^>]*class=["\'][^"\']*entry-title[^"\']*["\'][^>]*>(.*?)</h[1-4]>', article, re.I | re.S)
        images = [attrs for tag, attrs in tags if tag == 'img']
        image = images[0] if images else {}
        title = clean(title.group(1)) if title else clean(image.get('alt'))
        title = title or target.rstrip('/').split('/')[-1].replace('-', ' ').title()
        thumb = image.get('data-src') or image.get('src') or ''
        plot = re.search(r'<div\b[^>]*class=["\'][^"\']*entry-content[^"\']*["\'][^>]*>(.*?)</div>', article, re.I | re.S)
        yield title, target, urljoin(base, thumb) if thumb else '', clean(plot.group(1)) if plot else ''


def cache_path():
    try:
        import xbmcaddon
        import xbmcvfs
        profile = xbmcvfs.translatePath(xbmcaddon.Addon('plugin.video.RomyLive').getAddonInfo('profile'))
        os.makedirs(profile, exist_ok=True)
        return os.path.join(profile, 'desenefaine_byse_v1.sqlite')
    except Exception:
        return ':memory:'


class PresenceCache:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=3)
        self.db.execute('CREATE TABLE IF NOT EXISTS presence (url TEXT PRIMARY KEY, present INTEGER, checked REAL)')

    def get(self, url):
        row = self.db.execute('SELECT present, checked FROM presence WHERE url=?', (url,)).fetchone()
        if row and time.time() - row[1] < (21600 if row[0] else 1800):
            return bool(row[0])
        return None

    def put(self, url, present):
        self.db.execute('INSERT OR REPLACE INTO presence VALUES (?, ?, ?)', (url, int(present), time.time()))
        self.db.commit()

    def close(self):
        self.db.close()


def install(ns, fetch):
    def listing(url, page=1):
        text = fetch(url)
        if not text:
            ns['notify']('[COLOR red]Nu s-a putut incarca categoria Desenefaine.com![/COLOR]')
            return
        entries = list(cards(text, url))
        results = {}
        movies = [entry[1] for entry in entries if urlparse(entry[1]).path.startswith('/film/')]
        cache = None
        try:
            cache = PresenceCache(cache_path())
            results = {target: cache.get(target) for target in movies}
        except (OSError, sqlite3.Error):
            results = {target: None for target in movies}
        pending = [target for target in movies if results.get(target) is None]

        def check(target):
            try:
                detail = fetch(target)
                # Errors / challenge pages are unknown, never cached as absent.
                if not detail:
                    return target, None
                selected = byse_option(detail, target)
                if selected:
                    return target, True
                # Cloudflare's passive JS detection also appears on valid pages.
                # Only an interstitial title or explicit challenge form indicates
                # that the actual detail content was not received.
                if re.search(r'<title\b[^>]*>\s*(?:Just a moment|Attention Required|Security verification)', detail, re.I) or re.search(
                        r'<form\b[^>]*\bid=["\']challenge-form["\']', detail, re.I):
                    return target, None
                if not re.search(r'<(?:html|article|a|iframe)\b', detail, re.I):
                    return target, None
                return target, False
            except Exception:
                return target, None

        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                for target, present in pool.map(check, pending):
                    results[target] = present
                    if cache is not None and present is not None:
                        try:
                            cache.put(target, present)
                        except sqlite3.Error:
                            pass
        finally:
            if cache is not None:
                cache.close()
        added = 0
        for title, target, thumb, plot in entries:
            if target in results and results[target] is not True:
                continue
            ns['_desenefaine_add'](title, ns['_desenefaine_route']('detail', target),
                                  thumb or ns['DESENEFAINE_ICON'], plot)
            added += 1
        following = next_page(text, url, max(1, int(page or 1)))
        if following:
            number, target = following
            ns['_desenefaine_add']('[COLOR aqua][B]Mai mult - Pagina %s[/B][/COLOR]' % number,
                                  ns['_desenefaine_route']('list', target, number),
                                  ns['DESENEFAINE_ICON'], 'Mai multe rezultate - Desenefaine.com')
        unknown = sum(value is None for value in results.values())
        if unknown:
            ns['notify']('[COLOR yellow]%s filme nu au putut fi verificate; nu sunt afisate. Reincearca mai tarziu.[/COLOR]' % unknown)
        elif not added:
            ns['notify']('[COLOR yellow]Nu am gasit titluri eligibile pe aceasta pagina.%s[/COLOR]' %
                         (' Foloseste Mai mult.' if following else ''))

    ns['desenefaine_list_page'] = listing