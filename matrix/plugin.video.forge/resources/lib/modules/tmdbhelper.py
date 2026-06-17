# -*- coding: utf-8 -*-
"""TMDBHelper integration helpers.

Forge exposes a keyless ``playback.media`` mode (see ``kodi_utils.player_check``) so external
addons such as TMDBHelper (``plugin.video.themoviedb.helper``) can drive playback. This module
installs the matching TMDBHelper *player* config files into TMDBHelper's userdata folder so the
"Play with..." dialog offers Forge.
"""

import os

from modules import kodi_utils

TMDBHELPER_ID = "plugin.video.themoviedb.helper"
PLAYERS_DIR = "special://profile/addon_data/%s/players/" % TMDBHELPER_ID
PLAYER_FILES = ("forge.auto.json", "forge.select.json")


def install_player():
	"""Copy the bundled Forge player configs into TMDBHelper's players folder."""
	if not kodi_utils.get_visibility("System.HasAddon(%s)" % TMDBHELPER_ID):
		kodi_utils.ok_dialog(
			"TMDBHelper Not Found",
			"The TMDBHelper addon (%s) is not installed." % TMDBHELPER_ID,
		)
		return
	dest_dir = kodi_utils.translate_path(PLAYERS_DIR)
	if not kodi_utils.path_exists(dest_dir):
		kodi_utils.make_directories(dest_dir)
	source_dir = os.path.join(kodi_utils.addon_path(), "resources", "data", "tmdbhelper")
	copied = []
	for name in PLAYER_FILES:
		source = os.path.join(source_dir, name)
		destination = os.path.join(dest_dir, name)
		if kodi_utils.path_exists(destination):
			kodi_utils.delete_file(destination)
		if kodi_utils.copy_file(source, destination):
			copied.append(name)
	if len(copied) == len(PLAYER_FILES):
		kodi_utils.notification("TMDBHelper Player Installed — restart Kodi to use Forge")
	else:
		kodi_utils.notification("TMDBHelper Player Install Failed")
