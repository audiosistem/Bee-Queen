# -*- coding: utf-8 -*-

import sys

from resources.lib.modules import bookmarks
from resources.lib.modules import control
from resources.lib.modules import mdblist
from resources.lib.modules import simkl
from resources.lib.modules import trakt


def _provider():
    try:
        return simkl.getIndicatorsProvider()
    except Exception:
        return 'trakt' if trakt.getTraktIndicatorsInfo() else 'local'


# Movie vs TV caches are separate in Gratis. A movie mark must not skip the next episode-list sync.
_LIST_SYNC_SKIP_PROPS = {
    ('trakt', 'movie'): 'gratisred.trakt_skip_list_sync_movies',
    ('trakt', 'tv'): 'gratisred.trakt_skip_list_sync_tv',
    ('simkl', 'movie'): 'gratisred.simkl_skip_list_sync_movies',
    ('simkl', 'tv'): 'gratisred.simkl_skip_list_sync_tv',
    ('mdblist', 'movie'): 'gratisred.mdblist_skip_list_sync_movies',
    ('mdblist', 'tv'): 'gratisred.mdblist_skip_list_sync_tv',
}


def _arm_provider_list_sync_skip(provider=None, media='tv'):
    """Next matching list open already has a fresh local cache — skip that cloud pull only."""
    provider = provider or _provider()
    prop = _LIST_SYNC_SKIP_PROPS.get((provider, media))
    if not prop:
        return
    try:
        control.window.setProperty(prop, 'true')
    except Exception:
        pass


def _consume_provider_list_sync_skip(provider=None, media='tv'):
    provider = provider or _provider()
    prop = _LIST_SYNC_SKIP_PROPS.get((provider, media))
    if not prop:
        return False
    try:
        if control.window.getProperty(prop) == 'true':
            control.window.clearProperty(prop)
            return True
    except Exception:
        pass
    return False


def getMovieIndicators(refresh=False):
    provider = _provider()
    if provider == 'local':
        try:
            return bookmarks._indicators()
        except Exception:
            return
    skip_sync = refresh and _consume_provider_list_sync_skip(provider, 'movie')
    if provider == 'simkl':
        try:
            if refresh and not skip_sync:
                # Activities + date_from delta when possible (same idea as Trakt activity gate).
                simkl.syncSimklWatched(silent=True)
            return simkl.cachesyncMovies(timeout=720)
        except Exception:
            return
    if provider == 'mdblist':
        try:
            if refresh and not skip_sync:
                mdblist.syncMdblistWatched(silent=True)
            return mdblist.cachesyncMovies(timeout=720)
        except Exception:
            return
    try:
        if refresh == False or skip_sync:
            timeout = 720
        elif trakt.getWatchedActivity() < trakt.timeoutsyncMovies():
            timeout = 720
        else:
            timeout = 0
        return trakt.cachesyncMovies(timeout=timeout)
    except Exception:
        pass


def getTVShowIndicators(refresh=False):
    provider = _provider()
    if provider == 'local':
        try:
            return bookmarks._indicators()
        except Exception:
            return
    skip_sync = refresh and _consume_provider_list_sync_skip(provider, 'tv')
    if provider == 'simkl':
        try:
            if refresh and not skip_sync:
                simkl.syncSimklWatched(silent=True)
            return simkl.cachesyncTVShows(timeout=720)
        except Exception:
            return
    if provider == 'mdblist':
        try:
            if refresh and not skip_sync:
                mdblist.syncMdblistWatched(silent=True)
            return mdblist.cachesyncTVShows(timeout=720)
        except Exception:
            return
    try:
        if refresh == False or skip_sync:
            timeout = 720
        elif trakt.getWatchedActivity() < trakt.timeoutsyncTVShows():
            timeout = 720
        else:
            timeout = 0
        return trakt.cachesyncTVShows(timeout=timeout)
    except Exception:
        pass


def getSeasonIndicators(imdb, tmdb=None):
    provider = _provider()
    if provider == 'simkl':
        try:
            return simkl.syncSeason(imdb, tmdb=tmdb)
        except Exception:
            return
    if provider == 'mdblist':
        try:
            return mdblist.syncSeason(imdb, tmdb=tmdb)
        except Exception:
            return
    try:
        if provider != 'trakt':
            raise Exception()
        return trakt.syncSeason(imdb)
    except Exception:
        pass


def getMovieOverlay(indicators_, imdb):
    try:
        if _provider() == 'local':
            overlay = bookmarks._get_watched('movie', imdb, '', '')
            return str(overlay)
        playcount = [i for i in indicators_ if i == imdb]
        overlay = 7 if len(playcount) > 0 else 6
        return str(overlay)
    except:
        return '6'


def aired_episode_total(seasons, last_episode, number_of_episodes=None):
    """Regular-season episodes that have aired. Later seasons still on the schedule are left out."""
    seasons = seasons or []
    last = last_episode if isinstance(last_episode, dict) else None
    try:
        last_s = int(last.get('season_number') or 0) if last else 0
        last_e = int(last.get('episode_number') or 0) if last else 0
    except Exception:
        last_s = last_e = 0
    if last_s > 0 and last_e > 0:
        prior = 0
        cur_count = 0
        for season in seasons:
            try:
                num = int(season.get('season_number') if season.get('season_number') is not None else season.get('number') or 0)
                count = int(season.get('episode_count') or 0)
            except Exception:
                continue
            if num < 1:
                continue
            if num < last_s:
                prior += count
            elif num == last_s:
                cur_count = count
        if cur_count and last_e > cur_count:
            return prior + cur_count
        return prior + last_e
    try:
        if number_of_episodes:
            return int(number_of_episodes)
    except Exception:
        pass
    total = 0
    found = False
    for season in seasons:
        try:
            num = int(season.get('season_number') if season.get('season_number') is not None else season.get('number') or 0)
            if num < 1:
                continue
            total += int(season.get('episode_count') or 0)
            found = True
        except Exception:
            continue
    return total if found else None


def season_aired_count(season_number, episode_count, last_episode):
    """How many episodes in this season have aired. A later season still on the schedule is 0."""
    try:
        season_number = int(season_number)
        episode_count = int(episode_count or 0)
    except Exception:
        return 0
    last = last_episode if isinstance(last_episode, dict) else None
    if not last:
        return episode_count
    try:
        last_s = int(last.get('season_number') or 0)
        last_e = int(last.get('episode_number') or 0)
    except Exception:
        return episode_count
    if last_s < 1 or last_e < 1:
        return episode_count
    if season_number < last_s:
        return episode_count
    if season_number == last_s:
        if episode_count and last_e > episode_count:
            return episode_count
        return last_e
    return 0


def getTVShowOverlay(indicators_, imdb, tmdb, show_status=None, episode_count=None):
    try:
        if _provider() == 'local':
            try:
                total = int(episode_count or 0)
            except Exception:
                total = 0
            if total > 0 and bookmarks.local_watched_count(imdb) >= total:
                return '7'
            return '6'
        tmdb_s = str(tmdb)
        watched_n = 0
        for i in indicators_ or []:
            try:
                if str(i[0]) != tmdb_s:
                    continue
            except Exception:
                continue
            watched = i[2] or []
            if not watched:
                continue
            watched_n = len(watched)
            aired = int(i[1] or 0)
            extra = i[3] if len(i) > 3 and isinstance(i[3], dict) else {}
            if aired > 0:
                if len(watched) >= aired:
                    return '7'
                break
            status = str(extra.get('status') or '').lower()
            if status == 'completed':
                return '7'
            break
        # MDBList sync has no aired total (stored as watched+1 so a partial show stays unticked).
        # episode_count here is episodes that have aired, so a returning show still ticks when caught up.
        if _provider() == 'mdblist' and watched_n:
            try:
                total = int(episode_count or 0)
            except Exception:
                total = 0
            if total > 0 and watched_n >= total:
                return '7'
        return '6'
    except:
        return '6'


def localSeasonWatchedCount(imdb, season):
    """How many episodes in this season are marked watched in local bookmarks."""
    return bookmarks.local_watched_count(imdb, season)


def seasonWatchedCount(indicators_, tmdb, season):
    """How many episodes in this season are in the TV indicator cache."""
    try:
        tmdb_s = str(tmdb)
        season_n = int(season)
    except Exception:
        return 0
    for row in indicators_ or []:
        try:
            if str(row[0]) != tmdb_s:
                continue
        except Exception:
            continue
        count = 0
        for pair in row[2] or []:
            try:
                if int(pair[0]) == season_n:
                    count += 1
            except Exception:
                continue
        return count
    return 0


def getSeasonOverlay(indicators_, imdb, season):
    try:
        if _provider() == 'local':
            playcount = bookmarks._get_watched('season', imdb, season, '')
            return str(playcount)
        playcount = [i for i in indicators_ if int(season) == int(i)]
        playcount = 7 if len(playcount) > 0 else 6
        return str(playcount)
    except:
        return '6'


def getEpisodeOverlay(indicators_, imdb, tmdb, season, episode):
    try:
        if _provider() == 'local':
            overlay = bookmarks._get_watched('episode', imdb, season, episode)
            return str(overlay)
        playcount = [i[2] for i in indicators_ if i[0] == tmdb]
        playcount = playcount[0] if len(playcount) > 0 else []
        playcount = [i for i in playcount if int(season) == int(i[0]) and int(episode) == int(i[1])]
        overlay = 7 if len(playcount) > 0 else 6
        return str(overlay)
    except:
        return '6'


PLAYBACK_MARKED_PROPERTY = 'gratisred.playback_marked_watched'


def _flag_playback_marked():
    """Remember that watched state changed during this play so UI can refresh after stop."""
    try:
        control.window.setProperty(PLAYBACK_MARKED_PROPERTY, 'true')
    except Exception:
        pass


def _notify_marked(watched):
    try:
        message = 'Marked as watched.' if int(watched) == 7 else 'Marked as unwatched.'
        control.infoDialog(message, sound=True)
    except Exception:
        pass


def _finish_manual_mark(watched, media='tv'):
    """Toast + list refresh for Trakt / Simkl / Gratis Red / MDBList manual mark."""
    try:
        control.idle()
    except Exception:
        pass
    _arm_provider_list_sync_skip(media=media)
    _notify_marked(watched)
    try:
        control.refresh_list()
    except Exception:
        pass


def markMovieDuringPlayback(imdb, watched, tmdb=None):
    provider = _provider()
    try:
        if provider == 'trakt':
            if int(watched) == 7:
                trakt.markMovieAsWatched(imdb, tmdb=tmdb)
            else:
                trakt.markMovieAsNotWatched(imdb, tmdb=tmdb)
            trakt.cachesyncMovies()
            _arm_provider_list_sync_skip('trakt', 'movie')
            _flag_playback_marked()
            if trakt.getTraktAddonMovieInfo() == True:
                trakt.markMovieAsNotWatched(imdb, tmdb=tmdb)
        elif provider == 'simkl':
            if int(watched) == 7:
                simkl.markMovieAsWatched(imdb, tmdb=tmdb)
            else:
                simkl.markMovieAsNotWatched(imdb, tmdb=tmdb)
            if not simkl.apply_local_movie_watched(imdb, watched=int(watched) == 7):
                simkl.cachesyncMovies(timeout=0)
            _arm_provider_list_sync_skip('simkl', 'movie')
            _flag_playback_marked()
            if simkl.getSimklAddonMovieInfo() == True:
                simkl.markMovieAsNotWatched(imdb, tmdb=tmdb)
        elif provider == 'mdblist':
            if int(watched) == 7:
                mdblist.markMovieAsWatched(imdb, tmdb=tmdb)
            else:
                mdblist.markMovieAsNotWatched(imdb, tmdb=tmdb)
            mdblist.cachesyncMovies(timeout=0)
            _arm_provider_list_sync_skip('mdblist', 'movie')
            _flag_playback_marked()
            if mdblist.mdblist_official_status():
                mdblist.markMovieAsNotWatched(imdb, tmdb=tmdb)
    except:
        pass
    try:
        if int(watched) == 7:
            bookmarks.reset(1, 1, 'movie', imdb, '', '')
    except:
        pass


def markEpisodeDuringPlayback(imdb, tmdb, season, episode, watched, tvdb=None):
    provider = _provider()
    try:
        if provider == 'trakt':
            if int(watched) == 7:
                trakt.markEpisodeAsWatched(imdb, season, episode, tmdb=tmdb, tvdb=tvdb)
            else:
                trakt.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb, tvdb=tvdb)
            trakt.cachesyncTVShows()
            _arm_provider_list_sync_skip('trakt', 'tv')
            _flag_playback_marked()
            if trakt.getTraktAddonEpisodeInfo() == True:
                trakt.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb, tvdb=tvdb)
        elif provider == 'simkl':
            if int(watched) == 7:
                simkl.markEpisodeAsWatched(imdb, season, episode, tmdb=tmdb)
            else:
                simkl.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
            if not simkl.apply_local_episode_watched(tmdb, season, episode, watched=int(watched) == 7):
                simkl.cachesyncTVShows(timeout=0)
            _arm_provider_list_sync_skip('simkl', 'tv')
            _flag_playback_marked()
            if simkl.getSimklAddonEpisodeInfo() == True:
                simkl.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
        elif provider == 'mdblist':
            if int(watched) == 7:
                mdblist.markEpisodeAsWatched(imdb, season, episode, tmdb=tmdb)
            else:
                mdblist.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
            mdblist.cachesyncTVShows(timeout=0)
            _arm_provider_list_sync_skip('mdblist', 'tv')
            _flag_playback_marked()
            if mdblist.mdblist_official_status():
                mdblist.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
    except:
        pass
    try:
        if int(watched) == 7:
            bookmarks.reset(1, 1, 'episode', imdb, season, episode)
    except:
        pass


def movies(imdb, watched, tmdb=None):
    control.busy()
    provider = _provider()
    try:
        if provider == 'trakt':
            if int(watched) == 7:
                trakt.markMovieAsWatched(imdb, tmdb=tmdb)
            else:
                trakt.markMovieAsNotWatched(imdb, tmdb=tmdb)
            trakt.cachesyncMovies()
        elif provider == 'simkl':
            if int(watched) == 7:
                simkl.markMovieAsWatched(imdb, tmdb=tmdb)
            else:
                simkl.markMovieAsNotWatched(imdb, tmdb=tmdb)
            if not simkl.apply_local_movie_watched(imdb, watched=int(watched) == 7):
                simkl.cachesyncMovies(timeout=0)
        elif provider == 'mdblist':
            if int(watched) == 7:
                mdblist.markMovieAsWatched(imdb, tmdb=tmdb)
            else:
                mdblist.markMovieAsNotWatched(imdb, tmdb=tmdb)
            mdblist.cachesyncMovies(timeout=0)
        else:
            raise Exception()
    except:
        pass
    try:
        if int(watched) == 7:
            bookmarks.reset(1, 1, 'movie', imdb, '', '')
        else:
            bookmarks._delete_record('movie', imdb, '', '')
    except:
        pass
    _finish_manual_mark(watched, media='movie')


def episodes(imdb, tmdb, season, episode, watched):
    control.busy()
    provider = _provider()
    try:
        if provider == 'trakt':
            if int(watched) == 7:
                trakt.markEpisodeAsWatched(imdb, season, episode, tmdb=tmdb)
            else:
                trakt.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
            trakt.cachesyncTVShows()
        elif provider == 'simkl':
            if int(watched) == 7:
                simkl.markEpisodeAsWatched(imdb, season, episode, tmdb=tmdb)
            else:
                simkl.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
            if not simkl.apply_local_episode_watched(tmdb, season, episode, watched=int(watched) == 7):
                simkl.cachesyncTVShows(timeout=0)
        elif provider == 'mdblist':
            if int(watched) == 7:
                mdblist.markEpisodeAsWatched(imdb, season, episode, tmdb=tmdb)
            else:
                mdblist.markEpisodeAsNotWatched(imdb, season, episode, tmdb=tmdb)
            mdblist.cachesyncTVShows(timeout=0)
        else:
            raise Exception()
    except:
        pass
    try:
        if int(watched) == 7:
            bookmarks.reset(1, 1, 'episode', imdb, season, episode)
        else:
            bookmarks._delete_record('episode', imdb, season, episode)
    except:
        pass
    _finish_manual_mark(watched, media='tv')


def tvshows(tvshowtitle, imdb, tmdb, season, watched):
    control.busy()
    provider = _provider()
    try:
        if provider != 'local':
            raise Exception()
        from resources.lib.indexers import episodes
        name = control.addonInfo('name')
        dialog = control.progressDialogBG
        dialog.create(str(name), str(tvshowtitle))
        dialog.update(0, str(name), str(tvshowtitle))
        items = []
        if season:
            items = episodes.episodes().get(tvshowtitle, '0', imdb, tmdb, meta=None, season=season, idx=False)
            items = [i for i in items if int('%01d' % int(season)) == int('%01d' % int(i['season']))]
            items = [{'label': '%s S%02dE%02d' % (tvshowtitle, int(i['season']), int(i['episode'])), 'season': int('%01d' % int(i['season'])), 'episode': int('%01d' % int(i['episode'])), 'unaired': i['unaired']} for i in items]
            for i in range(len(items)):
                if control.monitor.abortRequested():
                    return sys.exit()
                dialog.update(int((100 / float(len(items))) * i), str(name), str(items[i]['label']))
                _season, _episode, unaired = items[i]['season'], items[i]['episode'], items[i]['unaired']
                if int(watched) == 7:
                    if not unaired == 'true':
                        bookmarks.reset(1, 1, 'episode', imdb, _season, _episode)
                else:
                    bookmarks._delete_record('episode', imdb, _season, _episode)
        else:
            seasons = episodes.seasons().get(tvshowtitle, '0', imdb, tmdb, meta=None, idx=False)
            seasons = [i['season'] for i in seasons]
            for s in seasons:
                items = episodes.episodes().get(tvshowtitle, '0', imdb, tmdb, meta=None, season=s, idx=False)
                items = [{'label': '%s S%02dE%02d' % (tvshowtitle, int(i['season']), int(i['episode'])), 'season': int('%01d' % int(i['season'])), 'episode': int('%01d' % int(i['episode'])), 'unaired': i['unaired']} for i in items]
                for i in range(len(items)):
                    if control.monitor.abortRequested():
                        return sys.exit()
                    dialog.update(int((100 / float(len(items))) * i), str(name), str(items[i]['label']))
                    _season, _episode, unaired = items[i]['season'], items[i]['episode'], items[i]['unaired']
                    if int(watched) == 7:
                        if not unaired == 'true':
                            bookmarks.reset(1, 1, 'episode', imdb, _season, _episode)
                    else:
                        bookmarks._delete_record('episode', imdb, _season, _episode)
        try:
            dialog.close()
        except:
            pass
    except:
        try:
            dialog.close()
        except:
            pass
    try:
        if provider == 'trakt':
            if season:
                if int(watched) == 7:
                    trakt.markSeasonAsWatched(imdb, season, tmdb=tmdb)
                else:
                    trakt.markSeasonAsNotWatched(imdb, season, tmdb=tmdb)
            else:
                if int(watched) == 7:
                    trakt.markTVShowAsWatched(imdb, tmdb=tmdb)
                else:
                    trakt.markTVShowAsNotWatched(imdb, tmdb=tmdb)
            trakt.cachesyncTVShows()
        elif provider == 'simkl':
            local_ok = True
            if season:
                from resources.lib.indexers import episodes
                items = episodes.episodes().get(tvshowtitle, '0', imdb, tmdb, meta=None, season=season, idx=False)
                items = [(int(i['season']), int(i['episode'])) for i in items]
                items = [i[1] for i in items if int('%01d' % int(season)) == int('%01d' % i[0])]
                for i in items:
                    if int(watched) == 7:
                        simkl.markEpisodeAsWatched(imdb, season, i, tmdb=tmdb)
                    else:
                        simkl.markEpisodeAsNotWatched(imdb, season, i, tmdb=tmdb)
                    if not simkl.apply_local_episode_watched(tmdb, season, i, watched=int(watched) == 7):
                        local_ok = False
            else:
                if int(watched) == 7:
                    if not simkl.markTVShowAsWatched(imdb, tmdb=tmdb):
                        try:
                            control.idle()
                        except Exception:
                            pass
                        control.infoDialog('Error', sound=True)
                        return
                else:
                    simkl.markTVShowAsNotWatched(imdb, tmdb=tmdb)
                local_ok = False
            if not local_ok:
                simkl.cachesyncTVShows(timeout=0)
        elif provider == 'mdblist':
            if season:
                from resources.lib.indexers import episodes
                items = episodes.episodes().get(tvshowtitle, '0', imdb, tmdb, meta=None, season=season, idx=False)
                items = [(int(i['season']), int(i['episode'])) for i in items]
                items = [i[1] for i in items if int('%01d' % int(season)) == int('%01d' % i[0])]
                for i in items:
                    if int(watched) == 7:
                        mdblist.markEpisodeAsWatched(imdb, season, i, tmdb=tmdb)
                    else:
                        mdblist.markEpisodeAsNotWatched(imdb, season, i, tmdb=tmdb)
            else:
                if int(watched) == 7:
                    if not mdblist.markTVShowAsWatched(imdb, tmdb=tmdb):
                        try:
                            control.idle()
                        except Exception:
                            pass
                        control.infoDialog('Error', sound=True)
                        return
                else:
                    mdblist.markTVShowAsNotWatched(imdb, tmdb=tmdb)
            mdblist.cachesyncTVShows(timeout=0)
    except:
        pass
    _finish_manual_mark(watched, media='tv')
