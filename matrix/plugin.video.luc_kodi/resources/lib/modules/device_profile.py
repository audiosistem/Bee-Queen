# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on — device_profile.py (v1.0.90)

	Perfil de memoria del aparato, sin nada en pantalla (no confundir con el
	HUD de RAM descartado el 31-ago-2026). El servicio lo calcula al arrancar
	con dos infolabels que ya se comprobaron fiables en la Shield y en la
	tablet (System.FreeMemory y System.Memory(total)) y lo deja en la ventana
	Home. En perfil 'low' el addon gasta menos RAM en caches de conveniencia:
	la cache RAM de listas de fuentes guarda 6 titulos x 100 fuentes en vez de
	12 x 200. En perfil 'normal' no cambia nada.

	Idea tomada de TMDb Movies (_detect_platform), sin su parte de ajustar
	TorrServer, que aqui no aplica.
"""
import re

PROP = 'luc_kodi.device.profile'
LOW_FREE_MB = 350
LOW_TOTAL_MB = 2048


def _mb(label):
	try:
		txt = str(label or '').replace(',', '').replace('.', '')
		m = re.search(r'(\d+)\s*(GB|MB)?', txt, re.I)
		if not m: return 0
		v = int(m.group(1))
		return v * 1024 if (m.group(2) or '').upper() == 'GB' else v
	except Exception:
		return 0


def detect():
	"""Calcula y publica el perfil. Devuelve (perfil, libre_mb, total_mb)."""
	import xbmc
	from resources.lib.modules import control
	free = _mb(xbmc.getInfoLabel('System.FreeMemory'))
	total = _mb(xbmc.getInfoLabel('System.Memory(total)'))
	low = (free and free < LOW_FREE_MB) or (total and total < LOW_TOTAL_MB)
	profile = 'low' if low else 'normal'
	try: control.homeWindow.setProperty(PROP, profile)
	except Exception: pass
	return profile, free, total


def is_low():
	try:
		from resources.lib.modules import control
		return control.homeWindow.getProperty(PROP) == 'low'
	except Exception:
		return False
