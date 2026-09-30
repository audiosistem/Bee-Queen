# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — Audio languages, declared (v1.0.89)

	Nivel 1 de la sonda de audio: que idiomas DECLARA cada fuente, leido de lo
	que ya llega con el indexado, sin ninguna peticion de red.

	Tres procedencias, que se suman:

	1. El nombre del release, ya sin el titulo (name_info). Palabras completas
	   ('castellano', 'latino', 'french') y codigos de tres letras ('spa',
	   'ita'). Los codigos que tambien son palabras corrientes ('fin', 'per',
	   'tam', 'nor'...) solo cuentan si van pegados a otro idioma o a una marca
	   de audio, porque sueltos dan falsos positivos.

	2. La pista que dejan los scrapers de tipo Stremio (lang_hint): las
	   banderas de Torrentio, Comet, MediaFusion y Peerflix, y las lineas con
	   el globo o la cabeza que habla. Hasta la 1.0.88 esa linea se leia para
	   sacar seeders y tamano y el resto se tiraba.

	3. Lo que el servicio ya sabe del fichero: Easynews manda `alangs` con
	   los idiomas de audio reales del contenedor. Se recogia en el item y no
	   lo miraba nadie.

	Es DECLARADO: dice lo que el indexado afirma, no lo que hay dentro. Lo que
	hay dentro lo dice audio_probe.py, y cuando existe tiene prioridad.

	Codigos de salida, pensados para la fila de la lista (cortos, mayusculas,
	solo Latin-1 porque el plugin no trae fuentes propias):
		CAST  espanol de Espana          LAT   espanol latinoamericano
		ES    espanol sin variante clara PT-BR portugues de Brasil
		FR-CA frances de Quebec          MULTI hay varias pistas y el nombre no
		                                       dice cuales
		EN, FR, DE, IT... ISO 639-1 en mayusculas

	'ES' no es un fallo: es lo honesto cuando el nombre dice 'spanish' o la
	pista dice 'spa' y nada mas. Inventar la variante seria mentir.
"""

import re

# ── Idioma en ISO 639-2 (B y T) → codigo de fila ──────────────────────────
ISO3 = {
	'spa': 'ES', 'esp': 'ES', 'eng': 'EN', 'fre': 'FR', 'fra': 'FR', 'ger': 'DE', 'deu': 'DE',
	'ita': 'IT', 'por': 'PT', 'rus': 'RU', 'ukr': 'UK', 'jpn': 'JA', 'kor': 'KO', 'chi': 'ZH',
	'zho': 'ZH', 'hin': 'HI', 'tam': 'TA', 'tel': 'TE', 'pol': 'PL', 'dut': 'NL', 'nld': 'NL',
	'tur': 'TR', 'ara': 'AR', 'gre': 'EL', 'ell': 'EL', 'heb': 'HE', 'hun': 'HU', 'cze': 'CS',
	'ces': 'CS', 'rum': 'RO', 'ron': 'RO', 'swe': 'SV', 'nor': 'NO', 'nob': 'NO', 'nno': 'NO',
	'dan': 'DA', 'fin': 'FI', 'tha': 'TH', 'vie': 'VI', 'bul': 'BG', 'hrv': 'HR', 'srp': 'SR',
	'slk': 'SK', 'slo': 'SK', 'slv': 'SL', 'lit': 'LT', 'lav': 'LV', 'est': 'ET', 'per': 'FA',
	'fas': 'FA', 'ind': 'ID', 'may': 'MS', 'msa': 'MS', 'cat': 'CA', 'baq': 'EU', 'eus': 'EU',
	'glg': 'GL', 'ice': 'IS', 'isl': 'IS', 'kan': 'KN', 'mal': 'ML', 'mar': 'MR', 'ben': 'BN',
	'urd': 'UR', 'fil': 'TL', 'tgl': 'TL'}

# ISO 639-1 → codigo de fila (Easynews y las etiquetas BCP-47 los traen asi).
ISO2 = dict((v.lower(), v) for v in ISO3.values())

# Palabras completas del nombre. Nunca dan falso positivo con el titulo
# delante porque name_info ya viene sin el.
WORDS = {
	'castellano': 'CAST', 'castilian': 'CAST', 'truespanish': 'CAST', 'espanol': 'ES',
	'spanish': 'ES', 'latino': 'LAT', 'latin': 'LAT', 'latinoamericano': 'LAT',
	'english': 'EN', 'french': 'FR', 'truefrench': 'FR', 'vff': 'FR', 'vfi': 'FR', 'vf2': 'FR',
	'vfq': 'FR-CA', 'quebecois': 'FR-CA', 'german': 'DE', 'deutsch': 'DE', 'italian': 'IT',
	'italiano': 'IT', 'portuguese': 'PT', 'dublado': 'PT-BR', 'ptbr': 'PT-BR', 'brazilian': 'PT-BR',
	'russian': 'RU', 'ukrainian': 'UK', 'japanese': 'JA', 'korean': 'KO', 'chinese': 'ZH',
	'mandarin': 'ZH', 'cantonese': 'ZH', 'hindi': 'HI', 'tamil': 'TA', 'telugu': 'TE',
	'polish': 'PL', 'pldub': 'PL', 'dutch': 'NL', 'turkish': 'TR', 'arabic': 'AR', 'greek': 'EL',
	'hebrew': 'HE', 'hungarian': 'HU', 'czech': 'CS', 'romanian': 'RO', 'swedish': 'SV',
	'norwegian': 'NO', 'danish': 'DA', 'finnish': 'FI', 'thai': 'TH', 'vietnamese': 'VI',
	'bulgarian': 'BG', 'persian': 'FA', 'catalan': 'CA', 'catala': 'CA'}

# Codigos de tres letras que no se confunden con palabras corrientes.
STRONG3 = {
	'spa': 'ES', 'esp': 'ES', 'lat': 'LAT', 'eng': 'EN', 'ita': 'IT', 'ger': 'DE', 'deu': 'DE',
	'fre': 'FR', 'fra': 'FR', 'rus': 'RU', 'ukr': 'UK', 'jpn': 'JA', 'kor': 'KO', 'chi': 'ZH',
	'chs': 'ZH', 'cht': 'ZH', 'zho': 'ZH', 'hin': 'HI', 'pol': 'PL', 'por': 'PT', 'dut': 'NL',
	'nld': 'NL', 'tur': 'TR', 'ara': 'AR', 'heb': 'HE'}

# Codigos que tambien son palabras ('fin', 'per', 'nor', 'dan'...). Solo
# cuentan junto a otro idioma o a una marca de audio.
WEAK3 = {
	'tam': 'TA', 'tel': 'TE', 'nor': 'NO', 'fin': 'FI', 'per': 'FA', 'dan': 'DA', 'gre': 'EL',
	'ell': 'EL', 'cze': 'CS', 'ces': 'CS', 'hun': 'HU', 'bul': 'BG', 'rum': 'RO', 'ron': 'RO',
	'swe': 'SV', 'tha': 'TH', 'vie': 'VI', 'cat': 'CA'}

# Marcas que declaran varias pistas sin decir cuales.
MULTI_TOKENS = ('multi', 'dual', 'multiaudio', 'dualaudio')
# Un idioma justo antes de una de estas es de SUBTITULOS, no de audio.
SUB_TOKENS = ('sub', 'subs', 'subbed', 'subtitle', 'subtitles', 'subtitulado', 'subtitulos',
	'subt', 'srt', 'hardsub', 'softsub')
# Lo que convierte en contexto de audio un codigo debil vecino.
AUDIO_CONTEXT = ('audio', 'dub', 'dubbed', 'multi', 'dual', 'ac3', 'aac', 'dts', 'dd5', 'eac3')

# Banderas → codigo. Torrentio pone la de Espana para 'spanish' (el nombre
# no distingue variante) y la de Mexico para 'latino'.
FLAGS = {
	'\U0001F1EA\U0001F1F8': 'ES', '\U0001F1F2\U0001F1FD': 'LAT', '\U0001F1E6\U0001F1F7': 'LAT',
	'\U0001F1E8\U0001F1F4': 'LAT', '\U0001F1F5\U0001F1EA': 'LAT', '\U0001F1E8\U0001F1F1': 'LAT',
	'\U0001F1EC\U0001F1E7': 'EN', '\U0001F1FA\U0001F1F8': 'EN', '\U0001F1EB\U0001F1F7': 'FR',
	'\U0001F1E9\U0001F1EA': 'DE', '\U0001F1EE\U0001F1F9': 'IT', '\U0001F1F5\U0001F1F9': 'PT',
	'\U0001F1E7\U0001F1F7': 'PT-BR', '\U0001F1F7\U0001F1FA': 'RU', '\U0001F1FA\U0001F1E6': 'UK',
	'\U0001F1EF\U0001F1F5': 'JA', '\U0001F1F0\U0001F1F7': 'KO', '\U0001F1E8\U0001F1F3': 'ZH',
	'\U0001F1F9\U0001F1FC': 'ZH', '\U0001F1EE\U0001F1F3': 'HI', '\U0001F1F5\U0001F1F1': 'PL',
	'\U0001F1F3\U0001F1F1': 'NL', '\U0001F1F9\U0001F1F7': 'TR', '\U0001F1F8\U0001F1E6': 'AR',
	'\U0001F1EC\U0001F1F7': 'EL', '\U0001F1EE\U0001F1F1': 'HE', '\U0001F1ED\U0001F1FA': 'HU',
	'\U0001F1E8\U0001F1FF': 'CS', '\U0001F1F7\U0001F1F4': 'RO', '\U0001F1F8\U0001F1EA': 'SV',
	'\U0001F1F3\U0001F1F4': 'NO', '\U0001F1E9\U0001F1F0': 'DA', '\U0001F1EB\U0001F1EE': 'FI',
	'\U0001F1F9\U0001F1ED': 'TH', '\U0001F1FB\U0001F1F3': 'VI', '\U0001F1E7\U0001F1EC': 'BG',
	'\U0001F1ED\U0001F1F7': 'HR', '\U0001F1F7\U0001F1F8': 'SR', '\U0001F1F8\U0001F1F0': 'SK',
	'\U0001F1F8\U0001F1EE': 'SL', '\U0001F1F1\U0001F1F9': 'LT', '\U0001F1F1\U0001F1FB': 'LV',
	'\U0001F1EA\U0001F1EA': 'ET', '\U0001F1EE\U0001F1F7': 'FA', '\U0001F1EE\U0001F1E9': 'ID',
	'\U0001F1F2\U0001F1FE': 'MS'}
_FLAG_RE = re.compile('[\U0001F1E6-\U0001F1FF]{2}')
# Globo y cabeza que habla: las lineas de idioma de MediaFusion y AIOStreams.
_LANG_LINE_MARKS = ('\U0001F310', '\U0001F5E3')
_MULTI_PHRASE_RE = re.compile(r'\b(multi[\s\-_.]*audio|dual[\s\-_.]*audio|multi|dual)\b', re.I)

# Orden de la fila: las variantes de espanol primero (es el diferenciador
# del plugin), ingles despues, y el resto en el orden en que aparecieron.
_ORDER = ('CAST', 'LAT', 'ES', 'EN')

# Ajuste audio.langs.preferred: indice del select → codigos que lo cumplen.
# 'Spanish (any)' acepta las tres formas; 'Spanish (Spain)' no acepta un ES
# sin variante como prueba de que haya castellano, pero lo realza igual en la
# lista porque podria serlo (ver matches()).
# Etiquetas del select en strings.po: 400790 + indice.
PREFERRED_LABEL_BASE = 400790
PREFERRED = (
	(),                      # 0 None
	('CAST', 'LAT', 'ES'),   # 1 Spanish (any)
	('CAST',),               # 2 Spanish (Spain)
	('LAT',),                # 3 Spanish (Latin America)
	('EN',), ('FR', 'FR-CA'), ('DE',), ('IT',), ('PT', 'PT-BR'), ('PT-BR',),
	('RU',), ('JA',), ('KO',), ('ZH',), ('HI',), ('PL',), ('NL',), ('TR',), ('AR',))


def preferred():
	"""Codigos del idioma preferido del usuario, o () si no ha elegido."""
	try:
		from resources.lib.modules.control import setting as getSetting
		idx = int(getSetting('audio.langs.preferred') or '0')
		return PREFERRED[idx] if 0 <= idx < len(PREFERRED) else ()
	except Exception:
		return ()


def matches(code, pref):
	"""True si `code` debe realzarse para la preferencia `pref`.
	Un ES sin variante se realza cuando se pide castellano o latino: puede
	serlo, y esconderlo seria peor que marcarlo."""
	if not pref:
		return False
	if code in pref:
		return True
	return code == 'ES' and any(p in ('CAST', 'LAT') for p in pref)


def confirms(codes, pref):
	"""True si la lista de pistas REALES cumple la preferencia sin dudas.
	Aqui un ES sin variante no confirma castellano ni latino."""
	return bool(pref) and any(c in pref for c in codes)


def _add(out, code):
	if code and code not in out:
		out.append(code)


def from_name_info(name_info, strict=False):
	"""Idiomas declarados en un name_info ('.titulo.quitado.1080p.castellano.').
	strict=True para nombres que aun llevan el titulo: solo palabras que no
	aparecen en titulos (variantes de espanol y frances, marcas multi)."""
	out, multi = [], False
	if not name_info:
		return out, multi
	toks = [t for t in re.split(r'[^a-z0-9]+', str(name_info).lower()) if t]
	n = len(toks)
	for i, t in enumerate(toks):
		if t in MULTI_TOKENS:
			multi = True
			continue
		nxt = toks[i + 1] if i + 1 < n else ''
		prv = toks[i - 1] if i else ''
		if nxt in SUB_TOKENS:
			continue
		code = None
		if t in WORDS:
			code = WORDS[t]
			if strict and code not in ('CAST', 'LAT', 'FR-CA', 'PT-BR') and t not in ('truefrench', 'vff', 'vfq'):
				code = None
		elif strict:
			code = None
		elif t in STRONG3:
			code = STRONG3[t]
		elif t in WEAK3:
			ctx = any(x in WORDS or x in STRONG3 or x in WEAK3 or x in AUDIO_CONTEXT
			          for x in (prv, nxt) if x)
			if ctx:
				code = WEAK3[t]
		elif t == '419' and prv == 'es':
			code = 'LAT'
		if code:
			_add(out, code)
	# 'spanish.latino' / 'spanish.latin' es UNA pista latina, no dos.
	if 'LAT' in out and 'ES' in out and 'spanish' in toks:
		idx = toks.index('spanish')
		if idx + 1 < n and toks[idx + 1] in ('latino', 'latin', 'lat'):
			out.remove('ES')
	# 'multi.vff' / 'multi.truefrench': la marca multi habla del frances.
	return out, multi


def from_hint(text):
	"""Idiomas de la pista compacta que dejan los scrapers (banderas y lineas
	de idioma). Devuelve (codigos, multi)."""
	out, multi = [], False
	if not text:
		return out, multi
	text = str(text)
	for f in _FLAG_RE.findall(text):
		_add(out, FLAGS.get(f))
	if _MULTI_PHRASE_RE.search(text):
		multi = True
	for line in text.split('\n'):
		if any(m in line for m in _LANG_LINE_MARKS) or _FLAG_RE.search(line):
			for w in re.split(r'[^a-zA-Z]+', line):
				code = WORDS.get(w.lower())
				if code:
					_add(out, code)
	return out, multi


def compact_hint(text):
	"""Reduce el texto de un stream de Stremio a lo que le sirve a from_hint():
	banderas, la marca multi/dual y las lineas de idioma. Es lo que se guarda
	en el item (y por tanto en la cache de proveedores), asi que se guarda lo
	minimo."""
	try:
		if not text:
			return ''
		text = str(text)
		parts = _FLAG_RE.findall(text)
		m = _MULTI_PHRASE_RE.search(text)
		if m:
			parts.append(m.group(0).lower().replace(' ', '.'))
		for line in text.split('\n'):
			if any(mk in line for mk in _LANG_LINE_MARKS):
				words = [w for w in re.split(r'[^a-zA-Z]+', line) if w.lower() in WORDS]
				if words:
					parts.append('\U0001F310 ' + ' '.join(words))
		return '\n'.join(parts)[:200]
	except Exception:
		return ''


def from_codes(codes):
	"""Lista de codigos ISO (639-1, 639-2 o BCP-47) tal como los manda un
	servicio ('eng,spa', ['en', 'es-419'])."""
	out = []
	if not codes:
		return out
	if isinstance(codes, (list, tuple, set)):
		codes = ','.join(str(c) for c in codes)
	for c in re.split(r'[,;/|\s]+', str(codes).lower()):
		if not c:
			continue
		_add(out, bcp_to_code(c))
	return out


def bcp_to_code(tag):
	"""es-ES → CAST, es-419/es-MX → LAT, pt-BR → PT-BR, fr-CA → FR-CA, spa → ES."""
	t = str(tag or '').lower().replace('_', '-')
	if not t:
		return None
	base, _, region = t.partition('-')
	if base in ('es', 'spa', 'esp'):
		if region == 'es':
			return 'CAST'
		if region and region not in ('es',):
			return 'LAT'
		return 'ES'
	if base in ('pt', 'por') and region == 'br':
		return 'PT-BR'
	if base in ('fr', 'fre', 'fra') and region == 'ca':
		return 'FR-CA'
	return ISO2.get(base) or ISO3.get(base)


def ordered(codes, pref=()):
	"""Ordena para la fila: preferido primero, luego espanol, ingles y resto."""
	codes = list(codes)
	head = [c for c in codes if matches(c, pref)]
	rest = [c for c in codes if c not in head]
	rest.sort(key=lambda c: (_ORDER.index(c) if c in _ORDER else len(_ORDER), codes.index(c)))
	return head + rest


def for_item(item, extra_names=(), extra_hints=()):
	"""Idiomas declarados de una fuente. extra_names/extra_hints son los de
	sus duplicados (mismo hash, otro indexador), que filter_dupes() descarta:
	un torrent es uno solo aunque cada indexador lo nombre a su manera, asi
	que lo que declare cualquiera de ellos vale para todos."""
	out, multi = [], False
	try:
		names = []
		if item.get('name_info'):
			names.append((item.get('name_info'), False))
		elif item.get('name'):
			names.append((item.get('name'), True))
		if item.get('lang_name'):
			names.append((item.get('lang_name'), False))
		for n in extra_names or ():
			if n:
				names.append((n, False))
		for n, strict in names:
			c, m = from_name_info(n, strict=strict)
			multi = multi or m
			for x in c:
				_add(out, x)
		# v1.0.91: las banderas de los indexadores NO siempre son audio. En
		# muchos releases (YTS sobre todo) son los idiomas de los SUBTITULOS
		# que trae el torrent: 'Moana.2026.2160p.WEBRip' salia como FR · ES ·
		# EN con una unica pista de audio. Reglas:
		#   - de YTS no se acepta ninguna bandera (sus releases son una sola
		#     pista y las banderas son subtitulos);
		#   - si el NOMBRE no dice nada de idioma ni de multi-audio y la pista
		#     trae 2 o mas idiomas sin decir 'multi audio', es una lista de
		#     subtitulos y se descarta;
		#   - una bandera sola se acepta (tracker regional, release doblado).
		# Lo que lee audio_probe del propio fichero sigue mandando sobre todo.
		name_says = bool(out) or multi
		own_yts = 'yts' in str(item.get('provider') or '').lower()
		hints = [] if own_yts else [item.get('lang_hint')]
		hints += list(extra_hints or ())
		for h in hints:
			c, m = from_hint(h)
			if not name_says and not m and len(c) >= 2:
				continue
			multi = multi or m
			for x in c:
				_add(out, x)
		for x in from_codes(item.get('alangs')):
			_add(out, x)
		# Con castellano ya presente, un ES suelto es la misma pista dicha con
		# menos detalle (Torrentio pinta la bandera de Espana tambien para
		# 'castellano'). Con LATINO no: bandera de Espana y de Mexico juntas
		# son dos pistas, y 'spanish.latino' ya se resolvio en el nombre.
		if 'ES' in out and 'CAST' in out:
			out.remove('ES')
		if multi and len(out) < 2:
			_add(out, 'MULTI')
	except Exception:
		pass
	return out
