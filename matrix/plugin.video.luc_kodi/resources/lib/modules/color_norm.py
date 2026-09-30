"""
	luc_kodi Add-on

	Norma de color de la ventana de fuentes (source_results).

	Hasta la 1.0.83 cada color de esta ventana era un hexadecimal escrito a
	mano: seis para la calidad en source_results.py, otros seis repetidos en
	el marco del poster del XML, siete PNG de tarjeta y siete de barra con el
	color cocido dentro, seis para los debrid en control.py, mas el salmon de
	los tags raros y el aqua del bitrate. Veinte y pico sitios para lo que en
	realidad son dos familias de color, y ya se habian desincronizado: la
	barra de 720p era (212,165,116) mientras su tarjeta era (255,167,38), y
	la de SCR (255,87,34) frente a (183,28,28) de la tarjeta.

	Aqui no se guardan colores: se guarda UN TONO por concepto. El papel que
	juega ese tono (tinta, superficie o senal) y el fondo real sobre el que
	cae deciden lo demas. Tres condiciones, que son las tres cosas que se le
	piden a esta ventana:

	  1. LEGIBILIDAD. Toda tinta da >= 4.0 de contraste WCAG contra el fondo
	     COMPUESTO de verdad (fondo de ventana + tarjeta de calidad al 23,5%
	     + tinte del debrid segun el degradado), no contra un negro teorico.

	  2. COMODIDAD. De todos los tonos que cumplen (1) se elige el MAS
	     APAGADO, no el mas vistoso: se sube la luminosidad de uno en uno
	     hasta que pasa el suelo y ahi se para. La saturacion va con techo
	     (0.60), que es lo que quema la vista de noche: el cian 4K y el
	     ambar 720p estaban a 1.00 y el acero de Premiumize a 0.29, y ese
	     ultimo no molesta a nadie.

	  3. IDENTIFICACION. Dos colores del mismo grupo tienen que separarse un
	     minimo medible (dE76 >= 12). La norma NO corrige esto sola a base de
	     girar tonos, porque girar el cian del 4K en silencio seria cambiarle
	     el diseno a alguien sin decirselo: lo comprueba y lo denuncia, y la
	     decision es de quien mantiene la tabla.

	El verde de marca ff00fa9a queda FUERA de la norma por declaracion
	expresa: es identidad del addon, no un color funcional de esta ventana, y
	aparece en sitios que no tienen nada que ver con source_results.
"""

import colorsys


# ── Tonos base ────────────────────────────────────────────────────────────
#
# De estos hexadecimales solo se usa el TONO (el matiz). La luminosidad y la
# saturacion que traigan aqui son historicas y las recalcula la norma. Se
# conservan tal cual venian para que la identidad no cambie: el 4K sigue
# siendo cian y Real-Debrid sigue siendo vino.
QUALITY_HUES = {
	'4K':    '00BCD4',
	'1080P': '4CAF50',
	'720P':  'FFA726',
	'SD':    '607D8B',
	'SCR':   'B71C1C',
	'CAM':   'B0C4DE',
}
QUALITY_FALLBACK = '363C3D'

# Excepciones declaradas al techo de saturacion, no automaticas. SD y 4K son
# los dos unicos tonos de la tabla que caen en el mismo sector azul-cian, y
# al llevarlos los dos a la luminosidad minima que pasa el suelo se quedaban
# a dE 11,5 (por debajo del minimo de 12). En vez de girarle el tono al cian
# del 4K, que es identidad de la ventana, se le baja el croma a SD: es la
# calidad mas baja de la lista y leerse como un azul agrisado en vez de como
# un azul vivo dice lo que tiene que decir.
QUALITY_SAT_CAP = {'SD': 0.22}

DEBRID_HUES = {
	'RD':     'A43A4B',
	'PM':     '7799B4',
	'AD':     'E9B321',
	'TB':     '47A54A',
	'OC':     'FF8800',
	'ED':     'FF4444',
	'CUSTOM': 'D39886',
}

# Proveedores heredados: las ramas OC/ED de router.py siguen en el arbol pero
# no hay debrid de primera clase detras (ver la auditoria de scrapers Custom).
# Se les da color para que nada quede sin pintar, y se les exime de la
# condicion de separacion: ED es rojo puro y RD vino, y al normalizarlos los
# dos caen a dE 9,5. Separarlos obligaria a mover el tono de Real-Debrid, que
# si esta vivo, por un proveedor que no lo esta.
DEBRID_LEGACY = frozenset(('OC', 'ED'))

# Fondo de la ventana bajo la lista: black.png con el fanart encima a
# colordiffuse 80F5F5F5 y la animacion de fade parada en 25. O sea negro mas,
# como mucho, un 12,5% de un fanart claro. Se toma el peor caso (fanart
# blanco) para que el suelo de contraste valga con cualquier contenido.
#
# ATENCION al tocar source_results.xml: este numero depende de que ESE fade
# siga parado en 25 en LOS DOS juegos de skin. Hasta la 1.0.85 el juego 2160p
# lo tenia en 50 — el generador habia doblado la opacidad como si fuera una
# medida de pantalla —, con lo que el fondo real en 4K era (61,61,61) y las
# catorce comprobaciones de senal y cabecera de esta ventana incumplian su
# suelo sin que nada lo cantara. La opacidad de un fade y el porcentaje de un
# zoom no se escalan nunca; solo las coordenadas de un slide.
BACKDROP = (32, 32, 32)

# Tarjeta de calidad: PNG plano a alfa 60/255 sobre el fondo de ventana.
CARD_ALPHA = 60 / 255.0

# Tarjeta enfocada. card_focus.png es (200,200,196) y el skin lo multiplicaba
# por un colordiffuse FF696969 escrito a mano, con lo que el gris real era
# (82,82,81).
#
# v1.0.86: ese gris ya no se escribe, se calcula. Sobre (82,82,81) la norma
# tenia que subir la tinta rutinaria hasta FFC2C2C2 para llegar al suelo de
# 4.0 — un gris casi blanco, repetido en toda la linea, que es justo lo que
# molesta de noche. Un papel mas oscuro alcanza el suelo antes y deja que la
# tinta se quede donde la norma la prefiere: apagada.
#
# Cuanto mas oscuro, tampoco a ojo: se oscurece lo MINIMO que hace falta para
# que el papel nuevo sea otro papel y no el mismo un poco sucio, o sea hasta
# la misma distancia que la norma ya exigia entre dos colores de la misma
# familia (dE76 >= 12). Sale un 34%, y de ahi (54,54,53).
#
# El colordiffuse del XML sale de la misma cuenta (focus_card_diffuse), asi
# que el gris de la tarjeta y el fondo contra el que se calcula la tinta no
# pueden volver a desincronizarse: son el mismo numero.
FOCUS_TEXTURE = (200, 200, 196)
FOCUS_DIFFUSE_LEGACY = 0x69
FOCUS_CARD_LEGACY = (82, 82, 81)
FOCUS_DIM_SEPARATION = 12.0
# Aclarado del gris de foco pedido por Lucian el 19-sep-2026: +25% sobre lo
# que da la norma, porque con las filas CAM el gris calculado se confundia con
# la propia tarjeta y no se veia cual estaba enfocada.
FOCUS_LIGHTEN = 1.25

# Degradado del tinte de debrid (common/gradient-diffuse-horizontal.png con
# flipx): alfa 124/255 en el borde izquierdo cayendo a 9/255 en el derecho.
# La segunda fila arranca a la izquierda y se extiende, asi que se mide en
# los dos extremos utiles y se exige el suelo en el PEOR de los dos.
TINT_ALPHA_LEFT = 124 / 255.0
TINT_ALPHA_RIGHT = 9 / 255.0
FOCUS_TINT_SCALE = 0x40 / 255.0

# Suelos. La tinta de acento pide un pelin mas que la rutinaria para que la
# jerarquia no dependa solo del croma.
CONTRAST_INK = 4.0
CONTRAST_ACCENT = 4.5
CONTRAST_SIGNAL = 3.0
CONTRAST_SEPARATOR = 2.2
SEPARATION_MIN = 12.0

SAT_MIN, SAT_MAX = 0.35, 0.60
SURFACE_L, SURFACE_SAT_MAX = 0.46, 0.45


# ── Aritmetica de color ───────────────────────────────────────────────────

def to_rgb(hex_str):
	"""'FFA43A4B' o 'A43A4B' -> (r, g, b)."""
	h = hex_str[-6:]
	return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def to_hex(rgb, alpha='FF'):
	return '%s%02X%02X%02X' % (alpha, int(round(rgb[0])), int(round(rgb[1])), int(round(rgb[2])))


def over(bg, fg, alpha):
	"""fg con alfa sobre bg."""
	return tuple(bg[i] * (1.0 - alpha) + fg[i] * alpha for i in range(3))


def _channel(v):
	v = v / 255.0
	return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminance(rgb):
	return 0.2126 * _channel(rgb[0]) + 0.7152 * _channel(rgb[1]) + 0.0722 * _channel(rgb[2])


def contrast(a, b):
	la, lb = luminance(a), luminance(b)
	if lb > la:
		la, lb = lb, la
	return (la + 0.05) / (lb + 0.05)


def _to_lab(rgb):
	def f(t):
		return t ** (1.0 / 3.0) if t > 0.008856 else (7.787 * t) + (16.0 / 116.0)
	r, g, b = [_channel(v) for v in rgb]
	x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
	y = (0.2126 * r + 0.7152 * g + 0.0722 * b)
	z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
	fx, fy, fz = f(x), f(y), f(z)
	return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def separation(a, b):
	"""dE76 entre dos colores. Suficiente para decir 'estos dos se confunden'."""
	la, lb = _to_lab(a), _to_lab(b)
	return sum((la[i] - lb[i]) ** 2 for i in range(3)) ** 0.5


# ── La norma ──────────────────────────────────────────────────────────────

_cache = {}


def _dimmest(hue_hex, backgrounds, target, sat_min=SAT_MIN, sat_max=SAT_MAX):
	"""El tono MAS APAGADO de esta familia que pasa el suelo en TODOS los
	fondos que se le pasan. Si ninguno llega, devuelve el mas claro probado y
	la marca de que no llego, para que la simulacion lo cante."""
	h, _l, s = colorsys.rgb_to_hls(*[v / 255.0 for v in to_rgb(hue_hex)])
	s = min(max(s, sat_min), sat_max)
	best = None
	for step in range(28, 94):
		L = step / 100.0
		# Se redondea ANTES de comprobar: lo que acaba en pantalla es el
		# entero, no el flotante, y por medio punto de redondeo la norma se
		# daba por buena y luego su propia auditoria la suspendia.
		rgb = tuple(float(int(round(v * 255.0))) for v in colorsys.hls_to_rgb(h, L, s))
		if all(contrast(rgb, bg) >= target for bg in backgrounds):
			return rgb, True
		best = rgb
	return best, False


def _norm(hue_hex, backgrounds, target, sat_min=SAT_MIN, sat_max=SAT_MAX):
	key = (hue_hex, tuple(tuple(round(c, 2) for c in b) for b in backgrounds), target, sat_min, sat_max)
	hit = _cache.get(key)
	if hit is None:
		hit = _dimmest(hue_hex, backgrounds, target, sat_min, sat_max)
		_cache[key] = hit
	return hit


def _focus_dim():
	"""Cuanto se oscurece la tarjeta enfocada respecto del gris historico: el
	velo MAS SUAVE que aun deja un papel distinto, no el mas oscuro que se ve
	seguro. Se mide contra la tarjeta vieja con su tinte de debrid en los dos
	extremos del degradado, para que valga en todas las filas y no solo en la
	que no lleva servicio."""
	hit = _cache.get('focus_dim')
	if hit is not None:
		return hit
	backgrounds = []
	for d in list(DEBRID_HUES) + [None]:
		tint = to_rgb(surface(d)) if d else None
		if tint is None:
			backgrounds.append(FOCUS_CARD_LEGACY)
		else:
			for a in (TINT_ALPHA_LEFT * FOCUS_TINT_SCALE, TINT_ALPHA_RIGHT * FOCUS_TINT_SCALE):
				backgrounds.append(over(FOCUS_CARD_LEGACY, tint, a))
	dim = 0.80
	for step in range(2, 81):
		a = step / 100.0
		if all(separation(over(bg, (0, 0, 0), a), bg) >= FOCUS_DIM_SEPARATION for bg in backgrounds):
			dim = a
			break
	_cache['focus_dim'] = dim
	return dim


def focus_card():
	"""El gris real de la tarjeta enfocada, ya oscurecido. Es el fondo contra
	el que se calculan las tintas de la fila enfocada.

	FOCUS_LIGHTEN es una decision de Lucian por encima del resultado de la
	norma: el gris que salia (54,54,53) se le pisaba con las filas CAM, donde
	el color de la tarjeta es de por si oscuro, y no se apreciaba cual estaba
	enfocada. Sube un 25% y queda en (68,68,66), acotado al gris historico
	para que siga siendo un oscurecimiento y no un aclarado.

	La norma no desaparece: _focus_dim() sigue calculando el velo minimo, y
	este factor se aplica DESPUES y se declara. Lo que se pierde es margen de
	separacion contra el gris sin enfocar, y eso se mide en la simulacion en
	vez de darlo por bueno."""
	dimmed = tuple(v * (1.0 - _focus_dim()) for v in FOCUS_CARD_LEGACY)
	return tuple(min(dimmed[i] * FOCUS_LIGHTEN, float(FOCUS_CARD_LEGACY[i]))
				 for i in range(3))


def focus_card_diffuse():
	"""El colordiffuse que hay que aplicarle a common/card_focus.png para que
	de exactamente ese gris. La textura no es blanca (200,200,196), asi que
	el valor se despeja de ella y no se inventa."""
	target = focus_card()
	out = []
	for i in range(3):
		v = int(round(255.0 * target[i] / FOCUS_TEXTURE[i])) if FOCUS_TEXTURE[i] else 0
		out.append(min(255, max(0, v)))
	return 'FF%02X%02X%02X' % tuple(out)


def card_backgrounds(quality_key, debrid_abv, focused=False):
	"""Los fondos reales que puede tener el texto de una fila: tarjeta de
	calidad (o gris de foco) mas el tinte del debrid en sus dos extremos."""
	quality = to_rgb(QUALITY_HUES.get((quality_key or '').upper(), QUALITY_FALLBACK))
	tint = to_rgb(surface(debrid_abv)) if debrid_abv else None
	if focused:
		base = focus_card()
		alphas = (TINT_ALPHA_LEFT * FOCUS_TINT_SCALE, TINT_ALPHA_RIGHT * FOCUS_TINT_SCALE)
	else:
		base = over(BACKDROP, quality, CARD_ALPHA)
		alphas = (TINT_ALPHA_LEFT, TINT_ALPHA_RIGHT)
	if tint is None:
		return [base]
	return [over(base, tint, a) for a in alphas]


def surface(debrid_abv):
	"""Papel SUPERFICIE: el tinte de la tarjeta. Luminosidad y saturacion
	fijas y bajas — una superficie nunca debe competir con la tinta que va
	encima. Devuelve alfa FF porque quien pone el alfa es el degradado."""
	hue = DEBRID_HUES.get((debrid_abv or '').upper())
	if not hue:
		return None
	h, _l, s = colorsys.rgb_to_hls(*[v / 255.0 for v in to_rgb(hue)])
	s = min(s, SURFACE_SAT_MAX)
	return to_hex([v * 255.0 for v in colorsys.hls_to_rgb(h, SURFACE_L, s)])


def surface_tint_focused(debrid_abv):
	"""El mismo tinte para la fila enfocada, con su alfa ya puesto."""
	hexa = surface(debrid_abv)
	if not hexa:
		return '00000000'
	return '%02X%s' % (int(round(FOCUS_TINT_SCALE * 255)), hexa[2:])


def signal(quality_key):
	"""Papel SENAL: barra de calidad, icono y marco del poster. No es texto,
	asi que el suelo es mas bajo, pero cae sobre el fondo de ventana pelado."""
	key = (quality_key or '').upper()
	hue = QUALITY_HUES.get(key, QUALITY_FALLBACK)
	rgb, _ok = _norm(hue, [BACKDROP], CONTRAST_SIGNAL, sat_max=QUALITY_SAT_CAP.get(key, SAT_MAX))
	return to_hex(rgb)


def ink(hue_hex, backgrounds, accent=False):
	"""Papel TINTA."""
	rgb, _ok = _norm(hue_hex, backgrounds, CONTRAST_ACCENT if accent else CONTRAST_INK)
	return to_hex(rgb)


def neutral_ink(backgrounds):
	"""Texto rutinario: tamano, proveedor, fuente, score. Gris puro, mismo
	suelo de legibilidad. Se distingue del acento por croma, no por brillo."""
	rgb, _ok = _norm('808080', backgrounds, CONTRAST_INK, sat_min=0.0, sat_max=0.0)
	return to_hex(rgb)


def separator_ink(backgrounds):
	"""La barra vertical entre trozos. Es puntuacion, no informacion: suelo
	mas bajo a proposito para que no compita. El ambar FFffb74d a saturacion
	1.00, repetido seis veces por fila, era lo mas ruidoso de la linea."""
	rgb, _ok = _norm('808080', backgrounds, CONTRAST_SEPARATOR, sat_min=0.0, sat_max=0.0)
	return to_hex(rgb)


def header_ink(quality_key):
	"""La cabecera de desglose de calidades va sobre el fondo de ventana, no
	sobre una tarjeta, asi que tiene su propio fondo y su propio calculo."""
	key = (quality_key or '').upper()
	hue = QUALITY_HUES.get(key, QUALITY_FALLBACK)
	rgb, _ok = _norm(hue, [BACKDROP], CONTRAST_ACCENT, sat_max=QUALITY_SAT_CAP.get(key, SAT_MAX))
	return to_hex(rgb)


def header_separator():
	return separator_ink([BACKDROP])


def row_palette(quality_key, debrid_abv, focused=False):
	"""Todo lo que necesita una fila, de una vez. Cacheado por combinacion:
	una lista de 150 fuentes tiene como mucho 6 calidades x 7 debrid."""
	key = ('row', (quality_key or '').upper(), (debrid_abv or '').upper(), focused)
	hit = _cache.get(key)
	if hit is not None:
		return hit
	bgs = card_backgrounds(quality_key, debrid_abv, focused)
	hue = DEBRID_HUES.get((debrid_abv or '').upper()) or QUALITY_HUES.get((quality_key or '').upper(), QUALITY_FALLBACK)
	pal = {
		'accent': ink(hue, bgs, accent=True),
		'routine': neutral_ink(bgs),
		'separator': separator_ink(bgs),
	}
	_cache[key] = pal
	return pal


def audit():
	"""Las tres condiciones, comprobables desde fuera. Devuelve una lista de
	incumplimientos; vacia quiere decir que la norma se cumple entera."""
	fails = []
	for group, table, target in (
			('quality/signal', QUALITY_HUES, CONTRAST_SIGNAL),
			('debrid/surface', DEBRID_HUES, None)):
		keys = sorted(table)
		for i in range(len(keys)):
			for j in range(i + 1, len(keys)):
				if group.startswith('quality'):
					a, b = to_rgb(signal(keys[i])), to_rgb(signal(keys[j]))
				else:
					a, b = to_rgb(surface(keys[i])), to_rgb(surface(keys[j]))
				if group.startswith('debrid') and (keys[i] in DEBRID_LEGACY or keys[j] in DEBRID_LEGACY):
					continue
				d = separation(a, b)
				if d < SEPARATION_MIN:
					fails.append('%s: %s y %s se confunden (dE %.1f < %.1f)' % (
						group, keys[i], keys[j], d, SEPARATION_MIN))
	for q in list(QUALITY_HUES) + ['UNKNOWN']:
		for d in list(DEBRID_HUES) + [None]:
			for focused in (False, True):
				bgs = card_backgrounds(q, d, focused)
				pal = row_palette(q, d, focused)
				for role, floor in (('accent', CONTRAST_ACCENT), ('routine', CONTRAST_INK),
									('separator', CONTRAST_SEPARATOR)):
					worst = min(contrast(to_rgb(pal[role]), bg) for bg in bgs)
					if worst < floor - 0.005:
						fails.append('%s/%s%s %s: contraste %.2f < %.2f' % (
							q, d or 'sin debrid', ' (enfocada)' if focused else '', role, worst, floor))
	return fails
