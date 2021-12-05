# -*- coding: utf-8 -*-
from resources.functions import *

streamsites = ['asiafaninfo',
           'clicksudorg',
           'divxfilmeonline',
           'dozaanimata',
           'filmehdnet',
           'filmeonline2016biz',
           'fsgratis',
           'fsonlineorg',
           'hindilover',
           'portalultautv',
           'serialenoihd',
           'topfilmeonline',
           'voxfilmeonline']

streamnames = {'asiafaninfo': {'nume' : 'AsiaFanInfo', 'thumb': os.path.join(media,'asiafaninfo.jpg')},
             'clicksudorg': {'nume': 'ClickSud', 'thumb': os.path.join(media, 'clicksud.jpg')},
             'divxfilmeonline': {'nume': 'DivXFilmeOnline', 'thumb': os.path.join(media,'divxfilmeonline.png')},
             'dozaanimata': {'nume': 'DozaAnimata', 'thumb': os.path.join(media,'dozaanimata.jpg')},
             'filmehdnet': {'nume': 'FilmeHD', 'thumb': os.path.join(media, 'filmehdnet.jpg')},
             'filmeonline2016biz': {'nume': 'FilmeOnline2016', 'thumb': os.path.join(media, 'filmeonline2016biz.jpg')},
             'fsgratis': {'nume': 'FSGratis', 'thumb': os.path.join(media,'fsgratis.jpg')},
             'fsonlineorg': {'nume': 'FSOnline', 'thumb': os.path.join(media, 'fsonlineorg.jpg')},
             'hindilover': {'nume': 'HindiLover', 'thumb': os.path.join(media, 'hindilover.jpg')},
             'portalultautv': {'nume': 'PortalulTauTv', 'thumb': os.path.join(media, 'portalultautv.jpg')},
             'serialenoihd': {'nume': 'SerialeNoiHD', 'thumb': os.path.join(media, 'serialenoihd.jpg')},
             'topfilmeonline': {'nume': 'TopFilmeOnline', 'thumb': os.path.join(media, 'topfilmeonline.jpg')},
             'voxfilmeonline': {'nume': 'VoxFilmeOnline', 'thumb': os.path.join(media, 'voxfilmeonline.jpg')}}


class asiafaninfo:
    
    base_url = 'http://www.asiafaninfo.net'
    thumb = os.path.join(media,'asiafaninfo.jpg')
    nextimage = next_icon
    searchimage = search_icon
    name = 'AsiaFanInfo.net'
    menu = [('Recente', base_url, 'recente', thumb), 
            ('Categorii', base_url, 'genuri', thumb),
            ('Căutare', base_url, 'cauta', searchimage)]
                

    def cauta(self, keyword):
        return self.__class__.__name__, self.name, self.parse_menu(self.get_search_url(keyword), 'by_genre')
        
    def get_search_url(self, keyword):
        url = self.base_url + '/?s=' + quote(keyword)
        return url

    def parse_menu(self, url, meniu, info={}):
        lists = []
        if meniu == 'recente':
            link = fetchData(url)
            regex = '''<li>(?:<strong>)?<a href=['"](.+?)['"].+?>(.+?)</li'''
            match = re.findall(regex, link, re.IGNORECASE | re.DOTALL)
            if len(match) > 0:
                for legatura, nume in match:
                    nume = replaceHTMLCodes(striphtml(nume))
                    info = {'Title': nume,'Plot': nume,'Poster': self.thumb}
                    lists.append((nume,legatura,'','get_links', info))
        elif meniu == 'get_links':
            link = fetchData(url)
            nume = ''
            regex_lnk = '''(?:((?:episodul|partea|sursa)[\s]\d+).+?)?<iframe.+?src=['"]((?:[htt]|[//]).+?)["']'''
            regex_seriale = '''(?:<h3>.+?strong>(.+?)<.+?href=['"](.+?)['"].+?)'''
            regex_infos = '''detay-a.+?description">(.+?)</div'''
            match_lnk = []
            #match_srl = re.compile(regex_seriale, re.IGNORECASE | re.DOTALL).findall(link)
            match_nfo = re.compile(regex_infos, re.IGNORECASE | re.DOTALL).findall(link)
            try:
                info = eval(str(info))
                info['Plot'] = (striphtml(match_nfo[0]).strip())
            except: pass
            content = ''
            for episod, content in re.findall('"collapseomatic ".+?(?:.+?>(episodul.+?)</)?(.+?)</li>', link, re.DOTALL | re.IGNORECASE):
                if episod: lists.append(('[COLOR lime]%s[/COLOR]' % episod,'nolink','','nimic', {}))
                match_lnk = []
                if content:
                    for numes, host1 in re.findall('''(?:>(sursa.+?)</.+?)?(?:src|href)?=['"]((?:[htt]|[//]).+?)["']''', content, re.DOTALL | re.IGNORECASE):
                        match_lnk.append((numes, host1))
                    for host, link1 in get_links(match_lnk):
                        lists.append((host,link1,'','play', info, url))
            if not content:
                match2_lnk = re.findall(regex_lnk, link, re.IGNORECASE | re.DOTALL)
                for host, link1 in get_links(match2_lnk):
                    lists.append((host,link1,'','play', info, url))
        elif meniu == 'by_genre' or meniu == 'cauta':
            if meniu == 'cauta':
                from resources.Core import Core
                Core().searchSites({'landsearch': self.__class__.__name__})
            else: 
                link = fetchData(url)
                regex_all = '''id="post-(.+?)</div>\s+</div>\s+</div>'''
                r_link = '''href=['"](.+?)['"].+?title.+?categ'''
                r_name = '''title.+?per.+?>(.+?)<.+?categ'''
                r_genre = '''category tag">(.+?)<'''
                r_autor = '''author">(.+?)<'''
                r_image = '''author".+?src="(.+?)"'''
                if link:
                    match = re.findall(regex_all, link, re.IGNORECASE | re.DOTALL)
                    for movie in match:
                        legatura = re.findall(r_link, movie, re.IGNORECASE | re.DOTALL)
                        if legatura:
                            legatura = legatura[0]
                            nume = re.findall(r_name, movie, re.IGNORECASE | re.DOTALL)[0]
                            try: gen = [', '.join(re.findall(r_genre, movie, re.IGNORECASE | re.DOTALL))]
                            except: gen = ''
                            try: autor = re.findall(r_autor, movie, re.IGNORECASE | re.DOTALL)[0]
                            except: autor = ''
                            try: imagine = re.findall(r_image, movie, re.IGNORECASE | re.DOTALL)[0]
                            except: imagine = self.thumb
                            nume = replaceHTMLCodes(striphtml(nume))
                            info = {'Title': nume,'Plot': '%s \nTraducator: %s' % (nume, autor),'Poster': imagine, 'Genre': gen}
                            lists.append((nume, legatura, imagine, 'get_links', info))
                    match = re.compile('"post-nav', re.IGNORECASE).findall(link)
                    if len(match) > 0:
                        if '/page/' in url:
                            new = re.compile('/page/(\d+)').findall(url)
                            nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new[0]) + 1), url)
                        else:
                            if '/?s=' in url:
                                nextpage = re.compile('\?s=(.+?)$').findall(url)
                                nexturl = '%s/page/2/?s=%s' % (self.base_url, nextpage[0])
                            else: 
                                nexturl = '%s%s' % (url, 'page/2/' if str(url).endswith('/') else '/page/2/')
                        lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        elif meniu == 'genuri':
            link = fetchData(url)
            regex_cat = '''class="cat-item.+?href=['"](.+?)['"][\s]?>(.+?)<'''
            if link:
                match = re.findall(regex_cat, link, re.IGNORECASE | re.DOTALL)
                if len(match) > 0:
                    for legatura, nume in match:
                        nume = replaceHTMLCodes(nume).capitalize()
                        lists.append((nume,legatura.replace('"', ''),'','by_genre', info))
        return lists

class clicksudorg:
    
    base_url = 'https://clicksud.biz'
    thumb = os.path.join(media, 'clicksud.jpg')
    nextimage = next_icon
    searchimage = search_icon
    name = 'ClickSud'
    menu = [('Recente', base_url, 'recente', thumb),
            ('Filme', '%s/tag/film/page/1/' % base_url, 'recente', thumb),
            ('Seriale românești', '%s/2012/06/seriale-romanesti-online/' % base_url, 'liste', thumb),
            ('Emisiuni online', '%s/2012/11/emisiuni-tv-online/' % base_url, 'liste', thumb),
            ('Seriale online', '%s/2020/08/seriale-online/' % base_url, 'liste', thumb),
            ('Seriale turcesti', '%s/2021/03/seriale-turcesti-online/' % base_url, 'liste', thumb),
            ('Las Fierbinti', base_url + '/las-fierbinti-online/', 'liste', thumb),
            ('Căutare', base_url, 'cauta', searchimage)]
    headers = {'Host': 'clicksud.biz',
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:70.1) Gecko/20100101 Firefox/70.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Referer': base_url}
        
    def get_search_url(self, keyword):
        url = self.base_url + '/page/1/?s=' + quote(keyword)
        return url

    def getKey(self, item):
        return item[1]

    def cauta(self, keyword):
        return self.__class__.__name__, self.name, self.parse_menu(self.get_search_url(keyword), 'recente')

    def parse_menu(self, url, meniu, info={}):
        lists = []
        imagine = ''
        if meniu == 'recente' or meniu == 'cauta':
            if meniu == 'cauta':
                from resources.Core import Core
                Core().searchSites({'landsearch': self.__class__.__name__})
            else: 
                link = fetchData(url.replace('+', '%2B'))
                regex_menu = '''"td-module-thumb(.*?)</div>\s+</div>\s+</div>'''
                regex_submenu = '''href=['"](.*?)['"].*?title=['"](.*?)['"].*?image\:.*?\(([htp].*?)\)'''
                regex_search = '''class="page-nav'''
                if link:
                    for meniul in re.compile(regex_menu, re.DOTALL).findall(link):
                        match = re.findall(regex_submenu, meniul, re.DOTALL)
                        for legatura, nume, imagine in match:
                            nume = replaceHTMLCodes(ensure_str(nume))
                            info = {'Title': nume,'Plot': nume,'Poster': imagine}
                            szep = re.findall('(?:sezo[a-zA-Z\s]+(\d+).+?)?epi[a-zA-Z\s]+(\d+)', nume, re.IGNORECASE | re.DOTALL)
                            if szep:
                                try:
                                    if re.search('–|-|~', nume):
                                        all_name = re.split(r'–|-|:|~', nume,1)
                                        title = all_name[0]
                                        title2 = all_name[1]
                                    else: 
                                        title = nume
                                        title2 = ''
                                    title, year = xbmc.getCleanMovieTitle(title)
                                    title2, year2 = xbmc.getCleanMovieTitle(title2)
                                    title = title if title else title2
                                    year = year if year else year2
                                    if year: info['Year'] = year
                                    if szep[0][1] and not szep[0][0]: info['Season'] = '01'
                                    else: info['Season'] = str(szep[0][0])
                                    info['Episode'] = str(szep[0][1])
                                    info['TvShowTitle'] = (re.sub('(?:sezo[a-zA-Z\s]+\d+.+?)?epi[a-zA-Z\s]+\d+.+?$', '', title, flags=re.IGNORECASE | re.DOTALL)).strip()
                                except: pass
                            switch = 'get_links'
                            lists.append((nume, legatura, imagine, switch, info))
                    match = re.compile(regex_search, re.DOTALL).findall(link)
                    if match:
                        if '/page/' in url:
                            new = re.search('/page/(\d+)', url)
                            nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new.group(1)) + 1)+'/', url)
                        else: nexturl = url + "page/2/"
                        lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        elif meniu == 'get_links':
            sources = []
            link = fetchData(url)
            regex_lnk = '''(?:(?:>(?:\s+)?(Server.*?)(?:\s+)?|item title="(.*?)".*?))?(?:text/javascript">\s+str=["'](.*?)["']|<iframe.*?src="((?:[htt]|[//]).*?)")'''
            match_lnk = re.findall(regex_lnk, link, re.IGNORECASE | re.DOTALL)
            for nume1, nume2, match1, match in match_lnk:
                if nume1:
                    nume1 = " ".join(nume1.split())
                if match:
                    if match.find('+f.id+') == -1 and not match.endswith('.js'): 
                        sources.append((nume1, match))
                        #log(match)
                else:
                    if match1 and not match:
                        match1 = unquote(match1.replace('@','%'))
                        match1 = re.findall('<iframe.*?src="((?:[htt]|[//]).*?)"', match1, re.IGNORECASE | re.DOTALL)[0]
                        nume = nume1 + nume2
                        sources.append((nume, match1))
            if info: 
                if not 'Poster' in info: info['Poster'] = self.thumb
            for host, link1 in get_links(sources):
                lists.append((host,link1,'','play', info, url))#addLink(host, link1, thumb, name, 10, striphtml(match_nfo[0]))
        elif meniu == 'seriale_rom' or meniu == 'emisiuni_online' or meniu == 'seriale_online':
            link = fetchData(url)
            if meniu == 'seriale_rom': 
                regex_seriale_rom = '''Seriale rom.*?<ul(.*?)</ul'''
            elif meniu == 'emisiuni_online':
                regex_seriale_rom = '''Emisiuni on.*?<ul(.*?)>Seriale'''
            elif meniu == 'seriale_online':
                regex_seriale_rom = '''Seriale online.*?<ul(.*?)</ul'''
            regex_serial_rom = '''href="(.*?)">(.*?)<'''
            seriale = re.search(regex_seriale_rom, link, re.DOTALL)
            if seriale:
                for legatura,nume in re.findall(regex_serial_rom, seriale.group(1), re.DOTALL):
                    if not legatura == '#' :
                        info = {'Title': nume, 'Plot': nume, 'TvShowTitle': nume, 'Poster': self.thumb}
                        switch = 'recente' if '/tag/' in legatura else 'liste'
                        lists.append((nume,legatura,self.thumb,switch,info))
            
        elif meniu == 'liste':
            link = fetchData(url.replace('+', '%2B'))
            regex_menu = '''(?:(?s)<table (.+?)</table|"td_block_inner tdb-block-inner td-fix-index"(.*?)"td_ajax_infinite")'''
            regex_submenu = '''(?:(?s)td-module-thumb".*?href="(.*?)".*?title="(.*?)"(?:.*?url\((.*?)\))?|<td>(.*?)<.*?href="(.*?)">(.*?)<(?:.*?src="(.*?)")?)'''
            regex2_submenu = '''(?s)data-label="(.*?)"><a.*?href="(.*?)"(?:.*?src="(.*?)")?'''
            regex_menu1 = '''<article(.*?)</article'''
            regex_submenu1 = '''href=['"](.*?)['"](?:.*?title=['"](.*?)['"])?(?:.*?content=['"]([htp].*?)['"])?'''
            regex_search1 = '''<span class='pager-older-link.*?href=['"](.*?)['"].*?</span'''
            for meniul in re.compile(regex_menu, re.DOTALL).findall(link):
                if meniul:
                    meniul = meniul[0] or meniul[1]
                    match = re.compile(regex_submenu).findall(meniul)
                    for legatura, nume, imagine, nume3, legatura2, nume2, imagine2 in match:
                        if not imagine:
                            imagine = imagine2 if imagine2 else self.thumb
                        if not legatura:
                            legatura = legatura2
                        if not nume:
                            nume = nume2
                        if not nume:
                            nume = nume3
                        try:
                            leg2 = re.findall('(ht.+?)"', legatura, re.IGNORECASE | re.DOTALL)
                            if leg2: legatura = leg2[0]
                        except:pass
                        nume = replaceHTMLCodes(nume)
                        szep = re.findall('([\s\w].+?)(?:sezo[a-zA-Z\s]+(\d+).+?)?epi[a-zA-Z\s]+(\d+)', nume, re.IGNORECASE | re.DOTALL)
                        if szep:
                            name, sezon, episod = szep[0]
                            sz = str(sezon)
                            eps = str(episod) if episod else '1'
                            info = {'Title': '%s S%s E%s' % (name, sz, eps), 'Plot': '%s S%s E%s' % (name, sz, eps), 'Season': sz, 'Episode': eps, 'TvShowTitle': name, 'Poster': imagine}
                        else:
                            info = {'Title': nume, 'Poster': imagine}
                        if legatura.endswith(".html"):
                            if  '/p/' in legatura: switch = 'liste'
                            else: switch = 'get_links'
                            if re.search('sezonul|episod', legatura): switch = 'get_links'
                        elif re.search('/search/', legatura): switch = 'recente'
                        else: switch = 'liste'
                        if re.search('sezonul|episod', legatura): switch = 'get_links'
                        if nume and not nume.isspace():
                            lists.append((nume,legatura.replace('"', ''),imagine,switch,info))
            for meniul in re.compile(regex_menu, re.DOTALL).findall(link):
                if meniul:
                    meniul = meniul[0] or meniul[1]
                    match = re.compile(regex2_submenu).findall(meniul)
                    for nume, legatura, imagine in match:
                        imagine = imagine if imagine else self.thumb
                        nume = replaceHTMLCodes(striphtml(ensure_str(nume)))
                        szep = re.findall('([\s\w].+?)(?:sezo[a-zA-Z\s]+(\d+).+?)?epi[a-zA-Z\s]+(\d+)', nume, re.IGNORECASE | re.DOTALL)
                        if szep:
                            if not info: info = {}
                            name, sezon, episod = szep[0]
                            sz = str(sezon)
                            eps = str(episod) if episod else '1'
                            info = {'Title': '%s S%s E%s' % (name, sz, eps), 'Plot': '%s S%s E%s' % (name, sz, eps), 'Season': sz, 'Episode': eps, 'TvShowTitle': name, 'Poster': imagine}
                        else:
                            info = {'Title': nume, 'Poster': imagine, 'Plot': nume}
                        if legatura.endswith(".html"):
                            if re.compile(r'/\d+/\d+/').search(legatura) or '/p/' in legatura: switch = 'liste'
                            else: switch = 'get_links'
                            if re.search('sezonul|episod', legatura): switch = 'get_links'
                        elif re.search('/search/', legatura): switch = 'recente'
                        else: switch = 'liste'
                        if nume and not nume.isspace():
                            lists.append((nume,legatura.replace('"', ''),imagine,switch,info))
            for meniul in re.compile(regex_menu1, re.DOTALL).findall(link):
                match = re.findall(regex_submenu1, meniul, re.DOTALL)
                for legatura, nume, imagine in match:
                    if nume and imagine:
                        if len(imagine) > 8:
                            nume = replaceHTMLCodes(ensure_str(nume))
                            info = {'Title': nume,'Plot': nume,'Poster': imagine}
                            szep = re.findall('(?:sezo[a-zA-Z\s]+(\d+).+?)?epi[a-zA-Z\s]+(\d+)', nume, re.IGNORECASE | re.DOTALL)
                            if szep:
                                try:
                                    if re.search('–|-|~', nume):
                                        all_name = re.split(r'–|-|:|~', nume,1)
                                        title = all_name[0]
                                        title2 = all_name[1]
                                    else: 
                                        title = nume
                                        title2 = ''
                                    title, year = xbmc.getCleanMovieTitle(title)
                                    title2, year2 = xbmc.getCleanMovieTitle(title2)
                                    title = title if title else title2
                                    year = year if year else year2
                                    if year: info['Year'] = year
                                    if szep[0][1] and not szep[0][0]: info['Season'] = '01'
                                    else: info['Season'] = str(szep[0][0])
                                    info['Episode'] = str(szep[0][1])
                                    info['TvShowTitle'] = (re.sub('(?:sezo[a-zA-Z\s]+\d+.+?)?epi[a-zA-Z\s]+\d+.+?$', '', title, flags=re.IGNORECASE | re.DOTALL)).strip()
                                except: pass
                            if re.search('sezonul|episod|film', legatura) or re.search('sezonul|episod|film', nume):
                                switch = 'get_links'
                            else: switch = 'liste'
                            lists.append((nume, legatura, imagine, switch, info))
            match = re.compile(regex_search1, re.DOTALL).findall(link)
            if match:
                nexturl = unquot(match[0])
                lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        return lists
   
class filmeonline2016biz:
    
    base_url = 'https://filmeonline.st'
    thumb = os.path.join(media, 'filmeonline2016biz.jpg')
    nextimage = next_icon
    searchimage = search_icon
    name = 'FilmeOnline2016.biz'
    menu = [('Recente', base_url, 'recente', thumb), 
            ('Genuri', base_url, 'genuri', thumb),
            ('Căutare', base_url, 'cauta', searchimage)]
    headers = {'User-Agent':'Mozilla/5.0 (Windows NT 6.1; rv:57.0) Gecko/20100101 Firefox/57.0', 'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'ro,en-US;q=0.7,en;q=0.3', 'TE': 'Trailers'}
        
    def get_search_url(self, keyword):
        url = self.base_url + '/?s=' + quote(keyword)
        return url

    def getKey(self, item):
        return item[1]

    def cauta(self, keyword):
        return self.__class__.__name__, self.name, self.parse_menu(self.get_search_url(keyword), 'recente')

    def parse_menu(self, url, meniu, info={}):
        lists = []
        imagine = ''
        if meniu == 'recente' or meniu == 'cauta':
            if meniu == 'cauta':
                from resources.Core import Core
                Core().searchSites({'landsearch': self.__class__.__name__})
            else:
                link = fetchData(url, url, headers=self.headers)
                if not re.search(">Nothing Found", link):
                    regex_menu = '''<article.+?href="(.+?)".+?\s+src="(http.+?)".+?title">(.+?)<.+?"description">(.+?)</articl'''
                    if link:
                        match = re.findall(regex_menu, link, re.DOTALL | re.IGNORECASE)
                        for legatura, imagine, nume, descriere in match:
                            if not "&paged=" in legatura:
                                nume = replaceHTMLCodes(striphtml(nume))
                                descriere = " ".join(replaceHTMLCodes(striphtml(descriere)).split())
                                info = {'Title': nume,'Plot': descriere,'Poster': imagine}
                                lists.append((nume, legatura, imagine, 'get_links', info))
                        match = re.compile('pagenavi', re.IGNORECASE).findall(link)
                        if len(match) > 0:
                            if '/page/' in url:
                                new = re.compile('/page/(\d+)').findall(url)
                                nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new[0]) + 1), url)
                            else:
                                if '/?s=' in url:
                                    nextpage = re.compile('\?s=(.+?)$').findall(url)
                                    nexturl = '%s%s?s=%s' % (self.base_url, ('page/2/' if str(url).endswith('/') else '/page/2/'), nextpage[0])
                                else: nexturl = url + "/page/2"
                            lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        elif meniu == 'get_links':
            import base64
            second = []
            link = fetchData('%s?show_player=true' % url)
            regex_lnk = '''(?:">(Episodul.+?)<.+?)?<iframe.+?src="((?:[htt]|[//]).+?)"'''
            regex_lnk2 = '''(?:">(Episodul.+?)<.+?)?atob\("(.+?)"'''
            regex_infos = '''kalin".+?<p>(.+?)</p'''
            regex_tag = '''category tag">(.+?)<'''
            match_lnk = re.findall(regex_lnk, link, re.IGNORECASE | re.DOTALL)
            match_lnk2 = re.findall(regex_lnk2, link, re.IGNORECASE | re.DOTALL)
            match_nfo = re.findall(regex_infos, link, re.IGNORECASE | re.DOTALL)
            match_tag = re.findall(regex_tag, link, re.IGNORECASE | re.DOTALL)
            try:
                info = eval(str(info))
                info['Plot'] = (striphtml(match_nfo[0]).strip())
                info['Genre'] = ', '.join(match_tag)
            except: pass
            infos = eval(str(info))
            try:
                for nume2, coded in match_lnk2:
                    second.append((nume2, base64.b64decode(coded)))
                second = second + match_lnk
            except: second = match_lnk
            for nume, link1 in second:
                try:
                    if py3: host = str(link1).split('/')[2].replace('www.', '').capitalize()
                    else: host = link1.split('/')[2].replace('www.', '').capitalize()
                    try:
                        year = re.findall("\((\d+)\)", infos.get('Title'))
                        infos['Year'] = year[0]
                    except: pass
                    try:
                        infos['TvShowTitle'] = re.sub(" (?:–|\().+?\)", "", info.get('Title'))
                        try:
                            infos['Season'] = str(re.findall("sezonul (\d+) ", info.get('Title'), re.IGNORECASE)[0])
                        except: infos['Season'] = '01'
                        infos['Episode'] = str(re.findall("episodul (\d+)$", nume, re.IGNORECASE)[0])
                        infos['Title'] = '%s S%sE%s' % (infos['TvShowTitle'], infos['Season'].zfill(2), infos['Episode'].zfill(2))
                        infos['Plot'] = infos['Title'] + ' ' + info['Plot']
                    except: pass
                    if nume:
                        lists.append(('[COLOR lime]%s[/COLOR]' % nume,'nimic','','', {}))
                    lists.append((host,link1,'','play', str(infos), url))
                except: pass
        elif meniu == 'genuri':
            link = fetchData(url, headers=self.headers)
            regex_cats = '''categories-2"(.+?)</ul'''
            regex_cat = '''href="(.+?)"(?:\s+.+?)?>(.+?)<'''
            if link:
                for cat in re.findall(regex_cats, link, re.IGNORECASE | re.DOTALL):
                    match = re.findall(regex_cat, cat, re.IGNORECASE | re.DOTALL)
                    if len(match) >= 0:
                        for legatura, nume in sorted(match, key=self.getKey):
                            nume = replaceHTMLCodes(nume).capitalize()
                            lists.append((nume,legatura.replace('"', ''),'','recente', info))
        return lists
    
class fsonlineorg:
    
    base_url = 'http://www.filmeserialeonline.org'
    thumb = os.path.join(media, 'fsonlineorg.jpg')
    nextimage = next_icon
    searchimage = search_icon
    name = 'FSOnline'
    menu = [('Recente', base_url, 'recente', thumb),
            ('Genuri Filme', '%s/filme-online/' % base_url, 'genuri', thumb),
            ('Genuri Seriale', '%s/seriale/' % base_url, 'genuri', thumb),
            ('Filme', base_url + '/filme-online/', 'recente', thumb),
            ('Seriale', base_url + '/seriale/', 'recente', thumb),
            ('Filme După ani', '%s/filme-online/' % base_url, 'ani', thumb),
            ('Seriale După ani', '%s/seriale/' % base_url, 'ani', thumb),
            ('Căutare', base_url, 'cauta', searchimage)]
        
    def get_search_url(self, keyword):
        url = self.base_url + '/?s=' + quote(keyword)
        return url

    def getKey(self, item):
        return item[1]

    def cauta(self, keyword):
        return self.__class__.__name__, self.name, self.parse_menu(self.get_search_url(keyword), 'recente')

    def parse_menu(self, url, meniu, info={}):
        lists = []
        #log('link: ' + link)
        imagine = ''
        if meniu == 'recente' or meniu == 'cauta':
            if meniu == 'cauta':
                from resources.Core import Core
                Core().searchSites({'landsearch': self.__class__.__name__})
            else:
                link = fetchData(url, self.base_url+ '/')
                regexprim = '''<div id="m(.*?)</div>.*?</div>'''
                regex = '''href="(.*?)".*?src="(.*?)".+?alt="(.*?)".*?class="tipoitem">(.*?)</.*?"icon-star">(.*?)</span.*?"calidad2">(.*?)</span.*?(?:.*"year">(.*?)</)?'''
                if link:
                    matches = re.findall(regexprim, link, re.DOTALL)
                    if matches:
                        for matchs in matches:
                            matchagain = re.findall(regex, matchs, re.DOTALL)
                            if matchagain:
                                for legatura, imagine, nume, descriere, tip, rating, an in matchagain:
                                    rating = striphtml(rating)
                                    descriere = replaceHTMLCodes(descriere)
                                    nume = replaceHTMLCodes(nume)
                                    imagine = imagine.strip()
                                    info = {'Title': nume,
                                        'Plot': descriere,
                                        'Rating': rating,
                                        'Poster': imagine,
                                        'Year': an}
                                    numelista = '%s (%s)' % (nume, an) if an else nume
                                    if re.search('/seriale/', legatura): lists.append((numelista + ' - Serial', legatura, imagine, 'seriale', str(info)))
                                    else: lists.append((numelista,legatura,imagine,'get_links', str(info)))
                    match = re.compile('"paginador"', re.IGNORECASE).findall(link)
                    if len(match) > 0:
                        if '/page/' in url:
                            new = re.compile('/page/(\d+)').findall(url)
                            nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new[0]) + 1), url)
                        else:
                            if '/?s=' in url:
                                nextpage = re.compile('\?s=(.+?)$').findall(url)
                                nexturl = '%s%s?s=%s' % (self.base_url, ('page/2/' if str(url).endswith('/') else '/page/2/'), nextpage[0])
                            else: nexturl = url + "/page/2"
                        lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        elif meniu == 'get_links':
            from resources.lib import requests
            from resources.lib.requests.packages.urllib3.exceptions import InsecureRequestWarning
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
            s = requests.Session()
            second = "%s/wp-content/themes/grifus/loop/second.php" % self.base_url
            third = '%s/wp-content/themes/grifus/includes/single/second.php' % self.base_url
            reg_id = '''id[\:\s]+(\d+)[,\}]'''
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:70.1) Gecko/20100101 Firefox/70.1', 'Referer': url}
            first = s.get(url, headers=headers)
            try:
                mid = re.findall(reg_id, first.text)[0].strip()
            except: mid = "1"
            dataid = {'id': mid, 'logat': '0'}
            data1 = {'call': '03AHhf_52tCb5gUikGtjLeSMufA-2Hd3hcejVejJrPldhT-fjSepWRZdKTuQ0YjvPiph7-zcazBsIoVtGAwi_C3JsOFH74_TvXq2rRRQ4Aev59zTCFHFIAOOyxuOHRyIKIy4AZoxalLMegYUL5-J6LBvFZvFuTeKa6h3oNLISO4J0qw0fZSGrEhN02Hlbtnmdilj-nRUrMUCpPLWnZaV8eB8iatMaOg6FEqayxdJ1oF8AaFlOoVOnRrw_WWPu0cH97VkreacJNaQqh0qz-5yB1tbFD0GVOHLtU7Bd6DvUf_24hTxFsCszvjPD_hltYNxTrSOj49_lpTs279NghbyVvz-yVFfC-3mU-bQ'}
            if re.search('/episodul/', url):
                s.post(second, data=data1, headers=headers)
                j = 0
                html = ''
                while (j <= 4):
                    reslink = '%s/wp-content/themes/grifus/loop/second_id.php?id=%s&embed=%s' % (self.base_url, mid, j)
                    res = s.get(reslink, headers=headers).text
                    html += res
                    j = j + 1
                    xbmc.sleep(300)
                g = html
            else:
                f = s.post(third, data=data1, headers=headers)
                g = s.post(third, data=dataid, headers=headers).text
            reg_link = '''<iframe(?:.+?)?src="(?:[\s+])?((?:[htt]|[//]).+?)"'''
            linkss = []
            if not re.search('/episodul/', url):
                reg = '''url:\s+"(.+?)"'''
                match_lnk = re.findall(reg, g, re.IGNORECASE | re.DOTALL)
                try:
                    for links in match_lnk:
                        link = s.get('%s/%s' % (self.base_url,links), headers=headers).text
                        linkss.append(re.findall(reg_link, link)[0])
                except: pass
            else:
                match_lnk = re.findall(reg_link, g, re.IGNORECASE | re.DOTALL)
                for links in match_lnk:
                    linkss.append(links)
            for host, link1 in get_links(linkss):
                if re.search('youtube.com', host, flags=re.IGNORECASE):
                    lists.append(('Trailer youtube',link1,'','play', info, url))
                else:
                    lists.append((host,link1,'','play', info, url))
        elif meniu == 'genuri':
            link = fetchData(url)
            regex_cats = '''"categorias">(.+?)</div'''
            regex_cat = '''href="(.+?)"(?:\s)?>(.+?)<.+?n>(.+?)<'''
            gen = re.findall(regex_cats, link, re.IGNORECASE | re.DOTALL)
            match = re.findall(regex_cat, gen[0], re.DOTALL)
            for legatura, nume, cantitate in match:
                nume = '%s [COLOR lime]%s[/COLOR]' % (replaceHTMLCodes(nume).capitalize(), cantitate)
                lists.append((nume,legatura,'','recente', info))
                        #for legatura, nume in sorted(match, key=self.getKey)
        elif meniu == 'seriale':
            link = fetchData(url)
            #log('link: ' + str(link))
            regex = '''(?:"se-q".+?title">(.*?)</span.+?)?"numerando">(.+?)<.+?class="episodiotitle.+?href="(.+?)"(?:[\s]+)?>(.+?)<.+?"date">(.+?)<'''
            match = re.findall(regex, link, re.DOTALL | re.IGNORECASE)
            info = eval(info)
            title = info.get('Title')
            #log(link)
            plot = info.get('Plot')
            for sezon, numerotare, link, nume, data in match:
                epis = numerotare.split('x')
                try:
                    infos = info
                    infos['Season'] = epis[0].strip()
                    infos['Episode'] = epis[1].strip()
                    infos['TVshowtitle'] = title
                    infos['Title'] = '%s S%02dE%02d' % (title, int(epis[0].strip()), int(epis[1].strip()))
                    infos['Plot'] = '%s S%02dE%02d - %s' % (title, int(epis[0].strip()), int(epis[1].strip()), plot)
                except: pass
                if sezon: lists.append(('[COLOR lime]%s[/COLOR]' % sezon,'nolink','','nimic', {}))
                lists.append((nume,link,'','get_links', str(info)))
        elif meniu == 'ani':
            link = fetchData(url)
            regex_cats = '''"filtro_y">.*?(?:An Seriale|An Film)(.*?)</div'''
            regex_cat = '''href="(.+?)"(?:\s)?>(.+?)<'''
            an = re.compile(regex_cats, re.DOTALL).findall(link)
            match = re.compile(regex_cat, re.DOTALL).findall(an[0])
            for legatura, nume in match:
                lists.append((nume,legatura,'','recente', info))
        return lists

class hindilover:
    
    base_url = 'https://hindilover.biz'
    thumb = os.path.join(media, 'hindilover.jpg')
    nextimage = next_icon
    searchimage = search_icon
    name = 'HindiLover.biz'
    menu = [('Recente', base_url, 'recente', thumb),
            ('Seriale Indiene în desfășurare', '%s/index/indiene-in-difuzare/0-64' % base_url, 'recente', thumb),
            ('Seriale Indiene terminate', '%s/index/seriale-indiene-terminate/0-69' % base_url, 'recente', thumb),
            ('Seriale Turcești în desfășurare', '%s/index/turcesti/0-65' % base_url, 'recente', thumb),
            ('Seriale Turcești terminate', '%s/index/seriale-turcesti-terminate/0-70' % base_url, 'recente', thumb),
            ('Seriale Coreene în desfășurare', '%s/index/0-71' % base_url, 'recente', thumb),
            ('Seriale Coreene terminate', '%s/index/0-73' % base_url, 'recente', thumb),
            ('Seriale Românești', '%s/index/0-74' % base_url, 'recente', thumb),
            ('Seriale Spaniole', '%s/index/0-76' % base_url, 'recente', thumb),
            ('Filme Indiene', '%s/hind/filme_indiene/1-0-31' % base_url, 'recente', thumb),
            ('Filme Turcești', '%s/turc/1/104' % base_url, 'recente', thumb),
            ('Filme Coreene', '%s/coreene/filme' % base_url, 'recente', thumb),
            ('Filme Românești', '%s/romanesti/filme' % base_url, 'recente', thumb),
            ('Filme Spaniole', '%s/spaniole/filme' % base_url, 'recente', thumb),
            ('Căutare', base_url, 'cauta', searchimage)]
        
    def get_search_url(self, keyword):
        url = self.base_url + '/?s=' + quote(keyword)
        return url

    def getKey(self, item):
        return item[1]

    def cauta(self, keyword):
        #return self.__class__.__name__, self.name, self.parse_menu(self.get_search_url(keyword), 'recente')
        return None

    def parse_menu(self, url, meniu, info={}):
        lists = []
        #log('link: ' + link)
        imagine = ''
        nexturl = None
        if meniu == 'recente' or meniu == 'cauta' or meniu == 'filme':
            if meniu == 'cauta':
                from resources.Core import Core
                Core().searchSites({'landsearch': self.__class__.__name__})
            else: 
                link = fetchData(url)
                regex_menu = '''class="movie"(.+?)(?:</li>|</td>|</div></div>)'''
                regex_submenu = '''src=(?:"|)(.+?)(?:"|\s+).+?href="(.+?)"(?:.+?"movie_hd">(.+?)<)?.+?href.+?">(.+?)(?:</div|</a)'''
                if link:
                    if re.search('<iframe.+?src=(?:")?((?:[htt]|[//]).+?)"', link, re.IGNORECASE) and info:
                        meniu = 'get_links'
                        return self.parse_menu(url,'get_links',info)
                    for movie in re.compile(regex_menu, re.IGNORECASE | re.MULTILINE | re.DOTALL).findall(link):
                        infog = {}
                        match = re.compile(regex_submenu, re.DOTALL).findall(movie)
                        for imagine, legatura, vizualizari, nume in match:
                            nume = replaceHTMLCodes(striphtml(nume))
                            nume = striphtml(nume)
                            imagine = '%s/%s' % (self.base_url, imagine.strip().replace('../../', ''))
                            legatura = '%s%s' % (self.base_url, legatura) if legatura.startswith('/') else legatura
                            if info:
                                try:
                                    infog = eval(info)
                                    if py3: nums = infog.get('Title')
                                    else: nums = infog.get('Title').decode('utf-8')
                                    nume = infog['Title'] = '%s %s' % (nums, nume)
                                    infog['Plot'] = nume
                                except: pass
                            else:
                                infog = {'Title': '%s' % (nume),'Plot': '%s' % (nume),'Poster': imagine}
                            lists.append(('%s' % (nume), legatura, imagine, 'recente', infog))
                    match = re.compile('"catpages', re.IGNORECASE).findall(link)
                    match2 = re.compile('"pagesBlockuz.+?swchitem', re.IGNORECASE).findall(link)
                    if len(match) > 0:
                        if re.search('/\d+-\d+-\d+$', url):
                            new = re.compile('/(\d+)-\d+-\d+').findall(url)
                            nexturl = re.sub('/(\d+)-', '/' + str(int(new[0]) + 1) + '-', url)
                    elif len(match2) > 0:
                        if re.search('/\d+$', url):
                            new = re.compile('/(\d+)$').findall(url)
                            nexturl = re.sub('/(\d+)$', '/' + str(new[0]) + '-2', url)
                        elif re.search('/\d+-\d+$', url):
                            new = re.compile('/\d+-(\d+)$').findall(url)
                            nexturl = re.sub('-(\d+)$', '-' + str(int(new[0]) + 1), url)
                        elif re.search('/\d+-\d+-\d+-\d+-\d+$', url):
                            new = re.compile('/\d+-(\d+)-\d+-\d+-\d+$').findall(url)
                            nexturl = re.sub(r'/(\d+)-(\d+)', r'/\1-' + str(int(new[0]) + 1), url)
                    if nexturl:
                        lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        
        elif meniu == "get_links":
            link = fetchData(url)
            regex_lnk = '''<iframe.+?src=(?:")?((?:[htt]|[//]).+?)"'''
            match = re.findall(regex_lnk, link, re.IGNORECASE | re.DOTALL)
            if match:
                for host, link1 in get_links(match):
                    lists.append((host,link1,'','play', info, url))
        elif meniu == 'serialeindiene' or meniu == 'serialeturcesti' or meniu == 'serialeterminate':
            link = fetchData(url)
            if meniu == 'serialeindiene':
                regex_block = '''"seriale indiene"(.+?)</div>\s+</div>'''
                #regex_serial = '''href="(.+?)".+?class="abcd[\w\s]+">(.+?)<!'''
            elif meniu == 'serialeturcesti':
                regex_block = '''"seriale turcesti"(.+?)</div>\s+</div>'''
            elif meniu == 'serialeterminate':
                regex_block = '''"seriale"(.+?)</div>\s+</div>'''
            regex_serial = '''href="(.+?)".+?class="abcd[\w\sÇ]+">(.+?)</di'''
            
            if link:
                for block in re.findall(regex_block, link, re.IGNORECASE | re.DOTALL):
                    match = re.findall(regex_serial, block, re.IGNORECASE | re.DOTALL)
                    for legatura, nume in match:
                        nume = replaceHTMLCodes(striphtml(nume))
                        legatura = legatura.strip()
                        lists.append((nume, legatura, self.thumb, 'recente', info))
        return lists
    
class portalultautv:
    
    base_url = 'https://portalultautv.net'
    thumb = os.path.join(media, 'portalultautv.jpg')
    nextimage = next_icon
    searchimage = search_icon
    name = 'PortalulTauTv.com'
    menu = [('Recente', base_url, 'recente', thumb), 
            ('Genuri', base_url, 'genuri', thumb),
            ('Căutare', base_url, 'cauta', searchimage)]
                

    def cauta(self, keyword):
        return self.__class__.__name__, self.name, self.parse_menu(self.get_search_url(keyword), 'recente')
        
    def get_search_url(self, keyword):
        url = self.base_url + '/?s=' + quote(keyword)
        return url

    def parse_menu(self, url, meniu, info={}):
        lists = []
        link = fetchData(url)
        if meniu == 'recente' or meniu == 'cauta':
            if meniu == 'cauta':
                from resources.Core import Core
                Core().searchSites({'landsearch': self.__class__.__name__})
            else: 
                link = fetchData(url, self.base_url + '/')
                regex_menu = '''<article(.+?)</art'''
                regex_submenu = '''href=['"](.+?)['"].+?title=['"](.+?)['"].+?src=['"](.+?)['"]'''
                if link:
                    for movie in re.compile(regex_menu, re.IGNORECASE | re.MULTILINE | re.DOTALL).findall(link):
                        match = re.compile(regex_submenu, re.DOTALL).findall(movie)
                        for legatura, nume, imagine in match:
                            nume = replaceHTMLCodes(striphtml(nume))
                            info = {'Title': nume,'Plot': nume,'Poster': imagine}
                            lists.append((nume, legatura, imagine, 'get_links', info))
                    match = re.compile('navigation"', re.IGNORECASE).findall(link)
                    match2 = re.compile('"next page-numbers"', re.IGNORECASE).findall(link)
                    if len(match) > 0 or len(match2) > 0:
                        if '/page/' in url:
                            new = re.compile('/page/(\d+)').findall(url)
                            nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new[0]) + 1), url)
                        else:
                            if '/?s=' in url:
                                nextpage = re.compile('\?s=(.+?)$').findall(url)
                                nexturl = '%s%s?s=%s' % (self.base_url, ('page/2/' if str(url).endswith('/') else '/page/2/'), nextpage[0])
                            else: nexturl = '%s/page/2' % url if not url.endswith('/') else '%spage/2' % url
                        #log(nexturl)
                        lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        elif meniu == 'get_links':
            link = fetchData(url)
            nume = ''
            regex_lnk = '''(?:type=[\'"]text/javascript["\']>(?:\s+)?str=['"](.+?)["']|(?:(S\d+E\d+).+?)?<iframe.+?src=['"]((?:[htt]|[//]).+?)["'])'''
            regex_seriale = '''(?:<h3>.+?strong>(.+?)<.+?href=['"](.+?)['"].+?)'''
            regex_infos = '''sinopsis(.+?)<div'''
            regex_content = '''<article(.+?)</articl'''
            match_content = re.findall(regex_content, link, re.IGNORECASE | re.DOTALL)
            if len(match_content) > 0:
                match_lnk = re.compile(regex_lnk, re.IGNORECASE | re.DOTALL).findall(link)
                match_nfo = re.compile(regex_infos, re.IGNORECASE | re.DOTALL).findall(link)
                match_srl = re.compile(regex_seriale, re.IGNORECASE | re.DOTALL).findall(link)
            else: 
                match_lnk = []
                match_nfo = []
                match_srl = []
            infos = eval(str(info))
            #try:
                #infos['Title'] = infos.get('Title').decode('unicode-escape')
                #infos['Plot'] = infos.get('Plot').decode('unicode-escape')
                #infos['Poster'] = infos.get('Poster').decode('unicode-escape')
            #except: pass
            #try:
                #if len(match_nfo) > 0:
                    #infos['Plot'] = htmlparser.HTMLParser().unescape(striphtml(match_nfo[0]).strip().decode('utf-8'))
            #except: pass
            titleorig = infos['Title']
            for numerotare, linknumerotare, linknumerotareunu in match_lnk:
                if not numerotare:
                    szep = re.findall('S(\d+)E(\d+)', linknumerotare, re.IGNORECASE | re.DOTALL)
                    if szep:
                        episod = linknumerotare
                        linknumerotare = linknumerotareunu
                        try:
                            if re.search('–|-|~', titleorig):
                                all_name = re.split(r'–|-|:|~', titleorig,1)
                                title = all_name[1]
                                title2 = all_name[0]
                            else: 
                                title = titleorig
                                title2 = ''
                            title, year = xbmc.getCleanMovieTitle(title)
                            title2, year2 = xbmc.getCleanMovieTitle(title2)
                            title = title if title else title2
                            year = year if year else year2
                            if year: infos['Year'] = year
                            if szep[0][1] and not szep[0][0]: infos['Season'] = '01'
                            else: infos['Season'] = str(szep[0][0])
                            infos['Episode'] = str(szep[0][1])
                            infos['TvShowTitle'] = title
                        except: pass
                else:
                    #log(unquote(numerotare.replace('@','%')))
                    numerotare = re.findall('<(?:iframe|script).+?src=[\'"]((?:[htt]|[//]).+?)["\']', unquote(numerotare.replace('@','%')), re.IGNORECASE | re.DOTALL)[0]
                    try:
                        if re.search('–|-|~', titleorig):
                            all_name = re.split(r'–|-|:|~', titleorig,1)
                            title = all_name[1]
                            title2 = all_name[0]
                        else: 
                            title = titleorig
                            title2 = ''
                        title, year = xbmc.getCleanMovieTitle(title)
                        title2, year2 = xbmc.getCleanMovieTitle(title2)
                        title = title if title else title2
                        year = year if year else year2
                        if year: infos['Year'] = year
                        infos['Title'] = title
                    except: pass
                    linknumerotare = numerotare
                #log(numerotare)
                try:
                    if not numerotare: host = episod
                    else: host = ''
                    #log(host)
                    for hosts, link1 in get_links([linknumerotare]):
                        lists.append(('%s %s' % (host, hosts),link1,'','play', str(infos), url))
                except:
                    for host, link1 in get_links([linknumerotareunu]):
                        lists.append((host,link1,'','play', str(infos), url))
            #for n_serial, l_serial in match_srl:
                #if not n_serial.isspace():
                    ##log(n_serial)
                    #if not 'https://www.portalultautv.com/filme-erotice-online/' in n_serial or not 'AD-BLOCK' in n_serial or not '1. Dezactivati' in n_serial:
                        #lists.append((n_serial,l_serial,'','get_links', info))
        elif meniu == 'genuri':
            link = fetchData(url)
            regex_cats = '''Categorie-Gen(.+?)</div'''
            regex_cat = '''\s+href=["'](.*?)['"\s]>(.+?)<'''
            if link:
                for cat in re.compile(regex_cats, re.IGNORECASE | re.MULTILINE | re.DOTALL).findall(link):
                    match = re.compile(regex_cat, re.DOTALL).findall(cat)
                    for legatura, nume in match:
                        lists.append((nume,legatura.replace('"', ''),'','recente', info))#addDir(nume, legatura.replace('"', ''), 6, movies_thumb, 'recente')
        return lists

class serialenoihd:
    
    base_url = 'https://serialenoihd.com'
    thumb = os.path.join(media, 'serialenoihd.jpg')
    nextimage = next_icon
    searchimage = search_icon
    name = 'SerialeNoiHD.com'
    menu = [('Recente', base_url, 'recente', thumb),
            ('Categorii', base_url, 'categorii', thumb),
            ('Căutare', base_url, 'cauta', searchimage)]
        
    def get_search_url(self, keyword):
        url = self.base_url + '/?s=' + quote(keyword)
        return url

    def getKey(self, item):
        return item[1]

    def cauta(self, keyword):
        return self.__class__.__name__, self.name, self.parse_menu(self.get_search_url(keyword), 'recente')

    def parse_menu(self, url, meniu, info={}):
        lists = []
        imagine = ''
        if meniu == 'recente' or meniu == 'cauta':
            if meniu == 'cauta':
                from resources.Core import Core
                Core().searchSites({'landsearch': self.__class__.__name__})
            else:
                link = fetchData(url)
                regex_menu = '''<article(.+?)</article'''
                regex_submenu = '''href="(.+?)".+?src="(.+?)".+?mark">(.+?)<.+?excerpt">(.+?)</div'''
                if link:
                    for movie in re.compile(regex_menu, re.IGNORECASE | re.MULTILINE | re.DOTALL).findall(link):
                        match = re.compile(regex_submenu, re.DOTALL).findall(movie)
                        for legatura, imagine, nume, descriere in match:
                            nume = replaceHTMLCodes(striphtml(nume))
                            descriere = replaceHTMLCodes(striphtml(descriere))
                            info = {'Title': nume,'Plot': descriere,'Poster': imagine}
                            szep = re.findall('(?:sezo[a-zA-Z\s]+(\d+).+?)?epi[a-zA-Z\s]+(\d+)', nume, re.IGNORECASE | re.DOTALL)
                            if szep:
                                try:
                                    if re.search('–|-|~', nume):
                                        all_name = re.split(r'–|-|:|~', nume,1)
                                        title = all_name[0]
                                        title2 = all_name[1]
                                    else: 
                                        title = nume
                                        title2 = ''
                                    title, year = xbmc.getCleanMovieTitle(title)
                                    title2, year2 = xbmc.getCleanMovieTitle(title2)
                                    title = title if title else title2
                                    year = year if year else year2
                                    if year: info['Year'] = year
                                    if szep[0][1] and not szep[0][0]: info['Season'] = '01'
                                    else: info['Season'] = str(szep[0][0])
                                    info['Episode'] = str(szep[0][1])
                                    info['TvShowTitle'] = (re.sub('(?:sezo[a-zA-Z\s]+\d+.+?)?epi[a-zA-Z\s]+\d+', '', title, flags=re.IGNORECASE | re.DOTALL)).strip()
                                except: pass
                            lists.append((nume, legatura, imagine, 'get_links', str(info)))
                    match = re.compile('"nav-links"', re.IGNORECASE).findall(link)
                    if len(match) > 0:
                        if '/page/' in url:
                            new = re.compile('/page/(\d+)').findall(url)
                            nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new[0]) + 1), url)
                        else:
                            if '/?s=' in url:
                                nextpage = re.compile('\?s=(.+?)$').findall(url)
                                nexturl = '%s%s?s=%s' % (self.base_url, ('page/2/' if str(url).endswith('/') else '/page/2/'), nextpage[0])
                            else: nexturl = url + "/page/2"
                        lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        elif meniu == 'get_links':
            link = fetchData(url)
            if re.search('content-protector-captcha', link):
                cpc = re.findall('content-protector-captcha.+?value="(.+?)"', link, re.DOTALL)
                cpt = re.findall('content-protector-token.+?value="(.+?)"', link, re.DOTALL)
                cpi = re.findall('content-protector-ident.+?value="(.+?)"', link, re.DOTALL)
                cpp = re.findall('content-protector-password.+?value="(.+?)"', link, re.DOTALL)
                cpsx = '348'
                cpsy = '220'
                data = {'content-protector-captcha': cpc[0],
                        'content-protector-token': cpt[0],
                        'content-protector-ident': cpi[0],
                        'content-protector-submit.x': cpsx,
                        'content-protector-submit.y': cpsy,
                        'content-protector-password': cpp[0]}
                link = fetchData(url, data=data)
            coded_lnk = '''type=[\'"].+?text/javascript[\'"]>(?:\s+)?str=['"](.+?)["']'''
            regex_lnk = '''<iframe.+?src="((?:[htt]|[//]).+?)"'''
            regex_infos = '''"description">(.+?)</'''
            match_coded = re.compile(coded_lnk, re.IGNORECASE | re.DOTALL).findall(link)
            match_lnk = re.compile(regex_lnk, re.IGNORECASE | re.DOTALL).findall(link)
            match_nfo = re.compile(regex_infos, re.IGNORECASE | re.DOTALL).findall(link)
            try:
                info = eval(str(info))
                info['Plot'] = (striphtml(match_nfo[0]).strip())
            except: pass
            regex_sub_oload = '''"captions" src="(.+?)"'''
            regex_sub_vidoza = '''tracks[:\s]+(.+?])'''
            for host, link1 in get_links(match_lnk):
                lists.append((host,link1,'','play', info, url))
            try:
                list_link = []
                for one_code in match_coded:
                    decoded = re.findall('<(?:iframe|script).+?src=[\'"]((?:[htt]|[//]).+?)["\']', unquote(one_code.replace('@','%')), re.IGNORECASE | re.DOTALL)[0]
                    list_link.append(decoded)
                for host, link1 in get_links(list_link):
                    lists.append((host,link1,'','play', info, url))
            except: pass
                
        elif meniu == 'categorii':
            cats = ['Seriale Indiene', 'Seriale Turcesti', 'Seriale Straine', 'Emisiuni TV', 'Seriale Romanesti']
            for cat in cats:
                lists.append((cat, self.base_url, self.thumb, 'titluri', {'categorie': cat}))
        elif meniu == 'titluri':
            info = eval(str(info))
            link = fetchData(url)
            regex_cats = '''%s</a>(.+?)</ul''' % info.get('categorie')
            regex_cat = '''href="(.+?)"(?:\s+)?>(.+?)<'''
            if link:
                for cat in re.findall(regex_cats, link, re.IGNORECASE | re.DOTALL):
                    match = re.findall(regex_cat, cat, re.IGNORECASE | re.DOTALL)
                    if len(match) >= 0:
                        for legatura, nume in sorted(match, key=self.getKey):
                            nume = replaceHTMLCodes(striphtml(nume)).capitalize()
                            lists.append((nume,legatura.replace('"', ''),'','recente', info))
        return lists

class topfilmeonline:
    
    base_url = 'https://topfilmeonline.net'
    thumb = os.path.join(media, 'topfilmeonline.jpg')
    nextimage = next_icon
    searchimage = search_icon
    name = 'TopFilmeOnline'
    menu = [('Recente', base_url, 'recente', thumb), 
            ('Genuri', base_url, 'genuri', thumb),
            ('Căutare', 'post', 'cauta', searchimage)]
        
    def get_search_url(self, keyword):
        url = self.base_url + '/?s=' + quote(keyword)
        return url

    def getKey(self, item):
        return item[1]

    def cauta(self, keyword):
        return self.__class__.__name__, self.name, self.parse_menu('post', 'cauta', keyw=keyword)

    def parse_menu(self, url, meniu, info={}, keyw=None):
        lists = []
        #log('link: ' + link)
        imagine = ''
        if meniu == 'recente':
            link = fetchData(url, self.base_url + '/')
            regex_submenu = '''class="post.+?href=['"](.+?)['"].+?title">(.+?)<.+?(?:imdb).+?([\d.]+)?.+?views.+?(\d+).+?lazy-src="(.+?)"'''
            if link:
                match = re.compile(regex_submenu, re.IGNORECASE | re.DOTALL).findall(link)
                if len(match) > 0:
                    for legatura, nume, imdb, views, imagine in match:
                        nume = replaceHTMLCodes(striphtml(nume))
                        info = {'Title': nume,'Plot': nume,'Poster': imagine, 'Rating' : imdb}
                        lists.append((nume, legatura, imagine, 'get_links', info))
                match = re.compile('"navigation', re.IGNORECASE).findall(link)
                if len(match) > 0:
                    if '/page/' in url:
                        new = re.compile('/page/(\d+)').findall(url)
                        nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new[0]) + 1), url)
                    else:
                        if '/?s=' in url:
                            nextpage = re.compile('\?s=(.+?)$').findall(url)
                            nexturl = '%s%s?s=%s' % (self.base_url, ('page/2/' if str(url).endswith('/') else '/page/2/'), nextpage[0])
                        else: nexturl = url + "/page/2"
                    lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        elif meniu == 'cauta':
            if url == 'post':

                if keyw:
                    url = self.get_search_url(keyw)
                    link = fetchData(url)
                else:
                    link = None
                    from resources.Core import Core
                    Core().searchSites({'landsearch': self.__class__.__name__})
            else:
                link = fetchData(url)
            regex = '''post-.+?href="(.+?)".+?>(.+?)<.+?summary">(.+?)</div'''
            if link:
                match = re.compile(regex, re.IGNORECASE | re.DOTALL).findall(link)
                if len(match) > 0:
                    for legatura, nume, descriere in match:
                        imagine = self.thumb
                        nume = replaceHTMLCodes(striphtml(ensure_str(nume)))
                        descriere = replaceHTMLCodes(striphtml(ensure_str(descriere)))
                        info = {'Title': nume,'Plot': descriere,'Poster': imagine}
                        lists.append((nume, legatura, imagine, 'get_links', info))
                match = re.compile('"navigation', re.IGNORECASE).findall(link)
                if len(match) > 0:
                    if '/page/' in url:
                        new = re.compile('/page/(\d+)').findall(url)
                        nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new[0]) + 1), url)
                    else:
                        if '/?s=' in url:
                            nextpage = re.compile('\?s=(.+?)$').findall(url)
                            nexturl = '%s%s?s=%s' % (self.base_url, ('page/2/' if str(url).endswith('/') else '/page/2/'), nextpage[0])
                        else: nexturl = url + "/page/2"
                    lists.append(('Next', nexturl, self.nextimage, meniu, {}))
            
        elif meniu == 'get_links':
            link = fetchData(url)
            links = []
            regex_lnk = '''<iframe.+?src="((?:[htt]|[//]).+?)"'''
            regex_infos = '''movie-description">(.+?)</p'''
            reg_id = '''data-singleid="(.+?)"'''
            reg_server = '''data-server="(.+?)"'''
            match_nfo = re.compile(regex_infos, re.IGNORECASE | re.DOTALL).findall(link)
            match_id = re.findall(reg_id, link, re.IGNORECASE | re.DOTALL)
            match_server = re.findall(reg_server, link, re.IGNORECASE | re.DOTALL)
            #try:
                #mid = list(set(match_id))[0]
                #mserver = list(set(match_server))
                #for code in mserver:
                    #try:
                        #get_stupid_links = fetchData('%s/wp-admin/admin-ajax.php' % self.base_url, data = {'action': 'samara_video_lazyload', 
                                                                                #'server': code,
                                                                                #'singleid': mid})
                        #match_lnk = re.findall(regex_lnk, get_stupid_links, re.IGNORECASE | re.DOTALL)
                        #links.append(match_lnk[0])
                    #except: pass
            #except: pass
            try:
                links = re.findall(regex_lnk, link, re.IGNORECASE | re.DOTALL)
            except: pass
            try:
                info = eval(str(info))
                info['Plot'] = (striphtml(match_nfo[0]).strip())
            except: pass
            for host, link1 in get_links(links):
                lists.append((host,link1,'','play', info, url))
        elif meniu == 'genuri':
            link = fetchData(url)
            regex_cats = '''"cat-item.+?href=['"](.+?)['"](?:>|.+?title.+?">)(.+?)<'''
            if link:
                match = re.compile(regex_cats, re.IGNORECASE | re.MULTILINE | re.DOTALL).findall(link)
                if len(match) >= 0:
                    for legatura, nume in sorted(match, key=self.getKey):
                        lists.append((nume,legatura.replace('"', ''),'','recente', info))#addDir(nume, legatura.replace('"', ''), 6, movies_thumb, 'recente')
        return lists
    
class voxfilmeonline:
    
    base_url = 'https://voxfilmeonline.biz'
    thumb = os.path.join(media, 'voxfilmeonline.jpg')
    nextimage = next_icon
    searchimage = search_icon
    name = 'VoxFilmeOnline'
    menu = [('Recente', base_url, 'recente', thumb), 
            ('Genuri', base_url, 'genuri', thumb),
            ('Căutare', base_url, 'cauta', searchimage)]
        
    def get_search_url(self, keyword):
        url = self.base_url + '/?s=' + quote(keyword)
        return url

    def getKey(self, item):
        return item[1]

    def cauta(self, keyword):
        return self.__class__.__name__, self.name, self.parse_menu(self.get_search_url(keyword), 'recente')

    def parse_menu(self, url, meniu, info={}):
        lists = []
        #log('link: ' + link)
        imagine = ''
        if meniu == 'recente' or meniu == 'cauta':
            if meniu == 'cauta':
                from resources.Core import Core
                Core().searchSites({'landsearch': self.__class__.__name__})
            else: 
                link = fetchData(url)
                regex_menu = '''<article(.+?)</art'''
                regex_submenu = '''href="(.+?)".+?title">(.+?)<(?:.+?rating">(.+?)</div)?.+?src="(ht.+?)"'''
                if link:
                    for movie in re.compile(regex_menu, re.IGNORECASE | re.MULTILINE | re.DOTALL).findall(link):
                        match = re.compile(regex_submenu, re.DOTALL).findall(movie)
                        for legatura, nume, descriere, imagine in match:
                            try:
                                nume = replaceHTMLCodes(striphtml(ensure_str(nume)))
                                descriere = replaceHTMLCodes(striphtml(ensure_str(descriere)))
                            except:
                                nume = striphtml(ensure_str(nume)).strip()
                                descriere = striphtml(ensure_str(descriere)).strip()
                            descriere = "-".join(descriere.split("\n"))
                            info = {'Title': nume,'Plot': descriere,'Poster': imagine}
                            lists.append((nume, legatura, imagine, 'get_links', info))
                    match = re.compile('pagination"', re.IGNORECASE).findall(link)
                    if len(match) > 0:
                        if '/page/' in url:
                            new = re.compile('/page/(\d+)').findall(url)
                            nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new[0]) + 1), url)
                        else:
                            if '/?s=' in url:
                                nextpage = re.compile('\?s=(.+?)$').findall(url)
                                nexturl = '%s%s?s=%s' % (self.base_url, ('page/2/' if str(url).endswith('/') else '/page/2/'), nextpage[0])
                            else: nexturl = url + "/page/2"
                        lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        elif meniu == 'get_links':
            link = fetchData(url)
            links = []
            regex_lnk = '''<iframe.+?src="((?:[htt]|[//]).+?)"'''
            match_lnk = re.compile(regex_lnk, re.IGNORECASE | re.DOTALL).findall(link)
            try:
                match_lnk = list(set(match_lnk))
            except: pass
            for host, link1 in get_links(match_lnk):
                lists.append((host,link1,'','play', info, url))#addLink(host, link1, thumb, name, 10, striphtml(match_nfo[0]))
        elif meniu == 'genuri':
            link = fetchData(url)
            regex_cats = '''cat\-item\-.+?href=['"](.+?)['"](?:\s+.+?">|>)?(.+?)</a'''
            if link:
                match = re.compile(regex_cats).findall(link)
                if len(match) >= 0:
                    for legatura, nume in sorted(match, key=self.getKey):
                        lists.append((nume,legatura.replace('"', ''),'','recente', info))#addDir(nume, legatura.replace('"', ''), 6, movies_thumb, 'recente')
        return lists
    
class divxfilmeonline:
    
    base_url = 'https://divxfilmeonline.net'
    thumb = os.path.join(media,'divxfilmeonline.png')
    nextimage = next_icon
    searchimage = search_icon
    name = 'DivXFilmeOnline'
    menu = [('Recente', base_url, 'recente', thumb), 
            ('Categorii', '%s/filme-hd/page/1/'% base_url, 'genuri', thumb),
            ('Filme', '%s/filme-online/page/1/'% base_url, 'recente', thumb),
            ('Filme 2020', '%s/filme-2020/page/1/'% base_url, 'recente', thumb),
            ('Filme 2019', '%s/filme-2019-online/page/1/'% base_url, 'recente', thumb),
            ('Seriale', '%s/seriale-online/'% base_url, 'recente', thumb),
            ('Seriale 2020', '%s/seriale-2020/'% base_url, 'recente', thumb),
            ('Seriale 2019', '%s/seriale-2019/'% base_url, 'recente', thumb),
            ('Căutare', base_url, 'cauta', searchimage)]
                

    def cauta(self, keyword):
        return self.__class__.__name__, self.name, self.parse_menu(self.get_search_url(keyword), 'recente')
        
    def get_search_url(self, keyword):
        url = self.base_url + '/page/1/?s=' + quote(keyword)
        return url

    def parse_menu(self, url, meniu, info={}):
        lists = []
        if meniu == 'recente':
            link = fetchData(url)
            regex = '''<li class.+?>(.+?)</li>'''
            mregex = '''src="(.+?)".+?href="(.+?)".+?span>(.+?)<'''
            match = re.findall(regex, link)
            if len(match) > 0:
                for movies in match:
                    movie = re.findall(mregex, movies)
                    if movie:
                        for imagine, legatura, nume in movie:
                            nume = replaceHTMLCodes(striphtml(nume))
                            info = {'Title': nume,'Plot': nume,'Poster': imagine}
                            if 'seriale-' in legatura:
                                lists.append((nume,legatura,'','recente', info))
                            else:
                                lists.append((nume,legatura,'','get_links', info))
                match = re.compile('(?:next"|pagination").+?page', re.IGNORECASE).findall(link)
                if len(match) > 0 :
                    nexturl = ''
                    if '/page/' in url:
                        new = re.compile('/page/(\d+)').findall(url)
                        nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new[0]) + 1), url)
                    elif 'page=' in url:
                            new = re.compile('page\=(\d+)').findall(url)
                            nexturl = re.sub('page\=(\d+)', 'page=' + str(int(new[0]) + 1), url)
                    else: nexturl = '%s?page=2' % url
                    lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        elif meniu == 'get_links':
            link = fetchData(url)
            regex_lnk = '''<iframe(?:.+?)?src=['"]((?:[htt]|[//]).+?)['"]'''
            regexnew = '''li class="server(?:.*?data-vs=|.*?=)"(.*?)"'''
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:70.1) Gecko/20100101 Firefox/70.1', 'Referer': url, 'Host': 'fastvid.co'}
            match = re.compile(regex_lnk).findall(link)
            links = re.findall(regexnew, link, re.DOTALL)
            if links:
                try:
                    for newlink in links:
                        result = requests.head(newlink, headers=headers)
                        thislink = result.headers['Location']
                        match.append(thislink)
                except: pass
            for host, link1 in get_links(match, url):
                lists.append((host,link1,'','play', info, url))
        elif meniu == 'cauta':
            from resources.Core import Core
            Core().searchSites({'landsearch': self.__class__.__name__})
        elif meniu == 'genuri':
            link = fetchData(url)
            regex_cat = '''<li class.+?alt="(.+?)".+?href="(.+?)"'''
            if link:
                match = re.findall(regex_cat, link)
                if len(match) > 0:
                    for nume, legatura in match:
                        nume = replaceHTMLCodes(nume).capitalize()
                        lists.append((nume,legatura.replace('"', ''),'','recente', info))
        return lists

class fsgratis:
    
    base_url = 'https://filmeserialegratis.org'
    thumb = os.path.join(media,'fsgratis.jpg')
    nextimage = next_icon
    searchimage = search_icon
    name = 'FSGratis'
    menu = [('Recente', base_url, 'recente', thumb), 
            ('Categorii', '%s/filme-online/page/1/'% base_url, 'genuri', thumb),
            ('Filme', '%s/filme-online/page/1/'% base_url, 'recente', thumb),
            ('Seriale', '%s/seriale/page/1/'% base_url, 'recente', thumb),
            ('Episoade noi', '%s/episoade-noi/page/1/'% base_url, 'recente', thumb),
            ('Top', '%s/trending/page/1/'% base_url, 'recente', thumb),
            ('Căutare', base_url, 'cauta', searchimage)]
                

    def cauta(self, keyword):
        return self.__class__.__name__, self.name, self.parse_menu(self.get_search_url(keyword), 'recente')
        
    def get_search_url(self, keyword):
        url = '%s/search/%s/page/1/' % (self.base_url, quote(keyword))
        return url

    def parse_menu(self, url, meniu, info={}):
        lists = []
        if meniu == 'recente':
            link = fetchData(url)
            regex = '''<li class.*?>(.*?)</li>'''
            mregex = '''href="(.+?)".*?src="(.*?)"(?:.*?ClB"\>(S.*?)\</f.*?)?.*?title"\>(.*?)\<(?:.*?year"\>(.*?)\<)?'''
            match = re.findall(regex, link, re.DOTALL)
            if len(match) > 0:
                for movies in match:
                    movie = re.findall(mregex, movies, re.IGNORECASE|re.DOTALL)
                    if movie:
                        for legatura, imagine, sezon, nume, an in movie:
                            nume = replaceHTMLCodes(striphtml(nume))
                            nume = '%s (%s)' % (nume, an if an else striphtml(sezon))
                            info = {'Title': nume,'Plot': nume,'Poster': imagine}
                            lists.append((nume,legatura,imagine,'steps', info))
                match = re.compile('pagenavi".+?page/', re.IGNORECASE|re.DOTALL).findall(link)
                if len(match) > 0 :
                    nexturl = ''
                    if '/page/' in url:
                        new = re.compile('/page/(\d+)').findall(url)
                        nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new[0]) + 1), url)
                    elif 'page=' in url:
                            new = re.compile('page\=(\d+)').findall(url)
                            nexturl = re.sub('page\=(\d+)', 'page\=' + str(int(new[0]) + 1), url)
                    else:
                        nexturl = '%spage/2/' % url
                    lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        elif meniu == 'steps':
            link = fetchData(url)
            sregex = '''(?:Sezonul <span>(.*?)</span.*?<i.*?)?"Num.*?">(.*?)<.*?src=(?:"|\&quot\;)(.+?)(?:"|\&quot\;).*?href="(.*?)">(.*?)</a>(?:<span>(.*?)</span>)?</td>'''
            opts = '''nv\=("Opt\d+")(?:><span)?>(.+?)<'''
            regex_lnk = '''.+?(%s/playerembed/.+?)(?:"|\&)''' % self.base_url
            match = re.findall(sregex, link, re.DOTALL)
            info = eval(info)
            if match:
                infos = info
                title = info.get('Title')
                plot = info.get('Plot')
                for sezon, numar, imagine, legatura, episod, an in match:
                    episod = episod.strip()
                    if sezon:
                        sezon = striphtml(sezon)
                        lists.append(('[COLOR lime]Sezon %s[/COLOR]' % sezon,'nolink','','nimic', {}))
                    try:
                        infos = info
                        infos['TVshowtitle'] = title
                        infos['Title'] = '%s %s' % (title, episod)
                        infos['Plot'] = infos.get('Title')
                    except: pass
                    lists.append((infos.get('Title'),legatura,'','steps', str(infos)))
            else: 
                matchnames = re.findall(opts, link)
                if matchnames:
                    for matchnumber, matchname in matchnames:
                        match = re.findall('PlayerTb.+?" id=' + matchnumber + regex_lnk, link, re.DOTALL)
                        if match:
                            for match1 in match:
                                if py3: nums = info.get('Title')
                                else: nums = info.get('Title').decode('utf-8')
                                lists.append(('%s %s' % (nums, striphtml(matchname)),match1,'','get_links', info))
        elif meniu == 'get_links':
            links = []
            regex_lnk = '''<iframe(?:.+?)?src=['"]((?:[htt]|[//]).+?)['"]'''
            regex_servers = '''(%s/playerembed/.+?)(?:"|\&)''' % self.base_url
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:70.1) Gecko/20100101 Firefox/70.1', 'Referer': url}
            s = requests.Session()
            link = s.get(url, headers=headers).text
            match3 = re.findall(regex_lnk, link, re.IGNORECASE|re.DOTALL)
            if match3:
                for match4 in match3:
                    string = re.findall('trhide.+?tid=(.+?)\&', match4, re.IGNORECASE|re.DOTALL)
                    if string:
                        string = string[0]
                        length = len(string) - 1
                        trde = ''
                        while (length >= 0): 
                            trde = trde + string[length]
                            length -= 1
                        urls = '%s/?trhide=1&trhex=%s' % (self.base_url, trde)
                        filmlink = s.get(urls, headers=headers, allow_redirects=False)
                        filmlink = filmlink.headers.get('Location')
                        links.append(filmlink)
                    else:
                        links.append(match4)
            else:
                match = re.findall(regex_lnk, link, re.IGNORECASE|re.DOTALL)
                if match:
                    for match1 in match:
                        links.append(match1)
            for host, link1 in get_links(links):
                lists.append((host,link1,'','play', info, url))
        elif meniu == 'cauta':
            from resources.Core import Core
            Core().searchSites({'landsearch': self.__class__.__name__})
        elif meniu == 'genuri':
            link = fetchData(url)
            regex = '''categorii(.*?)</ul'''
            regex_cat = '''<li.*?href="(.*?)">(.*?)<'''
            if link:
                match = re.findall(regex, link, re.IGNORECASE|re.DOTALL)
                if len(match) > 0:
                    for match1 in match:
                        match2 = re.findall(regex_cat, match1)
                        if match2:
                            for legatura, nume in match2:
                                nume = replaceHTMLCodes(nume).capitalize()
                                lists.append((nume,legatura.replace('"', ''),'','recente', info))
        return lists

class dozaanimata:
    
    base_url = 'https://www.dozaanimata.ro'
    thumb = os.path.join(media,'dozaanimata.jpg')
    nextimage = next_icon
    searchimage = search_icon
    name = 'DozaAnimata'
    menu = [('Desene', '%s/tag/desene/' % base_url, 'recente', thumb), 
            ('Anime', '%s/tag/anime/' % base_url, 'recente', thumb),
            ('Filme', '%s/genre/filme/'% base_url, 'recente', thumb),
            ('Seriale', '%s/series/'% base_url, 'recente', thumb),
            ('Canale', base_url, 'genuri', thumb),
            ('Căutare', base_url, 'cauta', searchimage)]
                

    def cauta(self, keyword):
        return self.__class__.__name__, self.name, self.parse_menu(self.get_search_url(keyword), 'recente')
        
    def get_search_url(self, keyword):
        url = '%s/page/1/?s=%s' % (self.base_url, quote(keyword))
        return url

    def parse_menu(self, url, meniu, info={}):
        lists = []
        if meniu == 'recente':
            link = fetchData(url)
            regex = '''data-movie-id=(.+?)clearfix"></div>'''
            mregex = '''href="(.+?)".+?(?:.+?quality(?:\s+tv)?"\>(.+?)\<)?.+?(?:.+?eps"\>(.+?)\</sp)?.+?data-original="(.+?)".+?info"\>(.+?)\</sp'''
            match = re.findall(regex, link, re.DOTALL)
            if len(match) > 0:
                for movies in match:
                    movie = re.findall(mregex, movies, re.DOTALL)
                    if movie:
                        for legatura, calitate, episod, imagine, nume in movie:
                            legatura = '%s%s' % (self.base_url, legatura) if legatura.startswith('/') else legatura
                            nume = replaceHTMLCodes(striphtml(nume))
                            if calitate:
                                nume = '%s [COLOR lime]%s[/COLOR]' % (nume, striphtml(calitate).strip())
                            if episod:
                                nume = '%s [COLOR lime]%s[/COLOR]' % (nume, striphtml(episod).strip())
                            info = {'Title': nume,'Plot': nume,'Poster': imagine}
                            
                            lists.append((nume,legatura,imagine,'get_links', info))
                match = re.compile("pagination'.+?page/", re.IGNORECASE).findall(link)
                if len(match) > 0 :
                    nexturl = ''
                    if '/page/' in url:
                        new = re.compile('/page/(\d+)').findall(url)
                        nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new[0]) + 1), url)
                    elif 'page=' in url:
                            new = re.compile('page\=(\d+)').findall(url)
                            nexturl = re.sub('page\=(\d+)', 'page\=' + str(int(new[0]) + 1), url)
                    else:
                        nexturl = '%spage/2/' % url
                    lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        elif meniu == 'get_links':
            url = '%s%s' % (self.base_url, url) if url.startswith('/') else url
            link = fetchData(url)
            seasons_regex = '''tvseason"(?:.*?\>(Sez.*?)\<)?.*?(.*?)\</div\>\s*\</div\>'''
            episode_regex = '''href="(.+?)">(.+?)<'''
            coded_lnk = '''text/javascript[\'"]>(?:\s+)?str=['"](.+?)["']'''
            regex_lnk = '''<iframe.+?src="((?:[htt]|[//]).+?)"'''
            if link:
                s = re.findall(seasons_regex, link, re.DOTALL)
                if s:
                    for sezonname, episodelist in s:
                        lists.append(('[COLOR lime]%s[/COLOR]' % sezonname.strip(),'nolink','','nimic', {}))
                        episodes = re.findall(episode_regex, episodelist, re.DOTALL)
                        if episodes:
                            for episodeurl, episodename in episodes:
                                lists.append((episodename.strip(),episodeurl.strip(),'','get_links', info))
                else:
                    match_coded = re.compile(coded_lnk, re.IGNORECASE | re.DOTALL).findall(link)
                    match_lnk = re.findall(regex_lnk, link, re.DOTALL)
                    for host, link1 in get_links(match_lnk):
                        lists.append((host,link1,'','play', info, url))
                    list_link = []
                    for one_code in match_coded:
                        decoded = ''
                        try:
                            decoded = re.findall('<(?:iframe|script).+?src=[\'"]((?:[htt]|[//]).+?)["\']', unquote(one_code.replace('@','%')), re.IGNORECASE | re.DOTALL)[0]
                        except:
                            decoded = unquote(one_code.replace('@','%'))
                        list_link.append(decoded)
                    for host, link1 in get_links(list_link):
                        lists.append((host,link1,'','play', info, url))
        elif meniu == 'cauta':
            from resources.Core import Core
            Core().searchSites({'landsearch': self.__class__.__name__})
        elif meniu == 'genuri':
            link = fetchData(url)
            regex = '''Canale.+?<ul(.+?)</ul'''
            regex_cat = '''<li.+?href="(.+?)">(.+?)<'''
            if link:
                match = re.findall(regex, link, re.DOTALL)
                if len(match) > 0:
                    match2 = re.findall(regex_cat, match[0])
                    if match2:
                        for legatura, nume in match2:
                            nume = replaceHTMLCodes(nume).capitalize()
                            lists.append((nume,legatura.replace('"', ''),'','recente', info))
        return lists

class filmehdnet:
    
    base_url = 'https://filmehd.se'
    thumb = os.path.join(media, 'filmehdnet.jpg')
    nextimage = next_icon
    searchimage = search_icon
    name = 'FilmeHD.net'
    menu = [('Recente', base_url + '/page/1', 'recente', thumb), 
            ('Categorii', base_url, 'genuri', thumb),
            ('După ani', base_url, 'ani', thumb),
            ('Seriale', base_url + '/seriale', 'recente', thumb),
            ('De colecție', base_url + '/filme-vechi', 'recente', thumb),
            ('Căutare', base_url, 'cauta', searchimage)]
        
    def get_search_url(self, keyword):
        url = self.base_url + '/?s=' + quote(keyword)
        return url

    def getKey(self, item):
        return item[1]

    def cauta(self, keyword):
        return self.__class__.__name__, self.name, self.parse_menu(self.get_search_url(keyword), 'recente')

    def parse_menu(self, url, meniu, info={}):
        lists = []
        imagine = ''
        if meniu == 'recente' or meniu == 'cauta':
            if meniu == 'cauta':
                from resources.Core import Core
                Core().searchSites({'landsearch': self.__class__.__name__})
            else: 
                link = fetchData(url)
                regex_submenu = '''class="imgleft".+?href="(.+?)".+?src="(.+?)".+?href.+?>(.+?)<'''
                if link:
                    match = re.compile(regex_submenu, re.DOTALL).findall(link)
                    for legatura, imagine, nume in match:
                        if py3: nume = replaceHTMLCodes(nume)
                        else: nume = replaceHTMLCodes(nume.decode('utf-8')).encode('utf-8')
                        info = {'Title': nume,'Plot': nume,'Poster': imagine}
                        if 'serial-tv' in legatura or 'miniserie-tv' in legatura:
                            try:
                                if re.search('–|-|~', nume):
                                    all_name = re.split(r'–|-|:|~', nume,1)
                                    title = all_name[0]
                                    title2 = all_name[1]
                                else: title2 = ''
                                title, year = xbmc.getCleanMovieTitle(title)
                                title2, year2 = xbmc.getCleanMovieTitle(title2)
                                title = title if title else title2
                                year = year if year else year2
                                info['Year'] = year
                                info['TVShowTitle'] = title
                            except:pass
                        lists.append((nume, legatura, imagine, 'get_all', info))
                    match = re.compile('class=\'wp-pagenavi', re.IGNORECASE).findall(link)
                    if len(match) > 0:
                        if '/page/' in url:
                            new = re.compile('/page/(\d+)').findall(url)
                            nexturl = re.sub('/page/(\d+)', '/page/' + str(int(new[0]) + 1), url)
                        else:
                            if '/?s=' in url:
                                nextpage = re.compile('\?s=(.+?)$').findall(url)
                                nexturl = '%s%s?s=%s' % (self.base_url, ('page/2/' if str(url).endswith('/') else '/page/2/'), nextpage[0])
                            else: nexturl = url + "/page/2"
                        lists.append(('Next', nexturl, self.nextimage, meniu, {}))
        elif meniu == 'get_all':
            link = fetchData(url)
            regex_lnk = '''(?:id="tabs_desc_\d+_(.*?)".*?)?(?:<center>(.*?)</center>.*?)?data-src=['"]((?:[htt]|[//]).*?)['"]'''
            regex_infos = '''Descriere film.+?p>(.+?)</p'''
            match_lnk = re.findall(regex_lnk, link, re.IGNORECASE | re.DOTALL)
            match_nfo = re.findall(regex_infos, link, re.IGNORECASE | re.DOTALL)
            info = eval(str(info))
            try:
                info['Plot'] = (striphtml(match_nfo[0]).strip())
            except: pass
            for server, name, legatura in match_lnk:
                if server: lists.append(('Server %s' % server,legatura,'','nimic', info, url))
                if not legatura.startswith('http'):
                    legatura = '%s%s' % (self.base_url, legatura.replace('&amp;', '&'))
                name = striphtml(name)
                if info.get('TVShowTitle'):
                    try:
                        szep = re.findall('sezo[a-zA-Z\s]+(\d+)\s+epi[a-zA-Z\s]+(\d+)', name, re.IGNORECASE)
                        if szep:
                            info['Season'] = str(szep[0][0])
                            info['Episode'] = str(szep[0][1])
                    except: pass
                if name: lists.append((name,legatura,'','get_links', str(info)))
        elif meniu == 'get_links':
            link = fetchData(url)
            regex_lnk = '''<iframe(?:.+?)?src=['"]((?:[htt]|[//]).+?)['"]'''
            match_lnk = re.compile(regex_lnk, re.IGNORECASE | re.DOTALL).findall(link)
            for host, link1 in get_links(match_lnk):
                lists.append((host,link1,'','play', info, url))
        elif meniu == 'genuri':
            link = fetchData(url)
            cats = []
            regex_menu = '''GEN FILM.*<ul\s+class="sub-menu(.+?)</ul>'''
            regex_submenu = '''<li.+?a href="(.+?)">(.+?)<'''
            for meniu in re.compile(regex_menu, re.IGNORECASE | re.MULTILINE | re.DOTALL).findall(link):
                match = re.compile(regex_submenu, re.DOTALL).findall(meniu)
                for legatura, nume in match:
                    if py3: nume = replaceHTMLCodes(nume).capitalize()
                    else: nume = replaceHTMLCodes(nume.decode('utf-8')).encode('utf-8').capitalize()
                    cats.append((legatura, nume))
                cats.append(('https://filmehd.se/despre/filme-romanesti', 'Romanesti'))
            for legatura, nume in sorted(cats, key=self.getKey):
                lists.append((nume,legatura.replace('"', ''),self.thumb,'recente', info))
        elif meniu == 'ani':
            import datetime
            an = datetime.datetime.now().year
            while (an > 1929):
                legatura = self.base_url + '/despre/filme-' + str(an)
                lists.append((str(an),legatura,self.thumb,'recente', info))
                an -= 1
        return lists
