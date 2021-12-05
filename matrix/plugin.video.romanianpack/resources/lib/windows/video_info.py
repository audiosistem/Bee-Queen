# -*- coding: utf-8 -*-

from resources.functions import *
from resources.lib.windows.base import BaseDialog


class VideoInfoXML(BaseDialog):
    def __init__(self, *args, **kwargs):
        super(VideoInfoXML, self).__init__(self, args)
        self.window_id = 2000
        self.content = kwargs.get('content')
        self.nameorig = kwargs.get('nameorig')
        self.imdb = kwargs.get('imdb')
        self.castplot = 'Plot'
        self.morelikethis = None
        self.mlthis_items = None
        self.plot = ''
        self.meta = None
        self.info = None
        self.cm = None
        self.get_infos()
        self.make_items()
        self.set_properties()

    def onInit(self):
        super(VideoInfoXML, self).onInit()
        win = self.getControl(self.window_id)
        win.addItems(self.item_list)
        if self.morelikethis:
            self.setProperty('mrsp.morelikethis', 'True')
            wintwo = self.getControl(2001)
            wintwo.addItems(self.morelikethis)
        self.setFocusId(99)

    def run(self):
        self.doModal()
        try: del self.info
        except: pass
        try: del self.cm
        except: pass
        return self.selected

    def onAction(self, action):
        try:
            action_id = action.getId()
            if action_id in self.selection_actions:
                focus_id = self.getFocusId()
                chosen_source = self.item_list[self.get_position(self.window_id)]
                source = chosen_source.getProperty('mrsp.propvalue')
                if focus_id == 99:
                    if self.castplot == 'Plot':
                        self.castplot = 'Cast'
                        self.setProperty('mrsp.plot', self.meta.get('castandchar'))
                    else:
                        self.castplot = 'Plot'
                        self.setProperty('mrsp.plot', self.plot)
                    self.setProperty('mrsp.castplot', self.castplot)
                if focus_id == 101:
                    code = quote('%s' % (self.meta.get('original_title') or self.nameorig))
                    self.selected = ('search_name', code)
                    self.close()
                if focus_id == 2001:
                    mlt_chosen = self.morelikethis[self.get_position(focus_id)]
                    mlt_link = mlt_chosen.getProperty('mrsp.mltlink')
                    self.nameorig = mlt_chosen.getProperty('mrsp.mlttitle')
                    mlt_link = 'https://www.imdb.com%s' % mlt_link
                    mlt_link = re.sub('\?ref.*?$', '', mlt_link)
                    headers={'Accept-Language': 'ro-RO'}
                    self.content = fetchData(mlt_link, headers=headers)
                    self.castplot = 'Plot'
                    self.setProperty('mrsp.morelikethis', '')
                    self.morelikethis = None
                    self.mlthis_items = None
                    self.plot = ''
                    self.meta = None
                    self.info = None
                    self.cm = None
                    self.get_infos()
                    self.make_items()
                    self.set_properties()
                    win = self.getControl(self.window_id)
                    win.reset()
                    win.addItems(self.item_list)
                    if self.morelikethis:
                        self.setProperty('mrsp.morelikethis', 'True')
                        wintwo = self.getControl(2001)
                        wintwo.reset()
                        wintwo.addItems(self.morelikethis)
                if focus_id == 100 and self.meta.get('Trailer'):
                    params = {'nume' : self.meta.get('Title'), 'plot': self.meta.get('Plot'), 'poster': self.meta.get('poster_path'), 'link': self.meta.get('Trailer')}
                    self.selected = (None, '')
                    self.close()
                    playTrailerImdb(params)
            if action in self.closing_actions:
                self.selected = (None, '')
                self.close()
        except BaseException as e:
            log('onAction')
            log(e)

    def get_infos(self):
        #log(content)
        imdb_aka_container = '''(?:>Also Known As\:(?:</.*?>\s+)?(.+?)\n)|(?:>Also Known As.*?">(.*?)</span)'''
        imdb_cast_container = '''(?:<section.*?title-cast.*?">(.*?)</section>)|(?:cast_list">(.*?)</table)'''
        imdb_castandchar = '''(?:primary_photo.*?src=".*?".*?/name/.*?>(.*?)<.*?"character">(.*?)</a)|(?:ActorName.*?>(.+?)<div data-testid="title-cast-item")'''
        imdb_company_container = '''(?:Production Co:(.*?)</div)|(?:title-details-companies">(.*?)</path><path)'''
        imdb_company = '''href="/company/.*?>(.*?)<'''
        imdb_country_container = '''(?:Country:(.*?)</div)|(?:title-details-origin">(.*?)</ul>)'''
        imdb_country = '''href=.*?country_of.*?>(.*?)<'''
        imdb_seasons = '''(?:seasons-and-year-nav.*?href=.*?episodes\?season.*?>(.*?)<)|(?:label for="browse-episodes-season".*?">(.*?)</label)'''
        imdb_director_container = '''(?:(?:Creator|Director)(?:s)?:(.*?)</div)|(?:(?:Creator|Director)(?:s)?.*?<ul(.*?)</ul)'''
        imdb_director = '''href="/name/.*?>(.*?)<'''
        imdb_info_container = '''"title_wrapper">(.*?)</div>\s+</div>'''
        imdb_genre = '''href=.*?genre.*?>(.*?)<'''
        imdb_genre_container = '''storyline-genres">(.*?)</ul>'''
        imdb_id = '''((?:tt\d{6,})|(?:itle\?\d{6,}))/reference'''
        imdb_language_container = '''Language:(.*?)</div'''
        imdb_language = '''href=.*?language.*?>(.*?)</a>'''
        imdb_location = '''href=['"]/search/title\?locations=.*?['"]>(.*?)</a>'''
        imdb_mpaa = '''<h5><a href=['"]/mpaa['"]>MPAA</a>:</h5>(?:\s*)<div class=['"]info-content['"]>(.*?)</div>'''
        imdb_not_found = '''<h1 class=['"]findHeader['"]>No results found for '''
        imdb_tagline = '''(?:"summary_text">(.*?)<)|(?:data-testid="plot-xl.*?">(.*?)<)'''
        imdb_poster = '''(?:<link rel=['"]image_src['"] href=['"](.*?)['"]>)|(?:(?:PosterContainer|MediaContainer).*?poster-image.*?src="(.*?)")'''
        imdb_rating = '''"AggregateRating".*?"ratingValue":(?:\s+")?(.*?)(?:"|\})'''
        imdb_release_date = '''/releaseinfo.*?>(.*?)<'''
        imdb_runtime = '''datetime.*?>(.*?)<'''
        imdb_fanart = '''(?:"mediastrip".*?<img .*?loadlate="(.*?)")|(?:"photos-header".*?ipc-photo.*?src="(.*?)")'''
        imdb_plot = '''(?:Storyline.*?inline canwrap.*?<span>(.*?)</s)|(?:\="storyline-plot-summary">.*?"ipc.*?<div>(.*?)</div)'''
        imdb_title = '''property=['"]og:title['"] content="(.*?)"'''
        imdb_title_orig = '''(?:originalTitle">(.*?)<)|(?:>original\s+Title\:(.*?)<)'''
        imdb_trailer = '''(?:video_slate"|media__slate-overlay).*?href="(.*?)"'''
        imdb_trailer_first = '''trailer".*?"embedUrl": "(.*?)"'''
        imdb_votes = '''"ratingCount":(.*?)\,''';
        imdb_writer_container = '''(?:Writer(?:s)?:(.*?)</div)|(?:Writer(?:s)?.*?<ul(.*?)</ul)'''
        imdb_writer = '''href="/name/.*?>(.*?)<''';
        imdb_year = '''(?:/releaseinfo\?.*?#releases.*?">(.*?)<)|(?:more release dates"\s+>(.*?)<)'''
        imdb_created = '''"datePublished":\s?"(.*?)"'''
        imdb_episodes = '''(?:bp_sub_heading">(.*?)<)|(?:ipc-title__text">(Episodes.*?</span>))'''
        imdb_more_like_this_container = '''FeatureHeader.*?More like this.*?ipc-shoveler__arrow--left(.*?)ipc-shoveler__arrow--right'''
        imdb_more_like_this_container_doi = '''div class="rec_item"(.*?)</a>'''
        imdb_more_like_this = '''ipc-poster-card--base.*?ipc-image.*?src="(.*?)".*?ipc-rating-star.*?</svg>(.*?)</span>.*?ipc-poster-card__title.*?href="(.*?)".*?">(.*?)<'''
        imdb_more_like_this_doi = '''href="(.*?)".*?title="(.*?)".*?loadlate="(.*?)"'''
        created = ''
        if self.content:
            getposter = self.get_data(imdb_poster, self.content)
            if getposter : poster = re.sub(r'@\..+?.(\w{3}$)', r'@.\1', ''.join(getposter[0]))
            else: poster = ''
            getbackdrop = self.get_data(imdb_fanart, self.content)
            if getbackdrop: backdrop = re.sub(r'@\..+?.(\w{3}$)', r'@.\1', ''.join(getbackdrop[0]))
            else: backdrop = poster
            title = replaceHTMLCodes(striphtml(self.get_data(imdb_title, self.content)[0]))
            try: original_title = ''.join(self.get_data(imdb_title_orig, self.content)[0])
            except: original_title = ''
            try: production_countries = ", ".join(self.get_data(imdb_country, ''.join(self.get_data(imdb_country_container, self.content)[0])))
            except: production_countries = ''
            getcast = self.get_data(imdb_cast_container, self.content)
            if getcast:
                getcast = ''.join(getcast[0])
                castc = []
                for actor,role,actor1 in self.get_data(imdb_castandchar, getcast):
                    if actor1 and not actor:
                        try:
                            actor = self.get_data('^(.*?)<', actor1)[0]
                            roledata = self.get_data('>as\s*(.*?)<', actor1)
                            if roledata:
                                role = roledata[0]
                        except: pass
                    actor = replaceHTMLCodes(striphtml(actor))
                    role = replaceHTMLCodes(striphtml(role))
                    castc.append("%s%s" % (actor, (' [COLOR lime]as %s[/COLOR]' % role) if role else ''))
                castandchar = ", ".join(castc)
                castandchar = " ".join(castandchar.split())
            else: castandchar = ''
            info_container = self.get_data(imdb_info_container, self.content)
            try:
                if info_container:
                    genres = ", ".join(self.get_data(imdb_genre, info_container[0]))
                else:
                    genres = ", ".join(self.get_data(imdb_genre, ''.join(self.get_data(imdb_genre_container, self.content))))
            except: genres = ''
            try: 
                production_companies = ", ".join(self.get_data(imdb_company, ''.join(self.get_data(imdb_company_container, self.content)[0])))
            except: 
                production_companies = ''
            try: tagline = replaceHTMLCodes(''.join(self.get_data(imdb_tagline, self.content)[0])).strip()
            except: tagline = ''
            try: rating = self.get_data(imdb_rating, self.content)[0].strip()
            except: rating = ''
            try: votes = self.get_data(imdb_votes, self.content)[0].strip()
            except: votes = ''
            try: 
                if info_container:
                    release_date = self.get_data(imdb_release_date, info_container[0])[0]
                else:
                    release_date = self.get_data('ipc-metadata-list-item__list-content-item--link".*?/releaseinfo\?.*?rdat">(.*?)<', self.content)[0]
            except: release_date = ''
            try: overview = striphtml(replaceHTMLCodes(''.join(self.get_data(imdb_plot, self.content)[0])).strip())
            except: overview = ''
            try: 
                aka = self.get_data(imdb_aka_container, self.content)
                aka = ''.join(aka[0])
                aka = striphtml(aka)
            except: aka = ''
            try:
                if info_container:
                    spoken_languages = ", ".join(self.get_data(imdb_language, self.get_data(imdb_language_container, self.content)[0]))
                else:
                    spoken_languages = self.get_data('"title-details-languages">(.*?)</ul>', self.content)
                    spoken_languages = ", ".join(self.get_data(imdb_language, spoken_languages[0]))
            except: spoken_languages = ''
            try:
                writers = self.get_data(imdb_writer_container, self.content)
                writers = [j for i in writers for j in i]
                writers = ''.join(writers)
                writers = self.get_data(imdb_writer, writers)
                writers = list(set(writers))
                writers = ", ".join(writers)
            except: writers = ''
            try: 
                if info_container:
                    runtime = self.get_data(imdb_runtime, info_container[0])[0].strip()
                else:
                    runtime = striphtml(self.get_data('techspec_runtime".*?</span>.*?>(.*?)</div', self.content)[0])
            except: runtime = ''
            try:
                directors = self.get_data(imdb_director_container, self.content)
                directors = [j for i in directors for j in i]
                directors = ''.join(directors)
                directors = self.get_data(imdb_director, directors)
                directors = list(set(directors))
                directors = ", ".join(directors)
            except: directors = ''
            try: 
                seasons = self.get_data(imdb_seasons, self.content)
                seasons = ''.join(seasons[0])
            except: seasons = ''
            if seasons:
                try: created = self.get_data(imdb_created, self.content)[0]
                except: pass
            try: episodes = striphtml(''.join(self.get_data(imdb_episodes, self.content)[0]))
            except: episodes = ''
            try: 
                trailer = self.get_data(imdb_trailer_first, self.content)
                trailer.extend(self.get_data(imdb_trailer, self.content))
            except: trailer = ''
            mlthis = self.get_data(imdb_more_like_this_container, self.content)
            if mlthis:
                mlthis_items = self.get_data(imdb_more_like_this, mlthis[0])
                if mlthis_items:
                    self.mlthis_items = mlthis_items
            else:
                mlthis = self.get_data(imdb_more_like_this_container_doi, self.content)
                if mlthis:
                    mlthis_items = self.get_data(imdb_more_like_this_doi, ''.join(mlthis))
                    if mlthis_items:
                        self.mlthis_items = mlthis_items
            if self.mlthis_items: 
                self.make_mlthis_items()
            #traktwatch = self.get_data(imdb_id, content)[0] if self.get_data(imdb_id, content) else ''
            self.meta = {
                'poster_path': poster,
                'backdrop_path': backdrop,
                'Title': title,
                'original_title': original_title,
                'Country': production_countries,
                'castandchar': castandchar,
                'Genre': genres,
                'Company': production_companies,
                'overview': overview if overview else tagline,
                'Language': spoken_languages,
                'IMdb Rating': ('%s from %s votes' % (rating, votes)) if rating else '',
                'Released': release_date,
                'Tagline': tagline,
                'AKA': aka,
                'Writer': writers,
                'Director': directors,
                'Runtime': runtime,
                'Trailer': trailer,
                'Seasons': seasons,
                'First Episode': created,
                'Total aired': episodes}
            if self.imdb:
                self.meta['imdb'] = self.imdb
        
    def make_items(self):
        def builder():
            data = ['poster_path', 'backdrop_path', 'castandchar', 'Title', 'original_title', 'Tagline']
            for info in self.meta:
                try:
                    if self.meta.get(info):
                        listitem = self.make_listitem()
                        if info in data : continue
                        if info == 'imdb':
                            continue
                        if info == 'Trailer':
                            continue
                        elif info == 'overview':
                            continue

                        listitem.setProperty('mrsp.propname', info)
                        listitem.setProperty('mrsp.propvalue', self.meta.get(info))
                        yield listitem
                except BaseException as e:
                    log('enumerate meta')
                    log(e)
        try:
            self.item_list = list(builder())
        except BaseException as e:
            log('make items')
            log(e)
            
    def make_mlthis_items(self):
        if self.mlthis_items:
            def builder():
                if len(self.mlthis_items[0]) > 3:
                    try:
                        for imagine_item, rating_item, legatura_item, nume_item in self.mlthis_items:
                            listitem = self.make_listitem()
                            listitem.setProperty('mrsp.mlticon', imagine_item)
                            listitem.setProperty('mrsp.mlttitle', nume_item)
                            listitem.setProperty('mrsp.mltlink', legatura_item)
                            yield listitem
                    except BaseException as e:
                        log('mlthis 1')
                        log(e)
                else:
                    try:
                        for legatura_item, nume_item, imagine_item in self.mlthis_items:
                            listitem = self.make_listitem()
                            listitem.setProperty('mrsp.mlticon', imagine_item)
                            listitem.setProperty('mrsp.mlttitle', nume_item)
                            listitem.setProperty('mrsp.mltlink', legatura_item)
                            yield listitem
                    except BaseException as e:
                        log('mlthis 2')
                        log(e)
            try:
                self.morelikethis = list(builder())
            except BaseException as e:
                self.setProperty('mrsp.morelikethis', '')
                log('make_mlthis_items')
                log(e)

    def set_properties(self):
        try:
            if self.meta is None: return
            if self.meta.get('backdrop_path'):
                self.setProperty('mrsp.backdrop', self.meta.get('backdrop_path'))
            if self.meta.get('poster_path'):
                self.setProperty('mrsp.fanart', self.meta.get('poster_path'))
            if self.meta.get('Title'):
                self.setProperty('mrsp.title', self.meta.get('Title'))
            if self.meta.get('original_title'):
                self.setProperty('mrsp.original_title', self.meta.get('original_title'))
            if self.meta.get('castandchar'):
                self.setProperty('mrsp.cast', self.meta.get('castandchar'))
            if self.meta.get('Tagline'):
                self.setProperty('mrsp.tagline', self.meta.get('Tagline'))
            if self.nameorig:
                self.setProperty('mrsp.titlu_site', self.nameorig)
            if self.meta.get('Trailer'):
                self.setProperty('mrsp.trailercolor', 'yellow')
            else:
                self.setProperty('mrsp.trailercolor', 'gray')
            self.setProperty('mrsp.castplot', self.castplot)
            try: self.plot = self.meta.get('overview').decode('utf-8')
            except: self.plot = self.meta.get('overview')
            self.setProperty('mrsp.plot', self.plot)
        except BaseException as e:
            log('set properties')
            log(e)
    def get_data(self, regex, content):
        try: s = re.findall(regex, content, re.DOTALL | re.IGNORECASE)
        except: s = re.findall(regex, content.decode('utf-8'), re.DOTALL | re.IGNORECASE)
        return s
