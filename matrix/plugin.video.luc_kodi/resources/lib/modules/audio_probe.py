# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — Audio probe (v1.0.89)

	Nivel 2 de la sonda de audio: que pistas de audio hay DE VERDAD dentro del
	fichero que se va a reproducir, leidas de su cabecera antes de entregarlo
	al reproductor.

	Como funciona
	─────────────
	Un MKV describe todas sus pistas en el elemento Tracks, que mkvmerge y
	compania escriben al principio del fichero, antes del primer Cluster de
	video. Ahi va, por pista: tipo, codec, canales, idioma ISO 639-2, idioma
	BCP-47 (mkvmerge 50 en adelante, que es el unico sitio donde castellano y
	latino se distinguen por norma: es-ES frente a es-419), nombre libre y las
	marcas de pista por defecto y de comentario.

	El pre-flight ya descarga los primeros megas del enlace resuelto para medir
	la linea. La sonda se queda con los 2 primeros MB de esa misma descarga y
	los lee: CERO peticiones extra para el caso normal. Si el pre-flight esta
	apagado, pide ella sola 1 MB con Range.

	Casos raros que tambien cubre, con UNA peticion corta mas:
	  - MKV con Tracks mas alla de la cabecera descargada (se sigue la
	    SeekHead, que dice en que byte esta).
	  - MP4 con el indice (moov) al final: la cabecera del bloque de datos
	    (mdat) dice su tamano, y el moov empieza justo detras.

	Nada de esto puede romper la reproduccion: cualquier fallo deja un
	resultado 'unknown' y el flujo sigue como si el modulo no existiera.

	Parser propio en Python puro, sin dependencias: Kodi no trae ffprobe ni
	libmediainfo accesibles desde un addon.

	Lo leido se guarda por hash (y episodio) en source_ranker.db, tabla
	audio_tracks, para que la lista de fuentes pueda mostrar las pistas reales
	la proxima vez que aparezca ese torrent.
"""

import re
import ssl
import struct
import urllib.request as urllib2
from time import time as _now
from urllib.parse import parse_qsl

from resources.lib.modules import audio_langs
from resources.lib.modules import log_utils
from resources.lib.modules.control import setting as getSetting

# Cuanto de la descarga del pre-flight se conserva para leer la cabecera. En
# los MKV reales Tracks cae dentro de los primeros 10-100 KB; 2 MB deja margen
# para ficheros con adjuntos o capitulos gordos delante.
HEAD_KEEP = 2 * 1024 * 1024
# Lo que se pide cuando no hay descarga del pre-flight que aprovechar.
_OWN_HEAD = 1024 * 1024
# Lectura de un Tracks alejado (localizado por la SeekHead).
_SEEK_READ = 512 * 1024
# Tope del moov de un MP4. Una pelicula larga lo tiene de 2-8 MB por las
# tablas de muestras; por encima no compensa la espera.
_MOOV_MAX = 8 * 1024 * 1024
_TIMEOUT = 6
_NON_HTTP = ('plugin://', 'special://', 'magnet:', 'rtmp://', 'rtsp://', 'file://')

# Filas guardadas como maximo; se podan las mas viejas.
_DB_MAX_ROWS = 3000

# ── IDs EBML (Matroska) ────────────────────────────────────────────────────
EBML_HEADER = 0x1A45DFA3
SEGMENT = 0x18538067
SEEKHEAD = 0x114D9B74
SEEK = 0x4DBB
SEEK_ID = 0x53AB
SEEK_POS = 0x53AC
TRACKS = 0x1654AE6B
TRACK_ENTRY = 0xAE
CLUSTER = 0x1F43B675
T_NUMBER = 0xD7
T_TYPE = 0x83
T_DEFAULT = 0x88
T_FORCED = 0x55AA
T_HEARING = 0x55AB
T_VISUAL = 0x55AC
T_ORIGINAL = 0x55AE
T_COMMENTARY = 0x55AF
T_NAME = 0x536E
T_LANG = 0x22B59C
T_LANG_BCP = 0x22B59D
T_CODEC = 0x86
T_AUDIO = 0xE1
A_CHANNELS = 0x9F

_MKV_CODECS = (
	('A_EAC3', 'DD+'), ('A_AC3', 'DD'), ('A_TRUEHD', 'TRUE HD'), ('A_MLP', 'TRUE HD'),
	('A_DTS/LOSSLESS', 'DTS-HD MA'), ('A_DTS/EXPRESS', 'DTS-HD'), ('A_DTS', 'DTS'),
	('A_AAC', 'AAC'), ('A_OPUS', 'OPUS'), ('A_FLAC', 'FLAC'), ('A_VORBIS', 'VORBIS'),
	('A_MPEG/L3', 'MP3'), ('A_MPEG/L2', 'MP2'), ('A_PCM', 'PCM'), ('A_ALAC', 'ALAC'))
_MP4_CODECS = {
	'mp4a': 'AAC', 'ac-3': 'DD', 'ec-3': 'DD+', 'Opus': 'OPUS', 'fLaC': 'FLAC', 'dtsc': 'DTS',
	'dtsh': 'DTS-HD', 'dtsl': 'DTS-HD MA', 'dtse': 'DTS-HD', 'mlpa': 'TRUE HD', 'alac': 'ALAC',
	'.mp3': 'MP3', 'lpcm': 'PCM', 'sowt': 'PCM', 'twos': 'PCM'}
_LAYOUT = {1: '1.0', 2: '2.0', 3: '2.1', 6: '5.1', 7: '6.1', 8: '7.1'}

# Pistas que se reconocen por el nombre cuando el idioma es solo 'spa'.
_LAT_NAME = re.compile(r'latin|latam|mexic|hispanoam|es-?419|\blat\b', re.I)
_CAST_NAME = re.compile(r'castell|castil|espa[nñ]a|\bspain\b|europe|es-?es\b|\bcast\b', re.I)
_BR_NAME = re.compile(r'bra[sz]il|pt-?br', re.I)
_FRCA_NAME = re.compile(r'qu[eé]bec|canad|\bvfq\b|fr-?ca', re.I)
_COMMENT_NAME = re.compile(r'comment|comentario|commento|kommentar', re.I)
_AD_NAME = re.compile(r'descri|audio ?desc|\bad\b', re.I)


# ── ajustes ────────────────────────────────────────────────────────────────

def enabled():
	try:
		return getSetting('audio.probe.enabled') == 'true'
	except Exception:
		return False


def notify_mode():
	"""0 = mostrar las pistas, 1 = solo si falta el preferido, 2 = nunca.
	select de Kodi: devuelve el INDICE."""
	try:
		return int(getSetting('audio.probe.notify') or '0')
	except Exception:
		return 0


# ── lectura EBML ───────────────────────────────────────────────────────────

def _vint(buf, pos, keep_marker):
	"""Entero de longitud variable. Devuelve (valor, nueva_pos) o (None, pos)
	si no hay bytes suficientes. keep_marker=True para IDs (el ID incluye el
	bit de longitud), False para tamanos. Un tamano con todos los bits a 1 es
	'desconocido' y vuelve como -1."""
	if pos >= len(buf):
		return None, pos
	b = buf[pos]
	if b == 0:
		return None, pos
	length = 1
	mask = 0x80
	while not (b & mask):
		mask >>= 1
		length += 1
	if pos + length > len(buf):
		return None, pos
	val = b if keep_marker else (b & (mask - 1))
	all_ones = (b & (mask - 1)) == (mask - 1)
	for i in range(1, length):
		nb = buf[pos + i]
		val = (val << 8) | nb
		if nb != 0xFF:
			all_ones = False
	if not keep_marker and all_ones:
		return -1, pos + length
	return val, pos + length


def _elements(buf, start, end):
	"""Recorre los hijos de un elemento: (id, pos_datos, tamano). Se para en
	cuanto los bytes no alcanzan."""
	pos = start
	end = min(end, len(buf))
	while pos < end:
		eid, p = _vint(buf, pos, True)
		if eid is None:
			return
		size, p = _vint(buf, p, False)
		if size is None:
			return
		yield eid, p, size
		if size < 0:
			return
		pos = p + size


def _uint(buf, pos, size):
	v = 0
	for i in range(size):
		v = (v << 8) | buf[pos + i]
	return v


def _str(buf, pos, size):
	return bytes(buf[pos:pos + size]).split(b'\x00', 1)[0].decode('utf-8', 'ignore').strip()


def _parse_track_entry(buf, start, end):
	t = {'type': 0, 'default': True, 'forced': False, 'commentary': False, 'ad': False,
	     'name': '', 'lang': 'eng', 'bcp': '', 'codec_id': '', 'channels': 0}
	for eid, p, size in _elements(buf, start, end):
		if size < 0 or p + size > len(buf):
			break
		if eid == T_TYPE: t['type'] = _uint(buf, p, size)
		elif eid == T_DEFAULT: t['default'] = bool(_uint(buf, p, size))
		elif eid == T_FORCED: t['forced'] = bool(_uint(buf, p, size))
		elif eid == T_COMMENTARY: t['commentary'] = bool(_uint(buf, p, size))
		elif eid == T_VISUAL: t['ad'] = bool(_uint(buf, p, size))
		elif eid == T_NAME: t['name'] = _str(buf, p, size)
		elif eid == T_LANG: t['lang'] = _str(buf, p, size) or 'eng'
		elif eid == T_LANG_BCP: t['bcp'] = _str(buf, p, size)
		elif eid == T_CODEC: t['codec_id'] = _str(buf, p, size)
		elif eid == T_AUDIO:
			for aid, ap, asz in _elements(buf, p, p + size):
				if asz < 0 or ap + asz > len(buf):
					break
				if aid == A_CHANNELS:
					t['channels'] = _uint(buf, ap, asz)
	return t


def _parse_tracks_body(buf, start, end):
	tracks = []
	for eid, p, size in _elements(buf, start, end):
		if size < 0 or p + size > len(buf):
			break
		if eid == TRACK_ENTRY:
			tracks.append(_parse_track_entry(buf, p, p + size))
	return tracks


def parse_mkv(buf):
	"""Devuelve {'tracks': [...]} si encontro Tracks, {'need': (offset, len)}
	si Tracks esta mas alla de lo descargado, o {} si no es un MKV legible."""
	try:
		eid, p = _vint(buf, 0, True)
		if eid != EBML_HEADER:
			return {}
		size, p = _vint(buf, p, False)
		if size is None or size < 0:
			return {}
		p += size
		eid, p = _vint(buf, p, True)
		if eid != SEGMENT:
			return {}
		size, seg_data = _vint(buf, p, False)
		if size is None:
			return {}
		seg_end = len(buf) if size < 0 else seg_data + size
		tracks_at = None
		for eid, dp, sz in _elements(buf, seg_data, seg_end):
			if eid == TRACKS:
				if sz >= 0 and dp + sz <= len(buf):
					return {'tracks': _parse_tracks_body(buf, dp, dp + sz)}
				# Empieza dentro pero no cabe: se pide desde su cabecera.
				return {'need': (_header_start(buf, seg_data, TRACKS), max(sz, 0) + 64)}
			if eid == SEEKHEAD and sz >= 0 and dp + sz <= len(buf):
				for sid, sp, ssz in _elements(buf, dp, dp + sz):
					if sid != SEEK or ssz < 0:
						continue
					target, where = None, None
					for kid, kp, ksz in _elements(buf, sp, sp + ssz):
						if ksz < 0 or kp + ksz > len(buf):
							break
						if kid == SEEK_ID:
							target = _uint(buf, kp, ksz)
						elif kid == SEEK_POS:
							where = _uint(buf, kp, ksz)
					if target == TRACKS and where is not None:
						tracks_at = seg_data + where
			if eid == CLUSTER or sz < 0:
				break
		if tracks_at is not None:
			return {'need': (tracks_at, _SEEK_READ)}
		return {}
	except Exception:
		return {}


def _header_start(buf, seg_data, wanted):
	"""Offset de la cabecera del hijo `wanted` del Segment."""
	pos = seg_data
	for eid, dp, sz in _elements(buf, seg_data, len(buf)):
		if eid == wanted:
			return pos
		if sz < 0:
			break
		pos = dp + sz
	return seg_data


def parse_tracks_element(buf):
	"""Lee un buffer que EMPIEZA en la cabecera de un elemento Tracks."""
	try:
		eid, p = _vint(buf, 0, True)
		if eid != TRACKS:
			return []
		size, p = _vint(buf, p, False)
		if size is None:
			return []
		end = len(buf) if size < 0 else min(len(buf), p + size)
		return _parse_tracks_body(buf, p, end)
	except Exception:
		return []


# ── lectura MP4 ────────────────────────────────────────────────────────────

def _boxes(buf, start, end):
	pos = start
	end = min(end, len(buf))
	while pos + 8 <= end:
		size, btype = struct.unpack('>I4s', bytes(buf[pos:pos + 8]))
		hdr = 8
		if size == 1:
			if pos + 16 > len(buf):
				return
			size = struct.unpack('>Q', bytes(buf[pos + 8:pos + 16]))[0]
			hdr = 16
		elif size == 0:
			size = end - pos
		if size < hdr:
			return
		yield btype.decode('latin-1'), pos, pos + hdr, pos + size
		pos += size


def _mp4_lang(packed):
	if not packed or packed == 0x7FFF:
		return 'und'
	return ''.join(chr(((packed >> s) & 0x1F) + 0x60) for s in (10, 5, 0))


def _parse_trak(buf, start, end):
	t = {'type': 0, 'default': True, 'forced': False, 'commentary': False, 'ad': False,
	     'name': '', 'lang': 'und', 'bcp': '', 'codec_id': '', 'channels': 0}
	for btype, bpos, dpos, bend in _boxes(buf, start, end):
		if btype == 'tkhd' and dpos + 4 <= len(buf):
			flags = _uint(buf, dpos + 1, 3)
			t['default'] = bool(flags & 1)
		elif btype == 'mdia':
			for mt, mpos, mdp, mend in _boxes(buf, dpos, bend):
				if mt == 'mdhd' and mdp + 1 <= len(buf):
					off = mdp + (32 if buf[mdp] == 1 else 20)
					if off + 2 <= len(buf):
						t['lang'] = _mp4_lang(_uint(buf, off, 2))
				elif mt == 'elng':
					t['bcp'] = _str(buf, mdp + 4, mend - mdp - 4)
				elif mt == 'hdlr' and mdp + 24 <= len(buf):
					handler = bytes(buf[mdp + 8:mdp + 12]).decode('latin-1')
					t['type'] = {'vide': 1, 'soun': 2, 'subt': 17, 'sbtl': 17, 'text': 17}.get(handler, 0)
					t['name'] = _str(buf, mdp + 24, mend - mdp - 24)
				elif mt == 'minf':
					for nt, npos, ndp, nend in _boxes(buf, mdp, mend):
						if nt != 'stbl':
							continue
						for st, spos, sdp, send in _boxes(buf, ndp, nend):
							if st != 'stsd' or sdp + 16 > len(buf):
								continue
							entry = sdp + 8
							fmt = bytes(buf[entry + 4:entry + 8]).decode('latin-1')
							t['codec_id'] = fmt
							if fmt not in ('ac-3', 'ec-3') and entry + 26 <= len(buf):
								t['channels'] = _uint(buf, entry + 24, 2)
	return t


def parse_mp4(buf, base=0):
	"""{'tracks': [...]} si el moov esta en el buffer, {'need': (off, len)} si
	esta detras del mdat, {} si no es MP4."""
	try:
		if len(buf) < 12 or bytes(buf[4:8]) not in (b'ftyp', b'moov', b'free', b'skip', b'wide'):
			return {}
		after_mdat = None
		for btype, bpos, dpos, bend in _boxes(buf, 0, len(buf) + (1 << 62)):
			if btype == 'moov':
				if bend <= len(buf):
					tracks = [_parse_trak(buf, d, e) for bt, bp, d, e in _boxes(buf, dpos, bend) if bt == 'trak']
					return {'tracks': tracks}
				return {'need': (base + bpos, min(bend - bpos, _MOOV_MAX))}
			if btype == 'mdat':
				after_mdat = base + bend
			if bend > len(buf):
				break
		if after_mdat is not None:
			return {'need': (after_mdat, 64 * 1024), 'probe_moov': True}
		return {}
	except Exception:
		return {}


def parse_moov_at(buf):
	"""Buffer que EMPIEZA en la cabecera de un box. Si es el moov y esta
	entero, lo lee; si es el moov y falta, dice cuanto pedir."""
	try:
		for btype, bpos, dpos, bend in _boxes(buf, 0, 1 << 62):
			if btype == 'moov':
				if bend <= len(buf):
					return {'tracks': [_parse_trak(buf, d, e) for bt, bp, d, e in _boxes(buf, dpos, bend) if bt == 'trak']}
				# Longitud a pedir contando desde el principio del buffer.
				return {'more': bend}
			# Relleno entre el mdat y el moov: se salta si cabe entero.
			if btype in ('free', 'skip', 'wide', 'uuid') and bend <= len(buf):
				continue
			return {}
		return {}
	except Exception:
		return {}


# ── red ────────────────────────────────────────────────────────────────────

def _fetch(url, start, length):
	"""GET con Range. Devuelve bytes o b''. Respeta la sintaxis de cabeceras
	de Kodi (url|H=V), como el pre-flight."""
	resp = None
	try:
		clean_url, hdrs = url, {}
		if '|' in url:
			clean_url, qs = url.split('|', 1)
			try:
				hdrs.update(dict(parse_qsl(qs)))
			except Exception:
				pass
		hdrs.setdefault('User-Agent', 'Mozilla/5.0')
		hdrs['Range'] = 'bytes=%d-%d' % (start, start + length - 1)
		req = urllib2.Request(clean_url, headers=hdrs)
		try:
			ctx = ssl._create_unverified_context()
		except Exception:
			ctx = None
		resp = urllib2.urlopen(req, timeout=_TIMEOUT, context=ctx)
		code = int(resp.getcode() or 200)
		# Un servidor que ignora Range y devuelve 200 manda el fichero desde
		# el byte 0: solo vale si lo que se pedia era justo el principio.
		if code == 200 and start > 0:
			return b''
		out = bytearray()
		t0 = _now()
		while len(out) < length and (_now() - t0) < _TIMEOUT:
			chunk = resp.read(min(256 * 1024, length - len(out)))
			if not chunk:
				break
			out += chunk
		return bytes(out)
	except Exception:
		return b''
	finally:
		try:
			if resp is not None:
				resp.close()
		except Exception:
			pass


# ── de pistas crudas a codigos ─────────────────────────────────────────────

def _codec_label(codec_id):
	if not codec_id:
		return ''
	for prefix, label in _MKV_CODECS:
		if codec_id.startswith(prefix):
			return label
	return _MP4_CODECS.get(codec_id, codec_id.replace('A_', ''))


UNTAGGED = 'UND'  # v1.0.91: pistas de audio sin idioma declarado


def track_code(t):
	"""Codigo de fila de una pista (CAST, LAT, ES, EN...) o None."""
	name = t.get('name') or ''
	code = None
	if t.get('bcp'):
		code = audio_langs.bcp_to_code(t['bcp'])
	if not code:
		lang = (t.get('lang') or '').lower()
		if lang and lang not in ('und', 'mis', 'zxx', 'mul'):
			code = audio_langs.ISO3.get(lang) or audio_langs.ISO2.get(lang)
	if not code and name:
		# Sin idioma declarado: el nombre ('Castellano', 'English') lo dice.
		found, _m = audio_langs.from_name_info(name.lower())
		code = found[0] if found else None
	if code == 'ES' and name:
		if _LAT_NAME.search(name): code = 'LAT'
		elif _CAST_NAME.search(name): code = 'CAST'
	elif code == 'PT' and name and _BR_NAME.search(name):
		code = 'PT-BR'
	elif code == 'FR' and name and _FRCA_NAME.search(name):
		code = 'FR-CA'
	return code


def summarize(tracks):
	"""Pistas crudas → resultado legible."""
	audio, subs = [], []
	for t in tracks or ():
		if t.get('type') == 2:
			name = t.get('name') or ''
			commentary = bool(t.get('commentary')) or bool(_COMMENT_NAME.search(name))
			ad = bool(t.get('ad')) or (bool(_AD_NAME.search(name)) and not commentary)
			audio.append({
				'code': track_code(t), 'codec': _codec_label(t.get('codec_id')),
				'channels': _LAYOUT.get(t.get('channels') or 0, str(t.get('channels') or '')),
				'name': name[:40], 'default': bool(t.get('default')),
				'commentary': commentary, 'ad': ad})
		elif t.get('type') == 17:
			c = track_code(t)
			if c and c not in subs:
				subs.append(c)
	langs = []
	for a in audio:
		if a['code'] and not a['commentary'] and not a['ad'] and a['code'] not in langs:
			langs.append(a['code'])
	if 'ES' in langs and ('CAST' in langs or 'LAT' in langs):
		# Tres pistas 'spa' de las que dos tienen nombre: la tercera sigue
		# siendo espanol sin variante, y asi se queda. Solo se quita si es la
		# MISMA informacion, o sea si no hay ninguna pista ES propia.
		if not any(a['code'] == 'ES' and not a['commentary'] and not a['ad'] for a in audio):
			langs.remove('ES')
	return {'audio': audio, 'langs': langs, 'subs': subs}


# ── orquestacion ───────────────────────────────────────────────────────────

def read(url, head=None):
	"""Lee las pistas del enlace. Devuelve dict con 'container', 'audio',
	'langs', 'subs', 'reason' y 'requests' (peticiones extra hechas)."""
	out = {'container': '', 'audio': [], 'langs': [], 'subs': [], 'reason': '', 'requests': 0}
	try:
		if not url or str(url).lower().startswith(_NON_HTTP):
			out['reason'] = 'not_http'
			return out
		if not head:
			head = _fetch(url, 0, _OWN_HEAD)
			out['requests'] += 1
		if not head:
			out['reason'] = 'no_data'
			return out
		if head[:7] == b'#EXTM3U':
			out['reason'] = 'hls'
			return out
		res = parse_mkv(head)
		if res:
			out['container'] = 'mkv'
			if 'need' in res:
				off, ln = res['need']
				extra = _fetch(url, off, ln)
				out['requests'] += 1
				tracks = parse_tracks_element(extra)
			else:
				tracks = res.get('tracks') or []
		else:
			res = parse_mp4(head)
			if not res:
				out['reason'] = 'unknown_container'
				return out
			out['container'] = 'mp4'
			tracks = res.get('tracks')
			if tracks is None and 'need' in res:
				off, ln = res['need']
				extra = _fetch(url, off, ln)
				out['requests'] += 1
				moov = parse_moov_at(extra)
				if 'more' in moov and moov['more'] <= _MOOV_MAX:
					extra = _fetch(url, off, moov['more'])
					out['requests'] += 1
					moov = parse_moov_at(extra)
				tracks = moov.get('tracks') or []
		if not tracks:
			out['reason'] = 'no_tracks'
			return out
		out.update(summarize(tracks))
		if not out['audio']:
			out['reason'] = 'no_audio'
		return out
	except Exception:
		out['reason'] = 'error'
		return out


def describe(result):
	"""Linea del log. Sin URL."""
	try:
		parts = []
		for a in result.get('audio') or ():
			bits = [a.get('code') or '?']
			if a.get('codec'): bits.append(a['codec'])
			if a.get('channels'): bits.append(a['channels'])
			if a.get('name'): bits.append('"%s"' % a['name'])
			if a.get('default'): bits.append('default')
			if a.get('commentary'): bits.append('commentary')
			if a.get('ad'): bits.append('audio-description')
			parts.append(' '.join(bits))
		return '[AUDIOPROBE] container=%s tracks=%d requests=%d audio=[%s] subs=[%s]%s' % (
			result.get('container') or '?', len(result.get('audio') or ()), result.get('requests') or 0,
			' | '.join(parts), ','.join(result.get('subs') or ()),
			(' (%s)' % result['reason']) if result.get('reason') else '')
	except Exception:
		return '[AUDIOPROBE] (unprintable result)'


def key_for(item, meta):
	"""Clave de cache: hash, mas el episodio cuando lo hay. Un pack tiene un
	hash para muchos ficheros y cada uno puede traer pistas distintas."""
	try:
		h = str((item or {}).get('hash') or '').lower().strip()
		if not h or len(h) < 32:
			return None
		meta = meta or {}
		season, episode = meta.get('season'), meta.get('episode')
		if season not in (None, '') and episode not in (None, ''):
			return '%s:s%02de%02d' % (h, int(season), int(episode))
		return h
	except Exception:
		return None


def after_resolve(url, item, meta, head=None):
	"""Punto de entrada desde sources.py, con el enlace ya resuelto y el
	pre-flight ya pasado. Lee, registra, guarda y devuelve el resultado."""
	result = read(url, head)
	try:
		log_utils.log(describe(result), level=log_utils.LOGINFO)
	except Exception:
		pass
	if result.get('langs'):
		store(key_for(item, meta), result)
	elif result.get('audio'):
		# v1.0.91: hay pistas de audio pero ninguna dice su idioma (MP4 de
		# YTS: 'und'). Se guarda la marca UND para que la lista deje de
		# ensenar lo que declaraban las banderas (que eran subtitulos) y
		# diga la verdad: audio sin idioma declarado.
		store(key_for(item, meta), dict(result, langs=[UNTAGGED]))
	return result


def announce(result, autoplay_label=False):
	"""Aviso al usuario. Con autoplay_label=True no notifica: devuelve el
	texto para colgarlo de la ventana de autoplay, que ya se esta mostrando.
	El aviso de 'falta tu idioma' sale siempre que el modo no sea 'nunca'."""
	try:
		langs = result.get('langs') or []
		if not langs:
			return ''
		mode = notify_mode()
		if mode == 2:
			return ''
		from resources.lib.modules import control
		pref = audio_langs.preferred()
		text = ' [B]\u00b7[/B] '.join(audio_langs.ordered(langs, pref))
		# Solo se avisa cuando NINGUNA pista puede ser la pedida. Una pista
		# 'spa' sin variante cuando se pide castellano no se da por buena,
		# pero tampoco se denuncia: puede serlo y no hay forma de saberlo.
		missing = bool(pref) and not any(audio_langs.matches(c, pref) for c in langs)
		if missing:
			control.notification(
				title=control.lang(400809),
				message=(control.lang(400810) % _pref_label()) + '  ' + text,
				icon='WARNING', time=6000)
			return text if autoplay_label else ''
		if autoplay_label:
			return text if mode == 0 else ''
		if mode == 0:
			control.notification(title=control.lang(400809), message=text, time=4000)
		return ''
	except Exception:
		return ''


def _pref_label():
	"""El nombre del idioma preferido tal como sale en los ajustes."""
	try:
		from resources.lib.modules import control
		idx = int(getSetting('audio.langs.preferred') or '0')
		return control.lang(audio_langs.PREFERRED_LABEL_BASE + idx)
	except Exception:
		return ''


# ── cache en source_ranker.db ──────────────────────────────────────────────

def _connect():
	from resources.lib.database import source_ranker
	con = source_ranker._connect()
	con.execute('''
		CREATE TABLE IF NOT EXISTS audio_tracks (
			key     TEXT PRIMARY KEY,
			langs   TEXT NOT NULL,
			detail  TEXT,
			ts      INTEGER NOT NULL
		)
	''')
	return con


def store(key, result):
	if not key:
		return
	con = None
	try:
		con = _connect()
		con.execute('INSERT OR REPLACE INTO audio_tracks (key, langs, detail, ts) VALUES (?, ?, ?, ?)',
			(key, ','.join(result.get('langs') or ()), describe(result)[:500], int(_now())))
		con.execute('DELETE FROM audio_tracks WHERE key NOT IN '
			'(SELECT key FROM audio_tracks ORDER BY ts DESC LIMIT ?)', (_DB_MAX_ROWS,))
		con.commit()
	except Exception:
		log_utils.error()
	finally:
		try:
			if con is not None: con.close()
		except Exception:
			pass


def known(keys):
	"""{clave: [codigos]} de las que ya se sondearon. Una sola consulta para
	toda la lista de fuentes."""
	found = {}
	keys = [k for k in set(keys or ()) if k]
	if not keys:
		return found
	con = None
	try:
		con = _connect()
		for i in range(0, len(keys), 500):
			chunk = keys[i:i + 500]
			q = 'SELECT key, langs FROM audio_tracks WHERE key IN (%s)' % ','.join('?' * len(chunk))
			for row in con.execute(q, chunk).fetchall():
				found[row[0]] = [c for c in (row[1] or '').split(',') if c]
	except Exception:
		pass
	finally:
		try:
			if con is not None: con.close()
		except Exception:
			pass
	return found


def forget_all():
	con = None
	try:
		con = _connect()
		con.execute('DELETE FROM audio_tracks')
		con.commit()
	except Exception:
		pass
	finally:
		try:
			if con is not None: con.close()
		except Exception:
			pass
