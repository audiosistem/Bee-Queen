# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
"""

import re
from urllib.parse import unquote, unquote_plus

VIDEO_3D = ('.3d.', '.sbs.', '.hsbs', 'sidebyside', 'side.by.side', 'stereoscopic', '.tab.', '.htab.', 'topandbottom', 'top.and.bottom')

DOLBY_VISION = ('dolby.vision', 'dolbyvision', '.dovi.', '.dv.')
HDR = ('2160p.uhd.bluray', '2160p.uhd.blu.ray', '2160p.bluray.hevc.truehd', '2160p.blu.ray.hevc.truehd',
			'2160p.bluray.hevc.dts.hd.ma', '2160p.blu.ray.hevc.dts.hd.ma', '.hdr.', 'hdr10', 'hdr.10',
			'uhd.bluray.2160p', 'uhd.blu.ray.2160p')
HDR_true = ('.hdr.', 'hdr10', 'hdr.10')

# v1.0.83. AV1 no estaba aqui, aunque el badge source/AV1.png existe, el skin
# lo busca en luc_kodi.extra_info y source_ranker.py tiene una feature
# 'codec:AV1'. O sea que todo el arbol sabia leer un token que nadie emitia:
# solo llegaba cuando el scraper lo habia inyectado por get_extra_tags().
CODEC_AV1 = ('.av1.', '.av01', 'av1.')
CODEC_H264 = ('avc', 'h264', 'h.264', 'x264', 'x.264')
CODEC_H265 = ('h265', 'h.265', 'hevc', 'x265', 'x.265')
CODEC_XVID = ('xvid', '.x.vid')
CODEC_DIVX = ('divx', 'div2', 'div3', 'div4')
CODEC_MPEG = ('.mpg', '.mp2', '.mpeg', '.mpe', '.mpv', '.mp4', '.m4p', '.m4v', 'msmpeg', 'mpegurl')
CODEC_MKV = ('.mkv', 'matroska')
REMUX = ('remux', 'bdremux')

BLURAY = ('bluray', 'blu.ray', 'bdrip', 'bd.rip', '.brrip.', 'br.rip')
DVD = ('dvdrip', 'dvd.rip')
WEB = ('.web.', 'webdl', 'web.dl', 'webrip', 'web.rip')
HDRIP = ('.hdrip', '.hd.rip')
SCR = ('scr.', 'screener')
HC = ('.hc', 'korsub', 'kor.sub')

# Perfil y capa de Dolby Vision. Solo se consultan con DOLBY-VISION ya
# detectado: 'p5'/'p7'/'p8' son dos caracteres y salen sueltos en nombres de
# grupo y en numeraciones. FEL y MEL solo existen dentro de DV.
DV_P7 = ('.p7.', '.dvp7.', '.profile.7.', 'dvhe.07')
DV_P8 = ('.p8.', '.dvp8.', '.profile.8.', 'dvhe.08')
DV_P5 = ('.p5.', '.dvp5.', '.profile.5.', 'dvhe.05')
DV_FEL = ('.fel.', 'bl.el.rpu', 'blelrpu')
DV_MEL = ('.mel.',)
BITDEPTH_10 = ('.10bit.', '.10.bit.')
# Se exige 'fps' pegado al numero: '2160p' lleva un '60' dentro.
FPS_60 = ('.60fps.', '.60.fps.')
FPS_50 = ('.50fps.', '.50.fps.')

DOLBY_TRUEHD = ('true.hd', 'truehd')
# v1.0.83: 'ddpa' anadido. Es DD+ con Atmos escrito de corrido, y salia en
# una fila real de TORRENTGALAXY ('DDPA.5.1') donde el codec no se reconocia
# y el recuento de canales se quedaba huerfano en la linea.
DOLBY_DIGITALPLUS = ('dolby.digital.plus', 'dolbydigital.plus', 'dolbydigitalplus', 'dd.plus.', 'ddplus', '.ddp.', 'ddp2', 'ddp5', 'ddp7', 'ddpa', 'eac3', '.e.ac3')
DOLBY_DIGITALEX = ('.dd.ex.', 'ddex', 'dolby.ex.', 'dolby.digital.ex.', 'dolbydigital.ex.')
DOLBYDIGITAL = ('dd2.', 'dd5', 'dd7', 'dolbyd.', 'dolby.digital', 'dolbydigital', '.ac3', '.ac.3.', '.dd.')

DTSX = ('dts.x.', 'dtsx')
DTS_HDMA = ('hd.ma', 'hdma')
DTS_HD = ('dts.hd.', 'dtshd')

AUDIO_8CH = ('ch8.', '8ch.', '7.1ch', '7.1.')
AUDIO_7CH = ('ch7.', '7ch.', '6.1ch', '6.1.')
AUDIO_6CH = ('ch6.', '6ch.', '5.1ch', '5.1.')
AUDIO_2CH = ('ch2', '2ch', '2.0ch', '2.0.', 'audio.2.0.', 'stereo')

MULTI_LANG = ('dual.audio', 'dual.yg', 'multi')
LANG = ('arabic', 'bgaudio', 'castellano', 'chinese', 'dutch', 'finnish', 'french', 'german', 'greek', 'hebrew', 'italian', 'latino', 'polish',
				'portuguese', 'russian', 'spanish', 'tamil', 'telugu', 'truefrench', 'truespanish', 'turkish')
ABV_LANG = ('.ara.', '.ces.', '.chi.', '.chs.', '.cze.', '.dan.', '.de.', '.deu.', '.dut.', '.ell.', '.es.', '.esl.', '.esp.', '.fi.', '.fin.', '.fr.', '.fra.', '.fre.', '.frn.', '.gai.', '.ger.', '.gle.', '.gre.',
				'.gtm.', '.he.', '.heb.', '.hi.', '.hin.', '.hun.', '.hindi.', '.ind.', '.iri.', '.it.', '.ita.', '.ja.', '.jap.', '.jpn.', '.ko.', '.kor.', '.lat.', '.nl.', '.lit.', '.nld.', '.nor.', '.pl.', '.pol.',
				'.pt.', '.por.', '.ru.', '.rus.', '.som.', '.spa.', '.sv.', '.sve.', '.swe.', '.tha.', '.tr.', '.tur.', '.uae.', '.uk.', '.ukr.', '.vi.', '.vie.', '.zh.', '.zho.')
SUBS = ('subita', 'subfrench', 'subspanish', 'subtitula', 'swesub', 'nl.subs')
ADS = ('1xbet', 'betwin')

def seas_ep_filter(season, episode, release_title, split=False):
	try:
		release_title = re.sub(r'[^A-Za-z0-9-]+', '.', unquote(release_title).replace('\'', '')).replace('&', 'and').replace('%', '.percent').lower()
		season = str(season)
		season_fill = season.zfill(2)
		episode = str(episode)
		episode_fill = episode.zfill(2)
		int_episode = int(episode)

		string1 = r'(s<<S>>[.-]?e[p]?[.-]?<<E>>[.-])'
		string2 = r'(season[.-]?<<S>>[.-]?episode[.-]?<<E>>[.-])|' \
						r'([s]?<<S>>[x.]<<E>>[.-])'
		string3 = r'(s<<S>>e<<E1>>[.-]?e?<<E2>>[.-])'
		string4 = r'([.-]<<S>>[.-]?<<E>>[.-])'
		string5 = r'(episode[.-]?<<E>>[.-])'
		string6 = r'([.-]e[p]?[.-]?<<E>>[.-])'

		string_list = []
		append = string_list.append
		append(string1.replace('<<S>>', season_fill).replace('<<E>>', episode_fill))
		append(string1.replace('<<S>>', season).replace('<<E>>', episode_fill))
		append(string1.replace('<<S>>', season_fill).replace('<<E>>', episode))
		append(string1.replace('<<S>>', season).replace('<<E>>', episode))
		append(string2.replace('<<S>>', season_fill).replace('<<E>>', episode_fill))
		append(string2.replace('<<S>>', season).replace('<<E>>', episode_fill))
		append(string2.replace('<<S>>', season_fill).replace('<<E>>', episode))
		append(string2.replace('<<S>>', season).replace('<<E>>', episode))
		append(string3.replace('<<S>>', season_fill).replace('<<E1>>', str(int_episode-1).zfill(2)).replace('<<E2>>', episode_fill))
		append(string3.replace('<<S>>', season_fill).replace('<<E1>>', episode_fill).replace('<<E2>>', str(int_episode+1).zfill(2)))
		append(string4.replace('<<S>>', season_fill).replace('<<E>>', episode_fill))
		append(string4.replace('<<S>>', season).replace('<<E>>', episode_fill))
		append(string5.replace('<<E>>', episode_fill))
		append(string5.replace('<<E>>', episode))
		append(string6.replace('<<E>>', episode_fill))

		final_string = '|'.join(string_list)
		reg_pattern = re.compile(final_string)
		if split: return release_title.split(re.search(reg_pattern, release_title).group(), 1)[1]
		else: return bool(re.search(reg_pattern, release_title))
	except:
		from resources.lib.modules import log_utils
		log_utils.error()
		return None

def extras_filter():
	return ('sample', 'extra', 'deleted', 'unused', 'footage', 'inside', 'blooper', 'making.of', 'feature', 'featurette', 'behind.the.scenes', 'trailer')

def is_archive_part(path):
	"""v1.0.54: True si el fichero es una PARTE de un archivo multivolumen.
	Las listas invalid_extensions solo cubrian '.rar' y '.zip', asi que las
	partes numeradas (.z01/.z03, .r00, .part1.rar, .001) pasaban el filtro y,
	al ser enormes, ganaban el max(size) de la seleccion de fichero: el
	reproductor recibia un trozo de archivo y Kodi respondia "Playback not
	supported" (visto en kodi.log con un .z03 de un COMPLETE UHD BLURAY).
	Nada de esto es reproducible en streaming: hay que descomprimirlo antes."""
	try:
		low = str(path or '').lower().split('?')[0].split('|')[0]
		# .z01..z99 / .r00..r99 / .7z.001 / .part01.rar / .001..999
		return bool(re.search(r'\.(z\d{2}|r\d{2}|part\d+\.rar|\d{3})$', low))
	except: return False

def supported_video_extensions():
	try:
		from xbmc import getSupportedMedia
		supported_video_extensions = getSupportedMedia('video').split('|')
		return [i for i in supported_video_extensions if i != '' and i != '.zip']
	except:
		from resources.lib.modules import log_utils
		log_utils.error()

def getFileType(name_info=None, url=None):
	try:
		file_type = ''
		if name_info: fmt = name_info
		elif url: fmt = url_strip(url)
		if not fmt: return file_type

		if any(value in fmt for value in VIDEO_3D):  file_type += ' 3D /'

		if '.sdr' in fmt: file_type += ' SDR /'
		elif any(value in fmt for value in DOLBY_VISION): file_type += ' DOLBY-VISION /'
		elif any(value in fmt for value in HDR): file_type += ' HDR /'
		elif all(i in fmt for i in ('2160p', 'remux')): file_type += ' HDR /'
		if ' DOLBY-VISION ' in file_type:
			if any(value in fmt for value in HDR_true): file_type += ' HDR /' # for hybrid DV and HDR sources
			# v1.0.83. El perfil y la capa, cuando el nombre los declara. Esto
			# lee lo declarado y nada mas: FEL vive en el RPU del fichero y no
			# hay forma de confirmarlo ni desmentirlo antes de reproducir.
			if any(value in fmt for value in DV_P7): file_type += ' DV-P7 /'
			elif any(value in fmt for value in DV_P8): file_type += ' DV-P8 /'
			elif any(value in fmt for value in DV_P5): file_type += ' DV-P5 /'
			if any(value in fmt for value in DV_FEL): file_type += ' DV-FEL /'
			elif any(value in fmt for value in DV_MEL): file_type += ' DV-MEL /'
			elif '.hybrid.' in fmt: file_type += ' DV-HYBRID /'

		if any(value in fmt for value in CODEC_AV1): file_type += ' AV1 /'
		elif any(value in fmt for value in CODEC_H264): file_type += ' AVC /'
		elif any(value in fmt for value in CODEC_H265): file_type += ' HEVC /'
		elif any(i in file_type for i in (' HDR ', ' DOLBY-VISION ')): file_type += ' HEVC /'
		elif any(value in fmt for value in CODEC_XVID): file_type += ' XVID /'
		elif any(value in fmt for value in CODEC_DIVX): file_type += ' DIVX /'

		if '.wmv' in fmt: file_type += ' WMV /'
		elif any(value in fmt for value in CODEC_MPEG): file_type += ' MPEG /'
		elif '.avi' in fmt: file_type += ' AVI /'
		elif any(value in fmt for value in CODEC_MKV): file_type += ' MKV /'

		if any(value in fmt for value in BITDEPTH_10): file_type += ' 10BIT /'

		if any(value in fmt for value in FPS_60): file_type += ' 60FPS /'
		elif any(value in fmt for value in FPS_50): file_type += ' 50FPS /'
		elif '.hfr.' in fmt: file_type += ' HFR /'

		if any(value in fmt for value in REMUX): file_type += ' REMUX /'

		if any(value in fmt for value in BLURAY): file_type += ' BLURAY /'
		elif any(i in fmt for i in DVD): file_type += ' DVD /'
		elif any(value in fmt for value in WEB): file_type += ' WEB /'
		elif 'hdtv' in fmt: file_type += ' HDTV /'
		elif 'pdtv' in fmt: file_type += ' PDTV /'
		elif any(value in fmt for value in SCR): file_type += ' SCR /'
		elif any(value in fmt for value in HDRIP): file_type += ' HDRIP /'

		# 'ddpa' lleva la A de Atmos dentro, asi que la declara igual que si
		# el nombre pusiera 'atmos' con todas sus letras.
		if 'atmos' in fmt or 'ddpa' in fmt: file_type += ' ATMOS /'
		if any(value in fmt for value in DOLBY_TRUEHD): file_type += ' DOLBY-TRUEHD /'
		if any(value in fmt for value in DOLBY_DIGITALPLUS): file_type += ' DD+ /'
		elif any(value in fmt for value in DOLBYDIGITAL): file_type += ' DOLBYDIGITAL /'
		elif any(value in fmt for value in DOLBY_DIGITALEX): file_type += ' DD-EX /'

		if 'aac' in fmt: file_type += ' AAC /'
		elif 'mp3' in fmt: file_type += ' MP3 /'
		elif 'flac' in fmt: file_type += ' FLAC /'
		# elif 'opus' in fmt and not fmt.endswith('opus.'): file_type += ' OPUS /' #OPUS also a group titles endswith

		if any(value in fmt for value in DTSX): file_type += ' DTS-X /'
		elif any(value in fmt for value in DTS_HDMA): file_type += ' DTS-HD MA /'
		elif any(value in fmt for value in DTS_HD): file_type += ' DTS-HD /'
		elif '.dts' in fmt: file_type += ' DTS /'

		if any(value in fmt for value in AUDIO_8CH): file_type += ' 8CH /'
		elif any(value in fmt for value in AUDIO_7CH): file_type += ' 7CH /'
		elif any(value in fmt for value in AUDIO_6CH): file_type += ' 6CH /'
		elif any(value in fmt for value in AUDIO_2CH): file_type += ' 2CH /'

		if any(value in fmt for value in HC): file_type += ' HC /'

		if any(value in fmt for value in MULTI_LANG): file_type += ' MULTI-LANG /'
		elif any(value in fmt for value in LANG) and any(value in fmt for value in ('.eng.', '.en.', 'english')): file_type += ' MULTI-LANG /'
		elif any(value in fmt for value in ABV_LANG) and any(value in fmt for value in ('.eng.', '.en.', 'english')):file_type += ' MULTI-LANG /'

		if any(value in fmt for value in ADS): file_type += ' ADS /'
		if any(value in fmt for value in SUBS):
			if file_type != '': file_type += ' WITH SUBS'
			else: file_type = 'SUBS'
		file_type = file_type.rstrip('/') # leave trailing space for cases like " HDR " vs. " HDRIP "
		return file_type
	except:
		from resources.lib.modules import log_utils
		log_utils.error()
		return ''

def url_strip(url):
	try:
		url = unquote_plus(url)
		if 'magnet:' in url: url = url.split('&dn=')[1]
		url = url.lower().replace("'", "").lstrip('.').rstrip('.')
		fmt = re.sub(r'[^a-z0-9]+', '.', url)
		fmt = '.%s.' % fmt
		fmt = re.sub(r'(.+)((?:19|20)[0-9]{2}|season.\d+|s[0-3]{1}[0-9]{1}|e\d+|complete)(.complete\.|.episode\.\d+\.|.episodes\.\d+\.\d+\.|.series|.extras|.ep\.\d+\.|.\d{1,2}\.|-|\.|\s)', '', fmt) # new for pack files
		if '.http' in fmt: fmt = None
		if fmt == '': return None
		else: return '.%s' % fmt
	except:
		from resources.lib.modules import log_utils
		log_utils.error()
		return None

def aliases_check(title, aliases):
	fixed_aliases = []
	try:
		bad_aliases = {'Dexter': ['Dexter: New Blood',], 'Titans': ['Teen Titans',]}
		if title in bad_aliases:
			for i in aliases:
				if i.get('title') not in bad_aliases.get(title): fixed_aliases.append(i)
			aliases = fixed_aliases
		if title == 'Gomorrah': aliases.append({'title': 'Gomorra', 'country': ''})
		if title == 'Daredevil': aliases.append({'title': "Marvel's Daredevil", 'country': 'us'})
	except:
		from resources.lib.modules import log_utils
		log_utils.error()
	return aliases

def tvshow_reboots():
	reboots = {
		"Adam-12": ["1990"], "Battlestar Galactica": ["2004"], "Charlie's Angels": ["2011"], "Charmed": ["2018"], "Dynasty": ["2017"], "Fantasy Island": ["2021"],
		"The Flash": ["2014"], "The Fugitive": ["2000", "2020"], "Ghostwriter": ["2019"], "Gossip Girl": ["2021"], "Hawaii Five-0": ["2010"],
		"Ironside": ["2013"], "Kojak": ["2005"], "Kung Fu": ["2021"], "Lost in Space": ["2018"], "MacGyver": ["2016"], "Magnum P.I.": ["2018"], "Nancy Drew": ["2019"],
		"The Odd Couple": ["2015"], "One Day at a Time": ["2017"], "The Outer Limits": ["1995"], "Party of Five": ["2020"], "Perry Mason": ["2020"], "S.W.A.T.": ["2017"],
		"The Twilight Zone": ["1985", "2002", "2019"], "The Untouchables": ["1993"], "V": ["2009"], "The Wonder Years": ["2021"]}
	return reboots

def copy2clip(txt):
	from sys import platform
	if platform == "win32":
		try:
			from subprocess import check_call
			# cmd = "echo " + txt.strip() + "|clip"
			cmd = "echo " + txt.replace('&', '^&').strip() + "|clip" # "&" is a command seperator
			return check_call(cmd, shell=True)
		except:
			from resources.lib.modules import log_utils
			log_utils.error('Windows: Failure to copy to clipboard')
	elif platform == "darwin":
		try:
			from subprocess import check_call
			cmd = "echo " + txt.strip() + "|pbcopy"
			return check_call(cmd, shell=True)
		except:
			from resources.lib.modules import log_utils
			log_utils.error('Mac: Failure to copy to clipboard')
	elif platform == "linux":
		try:
			from subprocess import Popen, PIPE
			p = Popen(["xsel", "-pi"], stdin=PIPE)
			p.communicate(input=txt)
		except:
			from resources.lib.modules import log_utils
			log_utils.error('Linux: Failure to copy to clipboard')


# ---------------------------------------------------------------------
# v1.0.90 — Release group (inspirado en _extract_release_group de TMDb Movies)
# ---------------------------------------------------------------------
# Lo usa binge.py para que el siguiente episodio salga, si se puede, del
# mismo grupo que el anterior (mismo encode, misma mezcla de audio, mismo
# doblaje). Casos que cubre, por orden:
#   ...-GRUPO.mkv       sufijo con guion (el caso normal)
#   ...[GRUPO].mkv      grupo entre corchetes al final
#   ...x265.GRUPO       grupo tras el ultimo punto
# Se descarta basura que aparece en esas posiciones (codecs, resoluciones,
# idiomas, "dual", "remux"...). Si no hay certeza, devuelve ''.
_RG_JUNK = frozenset((
	'x264', 'x265', 'h264', 'h265', 'hevc', 'avc', 'av1', 'xvid', 'divx', 'mkv', 'mp4', 'avi',
	'1080p', '720p', '2160p', '480p', '4k', 'uhd', 'hdr', 'hdr10', 'dv', 'sdr', 'web', 'webdl',
	'webrip', 'bluray', 'remux', 'bdrip', 'hdtv', 'dual', 'multi', 'audio', 'subs', 'sub', 'eng',
	'spa', 'esp', 'lat', 'cast', 'castellano', 'latino', 'spanish', 'english', 'ita', 'fre', 'ger',
	'aac', 'ac3', 'eac3', 'dts', 'ddp', 'ddp5', 'truehd', 'atmos', 'flac', 'opus', 'proper',
	'repack', 'internal', 'extended', 'unrated', 'complete', 'season', 'rip', 'dl', 'ts', 'nf',
	'amzn', 'dsnp', 'hmax', 'atvp', 'www', 'com', 'org', 'net', 'rarbg', 'eztv', 'yts', 'none'))


def release_group(name):
	try:
		if not name: return ''
		n = unquote(str(name)).strip()
		n = re.sub(r'(?i)\.(mkv|mp4|avi|ts|m2ts|webm|m4v)$', '', n)
		n = re.sub(r'\s+', ' ', n).strip(' .-_')
		m = re.search(r'-\s?([A-Za-z0-9@_]{2,15})\s*(?:\[[^\]]*\])?$', n)
		if not m:
			m = re.search(r'\[([A-Za-z0-9_]{2,15})\]$', n)
		if not m:
			m = re.search(r'\.([A-Za-z][A-Za-z0-9_]{1,14})$', n)
			# tras un punto solo cuenta si el nombre tiene pinta de release
			if m and not re.search(r'(?i)(19|20)\d{2}|\d{3,4}p|s\d{1,2}e\d{1,3}', n):
				m = None
		if not m: return ''
		grp = m.group(1)
		if grp.lower() in _RG_JUNK or not re.search(r'[A-Za-z]', grp): return ''
		if re.match(r'(?i)^(s\d{1,2}e\d{1,3}|\d{3,4}p|v\d+)$', grp): return ''
		if re.match(r'^[0-9A-Fa-f]{8}$', grp) and re.search(r'\d', grp): return '' # CRC32 de anime, no es grupo
		return grp.upper()
	except Exception:
		return ''
