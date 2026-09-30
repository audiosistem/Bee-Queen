"""
	luc_kodi Add-on
"""

from json import dumps as jsdumps
from urllib.parse import quote_plus
from resources.lib.modules.control import joinPath, transPath, dialog, getSourceHighlightColor, getDebridHighlightColor, notification, setting as getSetting, cancelPlayback
from resources.lib.modules import tools
from resources.lib.modules import color_norm
from resources.lib.windows.base import BaseDialog


LIST_ID, WIDE_LIST_ID = 2000, 2001

# Los tokens que no se ven todos los dias. Izados aqui y no dentro del bucle
# de make_items(): esa lista puede traer cientos de filas y este fichero ya
# lleva trabajo hecho para no repetir nada por item.
#
# El conjunto es deliberadamente corto. Con TrueHD, DTS-X, DTS-HD MA y HDR10+
# dentro, en una lista de 4K casi toda fila tenia algo en salmon, y cuando
# todo esta realzado no hay realce. Se queda solo lo que de verdad aparece de
# vez en cuando, y ademas lo que condiciona si el aparato podra reproducirlo:
# no todos admiten el perfil 5 de DV, ni AV1.
#
# Atmos, TrueHD y los DTS no desaparecen: bajan a gris y ahora salen unidos a
# sus canales (ver audio_unit).
RARE_TAGS = frozenset((
	'AV1', '60FPS', '50FPS', 'HFR',
	'DV-P7', 'DV-P8', 'DV-P5', 'DV-FEL', 'DV-MEL', 'DV-HYBRID'))
# v1.0.84: ya no hay un salmon fijo. El acento de cada fila lo calcula la
# norma de color a partir del tono del servicio que ha resuelto esa fuente
# (debrid o custom) y del fondo real de la tarjeta. Tags raros y bitrate del
# pre-flight comparten ese acento: en una fila hay como mucho DOS tintas, la
# de acento y la rutinaria, mas el separador. Ver modules/color_norm.py.

# ── Audio: un solo bloque, codec y canales juntos ─────────────────────────
#
# getFileType() emite el codec y el recuento de canales como tokens sueltos, y
# asi salian en la fila: 'ATMOS | DOLBY-TRUEHD | 8CH', tres trozos separados
# por barras que el ojo tiene que volver a juntar. Lo que describen es una
# sola cosa, asi que se escriben como una sola cosa: 'ATMOS-TRUE HD (7.1)'.
#
# v1.0.84: cuando el nombre declara VARIAS pistas siguen siendo una sola
# cosa. Antes la primera se llevaba los canales y las demas quedaban sueltas
# detras ('DTS-MASTER AUDIO (5.1) | TRUE HD'), que vuelve a partir en dos algo
# que es un conjunto. Ahora van todas dentro del mismo bloque separadas por
# barra inclinada y el recuento de canales cierra el bloque entero:
# 'DTS-MASTER AUDIO/ATMOS-TRUE HD (5.1)'.
#
# Y eso ademas es lo honesto: el nombre declara UN recuento de canales, no uno
# por pista. Colgarselo a la primera decia que esa pista es 5.1 y de las otras
# no se sabe; al final del bloque dice lo que el nombre dice de verdad, que el
# conjunto es 5.1. Inventar un recuento por pista seguiria siendo mentir.
# ── El separador de DENTRO de un bloque ───────────────────────────────────
#
# La barra vertical separa cosas distintas de la fila. Dentro de un bloque no
# hay cosas distintas: hay una sola cosa con varias pistas o varias capas, y
# marcar eso con el mismo signo que separa el proveedor del contenedor es
# decir dos cosas diferentes con el mismo trazo. Dentro va un punto.
#
# Por que ESTE punto y no otro: el plugin no lleva fuentes propias — no hay
# Font.xml ni un solo TTF en resources/skins —, asi que 'font13' lo resuelve
# la fuente del skin que tenga puesto el usuario y los glifos disponibles los
# elige Estuary, Aeon Nox o el que sea. El punto medio U+00B7 esta en el
# bloque Latin-1, que cualquier fuente de interfaz europea trae entero; los
# candidatos mas vistosos (U+2022, U+2219, box-drawing) ya estan fuera de ahi
# y en una fuente recortada salen como cuadraditos vacios.
#
# Y el tamano: en una etiqueta de Kodi NO se puede cambiar el cuerpo de la
# letra a mitad de cadena — no hay BBCode de tamano, solo [B], [I], [COLOR] y
# [UPPERCASE]. El unico mando disponible es [B]: engorda el trazo del punto
# sin tocar el resto de la linea y sin depender de ningun glifo nuevo. En las
# fuentes que usan los skins eso deja el punto entre un 20% y un 30% mas
# gordo, que es lo que se buscaba; exacto al 25% no se puede prometer, porque
# depende de la fuente que ponga cada skin.
BLOCK_SEP = ' [B]\u00b7[/B] '


AUDIO_CODECS = (
	('DTS-X', 'DTS-X'),
	('DTS-HD MA', 'DTS-MASTER AUDIO'),
	('DTS-HD', 'DTS-HD'),
	('DTS', 'DTS'),
	('DOLBY-TRUEHD', 'TRUE HD'),
	('DD+', 'DOLBY DIGITAL PLUS'),
	('DOLBYDIGITAL', 'DOLBY DIGITAL'),
	('DD-EX', 'DOLBY DIGITAL EX'),
	('DD', 'DOLBY DIGITAL'),
	('FLAC', 'FLAC'),
	('PCM', 'PCM'),
	('AAC', 'AAC'),
	('MP3', 'MP3'),
	('OPUS', 'OPUS'))
AUDIO_CHANNELS = {'8CH': '7.1', '7CH': '6.1', '6CH': '5.1', '2CH': '2.0'}

# Atmos es una extension Dolby: viaja encima de TrueHD o de Dolby Digital
# Plus, nunca encima de DTS. Hasta la 1.0.83 se pegaba a found[0], o sea al
# primer codec de la lista, y en un nombre con DTS-HD MA + TrueHD + Atmos eso
# escribia 'ATMOS-DTS-MASTER AUDIO', que atribuye a DTS algo que no es suyo.
# La lista va en orden de quien se lo lleva si hay varios candidatos.
ATMOS_CARRIERS = ('TRUE HD', 'DOLBY DIGITAL PLUS', 'DOLBY DIGITAL EX', 'DOLBY DIGITAL')


def audio_unit(parts):
	"""Devuelve (bloque_audio, tokens_consumidos).

	bloque_audio es la cadena ya montada ('ATMOS-TRUE HD (7.1)') o '' cuando el
	nombre no declara audio. tokens_consumidos son los trozos que hay que
	quitar de la fila porque ya estan dentro del bloque.
	"""
	up = {p.upper(): p for p in parts}
	consumed, found = [], []
	for token, label in AUDIO_CODECS:
		if token in up:
			found.append(label)
			consumed.append(up[token])
	atmos = 'ATMOS' in up
	if atmos:
		consumed.append(up['ATMOS'])
	channels = ''
	for token, label in AUDIO_CHANNELS.items():
		if token in up:
			channels = label
			consumed.append(up[token])
			break
	if not found:
		# Atmos sin codec debajo: el nombre dice Atmos y nada mas. Se muestra
		# tal cual en vez de callarlo.
		if atmos:
			return ('ATMOS (%s)' % channels if channels else 'ATMOS'), consumed
		# Canales sin codec: no hay conjunto que formar, pero dejar un '6CH'
		# suelto en la fila es justo lo que se venia a quitar. Se muestran en
		# la forma en que la gente los nombra.
		if channels:
			return channels, consumed
		return '', []
	labels = list(found)
	if atmos:
		for carrier in ATMOS_CARRIERS:
			if carrier in labels:
				labels[labels.index(carrier)] = 'ATMOS-%s' % carrier
				break
		else:
			# Atmos declarado sin ningun codec Dolby debajo. No se le cuelga a
			# lo que haya: entra como un elemento mas del bloque.
			labels.insert(0, 'ATMOS')
	block = BLOCK_SEP.join(labels)
	if channels:
		block = '%s (%s)' % (block, channels)
	return block, consumed


# ── Rango dinamico: un solo bloque, igual que el audio ────────────────────
#
# Mismo problema que tenia el sonido y misma respuesta. Un fichero con
# fallback declaraba 'HDR | DOLBY-VISION' — dos trozos separados por barra que
# el ojo tiene que volver a juntar — y en realidad no son dos cosas: es UNA,
# el rango dinamico de ese fichero, que resulta que trae dos capas. Se escribe
# como una: 'HDR/DOLBY-VISION'.
#
# El orden va de menos a mas capaz, o sea se lee terminando en lo mejor que
# ese fichero sabe hacer. Con el fallback delante, ademas, la fila dice lo que
# le importa a quien no tiene un aparato con DV: que tambien hay HDR10.
#
# Lo que NO entra en el bloque son el perfil y la capa (DV-P5, DV-P8, DV-FEL,
# ...). Son lo unico realzado de esta fila desde la 1.0.83, y por una razon:
# condicionan si el aparato podra reproducirlo. Dentro del bloque perderian el
# acento y el sitio de delante, que es exactamente lo que se les dio.
#
# 10BIT tampoco entra. Con HDR es redundante, pero sobre un fichero SDR es
# informacion de verdad — 'x265 10bit SDR' existe y es un caso real — y aqui
# no hay forma de distinguir un caso del otro sin mentir en el otro.
HDR_RANGES = (
	('HDR', 'HDR'),
	('HDR10', 'HDR'),
	('HDR10+', 'HDR10+'),
	('HLG', 'HLG'),
	('DOLBY-VISION', 'DOLBY-VISION'))


def hdr_unit(parts):
	"""Devuelve (bloque_rango, tokens_consumidos).

	bloque_rango es la cadena ya montada ('HDR/DOLBY-VISION') o '' cuando el
	nombre no declara rango. tokens_consumidos son los trozos que hay que
	quitar de la fila porque ya estan dentro del bloque.
	"""
	up = {p.upper(): p for p in parts}
	consumed, labels = [], []
	for token, label in HDR_RANGES:
		if token in up:
			consumed.append(up[token])
			if label not in labels:
				labels.append(label)
	# 'HDR' y 'HDR10' son el mismo formato escrito de dos maneras: get_extra_tags
	# y sootio ya llaman 'HDR' a un nombre que pone hdr10, asi que los dos caen
	# en la misma etiqueta y el bloque no dice dos veces lo mismo.
	sdr = 'SDR' in up
	if sdr:
		consumed.append(up['SDR'])
	# HDR10+ es metadato dinamico ENCIMA de una base HDR10: no existe un
	# HDR10+ que no sea tambien HDR10. Nombrar la base al lado no anade nada.
	if 'HDR10+' in labels and 'HDR' in labels:
		labels.remove('HDR')
	if not labels:
		# SDR es la ausencia de rango, no un rango; pero si el nombre lo
		# declara y no hay nada mas, es lo unico que se puede decir.
		return ('SDR' if sdr else ''), consumed
	# SDR junto a HDR o DV es una contradiccion del propio nombre (getFileType
	# los hace excluyentes; solo coinciden si un scraper inyecto el suyo). Se
	# calla el imposible en vez de escribir 'SDR/HDR', que no significa nada.
	return BLOCK_SEP.join(labels), consumed


class SourceResultsXML(BaseDialog):
	def __init__(self, *args, **kwargs):
		BaseDialog.__init__(self, args)
		self.window_id = {
			'List': LIST_ID,
			'Wide List': WIDE_LIST_ID
		}.get(getSetting('sources.select.wide_list')) or LIST_ID
		self.results = kwargs.get('results')
		self.uncached = kwargs.get('uncached')
		self.total_results = str(len(self.results))
		self.meta = kwargs.get('meta')
		self.make_items()
		self.set_properties()
		self.dnlds_enabled = True if getSetting('downloads') == 'true' and (getSetting('movie.download.path') != '' or getSetting('tv.download.path') != '') else False

	def onInit(self):
		win = self.getControl(self.window_id)
		win.addItems(self.item_list)
		self.setFocusId(self.window_id)

	def run(self):
		self.doModal()
		self.clearProperties()
		return self.selected

	def onAction(self, action):
		try:
			action_id = action.getId() # change to just "action" as the ID is already returned in that.
			of_action_id = action_id
			if action_id in self.closing_actions:
				self.selected = (None, '')
				try: cancelPlayback()
				except: pass
				return self.close()
			if action_id in self.info_actions:
				chosen_source = self.item_list[self.get_position(self.window_id)]
				chosen_source = chosen_source.getProperty('luc_kodi.source_dict')
				syssource = quote_plus(chosen_source)
				self.execute_code('RunPlugin(plugin://plugin.video.luc_kodi/?action=sourceInfo&source=%s)' % syssource)
			if action_id in self.selection_actions:
				chosen_source = self.item_list[self.get_position(self.window_id)]
				source = chosen_source.getProperty('luc_kodi.source')
				if 'load' in source:
					position = self.get_position(self.window_id)
					self.load_uncachedTorrents()
					self.setFocusId(self.window_id)
					self.getControl(self.window_id).selectItem(position)
					self.selected = (None, '')
					return
				elif 'UNCACHED' in source:
					debrid = chosen_source.getProperty('luc_kodi.debrid')
					source_dict = chosen_source.getProperty('luc_kodi.source_dict')
					link_type = 'pack' if 'package' in source_dict else 'single'
					sysname = quote_plus(self.meta.get('title'))
					if 'tvshowtitle' in self.meta and 'season' in self.meta and 'episode' in self.meta:
						poster = self.meta.get('season_poster') or self.meta.get('poster')
						sysname += quote_plus(' S%02dE%02d' % (int(self.meta['season']), int(self.meta['episode'])))
					elif 'year' in self.meta: sysname += quote_plus(' (%s)' % self.meta['year'])
					try: new_sysname = quote_plus(chosen_source.getProperty('luc_kodi.name'))
					except: new_sysname = sysname
					self.execute_code('RunPlugin(plugin://plugin.video.luc_kodi/?action=cacheTorrent&caller=%s&type=%s&title=%s&items=%s&url=%s&source=%s&meta=%s)' %
											(debrid, link_type, sysname, quote_plus(jsdumps(self.results)), quote_plus(chosen_source.getProperty('luc_kodi.url')), quote_plus(source_dict), quote_plus(jsdumps(self.meta))))
					self.selected = (None, '')
				else:
					self.selected = ('play_Item', chosen_source)
					# ── Personal ranker: registrar elección manual ─────
					# self.results es la lista de dicts; posición del elegido
					# da la slice de fuentes mostradas pero no escogidas (las
					# de arriba — las que el usuario explícitamente saltó).
					try:
						position = self.get_position(self.window_id)
						if 0 <= position < len(self.results):
							from resources.lib.database import source_ranker
							chosen_dict = self.results[position]
							skipped_above = self.results[:position]
							source_ranker.record_choice(
								chosen_dict,
								all_items=skipped_above + [chosen_dict]
							)
					except Exception:
						pass
				return self.close()
			elif action_id in self.context_actions:
				from re import match as re_match
				chosen_source = self.item_list[self.get_position(self.window_id)]
				source_dict = chosen_source.getProperty('luc_kodi.source_dict')
				cm_list = [('[B]Additional Link Info[/B]', 'sourceInfo')]
				if 'cached (pack)' in source_dict or 'unchecked (pack)' in source_dict:
					cm_list += [('[B]Browse Debrid Pack[/B]', 'showDebridPack')]
				source = chosen_source.getProperty('luc_kodi.source')
				if not 'UNCACHED' in source and self.dnlds_enabled:
					cm_list += [('[B]Download[/B]', 'download')]
				if re_match(r'^CACHED.*TORRENT', source):
					debrid = chosen_source.getProperty('luc_kodi.debrid')
					cm_list += [('[B]Save to %s Cloud[/B]' % debrid, 'saveToCloud')]
				chosen_cm_item = dialog.contextmenu([i[0] for i in cm_list])
				if chosen_cm_item == -1: return
				cm_action = cm_list[chosen_cm_item][1]
				if cm_action == 'sourceInfo':
					self.execute_code('RunPlugin(plugin://plugin.video.luc_kodi/?action=sourceInfo&source=%s)' % quote_plus(source_dict))
				elif cm_action == 'showDebridPack':
					debrid = chosen_source.getProperty('luc_kodi.debrid')
					name = chosen_source.getProperty('luc_kodi.name')
					hash = chosen_source.getProperty('luc_kodi.hash')
					self.execute_code('RunPlugin(plugin://plugin.video.luc_kodi/?action=showDebridPack&caller=%s&name=%s&url=%s&source=%s)' %
									(quote_plus(debrid), quote_plus(name), quote_plus(chosen_source.getProperty('luc_kodi.url')), quote_plus(hash)))
					self.selected = (None, '')
				elif cm_action == 'download':
					sysname = quote_plus(self.meta.get('title'))
					poster = self.meta.get('poster', '')
					if 'tvshowtitle' in self.meta and 'season' in self.meta and 'episode' in self.meta:
						sysname = quote_plus(self.meta.get('tvshowtitle'))
						poster = self.meta.get('season_poster') or self.meta.get('poster')
						sysname += quote_plus(' S%02dE%02d' % (int(self.meta['season']), int(self.meta['episode'])))
					elif 'year' in self.meta: sysname += quote_plus(' (%s)' % self.meta['year'])
					try: new_sysname = quote_plus(chosen_source.getProperty('luc_kodi.name'))
					except: new_sysname = sysname
					self.execute_code('RunPlugin(plugin://plugin.video.luc_kodi/?action=download&name=%s&image=%s&source=%s&caller=sources&title=%s)' %
										(new_sysname, quote_plus(poster), quote_plus(source_dict), sysname))
					self.selected = (None, '')
				elif cm_action == 'saveToCloud':
					magnet = chosen_source.getProperty('luc_kodi.url')
					if debrid == 'AD':
						from resources.lib.debrid import alldebrid
						transfer_function = alldebrid.AllDebrid
						debrid_icon = alldebrid.ad_icon
					elif debrid == 'PM':
						from resources.lib.debrid import premiumize
						transfer_function = premiumize.Premiumize
						debrid_icon = premiumize.pm_icon
					elif debrid == 'RD':
						from resources.lib.debrid import realdebrid
						transfer_function = realdebrid.RealDebrid
						debrid_icon = realdebrid.rd_icon
					elif debrid == 'TB':
						from resources.lib.debrid import torbox
						transfer_function = torbox.TorBox
						debrid_icon = torbox.tb_icon
					else:
						# v1.0.78 — aqui habia ramas para 'OC' (Offcloud) y 'ED'
						# (EasyDebrid) que importaban resources.lib.debrid.offcloud
						# y .easydebrid. Esos dos ficheros NO existen en el addon,
						# asi que la rama era un ImportError esperando a que alguien
						# tuviera uno de esos servicios. Inalcanzable hoy porque
						# debrid_abv() nunca devuelve esas siglas para una fuente
						# real, pero un scraper nuevo que las devolviera tumbaba el
						# menu contextual entero. Un servicio desconocido ahora
						# avisa y no hace nada.
						notification(message='No cloud transfer available for %s' % debrid)
						return
					result = transfer_function().create_transfer(magnet)
					if result: notification(message='Sending MAGNET to the %s cloud' % debrid, icon=debrid_icon)
			elif action in self.closing_actions:
				self.selected = (None, '')
				self.close()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def get_quality_iconPath(self, quality):
		try:
			return joinPath(transPath('special://home/addons/plugin.video.luc_kodi/resources/skins/Default/media/resolution'), '%s.png' % quality)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def debrid_abv(self, debrid):
		try:
			d_dict = {'AllDebrid': 'AD', 'Premiumize.me': 'PM', 'Real-Debrid': 'RD', 'TorBox': 'TB'}
			d = d_dict[debrid]
		except:
			d = ''
		return d

	def debrid_name(self, debrid):
		"""Return a user-facing debrid service name (safe fallback)."""
		try:
			d_dict = {
				'AllDebrid': 'AllDebrid',
				'EasyDebrid': 'EasyDebrid',
				'Offcloud': 'Offcloud',
				'Premiumize.me': 'Premiumize',
				'Real-Debrid': 'Real-Debrid',
				'TorBox': 'TorBox'
			}
			# If we don't recognize it, show whatever provider gave us.
			d = d_dict.get(debrid) or (debrid or '')
		except:
			d = ''
		return d

	def _compute_quality_breakdown(self):
		"""Build a colored, single-line summary of result counts per quality bucket.

		Mirrors the per-item quality colors used in make_items() so the header
		visually matches the list rows.

		Buckets are split into two tiers:
		  * Main tier: 4K, 1080P, 720P, SD — always considered.
		  * Low tier:  SCR, CAM — only displayed when the title has NO
		    main-tier results at all (i.e. a cinema-only release like a
		    fresh CAM/TS rip). When at least one main-tier bucket has
		    results, SCR/CAM are hidden because they're almost always
		    misclassified noise once a real release is out.

		Empty buckets within the displayed tier are also omitted so the
		header stays uncluttered.

		Returns a Kodi-BBCode string suitable for a <label>, e.g.:
			[COLOR FF00BCD4][B]4K:13[/B][/COLOR] | [COLOR FF4CAF50][B]1080p:29[/B][/COLOR] | ...
		"""
		try:
			if not self.results:
				return ''
			# Same colors used for the per-item quality_color in make_items()
			# (label, hex, display_name)
			main_qualities = (
				('4K',    color_norm.header_ink('4K'),    '4K'),
				('1080P', color_norm.header_ink('1080P'), '1080p'),
				('720P',  color_norm.header_ink('720P'),  '720p'),
				('SD',    color_norm.header_ink('SD'),    'SD'),
			)
			low_qualities = (
				('SCR',   color_norm.header_ink('SCR'),   'SCR'),
				('CAM',   color_norm.header_ink('CAM'),   'CAM'),
			)
			counts = {q[0]: 0 for q in main_qualities + low_qualities}
			for item in self.results:
				q = (item.get('quality') or 'SD').upper()
				if q in counts:
					counts[q] += 1
				else:
					counts['SD'] += 1
			# Pick the tier to display: main tier wins if any of its buckets
			# has results; otherwise fall back to the low tier (cinema-only).
			main_has_results = any(counts[q[0]] > 0 for q in main_qualities)
			display_order = main_qualities if main_has_results else low_qualities
			parts = [
				'[COLOR %s][B]%s:%d[/B][/COLOR]' % (q_color, q_label, counts[q_key])
				for q_key, q_color, q_label in display_order
				if counts[q_key] > 0
			]
			if not parts:
				return ''
			# Same separator color used by extra_info in make_items() for visual consistency.
			sep = '[COLOR %s] | [/COLOR]' % color_norm.header_separator()
			return sep.join(parts)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return ''


	def make_items(self):
		def builder():
			# Resolver de badges: built-in por defecto, o el pack custom del
			# usuario si hay uno instalado y activo. Se resuelve UNA vez por
			# lista (nada de I/O ni lectura de settings por cada source).
			from resources.lib.modules import badges_config
			_badge_resolver = badges_config.get_resolver()
			# v1.0.65 — aviso de fuente pesada. La velocidad de linea aprendida
			# y la duracion del titulo se resuelven UNA vez por lista: dentro
			# del bucle serian una consulta a la BD por cada fuente.
			# v1.0.86 — el gris de la tarjeta enfocada. Lo calcula la norma
			# (una vez para toda la lista, no fila a fila) y el XML lo lee de
			# aqui, para que el papel y el fondo contra el que se calcula la
			# tinta sean literalmente el mismo numero.
			_focus_card = color_norm.focus_card_diffuse()
			# v1.0.89 — idiomas de audio. Preferencia y pistas ya sondeadas
			# se resuelven UNA vez por lista: lo sondeado es una sola consulta
			# a la base para todas las filas, no una por fila.
			_langs_on, _lang_pref, _lang_real = False, (), {}
			try:
				if getSetting('audio.langs.list') != 'false':
					from resources.lib.modules import audio_langs as _al
					from resources.lib.modules import audio_probe as _ap
					_langs_on = True
					_lang_pref = _al.preferred()
					_lang_real = _ap.known([_ap.key_for(_it, self.meta) for _it in self.results])
			except Exception:
				_langs_on, _lang_pref, _lang_real = False, (), {}
			_pf_mod, _pf_line = None, 0.0
			try:
				if getSetting('preflight.list.warn') == 'true':
					from resources.lib.modules import preflight as _pf_mod
					# v1.0.78 — los umbrales de advisory() se cachean por pasada,
					# asi que se olvidan al empezar cada lista: si el usuario
					# acaba de cambiarlos en ajustes, la siguiente lista los ve.
					_pf_mod.reset_cache()
					_pf_line = _pf_mod.line_mbps()
					# v1.0.69: NO se abandona cuando aun no hay velocidad medida.
					# La regla por tamano no la necesita, y antes esto dejaba la
					# columna muda hasta la primera reproduccion.
			except Exception:
				_pf_mod, _pf_line = None, 0.0
			for count, item in enumerate(self.results, 1):
				try:
					listitem = self.make_listitem()
					# v1.0.78 — las propiedades se juntan y se mandan de UNA vez.
					# Eran 35 llamadas al otro lado del puente C por fila: con 150
					# fuentes, 5.250 viajes para pintar una lista, y 1.650 de ellos
					# escribiendo cadena vacia en huecos de badge sin usar. Ahora es
					# una llamada por fila con setProperties(), que existe desde
					# Kodi 20. Los huecos vacios ni se escriben: el skin lee
					# 'ausente' y 'vacio' igual, y cada listitem es nuevo, asi que
					# no hay valor anterior que borrar.
					_props = {}
					_set = _props.__setitem__
					quality = item.get('quality', 'SD')
					# ── Norma de color, v1.0.84 ──────────────────────────
					# La paleta de esta fila se resuelve ANTES de escribir
					# nada, porque de ella salen las dos tintas y el
					# separador. Se calcula a partir del tono del servicio
					# que resuelve (debrid, o CUSTOM) y del fondo real de la
					# tarjeta, que depende de la calidad. row_palette()
					# cachea por combinacion: en una lista de 150 fuentes hay
					# como mucho seis calidades por siete servicios, asi que
					# el trabajo se hace una vez y no ciento cincuenta.
					_dbr = (item.get('debrid') or '')
					_pal_key = 'CUSTOM' if _dbr.lower() == 'custom' else self.debrid_abv(_dbr)
					_pal = color_norm.row_palette(quality, _pal_key, False)
					_palf = color_norm.row_palette(quality, _pal_key, True)
					_accent, _accentf = _pal['accent'], _palf['accent']
					_routine, _routinef = _pal['routine'], _palf['routine']
					_bar, _barf = _pal['separator'], _palf['separator']
					quality_icon = self.get_quality_iconPath(quality)
					extra_info = item.get('info') or ''
					# Normalizar separadores: getFileType usa ' / ', display espera ' | '
					# 1) ' / ' -> ' | '  2) quitar / sueltas  3) normalizar | sueltas
					import re as _re
					extra_info = extra_info.replace(' /', ' |').replace('/', '')
					extra_info = _re.sub(r'\s*\|\s*', ' | ', extra_info)  # normaliza spacing alrededor de |
					extra_info = _re.sub(r'(\s*\|\s*)+$', '', extra_info)  # quita trailing |
					extra_info = extra_info.split('GB ', 1)[-1]
					extra_info = extra_info.lstrip(' |').strip()
					extra_info_focused = ''
					_parts = []
					# ── Idiomas de audio, v1.0.89 ────────────────────────
					# Primero de la fila: fuera del foco la linea se corta y
					# el idioma es lo que decide si una fuente sirve o no.
					# Lo leido del propio fichero (audio_probe) manda sobre lo
					# declarado por el indexado y va en negrita; el idioma
					# preferido lleva el acento de la fila, la misma tinta
					# que ya significa 'mira aqui' para los tags raros.
					_lang_block = _lang_block_f = ''
					if _langs_on:
						try:
							_real = _lang_real.get(_ap.key_for(item, self.meta))
							_codes = _al.ordered(_real or item.get('langs') or [], _lang_pref)
							# v1.0.91: fichero leido con audio sin idioma declarado
							if _real and _codes == [_ap.UNTAGGED]:
								from resources.lib.modules.control import lang as _lang
								_codes = [_lang(400856)]
							if _codes:
								_bw = ('[B]%s[/B]' if _real else '%s')
								_lang_block = ('[COLOR %s] [B]\u00b7[/B] [/COLOR]' % _routine).join(
									'[COLOR %s]%s[/COLOR]' % (_accent if _al.matches(c, _lang_pref) else _routine, _bw % c) for c in _codes)
								_lang_block_f = ('[COLOR %s] [B]\u00b7[/B] [/COLOR]' % _routinef).join(
									'[COLOR %s]%s[/COLOR]' % (_accentf if _al.matches(c, _lang_pref) else _routinef, _bw % c) for c in _codes)
						except Exception:
							_lang_block = _lang_block_f = ''
					if extra_info:
						# Tabla de sinonimos para normalizacion global (aplica a todos los scrapers)
						_SYNONYMS = {
							'DOLBY VISION': 'DOLBY-VISION', 'DOLBY-VISION': 'DOLBY-VISION', 'DV': 'DOLBY-VISION',
							'DOLBY ATMOS': 'ATMOS', 'HDR10PLUS': 'HDR10+', 'HDR10 PLUS': 'HDR10+',
							'WEBDL': 'WEB-DL', 'WEB DL': 'WEB-DL', 'WEB': 'WEB',
							'BLU RAY': 'BLURAY', 'BLU-RAY': 'BLURAY',
							'MULTI LANG': 'MULTI-LANG', 'MULTILANG': 'MULTI-LANG', 'MULTI': 'MULTI-LANG',
							'DD PLUS': 'DD+', 'EAC3': 'DD+', 'AC3': 'DD',
							'10 BIT': '10BIT', 'AVC': 'H264', 'H.264': 'H264', 'H.265': 'HEVC',
							'X265': 'HEVC', 'X264': 'H264', 'HEVC': 'HEVC',
						}
						# Deduplicar con normalizacion de sinonimos (aplica a TODOS los scrapers)
						# Evita: HDR|HDR, DV|DOLBY-VISION, X265|HEVC, MULTI|MULTI-LANG, etc.
						_seen_parts = set()
						_parts = []
						for _p in extra_info.split(' | '):
							_p = _p.strip()
							# Descartar fragmentos de size residuales (ej. "9.32 GB" o "9.32")
							if not _p or _re.match(r'^\d+(\.\d+)?\s*(GB|MB|GiB|MiB)?$', _p, _re.I):
								continue
							_norm = _SYNONYMS.get(_p.upper(), _p.upper())
							if _norm not in _seen_parts:
								_parts.append(_SYNONYMS.get(_p.upper(), _p))  # display en forma canonical
								_seen_parts.add(_norm)
						# ── v1.0.83: lo que no se ve todos los dias, delante y aparte ──
						#
						# Dos problemas, uno de sitio y otro de color.
						#
						# El sitio: el <scroll> del skin esta SOLO en el layout
						# enfocado (Control.HasFocus(2000)). En las filas que no
						# tienes seleccionadas el texto se corta y ya esta, asi que
						# un DV-FEL al final de una linea larga no existe hasta que
						# te posas encima. Van primeros, conservando entre ellos el
						# orden en que getFileType() los emitio (imagen antes que
						# sonido), y el resto detras igual que siempre.
						#
						# El color: hasta ahora todos los trozos salian del mismo
						# gris, asi que anadir tokens solo alargaba la linea y lo
						# excepcional quedaba tan apagado como el MKV. El salmon es
						# el mismo de la etiqueta CUSTOM y del bitrate del
						# pre-flight: en esta ventana ya significa "mira aqui".
						#
						# ATMOS y REMUX se quedan en gris a proposito. En 2160p son
						# corrientes, y si se realza lo corriente no se realza nada.
						# _parts se queda como esta: es lo que leen los badges y lo
						# que se publica en luc_kodi.flags_raw para el skin. Lo que
						# se reescribe es solo lo que el usuario lee.
						_audio, _consumed = audio_unit(_parts)
						# v1.0.85: el rango dinamico se monta igual que el audio.
						# Diferencia de sitio: el bloque de sonido se va al final
						# (getFileType ya emite imagen antes que sonido y ahi es
						# donde se espera), mientras que el de rango se queda
						# EXACTAMENTE donde estaba el primero de sus tokens, que
						# es delante del codec. Si se anadiera al final, la fila
						# pasaria a leerse 'HEVC | 10BIT | ... | HDR/DV' y el dato
						# de imagen acabaria detras del contenedor.
						_hdr, _consumed_hdr = hdr_unit(_parts)
						_display = []
						for _p in _parts:
							if _p in _consumed_hdr:
								if _hdr and _hdr not in _display:
									_display.append(_hdr)
								continue
							if _p in _consumed:
								continue
							_display.append(_p)
						if _audio:
							_display.append(_audio)
						_rare_parts = [p for p in _display if p.upper() in RARE_TAGS]
						if _rare_parts:
							_display = _rare_parts + [p for p in _display if p.upper() not in RARE_TAGS]
						# Con el bloque de idiomas delante, MULTI-LANG ya esta
						# dicho y mejor: se quita de lo que se lee (no de _parts,
						# que alimenta los badges).
						if _lang_block:
							_display = [p for p in _display if p.upper() != 'MULTI-LANG']
						extra_info = ('[COLOR %s] | [/COLOR]' % _bar).join(
							'[COLOR %s]%s[/COLOR]' % (_accent if p.upper() in RARE_TAGS else _routine, p) for p in _display)
						extra_info_focused = ('[COLOR %s] | [/COLOR]' % _barf).join(
							'[COLOR %s]%s[/COLOR]' % (_accentf if p.upper() in RARE_TAGS else _routinef, p) for p in _display)
					if _lang_block:
						extra_info = (_lang_block + ('[COLOR %s] | [/COLOR]' % _bar) + extra_info) if extra_info else _lang_block
						extra_info_focused = (_lang_block_f + ('[COLOR %s] | [/COLOR]' % _barf) + extra_info_focused) if extra_info_focused else _lang_block_f
					# Aviso "esto va a bufferear": el bitrate medio que exige el
					# fichero (tamano / duracion) contra la velocidad medida de
					# la linea. Se antepone a extra_info en vez de tocar el skin,
					# asi sale igual en 1080i y en 2160p.
					if _pf_mod is not None:
						try:
							_adv = _pf_mod.advisory(item, self.meta, line=_pf_line)
							_v = _adv.get('verdict')
							if _v in ('heavy', 'info'):
								# Solo la cifra, y en UN SOLO color para los dos casos
								# (v1.0.65 oficial). El rojo y el dorado destacaban
								# demasiado para lo que son: un dato mas de la ficha,
								# no una alarma. v1.0.69: el salmon pasa a aqua
								# (ff77dad7), que se lee mejor sobre esta linea. La
								# etiqueta CUSTOM conserva su salmon.
								# v1.0.84: el aqua fijo desaparece. La cifra
								# comparte el acento de la fila con los tags
								# raros, que es lo que baja la segunda linea
								# de cuatro tintas a dos.
								_warn = '[COLOR %s]%dMbps[/COLOR]' % (_accent, int(_adv['required_mbps']))
								_warnf = '[COLOR %s]%dMbps[/COLOR]' % (_accentf, int(_adv['required_mbps']))
								_sep = '[COLOR %s] | [/COLOR]' % _bar
								_sepf = '[COLOR %s] | [/COLOR]' % _barf
								extra_info = (_warn + _sep + extra_info) if extra_info else _warn
								extra_info_focused = (_warnf + _sepf + extra_info_focused) if extra_info_focused else _warnf
						except Exception:
							pass
					size_label = '%.2f GB' % item.get('size', 0) if item.get('size') else 'NA'
					score_val = item.get('score', '')
					_set('luc_kodi.source_dict', jsdumps([item]))
					_set('luc_kodi.debrid', self.debrid_name(item.get('debrid')).upper())
					_set('luc_kodi.debridabrv', self.debrid_abv(item.get('debrid')))

					debrid_abv = self.debrid_abv(item.get('debrid'))
					# v1.0.84. 'highlight' y la tinta dejan de ser el mismo
					# valor, que era el fallo de fondo: la tarjeta se tine
					# con ese color, asi que escribir el texto del mismo
					# color era escribir con la tinta del papel. En una fila
					# de Real-Debrid el contraste era 1,74. Ahora 'highlight'
					# es SUPERFICIE (el tinte, apagado y sin competir) y
					# 'highlight_ink' es TINTA, calculada contra ese mismo
					# tinte. CUSTOM entra en la tabla como un servicio mas.
					highlight_color = color_norm.surface(_pal_key) or getSourceHighlightColor()
					_set('highlight', highlight_color)
					_set('highlight_ink', _accent)
					_set('highlight_ink_focused', _accentf)
					_set('routine_ink', _routine)
					_set('routine_ink_focused', _routinef)
					_set('separator_ink', _bar)
					_set('separator_ink_focused', _barf)
					_set('focus_card_tint', _focus_card)
					# El tinte de la fila enfocada. Hasta ahora el skin lo
					# construia con 40$INFO[...:3], que sobre un valor de
					# ocho caracteres deja siete y no es un color valido.
					_set('highlight_tint', color_norm.surface_tint_focused(_pal_key))
					_set('luc_kodi.provider', item.get('provider').upper())
					_set('luc_kodi.source', item.get('source').upper())
					_set('luc_kodi.seeders', str(item.get('seeders')))
					_set('luc_kodi.hash', item.get('hash', 'N/A'))
					_set('luc_kodi.name', item.get('name'))
					quality_colors = {
						'4K':    'FF00BCD4',
						'1080P': 'FF4CAF50',
						'720P':  'FFFFA726',
						'SD':    'FF607D8B',
						'SCR':   'FFB71C1C',
						'CAM':   'FFB0C4DE',
					}
					quality_assets = {
						'4K':    ('resolution/card_4k.png',    'resolution/bar_4k.png'),
						'1080P': ('resolution/card_1080p.png', 'resolution/bar_1080p.png'),
						'720P':  ('resolution/card_720p.png',  'resolution/bar_720p.png'),
						'SD':    ('resolution/card_sd.png',    'resolution/bar_sd.png'),
						'SCR':   ('resolution/card_scr.png',   'resolution/bar_scr.png'),
						'CAM':   ('resolution/card_cam_b.png',  'resolution/bar_cam_b.png'),
					}
					q_key = quality.upper()
					# v1.0.84: el diccionario de arriba se conserva como
					# documentacion de los tonos historicos, pero lo que se
					# pinta sale de la norma (papel senal).
					q_color = color_norm.signal(q_key)
					q_card, q_bar = quality_assets.get(q_key, ('resolution/card_default.png', ''))
					skin_media = transPath('special://home/addons/plugin.video.luc_kodi/resources/skins/Default/media/')
					_set('quality_color',   q_color)
					_set('quality_card_bg', joinPath(skin_media, q_card))
					_set('quality_bar',     joinPath(skin_media, q_bar) if q_bar else '')
					_set('luc_kodi.quality', quality.upper())
					_set('luc_kodi.quality_icon', quality_icon)
					# ── Media-flag icon slots (3rd row inside each card) ─────────────
					# itemlayout freezes <visible> per item, but a per-item texture
					# ($INFO[ListItem.Property]) resolves correctly. So we compute the
					# ordered, gap-free list of icon paths here and expose them as
					# luc_kodi.flag0..flagN; the skin shows one image per slot.
					# Built-in icon set, unless the user installed+enabled a custom
					# badge pack via the Setup Wizard (Nuvio Badges Studio format),
					# in which case its regex rules take over.
					_FLAG_SLOTS = 14
					_icons = _badge_resolver(quality, item.get('name') or '', _parts, skin_media)
					for _i in range(min(_FLAG_SLOTS, len(_icons))):
						_set('luc_kodi.flag%d' % _i, _icons[_i])
					_set('luc_kodi.url', item.get('url'))
					# v1.0.83. La tira de iconos de fuera de la lista se dibuja con
					# String.Contains sobre las etiquetas, asi que hasta ahora
					# cualquier cambio de redaccion en la fila apagaba iconos sin
					# avisar: renombrar DOLBY-TRUEHD a 'TRUE HD' habria bastado.
					# Los tokens crudos van en su propia propiedad y el skin mira
					# ahi, con lo que la fila queda libre para escribirse como se
					# lea mejor.
					_set('luc_kodi.flags_raw', ' | '.join(_parts))
					_set('luc_kodi.extra_info', extra_info)
					_set('luc_kodi.extra_info_focused', extra_info_focused)
					_set('luc_kodi.size_label', size_label)
					_set('luc_kodi.score', str(score_val) if score_val != '' else '')
					_set('luc_kodi.count', '%02d.' % count)
					listitem.setProperties(_props)
					yield listitem
				except:
					from resources.lib.modules import log_utils
					log_utils.error()
		try:
			self.item_list = list(builder())
			self.total_results = str(len(self.item_list))
			if self.uncached and getSetting('torrent.remove.uncached') == 'true':
				icon = '/resources/skins/Default/media/common/play.png'
				quality_icon = transPath('special://home/addons/plugin.video.luc_kodi' + icon)
				uncached = str(len(self.uncached))
				fill_char = str.rjust(' ', len(self.total_results) + 1, '>')
				listitem = self.make_listitem()
				listitem.setProperty('luc_kodi.name', 'View Uncached Torrents')
				listitem.setProperty('luc_kodi.source', 'load uncached torrents')
				listitem.setProperty('luc_kodi.quality_icon', quality_icon)
				listitem.setProperty('luc_kodi.size_label', uncached)
				listitem.setProperty('luc_kodi.count', fill_char)
				# Esta fila se construye aparte y no pasa por el lote de
				# propiedades de arriba: sin esto su colordiffuse llegaria
				# vacio al skin y la tarjeta enfocada saldria en el blanco
				# crudo de la textura.
				listitem.setProperty('focus_card_tint', color_norm.focus_card_diffuse())
				self.item_list.append(listitem)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def set_properties(self):
		if self.meta is None: return
		try:
			self.setProperty('luc_kodi.highlight.color', getSourceHighlightColor())
			self.setProperty('luc_kodi.total_results', self.total_results)
			self.setProperty('luc_kodi.quality_breakdown', self._compute_quality_breakdown())
			self.setProperty('luc_kodi.season', str(self.meta.get('season', '')))
			if 'tvshowtitle' in self.meta and 'season' in self.meta and 'episode' in self.meta: self.setProperty('luc_kodi.seas_ep', 'S%02dE%02d' % (int(self.meta['season']), int(self.meta['episode'])))
			if self.meta.get('season_poster'): self.setProperty('luc_kodi.poster', self.meta.get('season_poster', ''))
			else: self.setProperty('luc_kodi.poster', self.meta.get('poster', ''))
			self.setProperty('luc_kodi.fanart', self.meta.get('fanart', ''))
			self.setProperty('luc_kodi.clearlogo',     self.meta.get('clearlogo', ''))
			self.setProperty('luc_kodi.network_logo', self.meta.get('network_logo', ''))
			self.setProperty('luc_kodi.plot', self.meta.get('plot', ''))
			self.setProperty('luc_kodi.year', str(self.meta.get('year', '')))
			new_date = tools.convert_time(stringTime=str(self.meta.get('premiered', '')), formatInput='%Y-%m-%d', formatOutput='%m-%d-%Y', zoneFrom='utc', zoneTo='utc')
			self.setProperty('luc_kodi.premiered', new_date)
			mpaa = self.meta.get('mpaa') if self.meta.get('mpaa') else ''
			self.setProperty('luc_kodi.mpaa', mpaa)
			if self.meta.get('duration'):
				duration = int(self.meta.get('duration')) / 60
				duration = '%.0f min' % duration
			else: duration = ''
			self.setProperty('luc_kodi.duration', duration)
			details = ' | '.join(i for i in (mpaa, duration) if i)
			self.setProperty('luc_kodi.details', details)
			self.setProperty('luc_kodi.wide_list', 'true' if self.window_id == WIDE_LIST_ID else 'false')
			# v1.0.78 — las valoraciones ya NO se esperan aqui.
			#
			# set_properties() corre dentro de __init__, o sea DESPUES de que
			# sourceSelect haya cerrado el dialogo de espera y ANTES del
			# doModal(). Y _fetch_ratings hacia hasta tres peticiones HTTP en
			# serie (MDBList, Trakt, OMDB con timeout 8 s) sobre un titulo
			# frio. Todo ese rato el usuario mira una pantalla vacia, sin aro
			# ni ventana. Medido en el arnes: 0,3 ms con la cache caliente
			# frente a 900 ms por cada peticion que toque hacer.
			#
			# Las propiedades se escriben por nombre y el skin las lee cuando
			# existan, asi que se vacian ya —para que no quede lo del titulo
			# anterior— y se rellenan desde un hilo. La ventana abre al
			# instante y las notas aparecen solas un momento despues.
			for _svc in ('tmdb', 'trakt', 'imdb', 'imdb_source'):
				self.setProperty('luc_kodi.rating.%s' % _svc, '')
			import threading
			_t = threading.Thread(target=self._fetch_ratings)
			_t.daemon = True
			_t.start()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def _fetch_ratings(self):
		"""Rellena las propiedades de valoraciones de la ventana.

		v1.0.67 — la cascada (MDBList, TMDb, Trakt, OMDB) se mudo a
		modules/ratings.py para que la linea del reproductor lea exactamente
		las mismas cifras. Aqui solo queda el reparto por propiedades.

		  luc_kodi.rating.tmdb        — nota, p.ej. "7.3"
		  luc_kodi.rating.trakt       — nota, p.ej. "8.1"
		  luc_kodi.rating.imdb        — nota de IMDb, Metacritic o RT
		  luc_kodi.rating.imdb_source — 'imdb' | 'metacritic' | 'rt'
		"""
		try:
			# El vaciado lo hace ahora set_properties antes de lanzar el hilo,
			# para que las notas del titulo anterior desaparezcan en el mismo
			# instante en que abre la ventana y no un segundo despues.
			from resources.lib.modules import ratings as ratings_mod
			data = ratings_mod.fetch(self.meta, live=True)
			self.setProperty('luc_kodi.rating.tmdb',  data.get('tmdb') or '')
			self.setProperty('luc_kodi.rating.trakt', data.get('trakt') or '')
			imdb, source = data.get('imdb') or '', data.get('imdb_source') or ''
			if not imdb and data.get('rt'):
				# Se mantiene el comportamiento anterior: sin IMDb ni
				# Metacritic, el hueco lo ocupaba Rotten Tomatoes.
				imdb, source = data['rt'], 'rt'
			self.setProperty('luc_kodi.rating.imdb', imdb)
			self.setProperty('luc_kodi.rating.imdb_source', source)
		except Exception:
			from resources.lib.modules import log_utils
			log_utils.error()

	def load_uncachedTorrents(self):
		try:
			from resources.lib.windows.uncached_results import UncachedResultsXML
			from resources.lib.modules.control import addonPath, addonId
			window = UncachedResultsXML('uncached_results.xml', addonPath(addonId()), uncached=self.uncached, meta=self.meta)
			window.run()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
