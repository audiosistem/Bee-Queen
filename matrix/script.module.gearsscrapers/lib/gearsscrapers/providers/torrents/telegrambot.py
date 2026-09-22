
"""
	gearsscrapers Project
"""

import re, queue
from gearsscrapers.modules import source_utils
from gearsscrapers.modules import telegram_auth as _tg_auth

# @TorrentSearchRoBot via each installer's own linked Telegram account --
# ported from Starfleet's torrent_sources.py::search_telegram_bot(). This
# bot only works via Telegram's own inline-query mechanism, which needs a
# real logged-in user account (MTProto, via the vendored telethon/ at this
# addon's lib/ root), not a bot token -- see modules/telegram_auth.py for
# the per-user QR-link flow. Returns nothing (not an error) if nobody has
# linked an account yet in Settings > "Link Telegram Account".
#
# Confirmed live 2026-09-12 (in Starfleet, same bot/mechanism): the bot's
# inline results for a bare query are a decoy site-selector menu whose own
# description text says "Type |N| <query> (do not click here)" -- the real
# syntax is prefixing the query itself with |site_id|, not clicking
# anything. Also confirmed: the result `id` field IS the torrent's real
# BitTorrent info hash, not a per-site row id -- the exact same 40-hex id
# showed up for the exact same real release across two different backend
# sites (RarBG and LimeTorrents), which only happens for a content hash.
# That means a working magnet can be built directly from one inline
# query, no second hop through the bot's own deep-link/private-chat flow.
#
# Only queries a couple of backend site ids by default (not all the bot
# offers) to bound how many Telegram API calls one search makes.
_TG_SITE_IDS = [('4', 'RarBG'), ('8', 'TorrentsCSV')]
_RE_TG_HASH = re.compile(r'^[a-f0-9]{40}$', re.IGNORECASE)
_RE_TG_SIZE = re.compile(r'([\d,.]+\s*(?:GB|MB|KB))', re.IGNORECASE)
_RE_TG_SEEDS = re.compile(r'\|\s*([\d,]+)\s*\|')


def _telegram_client():
	try:
		if not _tg_auth.is_paired():
			return None
		_tg_auth.ensure_selector_event_loop()
		from telethon.sync import TelegramClient
		return TelegramClient(_tg_auth._session_path(), _tg_auth.API_ID, _tg_auth.API_HASH)
	except Exception:
		from gearsscrapers.modules import log_utils
		log_utils.error()
		return None


class source:
	priority = 3
	pack_capable = False
	hasMovies = True
	hasEpisodes = True
	def __init__(self):
		self.language = ['en']
		self.min_seeders = 0

	def sources(self, data, hostDict):
		self.sources = []
		if not data: return self.sources
		self.sources_append = self.sources.append
		try:
			self.aliases = data['aliases']
			self.year = data['year']
			if 'tvshowtitle' in data:
				self.title = data['tvshowtitle'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = data['title']
				self.hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode']))
			else:
				self.title = data['title'].replace('&', 'and').replace('/', ' ').replace('$', 's')
				self.episode_title = None
				self.hdlr = self.year
			self.undesirables = source_utils.get_undesirables()
			self.check_foreign_audio = source_utils.check_foreign_audio()

			client = _telegram_client()
			if not client: return self.sources

			query = '%s %s' % (self.title, self.hdlr)
			seen_hashes = set()
			with client:
				for site_id, site_name in _TG_SITE_IDS:
					if len(self.sources) >= 30: break
					try:
						hits = client.inline_query('TorrentSearchRoBot', '|%s| %s' % (site_id, query))
					except Exception:
						from gearsscrapers.modules import log_utils
						log_utils.error()
						continue
					for r in hits:
						ih = (getattr(r.result, 'id', '') or '').lower()
						if not _RE_TG_HASH.match(ih) or ih in seen_hashes:
							continue
						name = source_utils.clean_name((r.title or '').strip())
						if not name: continue
						if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year): continue

						name_info = source_utils.info_from_name(name, self.title, self.year, self.hdlr, self.episode_title)
						if source_utils.remove_lang(name_info, self.check_foreign_audio): continue
						if self.undesirables and source_utils.remove_undesirables(name_info, self.undesirables): continue

						desc = r.description or ''
						seeds_m = _RE_TG_SEEDS.search(desc)
						seeders = int((seeds_m.group(1) if seeds_m else '0').replace(',', ''))
						if self.min_seeders > seeders: continue

						url = 'magnet:?xt=urn:btih:%s&dn=%s' % (ih, name)
						quality, info = source_utils.get_release_quality(name_info, url)
						size_m = _RE_TG_SIZE.search(desc)
						dsize = 0
						if size_m:
							try:
								dsize, isize = source_utils._size(size_m.group(1))
								info.insert(0, isize)
							except Exception:
								pass
						info = ' | '.join(info)

						seen_hashes.add(ih)
						self.sources_append({'provider': 'telegrambot', 'source': 'torrent', 'seeders': seeders, 'hash': ih, 'name': name,
							'name_info': name_info, 'quality': quality, 'language': 'en', 'url': url, 'info': info,
							'direct': False, 'debridonly': True, 'size': dsize})
			return self.sources
		except:
			source_utils.scraper_error('TELEGRAMBOT')
			return self.sources
