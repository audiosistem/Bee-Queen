# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — network_audit.py (v1.0.94)

	AUDITORIA DE TV SHOWS > NETWORKS: QUE CADENAS MERECEN ESTAR.

	La lista curada de get_networks() tenia mas de cien entradas heredadas (29 desde la 1.0.94).
	Muchas son cadenas cerradas o renombradas (The WB, Spike, ABC Family, DC
	Universe, Epix, CBS All Access...) o de nicho, y abrir una de ellas lleva
	a una rejilla con cuatro series de hace quince anos o a ninguna. Antes de
	recortar, se mide. Por cada cadena se pregunta a TMDb con la clave del
	propio addon:

	  total      series de la cadena (discover with_networks)
	  activas    series con algun episodio emitido en los ultimos 2 anos
	             (air_date.gte): lo que la cadena sigue produciendo
	  conocidas  de esas activas, las que tienen al menos 50 votos en TMDb
	             (vote_count.gte). Es el mejor indicador de "serie disponible":
	             lo que tiene publico es lo que esta indexado en los trackers
	             y cacheado en los debrid; lo de 3 votos casi nunca da fuentes
	  nombre     el nombre que TMDb da al id, para cazar ids equivocados

	Ademas se buscan los ids de plataformas que hoy NO estan en la lista
	(en su dia Paramount+, Max, MGM+, AMC+, Movistar Plus+, Atresplayer; hoy
	Crunchyroll)
	a partir de series ancla: se busca la serie, se leen sus 'networks' y se
	mide cada una igual que las demas. Asi los ids nuevos salen de TMDb y no
	de la memoria de nadie.

	v1.0.96 — Tambien mide las PLATAFORMAS de streaming (la tabla curada que
	comparten Movies > Streaming y TV Shows > Streaming), con los mismos filtros
	que usan esos menus:
	  tv listed   series que TV Shows > Streaming muestra (50 votos o mas)
	  tv active   de esas, las que han emitido algo en los ultimos 2 anos
	  tv total    todas las series que TMDb/JustWatch situan en la plataforma
	  movies      peliculas que Movies > Streaming muestra (100 votos o mas)
	  nombre      el que TMDb da al id en esa region, para cazar ids equivocados
	              o plataformas que no existen en la region pedida

	El informe se ve en pantalla, se guarda en addon_data/network_audit.txt y
	va entero al kodi.log. Nunca incluye la clave ni URLs con ella.
"""

import os
import time
from datetime import date, timedelta
from threading import Thread, Lock

from resources.lib.modules import control
from resources.lib.modules import log_utils

_ACTIVE_DAYS = 730
_KNOWN_VOTES = 50
_WORKERS = 8
# Suelos de voto de los menus de streaming (tvshows.py / movies.py). Si se
# cambian alli, cambiarlos aqui para que el test mida lo mismo que se ve.
_TV_LISTED_VOTES = 50
_MOVIE_LISTED_VOTES = 100
# Por debajo de una pagina de la rejilla (20) la plataforma se queda corta.
_STREAM_WEAK = 20

# (etiqueta, titulo de la serie ancla, ano de estreno)
_ANCHORS = (
	('Paramount+', 'Landman', 2024),
	('Paramount+', 'Tulsa King', 2022),
	('Max / HBO Max', 'The Pitt', 2025),
	('Max / HBO Max', 'Peacemaker', 2022),
	('MGM+', 'From', 2022),
	('MGM+', 'Hotel Cocaine', 2024),
	('Apple TV', 'Slow Horses', 2022),
)
# Candidatas con id ya comprobado (tmdb.org/network/1112 es Crunchyroll)
_DIRECT = (('Crunchyroll', '1112'),)


def _key():
	from resources.lib.indexers.tmdb import TVshows
	return TVshows().API_key


def _get(path, params, key):
	"""GET a TMDb. Devuelve dict o None. Nunca registra la URL (lleva la clave)."""
	from resources.lib.indexers.tmdb import session, base_link
	query = dict(params or {})
	query['api_key'] = key
	for _attempt in range(3):
		try:
			resp = session.get(base_link + path, params=query, timeout=15)
		except Exception:
			time.sleep(1)
			continue
		if resp.status_code == 200:
			try: return resp.json()
			except Exception: return None
		if resp.status_code == 429:
			try: wait = int(resp.headers.get('Retry-After', '2'))
			except Exception: wait = 2
			time.sleep(min(wait, 10) + 0.5)
			continue
		return None
	return None


def _norm(text):
	out = ''.join(ch.lower() if ch.isalnum() else ' ' for ch in (text or ''))
	stop = {'channel', 'network', 'tv', 'the', 'plus', 'us', 'uk', 'au', 'ca'}
	# los digitos sueltos cuentan: 'Channel 4' y 'Channel 5' solo se distinguen por ellos
	return set(w for w in out.split() if (len(w) >= 2 or w.isdigit()) and w not in stop)


def _same(label, tmdb_name):
	"""Nombre nuestro y nombre de TMDb comparten alguna palabra. Solo marca
	sospecha: renombres legitimos (Amazon -> Prime Video) salen marcados y se
	revisan a ojo, que es para lo que esta la columna."""
	a, b = _norm(label), _norm(tmdb_name)
	if not a or not b: return True
	if a & b: return True
	# 'ITV' e 'ITV1': el mismo canal con el numero pegado
	return any(x.startswith(y) or y.startswith(x) for x in a for y in b if min(len(x), len(y)) >= 3)


def measure(nid, key, since):
	"""Mide una cadena (nid puede ser 'a|b'). Devuelve dict."""
	first = str(nid).split('|')[0]
	row = {'id': str(nid), 'tmdb_name': '', 'country': '', 'total': -1,
	       'active': -1, 'known': -1, 'top': []}
	det = _get('network/%s' % first, {}, key)
	if isinstance(det, dict):
		row['tmdb_name'] = det.get('name') or ''
		row['country'] = det.get('origin_country') or ''
	base = {'with_networks': str(nid), 'sort_by': 'popularity.desc', 'include_adult': 'false'}
	d = _get('discover/tv', base, key)
	if isinstance(d, dict): row['total'] = int(d.get('total_results') or 0)
	q = dict(base); q['air_date.gte'] = since
	d = _get('discover/tv', q, key)
	if isinstance(d, dict): row['active'] = int(d.get('total_results') or 0)
	q['vote_count.gte'] = _KNOWN_VOTES
	d = _get('discover/tv', q, key)
	if isinstance(d, dict):
		row['known'] = int(d.get('total_results') or 0)
		row['top'] = [r.get('name') or r.get('original_name') or '' for r in (d.get('results') or [])[:3]]
	return row


def provider_names(regions, key):
	"""{(region, id): nombre} de TMDb para series y peliculas, una peticion por
	region y tipo. Un id que falta en su region es un id equivocado o una
	plataforma que alli no existe."""
	names = {}
	for region in regions:
		for kind in ('tv', 'movie'):
			d = _get('watch/providers/%s' % kind, {'watch_region': region, 'language': 'en-US'}, key)
			for p in ((d or {}).get('results') or []):
				try: names.setdefault((region, int(p.get('provider_id'))), p.get('provider_name') or '')
				except Exception: pass
	return names


def measure_platform(pid, region, key, since):
	"""Mide una plataforma (pid puede ser 'a|b', TMDb lo trata como O)."""
	row = {'id': str(pid), 'region': region, 'tmdb_name': '', 'tv_total': -1, 'tv_listed': -1,
	       'tv_active': -1, 'movies': -1, 'top': []}
	base = {'with_watch_providers': str(pid), 'watch_region': region, 'sort_by': 'popularity.desc',
	        'include_adult': 'false', 'include_null_first_air_dates': 'false'}
	d = _get('discover/tv', base, key)
	if isinstance(d, dict): row['tv_total'] = int(d.get('total_results') or 0)
	q = dict(base); q['vote_count.gte'] = _TV_LISTED_VOTES
	d = _get('discover/tv', q, key)
	if isinstance(d, dict):
		row['tv_listed'] = int(d.get('total_results') or 0)
		row['top'] = [r.get('name') or r.get('original_name') or '' for r in (d.get('results') or [])[:3]]
	q['air_date.gte'] = since
	d = _get('discover/tv', q, key)
	if isinstance(d, dict): row['tv_active'] = int(d.get('total_results') or 0)
	m = {'with_watch_providers': str(pid), 'watch_region': region, 'region': region, 'sort_by': 'popularity.desc',
	     'include_adult': 'false', 'vote_count.gte': _MOVIE_LISTED_VOTES}
	d = _get('discover/movie', m, key)
	if isinstance(d, dict): row['movies'] = int(d.get('total_results') or 0)
	return row


def _same_platform(label, tmdb_name):
	"""Como _same(), y ademas acepta el mismo nombre con las palabras en otro
	orden ('OnDemandKorea' / 'KoreaOnDemand')."""
	if _same(label, tmdb_name): return True
	letters = lambda t: sorted(ch for ch in (t or '').lower() if ch.isalnum())
	return letters(label) == letters(tmdb_name)


def platform_flags(label, row, film_only):
	if row['tv_total'] < 0 and row['movies'] < 0: return ['NO DATA']
	out = []
	if not row['tmdb_name']: out.append('NOT IN %s' % row['region'])
	elif not _same_platform(label, row['tmdb_name']): out.append('ID?')
	if not film_only:
		if row['tv_listed'] == 0: out.append('TV EMPTY')
		elif 0 < row['tv_listed'] < _STREAM_WEAK: out.append('TV WEAK')
	if row['movies'] == 0: out.append('MOVIES EMPTY')
	elif 0 < row['movies'] < _STREAM_WEAK: out.append('MOVIES WEAK')
	return out


def discover_candidates(key, current_ids):
	"""Ids de cadena sacados de las series ancla. [(etiqueta, id, nombre_tmdb)]"""
	found = {}
	for label, title, year in _ANCHORS:
		try:
			res = _get('search/tv', {'query': title, 'first_air_date_year': year}, key)
			results = (res or {}).get('results') or []
			if not results: continue
			show = _get('tv/%s' % results[0].get('id'), {}, key) or {}
			for net in show.get('networks') or []:
				nid = str(net.get('id'))
				if nid and nid not in current_ids and nid not in found:
					found[nid] = (label + ' (via %s)' % title, nid, net.get('name') or '')
		except Exception:
			log_utils.error()
	for label, nid in _DIRECT:
		if nid not in current_ids and nid not in found:
			found[nid] = (label, nid, '')
	return list(found.values())


def score(row):
	"""Orden del informe: primero lo que tiene series conocidas en activo."""
	return (max(row['known'], 0), max(row['active'], 0), max(row['total'], 0))


def flags(label, row):
	out = []
	if row['total'] < 0: out.append('NO DATA')
	elif row['active'] == 0: out.append('DEAD')
	elif row['known'] < 5: out.append('WEAK')
	if row['tmdb_name'] and not _same(label, row['tmdb_name']): out.append('ID?')
	return out


def run_audit(progress=None):
	"""Mide todo. progress: objeto con update(pct, msg) y cancelled(), o None.
	Devuelve (filas_actuales, filas_candidatas); cada fila = (etiqueta, row)."""
	from resources.lib.indexers.tmdb import TVshows, Movies, WATCHPROVIDERS_FILM_ONLY
	key = _key()
	since = (date.today() - timedelta(days=_ACTIVE_DAYS)).isoformat()
	current = [(name, str(nid)) for name, nid, _logo in TVshows().get_networks()]
	current_ids = set()
	for _n, nid in current:
		current_ids.update(nid.split('|'))
	if progress: progress.update(2, 'Looking up platforms not in the list...')
	cands = discover_candidates(key, current_ids)
	platforms = [(name, str(pid), region or 'US') for name, pid, region in Movies().watchproviders_curated()]
	if progress: progress.update(4, 'Reading platform names from TMDb...')
	pnames = provider_names(sorted(set(r for _n, _p, r in platforms)), key)
	jobs = [('cur', name, nid) for name, nid in current] + [('cand', lab, nid) for lab, nid, _nm in cands] \
		+ [('stream', name, pid, region) for name, pid, region in platforms]
	results = {}
	lock = Lock()
	pos = [0]
	stop = [False]

	def worker():
		while True:
			with lock:
				if stop[0] or pos[0] >= len(jobs): return
				job = jobs[pos[0]]
				pos[0] += 1
			if job[0] == 'stream': row = measure_platform(job[2], job[3], key, since)
			else: row = measure(job[2], key, since)
			with lock:
				results[(job[0], job[2])] = row

	threads = [Thread(target=worker) for _i in range(_WORKERS)]
	for t in threads: t.start()
	while any(t.is_alive() for t in threads):
		if progress:
			if progress.cancelled():
				with lock: stop[0] = True
			with lock: done = len(results)
			progress.update(5 + int(done * 95.0 / max(len(jobs), 1)), '%d / %d networks and platforms' % (done, len(jobs)))
		time.sleep(0.3)
	for t in threads: t.join()
	cur_rows = [(name, results[('cur', nid)]) for name, nid in current if ('cur', nid) in results]
	cand_rows = [(lab, results[('cand', nid)]) for lab, nid, _nm in cands if ('cand', nid) in results]
	stream_rows = []
	for name, pid, region in platforms:
		row = results.get(('stream', pid))
		if row is None: continue
		for part in pid.split('|'):
			try: nm = pnames.get((region, int(part)), '')
			except Exception: nm = ''
			if nm:
				row['tmdb_name'] = nm
				break
		stream_rows.append((name, row, name in WATCHPROVIDERS_FILM_ONLY))
	return cur_rows, cand_rows, since, stream_rows


def format_report(cur_rows, cand_rows, since, plain=False, stream_rows=None):
	lines = []
	B = (lambda s: s) if plain else (lambda s: '[B]%s[/B]' % s)
	lines.append(B('TV Shows > Networks — audit %s' % date.today().isoformat()))
	lines.append('active = series with an episode aired since %s   known = active series with %d+ votes on TMDb'
	             % (since, _KNOWN_VOTES))
	lines.append('')
	head = '%-4s %-22s %-11s %-26s %6s %6s %6s  %-12s %s' % ('#', 'network', 'id', 'TMDb name', 'total', 'active', 'known', 'flags', 'top active series')
	for title, rows in (('IN THE LIST NOW (%d)' % len(cur_rows), cur_rows),
	                    ('NOT IN THE LIST — candidates (%d)' % len(cand_rows), cand_rows)):
		lines.append(B(title))
		if plain: lines.append(head)
		for i, (label, row) in enumerate(sorted(rows, key=lambda r: score(r[1]), reverse=True), 1):
			name = '%s %s' % (row['tmdb_name'], '(%s)' % row['country'] if row['country'] else '')
			fl = ','.join(flags(label, row))
			top = ' / '.join(row['top'])
			if plain:
				lines.append('%-4d %-22s %-11s %-26s %6d %6d %6d  %-12s %s' % (
					i, label[:22], row['id'][:11], name.strip()[:26], row['total'], row['active'], row['known'],
					fl, top[:70]))
			else:
				# El visor usa letra proporcional: columnas alineadas saldrian
				# torcidas, asi que en pantalla va una linea legible por cadena.
				tag = ('  [COLOR fffdb515]%s[/COLOR]' % fl) if fl else ''
				lines.append('%d. [B]%s[/B]  (TMDb: %s, id %s)  known %d · active %d · total %d%s%s' % (
					i, label, name.strip() or '?', row['id'], row['known'], row['active'], row['total'], tag,
					('[CR]      ' + top) if top else ''))
		lines.append('')
	if stream_rows:
		lines.append(B('Streaming platforms — Movies > Streaming and TV Shows > Streaming (%d)' % len(stream_rows)))
		lines.append('tv = series shown in TV Shows > Streaming (%d+ votes)   active = of those, aired since %s'
		             % (_TV_LISTED_VOTES, since))
		lines.append('total = every series TMDb/JustWatch places on the platform   movies = movies shown in Movies > Streaming (%d+ votes)'
		             % _MOVIE_LISTED_VOTES)
		shead = '%-4s %-20s %-10s %-3s %-24s %6s %6s %6s %6s  %-22s %s' % ('#', 'platform', 'id', 'reg', 'TMDb name', 'tv', 'active', 'total', 'movies', 'flags', 'top series')
		if plain: lines.append(shead)
		srows = sorted(stream_rows, key=lambda r: (max(r[1]['tv_listed'], 0), max(r[1]['movies'], 0)), reverse=True)
		for i, (label, row, film_only) in enumerate(srows, 1):
			fl = ','.join(platform_flags(label, row, film_only))
			top = ' / '.join(row['top'])
			if plain:
				lines.append('%-4d %-20s %-10s %-3s %-24s %6s %6d %6d %6d  %-22s %s' % (
					i, label[:20], row['id'][:10], row['region'], (row['tmdb_name'] or '?')[:24],
					'-' if film_only else str(row['tv_listed']), row['tv_active'], row['tv_total'], row['movies'], fl,
					'' if film_only else top[:70]))
			else:
				tag = ('  [COLOR fffdb515]%s[/COLOR]' % fl) if fl else ''
				tv = 'movies only' if film_only else 'tv %d · active %d · total %d' % (row['tv_listed'], row['tv_active'], row['tv_total'])
				lines.append('%d. [B]%s[/B]  (TMDb: %s, id %s, %s)  %s · movies %d%s%s' % (
					i, label, row['tmdb_name'] or '?', row['id'], row['region'], tv, row['movies'], tag,
					('[CR]      ' + top) if (top and not film_only) else ''))
		lines.append('')
	dead = [l for l, r in cur_rows if 'DEAD' in flags(l, r)]
	weak = [l for l, r in cur_rows if 'WEAK' in flags(l, r)]
	lines.append(B('Summary'))
	lines.append('%d networks in the list: %d with no series aired in 2 years, %d with fewer than 5 known active series.'
	             % (len(cur_rows), len(dead), len(weak)))
	if stream_rows:
		sweak = [l for l, r, f in stream_rows if any(x.startswith('TV ') for x in platform_flags(l, r, f))]
		sid = [l for l, r, f in stream_rows if any(x == 'ID?' or x.startswith('NOT IN') for x in platform_flags(l, r, f))]
		lines.append('%d streaming platforms: %d with fewer than %d series in TV Shows > Streaming, %d with a wrong or missing ID.'
		             % (len(stream_rows), len(sweak), _STREAM_WEAK, len(sid)))
	return lines


def _save(text):
	try:
		path = os.path.join(control.dataPath, 'network_audit.txt')
		with open(path, 'w', encoding='utf-8') as fh:
			fh.write(text)
		return path
	except Exception:
		log_utils.error()
		return ''


class _Progress(object):
	def __init__(self):
		self.dlg = control.progressDialog
		self.dlg.create('luc_kodi — Networks and streaming audit', 'Starting...')
	def update(self, pct, msg):
		try: self.dlg.update(int(pct), msg)
		except Exception: pass
	def cancelled(self):
		try: return self.dlg.iscanceled()
		except Exception: return False
	def close(self):
		try: self.dlg.close()
		except Exception: pass


def show():
	"""Tools > Test networks and streaming platforms."""
	progress = _Progress()
	try:
		cur_rows, cand_rows, since, stream_rows = run_audit(progress)
	except Exception:
		log_utils.error()
		progress.close()
		control.notification(message='Networks and streaming audit failed — see the log')
		return
	progress.close()
	plain = '\n'.join(format_report(cur_rows, cand_rows, since, plain=True, stream_rows=stream_rows))
	path = _save(plain)
	log_utils.log('[ plugin.video.luc_kodi ]  Networks and streaming audit\n' + plain, __name__, log_utils.LOGINFO)
	text = '[CR]'.join(format_report(cur_rows, cand_rows, since, stream_rows=stream_rows))
	if path: text += '[CR][CR]Saved to %s and written to kodi.log.' % path
	try:
		from resources.lib.windows.textviewer import TextViewerXML
		viewer = TextViewerXML('textviewer.xml', control.addonPath('plugin.video.luc_kodi'),
		                       heading='luc_kodi — Networks and streaming audit', text=text)
		viewer.run()
		del viewer
	except Exception:
		log_utils.error()
		control.dialog.textviewer('luc_kodi — Networks and streaming audit', plain, usemono=True)
