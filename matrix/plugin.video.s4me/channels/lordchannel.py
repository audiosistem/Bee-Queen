# -*- coding: utf-8 -*-
# ------------------------------------------------------------
# Canale per lordchannel.py
# ------------------------------------------------------------

from core import httptools, support, scrapertools
from core.item import Item
from platformcode import config, logger

host = config.get_channel_url()
headers = [['Referer', host]]

@support.menu
def mainlist(item):

    film = ['/film/',
            ('Generi', ['/film/', 'genres', 'film']),
           ]
    tvshow = ['/serietv/',
            ('Generi', ['/serietv/', 'genres', 'serietv']),
             ]

    anime = ['/anime/anime-ita/',
	     ('Generi', ['/anime/anime-ita/', 'genres', 'anime']),
             ('Anime SUB-Ita', ['/anime/anime-sub-ita/','peliculas']),
            ]
    search = ''
    return locals()

@support.scrape
def genres(item):
    patronBlock = r'<ul class=\"filter(?P<block>.*?)</ul>'
    patronMenu = r'<li>(?P<url>.*?)</li>'
    action = 'peliculas'
    
    def itemHook(item):
        item.title = support.typo(item.url, 'bold')
        item.url = host + '/'+ item.args + '/genere/' + item.url
        return item

    return locals()

@support.scrape
def peliculas(item):
    #if item.args == 'search':
    action = 'check'
    pagination = 100 #come il portale
    patron= r'<div class="col-6.*?<img\s.*?src="(?P<thumb>[^"]+).*?<h3.*?<a\shref="(?P<url>[^"]+).*?>(?P<title>.*?)</a'
    patronNext = r'<li class="paginator__item paginator__item--next">.*?href="(?P<url>[^"]+)'
    return locals()

@support.scrape
def episodios(item):
    patronBlock=r'<div class="accordion__card.*?<span>.*?:\s*(?P<season>\d*?)\s*</span>(?P<block>.*?)</table>'
    patron=r'<tr>\s<th class="episode-link".*?href="(?P<url>[^"]+).*?>(?P<episode>\d+).*?_blank">(?P<title>.*?)</a>'
    downloadEnabled = False
    return locals()

def check(item):
    item.data = httptools.downloadpage(item.url).data
    if 'episode-link' in item.data.lower():
        item.contentType = 'tvshow'
        return episodios(item)
    else:
        item.contentType = 'movie'
        return findvideos(item)


def search(item, text):
    item.url = "{}/cerca/?{}".format(host, support.urlencode({'q': text}))
    item.args = 'search'

    try:
        return peliculas(item)

    except:
        import sys
        for line in sys.exc_info():
            logger.error("search except: %s" % line)
        return []


def findvideos(item):
    video_url = item.url

    if item.contentType == 'movie':
        video_url = support.match(video_url, patron=r'<a\shref="(?P<url>[^"]+)"\sclass="btn-streaming streaming_btn">').match
    
    video_url = support.match(video_url, patron=r'<video-js.*?src="?(?P<url>.*?)"?\s.*?</video-js>').match

    if (video_url == ''):
       return []

    item = item.clone(server='directo', url=video_url, no_return=True) # , manifest='hls')
    return support.server(item,itemlist=[item], Download=False, Videolibrary=False)
