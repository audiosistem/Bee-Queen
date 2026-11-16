
def years():
	from datetime import date
	return list(range(date.today().year, 1899, -1))

def networks():
	from modules.kodi_utils import get_addoninfo, json, open_file
	path = 'special://home/addons/%s/resources/networks.json'
	with open_file(path % get_addoninfo('id')) as file: return json.loads(file.read())

movie_certifications = 'G', 'PG', 'PG-13', 'R', 'NC-17', 'NR'
tvshow_certifications = 'tv-y', 'tv-y7', 'tv-g', 'tv-pg', 'tv-14', 'tv-ma'
media_lists = 'tmdb%', 'trakt%', 'mdb%', 'imdb%', 'pov%', 'POV%', 'subtitles%', 'https%'

movie_genres, tvshow_genres = {
	'Action':             ['28', 'genre_action.png'],
	'Adventure':          ['12', 'genre_adventure.png'],
	'Animation':          ['16', 'genre_animation.png'],
	'Comedy':             ['35', 'genre_comedy.png'],
	'Crime':              ['80', 'genre_crime.png'],
	'Documentary':        ['99', 'genre_documentary.png'],
	'Drama':              ['18', 'genre_drama.png'],
	'Family':             ['10751', 'genre_family.png'],
	'Fantasy':            ['14', 'genre_fantasy.png'],
	'History':            ['36', 'genre_history.png'],
	'Horror':             ['27', 'genre_horror.png'],
	'Music':              ['10402', 'genre_music.png'],
	'Mystery':            ['9648', 'genre_mystery.png'],
	'Romance':            ['10749', 'genre_romance.png'],
	'Science Fiction':    ['878', 'genre_scifi.png'],
	'TV Movie':           ['10770', 'genre_tv.png'],
	'Thriller':           ['53', 'genre_thriller.png'],
	'War':                ['10752', 'genre_war.png'],
	'Western':            ['37', 'genre_western.png']
}, {
	'Animation':          ['16', 'genre_animation.png'],
	'Action & Adventure': ['10759', 'genre_action.png'],
	'Comedy':             ['35', 'genre_comedy.png'],
	'Crime':              ['80', 'genre_crime.png'],
	'Documentary':        ['99', 'genre_documentary.png'],
	'Drama':              ['18', 'genre_drama.png'],
	'Family':             ['10751', 'genre_family.png'],
	'Kids':               ['10762', 'genre_kids.png'],
	'Mystery':            ['9648', 'genre_mystery.png'],
	'News':               ['10763', 'genre_news.png'],
	'Reality':            ['10764', 'genre_reality.png'],
	'Sci-Fi & Fantasy':   ['10765', 'genre_scifi.png'],
	'Soap':               ['10766', 'genre_soap.png'],
	'Talk':               ['10767', 'genre_talk.png'],
	'War & Politics':     ['10768', 'genre_war.png'],
	'Western':            ['37', 'genre_western.png']
}

meta_languages = {
	'English':             {'long': 'eng', 'short': 'en', 'iso': 'en'},
	'Arabic':              {'long': 'ara', 'short': 'ar', 'iso': 'ar'},
	'Arabic Saudi Arabia': {'long':    '', 'short':   '', 'iso': 'ar-SA'},
	'Bengali':             {'long': 'ben', 'short': 'bn', 'iso': 'bn'},
	'Bulgarian':           {'long': 'bul', 'short': 'bg', 'iso': 'bg'},
	'Chinese':             {'long': 'chi', 'short': 'zh', 'iso': 'zh'},
	'Croatian':            {'long': 'hrv', 'short': 'hr', 'iso': 'hr'},
	'Czech':               {'long': 'cze', 'short': 'cs', 'iso': 'cs'},
	'Danish':              {'long': 'dan', 'short': 'da', 'iso': 'da'},
	'Dutch':               {'long': 'dut', 'short': 'nl', 'iso': 'nl'},
	'Finnish':             {'long': 'fin', 'short': 'fi', 'iso': 'fi'},
	'French':              {'long': 'fre', 'short': 'fr', 'iso': 'fr'},
	'German':              {'long': 'ger', 'short': 'de', 'iso': 'de'},
	'Greek':               {'long': 'ell', 'short': 'el', 'iso': 'el'},
	'Hebrew':              {'long': 'heb', 'short': 'he', 'iso': 'he'},
	'Hindi':               {'long': 'hin', 'short': 'hi', 'iso': 'hi'},
	'Hungarian':           {'long': 'hun', 'short': 'hu', 'iso': 'hu'},
	'Icelandic':           {'long': 'ice', 'short': 'is', 'iso': 'is'},
	'Indonesian':          {'long': 'ind', 'short': 'id', 'iso': 'id'},
	'Italian':             {'long': 'ita', 'short': 'it', 'iso': 'it'},
	'Japanese':            {'long': 'jpn', 'short': 'ja', 'iso': 'ja'},
	'Korean':              {'long': 'kor', 'short': 'ko', 'iso': 'ko'},
	'Malay':               {'long': 'may', 'short': 'ms', 'iso': 'ms'},
	'Norwegian':           {'long': 'nor', 'short': 'no', 'iso': 'no'},
	'Persian':             {'long': 'per', 'short': 'fa', 'iso': 'fa'},
	'Polish':              {'long': 'pol', 'short': 'pl', 'iso': 'pl'},
	'Portuguese':          {'long': 'por', 'short': 'pt', 'iso': 'pt'},
	'Portuguese (Brazil)': {'long': 'pob', 'short': 'pb', 'iso': 'pt-BR'},
	'Punjabi':             {'long': 'pan', 'short': 'pa', 'iso': 'pa'},
	'Romanian':            {'long': 'rum', 'short': 'ro', 'iso': 'ro'},
	'Russian':             {'long': 'rus', 'short': 'ru', 'iso': 'ru'},
	'Serbian':             {'long': 'scc', 'short': 'sr', 'iso': 'sr'},
	'Slovenian':           {'long': 'slv', 'short': 'sl', 'iso': 'sl'},
	'Spanish':             {'long': 'spa', 'short': 'es', 'iso': 'es'},
	'Spanish (Mexico)':    {'long':    '', 'short':   '', 'iso': 'es-MX'},
	'Swedish':             {'long': 'swe', 'short': 'sv', 'iso': 'sv'},
	'Tagalog':             {'long': 'tgl', 'short': 'tl', 'iso': 'tl'},
	'Tamil':               {'long': 'tam', 'short': 'ta', 'iso': 'ta'},
	'Telugu':              {'long': 'tel', 'short': 'te', 'iso': 'te'},
	'Thai':                {'long': 'tha', 'short': 'th', 'iso': 'th'},
	'Turkish':             {'long': 'tur', 'short': 'tr', 'iso': 'tr'},
	'Ukrainian':           {'long': 'ukr', 'short': 'uk', 'iso': 'uk'},
	'Urdu':                {'long': 'urd', 'short': 'ur', 'iso': 'ur'},
	'Vietnamese':          {'long': 'vie', 'short': 'vi', 'iso': 'vi'}
}

oscar_winners = (
	1054867, 1064213, 872585, 545611, 776503, 581734, #2020s
	496243, 490132, 399055, 376867, 314365, 194662, 76203, 68734, 74643, 45269, #2010s
	12162, 12405, 6977, 1422, 1640, 70, 122, 1574, 453, 98, #2000s
	14, 1934, 597, 409, 197, 13, 424, 33, 274, 581, #1990s
	403, 380, 746, 792, 606, 279, 11050, 783, 9443, 16619, #1980s
	12102, 11778, 703, 1366, 510, 240, 9277, 238, 1051, 11202, #1970s
	3116, 17917, 10633, 874, 15121, 11113, 5769, 947, 1725, 284, #1960s
	665, 17281, 826, 2897, 15919, 654, 11426, 27191, 2769, 705, #1950s
	25430, 23383, 33667, 887, 28580, 17661, 27367, 289, 43266, 223, #1940s
	770, 34106, 43278, 43277, 12311, 3078, 56164, 33680, 42861, 143, #1930s
	65203, 28966, 631
)

