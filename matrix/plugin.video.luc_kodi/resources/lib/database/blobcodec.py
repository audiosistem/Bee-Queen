# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — blobcodec.py (v1.0.91)

	Formato de las caches de fuentes (providers.db: cache y rel_src).

	Hasta la 1.0.90 se guardaba repr() y se leia con ast.literal_eval(). Con
	150 fuentes tipicas: 79,6 KB por fila y 7,9 ms por lectura, y ademas
	literal_eval va serializado con un candado (v1.0.54, Python 3.13), asi que
	los scrapers que leian su cache en paralelo hacian cola. Ahora:
	JSON compacto + zlib, guardado como BLOB con una marca delante: 9,5 KB por
	fila (8,4 veces menos) y 0,29 ms por lectura (27 veces mas rapido), sin
	candado.

	Compatibilidad: las filas viejas son TEXTO y se siguen leyendo con el
	literal_eval de siempre hasta que caducan solas por su TTL. Si un objeto
	no se puede pasar a JSON (tuplas anidadas se vuelven listas, pero un set
	o un objeto no), se guarda como antes, con repr().
"""
import json
import zlib

MAGIC = b'LZ1'


def pack(obj):
	try:
		return MAGIC + zlib.compress(json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode('utf-8'), 6)
	except (TypeError, ValueError):
		return repr(obj)


def unpack(value, legacy):
	"""legacy: el literal_eval que use el llamador para las filas viejas."""
	if isinstance(value, memoryview):
		value = bytes(value)
	if isinstance(value, (bytes, bytearray)):
		if value[:3] == MAGIC:
			return json.loads(zlib.decompress(bytes(value[3:])).decode('utf-8'))
		value = bytes(value).decode('utf-8', 'replace')
	return legacy(value)


def is_empty_marker(value):
	return value == '[]'
