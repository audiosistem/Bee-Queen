import json
from modules import kodi_utils, settings
# logger = kodi_utils.logger

ls, get_setting, media_path = kodi_utils.local_string, kodi_utils.get_setting, kodi_utils.media_path
show_busy_dialog, hide_busy_dialog = kodi_utils.show_busy_dialog, kodi_utils.hide_busy_dialog
select_dialog, confirm_dialog = kodi_utils.select_dialog, kodi_utils.confirm_dialog
notification, container_refresh = kodi_utils.notification, kodi_utils.container_refresh

class BaseListManager:
	setting_key = ''
	icon_file = ''
	heading_id = ''

	def __init__(self, params):
		self.params = params
		self.tmdb_id = params.get('tmdb_id')
		if self.tmdb_id: self.tmdb_id = int(self.tmdb_id)
		self.mediatype = params.get('mediatype')
		self.icon = media_path(self.icon_file)
		self.api = self._get_api()

	def _get_api(self):
		"""Must return the relevant API module."""
		raise NotImplementedError

	def check_auth(self):
		return bool(get_setting(self.setting_key, ''))

	def get_custom_lists(self):
		"""Fetch custom lists from the service."""
		return [], []

	def get_default_choices(self):
		"""Return hardcoded options like Watchlist, Collection, etc."""
		return []

	def handle_special_action(self, choice_id, choice_name):
		"""Handle specific non-sync menu items (like 'clear', 'new')."""
		return False

	def check_item_exists(self, choice_id):
		"""Check if current media item exists in the chosen list."""
		raise NotImplementedError

	def execute_toggle(self, choice, action_add):
		"""Call the API to either add or remove the item."""
		raise NotImplementedError

	def manage(self):
		if not self.check_auth(): return notification(32760)
		heading = ls(self.heading_id).replace('[B]', '').replace('[/B]', '')
		list1, list2 = self.get_custom_lists()
		choices = list1 + self.get_default_choices() + list2
		if not choices: return
		list_items = [{'line1': item[1], 'line2': item[2], 'icon': item[3]} for item in choices]
		choice = select_dialog([(i[0], i[1]) for i in choices], items=json.dumps(list_items), heading=heading)
		if choice is None: return
		special_result = self.handle_special_action(choice[0], choice[1])
		if special_result is not False: return special_result
		is_present = self.check_item_exists(choice[0])
		action_add = not is_present
		if not action_add:
			if not confirm_dialog(text='Remove from %s?' % choice[1]): return
		return self.execute_toggle(choice, action_add)

class TraktManager(BaseListManager):
	setting_key = 'trakt_user'
	icon_file = 'trakt.png'
	heading_id = 32198

	def _get_api(self):
		from indexers import trakt_api
		return trakt_api

	def get_custom_lists(self):
		list1 = [
			((item['ids']['trakt'], item['user']['ids']['slug'], item['ids']['slug']),
			 item['name'], '%s items' % item['item_count'],
			 '',
			 self.icon)
			for item in self.api.trakt_get_lists('my_lists')
		]
		list2 = [('new', 'Create a new list', '', self.icon)]
		return list1, list2

	def get_default_choices(self):
		choices = [(i.lower(), i, '', self.icon) for i in (ls(32500), ls(32453), ls(32499))]
		if self.mediatype == 'tvshow': choices.append(('dropped', 'Toggle Dropped', '', self.icon))
		return choices

	def handle_special_action(self, choice_id, choice_name):
		if 'new' in choice_id:
			show_busy_dialog()
			try: self.api.make_new_trakt_list(None)
			except: return notification(32574)
			finally: hide_busy_dialog()
			return self.manage()
		if 'dropped' in choice_id:
			args = self.params['tmdb_id'], 'shows', self.params['imdb_id']
			return self.api.hide_unhide_trakt_items(*args, 'dropped')
		return False

	def check_item_exists(self, choice_id):
		if any(x in choice_id for x in ('watchlist', 'favorites', 'collection')):
			list_items = self.api.trakt_fetch_collection_watchlist(choice_id, self.mediatype)
			return self.tmdb_id in {i['media_ids']['tmdb'] for i in list_items}
		list_items = self.api.get_trakt_list_contents('my_lists', *choice_id)
		return self.tmdb_id in {
			i['movie']['ids']['tmdb'] if i['type'] == 'movie' else i['show']['ids']['tmdb']
			for i in list_items
		}

	def execute_toggle(self, choice, action_add):
		content = 'shows' if self.mediatype == 'tvshow' else 'movies'
		data = {content: [{'ids': {'tmdb': self.tmdb_id}}]}
		if any(x in choice[0] for x in ('watchlist', 'favorites', 'collection')):
			if action_add: return self.api.add_to_sync(choice[0], data)
			else: return self.api.remove_from_sync(choice[0], data)
		if action_add: return self.api.add_to_list(choice[0][1], choice[0][2], data)
		return self.api.remove_from_list(choice[0][1], choice[0][2], data)

class MdbListManager(BaseListManager):
	setting_key = 'mdblist_user'
	icon_file = 'mdblist.png'
	heading_id = 32200

	def _get_api(self):
		from indexers import mdblist_api
		return mdblist_api

	def get_custom_lists(self):
		list1 = [
			(str(item['id']), item['name'], '%s items' % item['items'], self.icon)
			for item in self.api.mdbl_get_lists('my_lists') if not item['dynamic']
		]
		list2 = [('new', 'Create a new list', '', self.icon)]
		return list1, list2

	def get_default_choices(self):
		choices = [(i.lower(), i, '', self.icon) for i in (ls(32500), ls(32499))]
		if self.mediatype == 'tvshow': choices.append(('dropped', 'Toggle Dropped', '', self.icon))
		return choices

	def handle_special_action(self, choice_id, choice_name):
		if 'new' in choice_id:
			show_busy_dialog()
			try: self.api.make_new_mdbl_list(None)
			except: return notification(32574)
			finally: hide_busy_dialog()
			return self.manage()
		if 'dropped' in choice_id:
			args = self.params['tmdb_id'], 'shows', self.params['imdb_id']
			return self.api.hide_unhide_mdbl_items(*args, 'dropped')
		return False

	def check_item_exists(self, choice_id):
		if 'collection' in choice_id: list_items = self.api.mdblist_collection('all', None)
		elif 'watchlist' in choice_id: list_items = self.api.mdblist_watchlist('all', None)
		else: list_items = self.api.get_mdbl_list_contents('my_lists', choice_id)
		return self.tmdb_id in {i['id'] for i in list_items}

	def execute_toggle(self, choice, action_add):
		if 'collection' in choice[0]:
			data = {'shows' if self.mediatype == 'tvshow' else 'movies': [{'ids': {'tmdb': self.tmdb_id}}]}
			return self.api.add_to_collection(data) if action_add else self.api.remove_from_collection(data)
		data = {'shows' if self.mediatype == 'tvshow' else 'movies': [{'tmdb': self.tmdb_id}]}
		return self.api.add_to_list(choice[0], data) if action_add else self.api.remove_from_list(choice[0], data)

class TmdbManager(BaseListManager):
	setting_key = 'tmdb.token'
	icon_file = 'tmdb.png'

	def __init__(self, params):
		super().__init__(params)
		self.mediatype = 'tv' if params.get('mediatype') == 'tvshow' else 'movie'
		self.heading_id = self.api.tmdblist_heading

	def _get_api(self):
		from indexers import tmdb_api
		return tmdb_api

	def get_default_choices(self):
		if self.params.get('trakt_list_name') or self.params.get('mdbl_list_name'): return []
		return [(i.lower(), i, '', self.icon) for i in (ls(32500), ls(32453))]

	def get_custom_lists(self):
		res, tmdb_img_base = settings.get_resolution(), self.api.tmdb_image_base
		list1 = [
			(str(item['id']),
			 item['name'],
			 '%s items' % item['number_of_items'],
			 tmdb_img_base % (res['poster'], item['poster_path']) if item['poster_path'] else self.icon)
			for item in self.api.user_lists()
		]
		list_name = self.params.get('trakt_list_name') or self.params.get('mdbl_list_name') or ''
		list2 = [('new', 'Create a new list', list_name, self.icon), ('clear', 'Clear list cache', '', self.icon)]
		return list1, list2

	def handle_special_action(self, choice_id, choice_name):
		if 'clear' in choice_id:
			self.api.clear_tmdbl_cache()
			return self.manage()
		if 'new' in choice_id:
			show_busy_dialog()
			try:
				list_name = self.params.get('trakt_list_name') or self.params.get('mdbl_list_name') or ''
				result = self.api.list_create(list_name)
				if result and result.get('success'): self.api.clear_tmdbl_cache()
			except: return notification(32574)
			finally: hide_busy_dialog()
			return self.manage()
		if 'trakt_list_id' in self.params or 'mdbl_list_id' in self.params:
			func = self.api.import_trakt_list if 'trakt_list_id' in self.params else self.api.import_mdbl_list
			return func({**self.params, 'list_id': choice_id})
		return False

	def check_item_exists(self, choice_id):
		if choice_id in ('watchlist', 'favorites'):
			list_items = self.api.watchlist(self.mediatype) if choice_id == 'watchlist' else self.api.favorites(self.mediatype)
			return self.tmdb_id in {i['id'] for i in list_items}
		status = self.api.list_status(choice_id, self.mediatype, self.tmdb_id)
		return bool(status and status.get('success'))

	def execute_toggle(self, choice, action_add):
		if choice[0] in ('watchlist', 'favorites'):
			list_type = 'favorite' if choice[0] == 'favorites' else 'watchlist'
			data = {'media_type': self.mediatype, 'media_id': self.tmdb_id, list_type: action_add}
			success = self.api.add_to_watchlist_favorites(data, list_type).get('success')
		else:
			data = {'items': [{'media_type': self.mediatype, 'media_id': self.tmdb_id}]}
			func = self.api.list_add_items if action_add else self.api.list_remove_items
			success = func(choice[0], data).get('success')
		if success:
			self.api.clear_tmdbl_cache()
			if not action_add: container_refresh()
			return notification(32576)
		return notification(32574)

def update_tmdb_list(params):
	from indexers import tmdb_api
	if params.get('action', '') == 'delete':
		if not kodi_utils.confirm_dialog(): return
		tmdb_api.list_delete(params['list_id'])
	tmdb_api.clear_tmdbl_cache()
	kodi_utils.container_refresh()

def artwork_choice_tmdb_list(key, list_id, list_title, resolution, icon):
	from indexers import tmdb_api
	tmdb_image_base = tmdb_api.tmdb_image_base
	path = 'poster_path' if key == 'poster' else 'backdrop_path'
	choices = [
		(item[path], item['title'] if item['media_type'] == 'movie' else item['name'],
		tmdb_image_base % (resolution[key], item[path]) if item[path] else icon)
		for item in tmdb_api.list_details(list_id)
	]
	choices += [('clear', 'Clear', icon)]
	list_items = [{'line1': item[1], 'line2': item[0], 'icon': item[2]} for item in choices]
	kwargs = {'items': json.dumps(list_items), 'heading': list_title, 'enumerate': 'true'}
	return kodi_utils.select_dialog([i[0] for i in choices], **kwargs)

def edit_tmdb_list(params):
	from indexers import tmdb_api
	res, tmdb_img_base = settings.get_resolution(), tmdb_api.tmdb_image_base
	default_icon = kodi_utils.media_path('tmdb.png')
	heading = ls(tmdb_api.tmdblist_heading).replace('[B]', '').replace('[/B]', '')

	def get_icon(key, val):
		if key in ('poster', 'fanart') and val not in ('clear', 'None'): return tmdb_img_base % (res[key], val)
		return default_icon

	while True:
		is_pub = 'true' if params.get('public') in ('true', '1') else 'false'
		choices = [
			('name', params['name']), ('poster', params['poster']),  ('fanart', params['fanart']),
			('public', is_pub),       ('save', 'Save and Exit'),     ('cancel', 'Cancel')
		]
		list_items = [{'line1': v, 'line2': k, 'icon': get_icon(k, v)} for k, v in choices]
		choice = kodi_utils.select_dialog([c[0] for c in choices], items=json.dumps(list_items), heading=heading)
		if choice in ('cancel', None): return
		if choice == 'name':
			name = kodi_utils.dialog.input('New List Name', defaultt=params['name'])
			if name.strip(): params['name'] = name.strip()
		elif choice == 'public':
			text = 'Make %s Private?' % params['name']
			params['public'] = 'false' if kodi_utils.confirm_dialog(text=text) else 'true'
		elif choice in ('poster', 'fanart'):
			art = artwork_choice_tmdb_list(choice, params['list_id'], params['name'], res, default_icon)
			if art is not None: params[choice] = art
		elif choice == 'save':
			data = {
				'name': params['name'],
				'poster_path': '' if params['poster'] == 'clear' else params['poster'],
				'backdrop_path': '' if params['fanart'] == 'clear' else params['fanart'],
				'public': is_pub,
			}
			data = {k: v for k, v in data.items() if v not in ('None', None)}
			success = tmdb_api.list_update(params['list_id'], data).get('success')
			if not success: kodi_utils.notification(32574)
			tmdb_api.clear_tmdbl_cache()
			kodi_utils.container_refresh()
			return kodi_utils.notification(32576)


