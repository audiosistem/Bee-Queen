# -*- coding: utf-8 -*-
# Python 3

import json
import re

from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.config import cConfig
from urllib.parse import quote_plus

class cTMDB:
    TMDB_GENRES = {12: 'Abenteuer', 14: 'Fantasy', 16: 'Animation', 18: 'Drama', 27: 'Horror', 28: 'Action', 35: 'Komödie', 36: 'Historie', 37: 'Western', 53: 'Thriller', 80: 'Krimi', 99: 'Dokumentarfilm', 878: 'Science Fiction', 9648: 'Mystery', 10402: 'Musik', 10749: 'Liebesfilm', 10751: 'Familie', 10752: 'Kriegsfilm', 10759: 'Action & Adventure', 10762: 'Kids', 10763: 'News', 10764: 'Reality', 10765: 'Sci-Fi & Fantasy', 10766: 'Soap', 10767: 'Talk', 10768: 'War & Politics', 10770: 'TV-Film'}
    URL = 'https://api.themoviedb.org/3/'
    URL_TRAILER = 'plugin://plugin.video.youtube/play/?video_id=%s'
    TMDB_LANGUAGE = cConfig().getSetting('tmdb_lang')
    
    def __init__(self, api_key='', lang=TMDB_LANGUAGE):
        self.api_key = '86dd18b04874d9c94afadde7993d94e3'
        self.lang = lang
        self.poster = 'https://image.tmdb.org/t/p/%s' % cConfig().getSetting('poster_tmdb')
        self.fanart = 'https://image.tmdb.org/t/p/%s' % cConfig().getSetting('backdrop_tmdb')
        

    def search_movie_name(self, name, year='', page=1, advanced='false'):
        name = re.sub(' +', ' ', name)
        if year:
        #    term = quote_plus(name) + '&year=' + year
            name = re.sub(year, ' ', name) #Wenn das Jahr im Namen auftaucht dann das Jahr löschen
        #else:
        #    term = quote_plus(name)
        term = quote_plus(name)
        meta = self._call('search/movie', 'query=' + term + '&page=' + str(page))
        if 'errors' not in meta and 'status_code' not in meta:
            #if 'total_results' in meta and meta['total_results'] == 0 and year:
            #    meta = self.search_movie_name(name, '', advanced=advanced)
            if 'total_results' in meta and meta['total_results'] != 0:
                movie = ''
                if meta['total_results'] == 1:
                    movie = meta['results'][0]
                else:
                    for searchMovie in meta['results']:
                        try: # Exception Handling notwendig da TMDb in seltenen Fällen keine genre_ids mitliefert
                            if searchMovie['genre_ids'] and 99 not in searchMovie['genre_ids']:
                                if searchMovie['title'].lower() == name.lower():
                                    movie = searchMovie
                                    break
                        except Exception:
                            break
                    if not movie:
                        for searchMovie in meta['results']:
                            if searchMovie['genre_ids'] and 99 not in searchMovie['genre_ids']:
                                if year:
                                    if 'release_date' in searchMovie and searchMovie['release_date']:
                                        release_date = searchMovie['release_date']
                                        yy = release_date[:4]
                                        if int(year) - int(yy) > 1:
                                            continue
                                movie = searchMovie
                                break
                    if not movie:
                        movie = meta['results'][0]
                if advanced == 'true':
                    tmdb_id = movie['id']
                    meta = self.search_movie_id(tmdb_id)
                else:
                    meta = movie
        else:
            meta = {}
        return meta

    def search_movie_id(self, movie_id, append_to_response='append_to_response=trailers,credits'):
        result = self._call('movie/' + str(movie_id), append_to_response)
        result['tmdb_id'] = movie_id
        return result

    def search_tvshow_name(self, name, year='', page=1, genre='', advanced='false'):
        name = name.lower()
        if '- staffel' in name:
            name = re.sub('\s-\s\wtaffel[^>]([1-9\-]+)', '', name)
        elif 'staffel' in name:
            name = re.sub('\s\wtaffel[^>]([1-9\-]+)', '', name)
        if year:
        #    term = quote_plus(name) + '&year=' + year
            name = re.sub(year, ' ', name) #Wenn das Jahr im Namen auftaucht dann das Jahr löschen
        #else:
        #    term = quote_plus(name)
        term = quote_plus(name)
        meta = self._call('search/tv', 'query=' + term + '&page=' + str(page))
        if 'errors' not in meta and 'status_code' not in meta:
            #if 'total_results' in meta and meta['total_results'] == 0 and year:
            #    meta = self.search_tvshow_name(name, '', advanced=advanced)
            if 'total_results' in meta and meta['total_results'] != 0:
                movie = ''
                if meta['total_results'] == 1:
                    movie = meta['results'][0]
                else:
                    for searchMovie in meta['results']:
                        if genre == '' or genre in searchMovie['genre_ids']:
                            movieName = searchMovie['name']
                            if movieName.lower() == name.lower():
                                movie = searchMovie
                                break
                    if not movie:
                        for searchMovie in meta['results']:
                            if genre and genre in searchMovie['genre_ids']:
                                if year:
                                    if 'release_date' in searchMovie and searchMovie['release_date']:
                                        release_date = searchMovie['release_date']
                                        yy = release_date[:4]
                                        if int(year) - int(yy) > 1:
                                            continue
                                movie = searchMovie
                                break
                    if not movie:
                        movie = meta['results'][0]
                if advanced == 'true':
                    tmdb_id = movie['id']
                    meta = self.search_tvshow_id(tmdb_id)
                else:
                    meta = movie
        else:
            meta = {}
        return meta

    def search_tvshow_id(self, show_id, append_to_response='append_to_response=external_ids,videos,credits'):
        result = self._call('tv/' + str(show_id), append_to_response)
        result['tmdb_id'] = show_id
        return result

    def get_meta(self, media_type, name, imdb_id='', tmdb_id='', year='', season='', episode='', advanced='false'):
        name = re.sub(' +', ' ', name)
        meta = {}
        if media_type == 'movie':
            if tmdb_id:
                meta = self.search_movie_id(tmdb_id)
            elif name:
                meta = self.search_movie_name(name, year, advanced=advanced)
        elif media_type == 'tvshow':
            if tmdb_id:
                meta = self.search_tvshow_id(tmdb_id)
            elif name:
                meta = self.search_tvshow_name(name, year, advanced=advanced)
        if meta and 'id' in meta:
            meta = self._format(meta, name)
        return meta

    def getUrl(self, url, page=1, term=''):
        try:
            if term:
                term = term + '&page=' + str(page)
            else:
                term = 'page=' + str(page)
            result = self._call(url, term)
        except Exception:
            return False
        return result

    def _call(self, action, append_to_response=''):
        url = '%s%s?language=%s&api_key=%s' % (self.URL, action, self.lang, self.api_key)
        if append_to_response:
            url += '&%s' % append_to_response
        if 'person' in url:
            url = url.replace('&page=', '')
        oRequestHandler = cRequestHandler(url, ignoreErrors=True)
        name = oRequestHandler.request()
        try:
            data = json.loads(name)
        except Exception:
            return {}
        if 'status_code' in data and data['status_code'] == 34:
            return {}
        return data

    def getGenresFromIDs(self, genresID):
        sGenres = []
        for gid in genresID:
            genre = self.TMDB_GENRES.get(gid)
            if genre:
                sGenres.append(genre)
        return sGenres

    def getLanguage(self, Language):
        iso_639 = {'en': 'English', 'de': 'German', 'fr': 'French', 'it': 'Italian', 'nl': 'Nederlands', 'sv': 'Swedish', 'cs': 'Czech', 'da': 'Danish', 'fi': 'Finnish', 'pl': 'Polish', 'es': 'Spanish', 'el': 'Greek', 'tr': 'Turkish', 'uk': 'Ukrainian', 'ru': 'Russian', 'kn': 'Kannada', 'ga': 'Irish', 'hr': 'Croatian', 'hu': 'Hungarian', 'ja': 'Japanese', 'no': 'Norwegian', 'id': 'Indonesian', 'ko': 'Korean', 'pt': 'Portuguese', 'lv': 'Latvian', 'lt': 'Lithuanian', 'ro': 'Romanian', 'sk': 'Slovak', 'sl': 'Slovenian', 'sq': 'Albanian', 'sr': 'Serbian', 'th': 'Thai', 'vi': 'Vietnamese', 'bg': 'Bulgarian', 'fa': 'Persian', 'hy': 'Armenian', 'ka': 'Georgian', 'ar': 'Arabic', 'af': 'Afrikaans', 'bs': 'Bosnian', 'zh': 'Chinese', 'cn': 'Chinese', 'hi': 'Hindi'}
        if Language in iso_639:
            return iso_639[Language]
        else:
            return Language

    def get_meta_episodes(self, media_type, name, tmdb_id='', season='', episode='', advanced='false'):
        meta = {}
        if media_type == 'episode' and tmdb_id and season and episode:
            url = '%stv/%s/season/%s?api_key=%s&language=de' % (self.URL, tmdb_id, season, self.api_key)
            Data = cRequestHandler(url, ignoreErrors=True).request()
            if Data:
                try:
                    meta = json.loads(Data)
                    if 'status_code' in meta and meta['status_code'] == 34:
                        meta = {}
                except Exception:
                    meta = {}
        if 'episodes' in meta:
            for e in meta['episodes']:
                if 'episode_number':
                    if e['episode_number'] == int(episode):
                        return self._format_episodes(e, name)
        else:
            return {}

    def _format_episodes(self, meta, name):
        _meta = {}
        if 'air_date' in meta and meta['air_date']:
            _meta['aired'] = meta['air_date']
        if 'episode_number' in meta and meta['episode_number']:
            _meta['episode'] = meta['episode_number']
        if 'name' in meta and meta['name']:
            _meta['title'] = meta['name']
        if 'overview' in meta and meta['overview']:
            _meta['plot'] = meta['overview']
        if 'production_code' in meta and meta['production_code']:
            _meta['code'] = str(meta['production_code'])
        if 'season_number' in meta and meta['season_number']:
            _meta['season'] = meta['season_number']
        if 'still_path' in meta and meta['still_path']:
            _meta['cover_url'] = self.poster + meta['still_path']
        if 'vote_average' in meta and meta['vote_average']:
            _meta['rating'] = meta['vote_average']
        if 'vote_count' in meta and meta['vote_count']:
            _meta['votes'] = meta['vote_count']
        if 'crew' in meta and meta['crew']:
            _meta['writer'] = ''
            _meta['director'] = ''

            for crew in meta['crew']:
                if crew['department'] == 'Directing':
                    if _meta['director'] != '':
                        _meta['director'] += ' / '
                    _meta['director'] += '%s: %s' % (crew['job'], crew['name'])
                elif crew['department'] == 'Writing':
                    if _meta['writer'] != '':
                        _meta['writer'] += ' / '
                    _meta['writer'] += '%s: %s' % (crew['job'], crew['name'])
        if 'guest_stars' in meta and meta['guest_stars']:
            licast = []
            for c in meta['guest_stars']:
                licast.append((c['name'], c['character'], self.poster + str(c['profile_path'])))
            _meta['cast'] = licast
        return _meta

    def _format(self, meta, name):
        _meta = {}
        _meta['genre'] = ''
        if 'id' in meta:
            _meta['tmdb_id'] = meta['id']
        if 'backdrop_path' in meta and meta['backdrop_path']:
            _meta['backdrop_url'] = self.fanart + str(meta['backdrop_path'])
        if 'original_language' in meta and meta['original_language']:
            _meta['country'] = self.getLanguage(meta['original_language'])
        if 'original_title' in meta and meta['original_title']:
            _meta['originaltitle'] = meta['original_title']
        elif 'original_name' in meta and meta['original_name']:
            _meta['originaltitle'] = meta['original_name']
        if 'overview' in meta and meta['overview']:
            _meta['plot'] = meta['overview']
        if 'poster_path' in meta and meta['poster_path']:
            _meta['cover_url'] = self.poster + str(meta['poster_path'])
        if 'release_date' in meta and meta['release_date']:
            _meta['premiered'] = meta['release_date']
        elif 'first_air_date' in meta and meta['first_air_date']:
            _meta['premiered'] = meta['first_air_date']
        if 'premiered' in _meta and _meta['premiered'] and len(_meta['premiered']) == 10:
            _meta['year'] = int(_meta['premiered'][:4])
        if 'budget' in meta and meta['budget']:
            _meta['budget'] = '{:,} $'.format(meta['budget'])
        if 'revenue' in meta and meta['revenue']:
            _meta['revenue'] = '{:,} $'.format(meta['revenue'])
        if 'status' in meta and meta['status']:
            _meta['status'] = meta['status']
        duration = 0
        if 'runtime' in meta and meta['runtime']:
            duration = int(meta['runtime'])
        elif 'episode_run_time' in meta and meta['episode_run_time']:
            duration = int(meta['episode_run_time'][0])
        if duration > 1:
            _meta['duration'] = duration
        if 'tagline' in meta and meta['tagline']:
            _meta['tagline'] = meta['tagline']
        if 'vote_average' in meta and meta['vote_average']:
            _meta['rating'] = meta['vote_average']
        if 'vote_count' in meta and meta['vote_count']:
            _meta['votes'] = meta['vote_count']
        if 'genres' in meta and meta['genres']:
            for genre in meta['genres']:
                if _meta['genre'] == '':
                    _meta['genre'] += genre['name']
                else:
                    _meta['genre'] += ' / ' + genre['name']
        elif 'genre_ids' in meta and meta['genre_ids']:
            genres = self.getGenresFromIDs(meta['genre_ids'])
            for genre in genres:
                if _meta['genre'] == '':
                    _meta['genre'] += genre
                else:
                    _meta['genre'] += ' / ' + genre
        if 'production_companies' in meta and meta['production_companies']:
            _meta['studio'] = ''
            for studio in meta['production_companies']:
                if _meta['studio'] == '':
                    _meta['studio'] += studio['name']
                else:
                    _meta['studio'] += ' / ' + studio['name']
        if 'credits' in meta and meta['credits']:
            strmeta = str(meta['credits'])
            listCredits = eval(strmeta)
            casts = listCredits['cast']
            crews = []
            if len(casts) > 0:
                licast = []
                if 'crew' in listCredits:
                    crews = listCredits['crew']
                if len(crews) > 0:
                    _meta['credits'] = "{'cast': " + str(casts) + ", 'crew': " + str(crews) + "}"
                    for cast in casts:
                        licast.append((cast['name'], cast['character'], self.poster + str(cast['profile_path']), str(cast['id'])))
                    _meta['cast'] = licast
                else:
                    _meta['credits'] = "{'cast': " + str(casts) + '}'
            if len(crews) > 0:
                _meta['writer'] = ''
                for crew in crews:
                    if crew['job'] == 'Director':
                        _meta['director'] = crew['name']
                    elif crew['department'] == 'Writing':
                        if _meta['writer'] != '':
                            _meta['writer'] += ' / '
                        _meta['writer'] += '%s: %s' % (crew['job'], crew['name'])
                    elif crew['department'] == 'Production' and 'Producer' in crew['job']:
                        if _meta['writer'] != '':
                            _meta['writer'] += ' / '
                        _meta['writer'] += '%s: %s' % (crew['job'], crew['name'])
        if 'trailers' in meta and meta['trailers']:
            if 'youtube' in meta['trailers']:
                trailers = ''
                for t in meta['trailers']['youtube']:
                    if t['type'] == 'Trailer':
                        trailers = self.URL_TRAILER % t['source']
                if trailers:
                    _meta['trailer'] = trailers
        elif 'videos' in meta and meta['videos']:
            if 'results' in meta['videos']:
                trailers = ''
                for t in meta['videos']['results']:
                    if t['type'] == 'Trailer' and t['site'] == 'YouTube':
                        trailers = self.URL_TRAILER % t['key']
                if trailers:
                    _meta['trailer'] = trailers
        return _meta
