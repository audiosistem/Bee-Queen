import json
from urllib.parse import unquote
from windows import open_window
from indexers.tmdb_api import tmdb_people_info, tmdb_image_base
from menus.images import Images
from modules.kodi_utils import media_path, select_dialog, dialog, notification
# from modules.kodi_utils import logger

poster_empty = media_path('people.png')

def popular_people():
	Images().run({'mode': 'popular_people_image_results', 'page_no': 1})

def person_data_dialog(params):
	if 'query' in params: query = unquote(params['query'])
	else: query = None
	open_window(
		('windows.people', 'People'),
		'people.xml',
		query=query,
		actor_id=params.get('actor_id'),
		actor_name=params.get('actor_name'),
		actor_image=params.get('actor_image')
	)

def person_search(query=None):
	try: actors = tmdb_people_info(query)
	except: actors = None
	if not actors: return notification(32760)
	for item in actors:
		known_for_list = [i['title'] for i in item['known_for'] if 'title' in i and i['title']]
		item['icon'] = tmdb_image_base % ('h632', item['profile_path']) if item['profile_path'] else poster_empty
		item['line1'] = item['name']
		item['line2'] = ', '.join(known_for_list) if known_for_list else ''
	if len(actors) > 1:
		kwargs = {'items': json.dumps(actors), 'heading': 'POV', 'multi_line': 'true'}
		selection = select_dialog(actors, **kwargs)
		if selection is None: return
	else: selection = actors[0]
	actor = int(selection['id']), selection['name'], selection['icon']
	if not actor: return
	return person_data_dialog({'actor_id': actor[0], 'actor_name': actor[1], 'actor_image': actor[2]})

