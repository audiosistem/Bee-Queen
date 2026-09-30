# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — binge.py (v1.0.90)

	Continuidad de fuente entre episodios, inspirada en find_best_stream_index
	de TMDb Movies y adaptada a luc_kodi.

	Al reproducir un episodio se guarda la HUELLA de la fuente elegida
	(calidad, rango dinamico, codec, origen, release group, scraper, debrid e
	idiomas de audio). Cuando el siguiente episodio se lanza desde el dialogo
	de siguiente episodio (luc_kodi.next_ep_direct), la lista de autoplay se
	reordena para que salga primero lo que mas se parece: un REMUX HDR en
	castellano sigue siendo REMUX HDR en castellano, en vez de saltar a un
	WEB SDR en ingles porque puntuaba unas decimas mas.

	Diferencias con TMDb Movies:
	  - No hay peso para "cacheado": en luc_kodi todo lo que se muestra lo es.
	  - Se anade el idioma de audio (el diferenciador hispano del addon).
	  - Nunca bloquea: si nada se parece, queda el orden normal. Un SDR
	    prefiere SDR con mucha fuerza, pero si solo hay HDR, se reproduce HDR.
	  - La ordenacion es estable: entre fuentes igual de parecidas manda el
	    orden que ya habian decidido el ranker y la puntuacion de siempre.
"""

import re
from json import dumps as jsdumps, loads as jsloads
from time import time

from resources.lib.modules import control
from resources.lib.modules import log_utils

PROP = 'luc_kodi.binge.fingerprint'
MAX_AGE = 12 * 3600  # una huella de hace mas de 12 h ya no describe "lo que se estaba viendo"

_QV = {'4K': 4, '1080p': 3, '720p': 2, 'SCR': 1, 'SD': 1, 'CAM': 0}


def enabled():
	return control.setting('binge.continuity') != 'false'


def _text(item):
	return ' '.join(str(item.get(k) or '') for k in ('name', 'name_info', 'info')).lower()


def fingerprint(item):
	t = _text(item)
	if re.search(r'dolby[\s._-]?vision|\bdovi\b|\bdv\b', t): hdr = 'dv'
	elif re.search(r'hdr10\+?|\bhdr\b|\bhlg\b', t): hdr = 'hdr'
	else: hdr = 'sdr'
	if re.search(r'\bav1\b', t): codec = 'av1'
	elif re.search(r'x265|h[\s.]?265|hevc', t): codec = 'hevc'
	elif re.search(r'x264|h[\s.]?264|\bavc\b', t): codec = 'avc'
	else: codec = ''
	if 'remux' in t: origin = 'remux'
	elif re.search(r'blu[\s.-]?ray|bdrip|brrip', t): origin = 'bluray'
	elif re.search(r'web[\s.-]?dl|webrip|\bweb\b', t): origin = 'web'
	elif 'hdtv' in t: origin = 'hdtv'
	else: origin = ''
	try:
		from resources.lib.modules.source_utils import release_group
		group = release_group(item.get('name') or '')
	except Exception:
		group = ''
	try:
		from resources.lib.modules import audio_langs
		langs = [c for c in audio_langs.for_item(item) if c != 'MULTI']
	except Exception:
		langs = []
	return {'quality': item.get('quality') or '', 'hdr': hdr, 'codec': codec, 'origin': origin,
			'group': group, 'provider': (item.get('provider') or '').lower(),
			'debrid': (item.get('debrid') or '').lower(), 'langs': langs}


def remember(item, imdb='', tmdb='', season=None, episode=None):
	"""Guarda la huella de la fuente que se va a reproducir (solo episodios)."""
	try:
		if season in (None, '', 'None') or episode in (None, '', 'None') or not enabled():
			return
		fp = fingerprint(item)
		fp.update({'imdb': str(imdb or ''), 'tmdb': str(tmdb or ''), 'season': int(season),
				   'episode': int(episode), 'ts': int(time())})
		control.homeWindow.setProperty(PROP, jsdumps(fp))
	except Exception:
		log_utils.error()


def _stored(imdb, tmdb):
	try:
		raw = control.homeWindow.getProperty(PROP)
		if not raw: return None
		fp = jsloads(raw)
		if int(time()) - int(fp.get('ts', 0)) > MAX_AGE: return None
		same = (tmdb and fp.get('tmdb') == str(tmdb)) or (imdb and fp.get('imdb') == str(imdb))
		return fp if same else None
	except Exception:
		return None


def score(prev, cand):
	s = 0
	if prev['hdr'] == cand['hdr']: s += 6000
	elif prev['hdr'] == 'sdr': s -= 20000  # quien veia SDR (tele o aparato sin HDR) se queda en SDR
	pq, cq = _QV.get(prev['quality'], 0), _QV.get(cand['quality'], 0)
	if pq == cq: s += 5000
	elif cq < pq: s += 2000 + cq
	if prev['langs'] and cand['langs']:
		common = set(prev['langs']) & set(cand['langs'])
		if common:
			s += 4000
			if cand['langs'][0] == prev['langs'][0]: s += 500
	if prev['provider'] and prev['provider'] == cand['provider']: s += 2000
	if prev['debrid'] and prev['debrid'] == cand['debrid']: s += 1000
	if prev['group'] and prev['group'] == cand['group']: s += 1500
	if prev['codec'] and prev['codec'] == cand['codec']: s += 1000
	if prev['origin'] and prev['origin'] == cand['origin']: s += 500
	return s


def reorder(items, imdb='', tmdb=''):
	"""Reordena para autoplay del siguiente episodio. Devuelve la lista tal
	cual si no aplica (desactivado, no viene del dialogo, otra serie...)."""
	try:
		if not items or not enabled(): return items
		if control.homeWindow.getProperty('luc_kodi.next_ep_direct') != 'true': return items
		prev = _stored(imdb, tmdb)
		if not prev: return items
		scored = [(score(prev, fingerprint(it)), n, it) for n, it in enumerate(items)]
		scored.sort(key=lambda x: (-x[0], x[1]))
		out = [x[2] for x in scored]
		top = fingerprint(out[0])
		log_utils.log('[ luc_kodi ] binge: previous %s/%s/%s/%s/%s/%s -> first now %s/%s/%s/%s/%s/%s'
					  % (prev['quality'], prev['hdr'], prev['codec'], prev['group'] or '-', ','.join(prev['langs']) or '-', prev['provider'] or '-',
						 top['quality'], top['hdr'], top['codec'], top['group'] or '-', ','.join(top['langs']) or '-', top['provider'] or '-'),
					  level=log_utils.LOGINFO)
		return out
	except Exception:
		log_utils.error()
		return items
