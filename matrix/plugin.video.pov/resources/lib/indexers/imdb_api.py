import re
import requests
from caches.main_cache import cache_object
# from modules.kodi_utils import logger

api_url = 'https://api.imdbapi.dev'
base_url = 'https://www.imdb.com/%s'
timeout = 10.0
session = requests.Session()
session.mount('https://', requests.adapters.HTTPAdapter(pool_maxsize=100))

def people_get_imdb_id(actor_name, actor_tmdbID=None):
	name = actor_name.lower()
	url = 'https://sg.media-imdb.com/suggests/%s/%s.json' % (name[0], name.replace(' ', '%20'))
	string = 'imdb_people_get_imdb_id_%s' % name
	params = {'url': url, 'action': 'imdb_people_id', 'actor_tmdbID': actor_tmdbID, 'name': name}
	return cache_object(get_imdb, string, params, False, 8736)[0]

def imdb_tagged_images(imdb_id):
	url = '%s/names/%s/images' % (api_url, imdb_id)
	string = 'imdb_images_tagged_%s' % imdb_id
	params = {'url': url, 'action': 'imdb_tagged_images'}
	return cache_object(get_imdb, string, params, False, 168)[0]

def imdb_movie_year(imdb_id):
	url = 'https://v2.sg.media-imdb.com/suggestion/t/%s.json' % imdb_id
	string = 'imdb_movie_year_%s' % imdb_id
	params = {'url': url, 'action': 'imdb_movie_year'}
	return cache_object(get_imdb, string, params, False, 720)[0]

def get_imdb(params):
	imdb_list = []
	action = params['action']
	url = params['url']
	next_page = None
	if 'date' in params:
		from datetime import datetime, timedelta
		date_time = (datetime.utcnow() - timedelta(hours=5))
		for i in re.findall(r'date\[(\d+)\]', url):
			url = url.replace('date[%s]' % i, (date_time - timedelta(days = int(i))).strftime('%Y-%m-%d'))
	if action == 'imdb_people_id':
		try:
			actor_tmdbID = params['actor_tmdbID']
			name = params['name']
			if actor_tmdbID:
				from indexers.tmdb_api import tmdb_people_full_info
				imdb_list = tmdb_people_full_info(actor_tmdbID)['imdb_id']
			if not imdb_list:
				import json
				result = session.get(url, timeout=timeout).text
				result = json.loads(re.sub(r'^imdb\$.*?\(', '', result)[:-1])['d']
				imdb_list = next((i['id'] for i in result if i['l'].lower() == name))
		except: pass
	elif action == 'imdb_tagged_images':
		try:
			params = {'pageSize': 50}
			result = session.get(url, params=params, timeout=timeout)
			result = result.json()['images']
			imdb_list = [i for i in result if not i['type'] in ('still_frame', 'poster', 'product')]
		except: pass
	elif action == 'imdb_movie_year':
		result = session.get(url, timeout=timeout).json()
		try:
			result = next((int(i['y']) for i in result['d'] if 'y' in i))
			imdb_list = str(result)
		except: pass
	return (imdb_list, next_page)

def clear_imdb_cache(silent=False):
	from modules.kodi_utils import path_exists, clear_property, database_connect, maincache_db
	try:
		if not path_exists(maincache_db): return True
		dbcon = database_connect(maincache_db, isolation_level=None)
		dbcur = dbcon.cursor()
		dbcur.execute("""PRAGMA synchronous = OFF""")
		dbcur.execute("""PRAGMA journal_mode = OFF""")
		dbcur.execute("""SELECT id FROM maincache WHERE id LIKE ?""", ('imdb_%',))
		imdb_results = [str(i[0]) for i in dbcur.fetchall()]
		if not imdb_results: return True
		dbcur.execute("""DELETE FROM maincache WHERE id LIKE ?""", ('imdb_%',))
		for i in imdb_results: clear_property(i)
		return True
	except: return False

