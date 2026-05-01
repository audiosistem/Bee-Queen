# -*- coding: utf-8 -*-
# ------------------------------------------------------------
# Canale per 'casacinema'
# ------------------------------------------------------------


from core import support,httptools
from platformcode import logger

host = support.config.get_channel_url()
headers = [['Referer', host]]


@support.menu
def mainlist(item):

    top = [('Generi', ['', 'genres'])]
    film = ['/film']

    tvshow = ['/serie-tv', 
          ('Miniserie ', ['/miniserie-tv', 'peliculas', ''])]    

    search = ''

    return locals()


@support.scrape
def genres(item):
    action = 'peliculas'
    blacklist = ['Serie TV', 'Miniserie TV']
    patronMenu = r'<li><a href="(?P<url>[^"]+)">(?P<title>[^<>]+)</a></li>'
    patronBlock = r'<a href="#">Categorie</a>(?P<block>.*?)<a href="#"'
    return locals()


def check(item):
    item.data = httptools.downloadpage(item.url).data
    if 'stagione' in item.data.lower():
        item.contentType = 'tvshow'
        return episodios(item)
    else:
        return findvideos(item)


def search(item, text):    
    item.url = "{}/?{}".format(host, support.urlencode({'story': text,'do':'search', 'subaction':'search'}))
    try:
        item.args = 'search'
        return peliculas(item)

    # Continua la ricerca in caso di errore
    except:
        import sys
        for line in sys.exc_info():
            logger.error("%s" % line)
        return []

@support.scrape
def peliculas(item):
    action = 'check'
    patron = r'<div class="posts".*?<a href="(?P<url>[^"]+)[^>]+>[^>]+>[^>]+>(?P<title>[^\(\[<]+)(?:\[(?P<quality1>HD)\])?'
    patronNext = r'<a href="([^"]+)"\s*>Pagina'

    def itemHook(item):
        if item.quality1:
            item.quality = item.quality1
            item.title += support.typo(item.quality, '_ [] color std')
        if item.lang2:
            item.contentLanguage = item.lang2
            item.title += support.typo(item.lang2, '_ [] color std')
        if item.args == 'novita':
            item.title = item.title

        return item
    return locals()


@support.scrape
def episodios(item):
    patron = r'data-num="(?P<season>.*?)x(?P<episode>.*?)"\s*data-title="(?P<title>[^"]+)(?P<lang>[sS][uU][bB]\-[iI][tT][aA]+)?".*?<div class="mirrors"(?P<server_links>.*?)<!---'
    action = 'findvideos'
    return locals()


def findvideos(item):
    if item.server_links:
        return support.server(item, data = item.server_links)

    video_url = support.match(item.url, patron=r'player[^>]+>[^>]+>.*?src="([^"]+)"').match

    if (video_url == ''):
       return []

    itemlist = [item.clone(action="play", url=srv) for srv in support.match(video_url, patron='<li class="(?:active)?" data-link=\"([^"]+)').matches]
    itemlist = support.server(item,itemlist=itemlist)
    return itemlist
