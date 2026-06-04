# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	Context menu for the Bingie UI windows.

	The default skin attaches a context menu to each directory ListItem via
	item.addContextMenuItems(cm), and Kodi raises the skin's NATIVE context
	dialog (DialogContextMenu.xml) on long-press / the remote context key.

	The Bingie windows build real ListItems too, so we attach the SAME cm to
	each card here. That makes Bingie's context menu look and behave exactly
	like the default skin's (same orange/native dialog, same options), instead
	of the plain blue select dialog.

	build_*_cm() return the (label, builtin) list to attach with
	li.addContextMenuItems(cm). show_*() are kept as a fallback that presents
	the same list via a select dialog if a window ever needs it.

	The builtin commands are kept identical to movies.py / tvshows.py /
	episodes.py so the Bingie menu stays in sync with the default skin.
"""

from urllib.parse import quote_plus
from json import dumps as jsdumps
from resources.lib.modules import control

getLS = control.lang
getSetting = control.setting


def _sysaddon():
	return 'plugin://%s/' % control.addonId()


def _rescrape_extra():
	"""Return the rescrape builtin suffix per the user's default rescrape mode."""
	rescrape_method = getSetting('rescrape.default2')
	sel_map = {'0': 'rescrape=true&select=1', '1': 'rescrape=true&select=0',
			   '2': 'rescrape=true&all_providers=true&select=1',
			   '3': 'rescrape=true&all_providers=true&select=0'}
	return sel_map.get(rescrape_method, 'rescrape=true&select=1')


# ──────────────────────── builders ────────────────────────
def build_movie_cm(i):
	"""(label, builtin) list for a movie dict — mirrors movies.py cm."""
	try:
		sysaddon = _sysaddon()
		imdb = i.get('imdb', '') or ''
		tmdb = i.get('tmdb', '') or ''
		title = i.get('title', '') or ''
		year = i.get('year', '') or ''
		systitle = quote_plus(title)
		sysname = quote_plus('%s (%s)' % (title, year)) if year else quote_plus(title)
		sysmeta = quote_plus(jsdumps(i))
		url = '%s?action=play_Item&title=%s&year=%s&imdb=%s&tmdb=%s&meta=%s' % (sysaddon, systitle, year, imdb, tmdb, sysmeta)
		sysurl = quote_plus(url)
		art = i.get('art') if isinstance(i.get('art'), dict) else {}
		sysart = quote_plus(jsdumps(art))

		play_mode = getSetting('play.mode')
		playbackMenu = getLS(32063) if play_mode == '1' else getLS(32064)
		playlistManagerMenu, queueMenu = getLS(35522), getLS(32065)
		addToLibrary = getLS(32551)
		clearSourcesMenu = getLS(32611)
		rescrapeMenu, findSimilarMenu = getLS(32185), getLS(32184)
		watchedMenu = getLS(32066)
		rescrape_useDefault = getSetting('rescrape.default') == 'true'

		cm = []
		cm.append(('Play Trailer', 'RunPlugin(%s?action=play_Trailer&type=movie&name=%s&year=%s&imdb=%s)' % (sysaddon, sysname, year, imdb)))
		cm.append((watchedMenu, 'RunPlugin(%s?action=playcount_Movie&name=%s&imdb=%s&query=5)' % (sysaddon, sysname, imdb)))
		cm.append((playlistManagerMenu, 'RunPlugin(%s?action=playlist_Manager&name=%s&url=%s&meta=%s&art=%s)' % (sysaddon, sysname, sysurl, sysmeta, sysart)))
		cm.append((queueMenu, 'RunPlugin(%s?action=playlist_QueueItem&name=%s)' % (sysaddon, sysname)))
		cm.append((addToLibrary, 'RunPlugin(%s?action=library_movieToLibrary&name=%s&title=%s&year=%s&imdb=%s&tmdb=%s)' % (sysaddon, sysname, systitle, year, imdb, tmdb)))
		if imdb:
			cm.append((findSimilarMenu, 'Container.Update(%s?action=movies&url=%s)' % (sysaddon, quote_plus('https://api.trakt.tv/movies/%s/related?limit=20&page=1,return' % imdb))))
		cm.append((playbackMenu, 'RunPlugin(%s?action=alterSources&url=%s&meta=%s)' % (sysaddon, sysurl, sysmeta)))
		if not rescrape_useDefault:
			cm.append(('Rescrape Options...', 'PlayMedia(%s?action=rescrapeMenu&title=%s&year=%s&imdb=%s&tmdb=%s&meta=%s)' % (sysaddon, systitle, year, imdb, tmdb, sysmeta)))
		else:
			cm.append((rescrapeMenu, 'PlayMedia(%s?action=play_Item&title=%s&year=%s&imdb=%s&tmdb=%s&meta=%s&%s)' % (sysaddon, systitle, year, imdb, tmdb, sysmeta, _rescrape_extra())))
		cm.append((clearSourcesMenu, 'RunPlugin(%s?action=cache_clearSources)' % sysaddon))
		cm.append(('[COLOR red]luc_kodi Settings[/COLOR]', 'RunPlugin(%s?action=tools_openSettings)' % sysaddon))

		fb_tmdb = i.get('_fb_tmdb', '')
		if fb_tmdb:
			fb_mt = quote_plus(i.get('_fb_media_type', 'movie'))
			fb_genres = quote_plus(i.get('_fb_genres', ''))
			fb_title = quote_plus(title)
			cm.insert(0, ('[COLOR limegreen][B]More like this[/B][/COLOR]', 'RunPlugin(%s?action=reco_feedback&signal=1&tmdb=%s&title=%s&media_type=%s&genres=%s)' % (sysaddon, fb_tmdb, fb_title, fb_mt, fb_genres)))
			cm.insert(1, ('[COLOR red][B]Not interested[/B][/COLOR]', 'RunPlugin(%s?action=reco_feedback&signal=-1&tmdb=%s&title=%s&media_type=%s&genres=%s)' % (sysaddon, fb_tmdb, fb_title, fb_mt, fb_genres)))
		return cm
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return []


def build_tvshow_cm(i):
	"""(label, builtin) list for a tv show dict — mirrors tvshows.py cm."""
	try:
		sysaddon = _sysaddon()
		imdb = i.get('imdb', '') or ''
		tmdb = i.get('tmdb', '') or ''
		tvdb = i.get('tvdb', '') or ''
		title = i.get('tvshowtitle') or i.get('title', '') or ''
		year = i.get('year', '') or ''
		systitle = quote_plus(title)
		art = i.get('art') if isinstance(i.get('art'), dict) else {}
		sysart = quote_plus(jsdumps(art))

		findSimilarMenu = getLS(32184)
		addToLibrary = getLS(32551)
		playRandom = getLS(32535)
		watchedMenu = getLS(32066)

		cm = []
		cm.append((watchedMenu, 'RunPlugin(%s?action=playcount_TVShow&name=%s&imdb=%s&tvdb=%s&query=5)' % (sysaddon, systitle, imdb, tvdb)))
		if imdb:
			cm.append((findSimilarMenu, 'Container.Update(%s?action=tvshows&url=%s)' % (sysaddon, quote_plus('https://api.trakt.tv/shows/%s/related?limit=20&page=1,return' % imdb))))
		cm.append((playRandom, 'RunPlugin(%s?action=play_Random&rtype=season&tvshowtitle=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s&art=%s)' % (sysaddon, systitle, year, imdb, tmdb, tvdb, sysart)))
		cm.append((addToLibrary, 'RunPlugin(%s?action=library_tvshowToLibrary&tvshowtitle=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s)' % (sysaddon, systitle, year, imdb, tmdb, tvdb)))
		cm.append(('[COLOR red]luc_kodi Settings[/COLOR]', 'RunPlugin(%s?action=tools_openSettings)' % sysaddon))
		return cm
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return []


def build_episode_cm(e, tvshowtitle=None, imdb=None, tmdb=None, tvdb=None, year=None):
	"""(label, builtin) list for an episode dict — mirrors episodes.py cm."""
	try:
		sysaddon = _sysaddon()
		imdb = (e.get('imdb', '') or imdb or '')
		tmdb = (e.get('tmdb', '') or tmdb or '')
		tvdb = (e.get('tvdb', '') or tvdb or '')
		tvshowtitle = (e.get('tvshowtitle') or tvshowtitle or '')
		year = (e.get('year', '') or year or '')
		season = e.get('season')
		episode = e.get('episode')
		premiered = quote_plus(str(e.get('premiered', '') or ''))
		title = e.get('title', '') or ''
		systitle = quote_plus(title)
		systvshowtitle = quote_plus(tvshowtitle)
		try: label = '%s S%02dE%02d' % (tvshowtitle, int(season), int(episode))
		except Exception: label = tvshowtitle
		syslabel = quote_plus(label)
		sysmeta = quote_plus(jsdumps(e))
		art = e.get('art') if isinstance(e.get('art'), dict) else {}
		sysart = quote_plus(jsdumps(art))
		url = '%s?action=play_Item&title=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s&season=%s&episode=%s&tvshowtitle=%s&premiered=%s&meta=%s' % (
				sysaddon, systitle, year, imdb, tmdb, tvdb, season, episode, systvshowtitle, premiered, sysmeta)
		sysurl = quote_plus(url)

		enable_playnext = getSetting('enable.playnext') == 'true'
		play_mode = getSetting('play.mode')
		playbackMenu = getLS(32063) if (play_mode == '1' or enable_playnext) else getLS(32064)
		playlistManagerMenu, queueMenu = getLS(35522), getLS(32065)
		addToLibrary = getLS(32551)
		tvshowBrowserMenu = getLS(32071)
		clearSourcesMenu, rescrapeMenu = getLS(32611), getLS(32185)
		watchedMenu = getLS(32066)
		rescrape_useDefault = getSetting('rescrape.default') == 'true'

		cm = []
		cm.append((watchedMenu, 'RunPlugin(%s?action=playcount_Episode&name=%s&imdb=%s&tvdb=%s&season=%s&episode=%s&query=5)' % (sysaddon, systvshowtitle, imdb, tvdb, season, episode)))
		cm.append((playlistManagerMenu, 'RunPlugin(%s?action=playlist_Manager&name=%s&url=%s&meta=%s&art=%s)' % (sysaddon, syslabel, sysurl, sysmeta, sysart)))
		cm.append((queueMenu, 'RunPlugin(%s?action=playlist_QueueItem&name=%s)' % (sysaddon, syslabel)))
		cm.append((addToLibrary, 'RunPlugin(%s?action=library_tvshowToLibrary&tvshowtitle=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s)' % (sysaddon, systvshowtitle, year, imdb, tmdb, tvdb)))
		cm.append((tvshowBrowserMenu, 'Container.Update(%s?action=seasons&tvshowtitle=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s&art=%s,return)' % (sysaddon, systvshowtitle, year, imdb, tmdb, tvdb, sysart)))
		cm.append((playbackMenu, 'RunPlugin(%s?action=alterSources&url=%s&meta=%s)' % (sysaddon, sysurl, sysmeta)))
		if not rescrape_useDefault:
			cm.append(('Rescrape Options...', 'PlayMedia(%s?action=rescrapeMenu&title=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s&season=%s&episode=%s&tvshowtitle=%s&premiered=%s&meta=%s)' % (
					sysaddon, systitle, year, imdb, tmdb, tvdb, season, episode, systvshowtitle, premiered, sysmeta)))
		else:
			cm.append((rescrapeMenu, 'PlayMedia(%s?action=play_Item&title=%s&year=%s&imdb=%s&tmdb=%s&tvdb=%s&season=%s&episode=%s&tvshowtitle=%s&premiered=%s&meta=%s&%s)' % (
					sysaddon, systitle, year, imdb, tmdb, tvdb, season, episode, systvshowtitle, premiered, sysmeta, _rescrape_extra())))
		cm.append((clearSourcesMenu, 'RunPlugin(%s?action=cache_clearSources)' % sysaddon))
		cm.append(('[COLOR red]luc_kodi Settings[/COLOR]', 'RunPlugin(%s?action=tools_openSettings)' % sysaddon))
		return cm
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()
		return []


# ──────────────────────── native context-menu presentation ────────────────────────
def _present(cm):
	"""Present cm via Kodi's NATIVE context menu (DialogContextMenu.xml — the
	skin-themed dialog, same look as the default mode), not the plain blue
	select dialog. dialog.contextmenu() returns the chosen index or -1."""
	if not cm:
		return
	try:
		sel = control.dialog.contextmenu([c[0] for c in cm])
	except Exception:
		try: sel = control.selectDialog([c[0] for c in cm], control.addonName())
		except Exception: return
	if sel is None or sel < 0:
		return
	try:
		control.execute(cm[sel][1])
	except Exception:
		from resources.lib.modules import log_utils
		log_utils.error()


def show_for_movie(i):
	_present(build_movie_cm(i))


def show_for_tvshow(i):
	_present(build_tvshow_cm(i))


def show_for_episode(e, tvshowtitle=None, imdb=None, tmdb=None, tvdb=None, year=None):
	_present(build_episode_cm(e, tvshowtitle, imdb, tmdb, tvdb, year))
