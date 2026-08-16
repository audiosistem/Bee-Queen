# -*- coding: utf-8 -*-
import sys
from apis.punchplay_api import punchplay_search_my_lists
from modules import settings
from modules.kodi_utils import (add_items, set_content, set_category, end_directory, build_url, make_listitem,
	get_icon, get_addon_fanart, set_view_mode, MENU_FOLDER_CONTENT)

def search_punchplay_lists(params):
	def _builder():
		for item in results:
			try:
				media_ids = item.get('media_ids') or {}
				tmdb_id = media_ids.get('tmdb')
				if not tmdb_id: continue
				title = item.get('title') or 'Unknown'
				status_label = item.get('status_label', '')
				media_kind = item.get('media_kind', 'movies')
				if media_kind == 'anime': display = '%s | [I]%s · Anime[/I]' % (title, status_label)
				else: display = '%s | [I]%s[/I]' % (title, status_label)
				if media_kind == 'movies':
					url = build_url({'mode': 'extras_menu_choice', 'media_type': 'movie', 'tmdb_id': tmdb_id})
				else:
					url = build_url({'mode': 'build_season_list', 'tmdb_id': tmdb_id})
				listitem = make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': fanart, 'banner': fanart})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot('PunchPlay %s' % status_label)
				yield (url, listitem, True)
			except: pass
	handle = int(sys.argv[1])
	icon, fanart = get_icon('punchplay'), get_addon_fanart()
	search_title = params.get('key_id') or params.get('query') or ''
	try:
		if not settings.punchplay_user_active(): results = []
		else: results = punchplay_search_my_lists(search_title)
		add_items(handle, list(_builder()))
	except: pass
	set_content(handle, MENU_FOLDER_CONTENT)
	set_category(handle, search_title.capitalize())
	end_directory(handle)
	set_view_mode('view.main', MENU_FOLDER_CONTENT)
