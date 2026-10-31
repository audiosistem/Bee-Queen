
def years():
	from datetime import date
	return list(range(date.today().year, 1899, -1))

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

networks = (
	{'logo': '/ptSTdU4GPNJ1M8UVEOtA0KgtuNk.png', 'id': 129,  'name': 'A&E'},
	{'logo': '/2uy2ZWcplrSObIyt4x0Y9rkG6qO.png', 'id': 2,    'name': 'ABC'},
	{'logo': '/dwHtgdgA2G69Anoq1zWxcrzYUGi.png', 'id': 2697, 'name': 'Acorn TV'},
	{'logo': '/tHZPHOLc6iF27G34cAZGPsMtMSy.png', 'id': 80,   'name': 'Adult Swim'},
	{'logo': '/w7HfLNm9CWwRmAMU58udl2L7We7.png', 'id': 1024, 'name': 'Amazon'},
	{'logo': '/pmvRmATOCaDykE6JrVoeYxlFHw3.png', 'id': 174,  'name': 'AMC'},
	{'logo': '/m3KrDu1g96YByhH0wp4OvyghgsG.png', 'id': 91,   'name': 'Animal Planet'},
	{'logo': '/bngHRFi794mnMq34gfVcm9nDxN1.png', 'id': 2552, 'name': 'Apple TV +'},
	{'logo': '/fERjndErEpveJmQZccJbJDi93rj.png', 'id': 173,  'name': 'AT-X'},
	{'logo': '/tmhbFiRpgJFSmza9GTQam8ICyHp.png', 'id': 251,  'name': 'Audience'},
	{'logo': '/5sFjaa1lYQgcrfYHScn2GaezmN.png',  'id': 493,  'name': 'BBC America'},
	{'logo': '/uJjcCg3O4DMEjM0xtno9OWFciRP.png', 'id': 4,    'name': 'BBC One'},
	{'logo': '/7HVPn1p2w1nC5oRKBehXVHpss7e.png', 'id': 332,  'name': 'BBC Two'},
	{'logo': '/22fRhj8xFPbiexrJwiAOcDEIrS.png',  'id': 3,    'name': 'BBC Three'},
	{'logo': '/AgsOSxGvfxIonhPgrfkWCmsOKfA.png', 'id': 100,  'name': 'BBC Four'},
	{'logo': '/gaouRlJrfZlEA5EPHhO5qqZ1Fgu.png', 'id': 24,   'name': 'BET'},
	{'logo': '/wX5HsfS47u6UUCSpYXqaQ1x2qdu.png', 'id': 74,   'name': 'Bravo'},
	{'logo': '/c5OC6oVCg6QP4eqzW6XIq17CQjI.png', 'id': 56,   'name': 'Cartoon Network'},
	{'logo': '/rSWD2WoY26KJmOw7QHvZjC5OEWG.png', 'id': 1709, 'name': 'CBS All Access'},
	{'logo': '/wju8KhOUsR5y4bH9p3Jc50hhaLO.png', 'id': 16,   'name': 'CBS'},
	{'logo': '/7Ai64ZDaVbGDtm7f0QSZAKohjk4.png', 'id': 26,   'name': 'Channel 4'},
	{'logo': '/tAOMutfVve2or2LTYQfIa42sc33.png', 'id': 99,   'name': 'Channel 5'},
	{'logo': '/6mSHSquNpfLgDdv6VnOOvC5Uz2h.png', 'id': 359,  'name': 'Cinemax'},
	{'logo': '/6ooPjtXufjsoskdJqj6pxuvHEno.png', 'id': 47,   'name': 'Comedy Central'},
	{'logo': '/bR8S6Fjv3VGtEKyKF5lvvRJ5xfw.png', 'id': 928,  'name': 'Crackle'},
	{'logo': '/uPoKSf3GtME7IZz4alnoWvc0nWx.png', 'id': 110,  'name': 'CTV'},
	{'logo': '/eOL4PkiC0zkDpxKFQhBnmCtwx5p.png', 'id': 2243, 'name': 'DC Universe'},
	{'logo': '/tmttRFo2OiXQD0EHMxxlw8EzUuZ.png', 'id': 64,   'name': 'Discovery Channel'},
	{'logo': '/9AxUB1RdRnm0r5ki8Thb69Jo9Ma.png', 'id': 54,   'name': 'Disney Channel'},
	{'logo': '/nKM9EnV7jTpt3MKRbhBusJ03lAY.png', 'id': 44,   'name': 'Disney XD'},
	{'logo': '/1edZOYAfoyZyZ3rklNSiUpXX30Q.png', 'id': 2739, 'name': 'Disney+'},
	{'logo': '/ptpx2Ag52sYJG6LiX9zBlnKsQOS.png', 'id': 76,   'name': 'E!'},
	{'logo': '/A7k2PSYy38NzDPDhajalNWcMQ10.png', 'id': 136,  'name': 'E4'},
	{'logo': '/1DSpHrWyOORkL9N2QHX7Adt31mQ.png', 'id': 19,   'name': 'FOX'},
	{'logo': '/jk2Z7WH6JnHSZrxouYh4sireM3a.png', 'id': 1267, 'name': 'Freeform'},
	{'logo': '/9JTL7HcaiVxq7M6eu5m7giFqaxR.png', 'id': 384,  'name': 'Hallmark Channel'},
	{'logo': '/nmU0UMDJB3dRRQSTUqawzF2Od1a.png', 'id': 3186, 'name': 'HBO Max'},
	{'logo': '/tuomPhY2UtuPTqqFnKMVHvSb724.png', 'id': 49,   'name': 'HBO'},
	{'logo': '/tzTtKdQ7vC2FkBvJDUErOhBPdKJ.png', 'id': 210,  'name': 'HGTV'},
	{'logo': '/9fGgdJz17aBX7dOyfHJtsozB7bf.png', 'id': 65,   'name': 'History Channel'},
	{'logo': '/pqUTCleNUiTLAVlelGxUgWn1ELh.png', 'id': 453,  'name': 'Hulu'},
	{'logo': '/3s6YJSYXW9mtJwoszTVI1BHDNc6.png', 'id': 244,  'name': 'Investigation Discovery'},
	{'logo': '/oz9pjTHnBUmlju8OkaTymhKbh6C.png', 'id': 9,    'name': 'ITV'},
	{'logo': '/kEeaVLcJ6L6jq3v5YlPcjQs9igm.png', 'id': 34,   'name': 'Lifetime'},
	{'logo': '/w4qtv7xBkSVsbOQdSzjUjlyOuSr.png', 'id': 33,   'name': 'MTV'},
	{'logo': '/q9rPBG1rHbUjII1Qn98VG2v7cFa.png', 'id': 43,   'name': 'National Geographic'},
	{'logo': '/cm111bsDVlYaC1foL0itvEI4yLG.png', 'id': 6,    'name': 'NBC'},
	{'logo': '/wwemzKWzjKYJFfCeiB57q3r4Bcm.png', 'id': 213,  'name': 'Netflix'},
	{'logo': '/o4uC6wQQeyPes8Jg8afsV2CHmLo.png', 'id': 35,   'name': 'Nick Junior'},
	{'logo': '/i0e7qsKhCcB6EJy0qvjhnFB2lgp.png', 'id': 13,   'name': 'Nickelodeon'},
	{'logo': '/4knr4ozp2IQrA3SMQlLSYKcM3ML.png', 'id': 2076, 'name': 'Paramount Network'},
	{'logo': '/fi83B1oztoS47xxcemFdPMhIzK.png',  'id': 4330, 'name': 'Paramount+'},
	{'logo': '/4Fn4eQmEmJZ9YWjiIhZ6cF1QHAi.png', 'id': 14,   'name': 'PBS'},
	{'logo': '/gIAcGTjKKr0KOHL5s4O36roJ8p7.png', 'id': 3353, 'name': 'Peacock'},
	{'logo': '/Allse9kbjiP6ExaQrnSpIhkurEi.png', 'id': 67,   'name': 'Showtime'},
	{'logo': '/pNoTYkElreTiHtxhF1UpUnOyDPF.png', 'id': 214,  'name': 'Sky One'},
	{'logo': '/82MKSH7iM5LAGXFb0PDOclTWn5u.png', 'id': 55,   'name': 'Spike'},
	{'logo': '/qx3Y9LCaK4mq1ykFuDIfjshlo3U.png', 'id': 318,  'name': 'Starz'},
	{'logo': '/yMzgCPTJfk6SQ6IXX9PIlSxD4ZU.png', 'id': 270,  'name': 'SundanceTV'},
	{'logo': '/iYfrkobwDhTOFJ4AXYPSLIEeaAT.png', 'id': 77,   'name': 'Syfy'},
	{'logo': '/65r0kR6MfOBYF0gEQsJGM6v5fEG.png', 'id': 68,   'name': 'TBS'},
	{'logo': '/hEpcdJ4O6eitG9ADSnDXNUrlovS.png', 'id': 71,   'name': 'The CW'},
	{'logo': '/9GlDHjQj9c2dkfARCR3zlH87R66.png', 'id': 21,   'name': 'The WB'},
	{'logo': '/6GRfZSrYh9D6C88n9kWlyrySB2l.png', 'id': 84,   'name': 'TLC'},
	{'logo': '/6ISsKwa2XUhSC6oBtHZjYf6xFqv.png', 'id': 41,   'name': 'TNT'},
	{'logo': '/8SwN81R7P5vD5mhtOE0taw5mji4.png', 'id': 209,  'name': 'Travel Channel'},
	{'logo': '/c48pVcWAEYhEFXrWFsYxx343mjx.png', 'id': 364,  'name': 'truTV'},
	{'logo': '/lOCn3EqluXoP8olsZsJHoWITwQJ.png', 'id': 397,  'name': 'TV Land'},
	{'logo': '/g1e0H0Ka97IG5SyInMXdJkHGKiH.png', 'id': 30,   'name': 'USA Network'},
	{'logo': '/w9oUxxUiXTC1O1MzJSvsMjQbgft.png', 'id': 158,  'name': 'VH1'},
	{'logo': '/kCNFRiqVRMgNWKSWu0LzAIpy9um.png', 'id': 202,  'name': 'WGN America'},
	{'logo': '/9nCeig9m4R1HoDJYBZnt9flureo.png', 'id': 1436, 'name': 'YouTube Red'}
)

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
