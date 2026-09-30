# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — cache_footprint.py (v1.0.76)

	CUANTO OCUPA EN EL APARATO LO QUE DEJA ESTE ADDON, Y COMO SOLTARLO.

	Con la calidad en Original y el tope subido, cada ficha que se mira deja
	en el disco un poster, un fanart y a veces un clearlogo a tamano completo.
	Kodi NUNCA limpia esa carpeta: Textures13.db crece hasta que el usuario la
	borra a mano. Medido en un aparato el 4-sep-2026, con el tope en 720 la
	mediana por imagen era de 66 KB y con el tope en 3000/2160 pasa a 224 KB,
	asi que el ritmo de acumulacion se multiplica por mas de tres.

	La respuesta correcta a eso NO es bajar la calidad —esa es una eleccion
	del usuario y el addon esta para ayudarle a sostenerla— sino recoger
	detras. Este modulo hace las dos mitades de eso: contar y soltar.

	DOS CAMINOS, A PROPOSITO DISTINTOS:

	  MEDIR se hace leyendo Textures13.db en solo lectura y haciendo stat de
	  los ficheros. No se usa Textures.GetTextures por JSON-RPC porque su
	  array 'sizes' viene mal, cosa que ya estaba documentada en
	  display_test.py y no hay razon para tropezar dos veces.

	  BORRAR se hace SIEMPRE por JSON-RPC con Textures.RemoveTexture, nunca
	  tocando la base. Kodi tiene ese fichero abierto mientras corre y ademas
	  guarda estado en memoria; escribir por debajo es como se corrompe una
	  cache. La API oficial borra la fila y el fichero de forma coherente y es
	  la unica forma segura de hacerlo con Kodi vivo.

	QUE NO SE TOCA. Solo se cuentan y se borran texturas cuya URL viene de los
	proveedores de arte que usa ESTE addon. Ni la biblioteca de Kodi, ni otros
	addons, ni el skin, ni los iconos. Un limpiador que se pasa de listo con
	la carpeta de otro es peor que no tener limpiador.
"""

import os
import re

from resources.lib.modules import control
from resources.lib.modules import log_utils

try:
	from json import loads as jsloads, dumps as jsdumps
except ImportError:
	jsloads = jsdumps = None


_TMDB = re.compile(r'image\.tmdb\.org/t/p/([^/]+)/', re.I)

# v1.0.94 — proveedores de arte de ESTE addon, en un solo sitio para que el
# contador y la limpieza (maintenance.py) cuenten y borren exactamente lo
# mismo. Se anaden TheTVDB (arte de series desde la 1.0.93) y TVmaze
# (calendario y fichas de episodio), que se acumulaban sin que nadie los
# contara ni los recogiera.
ART_LIKES = ('%image.tmdb.org/t/p/%', '%fanart.tv/%',
	'%artworks.thetvdb.com/%', '%static.tvmaze.com/%')

def _texture_db():
	"""Ruta del Textures*.db en uso, cogiendo el numero mas alto que exista."""
	try:
		best, best_n = '', -1
		_dirs, files = control.listDir('special://database/')
		for name in files:
			match = re.match(r'^Textures(\d+)\.db$', name)
			if match and int(match.group(1)) > best_n:
				best, best_n = name, int(match.group(1))
		if best:
			return control.transPath('special://database/' + best)
	except Exception:
		log_utils.error()
	return ''


def _thumb_root():
	for candidate in ('special://masterprofile/Thumbnails/',
	                  special_profile() + 'Thumbnails/'):
		try:
			path = control.transPath(candidate)
			if os.path.isdir(path):
				return path
		except Exception:
			continue
	return ''


def special_profile():
	return 'special://profile/'


def _rows():
	"""(id, url, cachedurl) de las texturas de NUESTROS proveedores."""
	path = _texture_db()
	if not path:
		return []
	import sqlite3
	conn = None
	try:
		safe = path.replace('?', '%3f').replace('#', '%23')
		try:
			conn = sqlite3.connect('file:%s?mode=ro' % safe, uri=True, timeout=2)
		except Exception:
			conn = sqlite3.connect(path, timeout=2)
		out = []
		for like in ART_LIKES:
			try:
				out += conn.execute(
					'SELECT id, url, cachedurl FROM texture WHERE url LIKE ?',
					(like,)).fetchall()
			except Exception:
				continue
		return [r for r in out if r[2]]
	except Exception:
		log_utils.error()
		return []
	finally:
		try:
			if conn:
				conn.close()
		except Exception:
			pass


def _classify(url, width, height):
	"""Grupo del informe al que pertenece una textura.

	Fanart y still NO se pueden separar. TMDb no dice el tipo en la ruta —solo
	el tamano pedido— asi que lo unico medible es la forma, y un still de
	1280x720 y un fanart de 3840x2160 son los dos 16:9. Se probo separarlos por
	relacion de aspecto y el resultado fue contar diez stills como fanart, o
	sea un informe que miente en el grupo que mas pesa. Van juntos y con el
	nombre puesto: mejor un grupo honesto que dos inventados.
	"""
	low = url.lower()
	if 'fanart.tv' in low:
		return 'fanart.tv'
	if 'artworks.thetvdb.com' in low:
		return 'TheTVDB'
	if 'static.tvmaze.com' in low:
		return 'TVmaze'
	if not _TMDB.search(url):
		return ''
	if not width or not height:
		return 'TMDb unmeasured'
	if height > width:
		return 'TMDb posters'
	return 'TMDb fanart/stills'


def _dims_and_size(root, cachedurl):
	"""(ancho, alto, bytes). Ancho y alto pueden ser 0 si no se pudo leer."""
	path = os.path.join(root, cachedurl.replace('/', os.sep))
	try:
		size = os.path.getsize(path)
	except OSError:
		return 0, 0, 0
	w = h = 0
	try:
		with open(path, 'rb') as fh:
			head = fh.read(32768)
		w, h = _jpeg_or_png_dims(head)
	except Exception:
		pass
	return w, h, size


def _jpeg_or_png_dims(data):
	try:
		if data[:8] == b'\x89PNG\r\n\x1a\n':
			import struct
			w, h = struct.unpack('>II', data[16:24])
			return int(w), int(h)
		if data[:2] == b'\xff\xd8':
			i = 2
			while i < len(data) - 9:
				if data[i] != 0xFF:
					i += 1
					continue
				marker = data[i + 1]
				if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
				              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
					h = (data[i + 5] << 8) + data[i + 6]
					w = (data[i + 7] << 8) + data[i + 8]
					return int(w), int(h)
				length = (data[i + 2] << 8) + data[i + 3]
				if length <= 0:
					break
				i += 2 + length
	except Exception:
		pass
	return 0, 0


def measure_artwork():
	"""Reparto del arte en disco por grupo.

	Devuelve {grupo: {'count', 'bytes', 'ids', 'missing'}}. 'ids' se guarda
	para poder borrar exactamente lo que se ha contado, sin volver a mirar.
	"""
	root = _thumb_root()
	out = {}
	if not root:
		return out
	for tid, url, cachedurl in _rows():
		w, h, size = _dims_and_size(root, cachedurl)
		group = _classify(url or '', w, h)
		if not group:
			continue
		entry = out.setdefault(group, {'count': 0, 'bytes': 0, 'ids': [], 'missing': 0})
		entry['count'] += 1
		entry['ids'].append(tid)
		if size > 0:
			entry['bytes'] += size
		else:
			entry['missing'] += 1
	return out


# Bases de datos propias del addon.
#
# v1.0.74 — la lista se CONSTRUYE desde las constantes de control.py en vez de
# escribirse a mano, y no es una mejora cosmetica: la lista literal anterior
# tenia tres nombres que no existen. Buscaba 'metacache.db' cuando el fichero
# se llama metadata.db —y esa suele ser la base mas grande que tiene el addon,
# o sea que faltaba justo el dato principal del informe—, 'traktSync.db' con S
# mayuscula cuando en disco es traktsync.db, que en Android no casa nunca, y
# 'furk.db', que no existe. Ademas se dejaba fuera media docena de bases
# reales. Escrito asi, el dia que se anada una base al addon aparece sola.
#
# Las dos que no viven en control.py se anaden por nombre porque sus modulos
# las declaran localmente; si algun dia suben a control.py, esta lista las
# sigue encontrando igual (el existsPath decide).
_EXTRA_DBS = ('source_ranker.db', 'reco_feedback.db')


def _own_dbs():
	names = []
	for attr in ('metacacheFile', 'cacheFile', 'searchFile', 'bookmarksFile',
	             'providercacheFile', 'traktSyncFile', 'simklSyncFile',
	             'fanarttvCacheFile', 'watchedcacheFile', 'libcacheFile',
	             'viewsFile', 'subsFile'):
		try:
			path = getattr(control, attr, '')
			if path:
				names.append(os.path.basename(path))
		except Exception:
			continue
	for name in _EXTRA_DBS:
		if name not in names:
			names.append(name)
	return names


def measure_databases():
	"""Tamano de las bases propias del addon, en bytes."""
	out = {}
	for name in _own_dbs():
		for folder in ('special://profile/addon_data/plugin.video.luc_kodi/',
		               'special://database/'):
			try:
				path = control.transPath(folder + name)
				if os.path.isfile(path):
					out[name] = os.path.getsize(path)
					break
			except Exception:
				continue
	return out


def purge(ids, progress=None):
	"""Borra texturas por id con la API oficial. Devuelve (borradas, fallos).

	Nunca escribe en Textures13.db. Si Kodi rechaza una, se sigue con las
	demas: media limpieza es mejor que ninguna, y el informe siguiente lo
	dira igualmente.
	"""
	done = failed = 0
	total = len(ids)
	for index, tid in enumerate(ids):
		if progress is not None:
			try:
				if progress.iscanceled():
					break
				progress.update(int(index * 100.0 / max(total, 1)))
			except Exception:
				pass
		try:
			raw = control.jsonrpc(jsdumps({
				'jsonrpc': '2.0', 'id': 1,
				'method': 'Textures.RemoveTexture',
				'params': {'textureid': int(tid)}}))
			if raw and '"error"' not in raw:
				done += 1
			else:
				failed += 1
		except Exception:
			failed += 1
	log_utils.log('cache_footprint: purga terminada — %d borradas, %d fallidas de %d'
	              % (done, failed, total), __name__, log_utils.LOGDEBUG)
	return done, failed


def human(size):
	"""Bytes a algo legible. Se corta en GB: por encima no hay nada que decir."""
	value = float(size or 0)
	for unit in ('B', 'KB', 'MB', 'GB'):
		if value < 1024 or unit == 'GB':
			return '%.0f %s' % (value, unit) if unit in ('B', 'KB') else '%.1f %s' % (value, unit)
		value /= 1024.0
	return '%.1f GB' % value
