# -*- coding: utf-8 -*-
"""Lightweight per-shelf list sort for My Simkl / My Trakt / My TMDb (Gratis Red).

Not Red Light's list_sort_cache stack — settings-backed specs and a simple picker.
"""
from __future__ import absolute_import

import re

from resources.lib.modules import control

SORT_DEFAULT = 'default'
SORT_CHOICES = (
    ('default', 'Provider Default'),
    ('title:asc', 'Title (A-Z)'),
    ('title:desc', 'Title (Z-A)'),
    ('date_added:desc', 'Date Added (newest)'),
    ('date_added:asc', 'Date Added (oldest)'),
    ('year:desc', 'Year (newest)'),
    ('year:asc', 'Year (oldest)'),
    ('release_date:desc', 'Release Date (newest)'),
    ('release_date:asc', 'Release Date (oldest)'),
    ('random', 'Random'),
)

SHELF_LABELS = {
    'plantowatch': 'Plan to Watch',
    'watching': 'Watching',
    'completed': 'Completed',
    'hold': 'On Hold',
    'dropped': 'Dropped',
    'collection': 'Library',
    'watchlist': 'Watchlist',
    'favorites': 'Favorites',
    'watched': 'Watched',
}

SIMKL_SORTABLE = frozenset(('plantowatch', 'watching', 'completed', 'hold', 'dropped'))
TRAKT_SORTABLE = frozenset(('collection', 'watchlist', 'favorites'))
TMDB_SORTABLE = frozenset(('favorites', 'watchlist'))
MDBLIST_SORTABLE = frozenset(('watchlist', 'collection', 'dropped', 'watched'))

_PROVIDER_BRAND = {
    'simkl': 'Simkl',
    'trakt': 'Trakt',
    'tmdb': 'TMDb',
    'mdblist': 'MDBList',
}

_PERSONAL_PREFIX = 'ulist_'


def offers_release_date(provider, shelf=None, media=None):
    """True when the row already carries a release day, before metadata runs."""
    if media == 'episodes':
        return False
    if provider == 'simkl':
        return is_personal_shelf(shelf)
    if provider == 'mdblist':
        return shelf == 'watchlist' or is_personal_shelf(shelf)
    return provider in ('trakt', 'tmdb')


def sort_choices_for(provider, shelf=None, media=None):
    """Drop sorts the payload cannot support."""
    # TMDb never sends an added timestamp. Simkl and MDBList custom lists do not either.
    # Trakt list items include listed_at, and the status shelves that carry a date keep it.
    # Release Date needs a day on the row. Simkl status shelves, MDBList Library, Dropped,
    # and Watched, and episode lists, only have a year or an id.
    choices = SORT_CHOICES
    drop_added = provider == 'tmdb' or (
        provider in ('simkl', 'mdblist') and is_personal_shelf(shelf))
    if drop_added:
        choices = tuple(c for c in choices if not str(c[0]).startswith('date_added'))
    if not offers_release_date(provider, shelf, media):
        choices = tuple(c for c in choices if not str(c[0]).startswith('release_date'))
    return choices


def is_personal_shelf(shelf):
    try:
        return str(shelf or '').startswith(_PERSONAL_PREFIX)
    except Exception:
        return False


def personal_shelf_key(*parts):
    cleaned = []
    for part in parts:
        try:
            text = re.sub(r'[^0-9A-Za-z_.-]+', '_', str(part or '').strip())
        except Exception:
            text = ''
        text = text.strip('._-') or 'x'
        cleaned.append(text)
    return _PERSONAL_PREFIX + '_'.join(cleaned)


def trakt_shelf_from_url(url):
    """Map a My Trakt sync URL or personal list URL to a shelf key."""
    try:
        url = str(url or '')
    except Exception:
        return None
    if '/collection/' in url:
        return 'collection'
    if '/watchlist/' in url:
        return 'watchlist'
    if '/favorites/' in url:
        return 'favorites'
    match = re.search(r'/users/([^/]+)/lists/([^/]+)/items', url)
    if match:
        return personal_shelf_key(match.group(1), match.group(2))
    return None


def tmdb_shelf_from_url(url):
    """Map a My TMDb account URL or personal list URL to a shelf key."""
    try:
        url = str(url or '')
    except Exception:
        return None
    if '/favorite/' in url or '/favourite/' in url:
        return 'favorites'
    if '/watchlist/' in url:
        return 'watchlist'
    match = re.search(r'/list/(\d+)', url)
    if match:
        return personal_shelf_key(match.group(1))
    return None


def setting_id(provider, media, shelf):
    return 'sort.%s.%s.%s' % (provider, media, shelf)


def get_list_sort(provider, media, shelf):
    choices = sort_choices_for(provider, shelf, media)
    valid = frozenset(code for code, _ in choices)
    raw = control.setting(setting_id(provider, media, shelf)) or ''
    if raw in valid:
        return raw
    return SORT_DEFAULT


def set_list_sort(provider, media, shelf, spec):
    control.setSetting(setting_id(provider, media, shelf), spec or SORT_DEFAULT)


def _title_key(title):
    try:
        return str(title or '').lower()
    except Exception:
        return ''


def _year_key(year):
    try:
        return int(re.sub(r'[^0-9]', '', str(year)) or '0')
    except Exception:
        return 0


_RELEASE_RE = re.compile(r'(\d{4})(?:-(\d{2})-(\d{2}))?')


def _release_key(item, newest_first):
    """YYYY-MM-DD. A year alone sorts as 1 January. A missing date sorts last."""
    raw = ''
    try:
        raw = item.get('release_date') or item.get('premiered') or ''
    except Exception:
        raw = ''
    match = _RELEASE_RE.search(str(raw or ''))
    if not match or match.group(1) == '0000':
        return '0000-00-00' if newest_first else '9999-99-99'
    year, month, day = match.group(1), match.group(2), match.group(3)
    if month and day:
        return '%s-%s-%s' % (year, month, day)
    return '%s-01-01' % year


def _shelf_allowed(shelf, sortable=None):
    if is_personal_shelf(shelf):
        return True
    if sortable is not None:
        return shelf in sortable
    return True


def sort_items(items, provider, media, shelf, sortable=None):
    """Return a new list sorted by the user's per-shelf preference. Never raises."""
    if not items:
        return []
    if not _shelf_allowed(shelf, sortable):
        return list(items)
    try:
        spec = get_list_sort(provider, media, shelf)
        if spec == SORT_DEFAULT:
            return list(items)
        if spec == 'random':
            from random import random as _random
            return sorted(items, key=lambda _i: _random())
        field, _, direction = spec.partition(':')
        reverse = direction == 'desc'
        if field == 'title':
            return sorted(items, key=lambda i: _title_key(i.get('title')), reverse=reverse)
        if field == 'date_added':
            return sorted(items, key=lambda i: i.get('collected_at') or '', reverse=reverse)
        if field == 'year':
            return sorted(items, key=lambda i: _year_key(i.get('year')), reverse=reverse)
        if field == 'release_date':
            return sorted(items, key=lambda i: _release_key(i, reverse), reverse=reverse)
        return list(items)
    except Exception:
        return list(items)


def choose_list_sort(provider, media, shelf, sortable=None, heading_label=None):
    """Context-menu picker; refreshes the container on change."""
    try:
        if media not in ('movies', 'tvshows', 'episodes', 'mixed'):
            media = 'tvshows'
        shelf = str(shelf or '')
        if not _shelf_allowed(shelf, sortable):
            return
        choices = sort_choices_for(provider, shelf, media)
        current = get_list_sort(provider, media, shelf)
        labels = []
        for code, label in choices:
            labels.append('[B]%s[/B]' % label if code == current else label)
        brand = _PROVIDER_BRAND.get(provider, str(provider or '').title() or 'List')
        label = heading_label or SHELF_LABELS.get(shelf, 'List')
        heading = '%s Sort — %s' % (brand, label)
        choice = control.selectDialog(labels, heading)
        if choice is None or choice < 0:
            return
        chosen = choices[choice][0]
        if chosen == current:
            return
        set_list_sort(provider, media, shelf, chosen)
        control.infoDialog('Sort: %s' % choices[choice][1], sound=False)
        control.refresh()
    except Exception:
        pass
