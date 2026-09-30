# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — trailer_audio.py (v1.0.63)

	DIAGNOSTICO, no arreglo. Vuelca la tabla de pistas de audio del reproductor
	para poder escribir despues un selector honesto.

	EL PROBLEMA (medido, kodi.log 21-ago-2026). Los trailers auto-doblados de
	YouTube traen 16 pistas de audio: 8 idiomas x 2 perfiles AAC. Kodi coge
	siempre la PRIMERA, y en la NVIDIA Shield esa pista sale MUDA:

	  15:05:41  Open codec(86018), profile(1),   extrasize(0)  <- AAC-LC   MUDO
	  15:06:03  Open codec(86018), profile(-99), extrasize(0)  <- HE-AAC   SUENA

	Las dos caen al lector ADTS, las dos van sin extradata, ninguna registra
	error. El mudo NO deja rastro en el log: el hilo de audio arranca igual.
	Falla dentro del parseo de ffmpeg y Kodi no lo cuenta.

	CONSECUENCIA para el arreglo: no se puede detectar "esta pista esta rota" en
	tiempo de ejecucion. Hay que seleccionar por identidad. Y la unica senal que
	distingue las dos en el log —profile 1 vs -99— es interna de Kodi.

	Por eso esto es un volcado y no un setAudioStream(): antes de escribir el
	selector hace falta saber si la API expone algo que separe HE-AAC de AAC-LC.
	Si `name` o `codec` traen la diferencia, el selector es honesto. Si no traen
	nada, sera "indice + 1" y quedara documentado como la heuristica que es.
"""

import json

import xbmc

from resources.lib.modules import control
from resources.lib.modules import log_utils

LOGINFO = log_utils.LOGINFO

SETTING = 'trailer.audio.probe'


def _rpc(method, params):
	try:
		res = xbmc.executeJSONRPC(json.dumps({
			'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params,
		}))
		return json.loads(res)
	except Exception:
		log_utils.error()
		return {}


def probe(force=False):
	"""Vuelca al log las pistas de audio del reproductor activo.

	Se llama desde onAVStarted. Silenciosa salvo que el ajuste este activo, para
	no llenar los logs de todo el mundo con 16 lineas por reproduccion."""
	try:
		if not force and control.setting(SETTING) != 'true':
			return
		if not xbmc.Player().isPlayingVideo():
			return

		# getAvailableAudioStreams(): etiquetas tal cual las arma Kodi.
		try:
			labels = xbmc.Player().getAvailableAudioStreams() or []
		except Exception:
			labels = []
		control.log('[ luc_kodi ] trailer_audio: getAvailableAudioStreams (%s) = %s'
		            % (len(labels), labels), LOGINFO)

		# JSON-RPC: campos estructurados por pista.
		data = _rpc('Player.GetProperties', {
			'playerid': 1,
			'properties': ['currentaudiostream', 'audiostreams'],
		})
		result = (data.get('result') or {})
		streams = result.get('audiostreams') or []
		current = result.get('currentaudiostream') or {}

		control.log('[ luc_kodi ] trailer_audio: %s audiostreams, actual index=%s'
		            % (len(streams), current.get('index')), LOGINFO)
		for st in streams:
			# Se vuelca el dict COMPLETO a proposito: si una version de Kodi
			# expone un campo de perfil que hoy no conocemos, aqui aparece.
			control.log('[ luc_kodi ] trailer_audio: stream %s' % json.dumps(st, sort_keys=True), LOGINFO)

		# La pregunta concreta que este volcado tiene que contestar.
		hits = [st.get('index') for st in streams
		        if 'he-aac' in json.dumps(st).lower() or 'he_aac' in json.dumps(st).lower()]
		control.log('[ luc_kodi ] trailer_audio: indices con HE-AAC visible en la API: %s '
		            '(si sale [] el selector NO puede ir por nombre)' % hits, LOGINFO)
	except Exception:
		log_utils.error()


# --- Selector ----------------------------------------------------------------

MARK = 'luc_kodi.trailer.playing'
APPLY_SETTING = 'trailer.audio.prefer.heaac'


def _stem_of(name):
	"""Nombre de la pista sin el perfil ni separadores.

	"American English - original - AAC-LC " y "American English - original -
	HE-AAC " comparten stem: son la MISMA pista en dos perfiles. Comparar por
	stem es mas fiable que por `language`, que no siempre coincide entre las
	dos (medido: el trailer de 16 pistas tenia una entrada inglesa con codigo
	de idioma distinto del de su pareja, y por eso la seleccion fallaba).
	"""
	n = (name or '').lower().replace('_', '-')
	for tag in ('he-aac', 'heaac', 'aac-lc', 'aaclc'):
		n = n.replace(tag, '')
	return ' '.join(n.replace('-', ' ').split())


def _profile_of(name):
	"""Devuelve 'he-aac', 'aac-lc' o '' leyendo el nombre de la pista.

	MEDIDO (log 21-ago-2026 17:08): JSON-RPC devuelve el perfil literal en
	`name` — "American English - original - HE-AAC ". Es el UNICO campo que los
	distingue: `codec` es 'aac' en las dos, e `isdefault` era true en las dos
	del trailer de 2 pistas. Por eso NO hay heuristica de indice aqui.
	"""
	n = (name or '').lower().replace('_', '-')
	if 'he-aac' in n or 'heaac' in n:
		return 'he-aac'
	if 'aac-lc' in n or 'aaclc' in n:
		return 'aac-lc'
	return ''


def apply_preferred_profile():
	"""Cambia a la pista HE-AAC del MISMO idioma, solo en trailers nuestros.

	En la NVIDIA Shield la pista AAC-LC de los trailers auto-doblados de YouTube
	sale MUDA, y Kodi coge siempre la primera, que es AAC-LC. El mudo no deja
	rastro en el log —ni error de decodificacion ni nada, el hilo de audio
	arranca igual—, asi que no se puede detectar en ejecucion: hay que elegir
	por identidad.

	Tres guardas, y las tres importan:
	  1. Solo si el trailer lo lanzo luc_kodi (window property de trailer.py).
	     La reproduccion es de plugin.video.youtube; sin la marca estariamos
	     tocando tambien lo que el usuario reproduzca por su cuenta.
	  2. Solo si hay pares AAC-LC/HE-AAC. En contenido de debrid (TrueHD, AC3)
	     la busqueda vuelve vacia y no se toca nada.
	  3. Mismo `language` que la pista actual. Coger el primer HE-AAC de la
	     lista le cambiaria el idioma al usuario: en el trailer de 16 pistas
	     habia ocho idiomas y el HE-AAC del indice 1 es ingles.
	"""
	try:
		if control.setting(APPLY_SETTING) != 'true':
			return
		try:
			if not control.homeWindow.getProperty(MARK):
				return
		except Exception:
			return
		if not xbmc.Player().isPlayingVideo():
			return

		data = _rpc('Player.GetProperties', {
			'playerid': 1,
			'properties': ['currentaudiostream', 'audiostreams'],
		})
		result = (data.get('result') or {})
		streams = result.get('audiostreams') or []
		current = result.get('currentaudiostream') or {}
		if not streams:
			return

		if _profile_of(current.get('name')) == 'he-aac':
			return  # ya estamos donde queremos

		lang = current.get('language')
		stem = _stem_of(current.get('name'))
		heaac = [st for st in streams if _profile_of(st.get('name')) == 'he-aac']
		if not heaac:
			# Ni una pista HE-AAC: no es un trailer multi-perfil. No se toca.
			return

		# 1) mismo stem  2) mismo idioma  3) nada.
		# v1.0.67: antes solo se miraba el idioma, y cuando la pareja HE-AAC
		# venia etiquetada con otro codigo el selector se rendia ("no hay
		# HE-AAC en en-US") aunque la pista correcta estuviera ahi.
		target = next((st for st in heaac if _stem_of(st.get('name')) == stem), None)
		if target is None and lang:
			target = next((st for st in heaac if st.get('language') == lang), None)
		if target is None:
			# v1.0.68 — MEDIDO en el trailer "Michael": 16 pistas, HE-AAC en los
			# indices [3,5,7,9,11,13,15], ninguno en ingles. Los dos ingleses son
			# AAC-LC con el MISMO nombre, y el que Kodi elige (idx 1) sale MUDO.
			#
			# O sea que "HE-AAC" nunca fue la causa: era un indicador que acertaba
			# en los trailers anteriores. Lo que separa la pista que suena de la
			# muda es la representacion (el itag), y eso la API no lo expone. Aqui
			# solo se ven dos entradas indistinguibles.
			#
			# Ultimo recurso: si el idioma actual tiene OTRA pista, se prueba. Es
			# el mismo idioma y el mismo contenido, asi que no se le cambia nada
			# al usuario, y solo se dispara donde hoy no se hacia nada — no puede
			# romper ningun caso que ya funcione.
			same_lang = [st for st in streams
			             if st.get('language') == lang
			             and st.get('index') != current.get('index')
			             and _stem_of(st.get('name')) == stem]
			if same_lang:
				alt = same_lang[0]
				xbmc.Player().setAudioStream(int(alt.get('index')))
				control.log('[ luc_kodi ] trailer_audio: sin HE-AAC en %s; se prueba la otra pista '
				            'del mismo idioma: idx %s -> idx %s'
				            % (lang, current.get('index'), alt.get('index')), LOGINFO)
				probe(force=True)
				return
			# Aqui es donde hace falta el diagnostico, no cuando todo va bien:
			# se vuelca la tabla entera aunque el ajuste de probe este apagado.
			control.log('[ luc_kodi ] trailer_audio: hay %s pistas HE-AAC pero ninguna casa con '
			            'stem=%r lang=%r, y no hay alternativa en ese idioma — se deja como esta'
			            % (len(heaac), stem, lang), LOGINFO)
			probe(force=True)
			return

		xbmc.Player().setAudioStream(int(target.get('index')))
		control.log('[ luc_kodi ] trailer_audio: %s (idx %s) -> %s (idx %s)'
		            % (current.get('name'), current.get('index'),
		               target.get('name'), target.get('index')), LOGINFO)
	except Exception:
		log_utils.error()


def clear_mark():
	try:
		control.homeWindow.clearProperty(MARK)
	except Exception:
		pass
