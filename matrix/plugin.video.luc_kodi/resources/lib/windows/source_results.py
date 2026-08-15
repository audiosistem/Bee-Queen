"""
	luc_kodi Add-on
"""

from json import dumps as jsdumps
from urllib.parse import quote_plus
from resources.lib.modules.control import joinPath, transPath, dialog, getSourceHighlightColor, getDebridHighlightColor, notification, setting as getSetting, cancelPlayback
from resources.lib.modules.source_utils import getFileType
from resources.lib.modules import tools
from resources.lib.windows.base import BaseDialog


LIST_ID, WIDE_LIST_ID = 2000, 2001


class SourceResultsXML(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, args)
		self.window_id = {
			'List': LIST_ID,
			'Wide List': WIDE_LIST_ID
		}.get(getSetting('sources.select.wide_list')) or LIST_ID
		self.results = kwargs.get('results')
		self.uncached = kwargs.get('uncached')
		self.total_results = str(len(self.results))
		self.meta = kwargs.get('meta')
		self.make_items()
		self.set_properties()
		self.dnlds_enabled = True if getSetting('downloads') == 'true' and (getSetting('movie.download.path') != '' or getSetting('tv.download.path') != '') else False

	def onInit(self):
		win = self.getControl(self.window_id)
		win.addItems(self.item_list)
		self.setFocusId(self.window_id)

	def run(self):
		self.doModal()
		self.clearProperties()
		return self.selected

	def onAction(self, action):
		try:
			action_id = action.getId() # change to just "action" as the ID is already returned in that.
			of_action_id = action_id
			if action_id in self.closing_actions:
				self.selected = (None, '')
				try: cancelPlayback()
				except: pass
				return self.close()
			if action_id in self.info_actions:
				chosen_source = self.item_list[self.get_position(self.window_id)]
				chosen_source = chosen_source.getProperty('luc_kodi.source_dict')
				syssource = quote_plus(chosen_source)
				self.execute_code('RunPlugin(plugin://plugin.video.luc_kodi/?action=sourceInfo&source=%s)' % syssource)
			if action_id in self.selection_actions:
				chosen_source = self.item_list[self.get_position(self.window_id)]
				source = chosen_source.getProperty('luc_kodi.source')
				if 'load' in source:
					position = self.get_position(self.window_id)
					self.load_uncachedTorrents()
					self.setFocusId(self.window_id)
					self.getControl(self.window_id).selectItem(position)
					self.selected = (None, '')
					return
				elif 'UNCACHED' in source:
					debrid = chosen_source.getProperty('luc_kodi.debrid')
					source_dict = chosen_source.getProperty('luc_kodi.source_dict')
					link_type = 'pack' if 'package' in source_dict else 'single'
					sysname = quote_plus(self.meta.get('title'))
					if 'tvshowtitle' in self.meta and 'season' in self.meta and 'episode' in self.meta:
						poster = self.meta.get('season_poster') or self.meta.get('poster')
						sysname += quote_plus(' S%02dE%02d' % (int(self.meta['season']), int(self.meta['episode'])))
					elif 'year' in self.meta: sysname += quote_plus(' (%s)' % self.meta['year'])
					try: new_sysname = quote_plus(chosen_source.getProperty('luc_kodi.name'))
					except: new_sysname = sysname
					self.execute_code('RunPlugin(plugin://plugin.video.luc_kodi/?action=cacheTorrent&caller=%s&type=%s&title=%s&items=%s&url=%s&source=%s&meta=%s)' %
											(debrid, link_type, sysname, quote_plus(jsdumps(self.results)), quote_plus(chosen_source.getProperty('luc_kodi.url')), quote_plus(source_dict), quote_plus(jsdumps(self.meta))))
					self.selected = (None, '')
				else:
					self.selected = ('play_Item', chosen_source)
					# ── Personal ranker: registrar elección manual ─────
					# self.results es la lista de dicts; posición del elegido
					# da la slice de fuentes mostradas pero no escogidas (las
					# de arriba — las que el usuario explícitamente saltó).
					try:
						position = self.get_position(self.window_id)
						if 0 <= position < len(self.results):
							from resources.lib.database import source_ranker
							chosen_dict = self.results[position]
							skipped_above = self.results[:position]
							source_ranker.record_choice(
								chosen_dict,
								all_items=skipped_above + [chosen_dict]
							)
					except Exception:
						pass
				return self.close()
			elif action_id in self.context_actions:
				from re import match as re_match
				chosen_source = self.item_list[self.get_position(self.window_id)]
				source_dict = chosen_source.getProperty('luc_kodi.source_dict')
				cm_list = [('[B]Additional Link Info[/B]', 'sourceInfo')]
				if 'cached (pack)' in source_dict or 'unchecked (pack)' in source_dict:
					cm_list += [('[B]Browse Debrid Pack[/B]', 'showDebridPack')]
				source = chosen_source.getProperty('luc_kodi.source')
				if not 'UNCACHED' in source and self.dnlds_enabled:
					cm_list += [('[B]Download[/B]', 'download')]
				if re_match(r'^CACHED.*TORRENT', source):
					debrid = chosen_source.getProperty('luc_kodi.debrid')
					cm_list += [('[B]Save to %s Cloud[/B]' % debrid, 'saveToCloud')]
				chosen_cm_item = dialog.contextmenu([i[0] for i in cm_list])
				if chosen_cm_item == -1: return
				cm_action = cm_list[chosen_cm_item][1]
				if cm_action == 'sourceInfo':
					self.execute_code('RunPlugin(plugin://plugin.video.luc_kodi/?action=sourceInfo&source=%s)' % quote_plus(source_dict))
				elif cm_action == 'showDebridPack':
					debrid = chosen_source.getProperty('luc_kodi.debrid')
					name = chosen_source.getProperty('luc_kodi.name')
					hash = chosen_source.getProperty('luc_kodi.hash')
					self.execute_code('RunPlugin(plugin://plugin.video.luc_kodi/?action=showDebridPack&caller=%s&name=%s&url=%s&source=%s)' %
									(quote_plus(debrid), quote_plus(name), quote_plus(chosen_source.getProperty('luc_kodi.url')), quote_plus(hash)))
					self.selected = (None, '')
				elif cm_action == 'download':
					sysname = quote_plus(self.meta.get('title'))
					poster = self.meta.get('poster', '')
					if 'tvshowtitle' in self.meta and 'season' in self.meta and 'episode' in self.meta:
						sysname = quote_plus(self.meta.get('tvshowtitle'))
						poster = self.meta.get('season_poster') or self.meta.get('poster')
						sysname += quote_plus(' S%02dE%02d' % (int(self.meta['season']), int(self.meta['episode'])))
					elif 'year' in self.meta: sysname += quote_plus(' (%s)' % self.meta['year'])
					try: new_sysname = quote_plus(chosen_source.getProperty('luc_kodi.name'))
					except: new_sysname = sysname
					self.execute_code('RunPlugin(plugin://plugin.video.luc_kodi/?action=download&name=%s&image=%s&source=%s&caller=sources&title=%s)' %
										(new_sysname, quote_plus(poster), quote_plus(source_dict), sysname))
					self.selected = (None, '')
				elif cm_action == 'saveToCloud':
					magnet = chosen_source.getProperty('luc_kodi.url')
					if debrid == 'AD':
						from resources.lib.debrid import alldebrid
						transfer_function = alldebrid.AllDebrid
						debrid_icon = alldebrid.ad_icon
					elif debrid == 'PM':
						from resources.lib.debrid import premiumize
						transfer_function = premiumize.Premiumize
						debrid_icon = premiumize.pm_icon
					elif debrid == 'RD':
						from resources.lib.debrid import realdebrid
						transfer_function = realdebrid.RealDebrid
						debrid_icon = realdebrid.rd_icon
					elif debrid == 'OC':
						from resources.lib.debrid import offcloud
						transfer_function = offcloud.Offcloud
						debrid_icon = offcloud.oc_icon
					elif debrid == 'ED':
						from resources.lib.debrid import easydebrid
						transfer_function = easydebrid.EasyDebrid
						debrid_icon = easydebrid.ed_icon
					elif debrid == 'TB':
						from resources.lib.debrid import torbox
						transfer_function = torbox.TorBox
						debrid_icon = torbox.tb_icon
					result = transfer_function().create_transfer(magnet)
					if result: notification(message='Sending MAGNET to the %s cloud' % debrid, icon=debrid_icon)
			elif action in self.closing_actions:
				self.selected = (None, '')
				self.close()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def get_quality_iconPath(self, quality):
		try:
			return joinPath(transPath('special://home/addons/plugin.video.luc_kodi/resources/skins/Default/media/resolution'), '%s.png' % quality)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def debrid_abv(self, debrid):
		try:
			d_dict = {'AllDebrid': 'AD', 'EasyDebrid': 'ED', 'Offcloud': 'OC', 'Premiumize.me': 'PM', 'Real-Debrid': 'RD', 'TorBox': 'TB'}
			d = d_dict[debrid]
		except:
			d = ''
		return d

	def debrid_name(self, debrid):
		"""Return a user-facing debrid service name (safe fallback)."""
		try:
			d_dict = {
				'AllDebrid': 'AllDebrid',
				'EasyDebrid': 'EasyDebrid',
				'Offcloud': 'Offcloud',
				'Premiumize.me': 'Premiumize',
				'Real-Debrid': 'Real-Debrid',
				'TorBox': 'TorBox'
			}
			# If we don't recognize it, show whatever provider gave us.
			d = d_dict.get(debrid) or (debrid or '')
		except:
			d = ''
		return d

	def _compute_quality_breakdown(self):
		"""Build a colored, single-line summary of result counts per quality bucket.

		Mirrors the per-item quality colors used in make_items() so the header
		visually matches the list rows.

		Buckets are split into two tiers:
		  * Main tier: 4K, 1080P, 720P, SD — always considered.
		  * Low tier:  SCR, CAM — only displayed when the title has NO
		    main-tier results at all (i.e. a cinema-only release like a
		    fresh CAM/TS rip). When at least one main-tier bucket has
		    results, SCR/CAM are hidden because they're almost always
		    misclassified noise once a real release is out.

		Empty buckets within the displayed tier are also omitted so the
		header stays uncluttered.

		Returns a Kodi-BBCode string suitable for a <label>, e.g.:
			[COLOR FF00BCD4][B]4K:13[/B][/COLOR] | [COLOR FF4CAF50][B]1080p:29[/B][/COLOR] | ...
		"""
		try:
			if not self.results:
				return ''
			# Same colors used for the per-item quality_color in make_items()
			# (label, hex, display_name)
			main_qualities = (
				('4K',    'FF00BCD4', '4K'),
				('1080P', 'FF4CAF50', '1080p'),
				('720P',  'FFFFA726', '720p'),
				('SD',    'FF607D8B', 'SD'),
			)
			low_qualities = (
				('SCR',   'FFB71C1C', 'SCR'),
				('CAM',   'FFB0C4DE', 'CAM'),
			)
			counts = {q[0]: 0 for q in main_qualities + low_qualities}
			for item in self.results:
				q = (item.get('quality') or 'SD').upper()
				if q in counts:
					counts[q] += 1
				else:
					counts['SD'] += 1
			# Pick the tier to display: main tier wins if any of its buckets
			# has results; otherwise fall back to the low tier (cinema-only).
			main_has_results = any(counts[q[0]] > 0 for q in main_qualities)
			display_order = main_qualities if main_has_results else low_qualities
			parts = [
				'[COLOR %s][B]%s:%d[/B][/COLOR]' % (q_color, q_label, counts[q_key])
				for q_key, q_color, q_label in display_order
				if counts[q_key] > 0
			]
			if not parts:
				return ''
			# Same separator color used by extra_info in make_items() for visual consistency.
			sep = '[COLOR FFffb74d] | [/COLOR]'
			return sep.join(parts)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return ''


	def make_items(self):
		def builder():
			# Resolver de badges: built-in por defecto, o el pack custom del
			# usuario si hay uno instalado y activo. Se resuelve UNA vez por
			# lista (nada de I/O ni lectura de settings por cada source).
			from resources.lib.modules import badges_config
			_badge_resolver = badges_config.get_resolver()
			for count, item in enumerate(self.results, 1):
				try:
					listitem = self.make_listitem()
					quality = item.get('quality', 'SD')
					quality_icon = self.get_quality_iconPath(quality)
					extra_info = item.get('info') or ''
					# Normalizar separadores: getFileType usa ' / ', display espera ' | '
					# 1) ' / ' -> ' | '  2) quitar / sueltas  3) normalizar | sueltas
					import re as _re
					extra_info = extra_info.replace(' /', ' |').replace('/', '')
					extra_info = _re.sub(r'\s*\|\s*', ' | ', extra_info)  # normaliza spacing alrededor de |
					extra_info = _re.sub(r'(\s*\|\s*)+$', '', extra_info)  # quita trailing |
					extra_info = extra_info.split('GB ', 1)[-1]
					extra_info = extra_info.lstrip(' |').strip()
					extra_info_focused = ''
					_parts = []
					if extra_info:
						# Tabla de sinonimos para normalizacion global (aplica a todos los scrapers)
						_SYNONYMS = {
							'DOLBY VISION': 'DOLBY-VISION', 'DOLBY-VISION': 'DOLBY-VISION', 'DV': 'DOLBY-VISION',
							'DOLBY ATMOS': 'ATMOS', 'HDR10PLUS': 'HDR10+', 'HDR10 PLUS': 'HDR10+',
							'WEBDL': 'WEB-DL', 'WEB DL': 'WEB-DL', 'WEB': 'WEB',
							'BLU RAY': 'BLURAY', 'BLU-RAY': 'BLURAY',
							'MULTI LANG': 'MULTI-LANG', 'MULTILANG': 'MULTI-LANG', 'MULTI': 'MULTI-LANG',
							'DD PLUS': 'DD+', 'EAC3': 'DD+', 'AC3': 'DD',
							'10 BIT': '10BIT', 'AVC': 'H264', 'H.264': 'H264', 'H.265': 'HEVC',
							'X265': 'HEVC', 'X264': 'H264', 'HEVC': 'HEVC',
						}
						# Deduplicar con normalizacion de sinonimos (aplica a TODOS los scrapers)
						# Evita: HDR|HDR, DV|DOLBY-VISION, X265|HEVC, MULTI|MULTI-LANG, etc.
						_seen_parts = set()
						_parts = []
						for _p in extra_info.split(' | '):
							_p = _p.strip()
							# Descartar fragmentos de size residuales (ej. "9.32 GB" o "9.32")
							if not _p or _re.match(r'^\d+(\.\d+)?\s*(GB|MB|GiB|MiB)?$', _p, _re.I):
								continue
							_norm = _SYNONYMS.get(_p.upper(), _p.upper())
							if _norm not in _seen_parts:
								_parts.append(_SYNONYMS.get(_p.upper(), _p))  # display en forma canonical
								_seen_parts.add(_norm)
						extra_info = '[COLOR FFffb74d] | [/COLOR]'.join('[COLOR FF6D727D]%s[/COLOR]' % p for p in _parts)
						extra_info_focused = '[COLOR FF01579b] | [/COLOR]'.join('[COLOR FF1A1A1A]%s[/COLOR]' % p for p in _parts)
					size_label = '%.2f GB' % item.get('size', 0) if item.get('size') else 'NA'
					score_val = item.get('score', '')
					listitem.setProperty('luc_kodi.source_dict', jsdumps([item]))
					listitem.setProperty('luc_kodi.debrid', self.debrid_name(item.get('debrid')).upper())
					listitem.setProperty('luc_kodi.debridabrv', self.debrid_abv(item.get('debrid')))

					debrid_abv = self.debrid_abv(item.get('debrid'))
					# Color especial para CUSTOM (AIOStreams/MediaFusion con Debrid externo)
					if (item.get('debrid') or '').lower() == 'custom':
						highlight_color = 'ffd39886'
					else:
						highlight_color = getDebridHighlightColor(debrid_abv)
					listitem.setProperty('highlight', highlight_color)

					listitem.setProperty('highlight_tint', '60' + highlight_color[2:] if highlight_color and len(highlight_color) == 8 else '00000000')
					listitem.setProperty('luc_kodi.provider', item.get('provider').upper())
					listitem.setProperty('luc_kodi.source', item.get('source').upper())
					listitem.setProperty('luc_kodi.seeders', str(item.get('seeders')))
					listitem.setProperty('luc_kodi.hash', item.get('hash', 'N/A'))
					listitem.setProperty('luc_kodi.name', item.get('name'))
					quality_colors = {
						'4K':    'FF00BCD4',
						'1080P': 'FF4CAF50',
						'720P':  'FFFFA726',
						'SD':    'FF607D8B',
						'SCR':   'FFB71C1C',
						'CAM':   'FFB0C4DE',
					}
					quality_assets = {
						'4K':    ('resolution/card_4k.png',    'resolution/bar_4k.png'),
						'1080P': ('resolution/card_1080p.png', 'resolution/bar_1080p.png'),
						'720P':  ('resolution/card_720p.png',  'resolution/bar_720p.png'),
						'SD':    ('resolution/card_sd.png',    'resolution/bar_sd.png'),
						'SCR':   ('resolution/card_scr.png',   'resolution/bar_scr.png'),
						'CAM':   ('resolution/card_cam_b.png',  'resolution/bar_cam_b.png'),
					}
					q_key = quality.upper()
					q_color = quality_colors.get(q_key, 'FF363C3D')
					q_card, q_bar = quality_assets.get(q_key, ('resolution/card_default.png', ''))
					skin_media = transPath('special://home/addons/plugin.video.luc_kodi/resources/skins/Default/media/')
					listitem.setProperty('quality_color',   q_color)
					listitem.setProperty('quality_card_bg', joinPath(skin_media, q_card))
					listitem.setProperty('quality_bar',     joinPath(skin_media, q_bar) if q_bar else '')
					listitem.setProperty('luc_kodi.quality', quality.upper())
					listitem.setProperty('luc_kodi.quality_icon', quality_icon)
					# ── Media-flag icon slots (3rd row inside each card) ─────────────
					# itemlayout freezes <visible> per item, but a per-item texture
					# ($INFO[ListItem.Property]) resolves correctly. So we compute the
					# ordered, gap-free list of icon paths here and expose them as
					# luc_kodi.flag0..flagN; the skin shows one image per slot.
					# Built-in icon set, unless the user installed+enabled a custom
					# badge pack via the Setup Wizard (Nuvio Badges Studio format),
					# in which case its regex rules take over.
					_FLAG_SLOTS = 14
					_icons = _badge_resolver(quality, item.get('name') or '', _parts, skin_media)
					for _i in range(_FLAG_SLOTS):
						_val = _icons[_i] if _i < len(_icons) else ''
						listitem.setProperty('luc_kodi.flag%d' % _i, _val)
					listitem.setProperty('luc_kodi.url', item.get('url'))
					listitem.setProperty('luc_kodi.extra_info', extra_info)
					listitem.setProperty('luc_kodi.extra_info_focused', extra_info_focused)
					listitem.setProperty('luc_kodi.size_label', size_label)
					listitem.setProperty('luc_kodi.score', str(score_val) if score_val != '' else '')
					listitem.setProperty('luc_kodi.count', '%02d.' % count)
					yield listitem
				except:
					from resources.lib.modules import log_utils
					log_utils.error()
		try:
			self.item_list = list(builder())
			self.total_results = str(len(self.item_list))
			if self.uncached and getSetting('torrent.remove.uncached') == 'true':
				icon = '/resources/skins/Default/media/common/play.png'
				quality_icon = transPath('special://home/addons/plugin.video.luc_kodi' + icon)
				uncached = str(len(self.uncached))
				fill_char = str.rjust(' ', len(self.total_results) + 1, '>')
				listitem = self.make_listitem()
				listitem.setProperty('luc_kodi.name', 'View Uncached Torrents')
				listitem.setProperty('luc_kodi.source', 'load uncached torrents')
				listitem.setProperty('luc_kodi.quality_icon', quality_icon)
				listitem.setProperty('luc_kodi.size_label', uncached)
				listitem.setProperty('luc_kodi.count', fill_char)
				self.item_list.append(listitem)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def set_properties(self):
		if self.meta is None: return
		try:
			self.setProperty('luc_kodi.highlight.color', getSourceHighlightColor())
			self.setProperty('luc_kodi.total_results', self.total_results)
			self.setProperty('luc_kodi.quality_breakdown', self._compute_quality_breakdown())
			self.setProperty('luc_kodi.season', str(self.meta.get('season', '')))
			if 'tvshowtitle' in self.meta and 'season' in self.meta and 'episode' in self.meta: self.setProperty('luc_kodi.seas_ep', 'S%02dE%02d' % (int(self.meta['season']), int(self.meta['episode'])))
			if self.meta.get('season_poster'): self.setProperty('luc_kodi.poster', self.meta.get('season_poster', ''))
			else: self.setProperty('luc_kodi.poster', self.meta.get('poster', ''))
			self.setProperty('luc_kodi.fanart', self.meta.get('fanart', ''))
			self.setProperty('luc_kodi.clearlogo',     self.meta.get('clearlogo', ''))
			self.setProperty('luc_kodi.network_logo', self.meta.get('network_logo', ''))
			self.setProperty('luc_kodi.plot', self.meta.get('plot', ''))
			self.setProperty('luc_kodi.year', str(self.meta.get('year', '')))
			new_date = tools.convert_time(stringTime=str(self.meta.get('premiered', '')), formatInput='%Y-%m-%d', formatOutput='%m-%d-%Y', zoneFrom='utc', zoneTo='utc')
			self.setProperty('luc_kodi.premiered', new_date)
			mpaa = self.meta.get('mpaa') if self.meta.get('mpaa') else ''
			self.setProperty('luc_kodi.mpaa', mpaa)
			if self.meta.get('duration'):
				duration = int(self.meta.get('duration')) / 60
				duration = '%.0f min' % duration
			else: duration = ''
			self.setProperty('luc_kodi.duration', duration)
			details = ' | '.join(i for i in (mpaa, duration) if i)
			self.setProperty('luc_kodi.details', details)
			self.setProperty('luc_kodi.wide_list', 'true' if self.window_id == WIDE_LIST_ID else 'false')
			self._fetch_ratings()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def _fetch_ratings(self):
		"""
		Ratings pipeline — slots filled by best available source per slot:

		  MDBList (if configured) fills slots first.
		  Tier 2 fills any slots still empty after MDBList:
		    TMDB  : from meta dict (always, zero config)
		    Trakt : plugin's built-in API key, public endpoint, no login
		    IMDb  : OMDB free key (omdbapi.com) with MC/RT fallback

		  Properties set:
		    luc_kodi.rating.tmdb        — score string e.g. "7.3"
		    luc_kodi.rating.trakt       — score string e.g. "8.1"
		    luc_kodi.rating.imdb        — score string (IMDb, MC or RT value)
		    luc_kodi.rating.imdb_source — 'imdb' | 'metacritic' | 'rt'
		"""
		try:
			# Clear previous values so stale data never shows
			for svc in ('tmdb', 'trakt', 'imdb', 'imdb_source'):
				self.setProperty('luc_kodi.rating.%s' % svc, '')

			mediatype = self.meta.get('mediatype', 'movie')
			imdb_id   = self.meta.get('imdb', '')

			# ── TMDB from meta — always available regardless of tier ──
			tmdb_val = self.meta.get('rating', '')
			if tmdb_val:
				try:
					self.setProperty('luc_kodi.rating.tmdb', '%.1f' % float(tmdb_val))
				except (ValueError, TypeError):
					pass

			if not imdb_id:
				return

			# ════════════════════════════════════════════════════════
			# MDBList — fills slots when API key is configured
			# Any slot left empty here will be filled by Tier 2 below
			# ════════════════════════════════════════════════════════
			try:
				from resources.lib.modules import mdblist
				if mdblist.getMDBListCredentialsInfo():
					data = mdblist.getMediaInfo(imdb_id, mediatype)
					if data:
						ratings = data.get('ratings') or []
						score_map = {}
						for r in ratings:
							src = (r.get('source') or '').lower()
							val = r.get('value')
							if val is not None:
								score_map[src] = val

						# TMDB — override meta value with MDBList if available
						if 'tmdb' in score_map:
							try:
								self.setProperty('luc_kodi.rating.tmdb', '%.1f' % float(score_map['tmdb']))
							except (ValueError, TypeError):
								pass

						# Trakt
						for key in ('trakt', 'traktus'):
							if key in score_map:
								try:
									self.setProperty('luc_kodi.rating.trakt', '%.1f' % float(score_map[key]))
								except (ValueError, TypeError):
									pass
								break

						# IMDb → Metacritic fallback (from MDBList data)
						if 'imdb' in score_map:
							try:
								self.setProperty('luc_kodi.rating.imdb',        '%.1f' % float(score_map['imdb']))
								self.setProperty('luc_kodi.rating.imdb_source', 'imdb')
							except (ValueError, TypeError):
								pass
						else:
							for key in ('metacritic', 'metacritics'):
								if key in score_map:
									try:
										self.setProperty('luc_kodi.rating.imdb',        '%d' % int(float(score_map[key])))
										self.setProperty('luc_kodi.rating.imdb_source', 'metacritic')
									except (ValueError, TypeError):
										pass
									break
			except Exception:
				from resources.lib.modules import log_utils
				log_utils.error()

			# ════════════════════════════════════════════════════════
			# Tier 2 — fills any slot still empty (MDBList missing
			# data, not configured, or returned N/A for that slot)
			# ════════════════════════════════════════════════════════

			# ── Trakt — only if slot still empty ──
			if not self.getProperty('luc_kodi.rating.trakt'):
				try:
					from resources.lib.modules.trakt import getTraktAsJson
					from resources.lib.database import cache
					if mediatype == 'episode':
						season  = self.meta.get('season', '')
						episode = self.meta.get('episode', '')
						trakt_url = '/shows/%s/seasons/%s/episodes/%s/ratings' % (imdb_id, season, episode)
					elif mediatype in ('tvshow', 'season'):
						trakt_url = '/shows/%s/ratings' % imdb_id
					else:
						trakt_url = '/movies/%s/ratings' % imdb_id
					trakt_data = cache.get(getTraktAsJson, 24, trakt_url)
					if trakt_data and trakt_data.get('rating'):
						self.setProperty('luc_kodi.rating.trakt', '%.1f' % float(trakt_data['rating']))
				except Exception:
					from resources.lib.modules import log_utils
					log_utils.error()

			# ── OMDB — only if IMDb slot still empty ──
			if not self.getProperty('luc_kodi.rating.imdb'):
				try:
					omdb_key = getSetting('omdb.apikey').strip()
					if omdb_key:
						import requests as _req
						from resources.lib.database import cache
						def _omdb_fetch(iid, key):
							try:
								r = _req.get('https://www.omdbapi.com/', params={'i': iid, 'apikey': key}, timeout=8)
								if r.status_code == 200:
									return r.json()
							except Exception:
								pass
							return None
						omdb = cache.get(_omdb_fetch, 48, imdb_id, omdb_key)
						if omdb:
							imdb_score = omdb.get('imdbRating', '')
							if imdb_score and imdb_score != 'N/A':
								self.setProperty('luc_kodi.rating.imdb',        imdb_score)
								self.setProperty('luc_kodi.rating.imdb_source', 'imdb')
							else:
								ratings_list = omdb.get('Ratings', [])
								mc_raw = next((r['Value'] for r in ratings_list if r.get('Source') == 'Metacritic'), None)
								if mc_raw and mc_raw != 'N/A':
									self.setProperty('luc_kodi.rating.imdb',        mc_raw.split('/')[0].strip())
									self.setProperty('luc_kodi.rating.imdb_source', 'metacritic')
								else:
									rt_raw = next((r['Value'] for r in ratings_list if r.get('Source') == 'Rotten Tomatoes'), None)
									if rt_raw and rt_raw != 'N/A':
										self.setProperty('luc_kodi.rating.imdb',        rt_raw)
										self.setProperty('luc_kodi.rating.imdb_source', 'rt')
				except Exception:
					from resources.lib.modules import log_utils
					log_utils.error()

		except Exception:
			from resources.lib.modules import log_utils
			log_utils.error()

	def load_uncachedTorrents(self):
		try:
			from resources.lib.windows.uncached_results import UncachedResultsXML
			from resources.lib.modules.control import addonPath, addonId
			window = UncachedResultsXML('uncached_results.xml', addonPath(addonId()), uncached=self.uncached, meta=self.meta)
			window.run()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
