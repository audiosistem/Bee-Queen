import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import xml.dom.minidom as md
from resources.lib.functions import log, showMessage
import requests

main_site = 'www.cinemagia.ro'
main_url = 'https://%s/program-tv/' % main_site
headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Encoding': 'identity',
                'Accept-Language': 'en-US,en;q=0.5', 
                'Connection': 'keep-alive',
                'Host': main_site,
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:60.0) Gecko/20100101 Firefox/60.0'
            }

class Channels():
    
    def get(self):
        url = main_url
        req = requests.get(url, headers=headers, verify=False)
        html = req.content.decode()
        regex = '''<li class="station-container">.*?href="{0}(.*?)/".*?>(.*?)<'''.format(url)
        channels = re.findall(regex, html, re.DOTALL)
        if channels:
            channels = sorted(channels, key=lambda x: x[0].lower())
            try: addonpath = xbmcvfs.translatePath(path.decode('utf-8'))
            except: addonpath = xbmcvfs.translatePath(path)
            from resources.lib.windows.channel_list import ChannelsXML
            window = ChannelsXML('channel_list.xml', addonpath, 'Default', channels=channels)
            action, code = window.run()
            del window
            #log('action')
            #log(action)

class Cinemagia():
    url = '%spost/' % main_url
    generator = 'service.cinemagia'
    filePath = 'tvxml.xml'
    cats = None
    epg_details = 'true'
    headers = headers

    def __init__( self , *args, **kwargs):
        self.filePath=kwargs.get('filePath')
        self.cats=kwargs.get('cats')
        self.wanted=kwargs.get('wanted') or [('','')]
        self.days=kwargs.get('days')
        self.epg_details=kwargs.get('epg_details')

    def execute(self, dlg=None, notify=False):
        tv = ET.Element('tv')
        tv.set('generator-info-name', self.generator)
        tv.set('source-info-url', self.url)
        tv.set('source-info-name', 'cinemagia')
        j = 0
        for program, name in self.wanted:
            #print(name)
            channel = ET.SubElement(tv, 'channel')
            channel.set('id', name)
            displayName = ET.SubElement(channel, 'display-name')
            displayName.text = name
            if dlg:
                percent = (j + 1) * 100 / len(self.wanted)
                dlg.update(int(percent), message=name)
            self.scrapEpg('%s%s/' % (self.url, program), tv, name)
            j += 1
        xmlstr = ET.tostring(tv)
        #newxml = md.parse(xmlstr)
        newxml = md.parseString(xmlstr)
        with open(self.filePath,'w', encoding='utf-8') as outfile:
            outfile.write(newxml.toprettyxml(indent='\t',newl='\n'))
        if(dlg):
            dlg.close()
        if notify:
            showMessage('Cinemagia', 'EPG extraction finished')
        #tree = ET.ElementTree(tv)
        #tree.write(self.filePath, encoding='utf-8', xml_declaration=True)
    def scrapEpg(self, url, tv, channelName):
        #print(url)

        req = requests.get(url, headers=self.headers, verify=False)
        html = req.content.decode()

        currentDate = datetime.now()
        k = 0
        while k <= self.days-1:
            arrIds = ['morning', 'evening']
            if k == 0:
                ccurrentDate = currentDate
            else:
                ccurrentDate = currentDate + timedelta(days=k)
            for idNode in arrIds:
                soup = BeautifulSoup(html, "html.parser")
                contNode = soup.find('div', {'data-day-period' : idNode})
                if(contNode):
                    try: 
                        contEvents = contNode.findChildren(class_='container_events')[k]
                        oraNodes = contEvents.findChildren('td', class_='ora')
                        eventNodes = contEvents.findChildren('td', class_='event')
                        
                        i=0
                        for oraNode in oraNodes:
                            ora = oraNode.contents[1].string
                            titleNode = eventNodes[i].findChild(class_='title')
                            titleLinkNode = titleNode.findChild('a', title=True, href=True)
                            if(titleLinkNode):
                                title = titleLinkNode['title']
                            else:
                                title = titleNode.contents[0]
                            additional_title = titleNode.find('span', {'class' : None})
                            if additional_title:
                                title += additional_title.text
                            title = ' '.join(title.split())
                            descriptionNode = eventNodes[i].findChild(class_='small')
                            if descriptionNode:
                                description = descriptionNode.text
                            else:
                                description = ''
                            #start datetime
                            arrOra = ora.split(':')
                            h = int(arrOra[0])
                            m = int(arrOra[1])
                            startDateTime = ccurrentDate.replace(hour=h, minute=m, second=0, microsecond=0)
                            # next day
                            if(h < 7):
                                startDateTime += timedelta(days=1)
                                #print(startDateTime)

                            #stop datetime
                            if((i+1) < len(oraNodes)):
                                ora = oraNodes[i+1].contents[1].string
                                arrOra = ora.split(':')
                                h = int(arrOra[0])
                                m = int(arrOra[1])
                                stopDateTime = ccurrentDate.replace(hour=h, minute=m, second=0, microsecond=0)
                                # next day
                                if(h < 7):
                                    stopDateTime += timedelta(days=1)
                            else:
                                stopDateTime = ccurrentDate.replace(hour=7, minute=0, second=0, microsecond=0)
                                stopDateTime += timedelta(days=1)
                                #print(stopDateTime)

                            programmeElm = ET.SubElement(tv, 'programme')
                            programmeElm.set('start', startDateTime.strftime("%Y%m%d%H%M%S %z"))
                            programmeElm.set('stop', stopDateTime.strftime("%Y%m%d%H%M%S %z"))
                            programmeElm.set('channel', channelName)
                            titleElm = ET.SubElement(programmeElm, 'title')
                            titleElm.text = title
                            dateElm = ET.SubElement(programmeElm, 'date')
                            dateElm.text = startDateTime.strftime("%Y%m%d")

                            #event details
                            self.getEventDetails(titleLinkNode, programmeElm, description)

                            i=i+1
                    except BaseException as e: 
                        log(e)
                        pass
            k += 1

    def getEventDetails(self, titleLinkNode, programmeElm, description):
        descAll = ''
        descAll += description
        if self.epg_details == 'true':
            if titleLinkNode:
                url = titleLinkNode['href']
                req = requests.get(url, None, headers=self.headers, verify=False)
                html = req.content.decode()

                soup = BeautifulSoup(html, "html.parser")

                genNode = soup.find('div', id='movieGenreUserChoiceResults')
                log('genuri')
                log(genNode.text.strip())
                if(genNode):
                    gen = genNode.text.strip()
                    p = re.compile('[\n]+')
                    gen = p.sub(", ", gen)
                    descAll += gen

                ratingNode = soup.find('div', class_='imdb-rating')
                if(ratingNode):
                    rating = ratingNode.text.strip()
                    descAll += "\n" + rating
            
                descNode = soup.find('div', id='short_body_sinopsis')
                if(descNode):
                    desc= descNode.text.strip()
                    descAll += "\n" + desc
        
        # print(descAll)
        if descAll:
            descElm = ET.SubElement(programmeElm, 'desc')
            descElm.text = descAll
            descElm.set('lang', 'ro')
