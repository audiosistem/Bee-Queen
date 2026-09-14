# -*- coding: utf-8 -*-
# RomyLive+ - modified for "Canale TV Romania 2" categories
# Original protected wrapper unpacked for maintainability.

import sys
import os as _romy_os
# Ensure our modified plugin root is importable so we can load `categorize`.
try:
    _ROMY_ROOT = _romy_os.path.dirname(_romy_os.path.abspath(__file__))
    if _ROMY_ROOT and _ROMY_ROOT not in sys.path:
        sys.path.insert(0, _ROMY_ROOT)
except Exception:
    _ROMY_ROOT = ''
try:
    from categorize import classify as _rds_classify, CATEGORY_ORDER as _RDS_CATEGORY_ORDER, CATEGORY_ADULTI as _RDS_CAT_ADULTI
except Exception:
    _rds_classify = lambda n: 'Diverse'
    _RDS_CATEGORY_ORDER = ['Filme','Sport','Stiri','Copii','Muzica','Documentare','Generaliste / Divertisment','Adulti','Diverse']
    _RDS_CAT_ADULTI = 'Adulti'

# Local icon path used for the new "Canale TV Romania 2" section and its subcategories.
_ROMY_LOCAL_ICON = 'special://home/addons/plugin.video.RomyLive/icon.png'
_ROMY_LOCAL_FANART = 'special://home/addons/plugin.video.RomyLive/fanart.png'

try:
    import cookielib
except ImportError:
    import http.cookiejar as cookielib
try:
    import urllib.parse as urllib
except ImportError:
    import urllib
try:
    import urllib2
except ImportError:
    import urllib.request as urllib2
import datetime
from datetime import datetime
import re
import os
import base64
import codecs
import itertools
import string
import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmcvfs
import traceback
import time
import resolveurl
import requests

try:
    import json
except:
    import simplejson as json

try:
    from html import unescape as html_unescape
except:
    from HTMLParser import HTMLParser
    html_unescape = HTMLParser().unescape

class KodiPath(str):
    def decode(self, encoding='utf-8', errors='strict'):
        return str(self)


def kodi_translate_path(path):
    try:
        translated = xbmcvfs.translatePath(path)
    except AttributeError:
        translated = kodi_translate_path(path)
    if isinstance(translated, bytes):
        translated = translated.decode('utf-8')
    return KodiPath(translated)

##CONFIGURAÇÕES
####  TITULO DO MENU  #################################################################
title_menu = ''
###  DESCRIÇÃO DO ADDON ###############################################################
title_descricao = 'Descrição do addon'

####  LINK DO TITULO DE MENU  #########################################################
## OBS: POR PADRÃO JÁ TEM UM MENU EM BRANCO PARA NÃO TER ERRO AO CLICAR ###############
url_b64_title = ''
#url_title = base64.b64decode(url_b64_title).decode('utf-8')
url_title = ''


##### PESQUISA - get.php
#url_b64_pesquisa = ''
#url_pesquisa = base64.b64decode(url_b64_pesquisa).decode('utf-8')
url_pesquisa = 'http://teste.com/get.php'
menu_pesquisar = '[COLOR white][B]PESQUISAR...[/B][/COLOR]'
thumb_pesquisar = ''
fanart_pesquisar = ''
#### Descrição Pesquisa
desc_pesquisa = 'Pesquise por filme'
## MENU CONFIGURAÇÕES
menu_configuracoes = '[B][COLOR white]CONFIGURAÇÕES[/COLOR][/B]'
thumb_icon_config = ''
desc_configuracoes = ''
## FAVORITOS
menu_favoritos = '[B][COLOR white]FAVORITOS[/COLOR][/B]'
thumb_favoritos = ''
desc_favoritos = ''

#### MENU VIP ################################################################
titulo_vip = '[COLOR white][B]ÁREA DE ACESSO[/B][/COLOR] [COLOR gold][B](VIP)[/B][/COLOR]'
thumbnail_vip = ''
fanart_vip = ''
#### DESCRIÇÃO VIP ###########################################################
vip_descricao = ''
#### DIALOGO VIP - SERVIDOR DESATIVADO - CLICK ###################################
vip_dialogo = 'No Kodi só canais pelo vip, use o app'
##SERIVODR VIP
url_server_vip = ''


## MULTLINK
## nome para $nome, padrão: lsname para $lsname
playlist_command = 'nome'
dialog_playlist = '[COLOR white][B]Selecteaza -->[/B][/COLOR]'


# user agent - Padrão: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36
useragent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36'

# Base - seu link principal
url_b64_principal = 'url base 64 encode'
url_principal = 'https://documentarys.do.am/2026/Principal/main.md'
url_filme_principal = 'https://documentarys.do.am/2026/filme/principal.txt'
url_vidzstore_filme = 'https://premieres.vidzstore.com/upload/2026/'
url_tv_principal = 'https://documentarys.do.am/2026/TV/Principal.txt'
url_tv_adult = 'https://documentarys.do.am/2026/TV/erotic.txt'
url_sitefilme = 'https://sitefilme.com/'
url_portalultautv = 'https://portalultautv.info/'
url_portalultautv_adult = 'https://portalultautv.info/category/filme-erotice-online/'
thumb_portalultautv = 'https://documentarys.do.am/2026/Principal/romylive.png'
thumb_portalultautv_adult = 'https://documentarys.do.am/2026/TV/logo/xxx.jpg'
url_paradisehill = 'https://en.paradisehill.cc/'
url_filmebunehd = 'https://filmebunehd1.com'
thumb_filmebunehd = 'https://documentarys.do.am/2026/Principal/romylive.png'
fanart_filmebunehd = 'https://documentarys.do.am/2026/Principal/romylive.png'
url_dinbox_tv = 'dinbox://tv'
url_tv_sports = 'https://documentarys.do.am/2026/TV/sports.txt'
url_sportsonline_prog = 'https://sportsonline.vc/prog.txt'
thumb_sportsonline = 'https://documentarys.do.am/2026/TV/sport.png'
url_rojadirecta_main = 'http://www.rojadirecta.eu/'
thumb_rojadirecta = 'https://documentarys.do.am/2026/TV/sport.png'
_rojadirecta_source_cache = {}
url_streami_main = 'https://streami.top/'
url_streami_events = 'https://streami.top/api/getEvents.php'
url_streami_popular = 'https://streami.top/api/J.php'
streami_useragent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
streami_xssig = 'bytmo8xialhem066'
thumb_streami = 'https://i.postimg.cc/mkTf5qyH/streamitop.png'
url_vavoo_main = 'https://vavoo.to/'
url_vavoo_channels = 'https://vavoo.to/channels'
vavoo_useragent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
thumb_vavoo = 'https://vavoo.to/favicon.ico'
vavoo_base_sites = ['https://vavoo.to', 'https://kool.to']
vavoo_ping_urls = ['https://www.lokke.app/api/app/ping', 'https://www.vavoo.tv/api/app/ping']
_vavoo_channels_cache = None
_vavoo_signature_cache = None

# DaddyLive 24/7 Channels (dlhd.pk)
url_daddylive_main = 'https://dlhd.pk/24-7-channels.php'
daddylive_base = 'https://dlhd.pk'
daddylive_useragent = 'Mozilla/5.0 (X11; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0'
thumb_daddylive = 'https://documentarys.do.am/2026/TV/sport.png'
fanart_daddylive = 'https://documentarys.do.am/2026/Principal/romylive.png'
epg_daddylive_url = 'https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz'
xmltv_epg_url = 'https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz'
url_veziaici_asia = 'https://veziaici.net/category/a-emisiuni-romanesti/asia-express-sezonul-9-drumul-matasii-online/'
thumb_asia = 'https://documentarys.do.am/APK/logo/asiaexpress.jpg'
fanart_asia = 'https://documentarys.do.am/2026/Principal/romylive.png'
url_veziaici_masterchef = 'https://veziaici.net/category/a-emisiuni-romanesti/masterchef-romania-emisiune-integrala-online/masterchef-sezonul-11-online-editii-in-reluare/'
thumb_masterchef = 'https://documentarys.do.am/APK/logo/masterchef.jpg'
fanart_masterchef = 'https://documentarys.do.am/2026/Principal/romylive.png'
url_veziaici_insula = 'https://veziaici.net/category/a-emisiuni-romanesti/a-insula-iubirii-online/'
thumb_insula = 'https://documentarys.do.am/APK/logo/insulaiubirii.jpg'
fanart_insula = 'https://documentarys.do.am/2026/Principal/romylive.png'
url_veziaici_vocea = 'https://veziaici.net/category/a-emisiuni-romanesti/b-aici-vocea-romaniei-emisiune-gratuita-online/vocea-romaniei-sezonul-14-in-reluare-complet/'
thumb_vocea = 'https://documentarys.do.am/APK/logo/ChatGPT_Image_Sep_10-2026-02_24_15_PM.jpg'
fanart_vocea = 'https://documentarys.do.am/2026/Principal/romylive.png'
url_veziaici_jocul = 'https://veziaici.net/category/a-emisiuni-romanesti/jocul-cuvintelor-online/'
thumb_jocul = 'https://documentarys.do.am/APK/logo/jocul_cuvintelor.jpg'
fanart_jocul = 'https://documentarys.do.am/2026/Principal/romylive.png'
url_veziaici_furnicutele = 'https://veziaici.net/category/a-emisiuni-romanesti/furnicutele-emisiune-online-in-reluare/'
thumb_furnicutele = 'https://documentarys.do.am/2026/TV/logo/ChatGPT_Image_May_29-2026-10_09_41_AM.jpg'
fanart_furnicutele = 'https://documentarys.do.am/2026/Principal/romylive.png'
url_veziaici_chefi = 'https://veziaici.net/category/a-emisiuni-romanesti/integral-chefi-la-cutite-online/'
thumb_chefi = 'https://documentarys.do.am/2026/TV/logo/chefl.jpg'
fanart_chefi = 'https://documentarys.do.am/2026/Principal/romylive.png'
url_veziaici_camatarii = 'https://veziaici.net/category/c-seriale-romanesti/camatarii-documentar-online-in-reluare-din-2026/'
thumb_camatarii = 'https://documentarys.do.am/2026/TV/logo/ChatGPT_Image_May_29-2026-07_33_50_AM.jpg'
fanart_camatarii = 'https://documentarys.do.am/2026/Principal/romylive.png'
url_veziaici_las = 'https://veziaici.net/category/c-seriale-romanesti/vizionati-las-fierbinti-toate-sezoanele-integrale/'
thumb_las = 'https://documentarys.do.am/2026/seriale/romanesti/lasfierbinti/las_fierbinti.png'
fanart_las = 'https://documentarys.do.am/2026/Principal/romylive.png'
_xmltv_epg_cache = None
_daddylive_epg_cache = None
_daddylive_channels_cache = None
_daddylive_meta_cache = None

# SKY Italia (independent, no Mandra dependency)
url_sky_italia = 'sky_italia://list'
thumb_sky_italia = 'https://documentarys.do.am/2026/TV/logo/italiaworld.jpg'
fanart_sky_italia = 'https://documentarys.do.am/2026/Principal/romylive.png'
sky_italia_channels = [
    ('TG 24',           'tg24',             'https://pixel.disco.nowtv.it/logo/skychb_tg24_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('SKY UNO',         'skyuno',            'https://pixel.disco.nowtv.it/logo/skychb_skyuno_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('SKY UNO+',        'skyunoplus',        'https://pixel.disco.nowtv.it/logo/skychb_skyunoplus_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('SKY ATLANTIC',    'skyatlantic',       'https://pixel.disco.nowtv.it/logo/skychb_skyatlantic_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('SKY SERIE',       'skyserie',          'https://pixel.disco.nowtv.it/logo/skychb_skyserie_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('SKY COLLECTION',  'skycollection',     'https://pixel.disco.nowtv.it/logo/skychb_skycollection_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('SKY INVESTIGATION','skyinvestigation', 'https://pixel.disco.nowtv.it/logo/skychb_skyinvestigation_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('SKY ADVENTURE',   'skyadventure',      'https://pixel.disco.nowtv.it/logo/skychb_skyadventure_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('SKY CRIME',       'skycrime',          'https://pixel.disco.nowtv.it/logo/skychb_skycrime_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('SKY DOCUMENTARIES','skydocumentaries', 'https://pixel.disco.nowtv.it/logo/skychb_skydocumentaries_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('SKY NATURE',      'skynature',         'https://pixel.disco.nowtv.it/logo/skychb_skynature_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('HISTORY CHANNEL', 'historychannel',    'https://pixel.disco.nowtv.it/logo/skychb_historychannel_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('COMEDY CENTRAL',  'comedycentral',     'https://pixel.disco.nowtv.it/logo/skychb_comedycentral_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('SKY ARTE',        'skyarte',           'https://pixel.disco.nowtv.it/logo/skychb_skyarte_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
    ('MTV',             'mtv',               'https://pixel.disco.nowtv.it/logo/skychb_mtv_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT'),
]



# ===========================================================================
# MyRadioOnline.ro - Radio online romanesc pe categorii
# ===========================================================================
url_myradioonline = 'myradioonline://list'

# RDS.live subcategory (rdslive.tv)
url_rdslive = 'rdslive://list'
thumb_rdslive = 'https://rdslive.tv/wp-content/uploads/2025/10/logo-rds.png'
fanart_rdslive = 'https://documentarys.do.am/2026/Principal/romylive.png'

# ===========================================================================
# TVZoneHD - Canale TV Romania (tvzonehd.com)
# ===========================================================================
url_tvzone = 'tvzone://list'
thumb_tvzone = 'https://www.tvzonehd.com/favicon.ico'
fanart_tvzone = 'https://documentarys.do.am/2026/Principal/romylive.png'
TVZONE_BASE = 'https://www.tvzonehd.com/'
TVZONE_PROGRAM_URL = 'https://www.tvzonehd.com/program-tv'
TVZONE_STREAM_API = 'https://www.tvzonehd.com/stream.php'
TVZONE_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

RDSLIVE_CHANNELS = r'''
<item>
<title>[COLOR white][B]Acasa Gold[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/acasagold/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/acasa-gold.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Acasa TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/acasahd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/acasa-tv.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Antena 1[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/antena1/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ChatGPT-Image-May-31-2026-02_39_43-AM.png</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Antena Stars[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/antenastarssd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ChatGPT-Image-May-31-2026-11_32_52-AM.png</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>


<item>
<title>[COLOR white][B]Happy Channel[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/happychannelsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ChatGPT-Image-May-31-2026-11_40_52-AM.png</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Kanal D[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/kanald/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ChatGPT-Image-May-31-2026-11_44_11-AM.png</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]KANAL D2[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/kanald2hd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ChatGPT-Image-Jun-12-2026-09_17_43-AM.png</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Metropola TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_metropola/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ChatGPT-Image-Jun-12-2026-09_22_10-AM.png</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]National 24 Plus[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/national24sd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/plus_24.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]National TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/nationaltvsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/national_tv.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Prima TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/prima/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/prima.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Pro TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_protv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/protv.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TVR 1[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/tvr1hd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/tvr1.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TVR 2[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/tvr2sd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/tvr2.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TVR 3[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/tvr3sd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/tvr3.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TVR Cultural[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_tvr_cultural/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/tvr1.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TVR International[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_tvrinternational/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/internat.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>


<item>
<title>[COLOR white][B]Aleph News[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_alephnews/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/aleph-news.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Antena 3[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/antena3hd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ant3.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]B1TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/b1/video.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/b1tv.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]BBC World News[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/bbcworldnewssd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/bbc.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]CNN[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/cnnsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/cnn.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Deutsche Welle[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/dvdeutsch/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/deu.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Digi24[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/digi24/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/digi.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Euronews Romania[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/euronewsrosd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/euron.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Nasul TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_nasu/video.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/nasu.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Observator News[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_observator_news/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/obs.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Prima News[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_primanews/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/primapng.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Realitatea MD[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_realitateamd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/md.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Realitatea TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/realitateaplussd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/realitatea.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Romania TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/romaniatvsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/romaniatv.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TVR Info[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_tvrinfo/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/info.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>



<item>
<title>[COLOR white][B]DigiSport 1[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_digisport1/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/dg1.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]DigiSport 2[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/digisport2hd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/dg2.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]DigiSport 3[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/digisport3hd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/dg3.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]DigiSport 4[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/digisport4hd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/dg4.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Eurosport 1[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/eurosportsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/euro1.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Eurosport 2[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/eurosport2sd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/euro2.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Fight Box[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_fightbox/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/fightbox.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]PrimaSport 1[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/primasport1hd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/primas1.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]PrimaSport 2[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/primasport2sd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/primas2.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]PrimaSport 3[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/roprimasport3sd/video.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/primas3.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]PrimaSport 4[/B][/COLOR]</title>
<link>https://galandriel1.thobias11.cfd/puk4/usergendx42x9qrnd.m3u8|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 OPR/131.0.0.0&Origin=https://galandriel1.thobias11.cfd/&verifypeer=false&Referer=https://galandriel1.thobias11.cfd/</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/primas4.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]PrimaSport 5[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_primasport5/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/primas5.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Pro Arena[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/proarenahd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/proarena.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Realitatea Sportiva[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_realitateasportiva/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/realitateasport.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Sport Extra[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/sportextrahd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/sportextra.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TVR Sport[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/tvrsport/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/tvrsport.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>



<item>
<title>[COLOR white][B]AMC[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/amcsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/amc.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Antena Comedy[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_antenacomedy/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/comedyplay.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]AXN[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/axnsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/AX.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]AXN Black[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/axnblack/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/AXblack.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]AXN Spin[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/axnspin/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/AXSpi.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]AXN White[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/axnwhite/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/AXWhite.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]BBC First[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/bbcfirsthd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/bbcfirst.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Bollywood Clasic[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/bollywoodclasichd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/bollyclassic.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Cinemaraton[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/cinemaratonsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ciemarato.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Cinemaraton Plus[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/cinemaratonplus/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ciemaratoplus.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Cinemax[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/cinemaxhd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ciemax.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Cinemax 2[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/cinemax2sd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ciemax2.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Comedy Central[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/comedycentralsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/comedychael.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]DIVA[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/diva/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/diva.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Dizi[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_dizi/video.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/dizi.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]FilmBox Hits[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmboxhits/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/filmboxhits.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]FilmBox One[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmboxone/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/filmboxoe.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Actiune 1[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmeactiune1/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/actiue1.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Actiune 2[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmeactiune2/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/actiue2.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Actiune 3[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmeactiune3/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/actiue3.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Angelina Jolie[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmeAngelinaJolie/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/jolie.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Bollywood[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmebollywood/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/filmebolly.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Comedie[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmecomedie1/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/comedie1.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Craciun[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmecraciun/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/craciu.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Fantasy[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmefantasy/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/rfatasy.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Horror 1[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmehorror1/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/horror1.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Horror 2[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmehorror2/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/horror2.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Jason Statham[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_JasonStatham/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/jaso.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme John Travolta[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_JohnTravolta/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/trtavolta.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Premiere[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmepremiere/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/premiere.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Razboi[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmerazboi/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/razboi.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Sci Fi 1[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmescifi1/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/scfi1.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Sci Fi 2[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmescifi2/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/scifi2.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Sylvester Stallone[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmeStallone/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/stalloe.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Thriller 1[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmethriller1/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/thriller1.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Thriller 2[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmethriller2/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/thriller2.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Filme Western[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_filmewestern/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/wester.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]HBO[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/hbohd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/hbo.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]HBO 2[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/hbo2sd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/hbo2.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]HBO 3[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/hbo3sd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/hbo3.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Las Fierbinti[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_lfb/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/fierbiti.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Nostalgia TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_nostalgiatv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ostalgia.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Prima Comedy[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/primacomedysd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/primacomedy.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]PRO Cinema[/B][/COLOR]</title>
<link>https://saruman1.tharen1.cfd/porkynema/usergenrnd0ek16an4l.m3u8|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 OPR/131.0.0.0&Origin=https://saruman1.tharen1.cfd/&verifypeer=false&Referer=https://saruman1.tharen1.cfd/</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/hbo2.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]SkyShowTime 1[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/SkyShowTime/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/sky1.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]SkyShowTime 2[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/skyshowtime2hd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/sky2.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Viasat Kino[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_viasatkino/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/kio.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Warner TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/warner/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/warer.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>



<item>
<title>[COLOR white][B]Crime & Investigation[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_crime/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/image_2026-07-08_192357931.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]DaVinci[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/davinci/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/davici.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Digi Animal World[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/digianimalworld/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/aimalworld.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Digi Life[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/digilife/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/life.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Digi World[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/digiworld/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/world.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Discovery Channel[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/discoverysd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/discovery.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]DocuBox[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_docubox/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/docubox.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Dotto TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_dotto/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/dotto.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Food Network[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/travelchannelsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/food.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]History Channel[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/historychannelsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/hisdtory.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]ID Investigation Discovery[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_discoveryID/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/id.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]National Geographic[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/natgeo/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/atgeo.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]National Geographic Wild[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/natgeowildsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/atwild.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Prima History[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/primahistory/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/primahistory.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Travel Mix[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/travelmixsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/travel.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Viasat Explore[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/viasatexploresd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/explore.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Viasat History[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/viasathistorysd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/viasathistory.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Viasat Nature[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/viasatnaturesd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ature.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>



<item>
<title>[COLOR white][B]Cartoon Network[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/cartoonnetworksd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/catet.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Cartoonito[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/cartoonito-boomerang/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/cartooito.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Disney Channel[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/disneychannelsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/disneyc.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Disney Junior[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/disneyjunior/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/disneyjr.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Duck TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/ducktvsd/video.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/duck.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Grizzy & Lemmings[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_Lemmings/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/grizly.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Jim Jam[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/jimjamsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/jimjam.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Kids Mania[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_kidsmania/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/kidsmania.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Minimax[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/minimax/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/minimax.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Nick Jr.[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/nickjrsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/nickjr.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Nickelodeon[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/nickelodeonsd/video.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/nickk.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Nicktoons[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/nicktoonssd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/nicktt.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Peppa Pig[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_peppapig/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/peppa.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Povesti cu Masha[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_masha/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/masha.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TraLaLa[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/tralalasd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/tralala.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>



<item>
<title>[COLOR white][B]Atomic[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/atomictvsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/atomic.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Atomic Academy TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/academy/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/academi.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Balcan Music TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/balkanmusicsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/balcan.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Etno Tv[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/etnotvsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/etno.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]H!T Music Channel[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/hitmusic/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/hitmusic.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Impact TV Dance[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_impact_dance/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/impactdance.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Impact TV Manele[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_impact_manele/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/impactmanele.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Kiss TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/kisstv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/kisstv.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Magic TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/magictv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/magic.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Mezzo[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/mezzo/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/mezzo.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Mooz Dance[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_moozdance/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/moozedance.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]MTV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/mtveuropesd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/mtv.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Music Channel[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/musicchannelro/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/musicchannel.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Party Mix[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/partymixsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/party.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Taraf TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/taraftvsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/taraf.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Traditional TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/traditionaltvsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/traditional.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TV Favorit[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/favorittvsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/images.jpeg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]U TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/utv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ChatGPT-Image-Jun-12-2026-10_24_38-AM.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]ZU TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/zutvsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/zu.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>


<item>
<title>[COLOR white][B]Agro TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/agrotvsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/agro-tv-1-.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]BBC Earth[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/bbcearthsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/bbc.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]E Entertainment[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/entertainment/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/eterteimet.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Fashion TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/fashiontv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/fashio.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]HGTV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/hgtv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/hgtv.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Job TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_jobtv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/job.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Medicool TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_medicooltv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/medicool.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Mireasa TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_mreasa/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/mireasa.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Rai 1[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rai1/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/rai.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Rai 3[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rai3/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/rai3.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Tele 7 ABC[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_tele7ABC/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/tele7.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Tele Moldova+[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_telemoldovaplus/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/telemoldova.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]The Fishing and Hunting[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/fishingandhuntingsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/fishig.png</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TLC[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/tlcsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/tlc.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TV Moldova[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/moldovatvsd/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/moldova.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TV Paprika[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/tvpaprika/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/papikra.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>



<item>
<title>[COLOR white][B]Banat TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_banat_tv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/baat.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Bucovina TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_bucovinatv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/bucovina.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Hunedoara 1[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_banat_tv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/huedoara.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Nova TV Brasov[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_novatv_brasov/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/oiova.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Tele M Botosani[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_telem_botosani/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/tele.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TVR Cluj[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_tvr_cluj/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/cluj.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TVR Iasi[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_tvr_iasi/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/iasi.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TVR Targu Mures[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_tvr_targu_mures/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/mures.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]TVR Timisoara[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_tvr_timiosara/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/ChatGPT-Image-May-31-2026-11_17_59-AM-480x270.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>



<item>
<title>[COLOR white][B]a7 TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/a7tv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/a7tv-ro-1-.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Alfa Omega[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/alfaomega/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/alom.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Angelus TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_angelustv/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/agelus.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Credo TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/credo/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/credo.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Light Channel[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_light_channel/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/light.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]RTN Chicago[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/free_rtnchicago/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/chicago.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Speranta TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/speranta/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/sperata.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Trinitas TV[/B][/COLOR]</title>
<link>https://ivanturbinca.com/hls-proxy.php?src=https://p15.magicplaces.eu/rds_trinitas/tracks-v1a1/mono.m3u8|User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1</link>
<thumbnail>https://documentarys.do.am/2026/TV/rds/logo/triitas.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>














'''

# ---- RDS.live dynamic scraper ----
RDSLIVE_BASE = 'https://rdslive.tv'
RDSLIVE_AJAX = 'https://rdslive.tv/wp-admin/admin-ajax.php'
RDSLIVE_PROXY = 'https://ivanturbinca.com/hls-proxy.php?src='
RDSLIVE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1'
RDSLIVE_FANART = 'https://documentarys.do.am/2026/Principal/romylive.png'

def _rdslive_cache_dir():
    import os
    try:
        p = xbmc.translatePath('special://profile/addon_data/plugin.video.RomyLive/')
    except Exception:
        p = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.RomyLive/')
    if not os.path.isdir(p):
        try: os.makedirs(p)
        except Exception: pass
    return p

def _rdslive_cache_path(name):
    import os
    return os.path.join(_rdslive_cache_dir(), name)

def rdslive_clear_cache():
    import os
    for f in ('rdslive_channels.json',):
        p = _rdslive_cache_path(f)
        if os.path.exists(p):
            try: os.remove(p)
            except Exception: pass

def _rdslive_http_get(url):
    import requests
    r = requests.get(url, headers={'User-Agent': RDSLIVE_UA, 'Referer': RDSLIVE_BASE + '/'}, timeout=15)
    r.raise_for_status()
    return r.text

def _rdslive_http_post(url, data, referer=None):
    import requests
    headers = {'User-Agent': RDSLIVE_UA, 'X-Requested-With': 'XMLHttpRequest',
               'Referer': referer or (RDSLIVE_BASE + '/'),
               'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}
    r = requests.post(url, data=data, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text

def _rdslive_scrape_channels():
    # Scrape https://rdslive.tv/canale-tv/ to get all channels (slug + name + image).
    #
    # The site now uses WP Rocket lazy-loading.  The old parser expected:
    #   <img src="real-image"><h3>name</h3>
    # but the live markup is now:
    #   <img src="data:image/svg+xml,..."
    #        data-lazy-src="real-image"><noscript>...</noscript><h3>name</h3>
    # That made the old regex return zero channels even though the page loaded.
    import re as _re
    html = _rdslive_http_get(RDSLIVE_BASE + '/canale-tv/')

    # Keep this parser dependency-free; Kodi installations do not necessarily
    # have BeautifulSoup or another HTML parser installed.
    card_pat = _re.compile(
        r'<a\b[^>]*href=["\'](https?://rdslive\.tv/canal/([^/"\']+)/)["\'][^>]*>'
        r'(.*?)</a>',
        _re.IGNORECASE | _re.DOTALL
    )
    seen = set()
    channels = []
    for m in card_pat.finditer(html):
        page, slug, card = m.group(1), m.group(2), m.group(3)
        if slug in seen:
            continue

        # The visible title is stable in <h3>; aria-label/alt are fallbacks.
        title_match = _re.search(r'<h3\b[^>]*>(.*?)</h3>', card, _re.IGNORECASE | _re.DOTALL)
        name = title_match.group(1) if title_match else ''
        name = _re.sub(r'<[^>]+>', ' ', name)
        name = html_unescape(_re.sub(r'\s+', ' ', name)).strip()

        alt_match = _re.search(r'\balt=["\']([^"\']*)["\']', card, _re.IGNORECASE)
        alt = html_unescape(alt_match.group(1)).strip() if alt_match else ''

        # Prefer the URL stored by WP Rocket in data-lazy-src.  Ignore the
        # placeholder data:image URL used in the normal src attribute.
        img = ''
        for tag in _re.findall(r'<img\b[^>]*>', card, _re.IGNORECASE | _re.DOTALL):
            for attr in ('data-lazy-src', 'data-src', 'src'):
                image_match = _re.search(
                    r'\b' + attr + r'\s*=["\']([^"\']+)["\']',
                    tag,
                    _re.IGNORECASE
                )
                if image_match:
                    candidate = html_unescape(image_match.group(1)).strip()
                    if candidate and not candidate.lower().startswith('data:image/'):
                        img = candidate
                        break
            if img:
                break

        if not img:
            # Some cached versions only expose data-lazy-srcset.
            srcset_match = _re.search(
                r'\bdata-lazy-srcset\s*=["\']([^"\']+)["\']',
                card,
                _re.IGNORECASE
            )
            if srcset_match:
                img = html_unescape(srcset_match.group(1).split(',')[0].strip().split(' ')[0])

        seen.add(slug)
        channels.append({
            'slug': slug,
            'name': name or alt or slug,
            'image': img or _ROMY_LOCAL_ICON,
            'page': page
        })
    return channels

def _rdslive_get_post_id(page_url):
    # Extract postid from single-canal page
    import re as _re
    html = _rdslive_http_get(page_url)
    m = _re.search(r'postid-(\d+)', html)
    return m.group(1) if m else None

def _rdslive_channels_cached():
    """Return the list of channels (from cache, live scrape, or fallback)."""
    import json as _json, os, time
    cache = _rdslive_cache_path('rdslive_channels.json')
    data = None
    if os.path.exists(cache) and (time.time() - os.path.getmtime(cache) < 6 * 3600):
        try: data = _json.load(open(cache, 'r', encoding='utf-8'))
        except Exception: data = None
    if not data:
        try:
            data = _rdslive_scrape_channels()
            _json.dump(data, open(cache, 'w', encoding='utf-8'))
        except Exception as e:
            try: xbmc.log('[RomyLive] RDS.live scrape error: %s' % e, level=xbmc.LOGERROR)
            except Exception: pass
            data = []
    return data or []


def _rdslive_render_channels(channels):
    """Render a list of channel dicts as Kodi <item> XML string."""
    parts = []
    for ch in channels:
        parts.append('<item><title>[COLOR white][B]' + ch['name'] + '[/B][/COLOR]</title><externallink>rdslive://channel/' + ch['slug'] + '</externallink><thumbnail>' + ch.get('image', _ROMY_LOCAL_ICON) + '</thumbnail><fanart>' + RDSLIVE_FANART + '</fanart><info>' + ch['name'] + ' - rdslive.tv (surse multiple)</info></item>')
    return '\n'.join(parts)


def _rdslive_verify_adult_pin():
    """Prompt for PIN and validate against addon setting `rdslive_adult_pin`.
    Returns True if PIN is correct (or no PIN configured), False otherwise.
    """
    try:
        import xbmcaddon, xbmcgui
        stored = (xbmcaddon.Addon().getSetting('rdslive_adult_pin') or '').strip()
    except Exception:
        stored = ''
    if not stored:
        # No PIN configured -> block access and instruct user to set one.
        try:
            xbmcgui.Dialog().ok('Adulti - PIN necesar',
                                'Categoria [B]Adulti[/B] este protejata prin PIN.',
                                'Seteaza mai intai un PIN in Setari > Categorie Adulti.')
        except Exception:
            pass
        return False
    try:
        entered = xbmcgui.Dialog().input('Introdu PIN pentru categoria Adulti',
                                         type=xbmcgui.INPUT_NUMERIC,
                                         option=xbmcgui.ALPHANUM_HIDE_INPUT)
    except Exception:
        entered = ''
    if entered == stored:
        return True
    try:
        xbmcgui.Dialog().notification('RomyLive', 'PIN gresit', xbmcgui.NOTIFICATION_ERROR, 3000)
    except Exception:
        pass
    return False


def rdslive_get_channel_list(category=None):
    """Root view: show categories menu. Category view: filtered channels."""
    import json as _json, os, time
    try: import urllib.parse as _up
    except Exception:
        try: import urllib as _up
        except Exception: _up = None

    data = _rdslive_channels_cached()

    # Root: category menu with counts
    if not category:
        # Build category buckets
        buckets = {c: [] for c in _RDS_CATEGORY_ORDER}
        for ch in data:
            cat = _rds_classify(ch.get('name', ''))
            buckets.setdefault(cat, []).append(ch)

        parts = []
        parts.append('<item><title>[COLOR gold][B]Actualizeaza lista[/B][/COLOR]</title><externallink>rdslive://refresh</externallink><thumbnail>' + _ROMY_LOCAL_ICON + '</thumbnail><fanart>' + RDSLIVE_FANART + '</fanart><info>Reincarca canalele de pe rdslive.tv</info></item>')
        parts.append('<item><title>[COLOR aqua][B]Toate canalele[/B][/COLOR] [COLOR white](' + str(len(data)) + ')[/COLOR]</title><externallink>rdslive://all</externallink><thumbnail>' + _ROMY_LOCAL_ICON + '</thumbnail><fanart>' + RDSLIVE_FANART + '</fanart><info>Toate canalele RDS.live intr-o singura lista</info></item>')
        for c in _RDS_CATEGORY_ORDER:
            count = len(buckets.get(c, []))
            if count == 0:
                continue
            try:
                cat_slug = _up.quote_plus(c) if _up else c.replace(' ', '+')
            except Exception:
                cat_slug = c.replace(' ', '+')
            color = 'red' if c == _RDS_CAT_ADULTI else 'aqua'
            parts.append('<item><title>[COLOR ' + color + '][B]' + c + '[/B][/COLOR] [COLOR white](' + str(count) + ')[/COLOR]</title><externallink>rdslive://cat/' + cat_slug + '</externallink><thumbnail>' + _ROMY_LOCAL_ICON + '</thumbnail><fanart>' + RDSLIVE_FANART + '</fanart><info>Canale RDS.live - categoria ' + c + '</info></item>')
        return '\n'.join(parts)

    # __all__ synthetic category: everything
    if category == '__all__':
        return _rdslive_render_channels(data)

    # Adulti requires PIN
    if category == _RDS_CAT_ADULTI:
        if not _rdslive_verify_adult_pin():
            return '<item><title>[COLOR red][B]Acces refuzat[/B][/COLOR]</title><externallink>rdslive://list</externallink><thumbnail>' + _ROMY_LOCAL_ICON + '</thumbnail><fanart>' + RDSLIVE_FANART + '</fanart><info>PIN incorect sau nesetat.</info></item>'

    # Filter by category
    filtered = [ch for ch in data if _rds_classify(ch.get('name', '')) == category]
    if not filtered:
        return '<item><title>[COLOR red][B]Nu sunt canale in aceasta categorie[/B][/COLOR]</title><externallink>rdslive://list</externallink><thumbnail>' + _ROMY_LOCAL_ICON + '</thumbnail><fanart>' + RDSLIVE_FANART + '</fanart><info>Categoria ' + category + ' este goala.</info></item>'
    return _rdslive_render_channels(filtered)

def rdslive_get_channel_sources(slug):
    # For a given channel slug, fetch its 4 sources and return them as playable items
    import json as _json, os
    page = RDSLIVE_BASE + '/canal/' + slug + '/'
    # Try cache of post_id
    cache = _rdslive_cache_path('rdslive_postids.json')
    postids = {}
    if os.path.exists(cache):
        try: postids = _json.load(open(cache, 'r', encoding='utf-8'))
        except Exception: postids = {}
    post_id = postids.get(slug)
    if not post_id:
        try:
            post_id = _rdslive_get_post_id(page)
            if post_id:
                postids[slug] = post_id
                _json.dump(postids, open(cache, 'w', encoding='utf-8'))
        except Exception as e:
            try: xbmc.log('[RomyLive] RDS.live post_id error %s: %s' % (slug, e), level=xbmc.LOGERROR)
            except Exception: pass
    if not post_id:
        return ''
    # Fetch channel image from the page
    try:
        html = _rdslive_http_get(page)
        import re as _re
        m = _re.search(r'<meta property="og:image" content="([^"]+)"', html)
        img = m.group(1) if m else RDSLIVE_FANART
        m = _re.search(r'<meta property="og:title" content="([^"]+)"', html)
        title = (m.group(1).split(' – ')[0].split(' - ')[0]) if m else slug
    except Exception:
        img = RDSLIVE_FANART; title = slug
    parts = []
    for i in (1, 2, 3, 4):
        try:
            resp = _rdslive_http_post(RDSLIVE_AJAX, 'action=get_video_source&tab=tab%d&post_id=%s' % (i, post_id), referer=page)
            j = _json.loads(resp)
            if j.get('success') and j.get('data'):
                stream = j['data']
                link = RDSLIVE_PROXY + stream + '|User-Agent=' + RDSLIVE_UA
                parts.append('<item><title>[COLOR white][B]' + title + '[/B][/COLOR] [COLOR aqua]Sursa ' + str(i) + '[/COLOR]</title><link>' + link + '</link><thumbnail>' + img + '</thumbnail><fanart>' + RDSLIVE_FANART + '</fanart><info>Stream live ' + title + ' (Sursa ' + str(i) + ') via rdslive.tv</info></item>')
        except Exception as e:
            try: xbmc.log('[RomyLive] RDS.live source %d error %s: %s' % (i, slug, e), level=xbmc.LOGWARNING)
            except Exception: pass
    if not parts:
        # Fallback: use embedded static list filtered by slug-ish match
        return ''
    return '\n'.join(parts)
# ---- end RDS.live dynamic scraper ----

thumb_myradioonline = 'https://myradioonline.ro/public/img/logo/myradioonline_ro.png'
fanart_myradioonline = 'https://documentarys.do.am/2026/Principal/romylive.png'

# Categorii si posturi (stream-uri extrase din myradioonline.ro)
myradioonline_categories = {
    'Manele': [
        ('Fm Radio Manele',    'https://ssl.servereradio.ro/8044/stream'),
        ('Radio Manele',       'https://play.wrhradios.com/8044/stream'),
        ('Radio Manele Vechi', 'https://ssl.fmradiomanele.ro:8054/stream'),
        ('Radio Pro Manele',   'https://sonica.cloudstreaming.eu/8000/stream;'),
        ('Radio Taraf',        'https://stream3.rdstrm.com/prx-http/live.radiotaraf.ro:8181/;'),
        ('Radio Petrecaretzu', 'https://stream3.rdstrm.com/prx-http/live.radiopetrecaretzu.ro:8383/;'),
        ('Radio AS Petrecere', 'https://stream.zeno.fm/zp999wm4tm0uv'),
    ],
    'Petrecere si Populara': [
        ('Radio Popular',      'https://livessl.radiopopular.ro:7777/live'),
        ('Radio Pro Popular',  'https://sonica.cloudstreaming.eu/9998/stream'),
        ('Radio Vesel',        'https://sonicssl.namehost.ro:8300/stream'),
        ('Antena Satelor',     'https://stream4.srr.ro:8443/antena-satelor'),
        ('Radio Prahova',      'https://r2.mediastreaming.ro/listen/rph/relay'),
        ('radio SOMES',        'https://radio.mediacp.eu/stream/radiosomes'),
        ('Disco Mix',          'https://play.discomix.ro/8002/stream'),
    ],
    'Romania Generaliste': [
        ('Magic Fm',           'https://live.magicfm.ro/magicfm.aacp'),
        ('Radio ZU',           'https://ivm.antenaplay.ro/liveaudio/radiozu/playlist.m3u8'),
        ('Kiss FM',            'https://live.kissfm.ro/kissfm.aacp'),
        ('Europa FM',          'https://astreaming.edi.ro:8443/EuropaFM_aac'),
        ('ProFM',              'https://edge76.rcs-rds.ro/profm/profm.mp3'),
        ('National FM',        'https://asculta.nationalfm.ro:9102/nfm2'),
        ('Digi FM',            'https://edge76.rcs-rds.ro/digifm/digifm.mp3'),
        ('Virgin Radio',       'https://astreaming.edi.ro:8443/VirginRadio_aac'),
        ('Focus FM',           'http://live.focusfm.ro:8000/focusfmhigh.ogg'),
        ('One FM',             'https://live.onefm.ro/onefm.aacp'),
        ('Super FM',           'https://live.superfm.ro/stream.mp3'),
        ('Vibe FM',            'https://astreaming.vibefm.ro:8443/vibe_ro64'),
        ('Radio Gold FM',      'https://live.radiogoldfm.ro:8443/WP.mp3'),
        ('Smart Radio',        'https://live.smartradio.ro:8443/live'),
        ('Radio HiT FM',       'https://live.radiohitfm.net/8989/stream'),
        ('Radio Impuls',       'https://live.radio-impuls.ro/stream'),
        ('Radio Cafe',         'https://live.radiocafe.ro:8443/'),
        ('Play Radio 91.6 FM', 'https://live.playradio.org:8443/FMHD'),
        ('Radio Guerrilla',    'https://live.guerrillaradio.ro:8443/guerrilla.aac'),
        ('Radio Accent',       'https://stream3.rdstrm.com/prx-http/86.122.157.14:8900/;'),
    ],
    'Dance si Electronic': [
        ('Dance FM',           'https://edge76.rcs-rds.ro/profm/dancefm.mp3'),
        ('Chill FM',           'https://edge76.rcs-rds.ro/profm/chillfm.mp3'),
        ('Deep House Radio',   'https://streaming-01.xtservers.com:7000/stream'),
        ('Radio Hot Style',    'https://ssl.servereradio.ro/8000/electronic.mp3'),
        ('FMV Fit Radio',      'https://radio.webicdp.com/listen/fmvfitradiorelax/radio.mp3'),
    ],
    'Retro si Oldies': [
        ('Nostalgia Radio',    'https://live.radionostalgia.ro:8443/nostalgia.aac'),
        ('Radio Pro Music 90s','https://stream.adradio.ro:8414'),
        ('Rock FM',            'https://live.rockfm.ro/rockfm.aacp'),
    ],
    'Stiri si Cultura': [
        ('Radio Romania Actualitati', 'https://stream4.srr.ro:8443/romania-actualitati'),
        ('Radio Romania Cultural',    'https://stream4.srr.ro:8443/romania-cultural'),
        ('Digi 24 FM',                'https://edge76.rcs-rds.ro/digifm/digi24fm.mp3'),
        ('Sport Total FM',            'https://livesptfm.com/SPTFM/Audio128/playlist.m3u8'),
        ('Radio Trinitas',            'https://live.radiotrinitas.ro:8003/;'),
        ('Radio Renasterea',          'https://cast1.asurahosting.com/proxy/arhiepis/stream'),
    ],
    'Regionale': [
        ('Radio Timisoara',                 'http://89.238.227.6:8360/;'),
        ('Radio Iasi',                      'http://89.238.227.6:8202/;stream/1'),
        ('Radio Bucovina FM',               'https://cloud.radiosonicpanel.ro/8032/stream'),
        ('Oltenia Craiova Radio Romania',   'https://stream3.rdstrm.com/prx-http/stream2.srr.ro:8370/;'),
        ('Radio Romania Resita',            'https://stream4.srr.ro:8443/radio-resita'),
    ],
    'Copii': [
        ('Itsy Bitsy', 'https://stream3.rdstrm.com/prx-http/live.itsybitsy.ro:8000/itsybitsy'),
    ],
}

# Logouri per statie (de pe myradioonline.ro)
_mro_base = 'https://myradioonline.ro/public/uploads/radio_img/'
myradioonline_logos = {
    'Fm Radio Manele':              _mro_base + 'fm-radio-manele/play_250_250.webp',
    'Radio Manele':                 _mro_base + 'radio-manele/play_250_250.webp',
    'Radio Manele Vechi':           _mro_base + 'radio-manele-vechi/play_250_250.webp',
    'Radio Pro Manele':             _mro_base + 'radio-pro-manele/play_250_250.webp',
    'Radio Taraf':                  _mro_base + 'radio-taraf/play_250_250.webp',
    'Radio Petrecaretzu':           _mro_base + 'radio-petrecaretzu/play_250_250.webp',
    'Radio AS Petrecere':           _mro_base + 'radio-as-petrecere/play_250_250.webp',
    'Radio Popular':                _mro_base + 'radio-popular/play_250_250.webp',
    'Radio Pro Popular':            _mro_base + 'radio-pro-popular/play_250_250.webp',
    'Radio Vesel':                  _mro_base + 'radio-vesel/play_250_250.webp',
    'Antena Satelor':               _mro_base + 'antena-satelor/play_250_250.webp',
    'Radio Prahova':                _mro_base + 'radio-prahova/play_250_250.webp',
    'radio SOMES':                  _mro_base + 'radio-somes/play_250_250.webp',
    'Disco Mix':                    _mro_base + 'disco-mix/play_250_250.webp',
    'Magic Fm':                     _mro_base + 'magic-fm/play_250_250.webp',
    'Radio ZU':                     _mro_base + 'radio-zu/play_250_250.webp',
    'Kiss FM':                      _mro_base + 'kiss-fm/play_250_250.webp',
    'Europa FM':                    _mro_base + 'europa-fm/play_250_250.webp',
    'ProFM':                        _mro_base + 'profm/play_250_250.webp',
    'National FM':                  _mro_base + 'national-fm/play_250_250.webp',
    'Digi FM':                      _mro_base + 'digi-fm/play_250_250.webp',
    'Virgin Radio':                 _mro_base + 'virgin-radio/play_250_250.webp',
    'Focus FM':                     _mro_base + 'focus-fm/play_250_250.webp',
    'One FM':                       _mro_base + 'one-fm/play_250_250.webp',
    'Super FM':                     _mro_base + 'super-fm/play_250_250.webp',
    'Vibe FM':                      _mro_base + 'vibe-fm/play_250_250.webp',
    'Radio Gold FM':                _mro_base + 'radio-gold-fm/play_250_250.webp',
    'Smart Radio':                  _mro_base + 'smart-radio/play_250_250.webp',
    'Radio HiT FM':                 _mro_base + 'radio-hit-fm/play_250_250.webp',
    'Radio Impuls':                 _mro_base + 'radio-impuls/play_250_250.webp',
    'Radio Cafe':                   _mro_base + 'radio-cafe/play_250_250.webp',
    'Play Radio 91.6 FM':           _mro_base + 'play-radio-91-6-fm/play_250_250.webp',
    'Radio Guerrilla':              _mro_base + 'radio-guerrilla/play_250_250.webp',
    'Radio Accent':                 _mro_base + 'radio-accent/play_250_250.webp',
    'Dance FM':                     _mro_base + 'dance-fm/play_250_250.webp',
    'Chill FM':                     _mro_base + 'chill-fm/play_250_250.webp',
    'Deep House Radio':             _mro_base + 'deep-house-radio/play_250_250.webp',
    'Radio Hot Style':              _mro_base + 'radio-hot-style/play_250_250.webp',
    'FMV Fit Radio':                _mro_base + 'fmv-fit-radio/play_250_250.webp',
    'Nostalgia Radio':              _mro_base + 'nostalgia-radio/play_250_250.webp',
    'Radio Pro Music 90s':          _mro_base + 'radio-pro-music-90s/play_250_250.webp',
    'Rock FM':                      _mro_base + 'rock-fm/play_250_250.webp',
    'Radio Romania Actualitati':    _mro_base + 'radio-romania-actualitati/play_250_250.webp',
    'Radio Romania Cultural':       _mro_base + 'radio-romania-cultural/play_250_250.webp',
    'Digi 24 FM':                   _mro_base + 'digi-24-fm/play_250_250.webp',
    'Sport Total FM':               _mro_base + 'sport-total-fm/play_250_250.webp',
    'Radio Trinitas':               _mro_base + 'radio-trinitas/play_250_250.webp',
    'Radio Renasterea':             _mro_base + 'radio-renasterea/play_250_250.webp',
    'Radio Timisoara':              _mro_base + 'radio-timisoara/play_250_250.webp',
    'Radio Iasi':                   _mro_base + 'radio-iasi/play_250_250.webp',
    'Radio Bucovina FM':            _mro_base + 'radio-bucovina-fm/play_250_250.webp',
    'Oltenia Craiova Radio Romania':_mro_base + 'oltenia-craiova-radio-romania/play_250_250.webp',
    'Radio Romania Resita':         _mro_base + 'radio-romania-resita/play_250_250.webp',
    'Itsy Bitsy':                   _mro_base + 'itsy-bitsy/play_250_250.webp',
}

#name - mensagem suporte
addon_name = xbmcaddon.Addon().getAddonInfo('name')


if sys.argv[1] == 'limparFavoritos':
    Path = kodi_translate_path(xbmcaddon.Addon().getAddonInfo('profile')).decode("utf-8")
    arquivo = os.path.join(Path, "favorites.dat")
    exists = os.path.isfile(arquivo)
    if exists:
        try:
            os.remove(arquivo)
        except:
            pass
    xbmcgui.Dialog().ok('Sucesso', '[B][COLOR red]Favoritos limpo com sucesso![/COLOR][/B]')
    xbmc.sleep(2000)
    exit()


if sys.argv[1] == 'SetPassword':
    addonID = xbmcaddon.Addon().getAddonInfo('id')
    addon_data_path = kodi_translate_path(os.path.join('special://home/userdata/addon_data', addonID))
    if os.path.exists(addon_data_path)==False:
        os.mkdir(addon_data_path)
    xbmc.sleep(4)
    #Path = kodi_translate_path(xbmcaddon.Addon().getAddonInfo('profile')).decode("utf-8")
    #arquivo = os.path.join(Path, "password.txt")
    arquivo = os.path.join(addon_data_path, "password.txt")
    exists = os.path.isfile(arquivo)
    keyboard = xbmcaddon.Addon().getSetting("keyboard")
    if exists == False:
        password = '0069'
        p_encoded = base64.b64encode(password.encode()).decode('utf-8')
        p_file1 = open(arquivo,'w')
        p_file1.write(p_encoded)
        p_file1.close()
        xbmc.sleep(4)
        p_file = open(arquivo,'r+')
        p_file_read = p_file.read()
        p_file_b64_decode = base64.b64decode(p_file_read).decode('utf-8')
        dialog = xbmcgui.Dialog()
        if setting_int(keyboard) == 0:
            ps = dialog.numeric(0, 'Insira a senha atual:')
        else:
            ps = dialog.input('Insira a senha atual:', option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if ps == p_file_b64_decode:
            if setting_int(keyboard) == 0:
                ps2 = dialog.numeric(0, 'Insira a nova senha:')
            else:
                ps2 = dialog.input('Insira a senha atual:', option=xbmcgui.ALPHANUM_HIDE_INPUT)
            if ps2 != '':
                ps2_b64 = base64.b64encode(ps2.encode()).decode('utf-8')
                p_file = open(arquivo,'w')
                p_file.write(ps2_b64)
                p_file.close()
                xbmcgui.Dialog().ok('[B][COLOR white]AVISO[/COLOR][/B]','A Senha foi alterada com sucesso!')
            else:
                xbmcgui.Dialog().ok('[B][COLOR white]AVISO[/COLOR][/B]','Não foi possivel alterar a senha!')
        else:
            xbmcgui.Dialog().ok('[B][COLOR white]AVISO[/COLOR][/B]','Senha invalida!, se não alterou utilize a senha padrão')
    else:
        p_file = open(arquivo,'r+')
        p_file_read = p_file.read()
        p_file_b64_decode = base64.b64decode(p_file_read).decode('utf-8')
        dialog = xbmcgui.Dialog()
        if setting_int(keyboard) == 0:
            ps = dialog.numeric(0, 'Insira a senha atual:')
        else:
            ps = dialog.input('Insira a senha atual:', option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if ps == p_file_b64_decode:
            if setting_int(keyboard) == 0:
                ps2 = dialog.numeric(0, 'Insira a nova senha:')
            else:
                ps2 = dialog.input('Insira a senha atual:', option=xbmcgui.ALPHANUM_HIDE_INPUT)
            if ps2 != '':
                ps2_b64 = base64.b64encode(ps2.encode()).decode('utf-8')
                p_file = open(arquivo,'w')
                p_file.write(ps2_b64)
                p_file.close()
                xbmcgui.Dialog().ok('[B][COLOR white]AVISO[/COLOR][/B]','A Senha foi alterada com sucesso!')
            else:
                xbmcgui.Dialog().ok('[B][COLOR white]AVISO[/COLOR][/B]','Não foi possivel alterar a senha!')
        else:
            xbmcgui.Dialog().ok('[B][COLOR white]AVISO[/COLOR][/B]','Senha invalida!, se não alterou utilize a senha padrão')
    exit()



addon_handle = int(sys.argv[1])
__addon__ = xbmcaddon.Addon()
addon = __addon__
__addonname__ = __addon__.getAddonInfo('name')
__icon__ = __addon__.getAddonInfo('icon')
addon_version = __addon__.getAddonInfo('version')

    







def notify(message, timeShown=5000):
    xbmc.executebuiltin('Notification(%s, %s, %d, %s)' % (__addonname__, message, timeShown, __icon__))

def to_unicode(text, encoding='utf-8', errors='strict'):
    """Force text to unicode"""
    if isinstance(text, bytes):
        return text.decode(encoding, errors=errors)
    return text

def setting_int(value, default=0):
    try:
        return int(value)
    except:
        return default

def get_search_string(heading='', message=''):
    """Ask the user for a search string"""
    search_string = None
    keyboard = xbmc.Keyboard(message, heading)
    keyboard.doModal()
    if keyboard.isConfirmed():
        search_string = to_unicode(keyboard.getText())
    return search_string

def getRequest(url, count):
    proxy_mode = addon.getSetting('proxy')
    if proxy_mode == 'true':
        try:
            import requests
            import random
            headers={'User-agent': useragent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Content-Type': 'text/html'}
            if int(count) > 0:
                attempt = int(count)-1
            else:
                attempt = 0
            #print('tentativa: '+str(attempt)+'')
            ### https://proxyscrape.com/free-proxy-list
            ##http
            data_proxy1 = getRequest2('https://api.proxyscrape.com/?request=getproxies&proxytype=http&timeout=10000&country=BR&ssl=no&anonymity=all', '')
            list1 = data_proxy1.splitlines()
            total1 = len(list1)
            number_http = random.randint(0,total1-1)
            proxy_http = 'http://'+list1[number_http]
            ##https
            data_proxy2 = getRequest2('https://api.proxyscrape.com/?request=getproxies&proxytype=http&timeout=10000&country=BR&ssl=yes&anonymity=all', '')
            list2 = data_proxy2.splitlines()
            total2 = len(list2)
            number_https = random.randint(0,total2-1)
            proxy_https = 'https://'+list2[number_https]
            #print(proxy_https)
            proxyDict = {"http" : proxy_http, "https" : proxy_https}
            req = requests.get(url, headers=headers, proxies=proxyDict)
            req.encoding = 'utf-8'
            #status = req.status_code
            response = req.text
            return response
        except:
            proxy_number = addon.getSetting('proxy_try')
            if int(attempt) > 0:
                limit = int(attempt)
            elif int(count) == 1 and int(attempt) == 0:
                limit = int(proxy_number)+1+1
            if int(limit) > 1:
                #print('ativar outro proxy')
                data = getRequest(url, int(limit))
                return data
            else:
                notify('[COLOR red]Erro ao utilizar o proxy ou servidor![/COLOR]')
                response = ''
                return response
    else:
        try:
            try:
                import urllib.request as urllib2
            except ImportError:
                import urllib2
            request_headers = {
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8,ru;q=0.7,de-DE;q=0.6,de;q=0.5,de-AT;q=0.4,de-CH;q=0.3,ja;q=0.2,zh-CN;q=0.1,zh;q=0.1,zh-TW;q=0.1,es;q=0.1,ar;q=0.1,en-GB;q=0.1,hi;q=0.1,cs;q=0.1,el;q=0.1,he;q=0.1,en-US;q=0.1",
            "User-Agent": useragent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
            }
            request = urllib2.Request(url, headers=request_headers)
            response = urllib2.urlopen(request).read().decode('utf-8')
            return response
        except urllib2.URLError as e:
            if hasattr(e, 'code'):
                xbmc.executebuiltin("XBMC.Notification(Falha, código de erro - "+str(e.code)+",10000,"+__icon__+")")    
            elif hasattr(e, 'reason'):
                xbmc.executebuiltin("XBMC.Notification(Falha, motivo - "+str(e.reason)+",10000,"+__icon__+")")
            response = ''
            return response



def getRequest2(url,ref,userargent=False):
    try:
        if ref > '':
            ref2 = ref
        else:
            ref2 = url
        if userargent:
            client_user = userargent
        else:
            client_user = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36'
        cj = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        opener.addheaders=[('Accept-Language', 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'),('User-Agent', client_user),('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'), ('Referer', ref2)]
        data = opener.open(url).read()
        response = data.decode('utf-8')
        return response
    except:
        pass

def regex_get_all(text, start_with, end_with):
    r = re.findall("(?i)(" + start_with + "[\S\s]+?" + end_with + ")", text)
    return r



def re_me(data, re_patten):
    match = ''
    m = re.search(re_patten, data)
    if m != None:
        match = m.group(1)
    else:
        match = ''
    return match



def resolve_data(url):
    # TVZone intercept: return synthetic XML so getData's parser can render items
    try:
        if isinstance(url, str):
            if url == url_tvzone:
                return tvzone_get_channel_list()
            if url.startswith('tvzone://refresh'):
                tvzone_clear_cache()
                return tvzone_get_channel_list()
            if url.startswith('tvzone://cat/'):
                _cat_slug = url[len('tvzone://cat/'):]
                try:
                    _cat_name = urllib.unquote_plus(_cat_slug)
                except Exception:
                    _cat_name = _cat_slug.replace('+', ' ')
                return tvzone_get_channel_list(_cat_name)
            # RDS.live intercept: return synthetic XML so getData's parser can render items
            if url == url_rdslive:
                return rdslive_get_channel_list()
            if url.startswith('rdslive://refresh'):
                rdslive_clear_cache()
                return rdslive_get_channel_list()
            if url.startswith('rdslive://all'):
                return rdslive_get_channel_list('__all__')
            if url.startswith('rdslive://cat/'):
                _cat_slug = url[len('rdslive://cat/'):]
                try:
                    _cat_name = urllib.unquote_plus(_cat_slug)
                except Exception:
                    _cat_name = _cat_slug.replace('+', ' ')
                return rdslive_get_channel_list(_cat_name)
            if url.startswith('rdslive://channel/'):
                return rdslive_get_channel_sources(url[len('rdslive://channel/'):])
    except Exception:
        pass
    try:
        data = getRequest(url, 1)
        import gzip, binascii
        #k = base64.b32decode('').decode('utf-8')
        k = base64.b32decode('').decode('utf-8')
        try:
            from StringIO import StringIO as BytesIO ## for Python 2
        except ImportError:            
            from io import BytesIO ## for Python 3
        if k in data:
            data = data.split(k)
            buf = BytesIO(binascii.unhexlify(data[0]))
            f = gzip.GzipFile(fileobj=buf)
            data = f.read()
    except:
        data = getRequest(url, 1)        
    return data

def veziaici_clean_text(value):
    try:
        value = html_unescape(value)
    except:
        pass
    value = re.sub(r'<[^>]+>', ' ', value or '')
    return re.sub(r'\s+', ' ', value).strip()


def veziaici_asia_pages():
    pages = [url_veziaici_asia]
    try:
        first = requests.get(url_veziaici_asia, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/', first, re.IGNORECASE)
        max_page = 1
        for page_num in page_nums:
            try:
                max_page = max(max_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_page + 1):
            pages.append(url_veziaici_asia.rstrip('/') + '/page/%d/' % page_num)
    except:
        for page_num in range(2, 5):
            pages.append(url_veziaici_asia.rstrip('/') + '/page/%d/' % page_num)

    search_url = 'https://veziaici.net/?s=Asia+Express+Episodul'
    pages.append(search_url)
    try:
        first_search = requests.get(search_url, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/\?s=Asia\+Express\+Episodul', first_search, re.IGNORECASE)
        max_search_page = 1
        for page_num in page_nums:
            try:
                max_search_page = max(max_search_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_search_page + 1):
            pages.append('https://veziaici.net/page/%d/?s=Asia+Express+Episodul' % page_num)
    except:
        for page_num in range(2, 5):
            pages.append('https://veziaici.net/page/%d/?s=Asia+Express+Episodul' % page_num)
    return pages


def veziaici_asia_collect_entries():
    entries = {}
    for page in veziaici_asia_pages():
        try:
            data = requests.get(page, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        except Exception as e:
            try:
                xbmc.log('[RomyLive] VeziAici Asia Express page error %s: %s' % (page, e), level=xbmc.LOGWARNING)
            except:
                pass
            continue
        matches = re.compile(r'<a\b[^>]*href=["\']([^"\']*asia-express[^"\']*)["\'][^>]*>(.*?)</a>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        for href, text in matches:
            title = veziaici_clean_text(text)
            try:
                href = html_unescape(href)
            except:
                pass
            if '/category/' in href or '/feed' in href or href.endswith(('.webp', '.jpg', '.jpeg', '.png')):
                continue
            if not re.search(r'episod', title or href, re.IGNORECASE):
                continue
            ep_num = veziaici_furnicutele_episode_number(title, href)
            season_num = veziaici_furnicutele_season_number(title, href)
            if season_num != 9:
                continue
            if ep_num > 0:
                key = (season_num, ep_num)
                if key not in entries:
                    entries[key] = {'title': title, 'url': href, 'season': season_num, 'episode': ep_num}
    return entries


def veziaici_asia_normalize_embed(src):
    try:
        src = html_unescape(src)
    except:
        pass
    return re.sub(r'vidmoly\.org', 'vidmoly.biz', src, flags=re.IGNORECASE)


def veziaici_asia_find_embeds(page_url):
    try:
        data = requests.get(page_url, headers={'User-Agent': useragent, 'Referer': url_veziaici_asia}, timeout=20, verify=False).text
    except Exception as e:
        try:
            xbmc.log('[RomyLive] VeziAici Asia Express episode error %s: %s' % (page_url, e), level=xbmc.LOGWARNING)
        except:
            pass
        return []
    iframes = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    iframes += re.compile(r'data-lazy-src=["\']([^"\']+)["\']', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    embeds = []
    seen = set()
    for src in iframes:
        src = veziaici_asia_normalize_embed(src)
        low = src.lower()
        if low.startswith('about:'):
            continue
        if low in seen:
            continue
        if 'vidmoly' in low:
            embeds.append((src, '[B]Vidmoly.biz[/B]'))
            seen.add(low)
        elif 'vkvideo' in low or 'vk.com' in low or 'vk.ru' in low:
            embeds.append((src, '[B]VKVideo[/B]'))
            seen.add(low)
        elif 'rumble.com/embed' in low:
            embeds.append((src, '[B]Rumble[/B]'))
            seen.add(low)
    return embeds


def veziaici_asia_find_embed(page_url):
    embeds = veziaici_asia_find_embeds(page_url)
    if embeds:
        return embeds[0]
    return '', ''


def veziaici_asia_list():
    # Asia Express / ExtraZone: afisam si folosim EXCLUSIV Vidmoly.biz.
    # La apasarea episodului, playerul porneste direct, fara lista de servere/variante.
    entries = veziaici_asia_collect_entries()
    if not entries:
        notify('[COLOR red]Nu am gasit episoade Asia Express[/COLOR]')
        return

    count = 0
    for key in sorted(entries.keys(), reverse=True):
        entry = entries[key]

        # Cauta embedurile, dar pastreaza numai Vidmoly.
        embeds = veziaici_asia_find_embeds(entry.get('url', ''))
        vidmoly_embed = ''
        for embed, host_name in embeds:
            if 'vidmoly.biz' in embed.lower() or 'vidmoly' in embed.lower():
                vidmoly_embed = embed
                break

        if not vidmoly_embed:
            continue

        season_num = entry.get('season', 9)
        ep_num = entry.get('episode', 0)
        date = veziaici_furnicutele_extract_date(
            entry.get('title', ''), entry.get('url', '')
        )

        # Link direct catre playerul Vidmoly prin resolverul deja folosit de addon.
        play_url = (
            'plugin://plugin.video.smr_link_tester/?mode=play_link'
            '&link=%s&switch=play$nome=%s'
        ) % (
            urllib.quote_plus(vidmoly_embed),
            urllib.quote_plus('[B]Vidmoly.biz[/B]')
        )

        title = (
            '[COLOR white][B]Asia Express Sezonul %d Episodul %d[/B][/COLOR]'
            % (season_num, ep_num)
        )

        addLink(
            title, play_url, '', thumb_asia, fanart_asia, '',
            '[COLOR grey][I] %s[/COLOR][/I]' % date if date else '', date,
            '',  # credits
            '',  # year
            '',  # director
            '',  # writer
            '',  # duration
            '',  # premiered
            '',  # studio
            '',  # rate
            '',  # originaltitle
            '',  # country
            '',  # rating
            '',  # userrating
            '',  # votes
            ''   # aired
        )
        count += 1

    if count == 0:
        notify('[COLOR red]Nu am gasit linkuri Vidmoly.biz pentru Asia Express[/COLOR]')



def veziaici_masterchef_pages():
    pages = [url_veziaici_masterchef]
    try:
        first = requests.get(url_veziaici_masterchef, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/', first, re.IGNORECASE)
        max_page = 1
        for page_num in page_nums:
            try:
                max_page = max(max_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_page + 1):
            pages.append(url_veziaici_masterchef.rstrip('/') + '/page/%d/' % page_num)
    except:
        for page_num in range(2, 5):
            pages.append(url_veziaici_masterchef.rstrip('/') + '/page/%d/' % page_num)

    search_url = 'https://veziaici.net/?s=MasterChef+Sezonul+11+Episodul'
    pages.append(search_url)
    try:
        first_search = requests.get(search_url, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/\?s=MasterChef\+Sezonul\+11\+Episodul', first_search, re.IGNORECASE)
        max_search_page = 1
        for page_num in page_nums:
            try:
                max_search_page = max(max_search_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_search_page + 1):
            pages.append('https://veziaici.net/page/%d/?s=MasterChef+Sezonul+11+Episodul' % page_num)
    except:
        for page_num in range(2, 5):
            pages.append('https://veziaici.net/page/%d/?s=MasterChef+Sezonul+11+Episodul' % page_num)
    return pages


def veziaici_masterchef_collect_entries():
    entries = {}
    for page in veziaici_masterchef_pages():
        try:
            data = requests.get(page, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        except Exception as e:
            try:
                xbmc.log('[RomyLive] VeziAici MasterChef page error %s: %s' % (page, e), level=xbmc.LOGWARNING)
            except:
                pass
            continue

        matches = re.compile(r'<a\b[^>]*href=["\']([^"\']*masterchef[^"\']*)["\'][^>]*>(.*?)</a>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        for href, text in matches:
            title = veziaici_clean_text(text)
            try:
                href = html_unescape(href)
            except:
                pass
            if '/category/' in href or '/feed' in href or href.endswith(('.webp', '.jpg', '.jpeg', '.png')):
                continue
            if not re.search(r'episod', title or href, re.IGNORECASE):
                continue
            ep_num = veziaici_furnicutele_episode_number(title, href)
            season_num = veziaici_furnicutele_season_number(title, href)
            if season_num != 11:
                continue
            if ep_num > 0:
                key = (season_num, ep_num)
                if key not in entries:
                    entries[key] = {'title': title, 'url': href, 'season': season_num, 'episode': ep_num}
    return entries


def veziaici_vk_clean(src):
    """Curata un embed si intoarce (url, cheie_unica).

    Pentru VK, cheia e oid_id, ca acelasi clip sa nu apara de doua ori cand
    pagina il pune si ca <iframe src> si ca data-lazy-src.
    """
    try:
        src = html_unescape(src)
    except:
        pass
    src = src.replace('&amp;', '&').replace('&#038;', '&')
    if src.startswith('//'):
        src = 'https:' + src
    key = src.lower()
    m_oid = re.search(r'[?&]oid=(-?\d+)', src)
    m_id = re.search(r'[?&]id=(\d+)', src)
    if m_oid and m_id:
        key = 'vk:%s_%s' % (m_oid.group(1), m_id.group(1))
    return src, key


def veziaici_is_vk(url):
    low = (url or '').lower()
    return 'vkvideo.ru' in low or 'vk.com' in low or 'vk.ru' in low or 'vkuser' in low


def veziaici_masterchef_find_embeds(page_url):
    try:
        data = requests.get(page_url, headers={'User-Agent': useragent, 'Referer': url_veziaici_masterchef}, timeout=20, verify=False).text
    except Exception as e:
        try:
            xbmc.log('[RomyLive] VeziAici MasterChef episode error %s: %s' % (page_url, e), level=xbmc.LOGWARNING)
        except:
            pass
        return []

    # Un singur scan, ca sa pastram ordinea din pagina (partea 1, partea 2, ...).
    # Cautam si src= si data-lazy-src= in aceeasi trecere.
    pattern = re.compile(r'(?:data-lazy-src|src)=["\']([^"\']+)["\']', re.MULTILINE|re.DOTALL|re.IGNORECASE)
    vidmoly_embeds = []
    vk_embeds = []
    seen = set()
    for match in pattern.finditer(data):
        src = match.group(1)
        src = re.sub(r'vidmoly\.org', 'vidmoly.biz', src, flags=re.IGNORECASE)
        src, key = veziaici_vk_clean(src)
        low = src.lower()
        if low.startswith('about:') or low.startswith('data:') or key in seen:
            continue
        if 'vidmoly' in low:
            vidmoly_embeds.append((src, '[B]Vidmoly.biz[/B]'))
            seen.add(key)
        elif veziaici_is_vk(low) and 'video_ext.php' in low:
            vk_embeds.append((src, '[B]VKVideo[/B]'))
            seen.add(key)

    # Vidmoly are prioritate: VK se foloseste doar cand pagina nu are Vidmoly.
    if vidmoly_embeds:
        return vidmoly_embeds
    return vk_embeds


def veziaici_vk_hls(embed_url):
    """Extrage stream-ul HLS dintr-un embed VK (video_ext.php).

    IMPORTANT: linkul VK contine expires= si srcIp=, deci e valabil doar
    cateva ore si numai de pe IP-ul care l-a cerut. De aceea extragerea se
    face la momentul redarii, pe cutia utilizatorului, nu la construirea listei.
    """
    if not embed_url:
        return ''
    headers = {
        'User-Agent': useragent,
        'Referer': 'https://veziaici.net/',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    # VK returneaza uneori (tranzitoriu) o pagina scurta fara date de player -
    # de obicei un rate-limit / hiccup momentan al CDN-ului, nu o eroare reala
    # a clipului. Reincercam de cateva ori inainte sa renuntam, ca sa nu pierdem
    # "partea 1" cand doar primul request a picat.
    data = ''
    for attempt in range(3):
        try:
            data = requests.get(embed_url, headers=headers, timeout=25, verify=False).text
        except Exception as e:
            try:
                xbmc.log('[RomyLive] VK fetch error %s: %s' % (embed_url, e), level=xbmc.LOGWARNING)
            except:
                pass
            data = ''
        if data and re.search(r'"(?:hls(?:_ondemand)?|url1080|url720|url480|url360|url240)"\s*:\s*"', data):
            break
        if attempt < 2:
            try:
                time.sleep(1.5)
            except:
                pass
    if not data:
        return ''

    # VK nu mai livreaza mp4 progresiv pentru clipurile noi; ordinea de mai jos
    # incearca intai HLS, apoi cade pe url720/480/360/240 daca mai exista.
    stream = ''
    m = re.search(r'"hls(?:_ondemand)?"\s*:\s*"(.*?)"', data)
    if m:
        stream = m.group(1)
    if not stream:
        for quality in ('url1080', 'url720', 'url480', 'url360', 'url240'):
            m = re.search(r'"%s"\s*:\s*"(.*?)"' % quality, data)
            if m and m.group(1):
                stream = m.group(1)
                break
    if not stream:
        return ''

    stream = stream.replace('\\/', '/').replace('\\u0026', '&').replace('&amp;', '&')
    return stream_url_with_headers(stream, 'https://vkvideo.ru/')


def veziaici_vk_play(url, name, iconimage):
    """Mode 57: rezolva embedul VK in momentul redarii si il da lui Kodi."""
    stream = ''
    try:
        stream = veziaici_vk_hls(url)
    except Exception as e:
        try:
            xbmc.log('[RomyLive] VK resolve error: %s' % e, level=xbmc.LOGWARNING)
        except:
            pass

    # Plasa de siguranta: daca extragerea directa esueaza, incercam resolverul.
    if not stream:
        try:
            resolved = resolveurl.resolve(url)
            if resolved:
                stream = stream_url_with_headers(resolved, 'https://vkvideo.ru/')
        except:
            pass

    if not stream:
        notify('[COLOR red]Nu am putut extrage stream-ul VK[/COLOR]')
        xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
        return False

    li = xbmcgui.ListItem(name or 'VKVideo', path=stream)
    if iconimage:
        li.setArt({'icon': iconimage, 'thumb': iconimage})
    try:
        li.getVideoInfoTag().setTitle(name or 'VKVideo')
    except:
        li.setInfo(type='video', infoLabels={'Title': name or 'VKVideo'})
    li.setProperty('IsPlayable', 'true')
    li.setContentLookup(False)
    if '.m3u8' in stream.split('|')[0]:
        li.setMimeType('application/vnd.apple.mpegurl')
    xbmcplugin.setResolvedUrl(addon_handle, True, li)
    return True


def veziaici_masterchef_list():
    entries = veziaici_masterchef_collect_entries()
    if not entries:
        notify('[COLOR red]Nu am gasit episoade MasterChef[/COLOR]')
        return

    count = 0
    for key in sorted(entries.keys(), reverse=True):
        entry = entries[key]
        embeds = veziaici_masterchef_find_embeds(entry.get('url', ''))
        if not embeds:
            continue

        season_num = entry.get('season', 11)
        ep_num = entry.get('episode', 0)
        date = veziaici_furnicutele_extract_date(entry.get('title', ''), entry.get('url', ''))

        # Un episod poate fi impartit in mai multe parti (ex. 2 clipuri VK pe
        # aceeasi pagina). Le listam pe toate, in ordinea din pagina.
        multi_part = len(embeds) > 1
        for idx, (embed, host_name) in enumerate(embeds):
            if veziaici_is_vk(embed):
                # VK se rezolva la redare (link legat de IP + expires).
                play_url = (
                    '%s?mode=57&url=%s&name=%s&iconimage=%s'
                ) % (
                    sys.argv[0],
                    urllib.quote_plus(embed),
                    urllib.quote_plus('MasterChef S%dE%d' % (season_num, ep_num)),
                    urllib.quote_plus(thumb_masterchef)
                )
            else:
                play_url = (
                    'plugin://plugin.video.smr_link_tester/?mode=play_link'
                    '&link=%s&switch=play$nome=%s'
                ) % (
                    urllib.quote_plus(embed),
                    host_name
                )

            part_label = ''
            if multi_part:
                part_label = ' [COLOR yellow]Partea %d[/COLOR]' % (idx + 1)

            title = '[COLOR white][B]MasterChef Sezonul %d Episodul %d[/B][/COLOR]%s' % (
                season_num, ep_num, part_label
            )
            addLink(
                title, play_url, '', thumb_masterchef, fanart_masterchef, '',
                '[COLOR grey][I] %s[/COLOR][/I]' % date if date else '', date,
                '',  # credits
                '',  # year
                '',  # director
                '',  # writer
                '',  # duration
                '',  # premiered
                '',  # studio
                '',  # rate
                '',  # originaltitle
                '',  # country
                '',  # rating
                '',  # userrating
                '',  # votes
                ''   # aired
            )
            count += 1

    if count == 0:
        notify('[COLOR red]Nu am gasit linkuri Vidmoly.biz sau VK pentru MasterChef[/COLOR]')


def veziaici_insula_pages():
    pages = [url_veziaici_insula]
    try:
        first = requests.get(url_veziaici_insula, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/', first, re.IGNORECASE)
        max_page = 1
        for page_num in page_nums:
            try:
                max_page = max(max_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_page + 1):
            pages.append(url_veziaici_insula.rstrip('/') + '/page/%d/' % page_num)
    except:
        for page_num in range(2, 5):
            pages.append(url_veziaici_insula.rstrip('/') + '/page/%d/' % page_num)

    search_url = 'https://veziaici.net/?s=Insula+Iubirii+Sezonul+10+Episodul'
    pages.append(search_url)
    try:
        first_search = requests.get(search_url, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/\?s=Insula\+Iubirii\+Sezonul\+10\+Episodul', first_search, re.IGNORECASE)
        max_search_page = 1
        for page_num in page_nums:
            try:
                max_search_page = max(max_search_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_search_page + 1):
            pages.append('https://veziaici.net/page/%d/?s=Insula+Iubirii+Sezonul+10+Episodul' % page_num)
    except:
        for page_num in range(2, 5):
            pages.append('https://veziaici.net/page/%d/?s=Insula+Iubirii+Sezonul+10+Episodul' % page_num)
    return pages


def veziaici_insula_collect_entries():
    entries = {}
    for page in veziaici_insula_pages():
        try:
            data = requests.get(page, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        except Exception as e:
            try:
                xbmc.log('[RomyLive] VeziAici Insula Iubirii page error %s: %s' % (page, e), level=xbmc.LOGWARNING)
            except:
                pass
            continue

        matches = re.compile(r'<a\b[^>]*href=["\']([^"\']*insula-iubirii[^"\']*)["\'][^>]*>(.*?)</a>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        for href, text in matches:
            title = veziaici_clean_text(text)
            try:
                href = html_unescape(href)
            except:
                pass
            if '/category/' in href or '/feed' in href or href.endswith(('.webp', '.jpg', '.jpeg', '.png')):
                continue
            # Doar Insula Iubirii Romania: excludem versiunea din Spania si reuniunile.
            if re.search(r'spania|reuniun', title + ' ' + href, re.IGNORECASE):
                continue
            if not re.search(r'episod', title or href, re.IGNORECASE):
                continue
            ep_num = veziaici_furnicutele_episode_number(title, href)
            season_num = veziaici_furnicutele_season_number(title, href)
            if season_num != 10:
                continue
            if ep_num > 0:
                key = (season_num, ep_num)
                if key not in entries:
                    entries[key] = {'title': title, 'url': href, 'season': season_num, 'episode': ep_num}
    return entries


def veziaici_insula_find_embeds(page_url):
    try:
        data = requests.get(page_url, headers={'User-Agent': useragent, 'Referer': url_veziaici_insula}, timeout=20, verify=False).text
    except Exception as e:
        try:
            xbmc.log('[RomyLive] VeziAici Insula Iubirii episode error %s: %s' % (page_url, e), level=xbmc.LOGWARNING)
        except:
            pass
        return []

    # Un singur scan, ca sa pastram ordinea din pagina (partea 1, partea 2, ...).
    pattern = re.compile(r'(?:data-lazy-src|src)=["\']([^"\']+)["\']', re.MULTILINE|re.DOTALL|re.IGNORECASE)
    vidmoly_embeds = []
    vk_embeds = []
    seen = set()
    for match in pattern.finditer(data):
        src = match.group(1)
        src = re.sub(r'vidmoly\.org', 'vidmoly.biz', src, flags=re.IGNORECASE)
        src, key = veziaici_vk_clean(src)
        low = src.lower()
        if low.startswith('about:') or low.startswith('data:') or key in seen:
            continue
        if 'vidmoly' in low:
            vidmoly_embeds.append((src, '[B]Vidmoly.biz[/B]'))
            seen.add(key)
        elif veziaici_is_vk(low) and 'video_ext.php' in low:
            vk_embeds.append((src, '[B]VKVideo[/B]'))
            seen.add(key)

    # Vidmoly are prioritate: VK se foloseste doar cand pagina nu are Vidmoly.
    if vidmoly_embeds:
        return vidmoly_embeds
    return vk_embeds


def veziaici_insula_list():
    entries = veziaici_insula_collect_entries()
    if not entries:
        notify('[COLOR red]Nu am gasit episoade Insula Iubirii[/COLOR]')
        return

    count = 0
    for key in sorted(entries.keys(), reverse=True):
        entry = entries[key]
        embeds = veziaici_insula_find_embeds(entry.get('url', ''))
        if not embeds:
            continue

        season_num = entry.get('season', 10)
        ep_num = entry.get('episode', 0)
        date = veziaici_furnicutele_extract_date(entry.get('title', ''), entry.get('url', ''))

        multi_part = len(embeds) > 1
        for idx, (embed, host_name) in enumerate(embeds):
            if veziaici_is_vk(embed):
                # VK se rezolva la redare (link legat de IP + expires).
                play_url = (
                    '%s?mode=57&url=%s&name=%s&iconimage=%s'
                ) % (
                    sys.argv[0],
                    urllib.quote_plus(embed),
                    urllib.quote_plus('Insula Iubirii S%dE%d' % (season_num, ep_num)),
                    urllib.quote_plus(thumb_insula)
                )
            else:
                play_url = (
                    'plugin://plugin.video.smr_link_tester/?mode=play_link'
                    '&link=%s&switch=play$nome=%s'
                ) % (
                    urllib.quote_plus(embed),
                    host_name
                )

            part_label = ''
            if multi_part:
                part_label = ' [COLOR yellow]Partea %d[/COLOR]' % (idx + 1)

            title = '[COLOR white][B]Insula Iubirii Sezonul %d Episodul %d[/B][/COLOR]%s' % (
                season_num, ep_num, part_label
            )
            addLink(
                title, play_url, '', thumb_insula, fanart_insula, '',
                '[COLOR grey][I] %s[/COLOR][/I]' % date if date else '', date,
                '',  # credits
                '',  # year
                '',  # director
                '',  # writer
                '',  # duration
                '',  # premiered
                '',  # studio
                '',  # rate
                '',  # originaltitle
                '',  # country
                '',  # rating
                '',  # userrating
                '',  # votes
                ''   # aired
            )
            count += 1

    if count == 0:
        notify('[COLOR red]Nu am gasit linkuri Vidmoly.biz sau VK pentru Insula Iubirii[/COLOR]')


def veziaici_vocea_pages():
    pages = [url_veziaici_vocea]
    try:
        first = requests.get(url_veziaici_vocea, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/', first, re.IGNORECASE)
        max_page = 1
        for page_num in page_nums:
            try:
                max_page = max(max_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_page + 1):
            pages.append(url_veziaici_vocea.rstrip('/') + '/page/%d/' % page_num)
    except:
        for page_num in range(2, 5):
            pages.append(url_veziaici_vocea.rstrip('/') + '/page/%d/' % page_num)

    search_url = 'https://veziaici.net/?s=Vocea+Romaniei+Sezonul+14+Episodul'
    pages.append(search_url)
    try:
        first_search = requests.get(search_url, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/\?s=Vocea\+Romaniei\+Sezonul\+14\+Episodul', first_search, re.IGNORECASE)
        max_search_page = 1
        for page_num in page_nums:
            try:
                max_search_page = max(max_search_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_search_page + 1):
            pages.append('https://veziaici.net/page/%d/?s=Vocea+Romaniei+Sezonul+14+Episodul' % page_num)
    except:
        for page_num in range(2, 5):
            pages.append('https://veziaici.net/page/%d/?s=Vocea+Romaniei+Sezonul+14+Episodul' % page_num)
    return pages


def veziaici_vocea_collect_entries():
    entries = {}
    for page in veziaici_vocea_pages():
        try:
            data = requests.get(page, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        except Exception as e:
            try:
                xbmc.log('[RomyLive] VeziAici Vocea Romaniei page error %s: %s' % (page, e), level=xbmc.LOGWARNING)
            except:
                pass
            continue

        matches = re.compile(r'<a\b[^>]*href=["\']([^"\']*vocea-romaniei[^"\']*)["\'][^>]*>(.*?)</a>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        for href, text in matches:
            title = veziaici_clean_text(text)
            try:
                href = html_unescape(href)
            except:
                pass
            if '/category/' in href or '/feed' in href or href.endswith(('.webp', '.jpg', '.jpeg', '.png')):
                continue
            # Doar Vocea Romaniei (nu Junior / Kids) si doar sezonul curent.
            if re.search(r'junior|kids|copii', title + ' ' + href, re.IGNORECASE):
                continue
            if not re.search(r'episod', title or href, re.IGNORECASE):
                continue
            ep_num = veziaici_furnicutele_episode_number(title, href)
            season_num = veziaici_furnicutele_season_number(title, href)
            if season_num != 14:
                continue
            if ep_num > 0:
                key = (season_num, ep_num)
                if key not in entries:
                    entries[key] = {'title': title, 'url': href, 'season': season_num, 'episode': ep_num}
    return entries


def veziaici_vocea_find_embeds(page_url):
    try:
        data = requests.get(page_url, headers={'User-Agent': useragent, 'Referer': url_veziaici_vocea}, timeout=20, verify=False).text
    except Exception as e:
        try:
            xbmc.log('[RomyLive] VeziAici Vocea Romaniei episode error %s: %s' % (page_url, e), level=xbmc.LOGWARNING)
        except:
            pass
        return []

    # Un singur scan, ca sa pastram ordinea din pagina (partea 1, partea 2, ...).
    pattern = re.compile(r'(?:data-lazy-src|src)=["\']([^"\']+)["\']', re.MULTILINE|re.DOTALL|re.IGNORECASE)
    vidmoly_embeds = []
    vk_embeds = []
    seen = set()
    for match in pattern.finditer(data):
        src = match.group(1)
        src = re.sub(r'vidmoly\.org', 'vidmoly.biz', src, flags=re.IGNORECASE)
        src, key = veziaici_vk_clean(src)
        low = src.lower()
        if low.startswith('about:') or low.startswith('data:') or key in seen:
            continue
        if 'vidmoly' in low:
            vidmoly_embeds.append((src, '[B]Vidmoly.biz[/B]'))
            seen.add(key)
        elif veziaici_is_vk(low) and 'video_ext.php' in low:
            vk_embeds.append((src, '[B]VKVideo[/B]'))
            seen.add(key)

    # Vidmoly are prioritate: VK se foloseste doar cand pagina nu are Vidmoly.
    if vidmoly_embeds:
        return vidmoly_embeds
    return vk_embeds


def veziaici_vocea_list():
    entries = veziaici_vocea_collect_entries()
    if not entries:
        notify('[COLOR red]Nu am gasit episoade Vocea Romaniei[/COLOR]')
        return

    count = 0
    for key in sorted(entries.keys(), reverse=True):
        entry = entries[key]
        embeds = veziaici_vocea_find_embeds(entry.get('url', ''))
        if not embeds:
            continue

        season_num = entry.get('season', 14)
        ep_num = entry.get('episode', 0)
        date = veziaici_furnicutele_extract_date(entry.get('title', ''), entry.get('url', ''))

        multi_part = len(embeds) > 1
        for idx, (embed, host_name) in enumerate(embeds):
            if veziaici_is_vk(embed):
                # VK se rezolva la redare (link legat de IP + expires).
                play_url = (
                    '%s?mode=57&url=%s&name=%s&iconimage=%s'
                ) % (
                    sys.argv[0],
                    urllib.quote_plus(embed),
                    urllib.quote_plus('Vocea Romaniei S%dE%d' % (season_num, ep_num)),
                    urllib.quote_plus(thumb_vocea)
                )
            else:
                play_url = (
                    'plugin://plugin.video.smr_link_tester/?mode=play_link'
                    '&link=%s&switch=play$nome=%s'
                ) % (
                    urllib.quote_plus(embed),
                    host_name
                )

            part_label = ''
            if multi_part:
                part_label = ' [COLOR yellow]Partea %d[/COLOR]' % (idx + 1)

            title = '[COLOR white][B]Vocea Romaniei Sezonul %d Episodul %d[/B][/COLOR]%s' % (
                season_num, ep_num, part_label
            )
            addLink(
                title, play_url, '', thumb_vocea, fanart_vocea, '',
                '[COLOR grey][I] %s[/COLOR][/I]' % date if date else '', date,
                '',  # credits
                '',  # year
                '',  # director
                '',  # writer
                '',  # duration
                '',  # premiered
                '',  # studio
                '',  # rate
                '',  # originaltitle
                '',  # country
                '',  # rating
                '',  # userrating
                '',  # votes
                ''   # aired
            )
            count += 1

    if count == 0:
        notify('[COLOR red]Nu am gasit linkuri Vidmoly.biz sau VK pentru Vocea Romaniei[/COLOR]')


def veziaici_jocul_pages():
    pages = [url_veziaici_jocul]
    try:
        first = requests.get(url_veziaici_jocul, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/', first, re.IGNORECASE)
        max_page = 1
        for page_num in page_nums:
            try:
                max_page = max(max_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_page + 1):
            pages.append(url_veziaici_jocul.rstrip('/') + '/page/%d/' % page_num)
    except:
        for page_num in range(2, 5):
            pages.append(url_veziaici_jocul.rstrip('/') + '/page/%d/' % page_num)

    search_url = 'https://veziaici.net/?s=Jocul+Cuvintelor+Sezonul+7+Episodul'
    pages.append(search_url)
    try:
        first_search = requests.get(search_url, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/\?s=Jocul\+Cuvintelor\+Sezonul\+7\+Episodul', first_search, re.IGNORECASE)
        max_search_page = 1
        for page_num in page_nums:
            try:
                max_search_page = max(max_search_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_search_page + 1):
            pages.append('https://veziaici.net/page/%d/?s=Jocul+Cuvintelor+Sezonul+7+Episodul' % page_num)
    except:
        for page_num in range(2, 5):
            pages.append('https://veziaici.net/page/%d/?s=Jocul+Cuvintelor+Sezonul+7+Episodul' % page_num)
    return pages


def veziaici_jocul_collect_entries():
    entries = {}
    # Categoria are ~20 de pagini (sezoanele 2-7). Sezonul 7 e la inceput, deci
    # ne oprim dupa 2 pagini consecutive fara episoade din sezonul 7, ca sa nu
    # descarcam degeaba arhiva din 2022.
    empty_streak = 0
    for page in veziaici_jocul_pages():
        try:
            data = requests.get(page, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        except Exception as e:
            try:
                xbmc.log('[RomyLive] VeziAici Jocul Cuvintelor page error %s: %s' % (page, e), level=xbmc.LOGWARNING)
            except:
                pass
            continue

        found_on_page = 0
        matches = re.compile(r'<a\b[^>]*href=["\']([^"\']*jocul-cuvintelor[^"\']*)["\'][^>]*>(.*?)</a>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        for href, text in matches:
            title = veziaici_clean_text(text)
            try:
                href = html_unescape(href)
            except:
                pass
            if '/category/' in href or '/feed' in href or href.endswith(('.webp', '.jpg', '.jpeg', '.png')):
                continue
            if not re.search(r'episod', title or href, re.IGNORECASE):
                continue
            ep_num = veziaici_furnicutele_episode_number(title, href)
            season_num = veziaici_furnicutele_season_number(title, href)
            if season_num != 7:
                continue
            found_on_page += 1
            if ep_num > 0:
                key = (season_num, ep_num)
                if key not in entries:
                    entries[key] = {'title': title, 'url': href, 'season': season_num, 'episode': ep_num}

        if entries and found_on_page == 0:
            empty_streak += 1
            if empty_streak >= 2:
                break
        else:
            empty_streak = 0
    return entries


def veziaici_jocul_find_embeds(page_url):
    try:
        data = requests.get(page_url, headers={'User-Agent': useragent, 'Referer': url_veziaici_jocul}, timeout=20, verify=False).text
    except Exception as e:
        try:
            xbmc.log('[RomyLive] VeziAici Jocul Cuvintelor episode error %s: %s' % (page_url, e), level=xbmc.LOGWARNING)
        except:
            pass
        return []

    # Un singur scan, ca sa pastram ordinea din pagina (partea 1, partea 2, ...).
    pattern = re.compile(r'(?:data-lazy-src|src)=["\']([^"\']+)["\']', re.MULTILINE|re.DOTALL|re.IGNORECASE)
    vidmoly_embeds = []
    vk_embeds = []
    seen = set()
    for match in pattern.finditer(data):
        src = match.group(1)
        src = re.sub(r'vidmoly\.org', 'vidmoly.biz', src, flags=re.IGNORECASE)
        src, key = veziaici_vk_clean(src)
        low = src.lower()
        if low.startswith('about:') or low.startswith('data:') or key in seen:
            continue
        if 'vidmoly' in low:
            vidmoly_embeds.append((src, '[B]Vidmoly.biz[/B]'))
            seen.add(key)
        elif veziaici_is_vk(low) and 'video_ext.php' in low:
            vk_embeds.append((src, '[B]VKVideo[/B]'))
            seen.add(key)

    # Vidmoly are prioritate: VK se foloseste doar cand pagina nu are Vidmoly.
    if vidmoly_embeds:
        return vidmoly_embeds
    return vk_embeds


def veziaici_jocul_list():
    entries = veziaici_jocul_collect_entries()
    if not entries:
        notify('[COLOR red]Nu am gasit episoade Jocul Cuvintelor[/COLOR]')
        return

    count = 0
    for key in sorted(entries.keys(), reverse=True):
        entry = entries[key]
        embeds = veziaici_jocul_find_embeds(entry.get('url', ''))
        if not embeds:
            continue

        season_num = entry.get('season', 7)
        ep_num = entry.get('episode', 0)
        date = veziaici_furnicutele_extract_date(entry.get('title', ''), entry.get('url', ''))

        multi_part = len(embeds) > 1
        for idx, (embed, host_name) in enumerate(embeds):
            if veziaici_is_vk(embed):
                # VK se rezolva la redare (link legat de IP + expires).
                play_url = (
                    '%s?mode=57&url=%s&name=%s&iconimage=%s'
                ) % (
                    sys.argv[0],
                    urllib.quote_plus(embed),
                    urllib.quote_plus('Jocul Cuvintelor S%dE%d' % (season_num, ep_num)),
                    urllib.quote_plus(thumb_jocul)
                )
            else:
                play_url = (
                    'plugin://plugin.video.smr_link_tester/?mode=play_link'
                    '&link=%s&switch=play$nome=%s'
                ) % (
                    urllib.quote_plus(embed),
                    host_name
                )

            part_label = ''
            if multi_part:
                part_label = ' [COLOR yellow]Partea %d[/COLOR]' % (idx + 1)

            title = '[COLOR white][B]Jocul Cuvintelor Sezonul %d Episodul %d[/B][/COLOR]%s' % (
                season_num, ep_num, part_label
            )
            addLink(
                title, play_url, '', thumb_jocul, fanart_jocul, '',
                '[COLOR grey][I] %s[/COLOR][/I]' % date if date else '', date,
                '',  # credits
                '',  # year
                '',  # director
                '',  # writer
                '',  # duration
                '',  # premiered
                '',  # studio
                '',  # rate
                '',  # originaltitle
                '',  # country
                '',  # rating
                '',  # userrating
                '',  # votes
                ''   # aired
            )
            count += 1

    if count == 0:
        notify('[COLOR red]Nu am gasit linkuri Vidmoly.biz sau VK pentru Jocul Cuvintelor[/COLOR]')


def veziaici_furnicutele_episode_number(title, href=''):
    for value in (title or '', href or ''):
        try:
            m = re.search(r'Episod(?:ul)?[\s\-_]+(\d+)', value, re.IGNORECASE)
            if m:
                return int(m.group(1))
            m = re.search(r'\bE(?:p)?[\s\-_]?(\d{1,3})\b', value, re.IGNORECASE)
            if m:
                return int(m.group(1))
        except:
            pass
    return 0


def veziaici_furnicutele_season_number(title, href=''):
    for value in (title or '', href or ''):
        try:
            m = re.search(r'Sezonul?[\s\-_]+(\d+)', value, re.IGNORECASE)
            if m:
                return int(m.group(1))
            m = re.search(r'\bS(?:ez)?(\d{1,2})\s*[\-_ ]?\s*E(?:p)?\d', value, re.IGNORECASE)
            if m:
                return int(m.group(1))
        except:
            pass
    return 1


def veziaici_furnicutele_extract_date(title, href=''):
    months = 'Ianuarie|Februarie|Martie|Aprilie|Mai|Iunie|Iulie|August|Septembrie|Octombrie|Noiembrie|Decembrie'
    for raw in (title or '', href or ''):
        value = re.sub(r'[\-_/]+', ' ', raw)
        try:
            m = re.search(r'(\d{1,2}\s+(?:%s)\s+\d{4})' % months, value, re.IGNORECASE)
            if m:
                return re.sub(r'\s+', ' ', m.group(1)).title()
            m = re.search(r'(\d{1,2}\s+(?:%s))' % months, value, re.IGNORECASE)
            if m:
                return re.sub(r'\s+', ' ', m.group(1)).title()
        except:
            pass
    return ''


def veziaici_furnicutele_pages():
    pages = [url_veziaici_furnicutele]
    try:
        first = requests.get(url_veziaici_furnicutele, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/', first, re.IGNORECASE)
        max_page = 1
        for page_num in page_nums:
            try:
                max_page = max(max_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_page + 1):
            pages.append(url_veziaici_furnicutele.rstrip('/') + '/page/%d/' % page_num)
    except:
        for page_num in range(2, 5):
            pages.append(url_veziaici_furnicutele.rstrip('/') + '/page/%d/' % page_num)
    search_url = 'https://veziaici.net/?s=Furnicutele+Episodul'
    pages.append(search_url)
    try:
        first_search = requests.get(search_url, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/\?s=Furnicutele\+Episodul', first_search, re.IGNORECASE)
        max_search_page = 1
        for page_num in page_nums:
            try:
                max_search_page = max(max_search_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_search_page + 1):
            pages.append('https://veziaici.net/page/%d/?s=Furnicutele+Episodul' % page_num)
    except:
        for page_num in range(2, 5):
            pages.append('https://veziaici.net/page/%d/?s=Furnicutele+Episodul' % page_num)
    return pages


def veziaici_furnicutele_collect_entries():
    entries = {}
    for page in veziaici_furnicutele_pages():
        try:
            data = requests.get(page, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        except Exception as e:
            try:
                xbmc.log('[RomyLive] VeziAici Furnicutele page error %s: %s' % (page, e), level=xbmc.LOGWARNING)
            except:
                pass
            continue
        matches = re.compile(r'<a\b[^>]*href=["\']([^"\']*furnicutele[^"\']*)["\'][^>]*>(.*?)</a>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        for href, text in matches:
            title = veziaici_clean_text(text)
            try:
                href = html_unescape(href)
            except:
                pass
            if '/category/' in href or '/feed' in href or href.endswith(('.webp', '.jpg', '.jpeg', '.png')):
                continue
            if not re.search(r'Episod', title, re.IGNORECASE) and not re.search(r'episodul', href, re.IGNORECASE):
                continue
            ep_num = veziaici_furnicutele_episode_number(title, href)
            season_num = veziaici_furnicutele_season_number(title, href)
            if ep_num > 0:
                key = (season_num, ep_num)
                if key not in entries:
                    entries[key] = {'title': title, 'url': href, 'season': season_num, 'episode': ep_num}
    return entries


def veziaici_furnicutele_normalize_embed(src):
    try:
        src = html_unescape(src)
    except:
        pass
    src = src.replace('&amp;', '&').replace('&#038;', '&')
    # vidmoly.org nu functioneaza in Kodi (resolverul nu il recunoaste) -> fortam mereu vidmoly.biz.
    return re.sub(r'vidmoly\.(?:org|net|to|me)', 'vidmoly.biz', src, flags=re.IGNORECASE)


def veziaici_furnicutele_find_embeds(page_url):
    try:
        data = requests.get(page_url, headers={'User-Agent': useragent, 'Referer': url_veziaici_furnicutele}, timeout=20, verify=False).text
    except Exception as e:
        try:
            xbmc.log('[RomyLive] VeziAici Furnicutele episode error %s: %s' % (page_url, e), level=xbmc.LOGWARNING)
        except:
            pass
        return []
    pattern = re.compile(r'(?:data-lazy-src|src)=["\']([^"\']+)["\']', re.MULTILINE|re.DOTALL|re.IGNORECASE)
    vidmoly_embeds = []
    other_embeds = []
    seen = set()
    for match in pattern.finditer(data):
        src = veziaici_furnicutele_normalize_embed(match.group(1))
        low = src.lower()
        if low.startswith('about:') or low.startswith('data:') or low in seen:
            continue
        if 'vidmoly' in low:
            vidmoly_embeds.append((src, '[B]Vidmoly.biz[/B]'))
            seen.add(low)
        elif 'vkvideo' in low or 'vk.com' in low or 'vk.ru' in low:
            other_embeds.append((src, '[B]VKVideo[/B]'))
            seen.add(low)
        elif 'rumble.com/embed' in low:
            other_embeds.append((src, '[B]Rumble[/B]'))
            seen.add(low)
    # Cerinta: EXCLUSIV Vidmoly.biz cand exista pe pagina; celelalte servere doar cand nu avem Vidmoly.
    if vidmoly_embeds:
        return vidmoly_embeds
    return other_embeds


def veziaici_furnicutele_find_embed(page_url):
    embeds = veziaici_furnicutele_find_embeds(page_url)
    if embeds:
        return embeds[0]
    return '', ''


def veziaici_furnicutele_list():
    entries = veziaici_furnicutele_collect_entries()
    if not entries:
        notify('[COLOR red]Nu am gasit episoade Furnicutele[/COLOR]')
        return
    count = 0
    for key in sorted(entries.keys(), reverse=True):
        entry = entries[key]
        season_num = entry.get('season', 1)
        ep_num = entry.get('episode', 0)
        embed, host_name = veziaici_furnicutele_find_embed(entry.get('url', ''))
        if not embed:
            continue
        play_url = 'plugin://plugin.video.smr_link_tester/?mode=play_link&link=%s&switch=play$nome=%s' % (urllib.quote_plus(embed), host_name)
        title = '[COLOR white][B]Furnicutele Sezonul %d Episodul %d[/B][/COLOR]' % (season_num, ep_num)
        date = veziaici_furnicutele_extract_date(entry.get('title', ''), entry.get('url', ''))
        addLink(title, play_url, '', thumb_furnicutele, fanart_furnicutele, '', '[COLOR grey][I] %s[/COLOR][/I]' % date if date else '', date, '', '', '', '', '', '', '', '', '', '', '', '', '', '')
        count += 1
    if count == 0:
        notify('[COLOR red]Nu am gasit linkuri video pentru Furnicutele[/COLOR]')



def veziaici_chefi_pages():
    pages = [url_veziaici_chefi]
    try:
        first = requests.get(url_veziaici_chefi, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/', first, re.IGNORECASE)
        max_page = 1
        for page_num in page_nums:
            try:
                max_page = max(max_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_page + 1):
            pages.append(url_veziaici_chefi.rstrip('/') + '/page/%d/' % page_num)
    except:
        for page_num in range(2, 40):
            pages.append(url_veziaici_chefi.rstrip('/') + '/page/%d/' % page_num)
    return pages


def veziaici_chefi_extract_date(title):
    try:
        months = 'Ianuarie|Februarie|Martie|Aprilie|Mai|Iunie|Iulie|August|Septembrie|Octombrie|Noiembrie|Decembrie'
        m = re.search(r'(\d{1,2}\s+(?:%s)\s+\d{4})' % months, title or '', re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.search(r'(\d{1,2}\s+(?:Mai|Iunie))\b' , title or '', re.IGNORECASE)
        if m:
            return m.group(1)
    except:
        pass
    return ''


def veziaici_chefi_collect_entries():
    entries = []
    seen = set()
    for page in veziaici_chefi_pages():
        try:
            data = requests.get(page, headers={'User-Agent': useragent, 'Referer': url_veziaici_chefi}, timeout=20, verify=False).text
        except Exception as e:
            try:
                xbmc.log('[RomyLive] VeziAici Chefi page error %s: %s' % (page, e), level=xbmc.LOGWARNING)
            except:
                pass
            continue
        matches = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        for href, text in matches:
            title = veziaici_clean_text(text)
            try:
                href = html_unescape(href)
            except:
                pass
            if href in seen or '/category/' in href:
                continue
            if not re.search(r'chefi', href, re.IGNORECASE):
                continue
            if not re.search(r'Episod', title, re.IGNORECASE):
                continue
            seen.add(href)
            entries.append({'title': title, 'url': href})
    return entries


def veziaici_chefi_find_embeds(page_url):
    try:
        data = requests.get(page_url, headers={'User-Agent': useragent, 'Referer': url_veziaici_chefi}, timeout=20, verify=False).text
    except Exception as e:
        try:
            xbmc.log('[RomyLive] VeziAici Chefi episode error %s: %s' % (page_url, e), level=xbmc.LOGWARNING)
        except:
            pass
        return []
    results = []
    seen = set()
    iframes = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    for src in iframes:
        try:
            src = html_unescape(src)
        except:
            pass
        if src in seen:
            continue
        low = src.lower()
        host_name = ''
        if 'vidmoly' in low:
            host_name = '[B]Vidmoly.net[/B]'
        elif 'vkvideo' in low or 'vk.com' in low:
            host_name = '[B]VKVideo[/B]'
        elif 'rumble.com/embed' in low:
            host_name = '[B]Rumble[/B]'
        elif 'streamtape' in low:
            host_name = '[B]StreamTape[/B]'
        elif 'dood' in low:
            host_name = '[B]Dood[/B]'
        elif 'filemoon' in low:
            host_name = '[B]FileMoon[/B]'
        elif 'uqload' in low:
            host_name = '[B]Uqload[/B]'
        if host_name:
            seen.add(src)
            results.append((src, host_name))
    return results


def veziaici_chefi_list():
    entries = veziaici_chefi_collect_entries()
    if not entries:
        notify('[COLOR red]Nu am gasit episoade Chef la cutite[/COLOR]')
        return
    for entry in entries:
        title = '[COLOR white][B]%s[/B][/COLOR]' % entry.get('title', 'Chef la cutite')
        date = veziaici_chefi_extract_date(entry.get('title', ''))
        desc = '[COLOR grey][I] %s[/COLOR][/I]' % date if date else ''
        addDir(title.encode('utf-8', 'ignore'), entry.get('url', ''), 1, thumb_chefi, fanart_chefi, desc, '', date, '', '', '', '', '', '', '', '', '', '', '', '', '', '')


def veziaici_chefi_episode(page_url):
    embeds = veziaici_chefi_find_embeds(page_url)
    if not embeds:
        notify('[COLOR red]Nu am gasit linkuri video pentru Chef la cutite[/COLOR]')
        return
    count = 1
    for embed, host_name in embeds:
        play_url = 'plugin://plugin.video.smr_link_tester/?mode=play_link&link=%s&switch=play$nome=%s' % (urllib.quote_plus(embed), host_name)
        title = '[COLOR white][B]Redare %d - %s[/B][/COLOR]' % (count, host_name)
        addLink(title, play_url, '', thumb_chefi, fanart_chefi, '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
        count += 1

def veziaici_camatarii_pages():
    pages = [url_veziaici_camatarii]
    try:
        first = requests.get(url_veziaici_camatarii, headers={'User-Agent': useragent}, timeout=20, verify=False).text
        page_nums = re.findall(r'/page/(\d+)/', first, re.IGNORECASE)
        max_page = 1
        for page_num in page_nums:
            try:
                max_page = max(max_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_page + 1):
            pages.append(url_veziaici_camatarii.rstrip('/') + '/page/%d/' % page_num)
    except:
        for page_num in range(2, 10):
            pages.append(url_veziaici_camatarii.rstrip('/') + '/page/%d/' % page_num)
    return pages


def veziaici_camatarii_extract_date(title):
    try:
        months = 'Ianuarie|Februarie|Martie|Aprilie|Mai|Iunie|Iulie|August|Septembrie|Octombrie|Noiembrie|Decembrie'
        m = re.search(r'(\d{1,2}\s+(?:%s)\s+\d{4})' % months, title or '', re.IGNORECASE)
        if m:
            return m.group(1)
    except:
        pass
    return ''


def veziaici_camatarii_collect_entries():
    entries = []
    seen = set()
    for page in veziaici_camatarii_pages():
        try:
            data = requests.get(page, headers={'User-Agent': useragent, 'Referer': url_veziaici_camatarii}, timeout=20, verify=False).text
        except Exception as e:
            try:
                xbmc.log('[RomyLive] VeziAici Camatarii page error %s: %s' % (page, e), level=xbmc.LOGWARNING)
            except:
                pass
            continue
        matches = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        for href, text in matches:
            title = veziaici_clean_text(text)
            try:
                href = html_unescape(href)
            except:
                pass
            if href in seen or '/category/' in href:
                continue
            if not re.search(r'camatarii', href, re.IGNORECASE):
                continue
            if not re.search(r'Episod|episod', title, re.IGNORECASE):
                continue
            seen.add(href)
            entries.append({'title': title, 'url': href})
    return entries


def veziaici_camatarii_find_embeds(page_url):
    try:
        data = requests.get(page_url, headers={'User-Agent': useragent, 'Referer': url_veziaici_camatarii}, timeout=20, verify=False).text
    except Exception as e:
        try:
            xbmc.log('[RomyLive] VeziAici Camatarii episode error %s: %s' % (page_url, e), level=xbmc.LOGWARNING)
        except:
            pass
        return []
    results = []
    seen = set()
    # cauta si data-lazy-src
    iframes = re.compile(r'<iframe[^>]+(?:src|data-lazy-src)=["\']([^"\']+)["\']', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    for src in iframes:
        try:
            src = html_unescape(src)
        except:
            pass
        if src in seen or src == 'about:blank':
            continue
        low = src.lower()
        host_name = ''
        if 'vidmoly' in low:
            host_name = '[B]Vidmoly.net[/B]'
        elif 'vkvideo' in low or 'vk.com' in low:
            host_name = '[B]VKVideo[/B]'
        elif 'rumble.com/embed' in low:
            host_name = '[B]Rumble[/B]'
        elif 'streamtape' in low:
            host_name = '[B]StreamTape[/B]'
        elif 'dood' in low:
            host_name = '[B]Dood[/B]'
        elif 'filemoon' in low:
            host_name = '[B]FileMoon[/B]'
        elif 'uqload' in low:
            host_name = '[B]Uqload[/B]'
        if host_name:
            seen.add(src)
            results.append((src, host_name))
    return results


def veziaici_camatarii_list():
    entries = veziaici_camatarii_collect_entries()
    if not entries:
        notify('[COLOR red]Nu am gasit episoade Camatarii[/COLOR]')
        return
    for entry in entries:
        title = '[COLOR white][B]%s[/B][/COLOR]' % entry.get('title', 'Camatarii')
        date = veziaici_camatarii_extract_date(entry.get('title', ''))
        desc = '[COLOR grey][I] %s[/COLOR][/I]' % date if date else ''
        addDir(title.encode('utf-8', 'ignore'), entry.get('url', ''), 1, thumb_camatarii, fanart_camatarii, desc, '', date, '', '', '', '', '', '', '', '', '', '', '', '', '', '')


def veziaici_camatarii_episode(page_url):
    embeds = veziaici_camatarii_find_embeds(page_url)
    if not embeds:
        notify('[COLOR red]Nu am gasit linkuri video pentru Camatarii[/COLOR]')
        return
    count = 1
    for embed, host_name in embeds:
        play_url = 'plugin://plugin.video.smr_link_tester/?mode=play_link&link=%s&switch=play$nome=%s' % (urllib.quote_plus(embed), host_name)
        title = '[COLOR white][B]Redare %d - %s[/B][/COLOR]' % (count, host_name)
        addLink(title, play_url, '', thumb_camatarii, fanart_camatarii, '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
        count += 1


def veziaici_las_pages():
    """Intoarce toate paginile categoriei Las Fierbinti.

    Categoria are paginare WordPress, asa ca nu depindem de o limita fixa de
    episoade. Numarul maxim este citit din pagina principala si lista ramane
    valabila cand site-ul mai adauga sezoane.
    """
    pages = [url_veziaici_las]
    try:
        first = requests.get(
            url_veziaici_las,
            headers={'User-Agent': useragent},
            timeout=20,
            verify=False
        ).text
        page_nums = re.findall(r'/page/(\d+)/', first, re.IGNORECASE)
        max_page = 1
        for page_num in page_nums:
            try:
                max_page = max(max_page, int(page_num))
            except:
                pass
        for page_num in range(2, max_page + 1):
            pages.append(url_veziaici_las.rstrip('/') + '/page/%d/' % page_num)
    except Exception as e:
        try:
            xbmc.log('[RomyLive] VeziAici Las Fierbinti pages error: %s' % e, level=xbmc.LOGWARNING)
        except:
            pass
    return pages


def veziaici_las_collect_entries():
    """Colecteaza episoadele din toate paginile categoriei, fara duplicate."""
    entries = {}
    for page in veziaici_las_pages():
        try:
            data = requests.get(
                page,
                headers={'User-Agent': useragent, 'Referer': url_veziaici_las},
                timeout=20,
                verify=False
            ).text
        except Exception as e:
            try:
                xbmc.log('[RomyLive] VeziAici Las Fierbinti page error %s: %s' % (page, e), level=xbmc.LOGWARNING)
            except:
                pass
            continue

        matches = re.compile(
            r'<a\b[^>]*href=["\']([^"\']*las-fierbinti[^"\']*)["\'][^>]*>(.*?)</a>',
            re.MULTILINE | re.DOTALL | re.IGNORECASE
        )
        for match in matches.finditer(data):
            href, text = match.group(1), match.group(2)
            title = veziaici_clean_text(text)
            try:
                href = html_unescape(href)
            except:
                pass
            if '/category/' in href or '/feed' in href:
                continue
            if not re.search(r'episod', title or href, re.IGNORECASE):
                continue

            episode = veziaici_furnicutele_episode_number(title, href)
            season = veziaici_furnicutele_season_number(title, href)
            if episode <= 0:
                continue

            # Data este in meta-ul cardului (de exemplu "May 19, 2026"),
            # nu intotdeauna in titlul episodului.
            category_date = ''
            try:
                card_tail = data[match.end():match.end() + 5000]
                date_match = re.search(
                    r'<abbr[^>]*class=["\'][^"\']*date published[^"\']*["\'][^>]*>(.*?)</abbr>',
                    card_tail,
                    re.MULTILINE | re.DOTALL | re.IGNORECASE
                )
                if date_match:
                    category_date = veziaici_las_normalize_date(
                        veziaici_clean_text(date_match.group(1))
                    )
            except:
                pass

            # Cheia include sezonul si episodul; astfel linkurile duplicate
            # aparute in card, imagine sau pagini consecutive se elimina.
            key = (season, episode)
            if key not in entries or (
                not entries[key].get('title') and title
            ):
                entries[key] = {
                    'title': title,
                    'url': href,
                    'season': season,
                    'episode': episode,
                    'date': category_date,
                }
    return entries


def veziaici_las_normalize_date(value):
    """Converteste data engleza din cardurile WordPress in format romanesc."""
    months = {
        'january': 'Ianuarie',
        'february': 'Februarie',
        'march': 'Martie',
        'april': 'Aprilie',
        'may': 'Mai',
        'june': 'Iunie',
        'july': 'Iulie',
        'august': 'August',
        'september': 'Septembrie',
        'october': 'Octombrie',
        'november': 'Noiembrie',
        'december': 'Decembrie',
    }
    value = (value or '').strip()
    match = re.search(
        r'(\w+)\s+(\d{1,2}),\s*(\d{4})',
        value,
        re.IGNORECASE
    )
    if match:
        month = months.get(match.group(1).lower(), match.group(1))
        return '%s %s %s' % (match.group(2), month, match.group(3))
    return value


def veziaici_las_subtitle(title, date):
    """Pastreaza numele partii si pune data pe acelasi rand secundar."""
    subtitle = veziaici_clean_text(title or '')
    subtitle = re.sub(
        r'^\s*Las\s+Fierbinti\s+Sezonul?\s+\d+\s+Episod(?:ul)?\s+\d+',
        '',
        subtitle,
        flags=re.IGNORECASE
    )
    subtitle = re.sub(
        r'\b(?:\d{1,2}\s+(?:Ianuarie|Februarie|Martie|Aprilie|Mai|Iunie|'
        r'Iulie|August|Septembrie|Octombrie|Noiembrie|Decembrie)'
        r'(?:\s+\d{4})?)\b',
        '',
        subtitle,
        flags=re.IGNORECASE
    )
    subtitle = re.sub(r'\b(?:online|din)\b', '', subtitle, flags=re.IGNORECASE)
    subtitle = re.sub(r'\s+', ' ', subtitle).strip(' -/')
    if subtitle.lower() in ('ultimul episod', 'episodul'):
        subtitle = ''
    if subtitle and date:
        return '%s / %s' % (subtitle, date)
    return subtitle or date


def veziaici_las_full_title(title, date, season, episode):
    """Foloseste titlul exact al articolului si completeaza data cand lipseste."""
    title = veziaici_clean_text(title or '')
    if not title:
        title = 'Las Fierbinti Sezonul %d Episodul %d' % (season, episode)

    # Unele carduri au data completa in titlu, altele au doar ziua si luna,
    # iar pentru unele data este disponibila numai in meta-ul cardului.
    month_pattern = (
        r'Ianuarie|Februarie|Martie|Aprilie|Mai|Iunie|Iulie|August|'
        r'Septembrie|Octombrie|Noiembrie|Decembrie'
    )
    date_match = re.search(
        r'\b(\d{1,2})\s+(%s)(?:\s+(\d{4}))?\b' % month_pattern,
        title,
        re.IGNORECASE
    )
    if date:
        if date_match:
            # Daca titlul are "21 Mai", adauga anul din data cardului.
            if not date_match.group(3):
                year_match = re.search(r'\b(\d{4})\b', date)
                if year_match:
                    insert_at = date_match.end()
                    title = title[:insert_at] + ' ' + year_match.group(1) + title[insert_at:]
        else:
            title = title.rstrip(' -/') + ' din ' + date
    return title


def veziaici_las_find_embeds(page_url):
    """Gaseste doar serverele cerute de utilizator si prezente pe episod."""
    try:
        data = requests.get(
            page_url,
            headers={'User-Agent': useragent, 'Referer': url_veziaici_las},
            timeout=20,
            verify=False
        ).text
    except Exception as e:
        try:
            xbmc.log('[RomyLive] VeziAici Las Fierbinti episode error %s: %s' % (page_url, e), level=xbmc.LOGWARNING)
        except:
            pass
        return []

    pattern = re.compile(
        r'(?:data-lazy-src|src)=["\']([^"\']+)["\']',
        re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    results = []
    seen_hosts = set()
    for match in pattern.finditer(data):
        src = match.group(1)
        try:
            src = html_unescape(src)
        except:
            pass
        src = src.replace('&amp;', '&').replace('&#038;', '&')
        if src.startswith('//'):
            src = 'https:' + src
        # Curata si normalizeaza linkurile VK de forma video_ext.php,
        # inclusiv cele care apar de doua ori in pagina (src + data-lazy-src).
        try:
            src, source_key = veziaici_vk_clean(src)
        except:
            source_key = src.lower()
        low = src.lower()

        if low.startswith('about:') or low.startswith('data:'):
            continue

        host_name = ''
        host_key = ''
        if 'voe.sx/e/' in low:
            host_name = '[B]Voe.sx[/B]'
            host_key = 'voe.sx'
        elif 'vidmoly' in low:
            host_name = '[B]Vidmoly.biz[/B]'
            host_key = 'vidmoly.biz'
            # Site-ul a folosit si vidmoly.org; resolverul curent foloseste
            # domeniul biz, conform formatului cerut pentru embed.
            src = re.sub(r'https?://(?:www\.)?vidmoly\.org',
                         'https://vidmoly.biz', src, flags=re.IGNORECASE)

            # Nu afisam embeduri Vidmoly expirate sau sterse. In logul trimis,
            # embed-9g4xqgqsa78t.html raspundea cu 404, in timp ce
            # embed-j0sl3b1owux6.html raspundea cu 200.
            try:
                probe = requests.get(
                    src,
                    headers={
                        'User-Agent': useragent,
                        'Referer': page_url,
                    },
                    timeout=12,
                    verify=False,
                    allow_redirects=True
                )
                if int(getattr(probe, 'status_code', 0)) >= 400:
                    try:
                        xbmc.log(
                            '[RomyLive] Ignor embed Vidmoly indisponibil %s (HTTP %s)' %
                            (src, getattr(probe, 'status_code', '')),
                            level=xbmc.LOGWARNING
                        )
                    except:
                        pass
                    continue
            except Exception as e:
                # Daca verificarea esueaza temporar (TLS, timeout sau
                # protectia site-ului), nu elimina sursa din lista. Altfel,
                # un episod cu Voe + VidMoly ramane fara VidMoly doar pentru
                # ca proba a esuat inainte de redare.
                try:
                    xbmc.log(
                        '[RomyLive] Nu pot verifica embedul Vidmoly %s: %s; il pastrez' %
                        (src, e),
                        level=xbmc.LOGWARNING
                    )
                except:
                    pass
        elif veziaici_is_vk(low) and 'video_ext.php' in low:
            host_name = '[B]VKVideo[/B]'
            host_key = 'vkvideo'

        if host_key and host_key not in seen_hosts:
            seen_hosts.add(host_key)
            results.append((src, host_name))
    return results


def veziaici_las_list():
    """Afiseaza episoadele Las Fierbinti, cele mai noi primele."""
    entries = veziaici_las_collect_entries()
    if not entries:
        notify('[COLOR red]Nu am gasit episoade Las Fierbinti[/COLOR]')
        return

    count = 0
    for key in sorted(entries.keys(), reverse=True):
        entry = entries[key]
        title = entry.get('title', '')
        episode = entry.get('episode', 0)
        date = entry.get('date', '')
        if not date:
            date = veziaici_furnicutele_extract_date(title, entry.get('url', ''))

        # Afisarea ramane de tip folder: la click se deschide selectorul de
        # servere, nu porneste automat primul embed.
        full_title = veziaici_las_full_title(
            title,
            date,
            entry.get('season', 1),
            episode
        )
        label = '[COLOR white][B]%s[/B][/COLOR]' % full_title
        subtitle = veziaici_las_subtitle(title, date)
        desc = '[COLOR grey][I] %s[/COLOR][/I]' % subtitle if subtitle else ''
        addDir(
            label.encode('utf-8', 'ignore'),
            entry.get('url', ''),
            1,
            thumb_las,
            fanart_las,
            desc,
            '',
            date,
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            ''
        )
        count += 1

    if count == 0:
        notify('[COLOR red]Nu am gasit episoade Las Fierbinti[/COLOR]')


def veziaici_las_episode(page_url, title=''):
    """Alege si porneste direct serverul disponibil pentru episod."""
    embeds = veziaici_las_find_embeds(page_url)
    if not embeds:
        notify('[COLOR red]Nu am gasit servere Voe.sx, Vidmoly.biz sau VKVideo pentru acest episod[/COLOR]')
        return False

    # Afisam fiecare gazda disponibila, nu pornim automat prima sursa.
    # Astfel utilizatorul poate alege Voe.sx sau Vidmoly.biz pentru acelasi
    # episod atunci cand pagina le contine pe amandoua.
    labels = []
    for embed, host_name in embeds:
        label = re.sub(r'<[^>]+>', '', host_name or '').strip()
        labels.append(label or 'Server video')

    dialog = xbmcgui.Dialog()
    index = dialog.select('[COLOR white][B]SELECTEAZA -->[/B][/COLOR]', labels)
    if index < 0:
        return False

    embed, host_name = embeds[index]
    clean_title = veziaici_clean_text(title or host_name or 'Las Fierbinti')

    # Pentru Voe/VidMoly incercam mai intai resolverul direct. Astfel Kodi
    # primeste streamul final si nu mai deschide pagina intermediara SMR.
    # Pentru VK extragem HLS-ul chiar in momentul redarii, deoarece linkul
    # video_ext.php este legat de IP si expira.
    stream = ''
    try:
        if veziaici_is_vk(embed):
            stream = veziaici_vk_hls(embed)
        else:
            resolved = resolveurl.resolve(embed)
            if resolved and not resolved.startswith('plugin://'):
                stream = stream_url_with_headers(resolved, embed)
    except Exception as e:
        try:
            xbmc.log(
                '[RomyLive] Redare directa esuata pentru %s: %s' %
                (host_name, e),
                level=xbmc.LOGWARNING
            )
        except:
            pass

    if stream:
        try:
            list_item = xbmcgui.ListItem(clean_title, path=stream)
            list_item.setProperty('IsPlayable', 'true')
            list_item.setArt({'icon': thumb_las, 'thumb': thumb_las})
            list_item.setInfo(
                type='video',
                infoLabels={'Title': clean_title, 'Studio': host_name}
            )
            list_item.setContentLookup(False)
            if '.m3u8' in stream.split('|')[0].lower():
                list_item.setMimeType('application/vnd.apple.mpegurl')
            # Inchidem cererea de director inainte de a porni playerul.
            # Fara acest pas, la Stop Kodi poate reintra in mode=1 si poate
            # afisa selectorul inca o data.
            xbmcplugin.endOfDirectory(addon_handle)
            xbmc.Player().play(item=stream, listitem=list_item)
            return True
        except Exception as e:
            try:
                xbmc.log(
                    '[RomyLive] Player direct a esuat pentru %s: %s' %
                    (host_name, e),
                    level=xbmc.LOGWARNING
                )
            except:
                pass

    # Fallback pentru resolver-ele instalate separat sau pentru un site care
    # schimba formatul embedului.
    play_url = (
        'plugin://plugin.video.smr_link_tester/?mode=play_link'
        '&link=%s&switch=play$nome=%s'
    ) % (
        urllib.quote_plus(embed),
        urllib.quote_plus(host_name)
    )

    try:
        list_item = xbmcgui.ListItem(clean_title)
        list_item.setProperty('IsPlayable', 'true')
        list_item.setInfo(
            type='video',
            infoLabels={'Title': clean_title, 'Studio': host_name}
        )
        xbmcplugin.endOfDirectory(addon_handle)
        xbmc.Player().play(item=play_url, listitem=list_item)
    except Exception as e:
        # Compatibilitate cu build-uri Kodi care nu accepta plugin:// in
        # xbmc.Player().play().
        try:
            xbmc.log(
                '[RomyLive] Player().play a esuat pentru %s: %s; folosesc PlayMedia' %
                (host_name, e),
                level=xbmc.LOGWARNING
            )
        except:
            pass
        xbmc.executebuiltin('PlayMedia(%s)' % play_url)
    return True


def getData(url,fanart,pesquisa=False):
    if url == url_sky_italia:
        sky_italia_list()
        return
    if url == url_myradioonline:
        myradioonline_list()
        return
    if url.startswith(url_veziaici_chefi):
        veziaici_chefi_list()
        return
    if url.startswith('https://veziaici.net/') and '/category/' not in url and re.search(r'chefi|cutite', url, re.IGNORECASE):
        veziaici_chefi_episode(url)
        return
    if url.startswith(url_veziaici_camatarii):
        veziaici_camatarii_list()
        return
    if url.startswith('https://veziaici.net/') and '/category/' not in url and re.search(r'camatarii', url, re.IGNORECASE):
        veziaici_camatarii_episode(url)
        return
    if url.startswith(url_veziaici_las):
        veziaici_las_list()
        return
    if url.startswith('https://veziaici.net/') and '/category/' not in url and re.search(r'las-fierbinti', url, re.IGNORECASE):
        return veziaici_las_episode(url)
    if url.startswith(url_veziaici_masterchef):
        veziaici_masterchef_list()
        return
    if url.startswith(url_veziaici_insula):
        veziaici_insula_list()
        return
    if url.startswith(url_veziaici_vocea):
        veziaici_vocea_list()
        return
    if url.startswith(url_veziaici_jocul):
        veziaici_jocul_list()
        return
    if url.startswith(url_veziaici_asia):
        veziaici_asia_list()
        return
    if url.startswith(url_veziaici_furnicutele):
        veziaici_furnicutele_list()
        return
    if url.startswith(url_vidzstore_filme):
        vidzstore_filme(url, fanart)
        return
    if url.startswith(url_sitefilme):
        sitefilme_filme(url, fanart)
        return
    if url.startswith(url_paradisehill):
        paradisehill_filme(url, fanart)
        return
    if url.startswith(url_filmebunehd):
        filmebunehd_router(url, fanart)
        return
    if url == url_dinbox_tv:
        dinbox_list_categories()
        return
    if url == url_vavoo_main:
        vavoo_list_countries()
        return
    if url == url_sportsonline_prog:
        sportsonline_list_events()
        return
    if url == url_rojadirecta_main:
        rojadirecta_list_events()
        return
    if url == url_streami_main:
        streami_list_events()
        return
    if url == url_daddylive_main:
        daddylive_list_channels()
        return
    if url == url_portalultautv:
        portalultautv_list_categories()
        return
    if url.startswith(url_portalultautv):
        portalultautv_filme(url, fanart)
        return
    adult = xbmcaddon.Addon().getSetting("adult")
    adult2 = xbmcaddon.Addon().getSetting("adult2")
    uhdtv = addon.getSetting('uhdtv')
    fhdtv = addon.getSetting('fhdtv')
    hdtv = addon.getSetting('hdtv')
    sdtv = addon.getSetting('sdtv')
    filtrar = addon.getSetting('filtrar')
    data = resolve_data(url)
    if url == url_tv_principal and 'rdslive://list' not in data:
        data = '''
<item>
<title>[COLOR aqua][B]Canale TV[/B][/COLOR] [COLOR gold][B]Romania 2[/B][/COLOR]</title>
<externallink>rdslive://list</externallink>
<thumbnail>''' + _ROMY_LOCAL_ICON + '''</thumbnail>
<fanart>''' + _ROMY_LOCAL_FANART + '''</fanart>
<info>Canale TV romanesti de pe rdslive.tv, organizate pe categorii (Filme, Sport, Stiri, etc.)</info>
</item>

''' + data
    if url == url_tv_principal and 'tvzone://list' not in data:
        data = '''
<item>
<title>[COLOR aqua][B]Canale TV[/B][/COLOR] [COLOR gold][B]Romania[/B][/COLOR]</title>
<externallink>tvzone://list</externallink>
<thumbnail>''' + _ROMY_LOCAL_ICON + '''</thumbnail>
<fanart>''' + _ROMY_LOCAL_FANART + '''</fanart>
<info>Toate canalele TV romanesti de pe tvzonehd.com</info>
</item>

''' + data
    if url == url_tv_principal and url_vavoo_main not in data:
        data = '''
<item>
<title>[COLOR white][B]VaVoo[/B][/COLOR][COLOR white][B]TV[/B][/COLOR]</title>
<externallink>https://vavoo.to/</externallink>
<thumbnail>https://vavoo.to/favicon.ico</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
<info>VaVooTV live channels by country</info>
</item>

''' + data
    if url == url_filme_principal and '<title>Filme Online</title>' not in data:
        data += '''
<item>
<title>[COLOR aqua][B]Filme[/B][/COLOR] [COLOR violet][B]Online[/B][/COLOR]</title>
<externallink>https://sitefilme.com/</externallink>
<thumbnail>https://documentarys.do.am/2026/filme/filme.png</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR aqua][B]Filme[/B][/COLOR] [COLOR violet][B]Online 2[/B][/COLOR]</title>
<externallink>https://portalultautv.info/</externallink>
<thumbnail>https://documentarys.do.am/2026/Principal/romylive.png</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR aqua][B]Filme[/B][/COLOR] [COLOR violet][B]Online 3[/B][/COLOR]</title>
<externallink>https://filmebunehd1.com</externallink>
<thumbnail>https://documentarys.do.am/2026/Principal/romylive.png</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

'''
    if url == url_tv_adult and 'en.paradisehill.cc/categories' not in data:
        data += '''
<item>
<title>[COLOR aqua][B]Filme[/B][/COLOR] [COLOR violet][B]XXX 2[/B][/COLOR]</title>
<externallink>https://en.paradisehill.cc/categories/</externallink>
<thumbnail>https://documentarys.do.am/2026/TV/logo/big-logo.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR aqua][B]Filme[/B][/COLOR] [COLOR violet][B]XXX 3[/B][/COLOR]</title>
<externallink>https://portalultautv.info/category/filme-erotice-online/</externallink>
<thumbnail>https://documentarys.do.am/2026/TV/logo/xxx.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

'''
    if url == url_tv_sports and url_sportsonline_prog not in data:
        data = '''
<item>
<title>[COLOR white][B]DaddyLive[/B][/COLOR] [COLOR white][B]24/7 Channels[/B][/COLOR]</title>
<externallink>https://dlhd.pk/24-7-channels.php</externallink>
<thumbnail>https://documentarys.do.am/2026/TV/logo/daddy.jpg</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

<item>
<title>[COLOR white][B]Sports[/B][/COLOR][COLOR white][B]Online.Vc[/B][/COLOR]</title>
<externallink>https://sportsonline.vc/prog.txt</externallink>
<thumbnail>https://documentarys.do.am/2026/TV/logo/sports.webp</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

''' + data
    elif url == url_tv_sports:
        data = '''
<item>
<title>[COLOR gold][B]DaddyLive 24/7 Channels[/B][/COLOR]</title>
<externallink>https://dlhd.pk/24-7-channels.php</externallink>
<thumbnail>https://documentarys.do.am/2026/TV/sport.png</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
</item>

''' + data
    if url == url_tv_sports:
        data = re.sub(r'(?is)\s*<item>.*?<externallink>https?://streami\.top/?</externallink>.*?</item>', '', data)
        data = re.sub(r'(?is)\s*<item>.*?<externallink>http://www\.rojadirecta\.eu/?</externallink>.*?</item>', '', data)
    if url == url_filme_principal:
        data = re.sub(r'(?is)\s*<item>.*?<externallink>https://premieres\.vidzstore\.com/upload/2026/?</externallink>.*?</item>', '', data)
        data = re.sub(r'(?is)(<title>\[COLOR aqua\]\[B\]Filme\[/B\]\[/COLOR\] \[COLOR violet\]\[B\]Online\[/B\]\[/COLOR\]) \[COLOR aqua\]\[B\]2\[/B\]\[/COLOR\](</title>)', r'\1\2', data)
    if 'worlds/italia.txt' in url and url_sky_italia not in data:
        data = '''
<item>
<title>[COLOR aqua][B]SKY[/COLOR] [COLOR violet]LIVE[/COLOR] [COLOR aqua]Italia[/B][/COLOR]</title>
<externallink>sky_italia://list</externallink>
<thumbnail>https://pixel.disco.nowtv.it/logo/skychb_skyuno_lightnow/LOGO_CHANNEL_DARK/4000?language=it-IT&proposition=NOWOTT</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
<info>Canale SKY Italia: TG24, Sky Uno, Atlantic, Serie, Crime si altele</info>
</item>

''' + data
    if 'radio/radiolive.txt' in url and 'myradioonline://list' not in data:
        data = '''
<item>
<title>[COLOR aqua][B]MyRadio[/COLOR][COLOR violet]Online.ro[/B][/COLOR]</title>
<externallink>myradioonline://list</externallink>
<thumbnail>https://myradioonline.ro/public/img/logo/myradioonline_ro.png</thumbnail>
<fanart>https://documentarys.do.am/2026/Principal/romylive.png</fanart>
<info>Radio online romanesc: Manele, Petrecere, Generaliste, Dance, Stiri si altele</info>
</item>

''' + data
    if 'seriale/principal.txt' in url and url_veziaici_asia not in data:
        asia_inject = '''
<item>
<title>[COLOR white][B]Asia Express[/B][/COLOR]</title>
<externallink>''' + url_veziaici_asia + '''</externallink>
<thumbnail>''' + thumb_asia + '''</thumbnail>
<fanart>''' + fanart_asia + '''</fanart>
<info>Asia Express Sezonul 9: Drumul Matasii - episoade online de pe veziaici.net</info>
</item>

'''
        masterchef_inject = '''
<item>
<title>[COLOR white][B]MasterChef[/B][/COLOR]</title>
<externallink>''' + url_veziaici_masterchef + '''</externallink>
<thumbnail>''' + thumb_masterchef + '''</thumbnail>
<fanart>''' + fanart_masterchef + '''</fanart>
<info>MasterChef Sezonul 11 - episoade online in reluare de pe veziaici.net</info>
</item>

'''
        insula_inject = '''
<item>
<title>[COLOR white][B]Insula Iubirii[/B][/COLOR]</title>
<externallink>''' + url_veziaici_insula + '''</externallink>
<thumbnail>''' + thumb_insula + '''</thumbnail>
<fanart>''' + fanart_insula + '''</fanart>
<info>Insula Iubirii Sezonul 10 - episoade online in reluare de pe veziaici.net</info>
</item>

'''
        vocea_inject = '''
<item>
<title>[COLOR white][B]Vocea Romaniei[/B][/COLOR]</title>
<externallink>''' + url_veziaici_vocea + '''</externallink>
<thumbnail>''' + thumb_vocea + '''</thumbnail>
<fanart>''' + fanart_vocea + '''</fanart>
<info>Vocea Romaniei Sezonul 14 - episoade online in reluare de pe veziaici.net</info>
</item>

'''
        jocul_inject = '''
<item>
<title>[COLOR white][B]Jocul Cuvintelor[/B][/COLOR]</title>
<externallink>''' + url_veziaici_jocul + '''</externallink>
<thumbnail>''' + thumb_jocul + '''</thumbnail>
<fanart>''' + fanart_jocul + '''</fanart>
<info>Jocul Cuvintelor Sezonul 7 - episoade online in reluare de pe veziaici.net</info>
</item>

'''
        data = asia_inject + masterchef_inject + insula_inject + vocea_inject + jocul_inject + data
    if 'seriale/principal.txt' in url and url_veziaici_las not in data:
        las_inject = '''
<item>
<title>[COLOR white][B]Las Fierbinti[/B][/COLOR]</title>
<externallink>''' + url_veziaici_las + '''</externallink>
<thumbnail>''' + thumb_las + '''</thumbnail>
<fanart>''' + fanart_las + '''</fanart>
<info>Las Fierbinti - toate sezoanele si episoadele integrale de pe veziaici.net</info>
</item>

'''
        data = las_inject + data
    if 'seriale/principal.txt' in url and url_veziaici_camatarii not in data:
        camatarii_inject = '''
<item>
<title>[COLOR white][B]Camatarii[/B][/COLOR]</title>
<externallink>''' + url_veziaici_camatarii + '''</externallink>
<thumbnail>''' + thumb_camatarii + '''</thumbnail>
<fanart>''' + fanart_camatarii + '''</fanart>
<info>Camatarii serial documentar online in reluare din 2026 - veziaici.net</info>
</item>

'''
        camat_voyo_marker = 'camatarii.txt'
        if camat_voyo_marker in data:
            try:
                insert_pos = data.index('</item>', data.index(camat_voyo_marker)) + len('</item>')
                data = data[:insert_pos] + '\n' + camatarii_inject + data[insert_pos:]
            except:
                data = data + camatarii_inject
        else:
            data = data + camatarii_inject
    if isinstance(data, (int, str, list)):
        channels = re.compile('<channels>(.+?)</channels>',re.MULTILINE|re.DOTALL).findall(data)
        channel = re.compile('<channel>(.*?)</channel>',re.MULTILINE|re.DOTALL).findall(data)
        item = re.compile('<item>(.*?)</item>',re.MULTILINE|re.DOTALL).findall(data)
        if len(channels) >0:
            for channel in channel:
                linkedUrl=''
                lcount=0
                try:
                    linkedUrl = re.compile('<externallink>(.*?)</externallink>').findall(channel)[0]
                    lcount=len(re.compile('<externallink>(.*?)</externallink>').findall(channel))
                except: pass
                
                try:
                    linkedUrl = base64.b32decode(linkedUrl).decode('utf-8')
                except:
                    pass
                    

                name = re.compile('<name>(.*?)</name>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                try:
                    thumbnail = re.compile('<thumbnail>(.*?)</thumbnail>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                except:
                    thumbnail = ''
                try:
                    fanart1 = re.compile('<fanart>(.*?)</fanart>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                except:
                    fanart1 = ''

                if not fanart1:
                    if __addon__.getSetting('use_thumb') == "true":
                        fanArt = thumbnail
                    else:
                        fanArt = fanart
                else:
                    fanArt = fanart1
                if fanArt == None:
                    #raise
                    fanArt = ''

                try:
                    desc = re.compile('<info>(.*?)</info>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if desc == None:
                        #raise
                        desc = ''
                except:
                    desc = ''

                try:
                    genre = re.compile('<genre>(.*?)</genre>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if genre == None:
                        #raise
                        genre = ''
                except:
                    genre = ''

                try:
                    date = re.compile('<date>(.*?)</date>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if date == None:
                        #raise
                        date = ''
                except:
                    date = ''

                try:
                    credits = re.compile('<credits>(.*?)</credits>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if credits == None:
                        #raise
                        credits = ''
                except:
                    credits = ''

                try:
                    year = re.compile('<year>(.*?)</year>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if year == None:
                        #raise
                        year = ''
                except:
                    year = ''

                try:
                    director = re.compile('<director>(.*?)</director>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if director == None:
                        #raise
                        director = ''
                except:
                    director = ''

                try:
                    writer = re.compile('<writer>(.*?)</writer>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if writer == None:
                        #raise
                        writer = ''
                except:
                    writer = ''

                try:
                    duration = re.compile('<duration>(.*?)</duration>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if duration == None:
                        #raise
                        duration = ''
                except:
                    duration = ''

                try:
                    premiered = re.compile('<premiered>(.*?)</premiered>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if premiered == None:
                        #raise
                        premiered = ''
                except:
                    premiered = ''

                try:
                    studio = re.compile('<studio>(.*?)</studio>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if studio == None:
                        #raise
                        studio = ''
                except:
                    studio = ''

                try:
                    rate = re.compile('<rate>(.*?)</rate>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if rate == None:
                        #raise
                        rate = ''
                except:
                    rate = ''

                try:
                    originaltitle = re.compile('<originaltitle>(.*?)</originaltitle>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if originaltitle == None:
                        #raise
                        originaltitle = ''
                except:
                    originaltitle = ''

                try:
                    country = re.compile('<country>(.*?)</country>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if country == None:
                        #raise
                        country = ''
                except:
                    country = ''

                try:
                    rating = re.compile('<country>(.*?)</country>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if rating == None:
                        #raise
                        rating = ''
                except:
                    rating = ''

                try:
                    userrating = re.compile('<userrating>(.*?)</userrating>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if userrating == None:
                        #raise
                        userrating = ''
                except:
                    userrating = ''

                try:
                    votes = re.compile('<votes>(.*?)</votes>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if votes == None:
                        #raise
                        votes = ''
                except:
                    votes = ''

                try:
                    aired = re.compile('<aired>(.*?)</aired>',re.MULTILINE|re.DOTALL).findall(channel)[0]
                    if aired == None:
                        #raise
                        aired = ''
                except:
                    aired = ''

                try:
                    if linkedUrl=='':
                        #addDir(name.encode('utf-8', 'ignore'),url.encode('utf-8'),2,thumbnail,fanArt,desc,genre,date,credits,True)
                        #addDir(name.encode('utf-8', 'ignore'),url.encode('utf-8'),2,thumbnail,fanArt,desc,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired)
                        addDir(name.encode('utf-8', 'ignore'),'',1,thumbnail,fanArt,desc,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired)
                    else:
                        #print linkedUrl
                        #addDir(name.encode('utf-8'),linkedUrl.encode('utf-8'),1,thumbnail,fanArt,desc,genre,date,None,'source')
                        if adult == 'false' and re.search("ADULTOS",name,re.IGNORECASE) and name.find('(+18)') >=0:
                            pass
                        else:
                            addDir(name.encode('utf-8', 'ignore'),linkedUrl,1,thumbnail,fanArt,desc,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired)
                except:
                    notify('[COLOR red]Erro ao Carregar os dados![/COLOR]')
        elif re.search("#EXTM3U",data) or re.search("#EXTINF",data):
            content = data.rstrip()
            match = re.compile(r'#EXTINF:(.+?),(.*?)[\n\r]+([^\r\n]+)').findall(content)
            for other,channel_name,stream_url in match:
                if 'tvg-logo' in other:
                    thumbnail = re_me(other,'tvg-logo=[\'"](.*?)[\'"]')
                    if thumbnail:
                        if thumbnail.startswith('http'):
                            thumbnail = thumbnail
                        #elif not addon.getSetting('logo-folderPath') == "":
                        #    logo_url = addon.getSetting('logo-folderPath')
                        #    thumbnail = logo_url + thumbnail

                        else:
                            thumbnail = ''
                    else:
                        thumbnail = ''
                else:
                    thumbnail = ''

                if 'group-title' in other:
                    cat = re_me(other,'group-title=[\'"](.*?)[\'"]')
                else:
                    cat = ''

                if 'tvg-id' in other:
                    epgid = re_me(other,'tvg-id=[\'"](.*?)[\'"]')
                else:
                    epgid = ''
                m3u_desc = _xmltv_merge_description('', channel_name, epgid)

                try:
                    #resolver_final = resolver(stream_url, channel_name, thumbnail)
                    if uhdtv == 'false' and re.search("4K",channel_name):
                        pass
                    elif fhdtv == 'false' and re.search("FHD",channel_name):
                        pass
                    elif hdtv == 'false' and re.search("HD",channel_name) and not re.search("FHD",channel_name):
                        pass
                    elif sdtv == 'false' and re.search("SD",channel_name):
                        pass
                    elif sdtv == 'false' and not re.search("SD",channel_name) and not re.search("HD",channel_name) and not re.search("4K",channel_name):
                        pass
                    #Futebol
                    elif int(filtrar) == 1 and re.search("Praia",channel_name,re.IGNORECASE):
                        pass
                    elif int(filtrar) == 1 and not re.search("SPORTV",channel_name,re.IGNORECASE) and not re.search("DAZN",channel_name,re.IGNORECASE) and not re.search("ESPN Brasil",channel_name,re.IGNORECASE) and not re.search("PREMIERE",channel_name,re.IGNORECASE) and not re.search("COPA",channel_name,re.IGNORECASE):
                        pass
                    #Esportes
                    elif int(filtrar) == 2 and re.search("Praia",channel_name,re.IGNORECASE):
                        pass
                    elif int(filtrar) == 2 and not re.search("Band Sports",channel_name,re.IGNORECASE) and not re.search("Combate",channel_name,re.IGNORECASE) and not re.search("Fox Sports",channel_name,re.IGNORECASE) and not re.search("SPORTV",channel_name,re.IGNORECASE) and not re.search("DAZN",channel_name,re.IGNORECASE) and not re.search("ESPN",channel_name,re.IGNORECASE) and not re.search("PREMIERE",channel_name,re.IGNORECASE) and not re.search("COPA",channel_name,re.IGNORECASE):
                        pass
                    #Filmes e Series
                    elif int(filtrar) == 3 and re.search("Sports",channel_name,re.IGNORECASE):
                        pass
                    elif int(filtrar) == 3 and re.search("XY Max",channel_name,re.IGNORECASE):
                        pass
                    elif int(filtrar) == 3 and not re.search("AMC",channel_name,re.IGNORECASE) and not re.search("Canal Brasil",channel_name,re.IGNORECASE) and not re.search("Cinemax",channel_name,re.IGNORECASE) and not re.search("HBO",channel_name,re.IGNORECASE) and not re.search("Max",channel_name,re.IGNORECASE) and not re.search("Megapix",channel_name,re.IGNORECASE) and not re.search("Paramount",channel_name,re.IGNORECASE) and not re.search("SPACE",channel_name,re.IGNORECASE) and not re.search("TCM",channel_name,re.IGNORECASE) and not re.search("Telecine Action",channel_name,re.IGNORECASE) and not re.search("TC Action",channel_name,re.IGNORECASE) and not re.search("Telecine Cult",channel_name,re.IGNORECASE) and not re.search("TC Cult",channel_name,re.IGNORECASE) and not re.search("TC Cult",channel_name,re.IGNORECASE) and not re.search("Telecine Fun",channel_name,re.IGNORECASE) and not re.search("TC Fun",channel_name,re.IGNORECASE) and not re.search("Telecine Pipoca",channel_name,re.IGNORECASE) and not re.search("TC Pipoca",channel_name,re.IGNORECASE) and not re.search("Telecine Premium",channel_name,re.IGNORECASE) and not re.search("TC Premium",channel_name,re.IGNORECASE) and not re.search("Telecine Touch",channel_name,re.IGNORECASE) and not re.search("TC Touch",channel_name,re.IGNORECASE) and not re.search("TNT",channel_name,re.IGNORECASE) and not re.search("A&E",channel_name,re.IGNORECASE) and not re.search("AXN",channel_name,re.IGNORECASE) and not re.search("AXN",channel_name,re.IGNORECASE) and not re.search("FOX",channel_name,re.IGNORECASE) and not re.search("FX",channel_name,re.IGNORECASE) and not re.search("SONY",channel_name,re.IGNORECASE) and not re.search("Studio Universal",channel_name,re.IGNORECASE) and not re.search("SyFy",channel_name,re.IGNORECASE) and not re.search("Universal Channel",channel_name,re.IGNORECASE) and not re.search("Universal TV",channel_name,re.IGNORECASE) and not re.search("Warner",channel_name,re.IGNORECASE):
                        pass
                    #Infantil
                    elif int(filtrar) == 4 and re.search("FM",channel_name,re.IGNORECASE):
                        pass
                    elif int(filtrar) == 4 and not re.search("Baby TV",channel_name,re.IGNORECASE) and not re.search("BOOMERANG",channel_name,re.IGNORECASE) and not re.search("CARTOON NETWORK",channel_name,re.IGNORECASE) and not re.search("DISCOVERY KIDS",channel_name,re.IGNORECASE) and not re.search("DISNEY",channel_name,re.IGNORECASE) and not re.search("GLOOB",channel_name,re.IGNORECASE) and not re.search("NAT GEO KIDS",channel_name,re.IGNORECASE) and not re.search("NICKELODEON",channel_name,re.IGNORECASE) and not re.search("NICK JR",channel_name,re.IGNORECASE) and not re.search("PLAYKIDS",channel_name,re.IGNORECASE) and not re.search("TOONCAST",channel_name,re.IGNORECASE) and not re.search("ZOOMOO",channel_name,re.IGNORECASE):
                        pass
                    #Documentario
                    elif int(filtrar) == 5  and re.search("Kids",channel_name,re.IGNORECASE):
                        pass
                    elif int(filtrar) == 5 and not re.search("Discovery",channel_name,re.IGNORECASE) and not re.search("H2 HD",channel_name,re.IGNORECASE) and not re.search("H2 SD",channel_name,re.IGNORECASE) and not re.search("H2 FHD",channel_name,re.IGNORECASE) and not re.search("History",channel_name,re.IGNORECASE) and not re.search("Nat Geo Wild",channel_name,re.IGNORECASE) and not re.search("National Geographic",channel_name,re.IGNORECASE):
                        pass
                    #Abertos
                    elif int(filtrar) == 6 and re.search("Brasileirinhas",channel_name,re.IGNORECASE):
                        pass
                    elif int(filtrar) == 6 and re.search("News",channel_name,re.IGNORECASE) or int(filtrar) == 6 and re.search("Sat",channel_name,re.IGNORECASE) or int(filtrar) == 6 and re.search("FM",channel_name,re.IGNORECASE):
                        pass
                    elif int(filtrar) == 6 and not re.search("Globo",channel_name,re.IGNORECASE) and not re.search("RECORD",channel_name,re.IGNORECASE) and not re.search("RedeTV",channel_name,re.IGNORECASE) and not re.search("Rede Vida",channel_name,re.IGNORECASE) and not re.search("SBT",channel_name,re.IGNORECASE) and not re.search("TV Brasil",channel_name,re.IGNORECASE) and not re.search("TV Cultura",channel_name,re.IGNORECASE) and not re.search("TV Diario",channel_name,re.IGNORECASE) and not re.search("BAND",channel_name,re.IGNORECASE):
                        pass
                    #Reality show
                    elif int(filtrar) == 7 and not re.search("BBB",channel_name,re.IGNORECASE) and not re.search("Big Brother Brasil",channel_name,re.IGNORECASE) and not re.search("A Fazenda",channel_name,re.IGNORECASE):
                        pass
                    #Noticias
                    elif int(filtrar) == 8 and re.search("FM",channel_name,re.IGNORECASE):
                        pass
                    elif int(filtrar) == 8 and not re.search("CNN",channel_name,re.IGNORECASE) and not re.search("NEWS",channel_name,re.IGNORECASE):
                        pass
                    elif adult2 == 'false' and re.search("Adult",cat,re.IGNORECASE) or adult2 == 'false' and re.search("ADULT",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Blue Hustler",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("PlayBoy",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Redlight",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Sextreme",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("SexyHot",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Venus",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("AST TV",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("ASTTV",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("AST.TV",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("BRAZZERS",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("CANDY",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("CENTOXCENTO",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("DORCEL",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("EROXX",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("PASSION",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("PENTHOUSE",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("PINK-O",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("PINK O",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("PRIVATE",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("RUSNOCH",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("SCT",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("SEXT6SENSO",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("SHALUN TV",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("VIVID RED",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Porn",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("XY Plus",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("XY Mix",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("XY Mad",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("XXL",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Desire",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Bizarre",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Sexy HOT",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Reality Kings",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Prive TV",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Hustler TV",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Extasy",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Evil Angel",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Erox",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("DUSK",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Brazzers",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Brasileirinhas",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Pink Erotic",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Passion",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Passie",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Meiden Van Holland Hard",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Sext & Senso",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Super One",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Vivid TV",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Hustler HD",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("SCT",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Sex Ation",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Hot TV",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Hot HD",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("MILF",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("ANAL",channel_name,re.IGNORECASE) and not re.search("CANAL",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("PUSSY",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("ROCCO",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("BABES",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("BABIE",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("XY Max",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("TUSHY",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("BLACKED",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("FAKE TAXI",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("XXX",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("18",channel_name,re.IGNORECASE) or adult2 == 'false' and re.search("Porno",channel_name,re.IGNORECASE):
                        pass
                    elif re.search("Adult",cat,re.IGNORECASE) or re.search("ADULT",channel_name,re.IGNORECASE) or re.search("Blue Hustler",channel_name,re.IGNORECASE) or re.search("PlayBoy",channel_name,re.IGNORECASE) or re.search("Redlight",channel_name,re.IGNORECASE) or re.search("Sextreme",channel_name,re.IGNORECASE) or re.search("SexyHot",channel_name,re.IGNORECASE) or re.search("Venus",channel_name,re.IGNORECASE) or re.search("AST TV",channel_name,re.IGNORECASE) or re.search("ASTTV",channel_name,re.IGNORECASE) or re.search("AST.TV",channel_name,re.IGNORECASE) or re.search("BRAZZERS",channel_name,re.IGNORECASE) or re.search("CANDY",channel_name,re.IGNORECASE) or re.search("CENTOXCENTO",channel_name,re.IGNORECASE) or re.search("DORCEL",channel_name,re.IGNORECASE) or re.search("EROXX",channel_name,re.IGNORECASE) or re.search("PASSION",channel_name,re.IGNORECASE) or re.search("PENTHOUSE",channel_name,re.IGNORECASE) or re.search("PINK-O",channel_name,re.IGNORECASE) or re.search("PINK O",channel_name,re.IGNORECASE) or re.search("PRIVATE",channel_name,re.IGNORECASE) or re.search("RUSNOCH",channel_name,re.IGNORECASE) or re.search("SCT",channel_name,re.IGNORECASE) or re.search("SEXT6SENSO",channel_name,re.IGNORECASE) or re.search("SHALUN TV",channel_name,re.IGNORECASE) or re.search("VIVID RED",channel_name,re.IGNORECASE) or re.search("Porn",channel_name,re.IGNORECASE) or re.search("XY Plus",channel_name,re.IGNORECASE) or re.search("XY Mix",channel_name,re.IGNORECASE) or re.search("XY Mad",channel_name,re.IGNORECASE) or re.search("XXL",channel_name,re.IGNORECASE) or re.search("Desire",channel_name,re.IGNORECASE) or re.search("Bizarre",channel_name,re.IGNORECASE) or re.search("Sexy HOT",channel_name,re.IGNORECASE) or re.search("Reality Kings",channel_name,re.IGNORECASE) or re.search("Prive TV",channel_name,re.IGNORECASE) or re.search("Hustler TV",channel_name,re.IGNORECASE) or re.search("Extasy",channel_name,re.IGNORECASE) or re.search("Evil Angel",channel_name,re.IGNORECASE) or re.search("Erox",channel_name,re.IGNORECASE) or re.search("DUSK",channel_name,re.IGNORECASE) or re.search("Brazzers",channel_name,re.IGNORECASE) or re.search("Brasileirinhas",channel_name,re.IGNORECASE) or re.search("Pink Erotic",channel_name,re.IGNORECASE) or re.search("Passion",channel_name,re.IGNORECASE) or re.search("Passie",channel_name,re.IGNORECASE) or re.search("Meiden Van Holland Hard",channel_name,re.IGNORECASE) or re.search("Sext & Senso",channel_name,re.IGNORECASE) or re.search("Super One",channel_name,re.IGNORECASE) or re.search("Vivid TV",channel_name,re.IGNORECASE) or re.search("Hustler HD",channel_name,re.IGNORECASE) or re.search("SCT",channel_name,re.IGNORECASE) or re.search("Sex Ation",channel_name,re.IGNORECASE) or re.search("Hot TV",channel_name,re.IGNORECASE) or re.search("Hot HD",channel_name,re.IGNORECASE) or re.search("MILF",channel_name,re.IGNORECASE) or re.search("ANAL",channel_name,re.IGNORECASE) and not re.search("CANAL",channel_name,re.IGNORECASE) or re.search("PUSSY",channel_name,re.IGNORECASE) or re.search("ROCCO",channel_name,re.IGNORECASE) or re.search("BABES",channel_name,re.IGNORECASE) or re.search("BABIE",channel_name,re.IGNORECASE) or re.search("XY Max",channel_name,re.IGNORECASE) or re.search("TUSHY",channel_name,re.IGNORECASE) or re.search("FAKE TAXI",channel_name,re.IGNORECASE) or re.search("BLACKED",channel_name,re.IGNORECASE) or re.search("XXX",channel_name,re.IGNORECASE) or re.search("18",channel_name,re.IGNORECASE) or re.search("Porno",channel_name,re.IGNORECASE):
                        addDir2(channel_name.encode('utf-8', 'ignore'),stream_url,10,'',thumbnail,'',m3u_desc,'','','','','','','','','','','','','','','','',False)
                    elif '.mpd' in stream_url.lower():
                        addDir2(channel_name.encode('utf-8', 'ignore'),stream_url,20,'',thumbnail,'',m3u_desc,'','','','','','','','','','','','','','','','',False)
                    else:
                        #addLink(name1.encode('utf-8', 'ignore'),resolver_final.encode('utf-8'),'',cleaname,thumbnail,'',desc1)
                        addDir2(channel_name.encode('utf-8', 'ignore'),stream_url,18,'',thumbnail,'',m3u_desc,'','','','','','','','','','','','','','','','',False)
                except:
                    #notify('[COLOR red]Erro ao Carregar os dados![/COLOR]')
                    pass
        else:
            #getItems(soup('item'),fanart)
            getItems(item,fanart,pesquisa)
    else:
        #parse_m3u(soup)
        notify('[COLOR red]Erro ao Carregar os dados![/COLOR]')
    if '<SetContent>' in data:
        try:
            content=re.findall('<SetContent>(.*?)<',data)[0]
            xbmcplugin.setContent(addon_handle, str(content))
        except:
            xbmcplugin.setContent(addon_handle, 'movies')
    else:
        xbmcplugin.setContent(addon_handle, 'movies')

    if '<SetViewMode>' in data:
        try:
            viewmode=re.findall('<SetViewMode>(.*?)<',data)[0]
            pass
            #print 'done setview',viewmode
        except: pass


def _xmltv_clean_label(label):
    try:
        if isinstance(label, bytes):
            label = label.decode('utf-8', 'ignore')
    except Exception:
        pass
    try:
        label = html_unescape(label)
    except Exception:
        pass
    label = re.sub(r'\[/?(?:COLOR|B|I|U)[^\]]*\]', '', label, flags=re.IGNORECASE)
    label = re.sub(r'<[^>]+>', ' ', label)
    return re.sub(r'\s+', ' ', label).strip()


def _xmltv_parse_time(value):
    try:
        m = re.match(r'(\d{14})(?:\s*([+-])(\d{2})(\d{2}))?', value or '')
        if not m:
            return None
        dt = datetime.strptime(m.group(1), '%Y%m%d%H%M%S')
        if m.group(2):
            sign = 1 if m.group(2) == '+' else -1
            offset_seconds = (int(m.group(3)) * 3600) + (int(m.group(4)) * 60)
            dt = datetime.fromtimestamp(__import__('calendar').timegm(dt.timetuple()) - (sign * offset_seconds))
        return dt
    except Exception:
        return None


def _xmltv_load_epg():
    global _xmltv_epg_cache
    if _xmltv_epg_cache is not None:
        return _xmltv_epg_cache
    epg = {'name_to_id': {}, 'programmes': {}}
    try:
        if addon.getSetting('xmltv_epg_enabled') != 'true':
            _xmltv_epg_cache = epg
            return epg
    except Exception:
        _xmltv_epg_cache = epg
        return epg
    try:
        url = addon.getSetting('xmltv_epg_url') or xmltv_epg_url
        if not url:
            _xmltv_epg_cache = epg
            return epg
        if re.match(r'^https?://', url, re.IGNORECASE):
            r = requests.get(url, headers={'User-Agent': useragent}, timeout=30, verify=False)
            if r is None or r.status_code != 200 or not r.content:
                _xmltv_epg_cache = epg
                return epg
            content = r.content
        else:
            with open(kodi_translate_path(url), 'rb') as f:
                content = f.read()
        try:
            import gzip
            from io import BytesIO
            if url.lower().endswith('.gz') or content[:2] == b'\x1f\x8b':
                content = gzip.GzipFile(fileobj=BytesIO(content)).read()
        except Exception:
            pass
        text = content.decode('utf-8', 'ignore')
        channel_map = {}
        for cm in re.finditer(r'<channel\s+id=["\']([^"\']+)["\'][^>]*>(.*?)</channel>', text, re.DOTALL | re.IGNORECASE):
            cid = html_unescape(cm.group(1)).strip()
            channel_map.setdefault(_dl_norm(cid), cid)
            block = cm.group(2)
            for nm in re.finditer(r'<display-name[^>]*>([^<]+)</display-name>', block, re.IGNORECASE):
                key = _dl_norm(nm.group(1))
                if key:
                    channel_map.setdefault(key, cid)
        progs = {}
        for pm in re.finditer(r'<programme\s+([^>]+)>(.*?)</programme>', text, re.DOTALL | re.IGNORECASE):
            attrs = pm.group(1)
            block = pm.group(2)
            sm = re.search(r'start=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            em = re.search(r'stop=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            cm = re.search(r'channel=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            if not sm or not em or not cm:
                continue
            t = re.search(r'<title[^>]*>([^<]+)</title>', block, re.IGNORECASE)
            d = re.search(r'<desc[^>]*>([^<]+)</desc>', block, re.IGNORECASE)
            title = html_unescape(t.group(1)).strip() if t else ''
            desc = html_unescape(d.group(1)).strip() if d else ''
            progs.setdefault(html_unescape(cm.group(1)).strip(), []).append({'start': sm.group(1), 'stop': em.group(1), 'title': title, 'desc': desc})
        epg = {'name_to_id': channel_map, 'programmes': progs}
    except Exception:
        pass
    _xmltv_epg_cache = epg
    return epg


def _xmltv_epg_for_channel(channel_name, epg_id=''):
    try:
        epg = _xmltv_load_epg()
        cid = (epg_id or '').strip()
        if cid not in epg['programmes']:
            key = _dl_norm(cid or _xmltv_clean_label(channel_name))
            cid = epg['name_to_id'].get(key, '')
            if not cid:
                for k, v in epg['name_to_id'].items():
                    if key and (key in k or k in key):
                        cid = v
                        break
        if not cid:
            return ''
        progs = epg['programmes'].get(cid, [])
        if not progs:
            return ''
        now = datetime.now()
        current = None
        upcoming = []
        for p in progs:
            ps = _xmltv_parse_time(p.get('start'))
            pe = _xmltv_parse_time(p.get('stop'))
            if not ps or not pe:
                continue
            if ps <= now <= pe:
                current = (p, ps, pe)
            elif ps > now:
                upcoming.append((p, ps, pe))
        upcoming = sorted(upcoming, key=lambda x: x[1])[:3]
        lines = []
        if current:
            p, ps, pe = current
            lines.append('[COLOR yellow][B]ACUM:[/B][/COLOR] %s-%s  %s' % (ps.strftime('%H:%M'), pe.strftime('%H:%M'), p.get('title', '')))
            if p.get('desc'):
                lines.append(p.get('desc'))
        if upcoming:
            lines.append('')
            lines.append('[COLOR aqua][B]URMEAZA:[/B][/COLOR]')
            for p, ps, pe in upcoming:
                lines.append('  %s  %s' % (ps.strftime('%H:%M'), p.get('title', '')))
        return '\n'.join(lines)
    except Exception:
        return ''


def _xmltv_merge_description(description, channel_name, epg_id=''):
    try:
        epg_text = _xmltv_epg_for_channel(channel_name, epg_id)
        if epg_text:
            if description:
                return epg_text + '\n\n' + description
            return epg_text
    except Exception:
        pass
    return description

def getItems(items,fanart,pesquisa=False):
    use_thumb = addon.getSetting('use_thumb')
    for item in items:
        try:
            name = re.compile('<title>(.*?)</title>',re.MULTILINE|re.DOTALL).findall(item)[0].replace(';','')
            if name == None or name == '':
                #raise
                name = 'unknown?'
        except:
            name = ''

        try:
            thumbnail = re.compile('<thumbnail>(.*?)</thumbnail>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if thumbnail == None:
                #raise
                thumbnail = ''
        except:
            thumbnail = ''

        try:
            fanart1 = re.compile('<fanart>(.*?)</fanart>',re.MULTILINE|re.DOTALL).findall(item)[0]
        except:
            fanart1 = ''

        if not fanart1:
            if __addon__.getSetting('use_thumb') == "true":
                fanArt = thumbnail
            else:
                fanArt = fanart
        else:
            fanArt = fanart1
        if fanArt == None:
            #raise
            fanArt = ''

        try:
            desc = re.compile('<info>(.*?)</info>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if desc == None:
                #raise
                desc = ''
        except:
            desc = ''

        try:
            epgid = re.compile('<epgid>(.*?)</epgid>',re.MULTILINE|re.DOTALL).findall(item)[0].strip()
        except:
            try:
                epgid = re.compile('<tvg-id>(.*?)</tvg-id>',re.MULTILINE|re.DOTALL).findall(item)[0].strip()
            except:
                epgid = ''

        try:
            category = re.compile('<category>(.*?)</category>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if category == None:
                #raise
                category = ''
        except:
            category = ''

        try:
            subtitle1 = re.compile('<subtitle>(.*?)</subtitle>',re.MULTILINE|re.DOTALL).findall(item)
            if len(subtitle1)>0:
                subtitle = subtitle1[0]
                subs = []
                for sub in subtitle1:
                    subs.append('<subtitle>'+sub+'</subtitle>')
                #subtitle2 = subtitle1
                subtitle2 = subs
            else:
                subtitle = ''
                subtitle2 = ''
        except:
            subtitle = ''
            subtitle2 = ''

        try:
            utube = re.compile('<utube>(.*?)</utube>',re.MULTILINE|re.DOTALL).findall(item)
            if len(utube)>0:
                utube = utube[0]
            else:
                utube = ''
        except:
            utube = ''

        try:
            utubelive = re.compile('<utubelive>(.*?)</utubelive>',re.MULTILINE|re.DOTALL).findall(item)
            if len(utubelive)>0:
                utubelive = utubelive[0]
            else:
                utubelive = ''
        except:
            utubelive = ''

        try:
            jsonrpc = re.compile('<jsonrpc>(.*?)</jsonrpc>',re.MULTILINE|re.DOTALL).findall(item)
            externallink = re.compile('<externallink>(.*?)</externallink>',re.MULTILINE|re.DOTALL).findall(item)
            link = re.compile('<link>(.*?)</link>',re.MULTILINE|re.DOTALL).findall(item)
            if len(jsonrpc)>0:
                url = jsonrpc[0]
                url2 = ''
            elif len(externallink)>0:
                url = externallink[0]
                url2 = ''
            elif len(link)>0:
                try:
                    url = link[0]
                    mylinks = []
                    for link in link:
                        mylinks.append('<link>'+link+'</link>')
                    #url2 = link
                    url2 = mylinks
                except:
                    url = link[0]
                    url2 = ''
            else:
                url = ''
                url2 = ''
        except:
            url = ''
            url2 = ''

        try:
            genre = re.compile('<genre>(.*?)</genre>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if genre == None:
                #raise
                genre = ''
        except:
            genre = ''

        try:
            date = re.compile('<date>(.*?)</date>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if date == None:
                #raise
                date = ''
        except:
            date = ''

        try:
            credits = re.compile('<credits>(.*?)</credits>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if credits == None:
                #raise
                credits = ''
        except:
            credits = ''

        try:
            year = re.compile('<year>(.*?)</year>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if year == None:
                #raise
                year = ''
        except:
            year = ''

        try:
            director = re.compile('<director>(.*?)</director>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if director == None:
                #raise
                director = ''
        except:
            director = ''

        try:
            writer = re.compile('<writer>(.*?)</writer>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if writer == None:
                #raise
                writer = ''
        except:
            writer = ''

        try:
            duration = re.compile('<duration>(.*?)</duration>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if duration == None:
                #raise
                duration = ''
        except:
            duration = ''

        try:
            premiered = re.compile('<premiered>(.*?)</premiered>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if premiered == None:
                #raise
                premiered = ''
        except:
            premiered = ''

        try:
            studio = re.compile('<studio>(.*?)</studio>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if studio == None:
                #raise
                studio = ''
        except:
            studio = ''

        try:
            rate = re.compile('<rate>(.*?)</rate>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if rate == None:
                #raise
                rate = ''
        except:
            rate = ''

        try:
            originaltitle = re.compile('<originaltitle>(.*?)</originaltitle>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if originaltitle == None:
                #raise
                originaltitle = ''
        except:
            originaltitle = ''

        try:
            country = re.compile('<country>(.*?)</country>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if country == None:
                #raise
                country = ''
        except:
            country = ''

        try:
            rating = re.compile('<rating>(.*?)</rating>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if rating == None:
                #raise
                rating = ''
        except:
            rating = ''

        try:
            userrating = re.compile('<userrating>(.*?)</userrating>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if userrating == None:
                #raise
                userrating = ''
        except:
            userrating = ''

        try:
            votes = re.compile('<votes>(.*?)</votes>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if votes == None:
                #raise
                votes = ''
        except:
            votes = ''

        try:
            aired = re.compile('<aired>(.*?)</aired>',re.MULTILINE|re.DOTALL).findall(item)[0]
            if aired == None:
                #raise
                aired = ''
        except:
            aired = ''

        #try:
        #    xbmcgui.Dialog().textviewer('Informação: ', item('director')[0].string)
        #except:
        #    pass

        desc = _xmltv_merge_description(desc, name, epgid)

        #xbmcgui.Dialog().textviewer('Informação:', name)

        try:
            if name > '' and url == '' and not utube > '' and not utubelive > '':
                addLink(name.encode('utf-8', 'ignore'),'None','',thumbnail,fanArt,desc,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired)
            elif name > '' and url == None and not utube > '' and not utubelive > '':
                addLink(name.encode('utf-8', 'ignore'),'None','',thumbnail,fanArt,desc,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired)
            elif category == 'Adult' and url.find('redecanais') >= 0 and url.find('m3u8') >= 0:
                addDir2(name.encode('utf-8', 'ignore'),url,10,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            elif category == 'Adult' and url.find('canaismax') >= 0:
                addDir2(name.encode('utf-8', 'ignore'),url,10,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            elif '.mpd' in url.lower():
                addDir2(name.encode('utf-8', 'ignore'),url,20,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            elif url.find('canaismax') >= 0 and url.find('page') >= 0:
                addDir2(name.encode('utf-8', 'ignore'),url,16,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            elif url.find('ultracine_page') >= 0 and not len(url2) >1:
                addDir2(name.encode('utf-8', 'ignore'),url,16,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            elif url.find('streamtape.com') >= 0 and not len(url2) >1:
                addDir2(name.encode('utf-8', 'ignore'),url,16,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            elif url.find('netcine2_page') >= 0 and not len(url2) >1:
                addDir2(name.encode('utf-8', 'ignore'),url,16,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            elif url.find('series_canaismax') >= 0 and not len(url2) >1:
                addDir2(name.encode('utf-8', 'ignore'),url,16,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            elif url.find('filmes_canaismax') >= 0 and not len(url2) >1:
                addDir2(name.encode('utf-8', 'ignore'),url,16,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            elif utube > '' and len(utube) == 11:
                link_youtube = 'plugin://plugin.video.youtube/play/?video_id='+utube
                addLink(name.encode('utf-8', 'ignore'), link_youtube,subtitle,thumbnail,fanArt,desc,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired)
            elif utubelive > '' and len(utubelive) == 11:
                link_live = 'https://www.youtube.com/watch?v='+utubelive
                addDir2(name.encode('utf-8', 'ignore'),link_live,17,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            elif len(externallink)>0:
                addDir(name.encode('utf-8', 'ignore'),resolver(url),1,thumbnail,fanArt,desc,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired)
            ##Multilink
            elif len(url2) >1 and len(subtitle2) >1 and re.search(playlist_command,url,re.IGNORECASE):
                name_resolve = name+''
                addDir2(name_resolve.encode('utf-8', 'ignore'),str(url2).replace(',','||').replace('$'+playlist_command+'','#'+playlist_command+''),11,str(subtitle2).replace(',','||'),thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            elif len(url2) >1 and re.search(playlist_command,url,re.IGNORECASE):
                name_resolve = name+''
                addDir2(name_resolve.encode('utf-8', 'ignore'),str(url2).replace(',','||').replace('$'+playlist_command+'','#'+playlist_command+''),11,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
                #addLink(name.encode('utf-8', 'ignore'),resolver(url),subtitle,thumbnail,fanArt,desc,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired)
            elif category == 'Adult':
                addDir2(name.encode('utf-8', 'ignore'),url,10,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            elif resolver(url).startswith('plugin://plugin.video.youtube/playlist') == True or resolver(url).startswith('plugin://plugin.video.youtube/channel') == True or resolver(url).startswith('plugin://plugin.video.youtube/user') == True or resolver(url).startswith('Plugin://plugin.video.youtube/playlist') == True:
                addDir(name.encode('utf-8', 'ignore'),resolver(url),6,thumbnail,fanArt,desc,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired)
            elif pesquisa:
                addDir2(name.encode('utf-8', 'ignore'),url,16,subtitle,thumbnail,fanArt,desc.encode('utf-8'),genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,False)
            else:
                #xbmcgui.Dialog().textviewer('Informação:', 'ok')
                #addLink(name.encode('utf-8', 'ignore'),resolver(url, name, thumbnail).encode('utf-8'),subtitle,thumbnail,fanArt,desc,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired)
                addLink(name.encode('utf-8', 'ignore'),resolver(url),subtitle,thumbnail,fanArt,desc,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired)
        except:
            notify('[COLOR red]Erro ao Carregar os items![/COLOR]')


def adult_play_unlocked(name, url, iconimage, description, subtitle):
    urlresolver = resolver(url)
    if urlresolver.startswith('plugin://plugin.video.youtube/playlist') == True or urlresolver.startswith('plugin://plugin.video.youtube/channel') == True or urlresolver.startswith('plugin://plugin.video.youtube/user') == True or urlresolver.startswith('Plugin://plugin.video.youtube/playlist') == True:
        xbmc.executebuiltin("ActivateWindow(10025," + urlresolver + ",return)")
    else:
        li = xbmcgui.ListItem(name, path=urlresolver)
        li.setArt({"icon": iconimage, "thumb": iconimage})
        li.setInfo(type='video', infoLabels={'Title': name, 'plot': description })
        if subtitle > '':
            li.setSubtitles([subtitle])
        xbmc.Player().play(item=urlresolver, listitem=li)


def adult_section_session_file():
    try:
        Path = kodi_translate_path(xbmcaddon.Addon().getAddonInfo('profile')).decode("utf-8")
    except:
        Path = kodi_translate_path(xbmcaddon.Addon().getAddonInfo('profile'))
    try:
        if not os.path.exists(Path):
            os.makedirs(Path)
    except:
        pass
    return os.path.join(Path, "adult_section_unlocked.txt")


def adult_section_set_unlocked(unlocked):
    arquivo = adult_section_session_file()
    try:
        if unlocked:
            p_file = open(arquivo, 'w')
            p_file.write('1')
            p_file.close()
        elif os.path.exists(arquivo):
            os.remove(arquivo)
    except:
        pass


def adult_section_is_unlocked():
    try:
        return os.path.exists(adult_section_session_file())
    except:
        return False


def adult(name, url, iconimage, description, subtitle):
    if adult_section_is_unlocked():
        adult_play_unlocked(name, url, iconimage, description, subtitle)
        return
    try:
        Path = kodi_translate_path(xbmcaddon.Addon().getAddonInfo('profile')).decode("utf-8")
    except:
        Path = kodi_translate_path(xbmcaddon.Addon().getAddonInfo('profile'))
    arquivo = os.path.join(Path, "password.txt")
    exists = os.path.isfile(arquivo)
    keyboard = xbmcaddon.Addon().getSetting("keyboard")
    if exists == False:
        parental_password()
        xbmc.sleep(10)
        p_file = open(arquivo,'r+')
        p_file_read = p_file.read()
        p_file_b64_decode = base64.b64decode(p_file_read).decode('utf-8')
        dialog = xbmcgui.Dialog()
        if setting_int(keyboard) == 0:
            ps = dialog.numeric(0, 'Insira a senha atual:')
        else:
            ps = dialog.input('Insira a senha atual:', option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if ps == p_file_b64_decode:
            urlresolver = resolver(url)
            #if urlresolver.startswith("plugin://") and not 'elementum' in str(urlresolver):
            #    xbmc.executebuiltin('RunPlugin(' + urlresolver + ')')
            #elif urlresolver.startswith('plugin://plugin.video.youtube/playlist') == True or urlresolver.startswith('plugin://plugin.video.youtube/channel') == True or urlresolver.startswith('plugin://plugin.video.youtube/user') == True or urlresolver.startswith('Plugin://plugin.video.youtube/playlist') == True:
            if urlresolver.startswith('plugin://plugin.video.youtube/playlist') == True or urlresolver.startswith('plugin://plugin.video.youtube/channel') == True or urlresolver.startswith('plugin://plugin.video.youtube/user') == True or urlresolver.startswith('Plugin://plugin.video.youtube/playlist') == True:
                xbmc.executebuiltin("ActivateWindow(10025," + urlresolver + ",return)")
            else:
                li = xbmcgui.ListItem(name, path=urlresolver)
                li.setArt({"icon": iconimage, "thumb": iconimage})
                li.setInfo(type='video', infoLabels={'Title': name, 'plot': description })
                if subtitle > '':
                    li.setSubtitles([subtitle])
                xbmc.Player().play(item=urlresolver, listitem=li)
        else:
            xbmcgui.Dialog().ok('[B][COLOR white]AVISO[/COLOR][/B]','Senha invalida!, se não alterou utilize a senha padrão')
    else:
        p_file = open(arquivo,'r+')
        p_file_read = p_file.read()
        p_file_b64_decode = base64.b64decode(p_file_read).decode('utf-8')
        dialog = xbmcgui.Dialog()
        if setting_int(keyboard) == 0:
            ps = dialog.numeric(0, 'Insira a senha atual:')
        else:
            ps = dialog.input('Insira a senha atual:', option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if ps == p_file_b64_decode:
            urlresolver = resolver(url)
            #if urlresolver.startswith("plugin://") and not 'elementum' in str(urlresolver):
            #    xbmc.executebuiltin('RunPlugin(' + urlresolver + ')')
            #elif urlresolver.startswith('plugin://plugin.video.youtube/playlist') == True or urlresolver.startswith('plugin://plugin.video.youtube/channel') == True or urlresolver.startswith('plugin://plugin.video.youtube/user') == True or urlresolver.startswith('Plugin://plugin.video.youtube/playlist') == True:
            if urlresolver.startswith('plugin://plugin.video.youtube/playlist') == True or urlresolver.startswith('plugin://plugin.video.youtube/channel') == True or urlresolver.startswith('plugin://plugin.video.youtube/user') == True or urlresolver.startswith('Plugin://plugin.video.youtube/playlist') == True:
                xbmc.executebuiltin("ActivateWindow(10025," + urlresolver + ",return)")
            else:
                li = xbmcgui.ListItem(name, path=urlresolver)
                li.setArt({"icon": iconimage, "thumb": iconimage})
                li.setInfo(type='video', infoLabels={'Title': name, 'plot': description })
                if subtitle > '':
                    li.setSubtitles([subtitle])
                xbmc.Player().play(item=urlresolver, listitem=li)
        else:
            xbmcgui.Dialog().ok('[B][COLOR white]AVISO[/COLOR][/B]','Senha invalida!, se não alterou utilize a senha padrão')

def adult_section_password():
    dialog = xbmcgui.Dialog()
    dialog.ok('[B][COLOR white]Intrebare Adult[/COLOR][/B]', 'In ce an a fost rostit acest indemn:\n"Domnule Gorbaciov, daramati acest zid!"')
    password = dialog.numeric(0, 'Raspuns (anul):')
    if password == '1987':
        return True
    if password != '':
        xbmcgui.Dialog().ok('[B][COLOR white]AVISO[/COLOR][/B]', 'Parola invalida!')
    return False

def playlist(name, url, iconimage, description, subtitle):
    playlist_command1 = playlist_command
    dialog = xbmcgui.Dialog()
    links = re.compile('<link>([\s\S]*?)#'+playlist_command1+'', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(url)
    names = re.compile('#'+playlist_command1+'=([\s\S]*?)</link>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(url)
    names2 = []
    subtitles = re.compile('<subtitle>([\s\S]*?)</subtitle>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(subtitle)
    for name in names:
        myname = name.replace('+', ' ')
        names2.append(myname)
    if links !=[] and names2 !=[]:
        index = dialog.select(dialog_playlist, names2)
        if index >= 0:
            playname=names2[index]
            if playname > '':
                playname1 = playname
            else:
                playname1 = 'Desconhecido'
            playlink=links[index]
            if subtitles !=[]:
                playsub=subtitles[index]
            else:
                playsub = ''
            urlresolver = resolver(playlink)
            #if urlresolver.startswith("plugin://") and not 'elementum' in str(urlresolver):
            #    xbmc.executebuiltin('RunPlugin(' + urlresolver + ')')
            #elif urlresolver.startswith('plugin://plugin.video.youtube/playlist') == True or urlresolver.startswith('plugin://plugin.video.youtube/channel') == True or urlresolver.startswith('plugin://plugin.video.youtube/user') == True or urlresolver.startswith('Plugin://plugin.video.youtube/playlist') == True:
            if urlresolver.startswith('plugin://plugin.video.youtube/playlist') == True or urlresolver.startswith('plugin://plugin.video.youtube/channel') == True or urlresolver.startswith('plugin://plugin.video.youtube/user') == True or urlresolver.startswith('Plugin://plugin.video.youtube/playlist') == True:
                xbmc.executebuiltin("ActivateWindow(10025," + urlresolver + ",return)")
            else:
                li = xbmcgui.ListItem(playname1, path=urlresolver)
                li.setArt({"icon": iconimage, "thumb": iconimage})
                li.setInfo(type='video', infoLabels={'Title': playname1, 'plot': description })
                if subtitle > '':
                    li.setSubtitles([playsub])
                xbmc.Player().play(item=urlresolver, listitem=li)



def individual_player(name, url, iconimage, description, subtitle):
    urlresolver = resolver(url)
    #if urlresolver.startswith("plugin://") and not 'elementum' in str(urlresolver):
    #    xbmc.executebuiltin('RunPlugin(' + urlresolver + ')')
    #else:
    li = xbmcgui.ListItem(name, path=urlresolver)
    li.setArt({"icon": iconimage, "thumb": iconimage})
    li.setInfo(type='video', infoLabels={'Title': name, 'plot': description })
    if subtitle > '':
        li.setSubtitles([subtitle])
    xbmc.Player().play(item=urlresolver, listitem=li)


def m3u8_player(name, url, iconimage, description, subtitle):
    #if url.startswith("plugin://") and not 'elementum' in str(url):
    #    xbmc.executebuiltin('RunPlugin(' + url + ')')
    #else:
    li = xbmcgui.ListItem(name, path=url)
    li.setArt({"icon": iconimage, "thumb": iconimage})
    li.setInfo(type='video', infoLabels={'Title': name, 'plot': description })
    li.setProperty('IsPlayable', 'true')
    li.setMimeType('application/vnd.apple.mpegurl')
    li.setContentLookup(False)
    if subtitle > '':
        li.setSubtitles([subtitle])
    xbmcplugin.setResolvedUrl(addon_handle, True, li)


def mpd_player(name, url, iconimage, description, subtitle):
    stream_url = url
    stream_headers = ''
    license_type = ''
    license_key = ''
    if '|' in stream_url:
        stream_url, stream_options = stream_url.split('|', 1)
        header_options = []
        stream_options = stream_options.replace(';;', '&')
        for option in stream_options.split('&'):
            if '=' in option:
                option_name, option_value = option.split('=', 1)
                option_name_lower = option_name.lower()
                if option_name_lower in ['license_type', 'inputstream.adaptive.license_type']:
                    license_type = urllib.unquote_plus(option_value)
                elif option_name_lower in ['license_key', 'inputstream.adaptive.license_key']:
                    license_key = urllib.unquote_plus(option_value)
                elif option_name_lower in ['stream_headers', 'manifest_headers', 'inputstream.adaptive.stream_headers', 'inputstream.adaptive.manifest_headers']:
                    header_options.append(urllib.unquote_plus(option_value))
                else:
                    header_options.append(option_name + '=' + urllib.unquote_plus(option_value))
            else:
                header_options.append(option)
        stream_headers = '&'.join(header_options)

    if 'rr.cdn.vodafone.pt' in stream_url and stream_headers == '':
        stream_headers = 'User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)&Referer=http://rr.cdn.vodafone.pt/&Origin=http://rr.cdn.vodafone.pt&verifypeer=false'
    elif 'rr.cdn.vodafone.pt' in stream_url and 'verifypeer=false' not in stream_headers:
        stream_headers = stream_headers + '&Referer=http://rr.cdn.vodafone.pt/&Origin=http://rr.cdn.vodafone.pt&verifypeer=false'

    kodi_url = stream_url
    if stream_headers > '':
        kodi_url = stream_url + '|' + stream_headers

    li = xbmcgui.ListItem(name, path=kodi_url)
    li.setArt({"icon": iconimage, "thumb": iconimage})
    li.setInfo(type='video', infoLabels={'Title': name, 'plot': description })
    li.setMimeType('application/dash+xml')
    li.setContentLookup(False)
    li.setProperty('inputstream', 'inputstream.adaptive')
    li.setProperty('inputstream.adaptive.manifest_type', 'mpd')
    li.setProperty('inputstream.adaptive.file_type', 'mpd')
    if license_key > '':
        if license_type == '' or license_type == 'clearkey':
            license_type = 'org.w3.clearkey'
        li.setProperty('inputstream.adaptive.drm_legacy', license_type + '|' + license_key)
        if license_type == 'org.w3.clearkey':
            drm_config = None
            license_key_clean = license_key.strip()
            try:
                parsed_license_key = json.loads(license_key_clean)
                if isinstance(parsed_license_key, dict):
                    if license_type in parsed_license_key:
                        drm_config = parsed_license_key
                    else:
                        drm_config = {license_type: {'license': {'keyids': parsed_license_key}}}
            except Exception:
                keyids = {}
                for clear_key in license_key_clean.split(','):
                    clear_key = clear_key.strip()
                    if ':' in clear_key:
                        key_id, key_value = clear_key.split(':', 1)
                        key_id = key_id.strip().strip('"{} ')
                        key_value = key_value.strip().strip('"{} ')
                        if key_id and key_value:
                            keyids[key_id] = key_value
                if keyids:
                    drm_config = {license_type: {'license': {'keyids': keyids}}}
            if drm_config:
                li.setProperty('inputstream.adaptive.drm', json.dumps(drm_config))
    if stream_headers > '':
        li.setProperty('inputstream.adaptive.manifest_headers', stream_headers)
        li.setProperty('inputstream.adaptive.stream_headers', stream_headers)
    li.setProperty('IsPlayable', 'true')
    if subtitle > '':
        li.setSubtitles([subtitle])
    try:
        xbmcplugin.setResolvedUrl(addon_handle, True, li)
    except Exception:
        xbmc.Player().play(item=kodi_url, listitem=li)


def ascii(string):
    if isinstance(string, basestring):
        if isinstance(string, unicode):
           string = string.encode('ascii', 'ignore')
    return string
def uni(string, encoding = 'utf-8'):
    if isinstance(string, basestring):
        if not isinstance(string, unicode):
            string = unicode(string, encoding, 'ignore')
    return string
def removeNonAscii(s): return "".join(filter(lambda x: ord(x)<128, s))

def sendJSON(command):
    data = ''
    try:
        data = xbmc.executeJSONRPC(uni(command))
    except UnicodeEncodeError:
        data = xbmc.executeJSONRPC(ascii(command))

    return uni(data)


def pluginquerybyJSON(url):
    json_query = uni('{"jsonrpc":"2.0","method":"Files.GetDirectory","params":{"directory":"%s","media":"video","properties":["thumbnail","title","year","dateadded","fanart","rating","season","episode","studio"]},"id":1}') %url

    json_folder_detail = json.loads(sendJSON(json_query))
    for i in json_folder_detail['result']['files'] :
        url = i['file']
        name = removeNonAscii(i['label'])
        thumbnail = removeNonAscii(i['thumbnail'])
        try:
            fanart = removeNonAscii(i['fanart'])
        except Exception:
            fanart = ''
        try:
            date = i['year']
        except Exception:
            date = ''
        try:
            episode = i['episode']
            season = i['season']
            if episode == -1 or season == -1:
                description = ''
            else:
                description = '[COLOR yellow] S' + str(season)+'[/COLOR][COLOR hotpink] E' + str(episode) +'[/COLOR]'
        except Exception:
            description = ''
        try:
            studio = i['studio']
            if studio:
                description += '\n Studio:[COLOR steelblue] ' + studio[0] + '[/COLOR]'
        except Exception:
            studio = ''

        desc = description+'\n\nDate: '+str(date)

        if i['filetype'] == 'file':
            #addLink(url,name,thumbnail,fanart,description,'',date,'',None,'',total=len(json_folder_detail['result']['files']))
            addLink(name.encode('utf-8', 'ignore'),url.encode('utf-8'),'',thumbnail,fanart,desc,'','','','','','','','','','','','','','','','')
            #xbmc.executebuiltin("Container.SetViewMode(500)")

        else:
            #addDir(name,url,53,thumbnail,fanart,description,'',date,'')
            addDir(name.encode('utf-8', 'ignore'),url.encode('utf-8'),6,iconimage,fanart,desc,'','','','','','','','','','','','','','','','')
            #xbmc.executebuiltin("Container.SetViewMode(500)")

def youtube_live(url):
    data = getRequest2(url, 'https://www.youtube.com/')
    #print(data)
    match = re.compile('"hlsManifestUrl.+?"(.+?).m3u8', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    if match !=[]:
        stream = match[0].replace(':\\"https:', 'https:').replace('\/', '/').replace('\n', '')+'.m3u8|Referer=https://www.youtube.com/|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36'
        #print(stream)
        return stream
    else:
        stream = ''
        return stream


def youtube_live_player(name, url, iconimage, description, subtitle):
    li = xbmcgui.ListItem(name, path=youtube_live(url))
    li.setArt({"icon": iconimage, "thumb": iconimage})
    li.setInfo(type='video', infoLabels={'Title': name, 'plot': description })
    if subtitle > '':
        li.setSubtitles([subtitle])
    xbmc.Player().play(item=youtube_live(url), listitem=li)



def youtube(url):
    plugin_url = url
    xbmc.executebuiltin("ActivateWindow(10025," + plugin_url + ",return)")



def youtube_resolver(url):
    link_youtube = url
    if link_youtube.startswith('https://www.youtube.com/watch?v') == True or link_youtube.startswith('https://youtube.com/watch?v') == True:
        get_id1 = re.compile('v=(.+?)&', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(link_youtube)
        get_id2 = re.compile('v=(.*)', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(link_youtube)
        if get_id1 !=[]:
            #print('tem')
            id_video = get_id1[0]
            #print(id)
            resolve = 'plugin://plugin.video.youtube/play/?video_id='+id_video
        elif get_id2 !=[]:
            #print('tem2')
            id_video = get_id2[0]
            #print(id)
            resolve = 'plugin://plugin.video.youtube/play/?video_id='+id_video
        else:
            resolve = ''
    elif link_youtube.startswith('https://www.youtube.com/playlist?') == True or link_youtube.startswith('https://youtube.com/playlist?') == True:
        get_id1 = re.compile('list=(.+?)&', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(link_youtube)
        get_id2 = re.compile('list=(.*)', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(link_youtube)
        if get_id1 !=[]:
            #print('tem')
            id_video = get_id1[0]
            #print(id)
            resolve = 'plugin://plugin.video.youtube/playlist/'+id_video+'/?page=0'
        elif get_id2 !=[]:
            #print('tem2')
            id_video = get_id2[0]
            #print(id)
            resolve = 'plugin://plugin.video.youtube/playlist/'+id_video+'/?page=0'
        else:
            resolve = ''
    elif link_youtube.startswith('https://www.youtube.com/channel') == True or link_youtube.startswith('https://youtube.com/channel') == True:
        get_id1 = re.compile('channel/(.+?)&', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(link_youtube)
        get_id2 = re.compile('channel/(.*)', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(link_youtube)
        if get_id1 !=[]:
            #print('tem')
            id_video = get_id1[0]
            #print(id)
            resolve = 'plugin://plugin.video.youtube/channel/'+id_video+'/'
        elif get_id2 !=[]:
            #print('tem2')
            id_video = get_id2[0]
            #print(id)
            resolve = 'plugin://plugin.video.youtube/channel/'+id_video+'/'
        else:
            resolve = ''
    elif link_youtube.startswith('https://www.youtube.com/user') == True or link_youtube.startswith('https://youtube.com/user') == True:
        get_id1 = re.compile('user/(.+?)&', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(link_youtube)
        get_id2 = re.compile('user/(.*)', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(link_youtube)
        if get_id1 !=[]:
            #print('tem')
            id_video = get_id1[0]
            #print(id)
            resolve = 'plugin://plugin.video.youtube/user/'+id_video+'/'
        elif get_id2 !=[]:
            #print('tem2')
            id_video = get_id2[0]
            #print(id)
            resolve = 'plugin://plugin.video.youtube/user/'+id_video+'/'
        else:
            resolve = ''

    else:
        resolve = ''
    return resolve


def youtube_restore(url):
    if url.find('/?video_id=') >= 0:
        find_id = re.compile('/?video_id=(.*)', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(url)
        normal_url = 'https://www.youtube.com/watch?v='+str(find_id[0])
    elif url.find('youtube/playlist/') >= 0:
        find_id = re.compile('/playlist/(.+?)/', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(url)
        normal_url = 'https://www.youtube.com/playlist?list='+str(find_id[0])
    else:
        normal_url = ''
    return normal_url


def data_youtube(url, ref):
    try:
        try:
            import cookielib
        except ImportError:
            import http.cookiejar as cookielib
        try:
            import urllib2
        except ImportError:
            import urllib.request as urllib2
        if ref > '':
            ref2 = ref
        else:
            ref2 = url
        cj = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        opener.addheaders=[('Accept-Language', 'en-US,en;q=0.9;q=0.8'),('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'),('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'), ('Referer', ref2)]
        data = opener.open(url).read()
        response = data.decode('utf-8')
        return response
    except:
        #pass
        response = ''
        return response


def getPlaylistLinksYoutube(url):
    try:
        sourceCode = data_youtube(youtube_restore(url), '')
    except:
        sourceCode = ''
    ytb_re = re.compile('url":"https://i.ytimg.com/vi/(.+?)/hqdefault.+?"width":.+?,"height":.+?}]},"title".+?"text":"(.+?)"}],', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(sourceCode)
    for video_id,name in ytb_re:
        original_name = str(name).replace(r"\u0026","&").replace('\\', '')
        thumbnail = "https://img.youtube.com/vi/%s/0.jpg" % video_id
        fanart = "https://i.ytimg.com/vi/%s/hqdefault.jpg" % video_id
        plugin_url = 'plugin://plugin.video.youtube/play/?video_id='+video_id
        urlfinal = str(plugin_url)
        description = ''
        addLink(original_name.encode('utf-8', 'ignore'),urlfinal,'',str(thumbnail),str(fanart),description,'','','','','','','','','','','','','','','','')


def canaismax(url):
    try:
        page = str(re.compile('canaismax_page=(.*)', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(url)[0])
        data = getRequest2(page,'')
        source = re.compile('source.+?"(.+?)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        source2 = re.compile('var.+?url.+?=.+?"(.+?)";', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        if source2 !=[]:
            link = source2[0].replace('\n','').replace('\r','')
            if '.m3u8' in str(link):
                stream = str(link)
            else:
                stream = ''
        elif source !=[]:
            link = source[0].replace('\n','').replace('\r','')
            if '.m3u8' in str(link):
                stream = str(link)
            else:
                stream = ''
        else:
            stream = ''
        return stream
    except:
        stream = ''
        return stream


def netcine2(url):
    try:
        page = str(re.compile('netcine2_page=(.*)', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(url)[0])
        data = getRequest2(page,'')
        source = re.compile('source.+?"(.+?)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        if source !=[]:
            link = source[0].replace('\n','').replace('\r','')
        else:
            link = ''
        return link
    except:
        link = ''
        return link


def ultracine(url):
    try:
        page = str(re.compile('ultracine_page=(.*)', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(url)[0])
        data = getRequest2(page,'')
        source = re.compile('.log.+?"(.+?)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        if source !=[]:
            link = source[0].replace('\n','').replace('\r','')
        else:
            link = ''
        return link
    except:
        link = ''
        return link


def streamtape(url):
    correct_url = url.replace('streamtape.com/v/', 'streamtape.com/e/')
    data = getRequest2(correct_url,'')
    link_part1_re = re.compile('videolink.+?style="display:none;">(.*?)&token=').findall(data)
    link_part2_re = re.compile("<script>.+?token=(.*?)'.+?</script>").findall(data)
    if link_part1_re !=[] and link_part2_re !=[]:
        #link = 'https:'+link_re[0]+'&stream=1'
        #link = 'https:'+link_part1_re[0]+'&token='+link_part2_re[0]
        link = 'https:'+link_part1_re[0]+'&token='+link_part2_re[0]+'|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36'
    else:
        link = ''
    return link


def series_canaismax(url):
    try:
        page = re.compile('series_canaismax=(.+?)&idioma=(.*)', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(url)
        link = page[0][0]
        idioma = page[0][1]
        if 'leg' in idioma or 'Leg' in idioma or 'LEG' in idioma:
            data = getRequest2(link,'')
            tags = re.compile('javascript.+?data-id="(.+?)".+?data-episodio="(.+?)".+?data-player="(.+?)".+?<i>(.+?)</i>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
            tags2 = []
            for id,episodio,player,lang in tags:
                if 'LEG' in lang:
                    tags2.append((id,episodio,player))
            if tags2 !=[]:
                data_id = tags2[0][0]
                data_episodio = tags2[0][1]
                data_player = tags2[0][2]
                data2 = getRequest2('https://canaismax.com/embed/'+data_id+'/'+data_episodio+'/'+data_player,'')
                source = str(re.compile('source.+?"(.*?)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data2)[0])+'|Referer=https://canaismax.com/'
            else:
                source = ''
        elif 'dub' in idioma or 'Dub' in idioma or 'DUB' in idioma:
            data = getRequest2(link,'')
            tags = re.compile('javascript.+?data-id="(.+?)".+?data-episodio="(.+?)".+?data-player="(.+?)".+?<i>(.+?)</i>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
            tags2 = []
            for id,episodio,player,lang in tags:
                if 'DUB' in lang:
                    tags2.append((id,episodio,player))
            if tags2 !=[]:
                data_id = tags2[0][0]
                data_episodio = tags2[0][1]
                data_player = tags2[0][2]
                data2 = getRequest2('https://canaismax.com/embed/'+data_id+'/'+data_episodio+'/'+data_player,'')
                source = str(re.compile('source.+?"(.*?)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data2)[0])+'|Referer=https://canaismax.com/'
            else:
                source = ''
        else:
            source = ''
        return source
    except:
        source = ''
        return source


def filmes_canaismax(url):
    try:
        page = re.compile('filmes_canaismax=(.+?)&idioma=(.*)', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(url)
        link = page[0][0]
        idioma = page[0][1]
        if 'leg' in idioma or 'Leg' in idioma or 'LEG' in idioma:
            data = getRequest2(link,'')
            tags = re.compile('javascript.+?data-id="(.+?)".+?data-player="(.+?)".+?<i>(.+?)</i>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
            tags2 = []
            for id,player,lang in tags:
                if 'LEG' in lang:
                    tags2.append((id,player))
            if tags2 !=[]:
                data_id = tags2[0][0]
                data_player = tags2[0][1]
                data2 = getRequest2('https://canaismax.com/embed/'+data_id+'/'+data_player,'')
                source = str(re.compile('source.+?"(.*?)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data2)[0])+'|Referer=https://canaismax.com/'
            else:
                source = ''
        elif 'dub' in idioma or 'Dub' in idioma or 'DUB' in idioma:
            data = getRequest2(link,'')
            tags = re.compile('javascript.+?data-id="(.+?)".+?data-player="(.+?)".+?<i>(.+?)</i>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
            tags2 = []
            for id,player,lang in tags:
                if 'DUB' in lang:
                    tags2.append((id,player))
            if tags2 !=[]:
                data_id = tags2[0][0]
                data_player = tags2[0][1]
                data2 = getRequest2('https://canaismax.com/embed/'+data_id+'/'+data_player,'')
                source = str(re.compile('source.+?"(.*?)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data2)[0])+'|Referer=https://canaismax.com/'
            else:
                source = ''
        else:
            source = ''
        return source
    except:
        source = ''
        return source

def stream_url_with_headers(url, referer, origin=''):
    if url == '':
        return ''
    url = html_unescape(url).replace('\\/', '/').replace('\/', '/').replace('&amp;', '&')
    try:
        url = codecs.decode(url, 'unicode_escape')
    except:
        pass
    url = url.replace('\\/', '/').replace('\/', '/')
    if referer > '' and '|' not in url:
        url += '|Referer=' + urllib.quote_plus(referer) + '&User-Agent=' + urllib.quote_plus(useragent)
        if origin > '':
            url += '&Origin=' + urllib.quote_plus(origin)
    return url


def xhamster_to_signed_32(n):
    return n % ((-1 if n < 0 else 1) * 2**32)


class XHamsterByteGenerator:
    def __init__(self, algo_id, seed):
        self._algorithm = getattr(self, '_algo%s' % algo_id)
        self._s = xhamster_to_signed_32(seed)

    def _algo1(self, s):
        s = self._s = xhamster_to_signed_32(s * 1664525 + 1013904223)
        return s

    def _algo2(self, s):
        s = xhamster_to_signed_32(s ^ (s << 13))
        s = xhamster_to_signed_32(s ^ ((s & 0xFFFFFFFF) >> 17))
        s = self._s = xhamster_to_signed_32(s ^ (s << 5))
        return s

    def _algo3(self, s):
        s = self._s = xhamster_to_signed_32(s + 0x9e3779b9)
        s = xhamster_to_signed_32(s ^ ((s & 0xFFFFFFFF) >> 16))
        s = xhamster_to_signed_32(s * xhamster_to_signed_32(0x85ebca77))
        s = xhamster_to_signed_32(s ^ ((s & 0xFFFFFFFF) >> 13))
        s = xhamster_to_signed_32(s * xhamster_to_signed_32(0xc2b2ae3d))
        return xhamster_to_signed_32(s ^ ((s & 0xFFFFFFFF) >> 16))

    def _algo4(self, s):
        s = self._s = xhamster_to_signed_32(s + 0x6d2b79f5)
        s = xhamster_to_signed_32((s << 7) | ((s & 0xFFFFFFFF) >> 25))
        s = xhamster_to_signed_32(s + 0x9e3779b9)
        s = xhamster_to_signed_32(s ^ ((s & 0xFFFFFFFF) >> 11))
        s = xhamster_to_signed_32(s * 0x27d4eb2d)
        return s

    def _algo5(self, s):
        s = xhamster_to_signed_32(s ^ (s << 7))
        s = xhamster_to_signed_32(s ^ ((s & 0xFFFFFFFF) >> 9))
        s = xhamster_to_signed_32(s ^ (s << 8))
        s = self._s = xhamster_to_signed_32(s + 0xa5a5a5a5)
        return s

    def _algo6(self, s):
        s = self._s = xhamster_to_signed_32(s * xhamster_to_signed_32(0x2c9277b5) + xhamster_to_signed_32(0xac564b05))
        s2 = xhamster_to_signed_32(s ^ ((s & 0xFFFFFFFF) >> 18))
        shift = (s & 0xFFFFFFFF) >> 27 & 31
        return xhamster_to_signed_32((s2 & 0xFFFFFFFF) >> shift)

    def _algo7(self, s):
        s = self._s = xhamster_to_signed_32(s + xhamster_to_signed_32(0x9e3779b9))
        e = xhamster_to_signed_32(s ^ (s << 5))
        e = xhamster_to_signed_32(e * xhamster_to_signed_32(0x7feb352d))
        e = xhamster_to_signed_32(e ^ ((e & 0xFFFFFFFF) >> 15))
        e = xhamster_to_signed_32(e * xhamster_to_signed_32(0x846ca68b))
        return e

    def __next__(self):
        return self._algorithm(self._s) & 0xFF

    next = __next__


def xhamster_try_call(*funcs):
    for func in funcs:
        try:
            return func()
        except (AttributeError, KeyError, TypeError, IndexError, ValueError, ZeroDivisionError):
            pass
    return None


def xhamster_deobfuscate_url(format_url):
    if not format_url:
        return ''
    if all(char in string.hexdigits for char in format_url):
        byte_data = bytearray.fromhex(format_url)
        seed = int.from_bytes(byte_data[1:5], byteorder='little', signed=True)
        byte_gen = XHamsterByteGenerator(byte_data[0], seed)
        return bytearray(byte ^ next(byte_gen) for byte in byte_data[5:]).decode('latin-1')

    decoded = xhamster_try_call(lambda: base64.b64decode(format_url).decode().partition('_'))
    if not decoded:
        return ''
    cipher_type, _, ciphertext = decoded
    if cipher_type == 'xor':
        key = b'xh7999'
        return bytes(a ^ b for a, b in zip(ciphertext.encode(), itertools.cycle(key))).decode()
    if cipher_type == 'rot13':
        return codecs.decode(ciphertext, cipher_type)
    return ''


def xhamster_best_quality(srcs):
    if not srcs:
        return ''
    order = ['4k', '2160p', '1440p', '1080p', '720p', '480p', '360p', '240p']
    for quality in order:
        if quality in srcs and srcs[quality]:
            return srcs[quality]
    for quality in sorted(srcs.keys(), reverse=True):
        if srcs[quality]:
            return srcs[quality]
    return ''


def xhamster(link):
    referer = 'https://xhamster.com/'
    try:
        link = link.replace('/embed/', '/videos/')
        data = getRequest2(link, referer, useragent)
        if not data:
            data = getRequest(link, 1)
        if not data:
            return ''

        preload = re.compile(r'<link rel="preload" href="([^"]+m3u8)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).search(data)
        if preload:
            return stream_url_with_headers(preload.group(1).replace('.av1.', '.h264.'), link)

        video_src = re.compile(r'<video class="player-container.+?src="(http[^"]+)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).search(data)
        if video_src:
            return stream_url_with_headers(video_src.group(1), link)

        try:
            jsondata = data.split('>window.initials=')[-1].split(';</script>')[0]
            jdata = json.loads(jsondata)
            settings = jdata.get('xplayerSettings', {})
            settings2 = jdata.get('xplayerSettings2', {})
            sources = settings.get('sources', {})
            sources2 = settings2.get('sources', {})
            hexurl = ''

            if 'hls' in sources:
                hls = sources.get('hls') or {}
                for codec_name in ['h264', 'h265', 'av1']:
                    codec_src = hls.get(codec_name)
                    if codec_src and codec_src.get('url'):
                        hexurl = codec_src.get('url')
                        break

            if hexurl:
                if not hexurl.startswith('http'):
                    stream = xhamster_deobfuscate_url(hexurl)
                else:
                    parts = hexurl.split('/')
                    enc_string = parts[3] if len(parts) > 3 else ''
                    dec_string = xhamster_deobfuscate_url(enc_string)
                    stream = hexurl.replace(enc_string, dec_string) if dec_string else hexurl
                if stream:
                    return stream_url_with_headers(stream, link)

            if 'standard' in sources2:
                standard = sources2.get('standard') or {}
                h264 = standard.get('h264') or []
                srcs = {}
                for source in h264:
                    if source.get('quality') and source.get('url'):
                        srcs[source.get('quality')] = source.get('url')
                stream = xhamster_best_quality(srcs)
                if stream:
                    return stream_url_with_headers(stream, link)
        except Exception as e:
            try:
                xbmc.log('[RomyLive] xHamster JSON fallback: %s' % e, level=xbmc.LOGWARNING)
            except:
                pass

        patterns = [
            r'"hls"\s*:\s*"([^"]+?\.m3u8[^"]*)"',
            r'"hls"\s*:\s*\{[\s\S]*?"url"\s*:\s*"([^"]+?\.m3u8[^"]*)"',
            r'"sources"\s*:\s*\{[\s\S]*?"hls"[\s\S]*?"url"\s*:\s*"([^"]+?\.m3u8[^"]*)"',
            r'(https?:\\?/\\?/[^"\']+?\.m3u8[^"\']*)'
        ]
        for pattern in patterns:
            matches = re.compile(pattern, re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if match:
                    return stream_url_with_headers(match, link)

        mp4_matches = re.compile(r'"url"\s*:\s*"([^"]+?\.mp4[^"]*)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
        for match in mp4_matches:
            if match:
                return stream_url_with_headers(match, link)

        try:
            resolved = resolveurl.resolve(link)
            if resolved:
                return stream_url_with_headers(resolved, link)
        except:
            pass
    except Exception as e:
        try:
            xbmc.log('[RomyLive] Eroare xHamster: %s' % e, level=xbmc.LOGERROR)
        except:
            pass
    return ''
def resolver(link):
    link_decoded = link
    try:
        if not link_decoded.startswith("plugin://plugin") and link_decoded.startswith('https://drive.google.com') == True:
            #print('verdadeiro')
            resolved = link_decoded.replace('http','plugin://plugin.video.gdrive?mode=streamURL&amp;url=http')
            #print(resolved)
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.startswith('http://drive.google.com') == True:
            #print('verdadeiro')
            resolved = link_decoded.replace('http','plugin://plugin.video.gdrive?mode=streamURL&amp;url=http')
            #print(resolved)
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('streamtape.com') >= 0:
            link = streamtape(link_decoded)
            resolved = link
            #print(resolved)
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('xhamster.com/videos/') >= 0:
            link = xhamster(link_decoded)
            resolved = link
            #print(resolved)
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('ultracine_page') >= 0:
            link = ultracine(link_decoded)
            resolved = link
            #print(resolved)
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('netcine2_page') >= 0:
            link = netcine2(link_decoded)
            resolved = link
            #print(resolved)
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('series_canaismax') >= 0:
            link_corrigido = link_decoded.replace('idioma;', 'idioma')
            link = series_canaismax(link_corrigido)
            resolved = link
            #print(resolved)
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('filmes_canaismax') >= 0:
            link_corrigido = link_decoded.replace('idioma;', 'idioma')
            link = filmes_canaismax(link_corrigido)
            resolved = link
            #print(resolved)
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('eu-central-1.edge.mycdn.live') >= 0:
            #print('verdadeiro')
            resolved = link_decoded
            #print(resolved)
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('canaismax_page') >= 0:
            stream = canaismax(link_decoded)
            resolved = stream+'|Referer=https://canaismax.com/|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36'
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.startswith('https://youtube.com/') == True or link_decoded.startswith('https://www.youtube.com/') == True:
            try:
                resultado = youtube_resolver(link_decoded)
                if resultado==None:
                    #print('vazio')
                    resolved = ''
                else:
                    resolved = resultado
            except:
                resolved = ''
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.startswith('https://photos.app') == True:
            try:
                data = getRequest2(link_decoded, 'https://photos.google.com/')
                result = re.compile('<meta property="og:video" content="(.+?)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
                if result !=[]:
                    resolved = result[0].replace('-m18','-m22')
                else:
                    resolved = ''
            except:
                resolved = ''
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.startswith('magnet:?xt=') == True:
            resolved = 'plugin://plugin.video.elementum/play?uri='+link_decoded
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('.torrent') >= 0:
            resolved = 'plugin://plugin.video.elementum/play?uri='+link_decoded
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('.mp4') >= 0 and not link_decoded.startswith('magnet:?xt=') == True and not link_decoded.find('.torrent') >= 0:
            resolved = link_decoded
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('.mkv') >= 0 and not link_decoded.startswith('magnet:?xt=') == True and not link_decoded.find('.torrent') >= 0:
            resolved = link_decoded
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('.wmv') >= 0 and not link_decoded.startswith('magnet:?xt=') == True and not link_decoded.find('.torrent') >= 0:
            resolved = link_decoded
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('.wma') >= 0 and not link_decoded.startswith('magnet:?xt=') == True and not link_decoded.find('.torrent') >= 0:
            resolved = link_decoded
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('.avi') >= 0 and not link_decoded.startswith('magnet:?xt=') == True and not link_decoded.find('.torrent') >= 0:
            resolved = link_decoded
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('.mp3') >= 0 and not link_decoded.startswith('magnet:?xt=') == True and not link_decoded.find('.torrent') >= 0:
            resolved = link_decoded
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('.ac3') >= 0 and not link_decoded.startswith('magnet:?xt=') == True and not link_decoded.find('.torrent') >= 0:
            resolved = link_decoded
        elif not link_decoded.startswith("plugin://plugin") and link_decoded.find('.rmvb') >= 0 and not link_decoded.startswith('magnet:?xt=') == True and not link_decoded.find('.torrent') >= 0:
            resolved = link_decoded
        elif not link_decoded.startswith("plugin://plugin"):
            resolved = link_decoded
        elif link_decoded.startswith("plugin://plugin"):
            resolved = link_decoded
        return resolved
    except:
        resolved = ''
        return resolved
        #pass
        #notify('[COLOR red]Não foi possivel resolver um link![/COLOR]')



def getFavorites():
    try:
        try:
            items = json.loads(open(favorites).read())
        except:
            items = ''
        total = len(items)
        if int(total) > 0:
            for i in items:
                name = i[0]
                url = i[1]
                try:
                    urldecode = base64.b64decode(base64.b16decode(url))
                except:
                    urldecode = url
                try:
                    url2 = urldecode.decode('utf-8')
                except:
                    url2 = urldecode

                mode = i[2]
                subtitle = i[3]
                try:
                    subtitledecode = base64.b64decode(base64.b16decode(subtitle))
                except:
                    subtitledecode = subtitle
                try:
                    sub2 = subtitledecode.decode('utf-8')
                except:
                    sub2 = subtitledecode
                iconimage = i[4]
                try:
                    fanArt = i[5]
                    if fanArt == None:
                        raise
                except:
                    if addon.getSetting('use_thumb') == "true":
                        fanArt = iconimage
                    else:
                        fanArt = fanart
                description = i[6]

                if mode == 0:
                    try:
                        #addLink(name.encode('utf-8', 'ignore'),url2,sub2,iconimage,fanArt,description.encode('utf-8'),'','','','','','','','','','','','','','','','')
                        addLink(name.encode('utf-8', 'ignore'),url2,sub2,iconimage,fanArt,description.encode('utf-8'),'','','','','','','','','','','','','','','','')
                    except:
                        pass
                elif mode == 11 or mode == 16 or mode == 17 or mode == 18 or mode == 20:
                    try:
                        addDir2(str(name).encode('utf-8', 'ignore'),url2,mode,sub2,iconimage,fanArt,description.encode('utf-8'),'','','','','','','','','','','','','','','','',False)
                    except:
                        pass
                elif mode > 0 and mode < 7:
                    try:
                        addDir(name.encode('utf-8', 'ignore'),url2,mode,iconimage,fanArt,description.encode('utf-8'),'','','','','','','','','','','','','','','','')
                    except:
                        pass
                else:
                    try:
                        addDir2(name.encode('utf-8', 'ignore'),url2,mode,sub2,iconimage,fanArt,description.encode('utf-8'),'','','','','','','','','','','','','','','','')
                    except:
                        pass
                xbmcplugin.setContent(addon_handle, 'movies')
                xbmcplugin.endOfDirectory(addon_handle)
        else:
            xbmcgui.Dialog().ok('[B][COLOR white]AVISO[/COLOR][/B]','Nada Adicionado nos Favoritos')
    except:
        pass


def addFavorite(name,url,fav_mode,subtitle,iconimage,fanart,description):
    favList = []
    if os.path.exists(favorites)==False:
        addonID = xbmcaddon.Addon().getAddonInfo('id')
        addon_data_path = kodi_translate_path(os.path.join('special://home/userdata/addon_data', addonID))
        if os.path.exists(addon_data_path)==False:
            os.mkdir(addon_data_path)
        xbmc.sleep(7)
        favList.append((name,url,fav_mode,subtitle,iconimage,fanart,description))
        a = open(favorites, "w")
        a.write(json.dumps(favList))
        a.close()
        notify('Adicionado aos Favoritos do '+__addonname__)
        #xbmc.executebuiltin("XBMC.Container.Refresh")
    else:
        a = open(favorites).read()
        data = json.loads(a)
        data.append((name,url,fav_mode,subtitle,iconimage,fanart,description))
        b = open(favorites, "w")
        b.write(json.dumps(data))
        b.close()
        notify('Adicionado aos Favoritos do '+__addonname__)
        #xbmc.executebuiltin("XBMC.Container.Refresh")


def rmFavorite(name):
    data = json.loads(open(favorites).read())
    for index in range(len(data)):
        if data[index][0]==name:
            del data[index]
            b = open(favorites, "w")
            b.write(json.dumps(data))
            b.close()
            break
    notify('Removido dos Favoritos do '+__addonname__)
    #xbmc.executebuiltin("XBMC.Container.Refresh")

def addDir(name,url,mode,iconimage,fanart,description,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,folder=True):
    if mode == 1:
        if url > '':
            #u=sys.argv[0]+"?url="+urllib.quote_plus(base64.b64encode(url))+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&fanart="+urllib.quote_plus(fanart)
            #u=sys.argv[0]+"?url="+urllib.quote_plus(codecs.encode(base64.b32encode(base64.b16encode(url)), '\x72\x6f\x74\x31\x33'))+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&fanart="+urllib.quote_plus(fanart)
            #u=sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&fanart="+urllib.quote_plus(fanart)
            #u=sys.argv[0]+"?url="+urllib.quote_plus(base64.b32encode(url.encode('utf-8')))+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&fanart="+urllib.quote_plus(fanart)
            #u=sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&fanart="+urllib.quote_plus(fanart)
            u=sys.argv[0]+"?url="+urllib.quote_plus(base64.b16encode(base64.b64encode(url.encode('utf-8'))))+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&fanart="+urllib.quote_plus(fanart)
        else:
            u=sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(5)+"&name="+urllib.quote_plus(name)+"&fanart="+urllib.quote_plus(fanart)
    else:
        u=sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&fanart="+urllib.quote_plus(fanart)
    li=xbmcgui.ListItem(name)
    if folder:
        li.setArt({"icon": "DefaultFolder.png", "thumb": iconimage})
    else:
        li.setArt({"icon": "DefaultVideo.png", "thumb": iconimage})
        li.setProperty('IsPlayable', 'true')
    if date == '':
        date = None
    else:
        description += '\n\nDate: %s' %date
    li.setInfo('video', { 'title': name, 'plot': description })
    try:
        li.setInfo('video', { 'genre': str(genre) })
    except:
        pass
    try:
        li.setInfo('video', { 'dateadded': str(date) })
    except:
        pass
    try:
        li.setInfo('video', { 'credits': str(credits) })
    except:
        pass
    try:
        li.setInfo('video', { 'year': int(year) })
    except:
        pass
    try:
        li.setInfo('video', { 'year': int(year) })
    except:
        pass
    try:
        li.setInfo('video', { 'director': str(director) })
    except:
        pass
    try:
        li.setInfo('video', { 'writer': str(writer) })
    except:
        pass
    try:
        li.setInfo('video', { 'duration': int(duration) })
    except:
        pass
    try:
        li.setInfo('video', { 'premiered': str(premiered) })
    except:
        pass
    try:
        li.setInfo('video', { 'studio': str(studio) })
    except:
        pass
    try:
        li.setInfo('video', { 'mpaa': str(rate) })
    except:
        pass
    try:
        li.setInfo('video', { 'originaltitle': str(originaltitle) })
    except:
        pass
    try:
        li.setInfo('video', { 'country': str(country) })
    except:
        pass
    try:
        li.setInfo('video', { 'rating': float(rating) })
    except:
        pass
    try:
        li.setInfo('video', { 'userrating': int(userrating) })
    except:
        pass
    try:
        li.setInfo('video', { 'votes': str(votes) })
    except:
        pass
    try:
        li.setRating("imdb", float(rating), int(votes), True)
    except:
        pass
    try:
        li.setInfo('video', { 'aired': str(aired) })
    except:
        pass

    if fanart > '':
        li.setProperty('fanart_image', fanart)
    else:
        li.setProperty('fanart_image', ''+home+'/fanart.jpg')
    try:
        name_decode = name.decode('utf-8')
    except:
        name_decode = name
    try:
        name_fav = json.dumps(name_decode)
    except:
        name_fav =  name_decode
    try:
        contextMenu = []
        if favoritos == 'true' and  mode !=4 and mode !=7 and mode !=8 and mode !=9 and mode !=10 and mode !=12 and mode !=15:
            if name_fav in FAV:
                contextMenu.append(('Remover dos Favoritos do '+__addonname__,'RunPlugin(%s?mode=14&name=%s)'%(sys.argv[0], urllib.quote_plus(name))))
            else:
                fav_params = ('%s?mode=13&name=%s&url=%s&subtitle=%s&iconimage=%s&fanart=%s&description=%s&fav_mode=%s'%(sys.argv[0], urllib.quote_plus(name), urllib.quote_plus(base64.b16encode(base64.b64encode(url.encode('utf-8')))), '', urllib.quote_plus(iconimage), urllib.quote_plus(fanart), urllib.quote_plus(description), str(mode)))
                contextMenu.append(('Adicionar aos Favoritos do '+__addonname__,'RunPlugin(%s)' %fav_params))
        contextMenu.append(('Informação', 'RunPlugin(%s?mode=19&name=%s&description=%s)' % (sys.argv[0], urllib.quote_plus(name), urllib.quote_plus(description))))
        li.addContextMenuItems(contextMenu)
    except:
        pass
    xbmcplugin.addDirectoryItem(handle=addon_handle,url=u,listitem=li, isFolder=folder)

def addDir2(name,url,mode,subtitle,iconimage,fanart,description,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,folder=True):
    if mode == 1:
        if url > '':
            u=sys.argv[0]+"?url="+urllib.quote_plus(base64.b16encode(base64.b64encode(url.encode('utf-8'))))+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&fanart="+urllib.quote_plus(fanart)
        else:
            u=sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(5)+"&name="+urllib.quote_plus(name)+"&fanart="+urllib.quote_plus(fanart)
    else:
        u=sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&fanart="+urllib.quote_plus(fanart)+"&iconimage="+urllib.quote_plus(iconimage)+"&subtitle="+urllib.quote_plus(subtitle)+"&description="+urllib.quote_plus(description)
    li=xbmcgui.ListItem(name)
    if folder:
        li.setArt({"icon": "DefaultFolder.png", "thumb": iconimage})
    else:
        li.setArt({"icon": "DefaultVideo.png", "thumb": iconimage})
        li.setProperty('IsPlayable', 'true')
    if date == '':
        date = None
    else:
        description += '\n\nDate: %s' %date
    li.setInfo('video', { 'title': name, 'plot': description })
    try:
        li.setInfo('video', { 'genre': str(genre) })
    except:
        pass
    try:
        li.setInfo('video', { 'dateadded': str(date) })
    except:
        pass
    try:
        li.setInfo('video', { 'credits': str(credits) })
    except:
        pass
    try:
        li.setInfo('video', { 'year': int(year) })
    except:
        pass
    try:
        li.setInfo('video', { 'year': int(year) })
    except:
        pass
    try:
        li.setInfo('video', { 'director': str(director) })
    except:
        pass
    try:
        li.setInfo('video', { 'writer': str(writer) })
    except:
        pass
    try:
        li.setInfo('video', { 'duration': int(duration) })
    except:
        pass
    try:
        li.setInfo('video', { 'premiered': str(premiered) })
    except:
        pass
    try:
        li.setInfo('video', { 'studio': str(studio) })
    except:
        pass
    try:
        li.setInfo('video', { 'mpaa': str(rate) })
    except:
        pass
    try:
        li.setInfo('video', { 'originaltitle': str(originaltitle) })
    except:
        pass
    try:
        li.setInfo('video', { 'country': str(country) })
    except:
        pass
    try:
        li.setInfo('video', { 'rating': float(rating) })
    except:
        pass
    try:
        li.setInfo('video', { 'userrating': int(userrating) })
    except:
        pass
    try:
        li.setInfo('video', { 'votes': str(votes) })
    except:
        pass
    try:
        li.setRating("imdb", float(rating), int(votes), True)
    except:
        pass
    try:
        li.setInfo('video', { 'aired': str(aired) })
    except:
        pass
    if fanart > '':
        li.setProperty('fanart_image', fanart)
    else:
        li.setProperty('fanart_image', ''+home+'/fanart.jpg')
    try:
        name_decode = name.decode('utf-8')
    except:
        name_decode = name
    try:
        name_fav = json.dumps(name_decode)
    except:
        name_fav =  name_decode
    try:
        contextMenu = []
        if favoritos == 'true' and  mode !=4 and mode !=7 and mode !=8 and mode !=9 and mode !=10 and mode !=12 and mode !=15:
            if name_fav in FAV:
                contextMenu.append(('Remover dos Favoritos do '+__addonname__,'RunPlugin(%s?mode=14&name=%s)'%(sys.argv[0], urllib.quote_plus(name))))
            else:
                fav_params = ('%s?mode=13&name=%s&url=%s&subtitle=%s&iconimage=%s&fanart=%s&description=%s&fav_mode=%s'%(sys.argv[0], urllib.quote_plus(name), urllib.quote_plus(base64.b16encode(base64.b64encode(url.encode('utf-8')))), urllib.quote_plus(base64.b16encode(base64.b64encode(subtitle.encode('utf-8')))), urllib.quote_plus(iconimage), urllib.quote_plus(fanart), urllib.quote_plus(description), str(mode)))
                contextMenu.append(('Adicionar aos Favoritos do '+__addonname__,'RunPlugin(%s)' %fav_params))
        contextMenu.append(('Informação', 'RunPlugin(%s?mode=19&name=%s&description=%s)' % (sys.argv[0], urllib.quote_plus(name), urllib.quote_plus(description))))
        li.addContextMenuItems(contextMenu)
    except:
        pass
    xbmcplugin.addDirectoryItem(handle=addon_handle,url=u,listitem=li, isFolder=folder)

def addLink(name,url,subtitle,iconimage,fanart,description,genre,date,credits,year,director,writer,duration,premiered,studio,rate,originaltitle,country,rating,userrating,votes,aired,folder=False):
    if date == '':
        date = None
    else:
        description += '\n\nDate: %s' %date
    if iconimage > '':
        thumbnail = iconimage
    else:
        thumbnail = 'DefaultVideo.png'
    li=xbmcgui.ListItem(name)
    li.setArt({"icon": "DefaultVideo.png", "thumb": thumbnail})
    if url.startswith("plugin://plugin.video.f4mTester"):
        li.setProperty('IsPlayable', 'false')
    else:
        li.setProperty('IsPlayable', 'true')
    if fanart > '':
        li.setProperty('fanart_image', fanart)
    else:
        li.setProperty('fanart_image', ''+home+'/fanart.jpg')
    try:
        name_fav = json.dumps(name)
    except:
        name_fav = name
    name2_fav = name
    desc_fav = description
    li.setInfo('video', { 'plot': description })
    try:
        li.setInfo('video', { 'genre': str(genre) })
    except:
        pass
    try:
        li.setInfo('video', { 'dateadded': str(date) })
    except:
        pass
    try:
        li.setInfo('video', { 'credits': str(credits) })
    except:
        pass
    try:
        li.setInfo('video', { 'year': int(year) })
    except:
        pass
    try:
        li.setInfo('video', { 'year': int(year) })
    except:
        pass
    try:
        li.setInfo('video', { 'director': str(director) })
    except:
        pass
    try:
        li.setInfo('video', { 'writer': str(writer) })
    except:
        pass
    try:
        li.setInfo('video', { 'duration': int(duration) })
    except:
        pass
    try:
        li.setInfo('video', { 'premiered': str(premiered) })
    except:
        pass
    try:
        li.setInfo('video', { 'studio': str(studio) })
    except:
        pass
    try:
        li.setInfo('video', { 'mpaa': str(rate) })
    except:
        pass
    try:
        li.setInfo('video', { 'originaltitle': str(originaltitle) })
    except:
        pass
    try:
        li.setInfo('video', { 'country': str(country) })
    except:
        pass
    try:
        li.setInfo('video', { 'rating': float(rating) })
    except:
        pass
    try:
        li.setInfo('video', { 'userrating': int(userrating) })
    except:
        pass
    try:
        li.setInfo('video', { 'votes': str(votes) })
    except:
        pass
    try:
        li.setRating("imdb", float(rating), int(votes), True)
    except:
        pass
    try:
        li.setInfo('video', { 'aired': str(aired) })
    except:
        pass

    if subtitle > '':
        li.setSubtitles([subtitle])
    try:
        name_decode = name.decode('utf-8')
    except:
        name_decode = name
    try:
        name_fav = json.dumps(name_decode)
    except:
        name_fav =  name_decode
    try:
        contextMenu = []
        if favoritos == 'true':
            if name_fav in FAV:
                contextMenu.append(('Remover dos Favoritos do '+__addonname__,'RunPlugin(%s?mode=14&name=%s)'%(sys.argv[0], urllib.quote_plus(name))))
            else:
                fav_params = ('%s?mode=13&name=%s&url=%s&subtitle=%s&iconimage=%s&fanart=%s&description=%s&fav_mode=0'%(sys.argv[0], urllib.quote_plus(name), urllib.quote_plus(base64.b16encode(base64.b64encode(url.encode('utf-8')))), urllib.quote_plus(base64.b16encode(base64.b64encode(subtitle.encode('utf-8')))), urllib.quote_plus(iconimage), urllib.quote_plus(fanart), urllib.quote_plus(description)))
                contextMenu.append(('Adicionar aos Favoritos do '+__addonname__,'RunPlugin(%s)' %fav_params))
        contextMenu.append(('Informação', 'RunPlugin(%s?mode=19&name=%s&description=%s)' % (sys.argv[0], urllib.quote_plus(name), urllib.quote_plus(description))))
        try:
            if isinstance(url, str) and 'mode=55' in url and 'tvzonehd.com' in url:
                from urllib.parse import parse_qs as _pqs
                _tvz_favs = _tvzone_load_favorites()
                _tvz_qs = _pqs(url.split('?', 1)[1]) if '?' in url else {}
                _tvz_page_url = (_tvz_qs.get('url') or [''])[0]
                if _tvz_page_url:
                    _tvz_label = 'Sterge din Favorite TVZone' if _tvz_page_url in _tvz_favs else 'Adauga la Favorite TVZone'
                    _tvz_nm = name if isinstance(name, str) else (name.decode('utf-8', 'ignore') if hasattr(name, 'decode') else str(name))
                    _tvz_action = '%s?mode=56&url=%s&name=%s' % (sys.argv[0], urllib.quote_plus(_tvz_page_url), urllib.quote_plus(_tvz_nm))
                    contextMenu.append((_tvz_label, 'RunPlugin(%s)' % _tvz_action))
        except Exception:
            pass
        li.addContextMenuItems(contextMenu)
    except:
        pass
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=folder)

def parental_password():
    try:
        addonID = xbmcaddon.Addon().getAddonInfo('id')
        addon_data_path = kodi_translate_path(os.path.join('special://home/userdata/addon_data', addonID))
        if os.path.exists(addon_data_path)==False:
            os.mkdir(addon_data_path)
        xbmc.sleep(7)
        #Path = kodi_translate_path(xbmcaddon.Addon().getAddonInfo('profile')).decode("utf-8")
        #arquivo = os.path.join(Path, "password.txt")
        arquivo = os.path.join(addon_data_path, "password.txt")
        exists = os.path.isfile(arquivo)
        if exists == False:
            password = '0069'
            p_encoded = base64.b64encode(password.encode()).decode('utf-8')
            p_file = open(arquivo,'w')
            p_file.write(p_encoded)
            p_file.close()
    except:
        pass

def check_addon():
    try:
        check_file = kodi_translate_path(home+'/check.txt')
        exists = os.path.isfile(check_file)
        check_addon = addon.getSetting('check_addon')
        #check_file = 'check.txt'
        if exists == True:
            #print('existe')
            fcheck = open(check_file,'r+')
            elementum = addon.getSetting('elementum')
            youtube = addon.getSetting('youtube')
            if fcheck and fcheck.read() == '1' and check_addon == 'true':
                #print('valor 1')
                fcheck.close()
                link = getRequest2('https://raw.githubusercontent.com/zoreu/zoreu.github.io/master/kodi/verificar_addons_matrix.txt','').replace('\n','').replace('\r','')
                match = re.compile('addon_name="(.+?)".+?ddon_id="(.+?)".+?ir="(.+?)".+?rl_zip="(.+?)".+?escription="(.+?)"').findall(link)
                for addon_name,addon_id,directory,url_zip,description in match:
                    if addon_id == 'plugin.video.elementum' and elementum == 'false':
                        pass
                    elif addon_id == 'script.module.six' and youtube == 'false':
                        pass
                    elif addon_id == 'plugin.video.youtube' and youtube == 'false':
                        pass
                    else:
                        existe = kodi_translate_path(directory)
                        #print('Path dir:'+existe)
                        if os.path.exists(existe)==False:
                            install_wizard(addon_name,addon_id,url_zip,directory,description)
                            if addon_id == 'plugin.video.elementum':
                                xbmcgui.Dialog().ok()
                        else:
                            pass
        elif check_addon == 'true':
            #print('nao existe')
            fcheck = open(check_file,'w')
            fcheck.write('1')
            fcheck.close()
            xbmcgui.Dialog().ok()
    except:
        pass


def install_wizard(name,addon_id,url,directory,description):
    try:
        import downloader
        import extract
        import ntpath
        path = kodi_translate_path(os.path.join('special://','home/','addons', 'packages'))
        filename = ntpath.basename(url)
        dp = xbmcgui.DialogProgress()
        dp.create("Romy M3trix","Se descarca "+name+", va rog asteptati....")
        lib=os.path.join(path, filename)
        try:
            os.remove(lib)
        except:
            pass
        downloader.download(url, lib, dp)
        addonfolder = kodi_translate_path(os.path.join('special://','home/','addons'))
        xbmc.sleep(100)
        dp.update(0,"Instalando "+name+", Por Favor Espere")
        try:
            xbmc.executebuiltin("Extract("+lib+","+addonfolder+")")
        except:
            extract.all(lib,addonfolder,dp)
        #############
        #time.sleep(2)
        xbmc.sleep(100)
        xbmc.executebuiltin("XBMC.UpdateLocalAddons()")
        notify(name+' Instalat cu succes!')
        import database
        database.enable_addon(addon_id)
        if addon_id == 'plugin.video.elementum':
            database.enable_addon('repository.elementum')
        #xbmc.executebuiltin("XBMC.Container.Refresh()")
        xbmc.executebuiltin("XBMC.Container.Update()")
        #xbmcgui.Dialog().ok('[B][COLOR white]AVISO[/COLOR][/B]',''+name+' instalado, feche e abra o Kodi novamente')
    except:
        notify('Erro ao baixar o complemento')


def time_convert(timestamp):
    try:
        if timestamp > '':
            dt_object = datetime.fromtimestamp(int(timestamp))
            time_br = dt_object.strftime('%d/%m/%Y às %H:%M:%S')
            return str(time_br)
        else:
            valor = ''
            return valor
    except:
        valor = ''
        return valor

def info_vip():
    username_vip = addon.getSetting('username')
    password_vip = addon.getSetting('password')
    if username_vip > '' and password_vip > '':
        try:
            url_info = url_server_vip.replace('/get.php', '')+'/player_api.php?username=%s&password=%s'%(username_vip,password_vip)
            dados_vip = getRequest2(url_info, '')
            filtrar_info = re.compile('"status":"(.+?)".+?"exp_date":"(.+?)".+?"is_trial":"(.+?)".+?"created_at":"(.+?)".+?max_connections":"(.+?)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(dados_vip)
            if filtrar_info !=[]:
                status = str(filtrar_info[0][0])
                exp_date = str(filtrar_info[0][1])
                trial = str(filtrar_info[0][2])
                created = str(filtrar_info[0][3])
                max_connection = str(filtrar_info[0][4])
                #status do usuario
                if status > '' and status == 'Active':
                    status_result = 'Ativo'
                else:
                    status_result = 'Expirado'
                #Validade do vip
                if exp_date > '':
                    expires = time_convert(str(exp_date))
                else:
                    expires = ''
                #usuario de teste
                if trial > '' and trial == '0':
                    vip_trial = 'Não'
                else:
                    vip_trial = 'Sim'
                #criado
                if created > '':
                    created_time = time_convert(str(created))
                else:
                    created_time = ''
                #limite de conexoes
                if max_connection > '':
                    limite_conexao = max_connection
                else:
                    limite_conexao = ''

                try:
                    xbmcaddon.Addon().setSetting("status_vip", status_result)
                    xbmcaddon.Addon().setSetting("created_at", created_time)
                    xbmcaddon.Addon().setSetting("exp_date", expires)
                    xbmcaddon.Addon().setSetting("is_trial", vip_trial)
                    xbmcaddon.Addon().setSetting("max_connection", limite_conexao)
                except:
                    pass
        except:
            try:
                xbmcaddon.Addon().setSetting("status_vip", '')
                xbmcaddon.Addon().setSetting("created_at", '')
                xbmcaddon.Addon().setSetting("exp_date", '')
                xbmcaddon.Addon().setSetting("is_trial", '')
                xbmcaddon.Addon().setSetting("max_connection", '')
            except:
                pass

def vip():
    username_vip = addon.getSetting('username')
    password_vip = addon.getSetting('password')
    #tipo_servidor = addon.getSetting('servidor')
    vip_menu = addon.getSetting('exibirvip')
    saida_transmissao = addon.getSetting('saida')
    if username_vip > '' and password_vip > '':
        info_vip()
    if int(saida_transmissao) == 1:
        saida_canal = 'm3u8'
    else:
        saida_canal = 'ts'
    if vip_menu == 'true':
        if username_vip > '' and password_vip > '':
            url = ''+url_server_vip+'?username=%s&password=%s&type=m3u_plus&output=%s'%(username_vip,password_vip,saida_canal)
            #addDir(name,url,mode,iconimage,fanart,description)
            addDir(titulo_vip,url,1,thumbnail_vip,fanart_vip,vip_descricao,'','','','','','','','','','','','','','','','')
        else:
            #if tipo_servidor=='Desativado':
            #addDir(name,url,mode,iconimage,fanart,description)
            addDir(titulo_vip,'',9,thumbnail_vip,fanart_vip,vip_descricao,'','','','','','','','','','','','','','','','')

def Pesquisa():
    vq = get_search_string(heading="Digite algo para pesquisar")
    if ( not vq ): return False, 0
    title = urllib.quote_plus(vq)
    addDir('[COLOR white][B]PESQUISAR NOVAMENTE...[/B][/COLOR]','',7,thumb_pesquisar,fanart_pesquisar,desc_pesquisa,'','','','','','','','','','','','','','','','')
    try:
        getData(url_pesquisa+'?pesquisar='+title, '')
    except:
        pass
    xbmcplugin.endOfDirectory(addon_handle)

def SetView(name):
    if name == 'Wall':
        try:
            pass
        except:
            pass
    if name == 'List':
        try:
            pass
        except:
            pass
    if name == 'Poster':
        try:
            pass
        except:
            pass
    if name == 'Shift':
        try:
            pass
        except:
            pass
    if name == 'InfoWall':
        try:
            pass
        except:
            pass
    if name == 'WideList':
        try:
            pass
        except:
            pass
    if name == 'Fanart':
        try:
            pass
        except:
            pass

def vidzstore_name(label):
    label = urllib.unquote_plus(label).replace('/', '').strip()
    label = label.replace('-', ' ')
    label = re.sub(r'\s+', ' ', label)
    return label

def vidzstore_filme(url, fanart):
    if not url.endswith('/'):
        url += '/'

    data = getRequest(url, 1)
    if data == '':
        notify('[COLOR red]Nu s-a putut incarca serverul Filme Online![/COLOR]')
        return False

    output = re.compile('<a href="(output\\.m3u8)">', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    if len(output) > 0:
        movie_name = vidzstore_name(url.rstrip('/').split('/')[-1])
        m3u8_player(movie_name, url + output[0], __icon__, 'Filme Online', '')
        return True

    links = re.compile('<a href="([^"]+)">([^<]+)</a>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    for href, label in links:
        if href == '../' or label == '../':
            continue
        if not href.endswith('/'):
            continue

        next_url = url + href
        item_name = vidzstore_name(label)
        if url == url_vidzstore_filme:
            addDir(item_name.encode('utf-8', 'ignore'), next_url, 21, __icon__, fanart, 'Filme Online', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
        else:
            addLink(item_name.encode('utf-8', 'ignore'), next_url + 'output.m3u8', '', __icon__, fanart, 'Filme Online', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
    return False

def sitefilme_clean(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_unescape(text)
    text = text.replace('🖥️', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def sitefilme_absolute(url):
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('/'):
        return 'https://sitefilme.com' + url
    return url

def sitefilme_details(url):
    data = getRequest(url, 1)
    stream = ''
    subtitle = ''
    title = ''
    thumb = __icon__

    try:
        stream = re.compile(r'hlsSource\s*=\s*"([^"]+?\.m3u8[^"]*)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0]
    except:
        stream = ''
    try:
        subtitle = re.compile(r'subtitleSrc\s*=\s*"([^"]+?\.vtt[^"]*)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0]
    except:
        subtitle = ''
    try:
        title = sitefilme_clean(re.compile(r'<h1[^>]*>(.*?)</h1>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0])
    except:
        title = sitefilme_clean(url.rstrip('/').split('/')[-1])
    try:
        thumb = sitefilme_absolute(re.compile(r'<meta\s+property="og:image"\s+content="([^"]+)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0])
    except:
        try:
            thumb = sitefilme_absolute(re.compile(r'<img[^>]+src="([^"]+)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0])
        except:
            thumb = __icon__

    return title, stream, subtitle, thumb

def sitefilme_play(url, fanart):
    title, stream, subtitle, thumb = sitefilme_details(url)
    if stream == '':
        notify('[COLOR red]Nu s-a gasit linkul video pe SiteFilme![/COLOR]')
        return False
    m3u8_player(title, stream, thumb, 'Filme Online', subtitle)
    return True

def sitefilme_filme(url, fanart):
    if '/online/' in url:
        return sitefilme_play(url, fanart)

    data = getRequest(url, 1)
    if data == '':
        notify('[COLOR red]Nu s-a putut incarca SiteFilme![/COLOR]')
        return False

    posts = re.compile(r'<div\s+class="post"[\s\S]*?(?=<div\s+class="post"|<div\s+class="clear")', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    added = []
    for post in posts:
        try:
            movie_url = sitefilme_absolute(re.compile(r'<a\s+href="(https://sitefilme\.com/online/[^"]+/?)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(post)[0])
        except:
            continue
        if movie_url in added:
            continue
        added.append(movie_url)

        title, stream, subtitle, detail_thumb = sitefilme_details(movie_url)
        if title == '':
            title = 'Film SiteFilme ' + sitefilme_clean(movie_url.rstrip('/').split('/')[-1])
        if stream == '':
            continue
        if detail_thumb != __icon__:
            thumb = detail_thumb
        else:
            try:
                thumb = sitefilme_absolute(re.compile(r'<img[^>]+src="([^"]+)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(post)[0])
            except:
                thumb = __icon__
        try:
            genre = sitefilme_clean(re.compile(r'<div\s+class="post-title">(?!\s*<a[\s\S]*?</a>)(.*?)</div>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(post)[0])
        except:
            genre = ''

        addLink(title.encode('utf-8', 'ignore'), stream, subtitle, thumb, fanart, 'Filme Online', genre, '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

    try:
        next_page = sitefilme_absolute(re.compile(r'<a\s+href="([^"]+)"\s+class="nextback">\s*Inainte', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0])
        addDir('[COLOR aqua][B]Pagina urmatoare[/B][/COLOR]', next_page, 22, __icon__, fanart, 'Filme Online', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
    except:
        pass

    return False

def portalultautv_clean(text):
    text = re.sub(r'<script[\s\S]*?</script>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<style[\s\S]*?</style>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def portalultautv_absolute(url, base=url_portalultautv):
    url = html_unescape(url or '').strip()
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('/'):
        return url_portalultautv.rstrip('/') + url
    if not url.startswith('http') and base:
        return base.rstrip('/') + '/' + url.lstrip('/')
    return url

def portalultautv_is_adult(title, url):
    check = (title + ' ' + url).lower()
    adult_words = ['erotice', 'erotic', 'xxx', 'adult', 'porno', 'porn']
    return any(word in check for word in adult_words)

def portalultautv_list_categories():
    data = getRequest(url_portalultautv, 1)
    if data == '':
        notify('[COLOR red]Nu s-a putut incarca Filme Online 2![/COLOR]')
        return False

    wanted = [
        'Actiune', 'Animatie', 'Aventura', 'Biografie', 'Comedie', 'Crima',
        'Documentar', 'Drama', 'Familie', 'Fantezie', 'Groaza', 'Indiene',
        'Istorice', 'Mister', 'Muzicale', 'Online', 'Razboi', 'Romance',
        'Romanesc', 'Romanesti', 'Romantice', 'Seriale', 'Seriale Online',
        'SF', 'Sport', 'Thriller', 'Western'
    ]
    wanted_map = dict((name.lower(), name) for name in wanted)
    added = []
    anchors = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    for href, label_html in anchors:
        label = portalultautv_clean(label_html)
        key = label.lower()
        if key not in wanted_map:
            continue
        cat_url = portalultautv_absolute(href)
        if portalultautv_is_adult(label, cat_url) or cat_url in added:
            continue
        added.append(cat_url)
        addDir(wanted_map[key].encode('utf-8', 'ignore'), cat_url, 35, thumb_portalultautv, fanart_daddylive, 'Filme Online 2', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

    if not added:
        notify('[COLOR red]Nu am gasit categoriile Filme Online 2![/COLOR]')
    xbmcplugin.setContent(addon_handle, 'videos')
    return False

def portalultautv_post_thumb(block):
    for pattern in [
        r'data-lazy-src=["\']([^"\']+)["\']',
        r'<noscript>[\s\S]*?<img[^>]+src=["\']([^"\']+)["\']',
        r'<img[^>]+src=["\']([^"\']+)["\']',
        r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']'
    ]:
        try:
            thumb = re.compile(pattern, re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(block)[0]
            if thumb and 'data:image/svg' not in thumb:
                return portalultautv_absolute(thumb)
        except:
            pass
    return __icon__

def portalultautv_list_films(url, fanart):
    data = getRequest(url, 1)
    if data == '':
        notify('[COLOR red]Nu s-a putut incarca Filme Online 2![/COLOR]')
        return False

    is_adult = url.startswith(url_portalultautv_adult)
    section_name = 'Filme XXX 3' if is_adult else 'Filme Online 2'
    fallback_thumb = thumb_portalultautv_adult if is_adult else thumb_portalultautv
    mode = 36
    posts = re.compile(r'<article\b[\s\S]*?</article>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    added = []
    for post in posts:
        try:
            movie_url = re.compile(r'<h2[^>]+class=["\'][^"\']*entry-title[^"\']*["\'][\s\S]*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(post)[0]
            title = portalultautv_clean(movie_url[1])
            movie_url = portalultautv_absolute(movie_url[0])
        except:
            try:
                movie_url = portalultautv_absolute(re.compile(r'<a[^>]+class=["\'][^"\']*wp-post-image-link[^"\']*["\'][^>]+href=["\']([^"\']+)["\']', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(post)[0])
                title = portalultautv_clean(movie_url.rstrip('/').split('/')[-1].replace('-', ' '))
            except:
                continue
        if movie_url in added:
            continue
        if not is_adult and portalultautv_is_adult(title, movie_url):
            continue
        added.append(movie_url)
        thumb = portalultautv_post_thumb(post)
        if thumb == __icon__:
            thumb = fallback_thumb
        try:
            plot = portalultautv_clean(re.compile(r'<div[^>]+class=["\'][^"\']*entry-content[^"\']*["\'][^>]*>([\s\S]*?)</div>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(post)[0])
        except:
            plot = section_name
        addDir(title.encode('utf-8', 'ignore'), movie_url, mode, thumb, fanart, plot.encode('utf-8', 'ignore'), section_name, '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', folder=False)

    try:
        next_page = ''
        patterns = [
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']next["\']',
            r'<link[^>]+rel=["\']next["\'][^>]+href=["\']([^"\']+)["\']',
            r'class=["\'][^"\']*next[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
            r'href=["\']([^"\']+/page/\d+/?)["\']'
        ]
        for p in patterns:
            m = re.compile(p, re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
            if m:
                next_page = m[0]
                break

        if next_page:
            addDir('[COLOR aqua][B]Pagina urmatoare[/B][/COLOR]', portalultautv_absolute(next_page, url), 35, fallback_thumb, fanart, section_name, '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
    except:
        pass

    if not added:
        notify('[COLOR red]Nu am gasit filme in %s![/COLOR]' % section_name)
    xbmcplugin.setContent(addon_handle, 'movies')
    return False

def portalultautv_vidara_stream(embed_url):
    match = re.search(r'/e/([^/?#]+)', embed_url)
    if not match:
        return '', '', ''
    filecode = match.group(1)
    try:
        headers = {
            'User-Agent': useragent,
            'Referer': embed_url,
            'Origin': 'https://vidara.to',
            'Content-Type': 'application/json'
        }
        response = requests.post('https://vidara.to/api/stream', headers=headers, json={'filecode': filecode, 'device': 'web'}, timeout=20)
        data = response.json()
        stream = data.get('streaming_url', '')
        subtitle = ''
        subs = data.get('subtitles', []) or []
        # Prefer Romanian subtitle
        for sub in subs:
            if sub.get('file_path') and 'romanian' in (sub.get('language') or '').lower():
                subtitle = sub.get('file_path')
                break
        if not subtitle:
            for sub in subs:
                if sub.get('file_path'):
                    subtitle = sub.get('file_path')
                    break
        title = data.get('title', '')
        if stream:
            # Adauga headere necesare - Referer e portalultautv nu vidara
            stream = stream + '|User-Agent=' + urllib.quote_plus(useragent) + '&Referer=' + urllib.quote_plus('https://portalultautv.info/')
        return stream, subtitle, title
    except Exception as e:
        try:
            xbmc.log('[RomyLive] Vidara stream error: %s' % e, level=xbmc.LOGWARNING)
        except:
            pass
        return '', '', ''


def _byseqekaho_b64url_decode(s):
    """Base64url decode (URL-safe base64, no padding required)."""
    s = s.replace('-', '+').replace('_', '/')
    pad = 4 - len(s) % 4
    if pad < 4:
        s += '=' * pad
    return base64.b64decode(s)


def _byseqekaho_decrypt_payload(playback):
    """Decripteaza payload AES-256-GCM din raspunsul API byseqekaho."""
    try:
        key_parts = playback.get('key_parts', [])
        if not key_parts:
            return None
        length = len(key_parts)
        version = str(playback.get('version', '')).strip()
        # xi() table: version -> [version_int, 31-version_int]
        tbl = {}
        for n in range(1, 21):
            tbl[str(n)] = [n, 31 - n]
        # Si() - selecteaza indicii
        if version in tbl:
            a_idx, s_idx = tbl[version]
            if 1 <= a_idx <= length and 1 <= s_idx <= length:
                selected = [key_parts[a_idx - 1], key_parts[s_idx - 1]]
                selected = [p for p in selected if isinstance(p, str) and p]
            else:
                selected = key_parts
        else:
            selected = key_parts
        if not selected:
            selected = key_parts
        # ko() - concateneaza bytes
        key_bytes = bytearray()
        for part in selected:
            if part:
                key_bytes.extend(_byseqekaho_b64url_decode(part))
        key_bytes = bytes(key_bytes)
        if len(key_bytes) != 32:
            # Fallback: all parts concat, take first 32
            key_bytes = bytearray()
            for part in key_parts:
                if part:
                    key_bytes.extend(_byseqekaho_b64url_decode(part))
            key_bytes = bytes(key_bytes[:32])
        iv_bytes = _byseqekaho_b64url_decode(playback.get('iv', ''))
        payload_bytes = _byseqekaho_b64url_decode(playback.get('payload', ''))
        # AES-256-GCM decrypt
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(key_bytes)
            decrypted = aesgcm.decrypt(iv_bytes, payload_bytes, None)
            return json.loads(decrypted.decode('utf-8'))
        except ImportError:
            pass
        try:
            from Crypto.Cipher import AES as _AES
            cipher = _AES.new(key_bytes, _AES.MODE_GCM, nonce=iv_bytes)
            tag = payload_bytes[-16:]
            ciphertext = payload_bytes[:-16]
            decrypted = cipher.decrypt_and_verify(ciphertext, tag)
            return json.loads(decrypted.decode('utf-8'))
        except ImportError:
            pass
        try:
            from Cryptodome.Cipher import AES as _AES2
            cipher = _AES2.new(key_bytes, _AES2.MODE_GCM, nonce=iv_bytes)
            tag = payload_bytes[-16:]
            ciphertext = payload_bytes[:-16]
            decrypted = cipher.decrypt_and_verify(ciphertext, tag)
            return json.loads(decrypted.decode('utf-8'))
        except ImportError:
            pass
    except Exception as e:
        try:
            xbmc.log('[RomyLive] Byseqekaho decrypt error: %s' % e, level=xbmc.LOGWARNING)
        except:
            pass
    return None


def portalultautv_byseqekaho_stream(embed_url):
    """Extrage stream URL de pe byseqekaho.com via API si decrypt AES-256-GCM."""
    match = re.search(r'/e/([^/?#]+)', embed_url)
    if not match:
        return '', '', ''
    filecode = match.group(1)
    try:
        api_url = 'https://byseqekaho.com/api/videos/%s/' % filecode
        headers = {
            'User-Agent': useragent,
            'Referer': embed_url,
            'Origin': 'https://byseqekaho.com',
            'Accept': 'application/json'
        }
        resp = requests.get(api_url, headers=headers, timeout=20)
        if resp.status_code != 200:
            return '', '', ''
        data = resp.json()
        title = data.get('title', '')
        playback = data.get('playback')
        if not playback:
            return '', '', ''
        decrypted = _byseqekaho_decrypt_payload(playback)
        if not decrypted:
            return '', '', ''
        sources = decrypted.get('sources', []) or []
        tracks = decrypted.get('tracks', []) or []
        if not sources:
            return '', '', ''
        # Alege cea mai buna calitate
        best = None
        best_h = 0
        for s in sources:
            h = int(s.get('height') or 0)
            if h > best_h:
                best_h = h
                best = s
        if not best:
            best = sources[0]
        stream = best.get('url', '')
        subtitle = ''
        for t in tracks:
            if t.get('file') or t.get('url'):
                subtitle = t.get('file') or t.get('url')
                break
        if stream:
            stream = stream + '|User-Agent=' + urllib.quote_plus(useragent) + '&Referer=' + urllib.quote_plus('https://portalultautv.info/')
        return stream, subtitle, title
    except Exception as e:
        try:
            xbmc.log('[RomyLive] Byseqekaho stream error: %s' % e, level=xbmc.LOGWARNING)
        except:
            pass
        return '', '', ''

def portalultautv_extract_embeds(data, page_url):
    embeds = []
    patterns = [
        r'<iframe[^>]+src=["\']([^"\']+)["\']',
        r'<iframe[^>]+data-lazy-src=["\']([^"\']+)["\']',
        r'<iframe[^>]+data-litespeed-src=["\']([^"\']+)["\']',
        r'<iframe[^>]+data-src=["\']([^"\']+)["\']',
        r'<a[^>]+href=["\']([^"\']*(?:vidara\.to|byseqekaho\.com|playmogo\.com|filemoon\.sx|voe\.sx|dood\.|cacatul\.online|hqq\.ac)[^"\']*)["\']'
    ]
    for pattern in patterns:
        for embed in re.compile(pattern, re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data):
            if embed in ('', 'about:blank') or embed.startswith('javascript:'):
                continue
            embed = portalultautv_absolute(embed, page_url)
            if embed.endswith('/about:blank'):
                continue
            if embed not in embeds:
                embeds.append(embed)
    return embeds

def portalultautv_details(url):
    data = getRequest(url, 1)
    title = portalultautv_clean(url.rstrip('/').split('/')[-1].replace('-', ' '))
    thumb = __icon__
    plot = 'Filme Online 2'
    if data == '':
        return title, thumb, plot, []
    try:
        title = portalultautv_clean(re.compile(r'<h1[^>]+class=["\'][^"\']*entry-title[^"\']*["\'][^>]*>(.*?)</h1>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0])
    except:
        try:
            title = portalultautv_clean(re.compile(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0])
        except:
            pass
    thumb = portalultautv_post_thumb(data)
    if thumb == __icon__:
        thumb = thumb_portalultautv_adult if url.startswith(url_portalultautv_adult) else thumb_portalultautv
    try:
        plot = portalultautv_clean(re.compile(r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']*)["\']', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0])
    except:
        pass
    return title, thumb, plot, portalultautv_extract_embeds(data, url)

def portalultautv_play(url, fanart):
    title, thumb, plot, embeds = portalultautv_details(url)

    # Deduplica embeds (pagina poate contine duplicate)
    seen_embeds = set()
    unique_embeds = []
    for e in embeds:
        if e not in seen_embeds:
            seen_embeds.add(e)
            unique_embeds.append(e)
    embeds = unique_embeds

    if len(embeds) == 0:
        notify('[COLOR red]Nu s-a gasit player video pe PortalulTauTV![/COLOR]')
        xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
        return False

    # Inlocuieste orice domeniu cu path /e/ cu hqq.ac si reda via smr_link_tester
    # Exceptii: domenii cu API propriu
    _known_direct = ('hqq.ac', 'vidara.to', 'byseqekaho.com')
    hqq_embeds = []
    filtered_embeds = []
    for embed in embeds:
        m = re.search(r'https?://[^/]+/e/([^/?#\s]+)', embed)
        if m and not any(d in embed for d in _known_direct):
            hqq_url = 'https://hqq.ac/e/' + m.group(1)
            hqq_embeds.append(hqq_url)
        else:
            filtered_embeds.append(embed)

    if hqq_embeds and not filtered_embeds:
        # Numai HQQ embeds - reda primul via smr_link_tester
        play_url = 'plugin://plugin.video.smr_link_tester/?mode=play_link&link=%s' % urllib.quote_plus(hqq_embeds[0])
        xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
        xbmc.sleep(300)
        xbmc.executebuiltin('RunPlugin(%s)' % play_url)
        return True

    embeds = filtered_embeds if filtered_embeds else embeds
    playable = []
    for embed in embeds:
        stream = ''
        subtitle = ''
        host_title = ''
        if 'vidara.to/' in embed:
            stream, subtitle, host_title = portalultautv_vidara_stream(embed)
        elif 'byseqekaho.com/' in embed:
            stream, subtitle, host_title = portalultautv_byseqekaho_stream(embed)
        if stream:
            playable.append((host_title or title, stream, subtitle, embed))

    if len(playable) == 0:
        for embed in embeds:
            try:
                resolved = resolveurl.resolve(embed)
            except:
                resolved = ''
            if resolved:
                playable.append((title, stream_url_with_headers(resolved, embed), '', embed))

    if len(playable) == 0:
        notify('[COLOR red]Nu s-a putut extrage stream-ul![/COLOR]')
        xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
        return False

    # Alege sursa daca sunt mai multe
    chosen = None
    if len(playable) == 1:
        chosen = playable[0]
    else:
        dialog = xbmcgui.Dialog()
        labels = ['%s - Sursa %d' % (p[0] or title, i+1) for i, p in enumerate(playable)]
        idx = dialog.select('Selecteaza sursa', labels)
        if idx >= 0:
            chosen = playable[idx]

    if not chosen:
        xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
        return False

    item_title, stream, subtitle, embed_ref = chosen
    li = xbmcgui.ListItem(item_title, path=stream)
    li.setArt({'icon': thumb, 'thumb': thumb})
    try:
        li.getVideoInfoTag().setTitle(item_title)
        li.getVideoInfoTag().setPlot(plot)
    except:
        li.setInfo(type='video', infoLabels={'Title': item_title, 'plot': plot})
    li.setProperty('IsPlayable', 'true')
    li.setContentLookup(False)
    stream_plain = stream.split('|')[0]
    if '.m3u8' in stream_plain:
        li.setMimeType('application/vnd.apple.mpegurl')
    if subtitle:
        li.setSubtitles([subtitle])
    xbmcplugin.setResolvedUrl(addon_handle, True, li)
    return True

def portalultautv_filme(url, fanart):
    if '/category/' in url or re.search(r'/page/\d+/?$', url, re.IGNORECASE):
        return portalultautv_list_films(url, fanart)
    return portalultautv_play(url, fanart)

def paradisehill_clean(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def paradisehill_absolute(url):
    url = html_unescape(url).strip()
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('/'):
        return url_paradisehill.rstrip('/') + url
    return url

def paradisehill_stream_url(src, referer):
    src = paradisehill_absolute(src.replace('\\/', '/'))
    return src + '|User-Agent=' + urllib.quote_plus(useragent) + '&Referer=' + urllib.quote_plus(referer)

def paradisehill_video_sources(data):
    sources = []
    try:
        video_json = re.compile(r'var\s+videoList\s*=\s*(\[.*?\]);', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0]
        video_json = video_json.replace('\\/', '/')
        videos = json.loads(video_json)
        for video in videos:
            for source in video.get('sources', []):
                src = source.get('src', '')
                if src and src not in sources:
                    sources.append(src)
    except:
        sources = re.compile(r'"src"\s*:\s*"([^"]+?\.(?:mp4|m3u8)[^"]*)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    return sources

def paradisehill_details(data, url):
    title = ''
    thumb = __icon__
    plot = 'Filme XXX 2'
    try:
        title = paradisehill_clean(re.compile(r'<meta\s+property="og:title"\s+content="([^"]+)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0])
    except:
        try:
            title = paradisehill_clean(re.compile(r'<title>(.*?)</title>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0])
        except:
            title = paradisehill_clean(url.rstrip('/').split('/')[-1])
    try:
        thumb = paradisehill_absolute(re.compile(r'<meta\s+property="og:image"\s+content="([^"]+)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0])
    except:
        thumb = __icon__
    try:
        plot = paradisehill_clean(re.compile(r'<meta\s+property="og:description"\s+content="([^"]*)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0])
    except:
        pass
    return title, thumb, plot

def paradisehill_list_categories(url, fanart):
    data = getRequest(url, 1)
    if data == '':
        notify('[COLOR red]Nu s-a putut incarca Filme XXX 2![/COLOR]')
        return False

    addDir('[COLOR aqua][B]Toate filmele[/B][/COLOR]', url_paradisehill + 'all/?sort=created_at', 26, __icon__, fanart, 'Filme XXX 2', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

    added = []
    categories = re.compile(r'<a\s+href="([^"]*/category/[^"]+)"[\s\S]*?<img[^>]+src="([^"]+)"[^>]+alt="([^"]+)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    for href, image, label in categories:
        cat_url = paradisehill_absolute(href)
        if cat_url in added:
            continue
        added.append(cat_url)
        title = paradisehill_clean(label) or paradisehill_clean(cat_url.rstrip('/').split('/')[-1])
        thumb = paradisehill_absolute(image)
        addDir(title.encode('utf-8', 'ignore'), cat_url, 26, thumb, fanart, 'Filme XXX 2', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
    return False

def paradisehill_list_films(url, fanart):
    data = getRequest(url, 1)
    if data == '':
        notify('[COLOR red]Nu s-a putut incarca Filme XXX 2![/COLOR]')
        return False

    blocks = re.compile(r'<div\s+class="item\s+list-film-item"[\s\S]*?</div>\s*</div>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)
    added = []
    for block in blocks:
        try:
            movie_url = paradisehill_absolute(re.compile(r'<a\s+href="([^"]+)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(block)[0])
        except:
            continue
        if movie_url in added:
            continue
        added.append(movie_url)
        try:
            title = paradisehill_clean(re.compile(r'itemprop="name"[^>]*>(.*?)</span>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(block)[0])
        except:
            try:
                title = paradisehill_clean(re.compile(r'alt="([^"]+)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(block)[0])
            except:
                title = paradisehill_clean(movie_url.rstrip('/').split('/')[-1])
        try:
            thumb = paradisehill_absolute(re.compile(r'<img[^>]+src="([^"]+)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(block)[0])
        except:
            thumb = __icon__
        try:
            genre = paradisehill_clean(re.compile(r'itemprop="genre"[^>]*>(.*?)</span>', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(block)[0])
        except:
            genre = ''
        addDir(title.encode('utf-8', 'ignore'), movie_url, 27, thumb, fanart, genre or 'Filme XXX 2', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

    try:
        next_page = paradisehill_absolute(re.compile(r'<li\s+class="next">\s*<a\s+href="([^"]+)"', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(data)[0])
        addDir('[COLOR aqua][B]Pagina urmatoare[/B][/COLOR]', next_page, 26, __icon__, fanart, 'Filme XXX 2', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
    except:
        pass
    return False

def paradisehill_play(url, fanart):
    data = getRequest(url, 1)
    if data == '':
        notify('[COLOR red]Nu s-a putut incarca filmul Filme XXX 2![/COLOR]')
        return False
    title, thumb, plot = paradisehill_details(data, url)
    sources = paradisehill_video_sources(data)
    if len(sources) == 0:
        notify('[COLOR red]Nu s-a gasit link video pe Filme XXX 2![/COLOR]')
        return False
    if len(sources) == 1:
        individual_player(title, paradisehill_stream_url(sources[0], url), thumb, plot, '')
        return True
    index = 1
    for src in sources:
        part_name = '%s - Partea %s' % (title, index)
        addLink(part_name.encode('utf-8', 'ignore'), paradisehill_stream_url(src, url), '', thumb, fanart, plot, '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
        index += 1
    xbmcplugin.setContent(addon_handle, 'videos')
    return False

def paradisehill_filme(url, fanart):
    if not url.endswith('/') and '?' not in url:
        url += '/'
    if '/categories/' in url:
        return paradisehill_list_categories(url, fanart)
    if re.search(r'/[0-9a-f]{8,}/?$', url, re.IGNORECASE):
        return paradisehill_play(url, fanart)
    return paradisehill_list_films(url, fanart)

def sportsonline_channel_name(stream_url):
    match = re.search(r'/channels/([^/]+)/([^/.]+)\.php', stream_url, re.IGNORECASE)
    if not match:
        return 'SportsOnline.Vc'
    group = match.group(1).upper()
    channel = match.group(2).upper()
    return channel if group == 'HD' else channel.replace('SPORTTV', 'SPORT TV ')

def sportsonline_clean(text):
    try:
        text = html_unescape(text)
    except:
        pass
    return re.sub(r'\s+', ' ', text).strip()

def sportsonline_b64decode(text):
    if not text:
        return ''
    try:
        missing = len(text) % 4
        if missing:
            text += '=' * (4 - missing)
        data = base64.b64decode(text)
        try:
            return data.decode('utf-8')
        except:
            return data
    except:
        return ''

def sportsonline_decode_config(encoded):
    decoded = sportsonline_b64decode(encoded)
    if not decoded:
        return {}
    order = [2, 0, 3, 1]
    chunk_len = int((len(decoded) + 3) / 4)
    chunks = []
    for index in range(4):
        start = index * chunk_len
        chunks.append(decoded[start:start + chunk_len])
    parts = ['', '', '', '']
    for index, chunk in enumerate(chunks):
        if len(chunk) > 3:
            chunk = chunk[:3] + chunk[4:]
        parts[order[index]] = sportsonline_b64decode(chunk)
    json_data = sportsonline_b64decode(''.join(parts))
    try:
        return json.loads(json_data)
    except:
        return {}

def sportsonline_list_events():
    data = resolve_data(url_sportsonline_prog)
    if not data:
        notify('[COLOR red]Nu pot incarca SportsOnline.Vc[/COLOR]')
        return
    current_day = ''
    count = 0
    for raw_line in data.splitlines():
        line = sportsonline_clean(raw_line)
        if not line:
            continue
        if not line.startswith('HD') and not line.startswith('BR') and not line.startswith('PT') and re.match(r'^[A-Z]+$', line):
            current_day = line.title()
            continue
        match = re.match(r'^(\d{1,2}:\d{2})\s+(.+?)\s+\|\s+(https?://\S+)', line)
        if not match:
            continue
        hour = match.group(1)
        event = sportsonline_clean(match.group(2))
        stream_url = match.group(3).strip()
        channel = sportsonline_channel_name(stream_url)
        day_prefix = current_day + ' ' if current_day else ''
        label = '[COLOR white][B]%s%s[/B][/COLOR] [COLOR aqua]%s[/COLOR] - %s' % (day_prefix, hour, channel, event)
        plot = 'SportsOnline.Vc\n%s%s\n%s\n%s' % (day_prefix, hour, event, stream_url)
        addDir2(label.encode('utf-8', 'ignore'), stream_url, 28, '', thumb_sportsonline, fanart or '', plot.encode('utf-8', 'ignore'), 'Sport', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', False)
        count += 1
    if count == 0:
        addDir('[COLOR red][B]SportsOnline.Vc - fara evenimente gasite[/B][/COLOR]', '', 5, thumb_sportsonline, fanart or '', 'Nu am gasit linii de program valide in prog.txt.', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

def sportsonline_resolve_stream(page_url):
    stream = page_url
    try:
        data = getRequest2(page_url, 'https://sportsonline.vc/', useragent)
        iframe = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE).findall(data)
        if iframe:
            iframe_url = iframe[0]
            iframe_data = getRequest2(iframe_url, page_url, useragent)
            direct = re.compile(r'(https?://[^"\']+?\.m3u8[^"\'<\s]*)', re.IGNORECASE).findall(iframe_data)
            if direct:
                stream = direct[0]
            else:
                config = re.compile(r"window\._econfig='([^']+)'", re.IGNORECASE).findall(iframe_data)
                config_data = sportsonline_decode_config(config[0]) if config else {}
                stream = config_data.get('stream_url_nop2p') or config_data.get('stream_url') or iframe_url
            if stream and '.m3u8' in stream and '|' not in stream:
                stream += '|Referer=' + urllib.quote_plus(iframe_url) + '&User-Agent=' + urllib.quote_plus(useragent)
    except:
        stream = page_url
    if '|' not in stream:
        stream += '|Referer=https://sportsonline.vc/&User-Agent=' + urllib.quote_plus(useragent)
    return stream

def sportsonline_play(name, url, iconimage, description, subtitle):
    stream = sportsonline_resolve_stream(url)
    m3u8_player(name or 'SportsOnline.Vc', stream, iconimage or thumb_sportsonline, description or 'SportsOnline.Vc', subtitle or '')


def vavoo_headers(referer=None):
    return {
        'User-Agent': vavoo_useragent,
        'Accept': 'application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.8,ro;q=0.6',
        'Referer': referer or url_vavoo_main
    }

def vavoo_catalog_headers(signature):
    return {
        'content-type': 'application/json; charset=utf-8',
        'mediahubmx-signature': signature,
        'user-agent': 'MediaHubMX/2',
        'accept': '*/*',
        'Accept-Language': 'de',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'close'
    }

def vavoo_ping_payload():
    current = int(time.time() * 1000)
    return {
        'reason': 'app-focus',
        'locale': 'de',
        'theme': 'dark',
        'metadata': {
            'device': {'type': 'desktop', 'uniqueId': 'kodi-romylive-%s' % current},
            'os': {'name': 'windows', 'version': 'Windows', 'abis': ['x64'], 'host': 'kodi'},
            'app': {'platform': 'electron'},
            'version': {'package': 'tv.vavoo.app', 'binary': '3.1.8', 'js': '3.1.8'}
        },
        'appFocusTime': 0,
        'playerActive': False,
        'playDuration': 0,
        'devMode': False,
        'hasAddon': True,
        'castConnected': False,
        'package': 'tv.vavoo.app',
        'version': '3.1.8',
        'process': 'app',
        'firstAppStart': current,
        'lastAppStart': current,
        'ipLocation': None,
        'adblockEnabled': True,
        'proxy': {'supported': ['ss'], 'engine': 'Mu', 'enabled': False, 'autoServer': True},
        'iap': {'supported': False}
    }

def vavoo_get_signature():
    global _vavoo_signature_cache
    if _vavoo_signature_cache:
        return _vavoo_signature_cache
    for ping_url in vavoo_ping_urls:
        try:
            r = requests.post(ping_url, json=vavoo_ping_payload(), timeout=25, verify=False)
            if r.status_code == 200:
                data = r.json()
                sig = data.get('addonSig', '')
                if sig:
                    _vavoo_signature_cache = sig
                    return sig
        except:
            pass
    return ''

def vavoo_extract_country(group):
    group = sportsonline_clean(group or '')
    if not group:
        return 'default'
    for sep in ['➾', '⟾', '->', '→', '»', '›']:
        if sep in group:
            return sportsonline_clean(group.split(sep)[0]) or 'default'
    return group

def vavoo_map_catalog_item(item):
    ids = item.get('ids', {}) if isinstance(item.get('ids', {}), dict) else {}
    return {
        'id': str(ids.get('id') or item.get('id') or item.get('url') or ''),
        'url': item.get('url', ''),
        'name': item.get('name', 'VaVooTV'),
        'country': vavoo_extract_country(item.get('group', '')),
        'logo': item.get('logo', ''),
        'p': 0
    }

def vavoo_country_code(country):
    codes = {
        'Albania': 'al',
        'Arabia': 'sa',
        'Balkans': 'ba',
        'Bulgaria': 'bg',
        'Croatia': 'hr',
        'France': 'fr',
        'France Sport': 'fr',
        'Germany': 'de',
        'Italy': 'it',
        'Netherlands': 'nl',
        'Poland': 'pl',
        'Portugal': 'pt',
        'Romania': 'ro',
        'Russia': 'ru',
        'Spain': 'es',
        'Turkey': 'tr',
        'United Kingdom': 'gb'
    }
    return codes.get(country, 'un')

def vavoo_flag(country):
    code = vavoo_country_code(country)
    if code == 'un':
        return thumb_vavoo
    return 'https://flagcdn.com/w320/%s.png' % code

def vavoo_clean_name(name):
    return sportsonline_clean(re.sub(r'\s+\(\d+\)$', '', name or 'VaVooTV'))

def vavoo_load_channels():
    global _vavoo_channels_cache
    if _vavoo_channels_cache is not None:
        return _vavoo_channels_cache
    sig = vavoo_get_signature()
    if sig:
        for base_site in vavoo_base_sites:
            try:
                channels = []
                cursor = None
                catalog_url = base_site.rstrip('/') + '/mediahubmx-catalog.json'
                headers = vavoo_catalog_headers(sig)
                while True:
                    body = {
                        'language': 'de',
                        'region': 'US',
                        'catalogId': 'iptv',
                        'id': 'iptv',
                        'adult': False,
                        'search': '',
                        'sort': '',
                        'filter': {},
                        'cursor': cursor,
                        'clientVersion': '3.0.2'
                    }
                    r = requests.post(catalog_url, headers=headers, json=body, timeout=30, verify=False)
                    if r.status_code != 200:
                        break
                    data = r.json()
                    for item in data.get('items', []) or []:
                        if item.get('type') == 'iptv' and item.get('url'):
                            channels.append(vavoo_map_catalog_item(item))
                    cursor = data.get('nextCursor')
                    if not cursor:
                        break
                if channels:
                    _vavoo_channels_cache = channels
                    return channels
            except:
                pass
    try:
        r = requests.get(url_vavoo_channels, headers=vavoo_headers(), timeout=30, verify=False)
        if r.status_code != 200:
            return []
        data = json.loads(r.text)
        if isinstance(data, list):
            _vavoo_channels_cache = data
            return data
    except:
        pass
    _vavoo_channels_cache = []
    return []

def vavoo_ordered_countries(channels):
    countries = sorted(set([c.get('country', '') for c in channels if c.get('country', '')]))
    if 'Romania' in countries:
        countries.remove('Romania')
        countries.insert(0, 'Romania')
    return countries

def vavoo_list_countries():
    channels = vavoo_load_channels()
    if not channels:
        notify('[COLOR red]Nu pot incarca VaVooTV[/COLOR]')
        addDir('[COLOR red][B]VaVooTV - fara tari[/B][/COLOR]', '', 5, thumb_vavoo, fanart or fanart_daddylive, 'Nu am putut incarca lista de canale vavoo.to.', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
        return
    counts = {}
    for channel in channels:
        country = channel.get('country', '')
        if country:
            counts[country] = counts.get(country, 0) + 1
    for country in vavoo_ordered_countries(channels):
        thumb = vavoo_flag(country)
        label = '[COLOR white][B]%s[/B][/COLOR] [COLOR aqua](%s)[/COLOR]' % (country, counts.get(country, 0))
        plot = 'VaVooTV - %s\n%s canale' % (country, counts.get(country, 0))
        addDir2(label.encode('utf-8', 'ignore'), country, 32, '', thumb, fanart or fanart_daddylive, plot.encode('utf-8', 'ignore'), 'TV', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', True)

def vavoo_list_channels(country):
    channels = [c for c in vavoo_load_channels() if c.get('country', '') == country]
    if not channels:
        notify('[COLOR red]Nu gasesc canale VaVooTV[/COLOR]')
        addDir('[COLOR red][B]VaVooTV - fara canale[/B][/COLOR]', '', 5, vavoo_flag(country), fanart or fanart_daddylive, 'Nu am gasit canale pentru %s.' % country, '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
        return
    try:
        channels.sort(key=lambda c: (int(c.get('p', 999999)), vavoo_clean_name(c.get('name', ''))))
    except:
        channels.sort(key=lambda c: vavoo_clean_name(c.get('name', '')))
    thumb = vavoo_flag(country)
    for channel in channels:
        cid = str(channel.get('id', ''))
        cname = vavoo_clean_name(channel.get('name', 'VaVooTV'))
        if not cid:
            continue
        label = '[COLOR white][B]%s[/B][/COLOR]' % cname
        plot = 'VaVooTV\n%s\n%s\nID: %s' % (country, cname, cid)
        addDir2(label.encode('utf-8', 'ignore'), cid, 33, '', thumb, fanart or fanart_daddylive, plot.encode('utf-8', 'ignore'), 'TV', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', False)

def vavoo_stream_url(channel_id):
    channel = None
    for item in vavoo_load_channels():
        if str(item.get('id', '')) == str(channel_id):
            channel = item
            break
    if not channel:
        return ''
    sig = vavoo_get_signature()
    if not sig:
        return ''
    for base_site in vavoo_base_sites:
        try:
            r = requests.post(
                base_site.rstrip('/') + '/mediahubmx-resolve.json',
                headers=vavoo_catalog_headers(sig),
                json={'language': 'de', 'region': 'US', 'url': channel.get('url', ''), 'clientVersion': '3.0.2'},
                timeout=25,
                verify=False
            )
            if r.status_code != 200:
                continue
            data = r.json()
            stream = ''
            if isinstance(data, list) and data and isinstance(data[0], dict):
                stream = data[0].get('url', '')
            elif isinstance(data, dict):
                stream = data.get('url', '') or data.get('streamUrl', '')
            if stream:
                return stream + '|User-Agent=' + urllib.quote_plus('VAVOO/2.6') + '&verifypeer=false&verify=false&ssl_verify=false'
        except:
            pass
    return ''

def vavoo_play(name, channel_id, iconimage, description, subtitle):
    stream = vavoo_stream_url(channel_id)
    if not stream:
        notify('[COLOR red]VaVooTV nu poate rezolva streamul[/COLOR]')
        return
    m3u8_player(name or 'VaVooTV', stream, iconimage or thumb_vavoo, description or 'VaVooTV', subtitle or '')


def rojadirecta_headers(referer=None):
    return {
        'User-Agent': useragent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.8,ro;q=0.6,es;q=0.5',
        'Referer': referer or url_rojadirecta_main
    }

def rojadirecta_abs_url(url, base=url_rojadirecta_main):
    if not url:
        return ''
    url = html_unescape(url).replace('\\/', '/').replace('\/', '/').replace('&amp;', '&').strip()
    if url.startswith('//'):
        return 'https:' + url
    try:
        return urllib.urljoin(base, url)
    except:
        if url.startswith('/'):
            return url_rojadirecta_main.rstrip('/') + url
        if not url.startswith('http'):
            return base.rstrip('/') + '/' + url.lstrip('/')
        return url

def rojadirecta_clean(text):
    try:
        text = html_unescape(text)
    except:
        pass
    text = re.sub(r'<span class=["\']es["\'][^>]*>.*?</span>', '', text, flags=re.I|re.S)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def rojadirecta_load_page(url, referer=None):
    try:
        r = requests.get(url, headers=rojadirecta_headers(referer), timeout=25, allow_redirects=True)
        if not r.encoding or r.encoding.lower() == 'iso-8859-1':
            r.encoding = 'iso-8859-1'
        if r.status_code >= 400:
            return '', r.url
        return r.text, r.url
    except:
        try:
            data = getRequest2(url, referer or url_rojadirecta_main, useragent)
            return data or '', url
        except:
            return '', url

def rojadirecta_event_blocks(data):
    matches = list(re.finditer(r'<span\s+class=["\']\d+["\'][^>]+SportsEvent[^>]*>', data, re.I))
    blocks = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(data)
        blocks.append(data[match.start():end])
    return blocks

def rojadirecta_source_available(url):
    if not url:
        return False
    if url in _rojadirecta_source_cache:
        return _rojadirecta_source_cache[url]
    if 'sebnsc.dad/' not in url:
        _rojadirecta_source_cache[url] = True
        return True
    try:
        r = requests.get(url, headers=rojadirecta_headers(url_rojadirecta_main), timeout=8, allow_redirects=True)
        available = r.status_code < 400
    except:
        available = False
    _rojadirecta_source_cache[url] = available
    return available

def rojadirecta_list_events():
    data, final_url = rojadirecta_load_page(url_rojadirecta_main)
    if not data:
        notify('[COLOR red]Nu pot incarca RojaDirecta[/COLOR]')
        addDir('[COLOR red][B]RojaDirecta - eroare la incarcare[/B][/COLOR]', '', 5, thumb_rojadirecta, fanart or fanart_daddylive, 'Pagina RojaDirecta nu a putut fi incarcata.', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
        return
    count = 0
    for block in rojadirecta_event_blocks(data):
        menu = re_me(block, r'<div[^>]+class=["\']menutitle["\'][^>]*>(.*?)</div>')
        event_name = rojadirecta_clean(re_me(menu, r'itemprop=["\']name["\'][^>]*>(.*?)</span>')) or 'RojaDirecta'
        hour = rojadirecta_clean(re_me(menu, r'<span[^>]+class=["\']t["\'][^>]*>(.*?)</span>'))
        sport_en = re.findall(r'<span[^>]+class=["\']en["\'][^>]*>(.*?)</span>', menu, re.I|re.S)
        sport = rojadirecta_clean(sport_en[0]) if sport_en else 'Sport'
        date_value = re_me(menu, r'itemprop=["\']startDate["\'][^>]+content=["\']([^"\']+)')
        rows = re.findall(r'<tr>(.*?)</tr>', block, re.I|re.S)
        source_index = 1
        for row in rows:
            href = re_me(row, r'<a[^>]+href=["\']([^"\']+)')
            if not href or 'rojadirecta.eu/' in href:
                continue
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.I|re.S)
            source_name = ''
            lang = ''
            stream_type = ''
            if len(cells) >= 5:
                source_name = rojadirecta_clean(cells[1])
                lang = rojadirecta_clean(cells[2])
                stream_type = rojadirecta_clean(cells[3])
            stream_url = rojadirecta_abs_url(href, final_url)
            if not rojadirecta_source_available(stream_url):
                continue
            source_label = source_name or ('Stream %s' % source_index)
            label = '[COLOR white][B]%s %s[/B][/COLOR] [COLOR aqua]%s[/COLOR] - %s' % (hour, event_name, source_label, sport)
            if lang:
                label += ' [COLOR yellow]%s[/COLOR]' % lang
            plot = 'RojaDirecta\n%s\n%s\n%s\n%s\n%s' % (date_value or hour, sport, source_label, stream_type, stream_url)
            addDir2(label.encode('utf-8', 'ignore'), stream_url, 34, '', thumb_rojadirecta, fanart or fanart_daddylive, plot.encode('utf-8', 'ignore'), 'Sport', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', False)
            count += 1
            source_index += 1
    if count == 0:
        addDir('[COLOR red][B]RojaDirecta - fara streamuri gasite[/B][/COLOR]', '', 5, thumb_rojadirecta, fanart or fanart_daddylive, 'Pagina s-a incarcat, dar nu am gasit surse Watch/Ver.', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

def rojadirecta_find_m3u8(data, base_url):
    if not data:
        return ''
    data = html_unescape(data).replace('\\/', '/').replace('\/', '/').replace('&amp;', '&')
    config = re.findall(r"window\._econfig='([^']+)'", data, re.I)
    if config:
        config_data = sportsonline_decode_config(config[0])
        stream = config_data.get('stream_url_nop2p') or config_data.get('stream_url') or ''
        if stream:
            return rojadirecta_abs_url(stream, base_url)
    encoded_src = re.findall(r'src%3A%20%22((?:https?:)?//[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^"\'<>\s\\]*?\.m3u8[^"\'<>\s\\]*)', data, re.I)
    if encoded_src:
        stream = re.split(r'(?i)%22|%27|%0A|%0D|%3C|%7D|%2C', encoded_src[0])[0]
        return rojadirecta_abs_url(stream, base_url)
    direct = re.findall(r'((?:https?:)?//[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^"\'<>\s\\]*?\.m3u8[^"\'<>\s\\]*)', data, re.I)
    if direct:
        stream = re.split(r'(?i)%22|%27|%0A|%0D|%3C|%7D|%2C', direct[0])[0]
        return rojadirecta_abs_url(stream, base_url)
    relative = re.findall(r'["\']([^"\']+?\.m3u8[^"\']*)["\']', data, re.I)
    if relative:
        return rojadirecta_abs_url(relative[0], base_url)
    try:
        decoded_data = urllib.unquote(data)
        direct = re.findall(r'((?:https?:)?//[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^"\'<>\s\\]*?\.m3u8[^"\'<>\s\\]*)', decoded_data, re.I)
        if direct:
            return rojadirecta_abs_url(direct[0], base_url)
    except:
        pass
    return ''

def rojadirecta_resolve_stream(page_url, depth=0, referer=url_rojadirecta_main, seen=None):
    if seen is None:
        seen = set()
    if not page_url or depth > 4:
        return ''
    page_url = rojadirecta_abs_url(page_url, referer)
    if page_url in seen:
        return ''
    seen.add(page_url)
    if '.m3u8' in page_url.lower():
        origin = ''
        try:
            parsed = urllib.urlparse(referer)
            origin = parsed.scheme + '://' + parsed.netloc
        except:
            pass
        headers = 'Referer=' + urllib.quote_plus(referer) + '&User-Agent=' + urllib.quote_plus(useragent)
        if origin:
            headers += '&Origin=' + urllib.quote_plus(origin)
        headers += '&verifypeer=false'
        return page_url + '|' + headers
    data, final_url = rojadirecta_load_page(page_url, referer)
    stream = rojadirecta_find_m3u8(data, final_url)
    if stream:
        origin = ''
        try:
            parsed = urllib.urlparse(final_url)
            origin = parsed.scheme + '://' + parsed.netloc
        except:
            pass
        headers = 'Referer=' + urllib.quote_plus(final_url) + '&User-Agent=' + urllib.quote_plus(useragent)
        if origin:
            headers += '&Origin=' + urllib.quote_plus(origin)
        headers += '&verifypeer=false'
        return stream + '|' + headers
    iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)', data or '', re.I)
    for iframe in iframes:
        iframe_url = rojadirecta_abs_url(iframe, final_url)
        stream = rojadirecta_resolve_stream(iframe_url, depth + 1, final_url, seen)
        if stream:
            return stream
    return ''

def rojadirecta_play(name, url, iconimage, description, subtitle):
    stream = rojadirecta_resolve_stream(url)
    if stream:
        m3u8_player(name or 'RojaDirecta', stream, iconimage or thumb_rojadirecta, description or 'RojaDirecta', subtitle or '')
        return
    notify('[COLOR red]RojaDirecta: stream indisponibil[/COLOR]')
    try:
        xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem(name or 'RojaDirecta'))
    except:
        pass


def streami_headers(referer=None):
    return {
        'User-Agent': streami_useragent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.8,ro;q=0.6',
        'Referer': referer or url_streami_main,
        'X-SSIG': streami_xssig
    }

def streami_abs_url(url, base=url_streami_main):
    if not url:
        return ''
    url = html_unescape(url).replace('\\/', '/').replace('\/', '/').replace('&amp;', '&')
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('/'):
        return 'https://streami.top' + url
    if not url.startswith('http'):
        return base.rstrip('/') + '/' + url.lstrip('/')
    return url

def streami_b64decode(text):
    if not text:
        return ''
    try:
        text = text.strip()
        missing = len(text) % 4
        if missing:
            text += '=' * (4 - missing)
        data = base64.b64decode(text)
        try:
            return data.decode('utf-8')
        except:
            return data
    except:
        return ''

def streami_event_title(event):
    title = event.get('title', '')
    if isinstance(title, dict):
        home = title.get('home', '')
        away = title.get('away', '')
        title = (home + ' - ' + away).strip(' -')
    return sportsonline_clean(title or event.get('league', '') or 'Streami.top')

def streami_event_time(event):
    try:
        return datetime.fromtimestamp(int(event.get('startTime', 0))).strftime('%d.%m %H:%M')
    except:
        return ''

def streami_load_events():
    events = []
    try:
        r = requests.get(url_streami_popular, headers=streami_headers(), timeout=25, verify=False)
        if r.status_code == 200:
            popular = json.loads(r.text)
            if isinstance(popular, list):
                events.extend(popular)
    except:
        pass
    try:
        r = requests.get(url_streami_events, headers=streami_headers(), timeout=25, verify=False)
        if r.status_code == 200:
            decoded = streami_b64decode(r.text)
            main_events = json.loads(decoded)
            if isinstance(main_events, list):
                events.extend(main_events)
    except:
        pass
    unique = []
    seen = set()
    for event in events:
        eid = str(event.get('id', ''))
        key = eid or json.dumps(event, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)
    try:
        unique.sort(key=lambda e: int(e.get('startTime', 0)))
    except:
        pass
    return unique

def streami_list_events():
    events = streami_load_events()
    if not events:
        notify('[COLOR red]Nu pot incarca Streami.top[/COLOR]')
        addDir('[COLOR red][B]Streami.top - fara evenimente[/B][/COLOR]', '', 5, thumb_streami, fanart or '', 'Nu am putut incarca lista de evenimente Streami.top.', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
        return
    count = 0
    for event in events:
        title = streami_event_title(event)
        event_time = streami_event_time(event)
        league = sportsonline_clean(event.get('league', ''))
        for block in event.get('_embeds', []) or []:
            language = sportsonline_clean(block.get('language', 'Streami.top'))
            embeds = block.get('embeds', {}) or {}
            if isinstance(embeds, dict):
                sources = embeds.values()
            else:
                sources = embeds
            for source in sources:
                if not isinstance(source, dict):
                    continue
                embed = streami_abs_url(source.get('embed', ''))
                if not embed:
                    continue
                quality = sportsonline_clean(source.get('label', ''))
                label = '[COLOR white][B]%s[/B][/COLOR] [COLOR aqua]%s[/COLOR] [COLOR yellow]%s[/COLOR] %s' % (event_time, title, quality, language)
                plot = 'Streami.top\n%s\n%s\n%s\n%s' % (event_time, league, language + ' ' + quality, embed)
                addDir2(label.encode('utf-8', 'ignore'), embed, 31, '', thumb_streami, fanart or fanart_daddylive, plot.encode('utf-8', 'ignore'), 'Sport', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', False)
                count += 1
    if count == 0:
        addDir('[COLOR red][B]Streami.top - fara streamuri gasite[/B][/COLOR]', '', 5, thumb_streami, fanart or fanart_daddylive, 'Evenimentele au fost incarcate, dar nu au surse video.', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

def streami_find_m3u8(data, base_url):
    if not data:
        return ''
    data = html_unescape(data).replace('\\/', '/').replace('\/', '/').replace('&amp;', '&')
    direct = re.compile(r'(https?://[^"\'<>\s\\]+?\.m3u8[^"\'<>\s\\]*)', re.IGNORECASE).findall(data)
    if direct:
        return streami_abs_url(direct[0], base_url)
    relative = re.compile(r'["\']([^"\']+?\.m3u8[^"\']*)["\']', re.IGNORECASE).findall(data)
    if relative:
        return streami_abs_url(relative[0], base_url)
    return ''

def streami_resolve_stream(embed_url, depth=0, referer=url_streami_main):
    if not embed_url:
        return ''
    embed_url = streami_abs_url(embed_url, referer)
    if '.m3u8' in embed_url:
        return embed_url + '|Referer=' + urllib.quote_plus(referer) + '&User-Agent=' + urllib.quote_plus(streami_useragent)
    try:
        r = requests.get(embed_url, headers=streami_headers(referer), timeout=25, verify=False, allow_redirects=True)
        data = r.text
        final_url = r.url
        stream = streami_find_m3u8(data, final_url)
        if stream:
            return stream + '|Referer=' + urllib.quote_plus(final_url) + '&User-Agent=' + urllib.quote_plus(streami_useragent)
        if depth < 3:
            iframes = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE).findall(data)
            for iframe in iframes:
                resolved = streami_resolve_stream(streami_abs_url(iframe, final_url), depth + 1, final_url)
                if resolved and '.m3u8' in resolved:
                    return resolved
    except:
        pass
    return embed_url + '|Referer=' + urllib.quote_plus(referer) + '&User-Agent=' + urllib.quote_plus(streami_useragent)

def streami_play(name, url, iconimage, description, subtitle):
    stream = streami_resolve_stream(url)
    if not stream:
        notify('[COLOR red]Streami.top indisponibil[/COLOR]')
        return
    m3u8_player(name or 'Streami.top', stream, iconimage or thumb_streami, description or 'Streami.top', subtitle or '')


# ============================================================
# DaddyLive 24/7 Channels (dlhd.pk) - integration
# ============================================================
def _dl_headers(referer=None, origin=None):
    h = {
        'User-Agent': daddylive_useragent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': referer or (daddylive_base + '/'),
    }
    if origin:
        h['Origin'] = origin
    return h


def _dl_get(url, referer=None, origin=None, timeout=15):
    try:
        return requests.get(url, headers=_dl_headers(referer, origin), timeout=timeout, verify=False)
    except Exception:
        return None


def _dl_norm(s):
    try:
        s = html_unescape(s)
    except Exception:
        pass
    s = re.sub(r'\s+', ' ', s).strip().upper()
    s = re.sub(r'[^A-Z0-9 ]+', '', s)
    return s


def _dl_load_meta():
    """Load StepDaddyLiveHD meta.json (logos + tags) from resources/."""
    global _daddylive_meta_cache
    if _daddylive_meta_cache is not None:
        return _daddylive_meta_cache
    meta_by_norm = {}
    try:
        addon_path = __addon__.getAddonInfo('path')
        try:
            addon_path = xbmcvfs.translatePath(addon_path)
        except Exception:
            pass
        meta_file = os.path.join(addon_path, 'resources', 'daddylive_meta.json')
        with open(meta_file, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        for k, v in raw.items():
            nk = _dl_norm(k)
            if not nk:
                continue
            meta_by_norm[nk] = {
                'logo': (v or {}).get('logo') or '',
                'tags': (v or {}).get('tags') or [],
                'orig_name': k,
            }
    except Exception:
        pass
    _daddylive_meta_cache = meta_by_norm
    return meta_by_norm


def _dl_meta_for(name):
    meta = _dl_load_meta()
    key = _dl_norm(name)
    if key in meta:
        return meta[key]
    # Try without trailing parenthesised qualifier "(Player-01)", "(UK)", etc.
    cleaned = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    key2 = _dl_norm(cleaned)
    if key2 and key2 in meta:
        return meta[key2]
    # Try stripping common trailing country/region/quality suffixes
    suffixes = r'\b(USA|UK|US|MX|DE|FR|IT|ES|PT|BR|AR|TR|GR|RO|RU|UA|NL|BE|PL|CZ|HU|HR|RS|BG|AT|CH|IE|SE|NO|FI|DK|IL|JP|KR|CN|HK|TW|IN|PK|AU|NZ|CA|TURKEY|FRANCE|GERMANY|ITALY|SPAIN|PORTUGAL|BRAZIL|ARGENTINA|GREECE|ROMANIA|RUSSIA|UKRAINE|NETHERLANDS|BELGIUM|POLAND|HUNGARY|CROATIA|SERBIA|BULGARIA|AUSTRIA|SWITZERLAND|IRELAND|SWEDEN|NORWAY|FINLAND|DENMARK|ISRAEL|JAPAN|KOREA|CHINA|TAIWAN|INDIA|PAKISTAN|AUSTRALIA|CANADA|HD|FHD|UHD|4K|PREMIUM|PLUS)\b'
    trimmed = re.sub(suffixes, '', cleaned, flags=re.IGNORECASE)
    trimmed = re.sub(r'\s+', ' ', trimmed).strip()
    key3 = _dl_norm(trimmed)
    if key3 and key3 in meta:
        return meta[key3]
    return {'logo': '', 'tags': [], 'orig_name': ''}


def _dl_decode_bundle(text):
    candidates = []
    patterns = [
        r'JSON\.parse\s*\(\s*atob\s*\(\s*["\']([^"\']{40,})["\']\s*\)\s*\)',
        r'atob\s*\(\s*["\'](eyJ[A-Za-z0-9+/=]{40,})["\']\s*\)',
        r'(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*["\'](eyJ[A-Za-z0-9+/=]{40,})["\']',
        r'["\'](eyJ[A-Za-z0-9+/=]{40,})["\']',
        r'["\']([A-Za-z0-9+/=]{80,})["\']',
    ]
    for pat in patterns:
        try:
            for m in re.findall(pat, text):
                if m not in candidates:
                    candidates.append(m)
        except Exception:
            pass
    for cand in candidates:
        try:
            pad = '=' * (-len(cand) % 4)
            decoded = base64.b64decode(cand + pad).decode('utf-8', 'ignore')
            data = json.loads(decoded)
            if not all(k in data for k in ['b_ts', 'b_sig', 'b_rnd', 'b_host']):
                continue
            out = {}
            for k, v in data.items():
                if isinstance(v, str):
                    try:
                        p2 = '=' * (-len(v) % 4)
                        out[k] = base64.b64decode(v + p2).decode('utf-8', 'ignore')
                    except Exception:
                        out[k] = v
                else:
                    out[k] = v
            return out
        except Exception:
            continue
    return {}


def _dl_load_epg():
    global _daddylive_epg_cache
    if _daddylive_epg_cache is not None:
        return _daddylive_epg_cache
    epg = {'name_to_id': {}, 'programmes': {}}
    try:
        if addon.getSetting('daddylive_epg_enabled') != 'true':
            _daddylive_epg_cache = epg
            return epg
    except Exception:
        _daddylive_epg_cache = epg
        return epg
    try:
        url = addon.getSetting('daddylive_epg_url') or epg_daddylive_url
        r = requests.get(url, headers={'User-Agent': daddylive_useragent}, timeout=30, verify=False)
        if r is None or r.status_code != 200 or not r.content:
            _daddylive_epg_cache = epg
            return epg
        content = r.content
        try:
            import gzip
            from io import BytesIO
            content = gzip.GzipFile(fileobj=BytesIO(content)).read()
        except Exception:
            pass
        text = content.decode('utf-8', 'ignore')
        channel_map = {}
        for cm in re.finditer(r'<channel\s+id="([^"]+)"[^>]*>(.*?)</channel>', text, re.DOTALL):
            cid = cm.group(1)
            block = cm.group(2)
            for nm in re.finditer(r'<display-name[^>]*>([^<]+)</display-name>', block):
                key = _dl_norm(nm.group(1))
                if key:
                    channel_map.setdefault(key, cid)
        progs = {}
        for pm in re.finditer(r'<programme\s+start="([^"]+)"\s+stop="([^"]+)"\s+channel="([^"]+)"[^>]*>(.*?)</programme>', text, re.DOTALL):
            start, stop, cid, block = pm.group(1), pm.group(2), pm.group(3), pm.group(4)
            t = re.search(r'<title[^>]*>([^<]+)</title>', block)
            d = re.search(r'<desc[^>]*>([^<]+)</desc>', block)
            try:
                title = html_unescape(t.group(1)) if t else ''
            except Exception:
                title = t.group(1) if t else ''
            try:
                desc = html_unescape(d.group(1)) if d else ''
            except Exception:
                desc = d.group(1) if d else ''
            progs.setdefault(cid, []).append({'start': start, 'stop': stop, 'title': title, 'desc': desc})
        epg = {'name_to_id': channel_map, 'programmes': progs}
    except Exception:
        pass
    _daddylive_epg_cache = epg
    return epg


def _dl_epg_for_channel(channel_name):
    try:
        epg = _dl_load_epg()
        key = _dl_norm(channel_name)
        cid = epg['name_to_id'].get(key)
        if not cid:
            for k, v in epg['name_to_id'].items():
                if key and (key in k or k in key):
                    cid = v
                    break
        if not cid:
            return ''
        progs = epg['programmes'].get(cid, [])
        if not progs:
            return ''
        try:
            from datetime import datetime as _dt
            now = _dt.utcnow()
        except Exception:
            return ''

        def parse(t):
            m = re.match(r'(\d{14})', t)
            if not m:
                return None
            try:
                return _dt.strptime(m.group(1), '%Y%m%d%H%M%S')
            except Exception:
                return None

        current = None
        upcoming = []
        for p in progs:
            ps = parse(p['start'])
            pe = parse(p['stop'])
            if not ps or not pe:
                continue
            if ps <= now <= pe:
                current = (p, ps, pe)
            elif ps > now:
                upcoming.append((p, ps, pe))
        upcoming = sorted(upcoming, key=lambda x: x[1])[:3]
        lines = []
        if current:
            p, ps, pe = current
            lines.append('[COLOR yellow][B]ACUM:[/B][/COLOR] %s-%s  %s' % (ps.strftime('%H:%M'), pe.strftime('%H:%M'), p['title']))
            if p['desc']:
                lines.append(p['desc'])
        if upcoming:
            lines.append('')
            lines.append('[COLOR aqua][B]URMEAZA:[/B][/COLOR]')
            for p, ps, pe in upcoming:
                lines.append('  %s  %s' % (ps.strftime('%H:%M'), p['title']))
        return '\n'.join(lines)
    except Exception:
        return ''


def _dl_fetch_channels():
    global _daddylive_channels_cache
    if _daddylive_channels_cache is not None:
        return _daddylive_channels_cache
    channels = []
    bases = [daddylive_base, 'https://daddylive.sx', 'https://daddylive.dad', 'https://dlhd.dad']
    text = ''
    for b in bases:
        r = _dl_get(b + '/24-7-channels.php', referer=b + '/')
        if r is not None and r.status_code == 200 and 'watch.php?id=' in (r.text or ''):
            text = r.text
            break
    if not text:
        return channels
    # New dlhd.pk format: <a href="/watch.php?id=NN">CHANNEL NAME ID: NN</a>
    pat = re.compile(r'<a\s[^>]*href=["\']/watch\.php\?id=(\d+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    try:
        hide_18 = addon.getSetting('daddylive_hide_18plus') != 'false'
    except Exception:
        hide_18 = True
    seen = set()
    for cid, raw_name in pat.findall(text):
        if cid in seen:
            continue
        seen.add(cid)
        name = re.sub(r'<[^>]+>', ' ', raw_name)
        try:
            name = html_unescape(name)
        except Exception:
            pass
        name = re.sub(r'\s+', ' ', name).strip()
        # Strip trailing " ID: NN"
        name = re.sub(r'\s*ID:\s*\d+\s*$', '', name, flags=re.IGNORECASE).strip()
        name = name.replace('#', '').strip()
        if not name:
            continue
        if hide_18 and re.match(r'^\s*18\s*\+', name):
            continue
        meta = _dl_meta_for(name)
        logo = meta.get('logo') or ''
        channels.append((cid, name, logo))
    channels.sort(key=lambda x: x[1].upper())
    _daddylive_channels_cache = channels
    return channels



# ===========================================================================
# TVZoneHD implementation (scrape channels + resolve stream via stream.php)
# ===========================================================================
def _tvzone_profile_dir():
    try:
        p = kodi_translate_path(xbmcaddon.Addon().getAddonInfo('profile'))
    except Exception:
        p = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
    try:
        if not os.path.exists(p):
            os.makedirs(p)
    except Exception:
        pass
    return p

def _tvzone_cache_path(name):
    return os.path.join(_tvzone_profile_dir(), name)

def tvzone_clear_cache():
    for f in ('tvzone_channels.json',):
        try:
            p = _tvzone_cache_path(f)
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

def _tvzone_headers_get(referer=None):
    h = {
        'User-Agent': TVZONE_UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7',
        'Upgrade-Insecure-Requests': '1',
    }
    if referer:
        h['Referer'] = referer
    return h

def _tvzone_headers_post(page_url):
    return {
        'User-Agent': TVZONE_UA,
        'Accept': '*/*',
        'Accept-Language': 'ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://www.tvzonehd.com',
        'Referer': page_url,
        'X-Requested-With': 'XMLHttpRequest',
    }

def _tvzone_http_get(url, referer=None, timeout=20):
    try:
        r = requests.get(url, headers=_tvzone_headers_get(referer), timeout=timeout, verify=False)
        return r.text, r.url
    except Exception as e:
        try: xbmc.log('[RomyLive] tvzone GET error %s: %s' % (url, e), level=xbmc.LOGWARNING)
        except Exception: pass
        return '', url

def _tvzone_http_post(page_url, slug, page_token, timeout=20):
    try:
        r = requests.post(TVZONE_STREAM_API, data={'s': slug, 'pt': page_token},
                          headers=_tvzone_headers_post(page_url), timeout=timeout, verify=False)
        return r.text
    except Exception as e:
        try: xbmc.log('[RomyLive] tvzone POST error: %s' % e, level=xbmc.LOGWARNING)
        except Exception: pass
        return ''

_TVZONE_RESERVED = set([
    '', 'blog', 'despre', 'contact', 'confidentialitate', 'dmca',
    'program-tv', 'meciuri-live', 'multi-tv', 'acum-la-tv',
    'embed.php', 'embed', 'stream.php', 'chat-api.php',
    'login', 'register', 'search', 'sitemap.xml', 'robots.txt',
    'terms', 'termeni', 'cookies', 'privacy', 'api'
])

_TVZONE_BAD_NAMES = set([
    'instaleaza', 'instaleaza', 'program', 'pagina', 'live', 'vezi', 'detalii',
    'home', 'acasa', 'acasa', 'citeste', 'citeste', 'mai mult', 'mai multe'
])

_TVZONE_FALLBACK = [
    ('Acasa Gold', 'https://www.tvzonehd.com/acasa-gold', ''),
    ('Acasa TV', 'https://www.tvzonehd.com/acasa-tv', ''),
    ('AMC', 'https://www.tvzonehd.com/amc', ''),
    ('Antena 1', 'https://www.tvzonehd.com/antena-1', ''),
    ('Antena 3', 'https://www.tvzonehd.com/antena-3-cnn', ''),
    ('Antena Stars', 'https://www.tvzonehd.com/antena-stars', ''),
    ('AXN', 'https://www.tvzonehd.com/axn-hd', ''),
    ('Digi 24', 'https://www.tvzonehd.com/digi24', ''),
    ('Digi Sport 1', 'https://www.tvzonehd.com/digi-sport-1', ''),
    ('Digi Sport 2', 'https://www.tvzonehd.com/digi-sport-2', ''),
    ('Digi Sport 3', 'https://www.tvzonehd.com/digi-sport-3', ''),
    ('Digi Sport 4', 'https://www.tvzonehd.com/digi-sport-4', ''),
    ('Discovery', 'https://www.tvzonehd.com/discovery', ''),
    ('Disney Channel', 'https://www.tvzonehd.com/disney-channel', ''),
    ('Etno TV', 'https://www.tvzonehd.com/etno-tv', ''),
    ('Eurosport 1', 'https://www.tvzonehd.com/eurosport-1', ''),
    ('Favorit TV', 'https://www.tvzonehd.com/favorit-tv', ''),
    ('Favorit 2', 'https://www.tvzonehd.com/favorit-2', ''),
    ('HBO', 'https://www.tvzonehd.com/hbo', ''),
    ('Kanal D', 'https://www.tvzonehd.com/kanal-d', ''),
    ('National Geographic', 'https://www.tvzonehd.com/national-geographic', ''),
    ('Prima History', 'https://www.tvzonehd.com/primahistory', ''),
    ('Prima Sport 1', 'https://www.tvzonehd.com/prima-sport-1', ''),
    ('Prima Sport 2', 'https://www.tvzonehd.com/prima-sport-2', ''),
    ('Prima TV', 'https://www.tvzonehd.com/prima-tv', ''),
    ('PRO Arena', 'https://www.tvzonehd.com/pro-arena', ''),
    ('PRO Cinema', 'https://www.tvzonehd.com/procinema', ''),
    ('PRO TV', 'https://www.tvzonehd.com/protv', ''),
    ('TVR 1', 'https://www.tvzonehd.com/tvr1', ''),
    ('TVR 2', 'https://www.tvzonehd.com/tvr2', ''),
    ('TVR 3', 'https://www.tvzonehd.com/tvr-3', ''),
    ('TVR Info', 'https://www.tvzonehd.com/tvrinfo', ''),
    ('TVR Folclor', 'https://www.tvzonehd.com/tvrfolclorr', ''),
]

def _tvzone_strip_tags(s):
    try: import html as _html
    except Exception: _html = None
    s = re.sub(r'<script\b.*?</script>', ' ', s, flags=re.I | re.S)
    s = re.sub(r'<style\b.*?</style>', ' ', s, flags=re.I | re.S)
    s = re.sub(r'<[^>]+>', ' ', s)
    if _html is not None:
        s = _html.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()

def _tvzone_slug_to_name(slug):
    s = slug.strip('/').replace('-', ' ').replace('_', ' ')
    out = []
    for w in s.split():
        lw = w.lower()
        if lw in ('tvr', 'hbo', 'axn', 'bbc', 'mtv', 'tlc', 'amc', 'ppv', 'id', 'tv', 'cnn', 'dw'):
            out.append(lw.upper())
        elif lw == 'protv':
            out.extend(['PRO', 'TV'])
        elif lw == 'procinema':
            out.extend(['PRO', 'Cinema'])
        elif lw == 'proarena':
            out.extend(['PRO', 'Arena'])
        elif lw.startswith('digisport') and lw[9:].isdigit():
            out.extend(['Digi', 'Sport', lw[9:]])
        elif lw.startswith('eurosport') and lw[10:].isdigit():
            out.extend(['Eurosport', lw[10:]])
        elif lw.startswith('primasport') and lw[10:].isdigit():
            out.extend(['Prima', 'Sport', lw[10:]])
        elif lw == 'primahistory':
            out.extend(['Prima', 'History'])
        elif lw == 'acasa':
            out.append('Acasa')
        else:
            out.append(w.capitalize())
    return ' '.join(out).strip()

def _tvzone_normalize_name(name):
    try: import html as _html
    except Exception: _html = None
    if _html is not None:
        name = _html.unescape(name or '')
    else:
        name = name or ''
    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'^\s*Vizioneaz[a\u0103]\s+', '', name, flags=re.I)
    name = re.sub(r'^\s*pagina\s+', '', name, flags=re.I)
    name = re.sub(r'\s+live(?:\s+online)?\s*$', '', name, flags=re.I)
    name = re.sub(r'\s+fhd(?:\s+online)?\s*$', '', name, flags=re.I)
    name = re.sub(r'\s+program\s+tv(?:\s+online)?\s*$', '', name, flags=re.I)
    name = re.sub(r'\s+online\s*$', '', name, flags=re.I)
    name = re.sub(r'\s*[-\u2013\u2014|\u2022]+\s*$', '', name).strip()
    fix = {
        'pro tv': 'PRO TV', 'pro arena': 'PRO Arena', 'pro cinema': 'PRO Cinema',
        'acasa tv': 'Acasa TV', 'acasa gold': 'Acasa Gold', 'prima tv': 'Prima TV',
        'kanal d': 'Kanal D', 'tvr 1': 'TVR 1', 'tvr 2': 'TVR 2',
        'hbo': 'HBO', 'hbo 2': 'HBO 2', 'hbo 3': 'HBO 3', 'tlc': 'TLC',
        'amc': 'AMC', 'axn': 'AXN', 'digi 24': 'Digi 24', 'digi24': 'Digi 24',
        'tvr info': 'TVR Info', 'tvrinfo': 'TVR Info',
        'tvr folclor': 'TVR Folclor', 'tvrfolclor': 'TVR Folclor', 'tvrfolclorr': 'TVR Folclor',
        'digi world': 'Digi World', 'digi life': 'Digi Life',
        'tvr 3': 'TVR 3', 'etno tv': 'Etno TV',
        'favorit tv': 'Favorit TV', 'favorit 2': 'Favorit 2',
    }
    low = name.lower()
    if low in fix:
        name = fix[low]
    return name.strip()

def _tvzone_is_bad_name(name):
    if not name: return True
    low = name.strip().lower()
    if low in _TVZONE_BAD_NAMES: return True
    if len(low) <= 2: return True
    if low.startswith(('instaleaza', 'instaleaza', 'program ', 'pagina ')): return True
    return False

def _tvzone_channel_url(href):
    try:
        try: import html as _html
        except Exception: _html = None
        try: from urllib.parse import urljoin as _urljoin, urlparse as _urlparse
        except Exception: from urlparse import urljoin as _urljoin, urlparse as _urlparse
        if _html is not None:
            href = _html.unescape(href)
        u = _urljoin(TVZONE_BASE, href)
        p = _urlparse(u)
    except Exception:
        return None
    if p.scheme not in ('http', 'https'): return None
    if p.netloc.lower() not in ('www.tvzonehd.com', 'tvzonehd.com'): return None
    path = p.path.strip('/')
    if not path or '/' in path: return None
    low = path.lower()
    if low in _TVZONE_RESERVED: return None
    if low.startswith(('blog', 'embed', 'api-', 'api_', 'admin')): return None
    if re.search(r'\.(?:css|js|png|jpg|jpeg|gif|webp|svg|ico|xml|json|txt|php)$', low, re.I): return None
    return 'https://www.tvzonehd.com/' + path

def _tvzone_extract_icon(open_tag, inner, page_url):
    try: from urllib.parse import urljoin as _urljoin
    except Exception: from urlparse import urljoin as _urljoin
    try: import html as _html
    except Exception: _html = None
    blob = open_tag + ' ' + inner
    pats = [
        r'<img\b[^>]*\bdata-src\s*=\s*["\']([^"\']+)["\']',
        r'<img\b[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']',
        r'background-image\s*:\s*url\((["\']?)([^)"\']+)\1\)',
    ]
    for pat in pats:
        m = re.search(pat, blob, re.I | re.S)
        if not m: continue
        val = m.group(1 if 'background-image' not in pat else 2)
        if _html is not None:
            val = _html.unescape(val).strip()
        else:
            val = val.strip()
        if not val: continue
        icon = _urljoin(page_url, val)
        low = icon.lower()
        if any(x in low for x in ('favicon', 'logo-tvzone', 'placeholder', 'loader')):
            continue
        return icon
    return ''

def _tvzone_name_from_anchor(open_tag, inner, url):
    try: from urllib.parse import urlparse as _urlparse
    except Exception: from urlparse import urlparse as _urlparse
    for key in ('data-name', 'data-title', 'aria-label', 'title'):
        m = re.search(r'\b' + re.escape(key) + r'\s*=\s*["\']([^"\']+)["\']', open_tag, re.I)
        if m:
            val = _tvzone_normalize_name(_tvzone_strip_tags(m.group(1)))
            if not _tvzone_is_bad_name(val):
                return val
    m = re.search(r'<img\b[^>]*\balt\s*=\s*["\']([^"\']+)["\']', inner, re.I | re.S)
    if m:
        val = _tvzone_normalize_name(_tvzone_strip_tags(m.group(1)))
        if not _tvzone_is_bad_name(val):
            return val
    for tag in ('h1', 'h2', 'h3', 'h4', 'strong', 'b', 'span'):
        m = re.search(r'<' + tag + r'\b[^>]*>(.*?)</' + tag + r'>', inner, re.I | re.S)
        if m:
            val = _tvzone_normalize_name(_tvzone_strip_tags(m.group(1)))
            if not _tvzone_is_bad_name(val):
                return val
    text = _tvzone_normalize_name(_tvzone_strip_tags(inner))
    if not _tvzone_is_bad_name(text) and len(text) <= 80:
        return text
    return _tvzone_slug_to_name(_urlparse(url).path.strip('/'))

def _tvzone_parse_links(src):
    found = {}
    for m in re.finditer(r'(<a\b[^>]*\bhref\s*=\s*["\']([^"\']+)["\'][^>]*>)(.*?)</a>', src, re.I | re.S):
        open_tag = m.group(1); href = m.group(2); inner = m.group(3)
        url = _tvzone_channel_url(href)
        if not url: continue
        name = _tvzone_normalize_name(_tvzone_name_from_anchor(open_tag, inner, url))
        if _tvzone_is_bad_name(name): continue
        icon = _tvzone_extract_icon(open_tag, inner, url)
        existing = found.get(url)
        if not existing:
            found[url] = {'name': name, 'icon': icon}
        else:
            if len(name) < len(existing['name']) and not _tvzone_is_bad_name(name):
                existing['name'] = name
            if not existing.get('icon') and icon:
                existing['icon'] = icon
    return found

def _tvzone_scrape_channels():
    src_p, _ = _tvzone_http_get(TVZONE_PROGRAM_URL, TVZONE_BASE)
    found = _tvzone_parse_links(src_p) if src_p else {}
    try:
        src_h, _ = _tvzone_http_get(TVZONE_BASE)
        extra = _tvzone_parse_links(src_h) if src_h else {}
        for u, info in extra.items():
            if u not in found:
                found[u] = info
            else:
                if not found[u].get('icon') and info.get('icon'):
                    found[u]['icon'] = info['icon']
    except Exception:
        pass
    for nm, u, ic in _TVZONE_FALLBACK:
        found.setdefault(u, {'name': nm, 'icon': ic})
    # Forced overrides
    forced = [
        ('Digi 24', 'https://www.tvzonehd.com/digi24'),
        ('TVR Info', 'https://www.tvzonehd.com/tvrinfo'),
        ('TVR Folclor', 'https://www.tvzonehd.com/tvrfolclorr'),
        ('TVR 3', 'https://www.tvzonehd.com/tvr-3'),
    ]
    for fn, fu in forced:
        old_icon = found.get(fu, {}).get('icon', '')
        found[fu] = {'name': fn, 'icon': old_icon}
    items = []
    seen = set()
    for u, info in found.items():
        nm = _tvzone_normalize_name(info.get('name', ''))
        if nm.lower().startswith('pagina '):
            nm = _tvzone_normalize_name(nm[7:])
        if _tvzone_is_bad_name(nm): continue
        key = nm.lower()
        if key in seen: continue
        seen.add(key)
        items.append((nm, u, info.get('icon', '')))
    items.sort(key=lambda x: x[0].lower())
    try: xbmc.log('[RomyLive] TVZone channels found: %d' % len(items), level=xbmc.LOGINFO)
    except Exception: pass
    return items

def _tvzone_classify(name, url=''):
    n = (name or '').lower(); u = (url or '').lower()
    if any(x in n for x in ('etno tv', 'favorit tv', 'favorit 2', 'muzic', 'mynele', 'taraf', 'folclor', 'party tv', 'kiss tv', 'ura tv', 'hit music')):
        return 'Muzica'
    if 'tvr folclor' in n or '/tvrfolclorr' in u or '/tvrfolclor' in u:
        return 'Muzica'
    if any(x in n for x in ('sport', 'eurosport', 'digi sport', 'prima sport', 'look sport', 'orange sport', 'match tv', 'motorsport', 'setanta', 'fight', 'esport', 'sky sport', 'nova sport', 'antena sport')):
        return 'Sport'
    if any(x in n for x in ('digi 24', 'digi24', 'antena 3', 'romania tv', 'realitatea', 'b1', 'aleph', 'euronews', 'cnn', 'bloomberg', 'bbc news', 'sky news', 'stiri', 'stire', 'tvr info', 'tvrinfo', 'news')):
        return 'Stiri'
    if any(x in n for x in ('hbo', 'cinema', 'film', 'movies', 'axn', 'amc', 'fox', 'tv 1000', 'tv1000', 'epic drama', 'sundance', 'diva', 'moviemix', 'kinopolis', 'megamax', 'romance tv', 'action', 'thriller', 'comedy central')):
        return 'Filme & Seriale'
    if any(x in n for x in ('discovery', 'national geographic', 'nat geo', 'history', 'animal planet', 'bbc earth', 'travel', 'da vinci', 'viasat', 'crime', 'invest', 'science', 'planet', 'documentar')):
        return 'Documentare'
    if any(x in n for x in ('cartoon', 'boomerang', 'nick', 'disney', 'baby tv', 'minimax', 'da vinci kids', 'jimjam', 'duck tv', 'kids', 'copii')):
        return 'Copii'
    if any(x in n for x in ('pro tv', 'protv', 'antena 1', 'antena1', 'kanal d', 'prima tv', 'tvr 1', 'tvr1', 'tvr 2', 'tvr2', 'acasa', 'happy', 'pro arena', 'pro cinema', 'nasul tv', 'metropola')):
        return 'Generaliste'
    return 'Diverse'

_TVZONE_CATEGORIES_ORDER = ['Generaliste', 'Sport', 'Stiri', 'Filme & Seriale', 'Documentare', 'Copii', 'Muzica', 'Diverse']

def _tvzone_load_favorites():
    import json as _json
    p = _tvzone_cache_path('tvzone_favorites.json')
    try:
        return set(_json.load(open(p, 'r', encoding='utf-8')))
    except Exception:
        return set()

def _tvzone_save_favorites(favs):
    import json as _json
    p = _tvzone_cache_path('tvzone_favorites.json')
    try:
        _json.dump(sorted(list(favs)), open(p, 'w', encoding='utf-8'))
    except Exception:
        pass

def _tvzone_load_channels_data():
    import json as _json, time as _time
    cache = _tvzone_cache_path('tvzone_channels.json')
    data = None
    try:
        if os.path.exists(cache) and (_time.time() - os.path.getmtime(cache)) < 6 * 3600:
            data = _json.load(open(cache, 'r', encoding='utf-8'))
    except Exception:
        data = None
    if not data:
        try:
            items = _tvzone_scrape_channels()
            data = [{'name': n, 'url': u, 'icon': i} for (n, u, i) in items]
            try:
                _json.dump(data, open(cache, 'w', encoding='utf-8'))
            except Exception:
                pass
        except Exception as e:
            try: xbmc.log('[RomyLive] TVZone scrape error: %s' % e, level=xbmc.LOGERROR)
            except Exception: pass
            data = [{'name': n, 'url': u, 'icon': i} for (n, u, i) in _TVZONE_FALLBACK]
    return data

def _tvzone_epg_label(name):
    try:
        txt = _dl_epg_for_channel(name)
    except Exception:
        txt = ''
    if not txt:
        return '', ''
    now = ''
    for line in txt.split('\n'):
        if 'ACUM' in line:
            m = re.search(r'ACUM:\[/B\]\[/COLOR\]\s*([0-9:]+)-([0-9:]+)\s+(.+)$', line)
            if m:
                now = ' [COLOR yellow]| ACUM %s: %s[/COLOR]' % (m.group(1), m.group(3).strip())
            break
    return now, txt

def _tvzone_build_channel_item(ch, fav_set):
    nm = ch.get('name') or ''
    pu = ch.get('url') or ''
    ic = ch.get('icon') or thumb_tvzone
    if not nm or not pu:
        return ''
    try:
        play_url = sys.argv[0] + '?mode=55&url=' + urllib.quote_plus(pu) + '&name=' + urllib.quote_plus(nm) + '&iconimage=' + urllib.quote_plus(ic)
    except Exception:
        play_url = sys.argv[0] + '?mode=55&url=' + pu + '&name=' + nm
    epg_now, epg_full = _tvzone_epg_label(nm)
    star = '[COLOR gold]* [/COLOR]' if pu in fav_set else ''
    fav_action = 'tvzone_unfav' if pu in fav_set else 'tvzone_fav'
    fav_label = 'Sterge din favorite TVZone' if pu in fav_set else 'Adauga la favorite TVZone'
    title = '<title>' + star + '[COLOR white][B]' + nm + '[/B][/COLOR]' + epg_now + '</title>'
    info_text = nm + ' - via tvzonehd.com'
    if epg_full:
        info_text = epg_full + '\n\n' + info_text
    return ('<item>' + title +
            '<link>' + play_url + '</link>' +
            '<thumbnail>' + ic + '</thumbnail>' +
            '<fanart>' + fanart_tvzone + '</fanart>' +
            '<info>' + info_text + '</info>' +
            '</item>')

def tvzone_get_channel_list(category=None):
    data = _tvzone_load_channels_data()
    fav_set = _tvzone_load_favorites()
    parts = []

    if category is None:
        # Root: show refresh + Categories (Favorite TVZone removed per user request)
        parts.append('<item><title>[COLOR gold][B]Actualizeaza lista[/B][/COLOR]</title><externallink>tvzone://refresh</externallink><thumbnail>' + thumb_tvzone + '</thumbnail><fanart>' + fanart_tvzone + '</fanart><info>Reincarca lista de canale de pe tvzonehd.com</info></item>')
        parts.append('<item><title>[COLOR aqua][B]Toate canalele[/B][/COLOR] [COLOR white](' + str(len(data)) + ')[/COLOR]</title><externallink>tvzone://cat/__all__</externallink><thumbnail>' + thumb_tvzone + '</thumbnail><fanart>' + fanart_tvzone + '</fanart><info>Toate cele ' + str(len(data)) + ' canale TVZoneHD</info></item>')
        # Build category counts
        cat_counts = {}
        for ch in data:
            c = _tvzone_classify(ch.get('name',''), ch.get('url',''))
            cat_counts[c] = cat_counts.get(c, 0) + 1
        for c in _TVZONE_CATEGORIES_ORDER:
            if cat_counts.get(c, 0) == 0: continue
            try:
                cat_slug = urllib.quote_plus(c)
            except Exception:
                cat_slug = c.replace(' ', '+')
            parts.append('<item><title>[COLOR aqua][B]' + c + '[/B][/COLOR] [COLOR white](' + str(cat_counts[c]) + ')[/COLOR]</title><externallink>tvzone://cat/' + cat_slug + '</externallink><thumbnail>' + thumb_tvzone + '</thumbnail><fanart>' + fanart_tvzone + '</fanart><info>Canale TVZoneHD - categoria ' + c + '</info></item>')
        return '\n'.join(parts)

    # Category listing
    if category == '__fav__':
        # Favorites: show only channels in fav_set
        for ch in data:
            if ch.get('url') in fav_set:
                s = _tvzone_build_channel_item(ch, fav_set)
                if s: parts.append(s)
        if not parts:
            parts.append('<item><title>[COLOR red][B]Nu ai inca favorite[/B][/COLOR]</title><externallink>tvzone://list</externallink><thumbnail>' + thumb_tvzone + '</thumbnail><fanart>' + fanart_tvzone + '</fanart><info>Foloseste meniul contextual (C sau lung-apasare) pe un canal ca sa il adaugi la favorite</info></item>')
        return '\n'.join(parts)

    if category == '__all__':
        # All: favorites first, then rest
        fav_items = [ch for ch in data if ch.get('url') in fav_set]
        rest = [ch for ch in data if ch.get('url') not in fav_set]
        for ch in fav_items + rest:
            s = _tvzone_build_channel_item(ch, fav_set)
            if s: parts.append(s)
        return '\n'.join(parts)

    # Specific genre
    fav_items = [ch for ch in data if ch.get('url') in fav_set and _tvzone_classify(ch.get('name',''), ch.get('url','')) == category]
    rest = [ch for ch in data if ch.get('url') not in fav_set and _tvzone_classify(ch.get('name',''), ch.get('url','')) == category]
    for ch in fav_items + rest:
        s = _tvzone_build_channel_item(ch, fav_set)
        if s: parts.append(s)
    if not parts:
        parts.append('<item><title>[COLOR red][B]Nu sunt canale in aceasta categorie[/B][/COLOR]</title><externallink>tvzone://list</externallink><thumbnail>' + thumb_tvzone + '</thumbnail><fanart>' + fanart_tvzone + '</fanart><info>Categoria ' + category + ' este goala</info></item>')
    return '\n'.join(parts)

def tvzone_toggle_favorite(url, name=''):
    favs = _tvzone_load_favorites()
    if url in favs:
        favs.remove(url)
        try: notify('[COLOR yellow]Sters din favorite TVZone: ' + (name or url) + '[/COLOR]')
        except Exception: pass
    else:
        favs.add(url)
        try: notify('[COLOR gold]Adaugat la favorite TVZone: ' + (name or url) + '[/COLOR]')
        except Exception: pass
    _tvzone_save_favorites(favs)
    try: xbmc.executebuiltin('Container.Refresh')
    except Exception: pass

def _tvzone_extract_player_data(page_html):
    slug = None; token = None
    for pat in (r"\bvar\s+_slug\s*=\s*['\"]([^'\"]+)['\"]", r"\b_slug\s*=\s*['\"]([^'\"]+)['\"]"):
        m = re.search(pat, page_html, re.I)
        if m:
            slug = m.group(1).strip(); break
    for pat in (r"\b_pageToken\s*=\s*['\"]([^'\"]+)['\"]", r"\bpageToken\s*[:=]\s*['\"]([^'\"]+)['\"]"):
        m = re.search(pat, page_html, re.I)
        if m:
            token = m.group(1).strip(); break
    return slug, token

def tvzone_resolve_stream(page_url):
    page_html, final_page = _tvzone_http_get(page_url, TVZONE_BASE)
    if not page_html:
        return '', page_url
    slug, token = _tvzone_extract_player_data(page_html)
    if not slug or not token:
        return '', final_page
    api_text = _tvzone_http_post(final_page, slug, token)
    if not api_text:
        return '', final_page
    try:
        import json as _json
        j = _json.loads(api_text)
    except Exception:
        return '', final_page
    stream_url = j.get('url')
    if not stream_url or not isinstance(stream_url, str):
        return '', final_page
    stream_url = stream_url.strip()
    if not stream_url.startswith(('http://', 'https://')):
        try:
            from urllib.parse import urljoin as _urljoin
        except Exception:
            from urlparse import urljoin as _urljoin
        stream_url = _urljoin(TVZONE_BASE, stream_url)
    return stream_url, final_page

def tvzone_play(name, page_url, iconimage, description, subtitle):
    stream, ref = tvzone_resolve_stream(page_url)
    if not stream:
        try: notify('[COLOR red]TVZoneHD stream indisponibil pentru ' + (name or '') + '[/COLOR]')
        except Exception: pass
        try:
            li = xbmcgui.ListItem(name or 'TVZoneHD')
            xbmcplugin.setResolvedUrl(addon_handle, False, li)
        except Exception:
            pass
        return
    try:
        from urllib.parse import urlencode as _uenc
    except Exception:
        from urllib import urlencode as _uenc
    headers = {'User-Agent': TVZONE_UA, 'Referer': ref, 'Origin': 'https://www.tvzonehd.com'}
    kodi_url = stream + '|' + _uenc(headers)
    m3u8_player(name or 'TVZoneHD', kodi_url, iconimage or thumb_tvzone, description or ('Canal ' + (name or '') + ' via tvzonehd.com'), subtitle or '')


def daddylive_list_channels():
    channels = _dl_fetch_channels()
    if not channels:
        notify('[COLOR red]Nu pot incarca DaddyLive 24/7[/COLOR]')
        addDir('[COLOR red][B]DaddyLive - eroare la incarcare[/B][/COLOR]', '', 5, thumb_daddylive, fanart_daddylive, 'Pagina dlhd.pk/24-7-channels.php nu a putut fi incarcata. Incearca din nou.', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
        return
    for cid, name, logo in channels:
        plot = 'DaddyLive 24/7 - %s' % name
        epg_text = _dl_epg_for_channel(name)
        if epg_text:
            plot = epg_text + '\n\n' + plot
        label = '[COLOR white][B]%s[/B][/COLOR]' % name
        thumb = logo if logo else thumb_daddylive
        try:
            label_e = label.encode('utf-8', 'ignore') if isinstance(label, str) and bytes is str else label
            plot_e = plot.encode('utf-8', 'ignore') if isinstance(plot, str) and bytes is str else plot
        except Exception:
            label_e = label
            plot_e = plot
        addDir2(label_e, str(cid), 30, '', thumb, fanart_daddylive, plot_e, 'TV', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', False)


def daddylive_resolve_stream(channel_id):
    try:
        bases = [daddylive_base, 'https://daddylive.sx', 'https://daddylive.dad', 'https://dlhd.dad']
        text = ''
        page_url = ''
        used_base = ''
        for b in bases:
            page_url = '%s/stream/stream-%s.php' % (b, channel_id)
            r = _dl_get(page_url, referer='%s/watch.php?id=%s' % (b, channel_id))
            if r is not None and r.status_code == 200 and 'iframe' in (r.text or '').lower():
                text = r.text
                used_base = b
                break
        if not text:
            return ''

        iframe_url = ''
        for m in re.finditer(r'<iframe[^>]+src=["\']([^"\']+)["\']', text, re.IGNORECASE):
            candidate = m.group(1)
            if candidate.startswith('//'):
                candidate = 'https:' + candidate
            elif candidate.startswith('/'):
                candidate = used_base + candidate
            if 'adbanner' in candidate.lower() or 'about:blank' in candidate.lower():
                continue
            iframe_url = candidate
            break
        if not iframe_url:
            return ''

        try:
            from urllib.parse import urlparse as _up
        except ImportError:
            from urlparse import urlparse as _up
        parsed = _up(iframe_url)
        iframe_origin = '%s://%s' % (parsed.scheme, parsed.netloc)

        r2 = _dl_get(iframe_url, referer=page_url, origin=used_base)
        if r2 is None or r2.status_code != 200:
            return ''
        body = r2.text

        # New dlhd format: source: window.atob('BASE64_M3U8')
        m3u8 = ''
        mm = re.search(r"source\s*:\s*window\.atob\(\s*['\"]([A-Za-z0-9+/=]+)['\"]\s*\)", body)
        if mm:
            try:
                cand = mm.group(1)
                pad = '=' * (-len(cand) % 4)
                decoded = base64.b64decode(cand + pad).decode('utf-8', 'ignore')
                if '.m3u8' in decoded:
                    m3u8 = decoded
            except Exception:
                m3u8 = ''

        # Fallback: direct m3u8 URL in body
        if not m3u8:
            dm = re.search(r'(https?://[^"\'\s]+?\.m3u8[^"\'\s]*)', body)
            if dm:
                m3u8 = dm.group(1)

        # Legacy fallback: CHANNEL_KEY + newkso flow
        if not m3u8:
            ck_list = re.findall(r'const\s+CHANNEL_KEY\s*=\s*["\']([^"\']+)["\']', body)
            if ck_list:
                channel_key = ck_list[-1]
                bundle = _dl_decode_bundle(body)
                b_ts = bundle.get('b_ts', '')
                b_sig = bundle.get('b_sig', '')
                b_rnd = bundle.get('b_rnd', '')
                b_host = bundle.get('b_host', '')
                if b_host and b_ts and b_sig:
                    try:
                        auth_url = '%sauth.php?channel_id=%s&ts=%s&rnd=%s&sig=%s' % (b_host, channel_key, b_ts, b_rnd, b_sig)
                        _dl_get(auth_url, referer=iframe_url, origin=iframe_origin)
                    except Exception:
                        pass
                lookup_url = '%s/server_lookup.php?channel_id=%s' % (iframe_origin, channel_key)
                rl = _dl_get(lookup_url, referer=iframe_url, origin=iframe_origin)
                server_key = ''
                if rl is not None and rl.status_code == 200:
                    try:
                        server_key = (rl.json() or {}).get('server_key', '') or ''
                    except Exception:
                        sk = re.search(r'"server_key"\s*:\s*"([^"]+)"', rl.text or '')
                        server_key = sk.group(1) if sk else ''
                if server_key:
                    if server_key == 'top1/cdn':
                        m3u8 = 'https://top1.newkso.ru/top1/cdn/%s/mono.m3u8' % channel_key
                    else:
                        m3u8 = 'https://%snew.newkso.ru/%s/%s/mono.m3u8' % (server_key, server_key, channel_key)

        if not m3u8:
            return ''

        stream = '%s|Referer=%s/&Origin=%s&User-Agent=%s' % (
            m3u8,
            iframe_origin,
            iframe_origin,
            urllib.quote_plus(daddylive_useragent),
        )
        return stream
    except Exception:
        return ''


def daddylive_play(name, channel_id, iconimage, description, subtitle):
    stream = daddylive_resolve_stream(channel_id)
    if not stream:
        notify('[COLOR red]Stream DaddyLive indisponibil[/COLOR]')
        try:
            li = xbmcgui.ListItem(name or 'DaddyLive')
            xbmcplugin.setResolvedUrl(addon_handle, False, li)
        except Exception:
            pass
        return
    m3u8_player(name or 'DaddyLive', stream, iconimage or thumb_daddylive, description or 'DaddyLive 24/7', subtitle or '')



def dinbox_setting(name):
    try:
        return addon.getSettingString(name)
    except:
        return addon.getSetting(name)

def dinbox_set_setting(name, value):
    try:
        addon.setSettingString(name, value)
    except:
        try:
            addon.setSetting(name, value)
        except:
            pass

def dinbox_credentials():
    abonement = dinbox_setting('dinbox_autentificare')
    parola = dinbox_setting('dinbox_parola')
    dialog = xbmcgui.Dialog()

    if not abonement:
        abonement = dialog.input('FunTvLive - Utilizator Dinbox')
        if abonement:
            dinbox_set_setting('dinbox_autentificare', abonement)
    if not parola:
        parola = dialog.input('FunTvLive - Parola Dinbox', option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if parola:
            dinbox_set_setting('dinbox_parola', parola)

    return abonement, parola

def dinbox_login():
    global dinbox_auth_data
    abonement, parola = dinbox_credentials()
    if not abonement or not parola:
        xbmcgui.Dialog().notification('FunTvLive', 'Lipsesc datele de autentificare.', xbmcgui.NOTIFICATION_ERROR)
        return None

    if dinbox_auth_data and 'authkey' in dinbox_auth_data:
        return dinbox_auth_data

    cached_auth = dinbox_setting('dinbox_cached_authkey')
    cached_sess = dinbox_setting('dinbox_cached_sesskey')
    cached_time = dinbox_setting('dinbox_cached_auth_time')
    try:
        cached_age = time.time() - int(cached_time)
    except:
        cached_age = 999999

    if cached_auth and cached_age < 60:
        dinbox_auth_data = {
            'authkey': cached_auth,
            'sess_key': cached_sess,
            'abonement': abonement
        }
        return dinbox_auth_data

    login_url = DINBOX_LOGIN_API_URL.format(abonement=urllib.quote_plus(abonement), password=urllib.quote_plus(parola))
    try:
        response = requests.get(login_url, timeout=10)
        data = response.json()
    except Exception as e:
        xbmc.log('[FunTvLive] Eroare login Dinbox: %s' % e, level=xbmc.LOGERROR)
        xbmcgui.Dialog().notification('FunTvLive', 'Eroare la autentificare.', xbmcgui.NOTIFICATION_ERROR)
        return None

    if data.get('error') == 0 and data.get('authkey'):
        dinbox_set_setting('dinbox_cached_authkey', data.get('authkey', ''))
        dinbox_set_setting('dinbox_cached_sesskey', str(data.get('sess_key') or abonement))
        dinbox_set_setting('dinbox_cached_auth_time', str(int(time.time())))
        dinbox_auth_data = data
        return data

    xbmcgui.Dialog().notification('FunTvLive', 'Autentificare esuata.', xbmcgui.NOTIFICATION_ERROR)
    return None

def dinbox_api_get(url):
    try:
        response = requests.get(url, timeout=10)
        return response.json()
    except Exception as e:
        xbmc.log('[FunTvLive] Eroare API Dinbox: %s' % e, level=xbmc.LOGERROR)
        xbmcgui.Dialog().notification('FunTvLive', 'Nu pot incarca datele.', xbmcgui.NOTIFICATION_ERROR)
        return {}

def dinbox_format_time(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime('%H:%M')
    except:
        return ''

def dinbox_now_next(item):
    name = item.get('name', '').strip()
    plot = ''
    epg_now = item.get('program_name', '').strip()
    start_now = dinbox_format_time(item.get('program_begin_time'))
    end_now = dinbox_format_time(item.get('program_end_time'))
    epg_next = item.get('next_program_name', '').strip()
    start_next = dinbox_format_time(item.get('next_program_begin_time'))
    end_next = dinbox_format_time(item.get('next_program_end_time'))

    if epg_now and start_now and end_now:
        plot += 'Acum: %s (%s - %s)' % (epg_now, start_now, end_now)
    elif epg_now:
        plot += 'Acum: %s' % epg_now

    if epg_next and start_next and end_next:
        plot += '\nUrmeaza: %s (%s - %s)' % (epg_next, start_next, end_next)
    elif epg_next:
        plot += '\nUrmeaza: %s' % epg_next

    return name, plot

def dinbox_list_categories():
    data = dinbox_login()
    if not data:
        return False

    authkey = data['authkey']
    sess_key = str(data.get('sess_key') or data.get('abonement') or '')
    api_url = (
        DINBOX_BASE_URL + '/program/category/list/?authkey=%s&sess_key=%s&device=%s'
        '&client_id=%s&api_key=%s&lang=ro'
    ) % (authkey, sess_key, DINBOX_DEVICE, DINBOX_CLIENT_ID, DINBOX_API_KEY)

    categories = dinbox_api_get(api_url).get('categories', [])
    for cat in categories:
        cat_id = str(cat.get('id', ''))
        if not cat_id:
            continue
        name = cat.get('name', 'Fara nume')
        icon = cat.get('icon_tv', '') or __icon__
        addDir(name.encode('utf-8', 'ignore'), cat_id, 23, icon, '', 'FunTvLive', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

    return False

def dinbox_list_channels(cat_id):
    data = dinbox_login()
    if not data:
        return False

    authkey = data['authkey']
    sess_key = str(data.get('sess_key') or data.get('abonement') or '')
    api_url = (
        DINBOX_BASE_URL + '/program/category/channel/list/?category_id=%s&icon_width=176&icon_height=104'
        '&authkey=%s&device=%s&client_id=%s&api_key=%s&sess_key=%s&lang=ro'
    ) % (cat_id, authkey, DINBOX_DEVICE, DINBOX_CLIENT_ID, DINBOX_API_KEY, sess_key)

    programs = dinbox_api_get(api_url).get('programs', [])
    for item in programs:
        playback_url = item.get('url', '')
        if not playback_url:
            continue
        icon = item.get('icon', '') or __icon__
        label, plot = dinbox_now_next(item)
        addDir2(label.encode('utf-8', 'ignore'), playback_url, 25, '', icon, '', plot, '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', False)

    xbmcplugin.setContent(addon_handle, 'videos')
    return False

def dinbox_resolve_stream(playback_url):
    if not playback_url:
        return ''
    if 'redirect=0' not in playback_url:
        joiner = '&' if '?' in playback_url else '?'
        playback_url += joiner + 'redirect=0'
    try:
        response = requests.get(playback_url, timeout=10)
        if response.url and response.url != playback_url and '.m3u8' in response.url:
            return response.url
        try:
            data = response.json()
            for key in ['url', 'stream_url', 'playback_url']:
                if data.get(key):
                    return data.get(key)
        except:
            pass
        if '.m3u8' in response.text:
            match = re.compile(r'(https?://[^\s"\']+?\.m3u8[^\s"\']*)', re.MULTILINE|re.DOTALL|re.IGNORECASE).findall(response.text)
            if match:
                return match[0].replace('\\/', '/')
    except Exception as e:
        xbmc.log('[FunTvLive] Eroare rezolvare stream: %s' % e, level=xbmc.LOGERROR)
    return playback_url

def dinbox_play(playback_url, name, iconimage, description):
    stream = dinbox_resolve_stream(playback_url)
    if not stream:
        xbmcgui.Dialog().notification('FunTvLive', 'Stream invalid.', xbmcgui.NOTIFICATION_ERROR)
        return True
    m3u8_player(name or 'FunTvLive', stream, iconimage or __icon__, description or 'FunTvLive', '')
    return True

###############################################################################
# SKY ITALIA - Canale SKY (independent, fara dependenta de Mandra)
###############################################################################

def sky_italia_list():
    """Afiseaza lista de canale SKY Italia ca foldere clickabile."""
    for ch_name, ch_id, ch_thumb in sky_italia_channels:
        label = '[COLOR white][B]' + ch_name + '[/B][/COLOR]'
        li = xbmcgui.ListItem(label)
        li.setArt({'icon': ch_thumb, 'thumb': ch_thumb, 'fanart': fanart_sky_italia})
        li.setInfo('video', {'title': ch_name, 'plot': 'SKY Italia - ' + ch_name})
        li.setProperty('IsPlayable', 'true')
        url_play = sys.argv[0] + '?mode=51&url=' + urllib.quote_plus(ch_id) + '&name=' + urllib.quote_plus(ch_name) + '&iconimage=' + urllib.quote_plus(ch_thumb)
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url_play, listitem=li, isFolder=False)
    xbmcplugin.endOfDirectory(addon_handle)


def sky_italia_play(channel_id, name, iconimage):
    """Redeaza un canal SKY Italia via inputstream.adaptive (DASH + ClearKey DRM)."""
    import json
    import base64
    import requests as _req
    from datetime import datetime, timedelta

    SECRET = 'my_secret_key'

    def xor_decrypt(data_b64, key):
        data = base64.b64decode(data_b64)
        key_bytes = key.encode()
        out = bytearray()
        for i in range(len(data)):
            out.append(data[i] ^ key_bytes[i % len(key_bytes)])
        return out.decode('utf-8')

    try:
        api_url = 'https://test34344.herokuapp.com/filter.php?numTest=A1A159&id=' + channel_id
        resp = _req.get(api_url, timeout=15).text
        res = json.loads(resp)
        decrypted = xor_decrypt(res['data'], SECRET)
        data = json.loads(decrypted)
        manifest = data['manifest']
        kid = data['kid']
        key = data['key']
    except Exception as e:
        xbmc.log('sky_italia_play error: ' + str(e), xbmc.LOGERROR)
        xbmcgui.Dialog().ok('SKY Italia', 'Eroare la obtinerea stream-ului. Incearca din nou.')
        xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
        return

    drm_type = 'org.w3.clearkey'
    key64 = kid + ':' + key
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
    host = 'https://www.nowtv.it'
    headers = 'User-Agent=' + ua + '&Referer=' + host + '/&Origin=' + host + '&verifypeer=false'

    li = xbmcgui.ListItem(name, path=manifest)
    li.setArt({'icon': iconimage, 'thumb': iconimage})
    li.setContentLookup(False)
    li.setProperty('inputstream', 'inputstream.adaptive')
    li.setMimeType('application/dash+xml')
    li.setProperty('inputstream.adaptive.drm_legacy', drm_type + '|' + key64)
    li.setProperty('inputstream.adaptive.stream_headers', headers)
    li.setProperty('inputstream.adaptive.manifest_headers', headers)
    li.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(addon_handle, True, li)



###############################################################################
# MyRadioOnline.ro - Radio online romanesc pe categorii
###############################################################################

def myradioonline_list():
    """Afiseaza categoriile de radio de pe MyRadioOnline.ro"""
    import urllib.parse as _up
    for cat_name, stations in myradioonline_categories.items():
        count = len(stations)
        display = '[COLOR gold][B]' + cat_name + '[/B][/COLOR]  [COLOR gray](' + str(count) + ' posturi)[/COLOR]'
        li = xbmcgui.ListItem(display)
        li.setArt({'icon': thumb_myradioonline, 'thumb': thumb_myradioonline, 'fanart': fanart_myradioonline})
        li.setInfo('music', {'title': cat_name})
        cat_enc = _up.quote(cat_name, safe='')
        plugin_url = (sys.argv[0] + '?mode=53&url=' + cat_enc +
                      '&name=' + cat_enc +
                      '&iconimage=' + _up.quote(thumb_myradioonline, safe='') +
                      '&fanart=' + _up.quote(fanart_myradioonline, safe=''))
        xbmcplugin.addDirectoryItem(addon_handle, plugin_url, li, True)
    xbmcplugin.endOfDirectory(addon_handle)


def myradioonline_category(cat_name_enc):
    """Afiseaza posturile dintr-o categorie MyRadioOnline"""
    import urllib.parse as _up
    cat_name = _up.unquote(cat_name_enc)
    stations = myradioonline_categories.get(cat_name, [])
    if not stations:
        for k in myradioonline_categories:
            if k == cat_name or _up.quote(k, safe='') == cat_name_enc:
                stations = myradioonline_categories[k]
                cat_name = k
                break
    for st_name, st_url in stations:
        st_logo = myradioonline_logos.get(st_name, thumb_myradioonline)
        li = xbmcgui.ListItem('[COLOR white]' + st_name + '[/COLOR]')
        li.setArt({'icon': st_logo, 'thumb': st_logo, 'fanart': fanart_myradioonline})
        li.setInfo('music', {'title': st_name})
        li.setProperty('IsPlayable', 'true')
        play_url = (sys.argv[0] + '?mode=54&url=' + _up.quote(st_url, safe='') +
                    '&name=' + _up.quote(st_name, safe='') +
                    '&iconimage=' + _up.quote(st_logo, safe=''))
        xbmcplugin.addDirectoryItem(addon_handle, play_url, li, False)
    xbmcplugin.endOfDirectory(addon_handle)


def myradioonline_play(stream_url, st_name, iconimage):
    """Redeaza un stream radio de pe MyRadioOnline.ro"""
    import urllib.parse as _up
    url_dec = _up.unquote(stream_url)
    icon_dec = _up.unquote(iconimage) if iconimage else thumb_myradioonline
    li = xbmcgui.ListItem(st_name)
    li.setArt({'icon': icon_dec, 'thumb': icon_dec, 'fanart': fanart_myradioonline})
    li.setInfo('music', {'title': st_name})
    li.setProperty('IsPlayable', 'true')
    ua = 'User-Agent=Mozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29'
    if '|' not in url_dec:
        url_dec = url_dec + '|' + ua
    li.setPath(url_dec)
    xbmcplugin.setResolvedUrl(addon_handle, True, li)

###############################################################################
# FILME BUNE HD 1 (filmebunehd1.com) - Filme Online 3
###############################################################################

def filmebunehd_request(path):
    """Trimite request la filmebunehd1.com si returneaza continutul"""
    import urllib.request
    try:
        full_url = url_filmebunehd + path if not path.startswith('http') else path
        req = urllib.request.Request(full_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': url_filmebunehd + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        response = urllib.request.urlopen(req, timeout=20)
        raw = response.read()
        try:
            return raw.decode('utf-8')
        except Exception:
            return raw.decode('latin-1', errors='replace')
    except Exception as e:
        xbmc.log('filmebunehd_request error: ' + str(e), xbmc.LOGERROR)
        return ''

def filmebunehd_build_url(path_key, params):
    """Construieste un URL intern filmebunehd"""
    from urllib.parse import urlencode
    qs = urlencode(params)
    return url_filmebunehd + '/' + path_key + '?' + qs

def filmebunehd_router(url, fanart):
    """Dispatcher principal pentru filmebunehd1.com"""
    from urllib.parse import urlparse, parse_qs
    clean = url.rstrip('/')
    base = url_filmebunehd.rstrip('/')

    if clean == base or clean == base + '/index' or url == url_filmebunehd + '/':
        filmebunehd_main_menu(fanart)
    elif '/movies-categories' in url:
        filmebunehd_movie_categories(fanart)
    elif '/series-categories' in url:
        filmebunehd_series_categories(fanart)
    elif '/movie-list' in url:
        qs = parse_qs(urlparse(url).query)
        path = qs.get('path', ['/movies'])[0]
        page = int(qs.get('page', ['1'])[0])
        filmebunehd_list_movies(path, page, fanart)
    elif '/series-list' in url:
        qs = parse_qs(urlparse(url).query)
        path = qs.get('path', ['/tvshow'])[0]
        page = int(qs.get('page', ['1'])[0])
        filmebunehd_list_series(path, page, fanart)
    elif '/movie-sources' in url:
        qs = parse_qs(urlparse(url).query)
        slug = qs.get('slug', [''])[0]
        title = qs.get('title', [slug])[0]
        filmebunehd_movie_sources(slug, title, fanart)
    elif '/series-info' in url:
        qs = parse_qs(urlparse(url).query)
        slug = qs.get('slug', [''])[0]
        title = qs.get('title', [slug])[0]
        filmebunehd_series_info(slug, title, fanart)
    elif '/episode-sources' in url:
        qs = parse_qs(urlparse(url).query)
        slug = qs.get('slug', [''])[0]
        season = qs.get('season', ['1'])[0]
        episode = qs.get('episode', ['1'])[0]
        title = qs.get('title', [slug])[0]
        filmebunehd_episode_sources(slug, season, episode, title, fanart)
    elif '/top-imdb' in url:
        qs = parse_qs(urlparse(url).query)
        page = int(qs.get('page', ['1'])[0])
        filmebunehd_top_imdb(page, fanart)
    elif '/search' in url:
        qs = parse_qs(urlparse(url).query)
        query = qs.get('q', [''])[0]
        page = int(qs.get('page', ['1'])[0])
        filmebunehd_search(query, page, fanart)
    else:
        filmebunehd_main_menu(fanart)

def filmebunehd_main_menu(fanart):
    """Meniu principal: Filme, Seriale, Top IMDb, Cauta"""
    items = [
        ('[COLOR aqua][B]Filme[/B][/COLOR]', filmebunehd_build_url('movies-categories', {}), thumb_filmebunehd),
        ('[COLOR violet][B]Seriale[/B][/COLOR]', filmebunehd_build_url('series-categories', {}), thumb_filmebunehd),
        ('[COLOR aqua][B]Top[/COLOR] [COLOR violet]IMDb[/B][/COLOR]', filmebunehd_build_url('top-imdb', {'page': 1}), thumb_filmebunehd),
    ]
    for title, link, thumb in items:
        addDir(title, link, 40, thumb, fanart or fanart_filmebunehd,
               'Filme Online 3', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

def filmebunehd_movie_categories(fanart):
    """Submeniu categorii filme"""
    categories = [
        ('Toate Filmele', '/movies'),
        ('Actiune', '/movie/action'),
        ('Aventura', '/movie/adventure'),
        ('Animatie', '/movie/animation'),
        ('Comedie', '/movie/comedy'),
        ('Crima', '/movie/crime'),
        ('Documentar', '/movie/documentary'),
        ('Drama', '/movie/drama'),
        ('Familie', '/movie/family'),
        ('Fantasy', '/movie/fantasy'),
        ('Horror', '/movie/horror'),
        ('Mister', '/movie/mystery'),
        ('Romance', '/movie/romance'),
        ('SF', '/movie/science-fiction'),
        ('Thriller', '/movie/thriller'),
        ('Western', '/movie/western'),
    ]
    for name, path in categories:
        link = filmebunehd_build_url('movie-list', {'path': path, 'page': 1})
        addDir('[COLOR white][B]' + name + '[/B][/COLOR]', link, 40, thumb_filmebunehd,
               fanart or fanart_filmebunehd, 'Filme Online 3', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

def filmebunehd_series_categories(fanart):
    """Submeniu categorii seriale"""
    categories = [
        ('Toate Serialele', '/tvshow'),
        ('Actiune', '/tvshow/action'),
        ('Aventura', '/tvshow/adventure'),
        ('Animatie', '/tvshow/animation'),
        ('Comedie', '/tvshow/comedy'),
        ('Crima', '/tvshow/crime'),
        ('Drama', '/tvshow/drama'),
        ('Familie', '/tvshow/family'),
        ('Fantasy', '/tvshow/fantasy'),
        ('Horror', '/tvshow/horror'),
        ('Mister', '/tvshow/mystery'),
        ('Romance', '/tvshow/romance'),
        ('SF', '/tvshow/science-fiction'),
        ('Thriller', '/tvshow/thriller'),
    ]
    for name, path in categories:
        link = filmebunehd_build_url('series-list', {'path': path, 'page': 1})
        addDir('[COLOR white][B]' + name + '[/B][/COLOR]', link, 40, thumb_filmebunehd,
               fanart or fanart_filmebunehd, 'Filme Online 3', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

def filmebunehd_parse_cards(html):
    """Parseaza cardurile movie-grid-card din HTML, returneaza lista de dictionare"""
    import json as json_mod
    import re as re_mod
    cards = []
    pattern = re_mod.compile(r'onclick=["\']openMovieModal\((\{.*?\})\)["\']', re_mod.DOTALL)
    for m in pattern.finditer(html):
        try:
            raw = m.group(1)
            raw = raw.replace('&quot;', '"').replace('&#39;', "'")
            try:
                data = json_mod.loads(raw)
            except Exception:
                raw2 = re_mod.sub(r"'([^']*)'", lambda x: '"' + x.group(1).replace('"', '\\"') + '"', raw)
                data = json_mod.loads(raw2)
            if data.get('slug'):
                cards.append(data)
        except Exception:
            continue
    return cards

def filmebunehd_list_movies(path, page, fanart):
    """Lista filme cu paginare"""
    import re as re_mod
    if path.startswith('/'):
        if '?' in path:
            page_path = path + '&page=' + str(page) if page > 1 else path
        else:
            page_path = path + ('?page=' + str(page) if page > 1 else '')
    else:
        page_path = path
    html = filmebunehd_request(page_path)
    if not html:
        notify('[COLOR red]Nu s-au putut incarca filmele![/COLOR]')
        return
    cards = filmebunehd_parse_cards(html)
    if not cards:
        notify('[COLOR yellow]Niciun film gasit![/COLOR]')
        return
    for card in cards:
        slug = card.get('slug', '')
        title = card.get('title', slug)
        thumb = card.get('poster_url', thumb_filmebunehd)
        if thumb and not thumb.startswith('http'):
            thumb = url_filmebunehd + thumb
        link = filmebunehd_build_url('movie-sources', {'slug': slug, 'title': title})
        label = '[COLOR white][B]' + title + '[/B][/COLOR]'
        addDir(label, link, 40, str(thumb), fanart or fanart_filmebunehd,
               'Filme Online 3', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
    next_page = page + 1
    if re_mod.search(r'page=' + str(next_page), html) or re_mod.search(r'href=["\'][^"\']*\?page=' + str(next_page), html):
        next_link = filmebunehd_build_url('movie-list', {'path': path, 'page': next_page})
        addDir('[COLOR gold][B]>> Pagina ' + str(next_page) + ' >>[/B][/COLOR]',
               next_link, 40, thumb_filmebunehd, fanart or fanart_filmebunehd,
               'Filme Online 3', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

def filmebunehd_list_series(path, page, fanart):
    """Lista seriale cu paginare"""
    import re as re_mod
    if path.startswith('/'):
        if '?' in path:
            page_path = path + '&page=' + str(page) if page > 1 else path
        else:
            page_path = path + ('?page=' + str(page) if page > 1 else '')
    else:
        page_path = path
    html = filmebunehd_request(page_path)
    if not html:
        notify('[COLOR red]Nu s-au putut incarca serialele![/COLOR]')
        return
    cards = filmebunehd_parse_cards(html)
    if not cards:
        notify('[COLOR yellow]Niciun serial gasit![/COLOR]')
        return
    for card in cards:
        slug = card.get('slug', '')
        title = card.get('title', slug)
        thumb = card.get('poster_url', thumb_filmebunehd)
        if thumb and not thumb.startswith('http'):
            thumb = url_filmebunehd + thumb
        link = filmebunehd_build_url('series-info', {'slug': slug, 'title': title})
        label = '[COLOR cyan][B]' + title + '[/B][/COLOR]'
        addDir(label, link, 40, str(thumb), fanart or fanart_filmebunehd,
               'Filme Online 3', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
    next_page = page + 1
    if re_mod.search(r'page=' + str(next_page), html) or re_mod.search(r'href=["\'][^"\']*\?page=' + str(next_page), html):
        next_link = filmebunehd_build_url('series-list', {'path': path, 'page': next_page})
        addDir('[COLOR gold][B]>> Pagina ' + str(next_page) + ' >>[/B][/COLOR]',
               next_link, 40, thumb_filmebunehd, fanart or fanart_filmebunehd,
               'Filme Online 3', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

def filmebunehd_get_iframe_src(player_path):
    """Acceseaza /player/... si extrage src din iframe"""
    import re as re_mod
    html = filmebunehd_request(player_path)
    if not html:
        return None
    # src poate fi pe linie separata - folosim DOTALL
    m = re_mod.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re_mod.IGNORECASE | re_mod.DOTALL)
    if m:
        src = m.group(1).strip()
        if src and src != 'about:blank':
            return src
    # Fallback: cauta orice src= cu URL http
    m2 = re_mod.search(r'src=["\']( *https?://[^"\']+)["\']', html, re_mod.IGNORECASE)
    if m2:
        src = m2.group(1).strip()
        if src:
            return src
    return None

def filmebunehd_movie_sources(slug, title, fanart):
    """Extrage sursele unui film din /watch/slug"""
    import re as re_mod
    import json as json_mod
    html = filmebunehd_request('/watch/' + slug)
    if not html:
        notify('[COLOR red]Nu s-au putut incarca sursele![/COLOR]')
        return
    # Cauta playersData in JS
    players = []
    m = re_mod.search(r'playersData\s*=\s*(\[.*?\])', html, re_mod.DOTALL)
    if m:
        try:
            players = json_mod.loads(m.group(1))
        except Exception:
            pass
    # Fallback: cauta players in JSON din card
    if not players:
        m2 = re_mod.search(r'"players"\s*:\s*(\[.*?\])', html, re_mod.DOTALL)
        if m2:
            try:
                players = json_mod.loads(m2.group(1))
            except Exception:
                pass
    # Daca nu am gasit nimic, incearca /player/slug/server/1..4
    if not players:
        players = [{'provider': 'Server ' + str(i), 'url': '/player/' + slug + '/server/' + str(i)} for i in range(1, 5)]

    # Extrage tmdb_id din pagina HTML (pentru VixSrc)
    tmdb_id = None
    tmdb_m = re_mod.search(r'tmdb[_-]?id["\']?\s*[=:]\s*["\']?(\d+)', html, re_mod.IGNORECASE)
    if tmdb_m:
        tmdb_id = tmdb_m.group(1)
    if not tmdb_id:
        tmdb_m2 = re_mod.search(r'themoviedb\.org/movie/(\d+)', html)
        if tmdb_m2:
            tmdb_id = tmdb_m2.group(1)
    if not tmdb_id:
        tmdb_m3 = re_mod.search(r'["\']tmdb["\']?\s*:\s*["\']?(\d+)', html, re_mod.IGNORECASE)
        if tmdb_m3:
            tmdb_id = tmdb_m3.group(1)
    if not tmdb_id:
        # fallback: cauta multiembed/vixsrc video_id in orice iframe src din pagina
        tmdb_m4 = re_mod.search(r'video_id=(\d+)', html)
        if tmdb_m4:
            tmdb_id = tmdb_m4.group(1)
    # Fallback final: cauta TMDB ID prin titlu din JSON-LD sau titlul primit ca parametru
    if not tmdb_id:
        title_search = title
        year_search = None
        # Parsare corecta JSON-LD pentru a obtine titlul decodat (evita raw unicode escapes)
        try:
            import json as _json_mod
            jld_blocks = re_mod.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re_mod.DOTALL)
            for _blk in jld_blocks:
                try:
                    _data = _json_mod.loads(_blk)
                    if _data.get('@type') == 'Movie':
                        if _data.get('name'):
                            title_search = _data['name']
                        if _data.get('datePublished'):
                            year_search = str(_data['datePublished'])[:4]
                        break
                except Exception:
                    pass
        except Exception:
            # Fallback regex (poate returna unicode raw)
            jld = re_mod.search(r'"@type"\s*:\s*"Movie".*?"name"\s*:\s*"([^"]+)".*?"datePublished"\s*:\s*"(\d{4})', html, re_mod.DOTALL)
            if jld:
                title_search = jld.group(1)
                year_search = jld.group(2)
        xbmc.log('[FilmeBuneHD] TMDB search titlu="%s" an=%s' % (title_search, str(year_search)), xbmc.LOGINFO)
        tmdb_id = filmebunehd_get_tmdb_id_by_title(title_search, year_search)
    xbmc.log('[FilmeBuneHD] movie_sources slug=%s tmdb_id=%s' % (slug, str(tmdb_id)), xbmc.LOGINFO)

    found = 0
    for idx, p in enumerate(players):
        provider = p.get('provider', 'Server ' + str(idx + 1))
        player_url = p.get('url', '')
        if not player_url:
            player_url = '/player/' + slug + '/server/' + str(idx + 1)
        if not player_url.startswith('http'):
            player_url = '/player/' + slug + '/server/' + str(idx + 1)
        embed = filmebunehd_get_iframe_src(player_url)
        if embed:
            # extrage tmdb_id din embed daca nu l-am gasit deja
            if not tmdb_id:
                em = re_mod.search(r'[?&]video_id=(\d+)', embed)
                if em:
                    tmdb_id = em.group(1)
            stream = 'plugin://plugin.video.smr_link_tester/?mode=play_link&link=' + urllib.quote_plus(embed) + '&switch=play$nome=filmebunehd'
            label = '[COLOR gold][B]' + title + ' - ' + provider + '[/B][/COLOR]'
            listitem = xbmcgui.ListItem(label)
            listitem.setArt({'thumb': thumb_filmebunehd, 'icon': 'DefaultVideo.png'})
            listitem.setInfo('video', {'title': label})
            listitem.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=stream, listitem=listitem, isFolder=False)
            found += 1

    # Adauga sursele VixSrc dupa Vinovo
    if tmdb_id:
        vix_results = filmebunehd_vixsrc_scrape_movie(tmdb_id)
        for (lbl, stream_url) in vix_results:
            label = '[COLOR gold][B]' + title + ' - ' + lbl + '[/B][/COLOR]'
            listitem = xbmcgui.ListItem(label)
            listitem.setArt({'thumb': thumb_filmebunehd, 'icon': 'DefaultVideo.png'})
            listitem.setInfo('video', {'title': title})
            listitem.setMimeType('application/x-mpegURL')
            listitem.setContentLookup(False)
            listitem.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=stream_url, listitem=listitem, isFolder=False)
            found += 1

    if found == 0:
        notify('[COLOR red]Nicio sursa disponibila pentru acest film![/COLOR]')
    xbmcplugin.endOfDirectory(addon_handle)

def filmebunehd_series_info(slug, title, fanart):
    """Parseaza /watch/slug/info pentru sezoane si episoade"""
    import re as re_mod
    # Pagina /info are toate linkurile season=&episode= listate explicit
    html = filmebunehd_request('/watch/' + slug + '/info')
    if not html:
        # fallback la /watch/slug
        html = filmebunehd_request('/watch/' + slug)
    if not html:
        notify('[COLOR red]Nu s-au putut incarca episoadele![/COLOR]')
        return
    # Cauta linkuri de tip /watch/slug?season=S&episode=E
    pattern = re_mod.compile(r'href=["\']/watch/' + re_mod.escape(slug) + r'\?season=(\d+)&(?:amp;)?episode=(\d+)["\']')
    episodes = []
    seen = set()
    for m in pattern.finditer(html):
        s = int(m.group(1))
        e = int(m.group(2))
        key = (s, e)
        if key not in seen:
            seen.add(key)
            episodes.append((s, e))
    if not episodes:
        # Fallback: cauta season=N&episode=N oriunde
        pattern2 = re_mod.compile(r'season=(\d+)[&;](?:amp;)?episode=(\d+)')
        for m in pattern2.finditer(html):
            s = int(m.group(1))
            e = int(m.group(2))
            key = (s, e)
            if key not in seen:
                seen.add(key)
                episodes.append((s, e))
    if not episodes:
        # Fallback final: citeste episodesPerSeason si maxSeasons din JS
        m_eps = re_mod.search(r'episodesPerSeason\s*=\s*(\d+)', html)
        m_seas = re_mod.search(r'maxSeasons\s*=\s*(\d+)', html)
        if m_eps and m_seas:
            eps_per_season = int(m_eps.group(1))
            max_seasons = int(m_seas.group(1))
            for s in range(1, max_seasons + 1):
                for e in range(1, eps_per_season + 1):
                    episodes.append((s, e))
    if not episodes:
        notify('[COLOR yellow]Nu am gasit episoade pentru acest serial![/COLOR]')
        return
    episodes.sort()
    for s, e in episodes:
        ep_title = title + ' - S' + str(s).zfill(2) + 'E' + str(e).zfill(2)
        link = filmebunehd_build_url('episode-sources', {'slug': slug, 'season': s, 'episode': e, 'title': ep_title})
        label = '[COLOR white][B]Sezon ' + str(s) + ' Episod ' + str(e) + '[/B][/COLOR]'
        addDir(label, link, 40, thumb_filmebunehd, fanart or fanart_filmebunehd,
               ep_title, '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

def _vixsrc_parse_m3u8_variants(master_url, custom_headers=None):
    import urllib.request as _req
    try:
        hdrs = custom_headers if custom_headers else {'User-Agent': 'Mozilla/5.0'}
        req = _req.Request(master_url, headers=hdrs)
        with _req.urlopen(req, timeout=10) as r:
            if r.status != 200:
                return []
            data = r.read().decode('utf-8', errors='replace')
        lines = data.splitlines()
        variants = []
        base = master_url.rsplit('/', 1)[0]
        for i, line in enumerate(lines):
            if '#EXT-X-STREAM-INF' not in line:
                continue
            resolution = 'UNKNOWN'
            if 'RESOLUTION=' in line:
                try:
                    resolution = line.split('RESOLUTION=')[1].split(',')[0].strip()
                except Exception:
                    pass
            final_url = None
            for j in range(i + 1, len(lines)):
                nl = lines[j].strip()
                if not nl or nl.startswith('#'):
                    continue
                if nl.startswith('http'):
                    final_url = nl
                elif nl.startswith('/'):
                    from urllib.parse import urlparse as _up
                    p = _up(master_url)
                    final_url = p.scheme + '://' + p.netloc + nl
                else:
                    final_url = base + '/' + nl
                break
            if final_url:
                variants.append({'resolution': resolution, 'url': final_url})
        return variants
    except Exception as e:
        xbmc.log('[VixSrc] m3u8 parse error: ' + str(e), xbmc.LOGWARNING)
        return []


def _vixsrc_get_quality(res_val):
    if not res_val or res_val == 'UNKNOWN':
        return 'SD'
    r = res_val.lower()
    if '2160' in r or '3840' in r or '4k' in r:
        return '4K'
    if '1080' in r or '1920' in r:
        return '1080p'
    if '720' in r or '1280' in r:
        return '720p'
    import re as _re
    m = _re.search(r'x(\d+)', r)
    if m:
        h = int(m.group(1))
        if h >= 2160: return '4K'
        if h >= 1000: return '1080p'
        if h >= 700: return '720p'
    return 'SD'


def _vixsrc_merge_url_query(url, query_dict):
    if not query_dict:
        return url
    from urllib.parse import urlparse as _up, urlunparse as _uu, urlencode as _ue, parse_qsl as _pq
    parsed = _up(url)
    params = dict(_pq(parsed.query))
    params.update(query_dict)
    parts = list(parsed)
    parts[4] = _ue(params)
    return _uu(parts)


def _vixsrc_fetch_page(url, headers):
    import urllib.request as _req
    try:
        req = _req.Request(url, headers=headers)
        with _req.urlopen(req, timeout=12) as r:
            if r.status != 200:
                return None
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        xbmc.log('[VixSrc] fetch error ' + url + ': ' + str(e), xbmc.LOGWARNING)
        return None


def filmebunehd_get_tmdb_id_by_title(title, year=None):
    """Cauta TMDB ID dupa titlu pe themoviedb.org (fara API key)"""
    import urllib.request as _req
    import urllib.parse as _up
    import re as _re
    try:
        query = _up.quote_plus(title)
        url = 'https://www.themoviedb.org/search?query=' + query
        req = _req.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        html = _req.urlopen(req, timeout=10).read().decode('utf-8', errors='replace')
        # Gaseste toate /movie/{id} din HTML
        ids = _re.findall(r'/movie/(\d+)', html)
        if ids:
            tmdb_id = ids[0]
            xbmc.log('[FilmeBuneHD] TMDB search "%s" -> ID %s' % (title, tmdb_id), xbmc.LOGINFO)
            return tmdb_id
    except Exception as e:
        xbmc.log('[FilmeBuneHD] TMDB search error: ' + str(e), xbmc.LOGWARNING)
    return None


def filmebunehd_vixsrc_scrape_movie(tmdb_id):
    """VixSrc scraper pentru filme - similar cu cel de seriale dar URL /movie/{tmdb_id}"""
    import re as _re
    import urllib.request as _req
    import json as _json
    base_url = 'https://vixsrc.to'
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0'
    page_url = base_url + '/movie/' + str(tmdb_id)
    # Referer trebuie sa fie pagina filmului (nu root) pentru ca API-ul sa accepte request-ul
    headers = {
        'User-Agent': ua,
        'Referer': page_url,
        'Accept': 'application/json, */*',
        'Origin': base_url,
    }
    xbmc.log('[VixSrc] Interogare film: ' + page_url, xbmc.LOGINFO)

    # Incearca API endpoint /api/movie/{id}
    api_url = base_url + '/api/movie/' + str(tmdb_id)
    target_url = None
    try:
        api_req = _req.Request(api_url, headers=headers)
        with _req.urlopen(api_req, timeout=10) as r:
            if r.status == 200:
                api_data = _json.loads(r.read().decode('utf-8', errors='replace'))
                if 'src' in api_data:
                    from urllib.parse import urljoin as _uj
                    target_url = _uj(base_url, api_data['src'])
                    xbmc.log('[VixSrc] API film src: ' + target_url, xbmc.LOGINFO)
    except Exception as e:
        xbmc.log('[VixSrc] API film eroare (film poate sa nu existe pe VixSrc): ' + str(e), xbmc.LOGWARNING)

    if not target_url:
        # Filmul nu exista pe VixSrc
        xbmc.log('[VixSrc] Film TMDB ' + str(tmdb_id) + ' negasit pe VixSrc', xbmc.LOGWARNING)
        return []

    fetch_headers = {'User-Agent': ua, 'Referer': page_url}
    wp = _vixsrc_fetch_page(target_url, fetch_headers)
    if not wp:
        xbmc.log('[VixSrc] Nu s-a putut obtine pagina embed film', xbmc.LOGWARNING)
        return []

    # Daca e iframe, urmareste-l
    iframe_m = _re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', wp)
    if iframe_m:
        iframe_url = iframe_m.group(1)
        if not iframe_url.startswith('http'):
            iframe_url = base_url + iframe_url
        wp2 = _vixsrc_fetch_page(iframe_url, dict(headers, Referer=page_url))
        if wp2:
            wp = wp2

    # Extrage token din window.masterPlaylist.params (format: 'token': 'abc...')
    token_m = _re.search(r"['\"]?token['\"]?\s*:\s*['\"]([a-f0-9A-F\-]{10,})['\"]", wp)
    if not token_m:
        xbmc.log('[VixSrc] Token negasit in pagina film', xbmc.LOGWARNING)
        return []
    token = token_m.group(1)

    # Extrage expires
    exp_m = _re.search(r"['\"]?expires['\"]?\s*:\s*['\"](\d+)['\"]", wp)

    # Extrage playlist URL din window.streams (primul activ) sau window.masterPlaylist.url
    playlist_base = None
    streams_m = _re.search(r'window\.streams\s*=\s*(\[.*?\]);', wp, _re.DOTALL)
    if streams_m:
        try:
            streams_raw = streams_m.group(1).replace("\\'", "'").replace('\\/', '/')
            streams_data = _json.loads(streams_raw)
            active = [s for s in streams_data if s.get('active')]
            chosen = active[0] if active else streams_data[0]
            playlist_base = chosen['url'].split('?')[0]
        except Exception as _e:
            xbmc.log('[VixSrc] Streams parse eroare: ' + str(_e), xbmc.LOGWARNING)
    if not playlist_base:
        # fallback: cauta masterPlaylist.url
        pl_m = _re.search(r"url\s*:\s*['\"]([^'\"]+/playlist/[^'\"?#]+)['\"]", wp)
        if pl_m:
            playlist_base = pl_m.group(1).replace('\\/', '/')
    if not playlist_base:
        # fallback generic: orice URL /playlist/
        pl_m2 = _re.search(r"['\"]?(https?://[^'\"\\s]+/playlist/[^\s'\"?#]+)", wp)
        if pl_m2:
            playlist_base = pl_m2.group(1).replace('\\/', '/')
    if not playlist_base:
        xbmc.log('[VixSrc] URL playlist negasit in pagina film', xbmc.LOGWARNING)
        return []

    # Adauga .m3u8 daca lipseste
    if not playlist_base.endswith('.m3u8'):
        playlist_base = playlist_base + '.m3u8'
    master_url = playlist_base

    q_params = {'token': token}
    if exp_m:
        q_params['expires'] = exp_m.group(1)
    if _re.search(r'canPlayFHD\s*=\s*true', wp):
        q_params['h'] = '1'

    hdr_suffix = '|Referer=' + page_url + '&Origin=' + base_url + '&User-Agent=' + urllib.quote_plus(ua)
    m3u8_headers = {'Referer': page_url, 'User-Agent': ua}

    final_m3u8_check = _vixsrc_merge_url_query(master_url, q_params)
    variants = _vixsrc_parse_m3u8_variants(final_m3u8_check, custom_headers=m3u8_headers)

    if variants:
        results = []
        seen = set()
        for v in variants:
            res = v.get('resolution', 'UNKNOWN')
            height = res.split('x')[-1] if 'x' in res else res
            if height in seen:
                continue
            seen.add(height)
            q_label = _vixsrc_get_quality(res)
            rendition = height + 'p'
            rend_params = dict(q_params)
            rend_params['rendition'] = rendition
            rend_url = _vixsrc_merge_url_query(master_url, rend_params)
            stream = rend_url + hdr_suffix
            results.append(('[COLOR cyan]' + q_label + '[/COLOR]', stream))
        xbmc.log('[VixSrc] Gasit ' + str(len(results)) + ' variante film pt TMDB ' + str(tmdb_id), xbmc.LOGINFO)
        if results:
            return results

    final_m3u8 = _vixsrc_merge_url_query(master_url, q_params)
    stream = final_m3u8 + hdr_suffix
    xbmc.log('[VixSrc] Fallback master m3u8 film pt TMDB ' + str(tmdb_id), xbmc.LOGINFO)
    return [('[COLOR cyan]HD[/COLOR]', stream)]


def filmebunehd_vixsrc_scrape(tmdb_id, season, episode):
    import re as _re
    import urllib.request as _req
    import json as _json
    base_url = 'https://vixsrc.to'
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0'
    page_url = base_url + '/tv/' + str(tmdb_id) + '/' + str(season) + '/' + str(episode)
    headers = {'User-Agent': ua, 'Referer': base_url + '/'}
    xbmc.log('[VixSrc] Interogare: ' + page_url, xbmc.LOGINFO)

    # Incearca API endpoint
    api_url = page_url.replace('/tv/', '/api/tv/')
    target_url = page_url
    try:
        req = _req.Request(api_url, headers=headers)
        with _req.urlopen(req, timeout=10) as r:
            if r.status == 200:
                api_data = _json.loads(r.read().decode('utf-8', errors='replace'))
                if 'src' in api_data:
                    from urllib.parse import urljoin as _uj
                    target_url = _uj(base_url, api_data['src'])
    except Exception as e:
        xbmc.log('[VixSrc] API fallback: ' + str(e), xbmc.LOGWARNING)

    wp = _vixsrc_fetch_page(target_url, dict(headers, Referer=page_url))
    if not wp:
        xbmc.log('[VixSrc] Nu s-a putut obtine pagina player', xbmc.LOGWARNING)
        return []

    # Fallback: urmareste iframe-uri
    pat_token = re.compile(r"['\"]token['\"]\s*:\s*['\"](\w+)['\"]")
    for _ in range(3):
        if pat_token.search(wp):
            break
        ip_m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', wp, re.IGNORECASE)
        if not ip_m:
            break
        from urllib.parse import urljoin as _uj
        iframe_url = _uj(page_url, ip_m.group(1))
        wp2 = _vixsrc_fetch_page(iframe_url, dict(headers, Referer=page_url))
        if wp2:
            wp = wp2
        else:
            break

    tk_m = pat_token.search(wp)
    if not tk_m:
        xbmc.log('[VixSrc] Token negasit in pagina', xbmc.LOGWARNING)
        return []

    token = tk_m.group(1)
    raw_url_m = re.search(r"(?:['\"]url['\"]\s*|\burl\s*):\s*['\"]([^'\"]+)['\"]", wp)
    if not raw_url_m:
        xbmc.log('[VixSrc] URL master m3u8 negasit', xbmc.LOGWARNING)
        return []

    raw_url = raw_url_m.group(1).replace('\\/', '/').replace('\\u0026', '&').replace('\\u003d', '=')
    master_url = re.sub(r'(/playlist/[^/?]+)(?!\.m3u8)(?=[?#]|$)', r'\1.m3u8', raw_url)

    q_params = {'token': token}
    exp_m = re.search(r"['\"]expires['\"]\s*:\s*['\"](\d+)['\"]", wp)
    if exp_m:
        q_params['expires'] = exp_m.group(1)
    if re.search(r'canPlayFHD\s*=\s*true', wp):
        q_params['h'] = '1'

    hdr_suffix = '|Referer=' + page_url + '&Origin=' + base_url + '&User-Agent=' + urllib.quote_plus(ua)
    m3u8_headers = {'Referer': page_url, 'User-Agent': ua}

    # Parseaza variantele din master pentru a afla ce rezolutii exista
    final_m3u8_check = _vixsrc_merge_url_query(master_url, q_params)
    variants = _vixsrc_parse_m3u8_variants(final_m3u8_check, custom_headers=m3u8_headers)

    if variants:
        results = []
        seen = set()
        for v in variants:
            res = v.get('resolution', 'UNKNOWN')
            # Extrage inaltimea (ex: "1920x1080" -> "1080")
            height = res.split('x')[-1] if 'x' in res else res
            if height in seen:
                continue
            seen.add(height)
            q_label = _vixsrc_get_quality(res)
            # Construieste master m3u8 cu rendition specific - evita EOF din variant individual
            rendition = height + 'p'
            rend_params = dict(q_params)
            rend_params['rendition'] = rendition
            rend_url = _vixsrc_merge_url_query(master_url, rend_params)
            stream = rend_url + hdr_suffix
            results.append(('[COLOR cyan]' + q_label + '[/COLOR]', stream))
        xbmc.log('[VixSrc] Gasit ' + str(len(results)) + ' variante pt TMDB ' + str(tmdb_id), xbmc.LOGINFO)
        if results:
            return results

    # Fallback: master fara rendition
    final_m3u8 = _vixsrc_merge_url_query(master_url, q_params)
    stream = final_m3u8 + hdr_suffix
    xbmc.log('[VixSrc] Fallback master m3u8 pt TMDB ' + str(tmdb_id), xbmc.LOGINFO)
    return [('[COLOR cyan]HD[/COLOR]', stream)]


def filmebunehd_episode_sources(slug, season, episode, title, fanart):
    import re as re_mod
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    found = 0
    tmdb_id = None
    s_str = str(season)
    e_str = str(episode)

    for i in range(1, 4):
        player_path = '/player/' + slug + '/season/' + s_str + '/episode/' + e_str + '/server/' + str(i)
        embed = filmebunehd_get_iframe_src(player_path)
        if not embed:
            continue
        embed = embed.replace('&amp;', '&').replace('&#38;', '&').strip()
        if not embed.startswith('http'):
            continue
        if not tmdb_id:
            m = re_mod.search(r'[?&]video_id=(\d+)', embed)
            if m:
                tmdb_id = m.group(1)
            if not tmdb_id:
                m2 = re_mod.search(r'/embed/tv/(\d+)/', embed)
                if m2:
                    tmdb_id = m2.group(1)
            if not tmdb_id:
                m3 = re_mod.search(r'/embed/(?:tv|serie)/(\d+)', embed)
                if m3:
                    tmdb_id = m3.group(1)

    xbmc.log('[FilmeBuneHD] episode_sources slug=%s s=%s e=%s tmdb_id=%s' % (slug, s_str, e_str, str(tmdb_id)), xbmc.LOGINFO)

    if tmdb_id:
        vix_results = filmebunehd_vixsrc_scrape(tmdb_id, s_str, e_str)
        for (lbl, stream_url) in vix_results:
            label = '[COLOR gold][B]' + title + ' - ' + lbl + '[/B][/COLOR]'
            listitem = xbmcgui.ListItem(label)
            listitem.setArt({'thumb': thumb_filmebunehd, 'icon': 'DefaultVideo.png'})
            listitem.setInfo('video', {'title': title, 'season': int(season), 'episode': int(episode)})
            listitem.setProperty('IsPlayable', 'true')
            listitem.setMimeType('application/x-mpegURL')
            listitem.setContentLookup(False)
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=stream_url, listitem=listitem, isFolder=False)
            found += 1

    if found == 0:
        notify('[COLOR red]Nicio sursa disponibila pentru acest episod![/COLOR]')
    xbmcplugin.endOfDirectory(addon_handle)
def filmebunehd_top_imdb(page, fanart):
    """Lista Top IMDb de pe /popular"""
    import re as re_mod
    path = '/popular' + ('?page=' + str(page) if page > 1 else '')
    html = filmebunehd_request(path)
    if not html:
        notify('[COLOR red]Nu s-a putut incarca Top IMDb![/COLOR]')
        return
    cards = filmebunehd_parse_cards(html)
    if not cards:
        notify('[COLOR yellow]Niciun film gasit in Top IMDb![/COLOR]')
        return
    for card in cards:
        slug = card.get('slug', '')
        title = card.get('title', slug)
        thumb = card.get('poster_url', thumb_filmebunehd)
        if thumb and not thumb.startswith('http'):
            thumb = url_filmebunehd + thumb
        ctype = card.get('type', 'movie')
        if ctype == 'tvshow':
            link = filmebunehd_build_url('series-info', {'slug': slug, 'title': title})
        else:
            link = filmebunehd_build_url('movie-sources', {'slug': slug, 'title': title})
        label = '[COLOR gold][B]' + title + '[/B][/COLOR]'
        addDir(label, link, 40, str(thumb), fanart or fanart_filmebunehd,
               'Top IMDb', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
    next_page = page + 1
    if re_mod.search(r'page=' + str(next_page), html):
        next_link = filmebunehd_build_url('top-imdb', {'page': next_page})
        addDir('[COLOR gold][B]>> Pagina ' + str(next_page) + ' >>[/B][/COLOR]',
               next_link, 40, thumb_filmebunehd, fanart or fanart_filmebunehd,
               'Top IMDb', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

def filmebunehd_search(query, page, fanart):
    """Cauta filme si seriale pe filmebunehd1.com"""
    import re as re_mod
    from urllib.parse import quote_plus
    if not query:
        query = get_search_string(heading='Cauta Film sau Serial')
        if not query:
            return
    path = '/search?q=' + quote_plus(query) + ('&page=' + str(page) if page > 1 else '')
    html = filmebunehd_request(path)
    if not html:
        notify('[COLOR red]Nu s-a putut efectua cautarea![/COLOR]')
        return
    cards = filmebunehd_parse_cards(html)
    if not cards:
        notify('[COLOR yellow]Niciun rezultat pentru: ' + query + '[/COLOR]')
        xbmcplugin.endOfDirectory(addon_handle)
        return
    for card in cards:
        slug = card.get('slug', '')
        title = card.get('title', slug)
        thumb = card.get('poster_url', thumb_filmebunehd)
        if thumb and not thumb.startswith('http'):
            thumb = url_filmebunehd + thumb
        ctype = card.get('type', 'movie')
        if ctype == 'tvshow':
            link = filmebunehd_build_url('series-info', {'slug': slug, 'title': title})
            type_tag = '[COLOR aqua][Serial][/COLOR] '
        else:
            link = filmebunehd_build_url('movie-sources', {'slug': slug, 'title': title})
            type_tag = '[COLOR lime][Film][/COLOR] '
        label = type_tag + '[B]' + title + '[/B]'
        addDir(label, link, 40, str(thumb), fanart or fanart_filmebunehd,
               'Cauta Film sau Serial', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')
    next_page = page + 1
    if re_mod.search(r'page=' + str(next_page), html) or re_mod.search(r'page[=\-]' + str(next_page), html):
        next_link = filmebunehd_build_url('search', {'q': query, 'page': next_page})
        addDir('[COLOR lime][B]>> Pagina ' + str(next_page) + ' >>[/B][/COLOR]',
               next_link, 40, thumb_filmebunehd, fanart or fanart_filmebunehd,
               'Cauta Film sau Serial', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '')

###############################################################################
# END FILME BUNE HD 1
###############################################################################

def SKindex():
    
    getData(url_principal, '')
    xbmcplugin.endOfDirectory(addon_handle)

def get_params():
    param=[]
    paramstring=sys.argv[2]
    if len(paramstring)>=2:
        params=sys.argv[2]
        cleanedparams=params.replace('?','')
        if (params[len(params)-1]=='/'):
            params=params[0:len(params)-2]
        pairsofparams=cleanedparams.split('&')
        param={}
        for i in range(len(pairsofparams)):
            splitparams={}
            splitparams=pairsofparams[i].split('=')
            if (len(splitparams))==2:
                param[splitparams[0]]=splitparams[1]

    return param
    
    
    
    
    
    
    

params=get_params()
url=None
name=None
mode=None
iconimage=None
fanart=None
description=None
subtitle=None

try:
    url=urllib.unquote(params["url"])
    #url=urllib.unquote_plus(params["url"]).decode('utf-8')
except:
    pass

try:
    #name=urllib.unquote(params["name"])
    name=urllib.unquote_plus(params["name"])
except:
    pass

try:
    #iconimage=urllib.unquote(params["iconimage"])
    iconimage=urllib.unquote_plus(params["iconimage"])
except:
    pass

try:
    mode=int(params["mode"])
except:
    pass

try:
    #fanart=urllib.unquote(params["fanart"])
    fanart=urllib.unquote_plus(params["fanart"])
except:
    pass

try:
    #description=urllib.unquote(params["description"])
    description=urllib.unquote_plus(params["description"])
except:
    pass

try:
    subtitle=urllib.unquote_plus(params["subtitle"])
except:
    pass

try:
    fav_mode=int(params["fav_mode"])
except:
    pass

if mode==None:
    adult_section_set_unlocked(False)
    xbmcplugin.setContent(addon_handle, 'movies')
    check_addon()
    parental_password()
    SKindex()
    SetView('List')

elif mode==1:
    #url = base64.b16decode(base64.b32decode(codecs.decode(url, '\x72\x6f\x74\x31\x33')))
    #url = base64.b64decode(url)
    url = base64.b64decode(base64.b16decode(url))
    try:
        url = url.decode('utf-8')
    except:
        pass
    if url == url_tv_adult:
        if not adult_section_is_unlocked():
            if not adult_section_password():
                xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)
                exit()
            adult_section_set_unlocked(True)
    else:
        adult_section_set_unlocked(False)
    playback_started = bool(getData(url, fanart))
    if url == url_tv_adult:
        xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)
    elif not playback_started:
        xbmcplugin.endOfDirectory(addon_handle)

#elif mode==2:
#    getChannelItems(name,url,fanart)
#    xbmcplugin.endOfDirectory(addon_handle)

#elif mode==3:
#    getSubChannelItems(name,url,fanart)
#    xbmcplugin.endOfDirectory(addon_handle)


#Configurações
elif mode==4:
    xbmcaddon.Addon().openSettings()
    xbmcgui.Dialog().ok()
    xbmc.executebuiltin("XBMC.Container.Refresh()")

#Link Vazio
elif mode==5:
    xbmc.executebuiltin("XBMC.Container.Refresh()")

elif mode==6:
    ytbmode = addon.getSetting('ytbmode')
    if int(ytbmode) == 0:
        pluginquerybyJSON(url)
    elif int(ytbmode) == 1:
        getPlaylistLinksYoutube(url)
    else:
        youtube(url)
    xbmcplugin.endOfDirectory(addon_handle)

#elif mode==7:
#    Pesquisa()

elif mode==9:
    xbmcgui.Dialog().ok(titulo_vip, vip_dialogo)
    xbmcaddon.Addon().openSettings()
    xbmcgui.Dialog().ok()
    xbmc.executebuiltin("XBMC.Container.Refresh()")

elif mode==10:
    adult(name, url, iconimage, description, subtitle)
    xbmcplugin.endOfDirectory(addon_handle)

elif mode==11:
    playlist(name, url, iconimage, description, subtitle)
    xbmcplugin.endOfDirectory(addon_handle)

#elif mode==12:
#    CheckUpdate(True)
#    xbmc.executebuiltin("XBMC.Container.Refresh()")

elif mode==13:
    try:
        name = name.split('\\ ')[1]
    except:
        pass
    try:
        name = name.split('  - ')[0]
    except:
        pass
    addFavorite(name,url,fav_mode,subtitle,iconimage,fanart,description)

elif mode==14:
    try:
        name = name.split('\\ ')[1]
    except:
        pass
    try:
        name = name.split('  - ')[0]
    except:
        pass
    rmFavorite(name)

elif mode==15:
    #xbmcplugin.setContent(addon_handle, 'movies')
    getFavorites()
    #xbmcplugin.endOfDirectory(addon_handle)

elif mode==16:
    individual_player(name, url, iconimage, description, subtitle)
    #xbmcplugin.endOfDirectory(addon_handle)

elif mode==17:
    youtube_live_player(name, url, iconimage, description, subtitle)
    #xbmcplugin.endOfDirectory(addon_handle)

elif mode==18:
    m3u8_player(name, url, iconimage, description, subtitle)
    #xbmcplugin.endOfDirectory(addon_handle)

elif mode==20:
    mpd_player(name, url, iconimage, description, subtitle)
    #xbmcplugin.endOfDirectory(addon_handle)

elif mode==21:
    resolved = vidzstore_filme(url, fanart)
    if not resolved:
        xbmcplugin.endOfDirectory(addon_handle)

elif mode==22:
    resolved = sitefilme_filme(url, fanart)
    if not resolved:
        xbmcplugin.endOfDirectory(addon_handle)

elif mode==23:
    dinbox_list_channels(url)
    xbmcplugin.endOfDirectory(addon_handle)

elif mode==25:
    dinbox_play(url, name, iconimage, description)

elif mode==26:
    paradisehill_filme(url, fanart)
    xbmcplugin.endOfDirectory(addon_handle)

elif mode==27:
    resolved = paradisehill_play(url, fanart)
    if not resolved:
        xbmcplugin.endOfDirectory(addon_handle)

elif mode==28:
    sportsonline_play(name, url, iconimage, description, subtitle)

elif mode==31:
    streami_play(name, url, iconimage, description, subtitle)

elif mode==32:
    vavoo_list_channels(url)
    xbmcplugin.endOfDirectory(addon_handle)

elif mode==33:
    vavoo_play(name, url, iconimage, description, subtitle)

elif mode==34:
    rojadirecta_play(name, url, iconimage, description, subtitle)

elif mode==35:
    portalultautv_filme(url, fanart)
    xbmcplugin.endOfDirectory(addon_handle)

elif mode==36:
    # setResolvedUrl e apelat intern de portalultautv_play
    portalultautv_play(url, fanart)

elif mode==30:
    daddylive_play(name, url, iconimage, description, subtitle)

elif mode==19:
    xbmcgui.Dialog().textviewer('Informação: '+name, description)

elif mode==40:
    filmebunehd_router(url, fanart)
    xbmcplugin.endOfDirectory(addon_handle)

elif mode==50:
    sky_italia_list()

elif mode==51:
    sky_italia_play(url, name, iconimage)

elif mode==52:
    myradioonline_list()

elif mode==53:
    myradioonline_category(url)

elif mode==54:
    myradioonline_play(url, name, iconimage)

elif mode==55:
    tvzone_play(name, url, iconimage, description, subtitle)

elif mode==56:
    tvzone_toggle_favorite(url, name)

elif mode==57:
    # setResolvedUrl e apelat intern de veziaici_vk_play
    veziaici_vk_play(url, name, iconimage)


