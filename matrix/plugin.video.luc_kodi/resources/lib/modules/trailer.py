# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — trailer.py (reescrito v1.0.44)

	Reproducción de tráilers SIN necesidad de que el usuario configure nada:
	ni API key de Google, ni client secret, ni login. Cadena de resolución:

		1. slyguy.trailers (si está instalado)  — handoff a su yt-dlp
		   mantenido activamente; cero mantenimiento para nosotros.
		2. script.module.yt-dlp (si está instalado) — carga blanda del
		   módulo de lekma sin declararlo como dependencia.
		3. Resolver keyless propio (yt_resolver.py, InnerTube) — SIEMPRE
		   disponible, sin add-ons externos.
		4. plugin.video.youtube (si está instalado) — comportamiento antiguo,
		   último recurso.

	El id del tráiler sale de meta['trailer'] (TMDb ya lo trae en los menús);
	si no viene, se consulta TMDb /videos en el momento (clave TMDb ya
	incluida en el addon) y, como última bala, Trakt.

	v1.0.44: eliminadas las API keys de Google hardcodeadas que traía el
	código heredado (misma clase de problema que la key personal de MDBList
	retirada en v1.0.40) y eliminado el crash al instanciar Trailer() sin
	plugin.video.youtube presente.
"""

import re
from json import loads as jsloads
from sys import argv
from urllib.parse import parse_qs, urlparse
from resources.lib.modules import client
from resources.lib.modules import control
from resources.lib.modules import log_utils

getSetting = control.setting
LOGINFO = log_utils.LOGINFO

YT_PLUGIN = 'plugin.video.youtube'
SLYGUY_PLUGIN = 'slyguy.trailers'
YTDLP_MODULE = 'script.module.yt-dlp'

# Clave TMDb incluida en el addon (misma fallback que player.py)
TMDB_FALLBACK_KEY = 'f2e500501d9fa3bd1637bfd00f11583a'
TMDB_VIDEOS = 'https://api.themoviedb.org/3/%s/%s/videos?api_key=%s'
TMDB_FIND = 'https://api.themoviedb.org/3/find/%s?api_key=%s&external_source=imdb_id'

_YT_ID_RE = re.compile(r'^[\w-]{11}$')


def _has_addon(addon_id):
	try: return control.condVisibility('System.HasAddon(%s)' % addon_id) == 1
	except: return False


class Trailer:
	def __init__(self):
		self.youtube_watch = 'https://www.youtube.com/watch?v=%s'

	# ──────────────────────────────────────────────────────────────
	# Entrada desde el router (action=play_Trailer)
	# ──────────────────────────────────────────────────────────────
	def play(self, type='', name='', year='', url='', imdb='', windowedtrailer=0, tmdb=''):
		try:
			# v1.0.50: worker devuelve VARIOS candidatos — si el primero está
			# geo-bloqueado ("not available in your country", visto en el log
			# del 04-07), se prueba el siguiente tráiler oficial de TMDb.
			candidates = self.worker(type, name, year, url, imdb, tmdb)
			if not candidates:
				control.notification(message='Trailer not found')
				return
			resolved = None
			for video_id in candidates:
				resolved = self.resolve(video_id)
				if resolved: break
				control.log('[ luc_kodi ] trailer: candidate %s failed, trying next' % video_id, LOGINFO)
			if not resolved:
				control.notification(message='Trailer not found')
				return
			title = control.infoLabel('ListItem.Title')
			if not title: title = control.infoLabel('ListItem.Label')
			if not title: title = '%s Trailer' % name if name else 'Trailer'
			icon = control.infoLabel('ListItem.Icon')
			item = control.item(label=title, offscreen=True)
			item.setProperty('IsPlayable', 'true')
			item.setArt({'icon': icon, 'thumb': icon})
			if resolved.get('is_dash'):
				# MPD local generado por yt_resolver → inputstream.adaptive.
				# manifest_type solo en Kodi 19/20 (deprecado en 21+, autodetecta).
				item.setProperty('inputstream', 'inputstream.adaptive')
				try:
					if int(control.getKodiVersion()) < 21:
						item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
				except: pass
				if resolved.get('user_agent'):
					from urllib.parse import quote
					item.setProperty('inputstream.adaptive.stream_headers',
									 'User-Agent=' + quote(resolved['user_agent']))
				item.setMimeType('application/dash+xml')
				item.setContentLookup(False)
			elif resolved.get('is_hls'):
				item.setMimeType('application/x-mpegURL')
				item.setContentLookup(False)
			try: item.setInfo(type='video', infoLabels={'title': title})
			except: pass
			control.addItem(handle=int(argv[1]), url=resolved['url'], listitem=item, isFolder=False)
			control.refresh()
			control.resolve(handle=int(argv[1]), succeeded=True, listitem=item)
			if windowedtrailer == 1:
				control.sleep(1000)
				while control.player.isPlayingVideo():
					control.sleep(1000)
				control.execute("Dialog.Close(%s, true)" % control.getCurrentDialogId)
		except:
			log_utils.error()

	# ──────────────────────────────────────────────────────────────
	# Obtener el video id de YouTube
	# ──────────────────────────────────────────────────────────────
	def worker(self, type, name, year, url, imdb, tmdb=''):
		"""Devuelve una LISTA de video ids candidatos, mejor primero."""
		official_only = getSetting('trailer.official.only') != 'false'
		if official_only and (tmdb or imdb):
			# v1.0.46: la búsqueda estricta en TMDb manda sobre el id de meta,
			# que puede ser un Teaser horneado en metacache por versiones previas
			return self.tmdb_trailer(type, tmdb, imdb, official_only=True)
		candidates = []
		vid = self._extract_id(url)
		if vid: candidates.append(vid)
		for key in self.tmdb_trailer(type, tmdb, imdb, official_only=official_only):
			if key not in candidates: candidates.append(key)
		tk = self.trakt_trailer(type, name, year, imdb)
		if tk and tk not in candidates: candidates.append(tk)
		return candidates

	def _extract_id(self, url):
		"""Acepta: id pelado de 11 chars, watch?v=, youtu.be/, embed/, y
		URLs plugin:// (video_id=) tanto nuestras como del addon de YouTube."""
		if not url: return None
		url = str(url)
		if _YT_ID_RE.match(url): return url
		try:
			parsed = urlparse(url)
			qs = parse_qs(parsed.query)
			for key in ('video_id', 'videoid', 'v', 'url'):
				vals = qs.get(key)
				if vals and _YT_ID_RE.match(vals[0]): return vals[0]
			# youtu.be/<id> o /embed/<id>
			tail = parsed.path.rstrip('/').split('/')[-1]
			if _YT_ID_RE.match(tail): return tail
		except: pass
		return None

	def tmdb_trailer(self, type, tmdb, imdb, official_only=True):
		"""Devuelve una LISTA de video ids (hasta 4, mejor primero) desde
		TMDb /videos (caché manual 7 días). Con official_only, SOLO type
		'Trailer' (nada de Teasers/Clips/Featurettes); se prioriza
		official=true y mayor size (TMDb reporta 480/720/1080/2160).
		v1.0.50: lista en vez de un único id — si el mejor candidato está
		geo-bloqueado en el país del usuario, play() prueba el siguiente."""
		try:
			key = getSetting('tmdb.api.key') or TMDB_FALLBACK_KEY
			media = 'movie' if type == 'movie' else 'tv'
			if not tmdb and imdb and str(imdb).startswith('tt'):
				result = client.request(TMDB_FIND % (imdb, key), error=True)
				if result:
					found = jsloads(result).get('%s_results' % ('movie' if media == 'movie' else 'tv'), [])
					if found: tmdb = found[0].get('id')
			if not tmdb: return []
			videos = self._tmdb_videos_cached(media, tmdb, key)
			if not videos: return []
			if official_only:
				videos = [i for i in videos if i.get('type') == 'Trailer']
			else:
				videos = [i for i in videos if i.get('type') in ('Trailer', 'Teaser')]
			if not videos: return []
			videos.sort(key=lambda i: (i.get('type') != 'Trailer', not i.get('official'), -(i.get('size') or 0)))
			keys = []
			for i in videos:
				k = i.get('key')
				if k and k not in keys: keys.append(k)
				if len(keys) >= 4: break
			return keys
		except:
			log_utils.error()
			return []

	def _tmdb_videos_cached(self, media, tmdb, key):
		from ast import literal_eval
		from time import time
		from resources.lib.database import cache
		cache_key = 'tmdb_videos_%s_%s' % (media, tmdb)
		try:
			cached = cache.cache_get(cache_key)
			if cached and (int(time()) - int(cached['date'])) < 7 * 24 * 3600:
				value = literal_eval(cached['value'])
				if isinstance(value, list): return value
		except Exception: log_utils.error()
		result = client.request(TMDB_VIDEOS % (media, tmdb, key), error=True)
		if not result: return None
		videos = [i for i in jsloads(result).get('results', []) if i.get('site') == 'YouTube']
		try: cache.cache_insert(cache_key, repr(videos))
		except Exception: log_utils.error()
		return videos

	def trakt_trailer(self, type, name, year, imdb):
		try:
			from resources.lib.modules import trakt
			id = (name.lower() + '-' + year) if imdb in ('0', '', None) else imdb
			if type == 'movie': item = trakt.getMovieSummary(id)
			else: item = trakt.getTVShowSummary(id)
			return self._extract_id(item.get('trailer'))
		except:
			log_utils.error()
			return None

	# ──────────────────────────────────────────────────────────────
	# Cadena de resolución (sin API key)
	# ──────────────────────────────────────────────────────────────
	def _min_height(self):
		try: return (0, 480, 720, 1080)[int(getSetting('trailer.min.resolution') or 2)]
		except (ValueError, TypeError, IndexError): return 720

	def resolve(self, video_id):
		"""Devuelve {'url': ..., 'is_hls': bool} o None."""
		mode = getSetting('trailer.player') or '0'
		min_height = self._min_height()

		if mode == '2':  # SlyGuy Trailers forzado
			return self._via_slyguy(video_id) or None
		if mode == '3':  # YouTube add-on forzado
			return self._via_youtube_plugin(video_id) or None
		if mode == '1':  # Solo keyless (resolver interno + Invidious)
			return self._via_builtin(video_id, min_height) or self._via_invidious(video_id, min_height) or None

		# '0' Auto: slyguy → yt-dlp módulo → interno → Invidious → youtube addon
		# v1.0.50: sin notificación de "tip" — si nada resuelve, play()
		# muestra un simple 'Trailer not found' y ya.
		return (self._via_slyguy(video_id)
				or self._via_ytdlp_module(video_id, min_height)
				or self._via_builtin(video_id, min_height)
				or self._via_invidious(video_id, min_height)
				or self._via_youtube_plugin(video_id))

	def _via_slyguy(self, video_id):
		if not _has_addon(SLYGUY_PLUGIN): return None
		control.log('[ luc_kodi ] trailer: handing off to slyguy.trailers', LOGINFO)
		return {'url': 'plugin://%s/play/?video_id=%s' % (SLYGUY_PLUGIN, video_id), 'is_hls': False}

	def _via_ytdlp_module(self, video_id, min_height=0):
		"""Carga blanda de script.module.yt-dlp (lekma) sin declararlo como
		dependencia: se añade su lib/ a sys.path solo si está instalado."""
		if not _has_addon(YTDLP_MODULE): return None
		try:
			import os, sys, xbmcaddon
			lib = os.path.join(xbmcaddon.Addon(YTDLP_MODULE).getAddonInfo('path'), 'lib')
			if lib not in sys.path: sys.path.insert(0, lib)
			from yt_dlp import YoutubeDL
			fmt = 'best[vcodec!=none][acodec!=none]/best'
			if min_height:
				fmt = ('best[height>=%d][vcodec!=none][acodec!=none]/' % min_height) + fmt
			opts = {'format': fmt,
					'quiet': True, 'no_warnings': True, 'cachedir': False,
					'noplaylist': True}
			info = YoutubeDL(opts).extract_info(self.youtube_watch % video_id, download=False)
			url = info.get('url')
			if not url and info.get('formats'):
				progressive = [f for f in info['formats']
							   if f.get('url') and f.get('vcodec') != 'none' and f.get('acodec') != 'none']
				if progressive: url = progressive[-1]['url']
			if url:
				control.log('[ luc_kodi ] trailer: resolved via script.module.yt-dlp', LOGINFO)
				return {'url': url, 'is_hls': '.m3u8' in url}
		except:
			log_utils.error()
		return None

	def _via_builtin(self, video_id, min_height=0):
		try:
			from resources.lib.modules import yt_resolver
			resolved = yt_resolver.resolve(video_id, min_height=min_height)
			if resolved:
				return {'url': resolved['url'], 'is_hls': resolved['is_hls'],
						'is_dash': resolved.get('is_dash', False),
						'user_agent': resolved.get('user_agent', '')}
		except:
			log_utils.error()
		return None

	def _via_invidious(self, video_id, min_height=0):
		"""Extracción del lado servidor vía instancias públicas de Invidious.
		Inmune al bot-check de InnerTube contra la IP del usuario porque es
		la instancia quien habla con YouTube. Se valida cada instancia con
		una petición JSON barata y se reproduce vía /latest_version con
		local=true (la instancia proxya el vídeo — las URLs de googlevideo
		van ligadas a la IP de la instancia, sin proxy darían 403 aquí).
		Lista de instancias en setting oculto: actualizable sin release."""
		instances = (getSetting('trailer.invidious.instances')
					 or 'inv.nadeko.net,invidious.nerdvpn.de,inv.thepixora.com')
		for inst in [i.strip().rstrip('/') for i in instances.split(',') if i.strip()]:
			try:
				check = 'https://%s/api/v1/videos/%s?fields=videoId,formatStreams&local=true' % (inst, video_id)
				# UA de navegador: varias instancias públicas filtran UAs no-browser
				result = client.request(check, timeout='6', headers={
					'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
					'Accept': 'application/json'})
				if not result:
					control.log('[ luc_kodi ] trailer: Invidious %s: no response (down/blocked/challenge)' % inst, LOGINFO)
					continue
				try: data = jsloads(result)
				except Exception:
					control.log('[ luc_kodi ] trailer: Invidious %s: non-JSON response (challenge page?)' % inst, LOGINFO)
					continue
				if data.get('videoId') != video_id:
					control.log('[ luc_kodi ] trailer: Invidious %s: unexpected payload %s' % (inst, str(data)[:120]), LOGINFO)
					continue
				best_url, best_h = None, -1
				if not data.get('formatStreams'):
					control.log('[ luc_kodi ] trailer: Invidious %s returned no formatStreams' % inst, LOGINFO)
				for fmt in data.get('formatStreams') or []:
					try: h = int(str(fmt.get('resolution', '0')).rstrip('p') or 0)
					except ValueError: h = 0
					if h > best_h and fmt.get('url'):
						best_h, best_url = h, fmt['url']
				if best_url and min_height and best_h < min_height:
					# el vídeo existe pero ningún formato muxed llega al mínimo;
					# la resolución no mejora en otra instancia (misma fuente)
					control.log('[ luc_kodi ] trailer: Invidious best is %sp < min %sp, skipping layer' % (best_h, min_height), LOGINFO)
					return None
				if best_url:
					if best_url.startswith('/'): best_url = 'https://%s%s' % (inst, best_url)
					control.log('[ luc_kodi ] trailer: resolved via Invidious (%s, %sp)' % (inst, best_h), LOGINFO)
					return {'url': best_url, 'is_hls': False}
				# sin formatStreams: latest_version como mejor esfuerzo (solo sin mínimo)
				if not min_height:
					url = 'https://%s/latest_version?id=%s&local=true' % (inst, video_id)
					control.log('[ luc_kodi ] trailer: resolved via Invidious latest_version (%s)' % inst, LOGINFO)
					return {'url': url, 'is_hls': False}
			except:
				continue
		control.log('[ luc_kodi ] trailer: no Invidious instance available', LOGINFO)
		return None

	def _via_youtube_plugin(self, video_id):
		if not _has_addon(YT_PLUGIN): return None
		control.log('[ luc_kodi ] trailer: falling back to plugin.video.youtube', LOGINFO)
		return {'url': 'plugin://%s/play/?video_id=%s' % (YT_PLUGIN, video_id), 'is_hls': False}
