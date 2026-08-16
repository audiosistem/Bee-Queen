# ported from Starfleet's torrent_sources.py for gearsscrapers
"""
	gearsscrapers Project
"""

import re
import xbmc
from gearsscrapers.modules import client
from gearsscrapers.modules import source_utils

# KONTRAST — small curated x265 release group (movies + full TV season
# packs, no per-episode releases). Its own HTML search page AND its RSS
# feed's `?search=` query param are both behind a genuine Cloudflare JS
# challenge (confirmed live), but the bare unfiltered feed itself is NOT
# protected and hands back a rolling ~30-item window of fully-resolved
# items -- title, category, infoHash, and a ready-to-use magnet URI, no
# per-item detail fetch or bencode parsing needed. Since server-side
# filtering is blocked, this fetches the whole feed once and matches
# locally -- low hit rate per search (only catches whatever KONTRAST has
# released in roughly the last ~12 days), but zero extra cost when it hits.

_RE_KONTRAST_ITEM = re.compile(
	r'<item><title>\[[^\]]*\]\s*([^<(]+?)(?:\s*\([^)]*\))?</title>'
	r'<category>([^<]+)</category>.*?'
	r'<torrent:infoHash>([a-fA-F0-9]{40})</torrent:infoHash>'
	r'<torrent:magnetURI><!\[CDATA\[(magnet:[^\]]+)\]\]></torrent:magnetURI>',
	re.IGNORECASE)


class source:
	priority = 5
	pack_capable = True
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.base_link = "https://kontrast.top"
		self.feed_link = '/feed/rss'
		self.min_seeders = 0

	def _get_feed_items(self):
		html = client.request(self.base_link + self.feed_link, timeout=8)
		if not html: return []
		return _RE_KONTRAST_ITEM.findall(html)

	def sources(self, data, hostDict):
		xbmc.log('[SF-DIAG] KONTRAST.sources() called', xbmc.LOGINFO)
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			if 'tvshowtitle' in data:
				title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('$', 's')
				episode_title = data['title']
				hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode']))
				want_media = 'tv'
			else:
				title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				episode_title = None
				hdlr = data['year']
				want_media = 'movie'
			aliases = data['aliases']
			year = data['year']
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
			items = self._get_feed_items()
			xbmc.log('[SF-DIAG] KONTRAST fetched %d feed items, title=%r want_media=%s' % (len(items), title, want_media), xbmc.LOGINFO)
		except Exception as e:
			xbmc.log('[SF-DIAG] KONTRAST.sources() exception before loop: %s' % e, xbmc.LOGINFO)
			source_utils.scraper_error('KONTRAST')
			return self.sources

		for raw_name, category, info_hash, magnet in items:
			try:
				cat_media = 'tv' if category.strip().lower() == 'tv' else 'movie'
				if cat_media != want_media: continue
				name = source_utils.clean_name(raw_name.strip())
				if not source_utils.check_title(title, aliases, name, hdlr, year): continue
				name_info = source_utils.info_from_name(name, title, year, hdlr, episode_title)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				hash = info_hash.lower()
				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				quality, info = source_utils.get_release_quality(name_info, url)
				info = ' | '.join(info)
				self.sources_append({'provider': 'kontrast', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name,
					'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url, 'info': info,
					'direct': False, 'debridonly': True, 'size': 0})
			except:
				source_utils.scraper_error('KONTRAST')
		xbmc.log('[SF-DIAG] KONTRAST.sources() returning %d results' % len(self.sources), xbmc.LOGINFO)
		return self.sources

	def sources_packs(self, data, hostDict, search_series=False, total_seasons=None, bypass_filter=False):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			title = data['tvshowtitle'].replace('&', 'and').replace('Special Victims Unit', 'SVU').replace('/', ' ').replace('$', 's')
			aliases = data['aliases']
			imdb = data['imdb']
			year = data['year']
			season = data['season']
			undesirables = source_utils.get_undesirables()
			check_foreign_audio = source_utils.check_foreign_audio()
			items = self._get_feed_items()
		except:
			source_utils.scraper_error('KONTRAST')
			return self.sources

		for raw_name, category, info_hash, magnet in items:
			try:
				if category.strip().lower() != 'tv': continue
				name = source_utils.clean_name(raw_name.strip())

				episode_start, episode_end = 0, 0
				if not search_series:
					if not bypass_filter:
						valid, episode_start, episode_end = source_utils.filter_season_pack(title, aliases, year, season, name)
						if not valid: continue
					package = 'season'
				else:
					if not bypass_filter:
						valid, last_season = source_utils.filter_show_pack(title, aliases, imdb, year, season, name, total_seasons)
						if not valid: continue
					else: last_season = total_seasons
					package = 'show'

				name_info = source_utils.info_from_name(name, title, year, season=season, pack=package)
				if source_utils.remove_lang(name_info, check_foreign_audio): continue
				if undesirables and source_utils.remove_undesirables(name_info, undesirables): continue

				hash = info_hash.lower()
				url = 'magnet:?xt=urn:btih:%s&dn=%s' % (hash, name)
				quality, info = source_utils.get_release_quality(name_info, url)
				info = ' | '.join(info)

				item = {'provider': 'kontrast', 'source': 'torrent', 'seeders': 0, 'hash': hash, 'name': name, 'name_info': name_info,
					'quality': quality, 'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True,
					'size': 0, 'package': package}
				if search_series: item.update({'last_season': last_season})
				elif episode_start: item.update({'episode_start': episode_start, 'episode_end': episode_end})
				self.sources_append(item)
			except:
				source_utils.scraper_error('KONTRAST')
		return self.sources
