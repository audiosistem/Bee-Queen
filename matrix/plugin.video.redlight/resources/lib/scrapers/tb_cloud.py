# -*- coding: utf-8 -*-
# Thanks to kodifitzwell for allowing me to borrow his code
import time
from apis.torbox_api import TorBox, TorBoxAPI
from modules import source_utils
from modules.utils import clean_file_name, normalize
from modules.settings import enabled_debrids_check, filter_by_name
from caches.settings_cache import get_setting
# from modules.kodi_utils import logger

class source:
	def __init__(self):
		self.scrape_provider = 'tb_cloud'
		self.sources = []
		self.extensions = source_utils.supported_video_extensions()

	def results(self, info):
		try:
			if not enabled_debrids_check('tb'): return source_utils.internal_results(self.scrape_provider, self.sources)
			self.scrape_results = []
			filter_title = filter_by_name(self.scrape_provider)
			self.media_type, title = info.get('media_type'), info.get('title')
			self.year = int(info.get('year') or 0)
			self.season, self.episode = info.get('season'), info.get('episode')
			self.tmdb_id = info.get('tmdb_id')
			self.title = title
			self.folder_query = source_utils.clean_title(normalize(title))
			self.aliases = source_utils.get_aliases_titles(info.get('aliases', []))
			self.title_queries = self._title_queries()
			self.scrape_deadline = time.time() + min(25, max(10, int(get_setting('redlight.results.timeout', '20'))))
			self._scrape_cloud_list('torrent')
			self._scrape_cloud_list('usenet')
			self._scrape_cloud_list('webdl')
			if not self.scrape_results: return source_utils.internal_results(self.scrape_provider, self.sources)
			def _process():
				for item in self.scrape_results:
					try:
						file_name = TorBoxAPI._torrent_file_label(item)
						if not file_name: continue
						file_name_latin = normalize(file_name) or file_name
						if self.media_type == 'episode':
							if not source_utils.seas_ep_filter(self.season, self.episode, file_name_latin): continue
						elif filter_title and not source_utils.check_title(title, file_name_latin, self.aliases, self.year, self.season, self.episode): continue
						display_name = clean_file_name(file_name).replace('html', ' ').replace('+', ' ').replace('-', ' ')
						file_id = TorBoxAPI._torrent_file_id(item)
						if file_id is None: continue
						try: size_bytes = int(item.get('size') or 0)
						except: size_bytes = 0
						size = round(size_bytes / 1073741824, 2) if size_bytes else 0.0
						size_label = '%.2f GB' % size if size_bytes else 'N/A'
						file_dl = '%d,%d' % (int(item['folder_id']), int(file_id))
						video_quality, details = source_utils.get_file_info(name_info=source_utils.release_info_format(file_name_latin))
						source_item = {'name': file_name, 'display_name': display_name, 'quality': video_quality, 'size': size, 'size_label': size_label, 'debrid': self.scrape_provider,
									'extraInfo': details, 'url_dl': file_dl, 'id': file_dl, 'downloads': False, 'direct': True, 'source': self.scrape_provider,
									'scrape_provider': self.scrape_provider, 'cloud_media_type': item.get('cloud_media_type', 'torrent')}
						yield source_item
					except: pass
			self.sources = list(_process())
		except Exception as e:
			from modules.kodi_utils import logger
			logger('torbox scraper Exception', str(e))
		source_utils.internal_results(self.scrape_provider, self.sources)
		return self.sources

	def _title_queries(self):
		queries = set()
		for candidate in [self.title] + list(self.aliases or []):
			if not candidate: continue
			for variant in (candidate, source_utils.normalize(candidate), normalize(candidate)):
				if not variant: continue
				query = source_utils.clean_title(variant)
				if query: queries.add(query)
		return queries

	def _contains_year(self, *texts):
		if not self.year: return False
		years = self._year_query_list()
		for text in texts:
			if not text: continue
			if any(str(y) in text for y in years):
				return True
		return False

	def _title_match(self, clean_file, folder_name):
		return any(q and (q in clean_file or (folder_name and q in folder_name)) for q in self.title_queries)

	def _folder_matched(self, folder_name, raw_folder):
		if self.media_type == 'movie':
			return self._contains_year(raw_folder) or self._title_match('', folder_name)
		if source_utils.seas_ep_filter(self.season, self.episode, raw_folder):
			return True
		return self._title_match('', folder_name)

	def _match_cloud_file(self, normalized, folder_name='', raw_file='', raw_folder='', folder_matched=False):
		if self.media_type == 'episode':
			return source_utils.seas_ep_filter(self.season, self.episode, normalized)
		if folder_matched:
			return True
		clean_file = source_utils.clean_title(normalized)
		title_match = self._title_match(clean_file, folder_name)
		year_match = self._contains_year(raw_file, raw_folder)
		return year_match or title_match

	def _video_file(self, file_item):
		label = TorBoxAPI._torrent_file_label(file_item)
		return label.lower().endswith(tuple(self.extensions))

	def _folder_might_match(self, raw_folder):
		raw = raw_folder or ''
		if self.media_type == 'movie':
			if self.year and self._contains_year(raw):
				return True
			folder_name = source_utils.clean_title(normalize(raw))
			return self._title_match('', folder_name)
		if self.folder_query and self.folder_query in source_utils.clean_title(normalize(raw)):
			return True
		if source_utils.seas_ep_filter(self.season, self.episode, raw):
			return True
		return False

	def _scrape_cloud_list(self, media_type):
		try:
			if time.time() >= self.scrape_deadline: return
			err, items = TorBox.mylist_items(media_type, fresh=False)
			if err: return
			append = self.scrape_results.append
			for item in items:
				if time.time() >= self.scrape_deadline: return
				if not TorBoxAPI._torrent_item_finished(item): continue
				folder_id = item['id']
				raw_folder = item.get('name') or ''
				folder_name = source_utils.clean_title(normalize(raw_folder))
				folder_matched = self._folder_matched(folder_name, raw_folder)
				if not folder_matched and not self._folder_might_match(raw_folder):
					continue
				files = item.get('files') or []
				if not files:
					files = TorBox.mylist_item_files(folder_id, media_type)
				if not files:
					continue
				for file in files:
					if time.time() >= self.scrape_deadline: return
					if not self._video_file(file): continue
					label = TorBoxAPI._torrent_file_label(file)
					normalized = normalize(label) or label
					if not self._match_cloud_file(normalized, folder_name, label, raw_folder, folder_matched): continue
					file_id = TorBoxAPI._torrent_file_id(file)
					if file_id is None: continue
					file_entry = dict(file)
					file_entry['id'] = file_id
					file_entry['folder_id'] = folder_id
					file_entry['cloud_media_type'] = media_type
					file_entry['folder_matched'] = folder_matched
					append(file_entry)
		except: return

	def _year_query_list(self):
		if not self.year: return tuple()
		return (str(self.year), str(self.year + 1), str(self.year - 1))
