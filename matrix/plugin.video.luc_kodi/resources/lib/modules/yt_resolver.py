# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — yt_resolver.py (v1.0.45)

	Resolver de vídeos de YouTube SIN API key, sin login y sin dependencias:
	API interna de YouTube (InnerTube, youtube.com/youtubei/v1/player)
	imitando clientes que no exigen PO token ni descifrado de firmas JS.

	v1.0.45 — lecciones del log real del Shield (2026-07-03):
	· android_vr devolvía LOGIN_REQUIRED "confirm you're not a bot".
	  FIX: truco visitorData de yt-dlp — la propia respuesta LOGIN_REQUIRED
	  trae responseContext.visitorData; se reintenta UNA vez con ese valor en
	  context.client.visitorData + header X-Goog-Visitor-Id, y se persiste en
	  una window property (cada tráiler es un invoker nuevo, el estado del
	  módulo muere) para que los siguientes pasen a la primera.
	· ios respondía OK pero con streamingData solo-SABR (sin PO token no hay
	  URLs utilizables) y el código pasaba EN SILENCIO. FIX: se loguea.
	· TVHTML5_SIMPLY_EMBEDDED_PLAYER 2.0 está muerto ("no longer supported").
	  Sustituido por el cliente ANDROID (sin JS; su HLS no exige PO token).

	v1.0.47 — segundo log real: los clientes keyless solo dan 360p como
	progresivo (itag 18); el 720p/1080p existe únicamente en adaptiveFormats
	(vídeo y audio separados). FIX: se genera un manifest DASH estático (MPD)
	con esos formatos —estructura tomada del generador GPL de SlyGuy
	Trailers— y se reproduce con inputstream.adaptive. Sin ISA instalado se
	cae al progresivo de siempre.

	v1.0.49 — tercer log real: ISA resolvía el MPD pero no podía abrirlo
	("CURLOpen failed ... special://temp/..."): su descargador CURL no lee
	rutas special:// ni archivos locales. FIX: el MPD se publica en una
	window property y se sirve por HTTP local (trailer_httpd.py en el
	service), igual que hacen el addon oficial de YouTube y SlyGuy.

	MANTENIMIENTO: si vuelve a romperse, actualizar _CLIENTS con las
	constantes de yt_dlp/extractor/youtube/_base.py (INNERTUBE_CLIENTS) del
	yt-dlp más reciente. La capa Invidious y la cadena de trailer.py siguen
	funcionando aunque esto caiga.
"""

import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote

import re
import xbmc
from resources.lib.modules import control
from resources.lib.modules import log_utils

LOGINFO = log_utils.LOGINFO

_PLAYER_URL = 'https://www.youtube.com/youtubei/v1/player?prettyPrint=false'
_TIMEOUT = 10
_VISITOR_PROP = 'luc_kodi.yt_visitor_data'

# Constantes de cliente — sincronizadas con yt-dlp 2026.01 (INNERTUBE_CLIENTS)
_CLIENTS = [
	{
		# Sin PO token, sin JS player. Cliente principal.
		'label': 'android_vr',
		'client': {
			'clientName': 'ANDROID_VR', 'clientVersion': '1.65.10',
			'deviceMake': 'Oculus', 'deviceModel': 'Quest 3',
			'androidSdkVersion': 32, 'osName': 'Android', 'osVersion': '12L',
			'userAgent': 'com.google.android.apps.youtube.vr.oculus/1.65.10 (Linux; U; Android 12L; eureka-user Build/SQ3A.220605.009.A1) gzip',
		},
		'client_id': 28,
	},
	{
		# Sin JS. PO token requerido para HTTPS pero NO para HLS →
		# se intenta HLS primero y progresivo como propina.
		'label': 'android',
		'client': {
			'clientName': 'ANDROID', 'clientVersion': '21.02.35',
			'androidSdkVersion': 30, 'osName': 'Android', 'osVersion': '11',
			'userAgent': 'com.google.android.youtube/21.02.35 (Linux; U; Android 11) gzip',
		},
		'client_id': 3,
		'prefer_hls': True,
	},
	{
		# Último recurso: HLS a veces disponible aunque su política pida PO.
		'label': 'ios',
		'client': {
			'clientName': 'IOS', 'clientVersion': '21.02.3',
			'deviceMake': 'Apple', 'deviceModel': 'iPhone16,2',
			'osName': 'iPhone', 'osVersion': '18.3.2.22D82',
			'userAgent': 'com.google.ios.youtube/21.02.3 (iPhone16,2; U; CPU iOS 18_3_2 like Mac OS X;)',
		},
		'client_id': 5,
		'prefer_hls': True,
	},
]


def _get_visitor_data():
	try: return control.homeWindow.getProperty(_VISITOR_PROP) or None
	except: return None


def _set_visitor_data(value):
	try:
		if value: control.homeWindow.setProperty(_VISITOR_PROP, value)
	except: pass


def _innertube_player(video_id, spec, visitor_data=None):
	client = dict(spec['client'])
	client.update({'hl': 'en', 'timeZone': 'UTC', 'utcOffsetMinutes': 0})
	if visitor_data:
		client['visitorData'] = visitor_data
	payload = {
		'context': {'client': client},
		'videoId': video_id,
		'contentCheckOk': True,
		'racyCheckOk': True,
	}
	body = json.dumps(payload).encode('utf-8')
	req = Request(_PLAYER_URL, data=body)
	req.add_header('Content-Type', 'application/json')
	req.add_header('User-Agent', spec['client']['userAgent'])
	req.add_header('X-YouTube-Client-Name', str(spec['client_id']))
	req.add_header('X-YouTube-Client-Version', spec['client']['clientVersion'])
	req.add_header('Origin', 'https://www.youtube.com')
	if visitor_data:
		req.add_header('X-Goog-Visitor-Id', visitor_data)
	try:
		resp = urlopen(req, timeout=_TIMEOUT)
		return json.loads(resp.read().decode('utf-8'))
	except (HTTPError, URLError) as e:
		control.log('[ luc_kodi ] yt_resolver: %s HTTP error: %s' % (spec['label'], e), LOGINFO)
		return None
	except Exception:
		log_utils.error()
		return None


def _response_visitor_data(data):
	try: return (data.get('responseContext') or {}).get('visitorData')
	except: return None


def _best_progressive(streaming_data):
	"""Mejor formato progresivo (audio+vídeo, URL limpia). Si viene
	'signatureCipher' en vez de 'url' necesitaría JS — se descarta."""
	best, best_height = None, -1
	for fmt in streaming_data.get('formats') or []:
		url = fmt.get('url')
		if not url: continue
		if not fmt.get('mimeType', '').startswith('video/'): continue
		height = fmt.get('height') or 0
		if height > best_height:
			best_height, best = height, url
	return best, best_height


_MPD_URL = 'http://127.0.0.1:%s/trailer.mpd'


_ISA_ID = 'inputstream.adaptive'
_isa_state = [None]  # caché por proceso (cada tráiler es un invoker nuevo, pero evita repetir JSON-RPC dentro del mismo resolve)


def _isa_available():
	"""v1.0.48: System.HasAddon devuelve false si ISA está instalado pero
	DESHABILITADO — el caso real de la tablet Android del log del 03-07.
	En Android ISA viene incluido con Kodi; si está apagado se habilita en
	silencio vía JSON-RPC. Si de verdad no está instalado (Linux/otros),
	se lanza el diálogo de instalación de Kodi una vez."""
	if _isa_state[0] is not None: return _isa_state[0]
	try:
		resp = json.loads(xbmc.executeJSONRPC(json.dumps({
			'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.GetAddonDetails',
			'params': {'addonid': _ISA_ID, 'properties': ['enabled']}})))
		addon = (resp.get('result') or {}).get('addon')
		if addon:
			if addon.get('enabled'):
				_isa_state[0] = True
				return True
			enable = json.loads(xbmc.executeJSONRPC(json.dumps({
				'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.SetAddonEnabled',
				'params': {'addonid': _ISA_ID, 'enabled': True}})))
			ok = enable.get('result') == 'OK'
			control.log('[ luc_kodi ] yt_resolver: inputstream.adaptive was disabled — auto-enabled: %s' % ok, LOGINFO)
			_isa_state[0] = ok
			return ok
		# No instalado: diálogo de instalación de Kodi (acción iniciada por el
		# usuario al pedir el tráiler, así que el prompt es aceptable)
		control.log('[ luc_kodi ] yt_resolver: inputstream.adaptive not installed — prompting Kodi install dialog', LOGINFO)
		try: control.notification(message='Installing InputStream Adaptive — retry the trailer after it finishes')
		except: pass
		xbmc.executebuiltin('InstallAddon(%s)' % _ISA_ID)
		_isa_state[0] = False
		return False
	except Exception:
		log_utils.error()
		_isa_state[0] = False
		return False


def _xml_escape(url):
	return (url.replace('&', '&amp;').replace('"', '&quot;')
			   .replace('<', '&lt;').replace('>', '&gt;'))


def _codecs(mime):
	m = re.search(r'codecs="([^"]+)"', mime or '')
	return m.group(1) if m else ''


def _codec_prefs():
	"""Filtro de códecs configurable por el usuario. AV1 (av01.*) y VP9
	Profile 2 (vp09.02.*, 10-bit/HDR) no se decodifican por hardware en
	dispositivos muy comunes (p. ej. NVIDIA Shield TV: pantalla negra o
	software-decode a tirones) → excluidos del MPD por defecto. Los
	dispositivos recientes (Google TV Streamer, Fire TV 2023+) pueden
	habilitarlos en Ajustes. H.264 (avc1) y VP9 8-bit pasan siempre."""
	return (control.setting('trailer.codec.av1') == 'true',
			control.setting('trailer.codec.vp92') == 'true')


def _codec_allowed(codecs, allow_av1, allow_vp92):
	c = (codecs or '').lower()
	if c.startswith('av01'): return allow_av1
	if c.startswith('vp09.02'): return allow_vp92
	return True


def _build_mpd(data, min_height):
	"""Manifest DASH estático a partir de adaptiveFormats con URL limpia e
	initRange/indexRange (SegmentBase). Grupos por contenedor como hace
	SlyGuy: video/mp4, audio/mp4, video/webm, audio/webm. Los reps de vídeo
	por debajo de min_height se excluyen; si ningún vídeo llega, None."""
	sd = data.get('streamingData') or {}
	allow_av1, allow_vp92 = _codec_prefs()
	groups = {'video/mp4': [], 'audio/mp4': [], 'video/webm': [], 'audio/webm': []}
	for f in sd.get('adaptiveFormats') or []:
		if not f.get('url'): continue  # signatureCipher → necesitaría JS
		if not f.get('initRange') or not f.get('indexRange'): continue
		mime = (f.get('mimeType') or '').split(';')[0].strip()
		if mime not in groups: continue
		if mime.startswith('video/'):
			if min_height and (f.get('height') or 0) < min_height: continue
			if not _codec_allowed(_codecs(f.get('mimeType')), allow_av1, allow_vp92): continue
		groups[mime].append(f)

	has_video = groups['video/mp4'] or groups['video/webm']
	has_audio = groups['audio/mp4'] or groups['audio/webm']
	if not has_video or not has_audio: return None

	try: duration = int((data.get('videoDetails') or {}).get('lengthSeconds') or 0)
	except (TypeError, ValueError): duration = 0
	if not duration:
		try: duration = int(int(has_video[0].get('approxDurationMs', 0)) / 1000)
		except Exception: duration = 300

	out = ['<MPD minBufferTime="PT1.5S" mediaPresentationDuration="PT%dS" type="static" '
		   'profiles="urn:mpeg:dash:profile:isoff-main:2011">' % duration, '<Period>']
	adap_id = 0
	for mime, fmts in groups.items():
		if not fmts: continue
		out.append('<AdaptationSet id="%d" mimeType="%s"><Role schemeIdUri="urn:mpeg:DASH:role:2011" value="main"/>' % (adap_id, mime))
		adap_id += 1
		for f in fmts:
			line = '<Representation id="%s" codecs="%s" bandwidth="%s"' % (
				f.get('itag'), _codecs(f.get('mimeType')), f.get('bitrate') or 0)
			if mime.startswith('video/'):
				line += ' width="%s" height="%s"' % (f.get('width') or 0, f.get('height') or 0)
			line += '>'
			out.append(line)
			if mime.startswith('audio/'):
				out.append('<AudioChannelConfiguration schemeIdUri="urn:mpeg:dash:23003:3:audio_channel_configuration:2011" value="2"/>')
			out.append('<BaseURL>%s</BaseURL>' % _xml_escape(f['url']))
			out.append('<SegmentBase indexRange="%s-%s"><Initialization range="%s-%s" /></SegmentBase>' % (
				f['indexRange'].get('start', 0), f['indexRange'].get('end', 0),
				f['initRange'].get('start', 0), f['initRange'].get('end', 0)))
			out.append('</Representation>')
		out.append('</AdaptationSet>')
	out.append('</Period>')
	out.append('</MPD>')
	return '\n'.join(out)


def _publish_mpd(mpd):
	"""v1.0.49: publica el MPD en la window property que sirve el
	micro-servidor del service (trailer_httpd) y devuelve la URL localhost.
	ISA solo pide el manifest una vez; los segmentos van directos a
	googlevideo (BaseURLs absolutas). Si la property del puerto no existe
	(service aún no arrancado — raro), arranque efímero de emergencia en
	este mismo invoker: sobrevive lo suficiente porque ISA pide el manifest
	nada más resolver, mientras el invoker sigue vivo."""
	try:
		from resources.lib.modules import trailer_httpd
		control.homeWindow.setProperty(trailer_httpd.PROP_CONTENT, mpd)
		port = control.homeWindow.getProperty(trailer_httpd.PROP_PORT)
		if not port:
			control.log('[ luc_kodi ] yt_resolver: trailer_httpd not running — starting ephemeral fallback', LOGINFO)
			trailer_httpd.start()
			for _ in range(20):
				port = control.homeWindow.getProperty(trailer_httpd.PROP_PORT)
				if port: break
				if control.monitor.waitForAbort(0.1): return None
		if port:
			return _MPD_URL % port
		control.log('[ luc_kodi ] yt_resolver: trailer_httpd unavailable, cannot serve MPD', LOGINFO)
	except Exception:
		log_utils.error()
	return None


def _mpd_best_height(data, min_height):
	best = 0
	allow_av1, allow_vp92 = _codec_prefs()
	for f in (data.get('streamingData') or {}).get('adaptiveFormats') or []:
		if not f.get('url') or not f.get('indexRange'): continue
		mime = (f.get('mimeType') or '')
		if mime.startswith('video/'):
			if not _codec_allowed(_codecs(mime), allow_av1, allow_vp92): continue
			h = f.get('height') or 0
			if h > best: best = h
	return best


def _extract_stream(data, spec, video_id, min_height=0):
	"""De una respuesta con status OK, saca la mejor URL reproducible.
	min_height: los progresivos por debajo se descartan; el HLS se acepta
	siempre porque el manifest adaptativo incluye todas las calidades de la
	fuente y Kodi sube solo hasta la mejor disponible."""
	sd = data.get('streamingData') or {}
	ua = spec['client']['userAgent']

	# v1.0.47: DASH adaptativo primero — es la única vía keyless a 720p/1080p
	# (el progresivo tope es 360p). Requiere inputstream.adaptive.
	if _isa_available():
		mpd = _build_mpd(data, min_height)
		if mpd:
			mpd_path = _publish_mpd(mpd)
			if mpd_path:
				control.log('[ luc_kodi ] yt_resolver: resolved %s via %s (DASH up to %sp)'
							% (video_id, spec['label'], _mpd_best_height(data, min_height)), LOGINFO)
				return {'url': mpd_path, 'user_agent': ua, 'is_hls': False,
						'is_dash': True, 'client': spec['label']}
	elif min_height:
		control.log('[ luc_kodi ] yt_resolver: inputstream.adaptive not installed — cannot serve >360p keyless', LOGINFO)

	if spec.get('prefer_hls'):
		hls = sd.get('hlsManifestUrl')
		if hls:
			control.log('[ luc_kodi ] yt_resolver: resolved %s via %s (HLS)' % (video_id, spec['label']), LOGINFO)
			return {'url': hls + '|User-Agent=' + quote(ua), 'user_agent': ua,
					'is_hls': True, 'client': spec['label']}

	url, height = _best_progressive(sd)
	if url and min_height and height < min_height:
		control.log('[ luc_kodi ] yt_resolver: %s progressive %sp < min %sp, skipping'
					% (spec['label'], height, min_height), LOGINFO)
		url = None
	if url:
		control.log('[ luc_kodi ] yt_resolver: resolved %s via %s (progressive %sp)'
					% (video_id, spec['label'], height), LOGINFO)
		return {'url': url + '|User-Agent=' + quote(ua), 'user_agent': ua,
				'is_hls': False, 'client': spec['label']}

	hls = sd.get('hlsManifestUrl')
	if hls:
		control.log('[ luc_kodi ] yt_resolver: resolved %s via %s (HLS fallback)' % (video_id, spec['label']), LOGINFO)
		return {'url': hls + '|User-Agent=' + quote(ua), 'user_agent': ua,
				'is_hls': True, 'client': spec['label']}

	# v1.0.45: antes este caso moría en silencio (lección del log del Shield)
	control.log('[ luc_kodi ] yt_resolver: %s → OK but no usable streams (SABR-only/ciphered, PO token likely required)'
				% spec['label'], LOGINFO)
	return None


def resolve(video_id, min_height=0):
	"""Devuelve dict {'url', 'user_agent', 'is_hls', 'client'} o None.
	La URL lleva |User-Agent= embebido porque googlevideo valida que el UA
	coincida con el cliente que resolvió."""
	visitor = _get_visitor_data()

	for spec in _CLIENTS:
		data = _innertube_player(video_id, spec, visitor_data=visitor)
		if not data: continue

		# Persistir SIEMPRE el visitorData más fresco que nos den
		fresh = _response_visitor_data(data)
		if fresh and fresh != visitor:
			_set_visitor_data(fresh)

		status = (data.get('playabilityStatus') or {}).get('status')
		if status == 'OK':
			resolved = _extract_stream(data, spec, video_id, min_height)
			if resolved: return resolved
			continue

		reason = (data.get('playabilityStatus') or {}).get('reason', '')
		control.log('[ luc_kodi ] yt_resolver: %s → %s %s' % (spec['label'], status, reason), LOGINFO)

		# Bot-check: reintentar UNA vez con el visitorData de la propia
		# respuesta (mismo mecanismo que yt-dlp). Solo si no lo llevaba ya.
		if status == 'LOGIN_REQUIRED' and fresh and fresh != visitor:
			control.log('[ luc_kodi ] yt_resolver: %s retrying with fresh visitorData' % spec['label'], LOGINFO)
			visitor = fresh
			data = _innertube_player(video_id, spec, visitor_data=visitor)
			if data:
				fresh2 = _response_visitor_data(data)
				if fresh2: _set_visitor_data(fresh2)
				status2 = (data.get('playabilityStatus') or {}).get('status')
				if status2 == 'OK':
					resolved = _extract_stream(data, spec, video_id, min_height)
					if resolved: return resolved
				else:
					control.log('[ luc_kodi ] yt_resolver: %s retry → %s' % (spec['label'], status2), LOGINFO)

	control.log('[ luc_kodi ] yt_resolver: could not resolve %s with any client' % video_id, LOGINFO)
	return None
