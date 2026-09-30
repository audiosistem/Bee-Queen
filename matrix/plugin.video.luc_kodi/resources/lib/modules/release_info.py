# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — modules/release_info.py

	Puts what the chosen release claims about itself into the one field every
	skin is guaranteed to draw during playback: the synopsis.

	Why this way, after two dead ends
	--------------------------------
	Attaching stream details to the ListItem does nothing here. Confirmed on
	device: during full screen playback ListItem.* resolves to nothing at all,
	because there is no container, and the VideoPlayer.* labels a skin does
	read are filled by the player itself. There is no way in.

	Drawing our own information window does not reach every setup either.
	Skins in the Arctic family draw their information inside VideoOSD.xml
	rather than as a separate window, so there is nothing to intercept, and on
	a touch screen there is no Info key to catch.

	What is left is the synopsis, and it works precisely because it is not
	clever: VideoPlayer.Plot comes from the metadata we hand Kodi, every skin
	shows it, and it needs no key, no window and no keymap.

	The cost is real and worth stating: this writes into the film's synopsis.
	That is why it is off by default and why each line is clearly marked for
	where it comes from.

	v1.0.67 — the short summary is cleared on the playing item. The tagline
	fallback added in 1.0.66 put a bold line right above the block on the
	titles that have one, which is why it showed on some films and not
	others. Browsing is untouched.

	v1.0.67 — the block moved to the head of the synopsis. At the end it read
	as something stuck on afterwards, and on a film with a long plot it was
	simply not on screen: skins clip the plot during playback, so the last
	line is the first to fall outside the box. The blank line went with it;
	one newline is what makes the whole thing read as a single block.

	Two lines now, and they stay apart on purpose. SCORES are checkable
	metadata about the film. RELEASE is what whoever packaged the file claims
	about it. Different things with different reliability, and merging them
	into one row would erase exactly the distinction the RELEASE marker exists
	to keep. The scraper the source came from rides on the RELEASE line, being
	the one item there that is ours and always true.

	Only flags Kodi cannot report are worth the intrusion. ATMOS, DTS-X,
	DTS-HD MA, TrueHD, REMUX, BluRay and WEB have no infolabel anywhere in
	Kodi; resolution and codec do, and any skin already has them from the
	first frame, so repeating those would be noise.
"""

from resources.lib.modules import control
from resources.lib.modules import log_utils

NAME_PROP    = 'luc_kodi.release.name'
FLAGS_PROP   = 'luc_kodi.release.flags'
SIZE_PROP    = 'luc_kodi.release.size'
QUALITY_PROP = 'luc_kodi.release.quality'
PROVIDER_PROP = 'luc_kodi.release.provider'
_ALL_PROPS = (NAME_PROP, FLAGS_PROP, SIZE_PROP, QUALITY_PROP, PROVIDER_PROP)

HEAD_COLOR = 'FF00FA9A'
DATA_COLOR = 'FF77DAD7'
# Gris de prosa, el mismo que ordena sin competir en el test de proveedores.
# Los nombres de las casas de notas son etiquetas, no datos: si van del mismo
# color que las cifras, cuatro nombres propios pelean con cuatro numeros y no
# se lee ninguno.
LABEL_COLOR = 'FFDFE4E7'

# Flags with no Kodi infolabel anywhere. On their own they justify writing
# into a synopsis at all.
EXCLUSIVE = ('ATMOS', 'DTS-X', 'DTS-HD MA', 'DTS-HD', 'DOLBY-TRUEHD', 'DD-EX',
				'REMUX', 'BLURAY', 'DVD', 'WEB', 'HDTV', 'PDTV', 'SCR', 'HDRIP',
				'3D', 'MULTI-LANG', 'HC', 'WITH SUBS', 'SUBS', 'ADS',
				# v1.0.83. El perfil y la capa de Dolby Vision cumplen el
				# criterio de esta lista al pie: no hay infolabel en ningun
				# sitio de Kodi que diga si lo que estas viendo es P7 FEL o P8.
				'DV-P7', 'DV-P8', 'DV-P5', 'DV-FEL', 'DV-MEL', 'DV-HYBRID')

# Container names. Never shown: knowing a file is an MKV tells nobody anything
# about how it will look or sound.
CONTAINERS = ('MKV', 'AVI', 'WMV', 'MPEG')

# getFileType() counts channels; people think in speaker layouts. 8CH and 7.1
# are the same thing, but sitting next to a skin's own '7.1' badge they read
# as two different claims.
#
# Only these four exist. source_utils has no token for 2.1 (AUDIO_2CH matches
# 2.0 and stereo, never 2.1), so a 2.1 release produces no channel flag at all
# and none is invented here.
CHANNEL_LAYOUTS = {'8CH': '7.1', '7CH': '6.1', '6CH': '5.1', '2CH': '2.0'}


def enabled():
	return control.setting('player.info.release') == 'true'


def remember(item):
	"""Called at resolve time. play_source() receives only the resolved URL,
	and a debrid link keeps none of the release name, size or quality."""
	if not isinstance(item, dict):
		return
	try:
		home = control.homeWindow
		home.setProperty(NAME_PROP, str(item.get('name') or item.get('name_info') or ''))
		home.setProperty(QUALITY_PROP, str(item.get('quality') or ''))
		home.setProperty(SIZE_PROP, str(item.get('size') or ''))
		# De donde salio la fuente. No es una afirmacion del nombre del
		# fichero como el resto de la linea, es dato nuestro y siempre cierto.
		home.setProperty(PROVIDER_PROP, str(item.get('provider') or ''))

		from resources.lib.modules.source_utils import getFileType
		if item.get('name_info'):
			flags = getFileType(name_info=item.get('name_info'))
		else:
			flags = getFileType(url=item.get('url'))
		home.setProperty(FLAGS_PROP, flags or '')
	except Exception:
		log_utils.error()


def context():
	home = control.homeWindow
	return {'name':    home.getProperty(NAME_PROP),
			'flags':   home.getProperty(FLAGS_PROP),
			'size':    home.getProperty(SIZE_PROP),
			'quality': home.getProperty(QUALITY_PROP),
			'provider': home.getProperty(PROVIDER_PROP)}


def forget():
	for prop in _ALL_PROPS:
		try:
			control.homeWindow.clearProperty(prop)
		except Exception:
			pass


def full_detail():
	"""'1' = show everything the release states, '0' = only what Kodi cannot
	report itself."""
	return control.setting('player.info.release.detail') != '0'


def _flag_list(flags, full=None):
	"""getFileType() returns ' A / B / C'. Split it, exclusive flags first.

	Whether to keep the rest is a real question with no universal answer. Kodi
	does hold the codec, the HDR flavour and the channel count from the first
	frame, so on a skin that draws them the release line would just repeat
	what is already on screen. But plenty of skins draw none of it during
	playback, and then dropping them means the information exists nowhere.
	This was hardcoded to drop them, which was wrong for exactly that case.
	Now it is a setting, and the default keeps them.

	Container names are always dropped: MKV or AVI says nothing useful."""
	if not flags:
		return []
	full = full_detail() if full is None else full
	parts = [part.strip() for part in flags.split('/') if part.strip()]
	parts = [p for p in parts if p not in CONTAINERS]
	parts = [CHANNEL_LAYOUTS.get(p, p) for p in parts]
	exclusive = [p for p in parts if p in EXCLUSIVE]
	if not full:
		return exclusive
	# Exclusive first, then the rest in the order getFileType emitted them,
	# which already runs picture before sound.
	return exclusive + [p for p in parts if p not in EXCLUSIVE]


def show_ratings():
	return control.setting('player.info.release.ratings') == 'true'


def show_scraper():
	return control.setting('player.info.release.scraper') == 'true'


def _sep():
	return ' [COLOR %s]\u00b7[/COLOR] ' % HEAD_COLOR


def _pair(label, value):
	return '[COLOR %s]%s[/COLOR] [COLOR %s]%s[/COLOR]' % (LABEL_COLOR, label, DATA_COLOR, value)


def line(ctx=None):
	"""La linea de la release, o '' cuando no hay nada que decir. Nunca
	inventa: ausente es ausente."""
	ctx = context() if ctx is None else ctx
	bits = []
	if ctx.get('quality'):
		bits.append(ctx['quality'])
	bits.extend(_flag_list(ctx.get('flags')))
	# 4K already says 2160p; drop the duplicate the parser adds for some names.
	if ctx.get('quality') == '4K' and '2160P' in [b.upper() for b in bits[1:]]:
		bits = [bits[0]] + [b for b in bits[1:] if b.upper() != '2160P']
	size = ctx.get('size')
	if size:
		try:
			bits.append('%.2f GB' % float(size))
		except Exception:
			bits.append(str(size))
	# El scraper va el ultimo y en mayusculas como el resto de la linea: en
	# minusculas, entre banderas todas en caja alta, parece un error de
	# formato antes que un dato.
	if show_scraper() and ctx.get('provider'):
		bits.append(str(ctx['provider']).upper())
	if not bits:
		return ''
	return ('[COLOR %s][B]RELEASE:[/B][/COLOR]  %s'
			% (HEAD_COLOR, _sep().join('[COLOR %s]%s[/COLOR]' % (DATA_COLOR, b) for b in bits)))


# Como se titula cada casa. El hueco de IMDb lo puede ocupar un suplente, y
# entonces hay que decir de quien es la nota: un 74 presentado como IMDb
# cuando es de Metacritic no es un detalle menor, son escalas distintas.
#
# 'RT' se escribe entero. Dos letras no son un nombre: al lado de IMDb, TMDb y
# Trakt, que se presentan como se llaman, RT obliga a adivinar de quien es esa
# cifra, y adivinar mal es facil (Rotten Tomatoes, Rating, Trakt...). La linea
# no va justa de sitio, asi que la abreviatura no compraba nada.
_IMDB_LABELS = {'imdb': 'IMDb', 'metacritic': 'Metacritic', 'rt': 'Rotten Tomatoes'}


def ratings_line(meta):
	"""Las notas, en una linea propia. Vacia si no hay ninguna.

	Van separadas de RELEASE a proposito. Lo de abajo es lo que AFIRMA quien
	empaqueto el fichero; esto son metadatos comprobables de la pelicula. Son
	dos cosas distintas con fiabilidad distinta, y juntarlas en un renglon
	borra justo la distincion por la que la linea de release lleva su
	etiqueta."""
	if not show_ratings():
		return ''
	try:
		from resources.lib.modules import ratings as ratings_mod
		# live=False: la sinopsis se escribe en el instante previo a arrancar
		# el video. Una peticion aqui es pantalla negra mientras se espera.
		data = ratings_mod.fetch(meta, live=False)
	except Exception:
		log_utils.error()
		return ''
	bits = []
	if data.get('imdb'):
		bits.append(_pair(_IMDB_LABELS.get(data.get('imdb_source'), 'IMDb'), data['imdb']))
	if data.get('tmdb'):
		bits.append(_pair('TMDb', data['tmdb']))
	if data.get('trakt'):
		bits.append(_pair('Trakt', data['trakt']))
	# Las dos de critica van al final, detras de las tres de publico. Cada
	# una solo si no ocupa ya el hueco de IMDb, o saldria dos veces.
	if data.get('rt') and data.get('imdb_source') != 'rt':
		bits.append(_pair('Rotten Tomatoes', data['rt']))
	# Metacritic y Rotten Tomatoes miden cosas distintas y por eso caben las
	# dos: RT es el porcentaje de criticos a los que les gusto, sin mas;
	# Metacritic es la media ponderada de las notas que pusieron. Un 95% con
	# un 71 de media es un dato, no una contradiccion.
	if data.get('metacritic') and data.get('imdb_source') != 'metacritic':
		bits.append(_pair('Metacritic', data['metacritic']))
	if not bits:
		return ''
	# SCORES y no RATED: 'rated' en una ficha de pelicula se lee como la
	# clasificacion por edades, que es otra cosa y ademas ya la muestran los
	# skins.
	return ('[COLOR %s][B]SCORES:[/B][/COLOR]   %s'
			% (HEAD_COLOR, _sep().join(bits)))


def announce():
	"""One line per playback saying whether this is even switched on.

	Written because three different builds went out numbered 1.0.66 and a log
	could not be told apart from another. A log should never leave you
	guessing which build produced it."""
	try:
		log_utils.log('[ luc_kodi ] release_info: player.info.release = %s, detail = %s, '
					'scores = %s, scraper = %s'
					% ('ON' if enabled() else 'OFF',
						'FULL' if full_detail() else 'EXCLUSIVE-ONLY',
						'ON' if show_ratings() else 'OFF',
						'ON' if show_scraper() else 'OFF'), level=log_utils.LOGINFO)
	except Exception:
		pass


def attach_to_plot(item, meta):
	"""Re-escribe el plot con el bloque DELANTE de la sinopsis. Se llama
	despues de infoTagger(), asi que pisa lo que aquel acaba de poner en vez
	de competir con el.

	v1.0.67 — iba al final y con una linea en blanco de por medio, y de ahi
	las dos quejas: se leia como algo pegado aparte, y en una pelicula con
	sinopsis larga directamente no se veia. Los skins recortan el plot durante
	la reproduccion, asi que lo ultimo es lo primero que se queda fuera del
	cuadro. Arriba se ve siempre, y sin el hueco el conjunto se lee como un
	bloque unico.

	El argumento de 1.0.66 para ponerlo al final era que se pudiera ignorar
	con la vista. Sigue valiendo para lo que se ignora, no para lo que no
	llega a existir.
	"""
	if not enabled():
		return False
	try:
		head = [x for x in (ratings_line(meta), line()) if x]
		if not head:
			return False
		plot = ((meta or {}).get('plot') or '').strip()
		# Un solo salto por linea: la linea en blanco es lo que separaba el
		# bloque de la sinopsis en vez de encabezarla.
		combined = '%s\n%s' % ('\n'.join(head), plot) if plot else '\n'.join(head)

		# El resumen corto se vacia SOLO en el item que va al reproductor.
		# v1.0.66 le puso el tagline de suplente cuando la pelicula no trae
		# plotoutline propio, y ahi arriba se colaba una frase en negrita
		# delante del bloque —'Meet Linda Liddle...'— que ademas empujaba
		# todo hacia abajo. Se vacian los dos campos y no solo plotoutline
		# porque cada skin lee uno: unos pintan VideoPlayer.PlotOutline y
		# otros VideoPlayer.Tagline, y quitar uno dejaria la frase puesta en
		# la mitad de los casos.
		#
		# Navegando no se toca nada: alli ese resumen corto es justo para lo
		# que se anadio.
		if control.KODI_VERSION < 20:
			item.setInfo(type='video', infoLabels={'plot': combined,
			                                       'plotoutline': '', 'tagline': ''})
		else:
			tag = item.getVideoInfoTag()
			tag.setPlot(combined)
			tag.setPlotOutline('')
			tag.setTagLine('')
		for entry in head:
			log_utils.log('[ luc_kodi ] release_info: %s' % entry, level=log_utils.LOGINFO)
		return True
	except Exception:
		log_utils.error()
		return False


# Nombre anterior. Lo llamaba player.py y puede llamarlo cualquier build
# antigua que todavia ande por ahi, asi que sigue existiendo.
def append_to_plot(item, meta):
	return attach_to_plot(item, meta)
