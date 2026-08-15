# -*- coding: utf-8 -*-
"""
	plugin.video.luc_kodi — Custom Badges engine

	Permite reemplazar los iconos de badges (Dolby Atmos, HDR, Dolby Vision,
	etc.) que se muestran en la 3a fila de cada card en Source Results por un
	pack "custom" instalado por el usuario, en el mismo espiritu que Nuvio
	Badges Studio (https://dustincos.github.io/nuvio-badges/):

	  https://raw.githubusercontent.com/dustincos/nuvio-badges/main/badges.json

	Formato aceptado en la importacion (compatible con el de Nuvio):
	  {
	    "name": "opcional",
	    "filters": [
	      {
	        "id": "v-hdr", "name": "HDR", "pattern": "(?i)\\bHDR\\b",
	        "imageURL": "https://.../hdr.png", "isEnabled": true
	      }, ...
	    ]
	  }
	(tambien se acepta la clave "rules" en vez de "filters", y "image"/
	"image_url" en vez de "imageURL", para packs hechos a mano).

	Cada imagen referenciada se descarga UNA sola vez durante la instalacion
	y se cachea localmente en addon_data/badges/ — en tiempo de reproduccion
	nunca se depende de la red, solo de los ficheros ya cacheados.

	Si el pack custom esta desactivado (o no hay ninguno instalado), el
	comportamiento es EXACTAMENTE el de siempre (lista de iconos incluidos
	en el addon, `_builtin_icons()` a continuacion es una copia literal de
	la logica previa de `source_results.py`).

	Instalacion: via badges_wizard.py (Setup Wizard, mismo patron que
	Torz/Comet/Sootio/Meteor — servidor LAN local sin teclado, o pegado
	manual como fallback).
"""

import json
import os
import re as _re

from resources.lib.modules import control
from resources.lib.modules.control import dataPath, joinPath, setting as getSetting, setSetting


def _invalidate_settings_cache():
	"""El dict cacheado en Window(10000)['luc_kodi_settings'] es la unica fuente
	de verdad de control.setting(). Tras un setSetting() externo hay que
	invalidarlo o seguiriamos leyendo el valor viejo (v1.0.38 settings cache)."""
	try:
		control.homeWindow.clearProperty('luc_kodi_settings')
	except Exception:
		pass


FLAG_SLOTS = 14  # mismo limite que _FLAG_SLOTS en source_results.py

_CACHE = {'mtime': None, 'rules': None}


# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------

def _badges_dir():
	return joinPath(dataPath, 'badges')


def _config_path():
	return joinPath(_badges_dir(), 'badges.json')


# -----------------------------------------------------------------------------
# Estado
# -----------------------------------------------------------------------------

def is_custom_enabled():
	try:
		return getSetting('badges.custom.enabled') == 'true' and os.path.isfile(_config_path())
	except Exception:
		return False


def reset_to_default():
	"""Desactiva el pack custom. No borra los ficheros descargados por si el
	usuario quiere volver a activarlo despues sin re-descargar nada."""
	try:
		setSetting('badges.custom.enabled', 'false')
		setSetting('badges.custom.name', 'not installed')
	except Exception:
		pass
	_invalidate_settings_cache()
	_CACHE['mtime'] = None
	_CACHE['rules'] = None


# -----------------------------------------------------------------------------
# Instalacion desde una URL (badges.json)
# -----------------------------------------------------------------------------

def _guess_ext(url):
	path = (url or '').split('?', 1)[0]
	low = path.lower()
	for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
		if low.endswith(ext):
			return ext
	return '.png'


def _safe_filename(s):
	s = _re.sub(r'[^A-Za-z0-9_-]+', '_', s or '').strip('_')
	return (s[:64] or 'badge')


def _derive_pack_name(url):
	try:
		from urllib.parse import urlparse
		p = urlparse(url)
		parts = [x for x in p.path.split('/') if x]
		if len(parts) >= 2:
			return '%s/%s' % (parts[0], parts[1])
		return p.netloc or url
	except Exception:
		return url


def _http_get(url, timeout):
	import urllib.request
	req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (luc_kodi badges wizard)'})
	with urllib.request.urlopen(req, timeout=timeout) as resp:
		return resp.read()


def _download_image(url, dest):
	try:
		data = _http_get(url, 15)
		if not data:
			return False
		with open(dest, 'wb') as fh:
			fh.write(data)
		return True
	except Exception:
		return False


def install_from_url(url):
	"""Descarga, valida e instala un badges.json remoto. Devuelve (ok, msg)."""
	url = (url or '').strip()
	if not url.lower().startswith('http'):
		return False, 'That does not look like a valid http(s) URL.'

	try:
		raw = _http_get(url, 20)
	except Exception as e:
		return False, 'Could not download that URL:\n%s' % str(e)

	try:
		data = json.loads(raw.decode('utf-8', errors='replace'))
	except Exception:
		return False, 'That file is not valid JSON.'

	if not isinstance(data, dict):
		return False, 'Unexpected JSON structure (expected an object).'

	filters = data.get('filters')
	if not isinstance(filters, list) or not filters:
		filters = data.get('rules')
	if not isinstance(filters, list) or not filters:
		return False, 'No "filters" (or "rules") array found in that JSON.'

	badges_dir = _badges_dir()
	try:
		if not os.path.isdir(badges_dir):
			os.makedirs(badges_dir)
	except Exception as e:
		return False, 'Could not create local badges folder:\n%s' % str(e)

	new_rules = []
	downloaded = 0
	skipped = 0

	for i, f in enumerate(filters):
		if not isinstance(f, dict):
			skipped += 1
			continue
		pattern = f.get('pattern')
		img_url = f.get('imageURL') or f.get('image') or f.get('image_url')
		if not pattern or not img_url:
			skipped += 1
			continue
		try:
			_re.compile(pattern)
		except Exception:
			skipped += 1
			continue

		rule_id = _safe_filename(f.get('id') or f.get('name') or ('rule%03d' % i))
		fname = '%s%s' % (rule_id, _guess_ext(img_url))
		dest = joinPath(badges_dir, fname)

		if not (img_url.lower().startswith('http') and _download_image(img_url, dest)):
			skipped += 1
			continue

		downloaded += 1
		new_rules.append({
			'id': rule_id,
			'name': f.get('name') or rule_id,
			'pattern': pattern,
			'image': fname,
			'enabled': bool(f.get('isEnabled', f.get('enabled', True))),
		})

	if not new_rules:
		return False, 'None of the entries in that file could be downloaded or parsed.'

	config = {
		'name': data.get('name') or _derive_pack_name(url),
		'source_url': url,
		'rules': new_rules,
	}
	try:
		with open(_config_path(), 'w', encoding='utf-8') as fh:
			json.dump(config, fh, ensure_ascii=False)
	except Exception as e:
		return False, 'Could not save the local config:\n%s' % str(e)

	try:
		setSetting('badges.custom.enabled', 'true')
		setSetting('badges.custom.name', '%s  (%d icons)' % (config['name'], downloaded))
	except Exception:
		pass
	_invalidate_settings_cache()

	_CACHE['mtime'] = None  # forzar recarga en el proximo render

	msg = '%d badge icon(s) installed.' % downloaded
	if skipped:
		msg += '\n%d entrie(s) skipped (bad pattern/image).' % skipped
	return True, msg


# -----------------------------------------------------------------------------
# Carga del pack activo (con cache en memoria por mtime del fichero)
# -----------------------------------------------------------------------------

def _load_active_rules():
	cfg_path = _config_path()
	try:
		mtime = os.path.getmtime(cfg_path)
	except Exception:
		return None

	if _CACHE['mtime'] == mtime and _CACHE['rules'] is not None:
		return _CACHE['rules']

	try:
		with open(cfg_path, 'r', encoding='utf-8') as fh:
			data = json.load(fh)
	except Exception:
		return None

	badges_dir = _badges_dir()
	compiled = []
	for r in data.get('rules', []):
		pattern = r.get('pattern')
		image = r.get('image')
		if not pattern or not image or not r.get('enabled', True):
			continue
		img_path = joinPath(badges_dir, image)
		if not os.path.isfile(img_path):
			continue
		try:
			rx = _re.compile(pattern, _re.IGNORECASE)
		except Exception:
			continue
		compiled.append((rx, img_path))

	_CACHE['mtime'] = mtime
	_CACHE['rules'] = compiled
	return compiled


def _match_custom(rules, quality, raw_name, parts):
	search_text = u'%s %s %s' % (quality or '', raw_name or '', ' '.join(parts or []))
	out = []
	for rx, img_path in rules:
		try:
			if rx.search(search_text):
				out.append(img_path)
		except Exception:
			continue
		if len(out) >= FLAG_SLOTS:
			break
	return out


# -----------------------------------------------------------------------------
# Pack por defecto (copia literal del comportamiento previo, sin cambios)
# -----------------------------------------------------------------------------

def _builtin_icons(parts):
	up = [p.upper() for p in parts]
	def has(tok): return any(tok in u for u in up)
	out = []
	# video / source (mismo orden y reglas que el strip anterior)
	if has('DOLBY-VISION'): out.append('source/dv.png')
	if has('HDR') and not has('HDRIP'): out.append('source/hdr.png')
	if has('HDR10'): out.append('source/hdr10plus.png')
	if has('SDR'): out.append('source/sdr.png')
	if has('HEVC') or ((has('DOLBY-VISION') or has('HDR')) and not has('HDRIP') and not has('AVC')):
		out.append('source/hevc.png')
	if has('AVC'): out.append('source/h264.png')
	if has('MPEG'): out.append('source/mpeg_video.png')
	if has('REMUX'): out.append('source/REMUX.png')
	if has('AV1'): out.append('source/AV1.png')
	if has('MKV'): out.append('source/mkv2.png')
	if has('AVI'): out.append('source/avc.png')
	if has('XVID'): out.append('source/xvid.png')
	if has('BLURAY'): out.append('source/bluray.png')
	if has('M2TS'): out.append('source/m2ts.png')
	if has('HDTV'): out.append('source/hdtv.png')
	if has('WEB'): out.append('source/web-dl.png')
	if has('DVDRIP'): out.append('source/dvd.png')
	# audio
	if has('ATMOS'): out.append('audio/atmos.png')
	if has('DOLBY-TRUEHD'): out.append('audio/dolbytruehd.png')
	if has('DOLBYDIGITAL'): out.append('audio/dolbydigital.png')
	if has('DD') and not has('DD-EX'): out.append('audio/eac3.png')
	if has('DTS-HD MA'): out.append('audio/dtshd_ma.png')
	if has('DTS-X'): out.append('audio/dts_x.png')
	if has('DTS') and not has('DTS-X') and not has('DTS-HD MA'): out.append('audio/dts2.png')
	if has('AAC'): out.append('audio/aac.png')
	if has('MP3'): out.append('audio/mp3.png')
	if has('FLAC'): out.append('audio/flac.png')
	if has('MULTI-LANG'): out.append('audio/multi_lingual.png')
	# channels
	if has('2CH'): out.append('channels/2.png')
	if has('6CH'): out.append('channels/6.png')
	if has('8CH'): out.append('channels/8.png')
	return out[:FLAG_SLOTS]


# -----------------------------------------------------------------------------
# Entry point usado por source_results.py
# -----------------------------------------------------------------------------

def get_resolver():
	"""Devuelve un callable (quality, raw_name, parts, skin_media_dir) -> lista
	ORDENADA de rutas absolutas de textura para la fila de badges.

	PERF: el chequeo del setting + el stat/parseo del badges.json se resuelven
	UNA sola vez aqui, no por cada uno de los N sources de la lista. Mismo
	criterio que la regla de settings cache: nada de I/O por item.
	"""
	rules = None
	try:
		if is_custom_enabled():
			rules = _load_active_rules()
	except Exception:
		rules = None

	if not rules:
		def _default(quality, raw_name, parts, skin_media_dir):
			return [joinPath(skin_media_dir, p) for p in _builtin_icons(parts)]
		return _default

	def _custom(quality, raw_name, parts, skin_media_dir):
		try:
			matched = _match_custom(rules, quality, raw_name, parts)
		except Exception:
			matched = None
		if matched:
			return matched
		# Sin coincidencias en el pack custom -> fallback a los iconos incluidos
		return [joinPath(skin_media_dir, p) for p in _builtin_icons(parts)]
	return _custom


def get_flag_icons(quality, raw_name, parts, skin_media_dir):
	"""Conveniencia para llamadas sueltas (no en bucle)."""
	return get_resolver()(quality, raw_name, parts, skin_media_dir)
