# -*- coding: utf-8 -*-
"""Build Kodi list items / play stream items."""
import json
import os

import xbmc
import xbmcgui
import xbmcplugin

from .common import (HANDLE, ICON, FANART, PROFILE_PATH, build_url, add_dir,
                     end_directory, get_setting_bool, log, notify)
from . import tmdb as T
from . import sources as SRC
from . import kodi_db as KDB
from . import mylists as ML


# ---------- helpers ----------

def _movie_info(m):
    info = {
        'title': m.get('title') or m.get('name') or '',
        'originaltitle': m.get('original_title', ''),
        'plot': m.get('overview', ''),
        'year': int((m.get('release_date') or '0000')[:4]) if (m.get('release_date') or '').strip() else 0,
        'premiered': m.get('release_date', ''),
        'rating': float(m.get('vote_average') or 0),
        'votes': str(m.get('vote_count') or 0),
        'mediatype': 'movie',
    }
    if m.get('runtime'):
        info['duration'] = int(m['runtime']) * 60
    if m.get('genres'):
        info['genre'] = [g['name'] for g in m['genres']]
    return info


def _tv_info(s):
    info = {
        'title': s.get('name') or s.get('title') or '',
        'tvshowtitle': s.get('name') or '',
        'plot': s.get('overview', ''),
        'year': int((s.get('first_air_date') or '0000')[:4]) if (s.get('first_air_date') or '').strip() else 0,
        'premiered': s.get('first_air_date', ''),
        'rating': float(s.get('vote_average') or 0),
        'votes': str(s.get('vote_count') or 0),
        'mediatype': 'tvshow',
    }
    if s.get('genres'):
        info['genre'] = [g['name'] for g in s['genres']]
    return info


def _art(item):
    return {
        'thumb': T.poster(item.get('poster_path')),
        'poster': T.poster(item.get('poster_path')),
        'fanart': T.backdrop(item.get('backdrop_path')) or FANART,
        'icon': T.poster(item.get('poster_path')) or ICON,
    }


def _marker_for_movie(imdb, tmdb):
    if not get_setting_bool('show_watched_marker', True):
        return ''
    return KDB.label_marker(KDB.get_movie_state(imdb=imdb, tmdb=tmdb))


def _marker_for_episode(imdb, tmdb, season, episode):
    if not get_setting_bool('show_watched_marker', True):
        return ''
    return KDB.label_marker(KDB.get_episode_state(imdb=imdb, tmdb=tmdb,
                                                  season=season, episode=episode))


# ---------- listings ----------

def list_movies(results, next_action=None, next_params=None):
    xbmcplugin.setContent(HANDLE, 'movies')
    for m in results.get('results', []):
        info = _movie_info(m)
        marker = _marker_for_movie(None, m.get('id'))
        li = xbmcgui.ListItem(label=marker + info['title'])
        li.setArt(_art(m))
        try:
            li.setInfo('video', info)
        except Exception:
            pass
        # Resume hint via Kodi resume property (seconds).
        watched, pos, total = KDB.get_movie_state(tmdb=m.get('id'))
        if pos > 30 and total > 0 and not watched:
            try:
                li.setProperty('ResumeTime', str(pos))
                li.setProperty('TotalTime', str(total))
            except Exception:
                pass
        if watched:
            try:
                info['playcount'] = 1
                li.setInfo('video', info)
            except Exception:
                pass
        li.setProperty('IsPlayable', 'true')
        url = build_url(action='play_movie', tmdb_id=m['id'], title=info['title'])
        ctx = ML.context_menu_entries('movie', tmdb_id=m['id'], title=info['title'])
        li.addContextMenuItems(ctx + [
            ('Movie info', 'Action(Info)'),
            ('Browse cast', 'Container.Update(%s)' % build_url(action='movie_cast', tmdb_id=m['id'])),
            ('Mark watched (Trakt)',
             'RunPlugin(%s)' % build_url(action='trakt_mark_watched',
                                         media_type='movie', tmdb_id=m['id'])),
            ('Mark watched (Bingebase)',
             'RunPlugin(%s)' % build_url(action='bingebase_mark_watched',
                                         media_type='movie', tmdb_id=m['id'],
                                         title=info['title'])),
            ('Mark watched (SIMKL)',
             'RunPlugin(%s)' % build_url(action='simkl_mark_watched',
                                         media_type='movie', tmdb_id=m['id'])),
        ], replaceItems=False)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)
    _add_pagination(results, next_action, next_params)
    end_directory('movies')


def list_tv(results, next_action=None, next_params=None):
    xbmcplugin.setContent(HANDLE, 'tvshows')
    for s in results.get('results', []):
        info = _tv_info(s)
        # Show "▶ Continue Sx" marker if any episode resume exists.
        progress = KDB.get_show_progress(tmdb=s.get('id')) if get_setting_bool('show_watched_marker', True) else {}
        marker = ''
        if progress:
            in_progress = [(sn, en, p) for sn, eps in progress.items()
                            for en, (w, p, t) in eps.items() if not w and p > 30]
            watched_count = sum(1 for sn, eps in progress.items() for en, (w, _, _) in eps.items() if w)
            if in_progress:
                in_progress.sort(reverse=True)
                sn, en, _ = in_progress[0]
                marker = '[COLOR FFFFA726]▶ S%02dE%02d[/COLOR] ' % (sn, en)
            elif watched_count:
                marker = '[COLOR FF45D267]✓ %d[/COLOR] ' % watched_count
        li = xbmcgui.ListItem(label=marker + info['title'])
        li.setArt(_art(s))
        try:
            li.setInfo('video', info)
        except Exception:
            pass
        url = build_url(action='tv_seasons', tmdb_id=s['id'], title=info['title'])
        ctx = ML.context_menu_entries('tv', tmdb_id=s['id'], title=info['title'])
        if ctx:
            li.addContextMenuItems(ctx, replaceItems=False)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    _add_pagination(results, next_action, next_params)
    end_directory('tvshows')


def list_seasons(tmdb_id, show):
    xbmcplugin.setContent(HANDLE, 'seasons')
    progress = KDB.get_show_progress(tmdb=tmdb_id) if get_setting_bool('show_watched_marker', True) else {}
    for s in show.get('seasons', []):
        if (s.get('season_number') or 0) == 0 and 'Specials' not in (s.get('name') or ''):
            continue
        sn = s.get('season_number') or 0
        label = s.get('name') or 'Season %s' % sn
        season_eps = progress.get(sn, {})
        marker = ''
        if season_eps:
            wc = sum(1 for _, (w, _, _) in season_eps.items() if w)
            if wc:
                marker = '[COLOR FF45D267]✓ %d[/COLOR] ' % wc
        li = xbmcgui.ListItem(label=marker + label)
        art = {
            'thumb': T.poster(s.get('poster_path')) or T.poster(show.get('poster_path')),
            'poster': T.poster(s.get('poster_path')) or T.poster(show.get('poster_path')),
            'fanart': T.backdrop(show.get('backdrop_path')) or FANART,
        }
        li.setArt(art)
        try:
            li.setInfo('video', {
                'title': label,
                'tvshowtitle': show.get('name', ''),
                'season': sn,
                'plot': s.get('overview') or show.get('overview', ''),
                'mediatype': 'season',
            })
        except Exception:
            pass
        url = build_url(action='tv_episodes', tmdb_id=tmdb_id, season=sn,
                        title=show.get('name', ''))
        ctx = ML.context_menu_entries('tv', tmdb_id=tmdb_id, title=show.get('name', ''))
        if ctx:
            li.addContextMenuItems(ctx, replaceItems=False)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    end_directory('seasons')


def list_episodes(tmdb_id, season_no, show, season_data):
    xbmcplugin.setContent(HANDLE, 'episodes')
    poster = T.poster(show.get('poster_path'))
    fanart = T.backdrop(show.get('backdrop_path')) or FANART
    for ep in season_data.get('episodes', []):
        title = ep.get('name') or 'Episode %s' % ep.get('episode_number')
        en = ep.get('episode_number') or 0
        marker = _marker_for_episode(None, tmdb_id, season_no, en)
        label = '%sS%02dE%02d - %s' % (marker, season_no, en, title)
        li = xbmcgui.ListItem(label=label)
        thumb = T.backdrop(ep.get('still_path'), 'w500') or poster
        li.setArt({'thumb': thumb, 'poster': poster, 'fanart': fanart})
        info = {
            'title': title,
            'tvshowtitle': show.get('name', ''),
            'season': season_no,
            'episode': en,
            'plot': ep.get('overview', ''),
            'aired': ep.get('air_date', ''),
            'rating': float(ep.get('vote_average') or 0),
            'mediatype': 'episode',
        }
        watched, pos, total = KDB.get_episode_state(tmdb=tmdb_id, season=season_no, episode=en)
        if watched:
            info['playcount'] = 1
        try:
            li.setInfo('video', info)
        except Exception:
            pass
        if pos > 30 and total > 0 and not watched:
            try:
                li.setProperty('ResumeTime', str(pos))
                li.setProperty('TotalTime', str(total))
            except Exception:
                pass
        li.setProperty('IsPlayable', 'true')
        url = build_url(action='play_episode', tmdb_id=tmdb_id,
                        season=season_no, episode=en,
                        title=show.get('name', ''))
        ctx = ML.context_menu_entries('tv', tmdb_id=tmdb_id, title=show.get('name', ''))
        ctx += [
            ('Mark watched (Trakt)',
             'RunPlugin(%s)' % build_url(action='trakt_mark_watched',
                                         media_type='tv', tmdb_id=tmdb_id,
                                         season=season_no, episode=en)),
            ('Mark watched (Bingebase)',
             'RunPlugin(%s)' % build_url(action='bingebase_mark_watched',
                                         media_type='tv', tmdb_id=tmdb_id,
                                         season=season_no, episode=en,
                                         title=show.get('name', ''))),
            ('Mark watched (SIMKL)',
             'RunPlugin(%s)' % build_url(action='simkl_mark_watched',
                                         media_type='tv', tmdb_id=tmdb_id,
                                         season=season_no, episode=en)),
        ]
        li.addContextMenuItems(ctx, replaceItems=False)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)
    end_directory('episodes')


def list_people(results, next_action=None, next_params=None):
    xbmcplugin.setContent(HANDLE, 'artists')
    for p in results.get('results', []):
        li = xbmcgui.ListItem(label=p.get('name', ''))
        li.setArt({
            'thumb': T.poster(p.get('profile_path')),
            'poster': T.poster(p.get('profile_path')),
            'fanart': FANART,
            'icon': T.poster(p.get('profile_path')) or ICON,
        })
        try:
            li.setInfo('video', {'title': p.get('name', ''), 'plot': 'Known for: ' + ', '.join(
                (kf.get('title') or kf.get('name') or '') for kf in (p.get('known_for') or [])[:3])})
        except Exception:
            pass
        url = build_url(action='person', person_id=p['id'], name=p.get('name', ''))
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    _add_pagination(results, next_action, next_params)
    end_directory('artists')


def _add_pagination(results, action, extra_params=None):
    if not action:
        return
    page = int(results.get('page') or 1)
    total = int(results.get('total_pages') or 1)
    if page < total:
        params = {'action': action, 'page': page + 1}
        if extra_params:
            # Don't let extras overwrite action/page
            for k, v in extra_params.items():
                if k not in ('action', 'page') and v is not None:
                    params[k] = v
        add_dir('Next page (%d/%d) »' % (page + 1, total), params,
                art={'icon': ICON, 'thumb': ICON, 'fanart': FANART})


# ---------- continue watching ----------

def _resolve_tmdb_from_imdb(imdb, media_type):
    if not imdb:
        return None
    try:
        data = T._get('/find/%s' % imdb, {'external_source': 'imdb_id'}, ttl=86400)
        bucket = 'movie_results' if media_type == 'movie' else 'tv_results'
        results = data.get(bucket) or []
        if results:
            return results[0].get('id')
    except Exception:
        pass
    return None


def list_continue_movies():
    xbmcplugin.setContent(HANDLE, 'movies')
    items = KDB.get_continue_watching_movies(limit=30)
    if not items:
        notify('Nothing to continue — play something first', time=3000)
        end_directory('movies')
        return
    for it in items:
        tmdb_id = it.get('tmdb')
        if not tmdb_id and it.get('imdb'):
            tmdb_id = _resolve_tmdb_from_imdb(it['imdb'], 'movie')
        if not tmdb_id:
            continue
        try:
            m = T.movie_details(tmdb_id)
        except Exception:
            continue
        info = _movie_info(m)
        try:
            pct = int(it['position'] / it['total'] * 100) if it['total'] else 0
        except Exception:
            pct = 0
        marker = '[COLOR FFFFA726]▶ %d%%[/COLOR] ' % pct if pct else '[COLOR FFFFA726]▶[/COLOR] '
        li = xbmcgui.ListItem(label=marker + info['title'])
        li.setArt(_art(m))
        try:
            li.setInfo('video', info)
        except Exception:
            pass
        if it['position'] > 30 and it['total'] > 0:
            try:
                li.setProperty('ResumeTime', str(it['position']))
                li.setProperty('TotalTime', str(it['total']))
            except Exception:
                pass
        li.setProperty('IsPlayable', 'true')
        url = build_url(action='play_movie', tmdb_id=tmdb_id, title=info['title'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)
    end_directory('movies')


def list_continue_tv():
    xbmcplugin.setContent(HANDLE, 'episodes')
    items = KDB.get_continue_watching_shows(limit=30)
    if not items:
        notify('Nothing to continue — play something first', time=3000)
        end_directory('episodes')
        return
    for it in items:
        tmdb_id = it.get('tmdb')
        if not tmdb_id and it.get('imdb'):
            tmdb_id = _resolve_tmdb_from_imdb(it['imdb'], 'tv')
        if not tmdb_id:
            continue
        try:
            show = T.tv_details(tmdb_id)
        except Exception:
            continue
        sn = int(it['season'] or 0)
        en = int(it['episode'] or 0)
        ep_meta = {}
        try:
            season_data = T.tv_season(tmdb_id, sn)
            for ep in season_data.get('episodes', []):
                if int(ep.get('episode_number') or 0) == en:
                    ep_meta = ep; break
        except Exception:
            pass
        ep_title = ep_meta.get('name') or 'Episode %d' % en
        try:
            pct = int(it['position'] / it['total'] * 100) if it['total'] else 0
        except Exception:
            pct = 0
        prefix = '[COLOR FFFFA726]▶ %d%%[/COLOR] ' % pct if pct else '[COLOR FFFFA726]▶[/COLOR] '
        label = '%s%s — S%02dE%02d - %s' % (prefix, show.get('name', ''), sn, en, ep_title)
        li = xbmcgui.ListItem(label=label)
        poster = T.poster(show.get('poster_path'))
        thumb = T.backdrop(ep_meta.get('still_path'), 'w500') or poster
        li.setArt({'thumb': thumb, 'poster': poster,
                   'fanart': T.backdrop(show.get('backdrop_path')) or FANART})
        info = {
            'title': ep_title, 'tvshowtitle': show.get('name', ''),
            'season': sn, 'episode': en,
            'plot': ep_meta.get('overview') or show.get('overview', ''),
            'aired': ep_meta.get('air_date', ''),
            'mediatype': 'episode',
        }
        try:
            li.setInfo('video', info)
        except Exception:
            pass
        if it['position'] > 30 and it['total'] > 0:
            try:
                li.setProperty('ResumeTime', str(it['position']))
                li.setProperty('TotalTime', str(it['total']))
            except Exception:
                pass
        li.setProperty('IsPlayable', 'true')
        url = build_url(action='play_episode', tmdb_id=tmdb_id, season=sn,
                        episode=en, title=show.get('name', ''))
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)
    end_directory('episodes')


# ---------- play ----------

PREF_QUALITY = ['4K', '1440p', '1080p', '720p', '480p', '360p', '240p', 'HLS', 'MP4', 'AUTO']

# ---- per-show quality memory ----

QUALITY_MEM_FILE = os.path.join(PROFILE_PATH, 'quality_memory.json')


def _load_quality_mem():
    try:
        if os.path.exists(QUALITY_MEM_FILE):
            with open(QUALITY_MEM_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_quality_mem(mem):
    try:
        with open(QUALITY_MEM_FILE, 'w', encoding='utf-8') as f:
            json.dump(mem, f)
    except Exception:
        pass


def _remember_quality(key, quality):
    if not get_setting_bool('remember_quality', True) or not quality:
        return
    mem = _load_quality_mem()
    mem[str(key)] = quality
    _save_quality_mem(mem)


def _recall_quality(key):
    if not get_setting_bool('remember_quality', True):
        return None
    return _load_quality_mem().get(str(key))


# ---- play entry points ----

def play_movie(tmdb_id):
    details = T.movie_details(tmdb_id)
    imdb = (details.get('external_ids') or {}).get('imdb_id')
    title = details.get('title') or details.get('original_title')
    year = None
    rd = details.get('release_date') or ''
    if rd and len(rd) >= 4:
        try:
            year = int(rd[:4])
        except ValueError:
            pass
    notify('Resolving stream...', time=2000)
    primary, secondary = _resolve_with_picker('movie', tmdb_id, imdb_id=imdb,
                                              title=title, year=year)
    streams = _combine_with_user_choice(primary, secondary, key='movie:%s' % tmdb_id)
    _pick_and_play(streams, _movie_info(details), _art(details),
                   media_type='movie', imdb_id=imdb, tmdb_id=tmdb_id,
                   memory_key='movie:%s' % tmdb_id)


def play_episode(tmdb_id, season, episode):
    show = T.tv_details(tmdb_id)
    imdb = (show.get('external_ids') or {}).get('imdb_id')
    title = show.get('name') or show.get('original_name')
    year = None
    fd = show.get('first_air_date') or ''
    if fd and len(fd) >= 4:
        try:
            year = int(fd[:4])
        except ValueError:
            pass
    notify('Resolving stream...', time=2000)
    primary, secondary = _resolve_with_picker('tv', tmdb_id, season=season,
                                              episode=episode, imdb_id=imdb,
                                              title=title, year=year)
    streams = _combine_with_user_choice(primary, secondary, key='tv:%s' % tmdb_id)
    info = _tv_info(show)
    info.update({'season': int(season), 'episode': int(episode), 'mediatype': 'episode'})
    _pick_and_play(streams, info, _art(show),
                   media_type='tv', imdb_id=imdb, tmdb_id=tmdb_id,
                   season=season, episode=episode,
                   memory_key='tv:%s' % tmdb_id)


def _resolve_with_picker(media_type, tmdb_id, season=None, episode=None,
                         imdb_id=None, title=None, year=None):
    show_picker = (get_setting_bool('enable_secondary_source', False)
                   and get_setting_bool('show_source_picker', False))
    force = None
    if show_picker:
        choice = xbmcgui.Dialog().select('Select source',
                                         ['Primary (vidsrc)', 'Secondary (vidsrc.xyz / 2embed)'])
        if choice == 0:
            force = 'primary'
        elif choice == 1:
            force = 'secondary'
        else:
            return [], []
    return SRC.resolve(media_type, tmdb_id, season=season, episode=episode,
                       imdb_id=imdb_id, force_provider=force,
                       title=title, year=year)


def _combine_with_user_choice(primary, secondary, key=None):
    """Apply server sub-picker for multiple cloudnestra mirrors, then merge with secondary."""
    if get_setting_bool('show_server_picker', True):
        servers = sorted({s.get('server', 'Cloudnestra') for s in primary
                           if s.get('provider') == 'primary'})
        # Only ask if more than one cloudnestra mirror is detected (i.e. multiple "#N" entries).
        if len(servers) > 1:
            labels = ['All servers (auto)'] + servers
            idx = xbmcgui.Dialog().select('Select Cloudnestra server', labels)
            if idx > 0:
                primary = [s for s in primary if s.get('server') == servers[idx - 1]]
    return primary + secondary


def _pick_and_play(streams, info, art, media_type='movie', imdb_id=None, tmdb_id=None,
                   season=None, episode=None, memory_key=None):
    if not streams:
        notify('No playable source found', time=4000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    def _rank(s):
        # File-host streams ALWAYS go to the bottom of the picker (per
        # explicit user requirement: existing direct-URL streams from
        # Cloudnestra / Vidnest / Stigstream stay on top, and any link
        # that requires ResolveURL sits below them so the user picks a
        # direct stream first when both are available).
        try:
            qi = PREF_QUALITY.index(s.get('quality', 'AUTO'))
        except ValueError:
            qi = len(PREF_QUALITY)
        is_fh = bool(s.get('needs_resolveurl')) or s.get('provider') == 'filehost'
        weight = s.get('sort_weight') or (999 if is_fh else 0)
        return (weight, qi, -(s.get('bandwidth') or 0), -(s.get('height') or 0))
    streams = sorted(streams, key=_rank)

    auto_play = get_setting_bool('auto_play_first', False)
    chosen = None

    # ---- per-show quality memory ----
    if memory_key and not auto_play and len(streams) > 1:
        recalled = _recall_quality(memory_key)
        if recalled:
            for s in streams:
                if s.get('quality') == recalled:
                    chosen = s
                    log('quality memory: using remembered %s for %s' % (recalled, memory_key))
                    break

    if chosen is None:
        if auto_play or len(streams) == 1:
            chosen = streams[0]
        else:
            labels = [s.get('label') or s.get('url', '') for s in streams]
            idx = xbmcgui.Dialog().select('Select source / quality (best first)', labels)
            if idx < 0:
                xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
                return
            chosen = streams[idx]
            if memory_key:
                _remember_quality(memory_key, chosen.get('quality'))

    # Build list of streams to use for fallback chain (chosen first, then the rest).
    chain = [chosen] + [s for s in streams if s is not chosen]

    # ALWAYS route through the player monitor so Trakt / SIMKL / Bingebase
    # scrobbling and local watched-marking fire on every playback — including
    # the single-stream case (previously only used the monitor when len>1 and
    # auto_fallback was enabled, which silently disabled all tracking on
    # titles that only returned one candidate).
    _play_via_monitor(chain, info, art, media_type=media_type,
                      imdb_id=imdb_id, tmdb_id=tmdb_id,
                      season=season, episode=episode)


def _play_via_monitor(chain, info, art, media_type='movie', imdb_id=None, tmdb_id=None,
                       season=None, episode=None):
    from .player_monitor import VidscrPlayer
    # Resolve immediately so Kodi has a list item; the monitor will then take
    # over (observe playback, fire scrobble events, switch streams on stall).
    li = _build_listitem(chain[0], info, art)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)
    player = VidscrPlayer()
    # skip_first_play=True because setResolvedUrl already triggers playback of
    # the first stream — calling player.play() again would restart it.
    player.play_stream_list(chain, info, art, media_type=media_type,
                            imdb_id=imdb_id, tmdb_id=tmdb_id,
                            season=season, episode=episode,
                            build_listitem_fn=_build_listitem,
                            skip_first_play=True)


def _play_stream(stream, info, art):
    if not stream:
        notify('No playable source found', time=4000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    li = _build_listitem(stream, info, art)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def _build_listitem(stream, info, art):
    url = stream['url']
    # File-host streams: crack via script.module.resolveurl. The bridge
    # falls back to a clear notification if RU isn't installed instead
    # of crashing — and existing direct-URL streams never enter this
    # branch (they never set ``needs_resolveurl``).
    if stream.get('needs_resolveurl'):
        from . import resolveurl_bridge as RU
        log('listing: routing file-host URL through ResolveURL: %s'
            % url[:100])
        resolved = RU.resolve(url)
        if not resolved:
            notify('Could not resolve %s' % (stream.get('host_name') or 'host'),
                   time=4000)
            li = xbmcgui.ListItem(path='')
            return li
        log('listing: ResolveURL -> %s' % resolved[:120])
        url = resolved
        # Clear hoster-specific headers — the resolved URL is direct.
        stream = dict(stream, url=url, headers={})

    headers = stream.get('headers') or {}
    is_hls = '.m3u8' in url.lower()
    is_mp4 = '.mp4' in url.lower()
    use_isa = get_setting_bool('use_inputstream', True) and is_hls

    if use_isa:
        li = xbmcgui.ListItem(path=url)
        li.setMimeType('application/vnd.apple.mpegurl')
        li.setContentLookup(False)
        try:
            li.setProperty('inputstream', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
            if headers:
                hdr = '&'.join('%s=%s' % (k, _q(v)) for k, v in headers.items())
                li.setProperty('inputstream.adaptive.stream_headers', hdr)
                li.setProperty('inputstream.adaptive.manifest_headers', hdr)
        except Exception as e:
            log('ISA setup failed: %s' % e)
    else:
        play_url = url
        if headers:
            play_url = url + '|' + '&'.join('%s=%s' % (k, _q(v)) for k, v in headers.items())
        li = xbmcgui.ListItem(path=play_url)
        if is_hls:
            li.setMimeType('application/vnd.apple.mpegurl')
            li.setContentLookup(False)
        elif is_mp4:
            li.setMimeType('video/mp4')
            li.setContentLookup(False)

    li.setArt(art)
    try:
        li.setInfo('video', info)
    except Exception:
        pass
    return li


def _q(v):
    import requests
    return requests.utils.quote(v, safe='')


# Backwards compatibility: still used by play_episode_imdb in default.py
def _pick_and_play_compat(streams, info, art):
    _pick_and_play(streams, info, art)


# Re-export under the old private name so default.py keeps working.
globals()['_pick_and_play'] = _pick_and_play
