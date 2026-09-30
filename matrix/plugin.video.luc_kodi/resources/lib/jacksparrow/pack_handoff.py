# -*- coding: utf-8 -*-
"""
pack_handoff — traspaso de resultados entre sources() y sources_packs().

PROBLEMA QUE RESUELVE (v1.0.63)
--------------------------------
`modules/sources.py` lanza TRES pasadas por cada busqueda de serie y cada una
crea su PROPIA instancia del scraper con `call()`:

	sources        -> call().sources(...)          # instancia A
	seasonPacks    -> _scraper = call(); ...       # instancia B
	showPacks      -> _scraper = call(); ...       # instancia C

Los scrapers hacian el traspaso con `self._queue = queue.SimpleQueue()` creada
en `__init__`, o sea una cola distinta por instancia: lo que la instancia A
metia no lo veia nadie. `sources_packs()` esperaba `timeout + 1` segundos
contra una cola que no se iba a llenar jamas y terminaba en `queue.Empty`.
Resultado: CERO packs de temporada y de serie, mas una espera muerta de 11 s
(comet), 16 s (torz), 21 s (mediafusion) o 46 s (sootio) por pasada.

Meteor lo tenia declarado a nivel de CLASE, que si cruzaba entre instancias
pero mezclaba resultados entre titulos si habia busquedas solapadas.

COMO FUNCIONA
-------------
Almacen a nivel de modulo (compartido por todas las instancias del proceso)
indexado por una clave que incluye el proveedor y el material del episodio,
asi que dos titulos distintos nunca se pisan:

	sources():        h = pack_handoff.begin('comet', imdb, season, episode)
	                  files = self._fetch(url)
	                  pack_handoff.publish(h, files)

	sources_packs():  files = pack_handoff.wait('comet', imdb, season, episode,
	                                            timeout=self.timeout)
	                  if files is None:      # nadie publico: se busca solo
	                      files = self._fetch(url)

`wait()` NO se queda colgado si no hay nadie publicando: si la clave no esta
registrada devuelve None al momento y el scraper hace su propia peticion, que
es lo que ya hacia aiostreams (el unico que estaba bien construido).

Las entradas caducan a los `TTL` segundos y se podan en cada escritura, para
que el almacen no crezca durante una sesion larga.
"""

import threading
import time

TTL = 120          # segundos que sobrevive un resultado publicado
_MAX_ENTRIES = 64  # tope duro por si algo deja de podar


class _Slot(object):
	__slots__ = ('event', 'payload', 'created')

	def __init__(self):
		self.event = threading.Event()
		self.payload = None
		self.created = time.time()


_store = {}
_lock = threading.Lock()


def _key(provider, imdb, season, episode):
	return '%s|%s|%s|%s' % (provider, imdb or '', season or '', episode or '')


def _prune_locked():
	"""Quita lo caducado. Se llama SIEMPRE con _lock tomado."""
	now = time.time()
	dead = [k for k, s in _store.items() if now - s.created > TTL]
	for k in dead:
		_store.pop(k, None)
	if len(_store) > _MAX_ENTRIES:
		for k in sorted(_store, key=lambda k: _store[k].created)[:len(_store) - _MAX_ENTRIES]:
			_store.pop(k, None)


def begin(provider, imdb, season, episode):
	"""
	Reserva la clave ANTES de lanzar la peticion, para que las pasadas de
	packs sepan que hay alguien buscando y esperen en vez de duplicarla.
	Devuelve un handle que hay que pasar a publish().
	"""
	k = _key(provider, imdb, season, episode)
	with _lock:
		_prune_locked()
		slot = _Slot()
		_store[k] = slot
		# la poda de arriba corre ANTES de insertar; se repite despues para que
		# el tope incluya la entrada recien creada
		_prune_locked()
	return (k, slot)


def publish(handle, payload):
	"""Deja el resultado y despierta a quien estuviera esperando."""
	if not handle:
		return
	try:
		_k, slot = handle
		slot.payload = payload
		slot.event.set()
	except Exception:
		pass


def wait(provider, imdb, season, episode, timeout=10):
	"""
	Devuelve lo publicado para esa clave, o None si nadie la reservo o si
	expiro la espera. None significa "buscalo tu", nunca "no hay resultados".
	"""
	k = _key(provider, imdb, season, episode)
	with _lock:
		slot = _store.get(k)
	if slot is None:
		return None
	if time.time() - slot.created > TTL:
		with _lock:
			_store.pop(k, None)
		return None
	if not slot.event.wait(timeout):
		return None
	return slot.payload


def clear():
	"""Solo para pruebas."""
	with _lock:
		_store.clear()
