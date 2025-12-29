import sys
import xbmcgui
import xbmcplugin
import xbmcaddon
import requests
import urllib.parse
import re
from urllib.parse import urlencode

# Configurare Addon
ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = "https://api.themoviedb.org/3"
API_KEY = "8ad3c21a92a64da832c559d58cc63ab4"
IMG_BASE = "https://image.tmdb.org/t/p/w500"

# === POSTERE PERSONALIZATE PENTRU CATEGORII (poți schimba link-urile cu ce vrei tu) ===
CATEGORY_POSTERS = {
    'popular_movies':   'https://cherudek.github.io/FilmApp/film_app_screenshot2.png',   # Filme Populare
    'popular_tv':       'https://static.posters.cz/image/hp/106300.jpg',   # Seriale Populare (poți schimba)
    'classic_movies':   'https://r3media.ro/wp-content/uploads/2023/10/colaj-sergiu-nicolaescu-filme-696x490.jpg',   # Filme de Colecție (ex: poster retro românesc)
    'dsc_vod':          'https://wordpress.yololiv.com/wp-content/uploads/2023/04/Video-on-Demond_page-0001-1-1-1024x576.jpg',   # DSC VOD OnDemand (poster modern/dark)
    'live_tv':          'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSn_j48shLFF9qI88ZeGn6eR2HSOGiYQrv1cg&s',   # Live TV România (imagine cu TV/antena)
    'search':           'https://cdn.pixabay.com/photo/2021/08/17/06/33/detective-6552140_960_720.jpg',   # Căutare (lupa stilizată)
}

def get_json(url):
    try:
        r = requests.get(url, timeout=10)
        return r.json()
    except:
        return {}

def get_ids(content_type, tmdb_id):
    url = f"{BASE_URL}/{content_type}/{tmdb_id}/external_ids?api_key={API_KEY}"
    return get_json(url)

def get_stream_link(imdb_id, content_type, season=None, episode=None):
    # SuperEmbed – sursă principală stabilă
    try:
        if content_type == 'movie':
            embed_url = f"https://www.superembed.stream/api/v1/embed/movie/imdb/{imdb_id}"
        else:
            embed_url = f"https://www.superembed.stream/api/v1/embed/tv/imdb/{imdb_id}/{season}/{episode}"
        
        response = requests.get(embed_url, timeout=12).json()
        if response.get('stream'):
            return response['stream']
    except:
        pass

    # Fallback vechi
    sources = ["https://webstreamr.hayd.uk", "https://nuviostreams.hayd.uk"]
    pattern = r'url"\s*:\s*"(https?://[^"]+?(?:m3u8|mp4)[^"]*)"'
    
    for base_url in sources:
        try:
            if content_type == 'movie':
                api_url = f"{base_url}/stream/movie/{imdb_id}.json"
            else:
                api_url = f"{base_url}/stream/series/{imdb_id}:{season}:{episode}.json"

            response = requests.get(api_url, timeout=10).text
            match = re.search(pattern, response)
            if match:
                return match.group(1).replace('\\/', '/')
        except:
            continue

    return None

def add_directory(name, params, folder=True, thumb='', plot=''):
    url = f"{sys.argv[0]}?{urlencode(params)}"
    li = xbmcgui.ListItem(name)
    
    # Dacă nu e specificat thumb, folosim posterul personalizat pentru categorie
    final_thumb = thumb or CATEGORY_POSTERS.get(params.get('mode'), '')
    
    if final_thumb:
        li.setArt({'thumb': final_thumb, 'poster': final_thumb, 'fanart': final_thumb})
    
    li.setInfo('video', {'plot': plot or 'Fără descriere'})
    xbmcplugin.addDirectoryItem(HANDLE, url, li, folder)

def add_playable_item(name, stream_url, thumb='', plot=''):
    li = xbmcgui.ListItem(name)
    if thumb:
        li.setArt({'thumb': thumb, 'poster': thumb, 'fanart': thumb})
    li.setInfo('video', {'plot': plot or 'Fără descriere'})
    li.setProperty('IsPlayable', 'true')
    li.setPath(stream_url)
    xbmcplugin.addDirectoryItem(HANDLE, stream_url, li, False)

def main_menu():
    add_directory("Filme Populare", 
                  {'mode': 'list', 'type': 'movie', 'page': '1'},
                  thumb=CATEGORY_POSTERS['popular_movies'])
    
    add_directory("Seriale Populare", 
                  {'mode': 'list', 'type': 'tv', 'page': '1'},
                  thumb=CATEGORY_POSTERS['popular_tv'])
    
    add_directory("Filme de Colecție (Clasice Românești)", 
                  {'mode': 'classic_movies'},
                  thumb=CATEGORY_POSTERS['classic_movies'])
    
    add_directory("DSC VOD OnDemand", 
                  {'mode': 'dsc_vod'},
                  thumb=CATEGORY_POSTERS['dsc_vod'])
    
    add_directory("Live TV România", 
                  {'mode': 'live_tv'},
                  thumb=CATEGORY_POSTERS['live_tv'])
    
    add_directory("Căutare", 
                  {'mode': 'search'},
                  thumb=CATEGORY_POSTERS['search'])
    
    xbmcplugin.endOfDirectory(HANDLE)

def classic_movies():
    classics = [
        {
            'title': 'Afacerea Protar (1956)',
            'url': 'https://ia800103.us.archive.org/19/items/AfacereaProtar/Afacerea%20Protar.mp4',
            'thumb': 'https://archive.org/services/img/AfacereaProtar',
            'plot': 'Comedie clasică românească regizată de Haralambie Boroș, cu Radu Beligan.'
        },
	{
        'title': 'Amintiri Din Copilarie',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://static.cinemagia.ro/img/resize/db/movie/00/19/68/amintiri-din-copilarie-227312l-576x0-w-2d5bc3cf.png',
        'url': 'https://ia800102.us.archive.org/6/items/AmintiriDinCopilrie/Amintiri%20din%20copil%C4%83rie.mp4'
      },
	  
	  {
        'title': 'Apa Ca Un Bivol Negru 1970',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://cinepub.ro/wp-content/uploads/2023/07/Apa-ca-un-bivol-negru-afis.jpg',
        'url': 'https://ia800101.us.archive.org/2/items/ApaCaUnBivolNegru/Apa%20ca%20un%20bivol%20negru.mp4'
      },
	  
	  {
        'title': 'Apoi S-A Nascut Legenda 1969',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://upload.wikimedia.org/wikipedia/ro/thumb/d/da/Apoi_s-a_nascut_legenda_1969.jpg/250px-Apoi_s-a_nascut_legenda_1969.jpg',
        'url': 'https://ia800809.us.archive.org/19/items/ApoiSANscutLegenda1968/Apoi%20s-a%20n%C4%83scut%20legenda%20%281968%29.mp4'
      },
	  {
        'title': 'Sapte Zile 1973',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://upload.wikimedia.org/wikipedia/ro/3/3d/%C8%98apte_zile.jpg',
        'url': 'https://ia600104.us.archive.org/35/items/ApteZile1973/%C5%9Eapte%20zile%201973.mp4'
      },
	  {
        'title': 'Asediul 1971',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://upload.wikimedia.org/wikipedia/ro/3/31/Asediul_1971.jpg',
        'url': 'https://ia600100.us.archive.org/5/items/Asediul1970/Asediul%201970.mp4'
      },
	 {
        'title': 'Asta-seara dansam in familie 1972',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://m.media-amazon.com/images/M/MV5BNTIwNDY2NjctMzViMy00MTEzLTliNTgtZjZjMDk5ZDJhYTUxXkEyXkFqcGc@._V1_QL75_UY281_CR16,0,190,281_.jpg',
        'url': 'https://ia800803.us.archive.org/32/items/AstaSearaDansam/Asta%20seara%20dansam.mp4'
      },
	  {
        'title': 'Baltagul 1969',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://m.media-amazon.com/images/M/MV5BMDhlZWU5NjMtYmMwMi00YTI3LTlmNjUtZjM1NzI1NTIzNTI3XkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg',
        'url': 'https://ia600808.us.archive.org/9/items/Baltagul1969/Baltagul%201969.mp4'
      },
	  	  {
        'title': 'Balul De Sambata Seara 1967',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://m.media-amazon.com/images/M/MV5BMzdjZDFiYjgtOGYxZi00ZWZiLWFmODQtNzRhODFhM2NiMWZiXkEyXkFqcGc@._V1_.jpg',
        'url': 'https://ia800600.us.archive.org/17/items/BalulDeSambataSeara/Balul%20de%20sambata%20seara.mp4'
      },
	  {
        'title': 'Bariera 1972',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://upload.wikimedia.org/wikipedia/ro/0/0e/Bariera_1972.jpg',
        'url': 'https://ia800807.us.archive.org/27/items/Bariera1972/Bariera%201972.mp4'
      },
	  {
        'title': 'Bijuterii De Familie 1958',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://i.ytimg.com/vi/doVKJ-sFdtU/sddefault.jpg',
        'url': 'https://ia800804.us.archive.org/10/items/BijuteriiDeFamilie1957FilmFull/Bijuterii%20de%20familie%201957%20film%20full.mp4'
      },
	  {
        'title': 'Canarul Si Viscolul 1970',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://m.media-amazon.com/images/M/MV5BOGZkYTcyOGMtMGE4ZS00NWY1LWFhZjAtZjlkZWNhZjRmNjBmXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg',
        'url': 'https://ia600102.us.archive.org/33/items/CanarulSiViscolul/canarul%20si%20viscolul.mp4'
      },
	  	  {
        'title': 'Casa Neterminata 1964',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://static.cinemagia.ro/img/db/movie/02/61/98/casa-neterminata-880830l.jpg',
        'url': 'https://ia801002.us.archive.org/11/items/CasaNeterminata/casa%20neterminata.mp4'
      },
	  {
        'title': 'Cine Va Deschide Usa 1969',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://static.cinemagia.ro/img/resize/db/movie/01/79/12/cine-va-deschide-usa-131242l-600x0-w-20378c55.jpg',
        'url': 'https://ia800601.us.archive.org/1/items/CineVaDeschideUsa1969/Cine%20Va%20Deschide%20Usa%201969.mp4'
      },
	  {
        'title': 'Citadela Sfaramata 1957',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://upload.wikimedia.org/wikipedia/ro/thumb/f/f5/The_Broken_Citadel.jpg/250px-The_Broken_Citadel.jpg',
        'url': 'https://ia800809.us.archive.org/35/items/CitadelaSfrrmata/Citadela%20sf%C4%83r%C3%A2mat%C4%83.mp4'
      },
	  {
        'title': 'Codin 1963',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://m.media-amazon.com/images/M/MV5BNzkxOGY5OTEtNTQ5Yi00NDUzLWE2NDgtYzBjNmFkNTg5MDI3XkEyXkFqcGc@._V1_.jpg',
        'url': 'https://ia800801.us.archive.org/6/items/Codin1963/Codin%20%281963.mp4'
      },
	  {
        'title': 'Comoara Din Vadul Vechi 1964',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://m.media-amazon.com/images/M/MV5BMzg3YTI5NzgtYmMxOC00ZDUzLTlkNjUtYmQ0YmQ4NzVlMDgxXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg',
        'url': 'https://ia800803.us.archive.org/32/items/ComoaraDinVadulVechi/Comoara%20din%20vadul%20vechi.mp4'
      },
	  {
        'title': 'Diminetile Unui Baiat Cuminte 1967',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://cinepub.ro/wp-content/uploads/2025/04/Diminetile-unui-baiat-cuminte-afis.jpg',
        'url': 'https://ia800809.us.archive.org/31/items/DiminetileUnuiBaiatCuminte/diminetile%20unui%20baiat%20cuminte.mp4'
      },
	  {
       'title': 'Dincolo De Brazi 1958',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://m.media-amazon.com/images/M/MV5BYWIyNzk1YjUtZjQwZC00NzkwLTllNGQtYWZmZDE4MjI2ODg1XkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg',
        'url': 'https://ia600100.us.archive.org/15/items/DincoloDeBraziFilmRomanesc/dincolo%20de%20brazi_film%20romanesc.mp4'
      },
	  {
        'title': 'Directorul Nostru 1955',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://upload.wikimedia.org/wikipedia/ro/9/92/Directorul_nostru.jpg',
        'url': 'https://ia600808.us.archive.org/32/items/DirectorulNostru1955/Directorul%20Nostru%201955.mp4'
      },
	  {
        'title': 'Doi Vecini 1958',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://m.media-amazon.com/images/M/MV5BOGFkNzVkNjEtMTgxMS00YWJjLWJjNTItZGNjMDg5Yzg2MTY1XkEyXkFqcGc@._V1_.jpg',
        'url': 'https://ia800100.us.archive.org/8/items/DoiVecini1959/Doi%20vecini%281959%29.mp4'
      },
	  {
        'title': 'Dragoste La Zero Grade 1964',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://m.media-amazon.com/images/M/MV5BOTRiNjIzOTktMzAwNy00OWQzLWEwMDctOTc5NzZiZjg4ODBjXkEyXkFqcGc@._V1_QL75_UY281_CR107,0,190,281_.jpg',
        'url': 'https://ia800809.us.archive.org/1/items/DragosteLaZeroGrade/Dragoste%20la%20zero%20grade.mp4'
      },
	  {
        'title': 'Duhul Aurului 1974',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://a.ltrbxd.com/resized/film-poster/1/8/1/6/7/7/181677-lust-for-gold-1974-0-230-0-345-crop.jpg?v=07d0bff096',
        'url': 'https://ia800104.us.archive.org/27/items/DuhulAurului/Duhul%20Aurului.mp4'
      },
	  {
        'title': 'Eruptia 1957',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://cinepub.ro/wp-content/uploads/2024/04/Eruptia-afis.jpg',
        'url': 'https://ia800809.us.archive.org/0/items/EruptiaFilmRomanesc1957/Eruptia-film%20romanesc%201957.mp4'
      },
	 {
       'title': 'Evadarea 1975',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://upload.wikimedia.org/wikipedia/ro/7/75/Evadarea_1975.jpg',
        'url': 'https://ia800103.us.archive.org/17/items/AzASzpAkinekASzemeKk_201711/Evadarea1975.mp4'
      },
	  	 {
        'title': 'In Sat La Noi 1951',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://upload.wikimedia.org/wikipedia/ro/thumb/e/ee/%C3%8En_sat_la_noi.jpg/200px-%C3%8En_sat_la_noi.jpg',
        'url': 'https://ia800803.us.archive.org/11/items/InSatLaNoi1951/In%20sat%20la%20noi%20%281951%29.mp4'
      },
	  {
        'title': 'LA MOARA CU NOROC 1957',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://cinepub.ro/wp-content/uploads/2023/06/La-moara-cu-noroc-afis.jpg',
        'url': 'https://ia800801.us.archive.org/30/items/LaMoaraCuNoroc1955/La%20moara%20cu%20noroc%20%281955%29.mp4'
      },
	  	{
        'title': 'Mingea 1958',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://upload.wikimedia.org/wikipedia/ro/thumb/9/93/1958-Mingea_S.jpg/250px-1958-Mingea_S.jpg',
        'url': 'https://ia800101.us.archive.org/11/items/Meandre1967/mingea.mp4'
      },
	 {
        'title': 'Mofturi 1900 1964',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://upload.wikimedia.org/wikipedia/ro/5/55/Mofturi_1900.jpg',
        'url': 'https://ia600101.us.archive.org/24/items/Mofturi19001964/Mofturi%201900%201964.mp4'
      },
	  {
        'title': 'Neamul Soimarestilor 1965',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://static.cinemagia.ro/img/db/movie/00/11/72/neamul-soimarestilor-107296l.jpg',
        'url': 'https://ia800103.us.archive.org/11/items/NeamulSoimarestilor/neamul%20soimarestilor.mp4'
      },
	  	  {
        'title': 'Nu Vreau Sa Ma Insor 1961',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://cinepub.ro/wp-content/uploads/2024/02/Nu-vreau-sa-ma-insor-afis.jpg',
        'url': 'https://ia800601.us.archive.org/14/items/NuVreauSaMaInsorFilmRomanesc/Nu%20vreau%20sa%20ma%20insor%20-film%20romanesc.mp4'
      },
	{
        'title': 'Nunta De Piatra 1973',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://m.media-amazon.com/images/M/MV5BZGUzOTgyZTItNDAwNy00NjNkLWIwYmQtOTY3YzIzYjJmNjljXkEyXkFqcGc@._V1_.jpg',
        'url': 'https://ia800101.us.archive.org/18/items/NuntaDePiatr/Nunta%20de%20Piatr%C4%83.mp4'
      },
	{
        'title': 'O Lume Fara Cer 1981',
		'desc': '🏛Filme Colectie RO🏛',
        'thumb': 'https://m.media-amazon.com/images/M/MV5BYTkzM2Y5MmYtMjhkOC00YTExLWEwNjUtNzgzZmJkYWE1MzdmXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg',
        'url': 'https://ia800104.us.archive.org/34/items/OLumeFaraCer/O%20Lume%20Fara%20Cer.mp4'
      },
    ]
    for film in classics:
        add_playable_item(film['title'], film['url'], thumb=film.get('thumb'), plot=film.get('plot'))
    xbmcplugin.endOfDirectory(HANDLE)

def dsc_vod():
    dsc_films = [
 	  {
        'title': 'Wellcome DSC MEDIA TV',
		'desc': '🎬.🎬',
        'thumb': 'https://ia600108.us.archive.org/26/items/descarcare222/WELL.png',
        'url': 'https://ia601707.us.archive.org/24/items/hubdsc/hubdsc.mp4'
      },   
    
        {
            'title': 'The Legend Of Ochi (2025)',
            'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDArl8BM3Gndv3DjmT37Ux9w#.mp4',
            'thumb': 'https://beam-images.warnermediacdn.com/BEAM_LWM_DELIVERABLES/d7a88d35-e424-443b-a9ea-30f46450a79c/ed20f130-67a1-11f0-85e1-12d03b70fa8b?host=wbd-images.prod-vod.h264.io&partner=beamcom',
            'plot': '🎬Într-un sat izolat de pe insula Carpathia, o fată timidă este crescută să se teamă de o specie animală evazivă numită ochi. Dar când descoperă că un pui de ochi rănit a fost lăsat în urmă, ea evadează într-o misiune de a-l aduce acasă.🎬'
        },
	  {
        'title': 'Kingdom.4.Return.Of.The.Great.General.2024',
		'plot': '🎬Când regatul Qin este invadat de vecinul Cho, legendarul general Ohki pornește să înfrunte armatele invadatoare în această epopee istorică plină de acțiune.🎬',
        'thumb': 'https://occ-0-391-299.1.nflxso.net/dnm/api/v6/mAcAr9TxZIVbINe88xb3Teg5_OA/AAAABZk3WR3mXyYp8gWYmuuKXJ3_5Sz81SthmyqHeHTrm-Q7yw353Fwe12RLyH5XJCmbtmUZe6j5ZN47Q0m7OVzVaNjOOzrhbWhVU3eD.jpg?r=51b',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDHRbN9iSJRH2el5qp7_m52o#.mp4'
      },
 	  {
        'title': 'Rebel Moon - Part One: A Child of Fire (2023)',
		'desc': '🎬Armatele nemiloase ale Planetei Mamă amenință un sătuc liniștit de pe o lună îndepărtată, iar un outsider misterios ajunge să fie singura lui șansă🎬',
        'thumb': 'https://theactionelite.com/wp-content/uploads/2023/12/Sofia-Boutella-and-cast-in-Rebel-Moon-review.webp',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDK5466uNXwU24kOrljKqyG0#.mp4'
      },
	  {
        'title': 'Rebel Moon Part Two The Scargiver 2024',
		'desc': '🎬Pe fundalul pregătirilor de luptă ale rebelilor contra forțelor Planetei Mamă, apar legături indestructibile, se făuresc eroi și se nasc legende.🎬',
        'thumb': 'https://everythingmoviereviews.com/wp-content/uploads/2024/04/rebelmoonpart2-1.jpeg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDCjT2ZxgLxuhLx2t7D39Q5w#.mp4'
      },	  
	  {
        'title': 'Dune 2021',
		'desc': '🎬Paul Atreides, un tânăr strălucit și talentat născut cu un mare destin, dincolo de capacitatea lui de înțelegere, trebuie să călătorească pe cea mai periculoasă planetă din univers pentru a asigura viitorul familiei și poporului său. Pe măsură ce forțe malefice intră în conflict pentru monopolul asupra celei mai de preț resurse a planetei - o marfă capabilă să descătușeze cel mai mare potențial al umanității, doar cei care își pot învinge frica vor supraviețui.🎬',
        'thumb': 'https://spaceandsorcery.wordpress.com/wp-content/uploads/2021/10/dune-2021.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDCeEmyUeq2-ERJW7v38OL_Y#.mp4'
      },
	  {
        'title': 'Children.Of.Dune.2003',
		'desc': '🎬Gemenii lui Paul Muad dib Atreides se implică în peisajul politic al Arrakisului Dune și al restului universului.🎬',
        'thumb': 'https://images.plex.tv/photo?size=large-1280&url=https%3A%2F%2Fimage.tmdb.org%2Ft%2Fp%2Foriginal%2F6BCFDHWotlOoPQJ7jGjUWyiITtk.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDIl0B4xLQvloMoYpE1w4tW0#.mp4'
      },
		  {
        'title': 'Dune.Part.Two.2024',
		'desc': '🎬Dune: Partea II explorează călătoria mitică a lui Paul Atreides în timp ce se asociază cu Chani și Fremen pentru a pune la cale răzbunarea împotriva conspiratorilor care i-au distrus familia. În fața alegerii între dragostea vieții sale și soarta universului, el se străduiește să prevină un viitor teribil ce doar el îl poate vedea🎬',
        'thumb': 'https://spoilertown.com/wp-content/uploads/2024/06/dune-part-two-2024.webp',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDD_q_u_KigFl1mGlzEXJcwY#.mp4'
      },  
	  {
        'title': 'Alpha (2018)',
		'desc': '🎬Alfa urmărește o poveste epică despre supraviețuire de acum 20.000 de ani, în timpul ultimei ere glaciare. În timpul primei sale vânători, considerată o inițiere a celui mai de elită grup al tribului său, tânărul Keda este rănit și considerat mort după ce o vânătoare de bizoni sfârșește groaznic. Trezindu-se rănit, singur și departe de satul său, el trebuie să învețe să supraviețuiască și să navigheze prin sălbăticia aspră și neiertătoare. În timp ce dezvoltă o prietenie cu un lup, ei învață să se bazeze unul pe altul pentru a vâna, a face față nenumăratelor pericole și pentru a-și găsi drumul spre casă înainte ca iarna neiertătoare să sosească.🎬',
        'thumb': 'https://m.media-amazon.com/images/S/pv-target-images/f850a0423752f38f6af71a4472b44967a9fe286c274eb38ad799f5b777aceb7a.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDE_RYGc5hx48dAJGhITPGaw#.mp4'
      },
	  {
        'title': 'Havoc Dezastru 2025',
		'desc': '🎬După ce un jaf de narcotice ia o turnură letală, un polițist blazat luptă cu criminalii orașului său corupt pentru a-l salva pe fiul unui politician.🎬',
        'thumb': 'https://www.joblo.com/wp-content/uploads/2025/04/en_us_havoc_main_ensemble_vertical_27x40_rgb_pre_1-copy.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDMxR8v7mNaB3T2-m1D6ycWg#.mp4'
      },	  
	  {
        'title': 'Guns.Up.2025',
		'desc': '🎬Ultima misiune a lui Ray Hayes, un fost acolit al mafiei, scapă de sub control chiar când era pe punctul de a părăsi „Familia”. Cu cronometrul deja pornit, Ray are la dispoziție o noapte pentru a-și scoate familia nevinovată din oraș înainte de a fi lichidat.🎬',
        'thumb': 'https://image.tmdb.org/t/p/w300/2IXLVSVOGCzE9zVQhxt8Htb0A0p.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDC9Jb50IUWCJWIXLsWjnChI#.mp4'
      },	  
	  {
        'title': 'Hitman.Agent.47.2015',
		'desc': '🎬Un asasin face echipă cu o femeie pentru a o ajuta să-și găsească tatăl și să descopere misterele strămoșilor ei🎬',
        'thumb': 'https://img1.hotstarext.com/image/upload/f_auto/sources/r1/cms/prod/old_images/MOVIE/1602/1770001602/1770001602-h',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDNR2VO7CMd47v9AhPJUn0HM#.mp4'
      },
	  {
        'title': 'Season of the Witch (2011)',
		'desc': '🎬Curajosul cavaler Lavey (Nicolas Cage) devine unica speranță de supraviețuire a omenirii, în bătălia înfricoșătoare cu forțele întunecate ale răului. În mijlocul celei mai mari epidemii de ciumă care a lovit Europa, Lavey își asumă o misiune temută de toți ceilalți: să o transporte la proces pe vrăjitoarea suspectată că ar fi provocat cumplita boală. Fiind convins că tânăra nu este responsabilă pentru molimă, Lavey urmat de războinicii săi, începe lupta cu forțele mistice și înșelătoare pentru a ridica blestemul aruncat asupra Europei.🎬',
        'thumb': 'https://images2.9c9media.com/image_asset/2025_7_12_28586661-8b42-478b-9f10-8f3dbbcd451a_jpg_2000x1125.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDHpXZaST3TlXt_6I9VS4asM#.mp4'
      },
	  {
        'title': 'Infinite.2021',
		'desc': '🎬Evan e bântuit de abilități pe care nu le-a învățat niciodată și amintiri din locuri pe care nu le-a vizitat vreodată. Apropiindu-se de o cădere nervoasă, membrii unui grup secret vin să-l salveze, dezvăluind că amintirile lui sunt reale.🎬',
        'thumb': 'https://www.acmodasi.in/amdb/images/movie/a/u/infinite-2021-25907.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDJv1Ni45q2TD5KCpUdjl0hA#.mp4'
      },	  
	  {
        'title': 'Wanted.2008',
		'desc': '🎬Un funcționar frustrat descoperă că este fiul unui asasin profesionist și că împărtășește abilitățile supraomenești de a ucide ca tatăl său.🎬',
        'thumb': 'https://m.media-amazon.com/images/S/pv-target-images/feee453e8ae8e6bae03f0a69d208a5ae05d65f8568e0e035d6fd5f1e333c2455.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDBkGupPGWDQHssifVyMX9j0#.mp4'
      },
	  {
        'title': 'Salt: Director’s Cut (2010)',
		'desc': '🎬Acuzată că este spioană rusă, agenta CIA Evelyn Salt fuge, folosindu-se de toate trucurile pe care le știe pentru a scăpa de urmăritori și a-și reface reputația.🎬',
        'thumb': 'https://cinemusefilms.com/wp-content/uploads/2016/04/63-salt.jpg?w=640',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDFGp6xjmScsYw4Bn8XFWnWo#.mp4'
      },
	  {
        'title': 'Mad.Max.Fury.Road.2015',
		'desc': '🎬Urmărit de un trecut turbulent, Mad Max prefera să călătorească de unul singur și să nu își facă prieteni. În ciuda convingerilor sale, se alătură unui grup de supraviețuitori ai deșertului, conduși de implacabila luptătoare Imperator Furiosa. Aceștia sunt urmăriți permanent și atacați de tiranul Immortan Joe care îi suspectează că i-au furat cea mai de preț posesie.🎬',
        'thumb': 'https://streamcoimg-a.akamaihd.net/000/958/725/958725-Banner-L2-847d2beb1082f33dab482bdae9b5b268.jpeg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDGyTPjEB84EZianvK6TOu_4#.mp4'
      },	  
	  {
        'title': 'The.Transporter.Refueled.2015',
		'desc': '🎬În sudul Franței, fostul mercenar din operațiuni speciale Frank Martin intră într-un joc de șah cu o femeie fatală și cei trei acomodați ai ei, care caută răzbunare împotriva unui sinistru baron rus.🎬',
        'thumb': 'https://images.plus.rtl.de/watch/705628/artwork_landscape/ut-fs-qe-kf/transporter-refueled-the',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDAgJSCB6-oZXMNHYF2Hfle4#.mp4'
      },
		  {
        'title': '20,000 Leagues Under the Sea',
		'desc': '🎬Un film bazat pe romanul lui Jules Verne. Trăiți aventurile fantastice ale căpitanului Nemo, un geniu care se luptă de la bordul submarinului său nuclear cu o țară agresoare.🎬',
        'thumb': 'https://i.ytimg.com/vi/K4OdftI7gVo/hq720.jpg?sqp=-oaymwEhCK4FEIIDSFryq4qpAxMIARUAAAAAGAElAADIQj0AgKJD&rs=AOn4CLALiODpIXytHuxRInmGvm8VoDZG_w',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDNDaKDZJ7BDskonMuz4CSDQ#.mp4'
      },  
	  {
        'title': 'Echo.Valley.2025',
		'desc': '🎬Kate se confruntă cu o tragedie personală în timp ce deține și dresează cai în Echo Valley, un loc izolat și pitoresc, când fiica ei, Claire, ajunge la ușa ei, înspăimântată, tremurând și acoperită de sângele altcuiva.🎬',
        'thumb': 'https://film-book.com/wp-content/uploads/2025/08/echo-valley-movie-poster-banner-01-700x400-1.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDP_fBnLUwhVP5ZbxloUlNXI#.mp4'
      },	  
	  {
        'title': 'Desert.Dawn.2025',
		'desc': '🎬Un șerif nou ales și adjunctul său reticent, care investighează uciderea unei femei, dezleagă o rețea mortală de minciuni, corupție și legături cu carteluri, care transformă orășelul lor liniștit într-o zonă de război.🎬',
        'thumb': 'https://m.media-amazon.com/images/S/pv-target-images/2c54fb89d40d1e7ae21aaed82e78476c3a36025036004ec28dfb9204a4eeaaf4.png',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDFL_UUDM4OjaPIwHUWSu01s#.mp4'
      },	  
	  {
        'title': 'Night.Carnage.2025',
		'desc': '🎬Un blogger care este și vârcolac întâlnește un playboy elegant, cu un secret întunecat al său. Cu Logan Andrews și Christian Howard în rolurile principale.🎬',
        'thumb': 'https://cineamo-tmdb.b-cdn.net/t/p/w780/iZztGzckOMByRRQgsFh2yk3udkU.jpg?width=640',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDE8T5TPLD_Qk0MMfd-ZPcWA#.mp4'
      },
	  {
        'title': 'Kraken 2025',
		'desc': '🎬Când un submarin rusesc dispare în Marea Groenlandei, comandantul Viktor Voronin conduce o misiune de salvare pentru a-și găsi fratele. Între timp, un monstru Kraken apare după distrugerea unei stații polare.🎬',
        'thumb': 'https://www.pearlpix.net/upload/images/xWYGs7o0lExX7XzdwyCFLZJ5C1L.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDPk707pfY4PawdcevLt7TGE#.mp4'
      },
	  {
        'title': 'Jurassic.World.Rebirth.2025',
		'desc': '🎬La cinci ani după Jurassic World: Dominion (2022), o expediție străbate regiuni ecuatoriale izolate pentru a extrage ADN de la trei creaturi preistorice masive, realizând o descoperire medicală revoluționară.🎬',
        'thumb': 'https://m.media-amazon.com/images/S/pv-target-images/6243fe1bd5fcc548ae60335babc1f67750668ef31840834056d087058e12ddea.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDJBH4ON5QVFUexbrYHbRhfM#.mp4'
      },
	  {
        'title': 'Elektra (2005)',
		'desc': '🎬Schimbarea de opinie a unei asasine o conduce într-un război împotriva unui sindicat al crimei malefice.🎬',
        'thumb': 'https://www.framerated.co.uk/frwpcontent/uploads/2025/01/elektra01-978x652.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDN78jt1hdTVOvkfMqhf2HlI#.mp4'
       },
  	  {
        'title': 'Karate.Kid.Legends.2025',
		'desc': '🎬După ce Li Fong, tânărul talentat kung fu, se mută în New York City, atrage atenția nedorită a unui campion local de karate și pornește într-o călătorie pentru a intra în competiția supremă de karate cu ajutorul domnului Han și al lui Daniel LaRusso.🎬',
        'thumb': 'https://www.framerated.co.uk/frwpcontent/uploads/2025/06/karatekidlegends01.jpg',
        'url': 'https://ia601707.us.archive.org/19/items/karate.-kid.-legends.-2025_202512/Karate.Kid.Legends.2025.mp4'
      },
	  {
        'title': 'Cronicile din Narnia: Călătoria pe mare cu Zori de Zi',
		'desc': '🎬La întoarcerea în Narnia pentru a i se alătura Prințului Caspian într-o călătorie pe maiestuoasa navă regală cunoscută sub numele de „The Dawn Treader”, Lucy, Edmund și vărul lor, Eustace, se întâlnesc cu merfolk, dragoni, pitici și o bandă rătăcitoare de războinici pierduți. Pe măsură ce marginea lumii se apropie, aventura lor remarcabilă pe mare navighează către o concluzie captivantă, dar plină de incertitudine.🎬',
        'thumb': 'https://disney.images.edge.bamgrid.com/ripcut-delivery/v2/variant/disney/3a38a269-6e71-4779-8dd2-9415501e103b/compose?aspectRatio=1.78&format=webp&width=1200',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDKdNS16xdAp-8Qy4uLOW2Pw#.mp4'
      },
  	  {
        'title': 'The.Divine.Fury',
		'desc': '🎬Un luptător campion mondial de MMA descoperă brusc stigmate pe palme. Vizita sa la o biserică duce la un exorcism neașteptat cu un preot. Împreună, se confruntă cu o confruntare finală cu Jisin, un agent sinistru al răului.🎬',
        'thumb': 'https://vhx.imgix.net/hi-yahtv/assets/8bbc4f25-7957-44b9-b7e1-36623484a2f1-bba5d876.jpg?auto=format%2Ccompress&fit=crop&h=720&q=75&w=1280',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDMVcBXg8QZFON_RDmVCS0vQ#.mp4'
      },	  
	  {
        'title': '47. Ronin. 2013',
		'desc': '🎬O bandă de samurai pornește să răzbune moartea și dezonoarea stăpânului lor din mâna unui shogun nemilos.🎬',
        'thumb': 'https://i.ytimg.com/vi/H9HUALYxz0k/maxresdefault.jpg',
        'url': 'https://ia801708.us.archive.org/33/items/47.-ronin.-2013_202512/47.Ronin.2013.mp4'
      },	  
	  {
        'title': 'The. Woman. King. 2022',
		'desc': '🎬O epopee istorică inspirată din evenimente reale care au avut loc în Regatul Dahomey, unul dintre cele mai puternice state ale Africii în secolele al XVIII-lea și al XIX-lea.🎬',
        'thumb': 'https://i.ytimg.com/vi/jSVT7VvWF9Q/maxresdefault.jpg',
        'url': 'https://ia601702.us.archive.org/25/items/the.-woman.-king.-2022_202512/The.Woman.King.2022.mp4'
      },
  	  {
        'title': 'The Hunt For Gollum 2009',
		'desc': '🎬Sauron se pregătește să-și dezlănțuie armatele, iar Gollum se strecoară prin Pământul de Mijloc cu cunoștințe cruciale despre locația Inelului. Trebuie găsit🎬',
        'thumb': 'https://i.ytimg.com/vi/5gL9Ctwmc_g/hq720.jpg?sqp=-oaymwEhCK4FEIIDSFryq4qpAxMIARUAAAAAGAElAADIQj0AgKJD&rs=AOn4CLBSUo0e6cyiOwQS3W0Ltf2J5v6xag',
        'url': 'https://ia801700.us.archive.org/7/items/the-hunt-for-gollum-2009/The_Hunt_For_Gollum_2009.mp4'
      },
	  {
        'title': 'Last Knights 2015',
		'desc': '🎬Un războinic căzut se ridică împotriva unui conducător corupt și sadic pentru a-și răzbuna stăpânul dezonorat.🎬',
        'thumb': 'https://m.media-amazon.com/images/M/MV5BMmRkN2Y4MzMtNmNhMi00MzJlLTk3ODQtYzZkMjE0MTFkYTdhXkEyXkFqcGc@._V1_.jpg',
        'url': 'https://ia601704.us.archive.org/19/items/last-knights-2015/Last%20Knights%20%282015%29.mp4'
      },
	  {
        'title': 'Mulan  Rise of a Warrior 2009',
		'desc': '🎬Povestea epică a războinicei chineze Mulan, care luptă pentru a-și apăra tatăl.🎬',
        'thumb': 'https://i.ytimg.com/vi/_nbAo9-k6W0/maxresdefault.jpg',
        'url': 'https://ia902807.us.archive.org/0/items/mulan-rise-of-a-warrior-2009_202512/Mulan%20%20Rise%20of%20a%20Warrior%20%282009%29.mp4'
      },
	  {
        'title': 'Morbius.2022',
		'desc': '🎬Biochimistul Michael Morbius încearcă să se vindece de o boală rară a sângelui, dar, fără să vrea, se infectează cu o formă de vampirism.🎬',
        'thumb': 'https://i0.wp.com/manapop.com/wp-content/uploads/2022/06/morbious-2022.jpg?ssl=1',
        'url': 'https://ia601006.us.archive.org/25/items/morbius.-2022_202512/Morbius.2022.mp4'
      },
	  {
        'title': 'Blade. Runner. 2049.2017',
		'desc': '🎬🎬',
        'thumb': 'https://files2.app.ertflix.gr/files/movies/blade-runner-2049/br2049-ertflix-img.jpg?m=resize&w=1200&h=628',
        'url': 'https://ia800308.us.archive.org/27/items/blade.-runner.-2049.2017/Blade.Runner.2049.2017.mp4'
      },
	  {
        'title': 'Awareness. 2023',
		'desc': '🎬🎬',
        'thumb': 'https://image.tmdb.org/t/p/original//13oj9ix9x4IGT0W9nQbzF5bPZU4.jpg',
        'url': 'https://ia801708.us.archive.org/32/items/awareness.-2023/Awareness.2023.mp4'
      },
	  {
        'title': 'Tides.2021',
		'desc': '🎬🎬',
        'thumb': 'https://4001reviews.de/wp-content/uploads/2021/09/Titelbild-Kritik-Tides-2021.jpg',
        'url': 'https://ia801708.us.archive.org/2/items/tides.-2021/Tides.2021.mp4'
      },
	  {
        'title': 'Demon pe două roți: Demonul răzbunării',
		'desc': '🎬Johnny Blaze (Nicolas Cage) se luptă cu blestemul care l-a transformat în diabolicul vînător de recompense, dar riscă totul cînd face echipă cu liderul unui grup de călugări rebeli (Idris Elba), pentru a salva un băiat de amenințarea diavolului și, poate, pentru a scăpa el însuși pentru totdeauna de acel blestem.🎬',
        'thumb': 'https://media.themoviedb.org/t/p/w780/z7qtrSn5iZrwKFE1sYPr597HweG.jpg',
        'url': 'http://dscmovisefree.ddns.net:80/play/t5gapbA-_eLACTBuV2KIDIbh6FJ1kmy3ETvTMUHwSWs#.mp4'
      },
	  {
        'title': 'Pacific Rim 2- Revolta',
		'desc': '🎬Jake Pentecost, fiul lui Stacker Pentecost, se reunește cu Mako Mori pentru a conduce o nouă generație de piloți Jaeger, inclusiv rivalul Lambert și hackerul Amara, în vârstă de 15 ani, împotriva unei noi amenințări Kaiju.🎬',
        'thumb': 'https://m.media-amazon.com/images/S/pv-target-images/3b5079770ae7fffe26b4a87d0c5ee3dd406850026b97e3ff3eaa174fcf283430.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219092.mp4'
      },
	  {
        'title': 'Shang Chi And The Legend Of The Ten Rings 2021',
		'desc': '🎬Shang-Chi, maestrul Kung Fu bazat pe arme, este forțat să-și înfrunte trecutul după ce a fost atras în organizația Zece Inele.🎬',
        'thumb': 'https://www.oldtrenchy.com/wp-content/uploads/2021/09/Shang-Chi-banner1.jpg',
        'url': 'https://ia601703.us.archive.org/6/items/shang-chi-and-the-legend-of-the-ten-rings-2021_202512/Shang_Chi_And_The_Legend_Of_The_Ten_Rings_2021.mp4'
      },	  
	  {
        'title': 'Maze Runner- The Death Cure',
		'desc': '🎬Tânărul erou Thomas pornește într-o misiune de a găsi un leac pentru o boală mortală cunoscută sub numele de „Flamul”.🎬',
        'thumb': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT5dbtMb6fTq1V68vfAFs0LOvc_9Bu78MExHg&s',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219115.mp4'
      },
	  {
        'title': 'Warcraft',
		'desc': '🎬În timp ce o hoardă de orci invadează planeta Azeroth folosind un portal magic, câțiva eroi umani și orci disidenți trebuie să încerce să oprească adevăratul rău din spatele acestui război.🎬',
        'thumb': 'https://resizing.flixster.com/t7xyo7a4Ds06C-NcNwtpowyO7ic=/fit-in/352x330/v2/https://resizing.flixster.com/-XZAfHZM39UwaGJIFWKAE8fS0ak=/v3/t/assets/p11882721_v_v8_ac.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219287.mp4'
      },
	  {
        'title': 'Condamnat Sa Ucida',
		'desc': '🎬Unui agent CIA pe moarte, care încearcă să se reconecteze cu fiica sa înstrăinată, i se oferă un medicament experimental care i-ar putea salva viața în schimbul unei ultime misiuni.🎬',
        'thumb': 'https://prorom.com//storage/images/movies/image_ro_a9bd226ee9fbc5b0e7e87db488326c2511480.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219459.mp4'
      },
	  {
        'title': 'Cod Rosu De Jaf',
		'desc': '🎬Suntem în anul 1992. O nefericită întorsătură a destinului face ca Bruce Ruthledge, vânător profesionist de uragane să-și piardă viața, lăsându-și cei doi fii, Will și Breeze, în voia sorții.🎬',
        'thumb': 'https://m.media-amazon.com/images/S/pv-target-images/f5e87e25ac136ac05ab1aa75c73a5c66182003baf71125175d21ae740dbbbba4.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219460.mp4'
      },
	  {
        'title': 'Frumoasa Si Bestia',
		'desc': '🎬O tânără femeie curajoasă, frumoasă și strălucită este închisă de o bestie în castelul său. În ciuda temerilor sale, ea învață să vadă dincolo de exteriorul hidos al bestiei și să realizeze inima blândă a adevăratului prinț din ea.🎬',
        'thumb': 'https://roatamare.com/wp-content/uploads/2017/05/frumoasa-si-bestia-afis.jpeg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219591.mp4'
      },
	  {
        'title': 'Escape Room',
		'desc': '🎬Șase străini se trezesc într-un labirint de camere misterioase și mortale și trebuie să-și folosească ingeniozitatea pentru a supraviețui.🎬',
        'thumb': 'https://m.media-amazon.com/images/I/91CVLmjQVJL._AC_UF1000,1000_QL80_.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219903.mp4'
      },
	  {
        'title': 'Baahubali 2 The Conclusion',
		'desc': '🎬Amarendra Baahubali, moștenitorul tronului lui Mahishmati, își găsește viața și relațiile în pericol, deoarece fratele său adoptiv, Bhallaladeva, conspiră pentru a revendica tronul.🎬',
        'thumb': 'https://static.toiimg.com/thumb/msid-60177580,width-1280,height-720,resizemode-4/60177580.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219764.mp4'
      },
	  {
        'title': 'Baahubali The Beginning',
		'desc': '🎬Un copil din regatul Mahishmati este crescut de membri ai tribului și, într-o zi, află despre moștenirea sa regală, despre curajul tatălui său în luptă și despre misiunea de a-l răsturna pe actualul conducător.🎬',
        'thumb': 'https://resizing.flixster.com/tY5T9kNktc40s4adUjq21LnjNtQ=/620x336/v2/https://resizing.flixster.com/-XZAfHZM39UwaGJIFWKAE8fS0ak=/v3/t/assets/p11546593_i_h10_ab.jpg',
        'url': 'http://luctv.net:8080/movie/costi1/costi1/64101.mkv'
      },	  
	  {
        'title': 'Prince Of Persia- The Sands Of Time',
		'desc': '🎬Un tânăr prinț și o prințesă fugari trebuie să oprească un ticălos care amenință, fără să știe, să distrugă lumea cu un pumnal special ce permite nisipului magic din interior să dea timpul înapoi.🎬',
        'thumb': 'https://www.citynetmagazine.com/wp-content/uploads/2010/06/prince-persia-ntn-1000x600.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219685.mp4'
      },
	  {
        'title': 'Wonder Woman',
		'desc': '🎬Când un pilot se prăbușește și povestește despre un conflict din lumea exterioară, Diana, o războinică amazoniană aflată în antrenament, părăsește casa pentru a lupta într-un război, descoperindu-și puterile depline și adevăratul destin.🎬',
        'thumb': 'https://spoilertown.com/wp-content/uploads/2025/06/wonder-woman-2017.webp',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219616.mp4'
      },
	  {
        'title': 'Animale Fantastice Si Unde Le Poti Gasi',
		'desc': '🎬În 1926, Newt Scamander sosește la New York cu barca, având o valiză misterioasă în care se află zeci de creaturi magice. După ce iese din port se întâlnește cu Mary Lou Barebone, care este membră a celui de-al Doilea Salem. Ea predică despre existența ființelor magice și despre modul în care acestea ar trebui vânate și doborâte.🎬',
        'thumb': 'https://beam-images.warnermediacdn.com/BEAM_LWM_DELIVERABLES/d627b35d-31a0-4e62-af14-6ec2fd8fdaef/76e1fb5d-b367-11f0-a9ca-02374aab4f9f?host=wbd-images.prod-vod.h264.io&partner=beamcom&w=500',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219610.mp4'
      },
	  {
        'title': 'Jaws - Falci',
		'desc': '🎬Când un rechin ucigaș uriaș dezlănțuie haosul asupra unei comunități de plajă din largul insulei Long Island, depinde de șeful poliției locale, un biolog marin și un navigator în vârstă să vâneze bestia.🎬',
        'thumb': 'https://images.justwatch.com/poster/110337976/s718/falci.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219583.mp4'
      },
	  {
        'title': 'Jaws 2 - Falci 2',
		'desc': '🎬Șeful poliției Brody trebuie să protejeze cetățenii din Amity după ce un al doilea rechin monstruos începe să terorizeze apele.🎬',
        'thumb': 'https://images.justwatch.com/poster/33788700/s718/falci-2.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219582.mp4'
      },
	  {
        'title': 'King Kong',
		'desc': '🎬Un producător de film lacom adună o echipă de cineaști și pornește spre infama Insulă a Craniilor, unde găsesc mai mult decât niște băștinași canibali.🎬',
        'thumb': 'https://i.guim.co.uk/img/static/sys-images/Film/Pix/pictures/2008/08/05/kingkong460.jpg?width=465&dpr=1&s=none&crop=none',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219577.mp4'
      },
	  {
        'title': 'Resident Evil- Capitolul Final',
		'desc': '🎬Alice se întoarce acolo unde a început coșmarul: Stupul din Raccoon City, unde Corporația Umbrella își adună forțele pentru un atac final împotriva singurilor supraviețuitori rămași ai apocalipsei.🎬',
        'thumb': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSATJVNZowBXYww8qBTvtmdwc3XmrVoc9wGEw&s',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219558.mp4'
      },
	  {
        'title': 'Terminator Genisys',
		'desc': '🎬Când John Connor, liderul rezistenței umane, îl trimite pe sergentul Kyle Reese înapoi în 1984 pentru a o proteja pe Sarah Connor și a proteja viitorul, o întorsătură neașteptată a evenimentelor creează o cronologie fracturată.🎬',
        'thumb': 'https://ntvb.tmsimg.com/assets/p10854590_v_h8_ai.jpg?w=1280&h=720',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219552.mp4'
      },
	  {
        'title': 'Equilibrium',
		'desc': '🎬Într-un viitor opresiv în care toate formele de sentimente sunt ilegale, un bărbat însărcinat cu aplicarea legii se ridică pentru a răsturna sistemul și statul.🎬',
        'thumb': 'https://m.media-amazon.com/images/I/81QrOj7axBS._AC_UF894,1000_QL80_.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219437.mp4'
      },
	  {
        'title': 'Furia Titanilor',
		'desc': '🎬Perseu înfruntă lumea subterană trădătoare pentru a-și salva tatăl, Zeus, capturat de fiul său, Ares, și de fratele său Hades, care dezlănțuie anticii Titani asupra lumii.🎬',
        'thumb': 'https://www.economica.net/wp-content/uploads/2012/04/wrath_titans_furia_titanilor_45077400.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219429.mp4'
      },
	  {
        'title': 'Gardienii Mormantului',
		'desc': '🎬În zilele noastre, Luke și Ethan cercetează mitul împăratului și al vieții veșnice în China îndepărtată pentru omul de afaceri Mason. Ei descoperă o peșteră și își încep cercetările, dar sunt apoi aparent atacați de un grup de păianjeni. Un Luke incapabil reușește să-i dea un apel de urgență lui Mason înainte de a ceda, aparent, rănilor sale.🎬',
        'thumb': 'https://www.nationaltv.ro/data_files/filme/large_poster_1715.jpg?cache=1753098284',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219426.mp4'
      },
	  {
        'title': 'Legenda Lui Hercule',
		'desc': '🎬Tânărul Hercule este fiul unei regine din Grecia antică și a lui Zeus, produsul unui pact realizat din dorința de a îndepărta de la domnie un rege despot și de a aduce pacea în regat. Fără să-și cunoască originile, curajosul prinț se lasă condus doar de dorința de a obține iubirea lui Hebe, prințesa Cretei, logodită cu propriul lui frate. Când află care este adevărata sa menire, legendarul personaj trebuie să aleagă între a deveni eroul unei națiuni sau a fugi cu femeia iubită.🎬',
        'thumb': 'https://media.themoviedb.org/t/p/w780/1OlinE4r38dgYbGSvkTVgY6iNDk.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219129.mp4'
      },
	  {
        'title': 'Razbunatorii- Razboiul Infinitului',
		'desc': '🎬Răzbunătorii și aliații lor trebuie să fie dispuși să sacrifice totul în încercarea de a-l învinge pe puternicul Thanos înainte ca atacul său devastator și ruină să pună capăt universului.🎬',
        'thumb': 'https://disney.images.edge.bamgrid.com/ripcut-delivery/v2/variant/disney/e5eaa6f1-2870-4651-bc96-b378c4f8b32b/compose?aspectRatio=1.78&format=webp&width=1200',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219077.mp4'
      },
	  {
        'title': 'Robin Hood- The Rebellion',
		'desc': '🎬Cu adevărata sa iubire capturată de ticălosul șerif din Nottingham, legendarul Robin Hood și echipa sa de haiduci execută o salvare îndrăzneață pentru a o salva.🎬',
        'thumb': 'https://i.ytimg.com/vi/tPTVmWrYLZg/maxresdefault.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219067.mp4'
      },
	  {
        'title': 'Singur Acasa 2 - Pierdut In New York',
		'desc': '🎬Kevin este din nou separat de familia sa când se îmbarcă accidental într-un zbor spre New York în timpul unei călătorii de Crăciun la Miami. Cu toate acestea, se întâlnește cu aceiași spărgători, care acum plănuiesc să jefuiască un magazin de jucării în Ajunul Crăciunului.🎬',
        'thumb': 'https://staticeu.sweet.tv/images/cache/v3/movie_poster/COzAARICcm8YAQ==/24684-singur-acasa-2-pierdut-in-new-york.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219057.mp4'
      },
	  {
        'title': 'The Christmas Chronicles',
		'desc': '🎬Povestea surorii și fratelui Kate și Teddy Pierce, al căror plan de Ajunul Crăciunului de a-l surprinde pe Moș Crăciun se transformă într-o călătorie neașteptată la care majoritatea copiilor nu ar putea decât să viseze.🎬',
        'thumb': 'https://chicagofilmscene.com/wp-content/uploads/2020/11/The-Christmas-Chronicles-VI.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219040.mp4'
      },
	  {
        'title': 'The Princess Switch - Un Schimb Regal',
		'desc': '🎬O patisieră modestă din Chicago și o viitoare prințesă descoperă că seamănă ca două gemene și fac un plan de schimbare a rolurilor cu ocazia Crăciunului.🎬',
        'thumb': 'https://fthspatpress.com/wp-content/uploads/2020/12/the-princess-switch.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219022.mp4'
      },
	  {
        'title': 'The Vanishing',
		'desc': '🎬Trei paznici de far de pe îndepărtatele Insule Flannan obțin un cufăr misterios, ceea ce duce la dispariția lor misterioasă.🎬',
        'thumb': 'https://images.sr.roku.com/idType/roku/context/global/id/00b177c943dd53e69ca6c9227f787fa0/images/gracenote/assets/p16290582_v_v8_aa.jpg/magic/396x0/filters:quality(70)',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219925.mp4'
      },
	  {
        'title': 'Trading Paint',
		'desc': '🎬Veteranul pilot de curse Sam Munroe și fiul său, un alt pilot dintr-un oraș mic, depășesc conflicte familiale și profesionale, echilibrând competiția, egoul, resentimentele și un inamic al curselor pentru a ieși mai puternici.🎬',
        'thumb': 'https://m.media-amazon.com/images/S/pv-target-images/97b5d8d3e570927fd008d19bb62b87ee7737876cd5de8ca1a35dae8bebf45604.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219922.mp4'
      },
	  {
        'title': 'Widows',
		'desc': '🎬Patru femei care nu au nimic în comun în afară de o datorie lăsată în urmă de activitățile criminale ale soților lor decedați își iau soarta în propriile mâini și conspiră pentru a-și construi un viitor după propriile reguli.🎬',
        'thumb': 'https://resizing.flixster.com/EcWLCGnecKn-KgbpUEVGYPjoxNE=/fit-in/705x460/v2/https://resizing.flixster.com/-XZAfHZM39UwaGJIFWKAE8fS0ak=/v3/t/assets/p15495823_v_v12_ah.jpg',
        'url': 'http://c.proserver.in:8080/movie/rsvod/OKWfvUv6Ln/219912.mp4'
      },
    ]
    for film in dsc_films:
        add_playable_item(film['title'], film['url'], thumb=film.get('thumb'), plot=film.get('plot'))
    xbmcplugin.endOfDirectory(HANDLE)

def live_tv():
    channels = [
        {
            'title': 'Antena 1 HD',
            'url': 'https://hls.rundletv.eu.org/LIVE$Antena1/6.m3u8/Level/300720051?end=END&start=LIVE',
            'thumb': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTBwvC_deklG6LQ2udfjStRkUIi4MhYqIJrpQ&s',  # Logo oficial Antena 1
            'plot': 'Post TV generalist român – știri, divertisment, seriale și emisiuni.'
        },
	 	 {
        'title': 'CaTine Ro',
		'desc': 'Live TV Romania',
        'thumb': 'https://cdn.catine.ro/wp-content/uploads/2021/01/logo-catine.png',
        'url': 'https://stream1.antenaplay.ro/live/CaTine/playlist.m3u8'
      },		
	   	{
        'title': 'MEDICOOL TV HD',
		'desc': 'Live TV Romania',
        'thumb': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS6ndXoWBdxnes6qfbz8wE1D6-Jc0F5ywzqVg&s',
        'url': 'https://stream1.antenaplay.ro/live/MediCOOLTV/chunklist.m3u8?version=1&session=TAts9hGFh2hckPJmua8s&starttime=1731062008&endtime=1731076438&source=web&token=H-s760VdYY4kPvuE0V9F6nn_ldo='
      },
	   	{
        'title': 'Dotto TV',
		'desc': 'Live TV Romania',
        'thumb': 'https://static.wikia.nocookie.net/logopedia/images/0/07/Dotto_TV_HD_white.png/revision/latest/scale-to-width-down/250?cb=20241108195044',
        'url': 'https://live.dottotv.ro/index.m3u8'
      },
    ]
    for channel in channels:
        add_playable_item(channel['title'], channel['url'], thumb=channel.get('thumb'), plot=channel.get('plot'))
    xbmcplugin.endOfDirectory(HANDLE)

def list_content(content_type, page=1, query=None):
    if query:
        url = f"{BASE_URL}/search/{content_type}?api_key={API_KEY}&query={urllib.parse.quote(query)}&language=ro-RO&page={page}"
    else:
        endpoint = "/movie/popular" if content_type == "movie" else "/tv/popular"
        url = f"{BASE_URL}{endpoint}?api_key={API_KEY}&language=ro-RO&page={page}"

    data = get_json(url)
    for item in data.get('results', []):
        title = item.get('title') or item.get('name', 'Fără titlu')
        year = (item.get('release_date') or item.get('first_air_date') or '0000')[:4]
        poster = IMG_BASE + item['poster_path'] if item.get('poster_path') else ''
        
        add_directory(f"{title} ({year})", 
                     {'mode': 'details', 'tmdb_id': str(item['id']), 'type': content_type}, 
                     thumb=poster, plot=item.get('overview'))

    if data.get('page', 1) < data.get('total_pages', 1):
        add_directory("➡️ Pagina Următoare", 
                     {'mode': 'list', 'type': content_type, 'page': str(data['page'] + 1), 'query': query or ''})
    xbmcplugin.endOfDirectory(HANDLE)

def show_details(tmdb_id, content_type):
    url = f"{BASE_URL}/{content_type}/{tmdb_id}?api_key={API_KEY}&language=ro-RO"
    data = get_json(url)
    poster = IMG_BASE + data.get('poster_path', '') if data.get('poster_path') else ''
    
    if content_type == 'movie':
        title = data.get('title', 'Film')
        year = data.get('release_date', '0000')[:4]
        li = xbmcgui.ListItem(f"▶ Redă Filmul: {title} ({year})")
        li.setArt({'thumb': poster, 'poster': poster})
        li.setInfo('video', {'title': title, 'year': int(year) if year.isdigit() else None})
        li.setProperty('IsPlayable', 'true')
        params = {'mode': 'play', 'tmdb_id': tmdb_id, 'type': 'movie', 'title': title, 'year': year}
        url = f"{sys.argv[0]}?{urlencode(params)}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, False)
    else:
        for s in data.get('seasons', []):
            if s['season_number'] == 0:
                continue
            add_directory(f"Sezonul {s['season_number']} ({s.get('episode_count', 0)} ep)", 
                         {'mode': 'episodes', 'tmdb_id': tmdb_id, 'season': str(s['season_number']), 'tv_show_title': data.get('name')}, 
                         thumb=poster)
    xbmcplugin.endOfDirectory(HANDLE)

def list_episodes(tmdb_id, season_num, tv_show_title):
    url = f"{BASE_URL}/tv/{tmdb_id}/season/{season_num}?api_key={API_KEY}&language=ro-RO"
    data = get_json(url)
    for ep in data.get('episodes', []):
        ep_num = ep['episode_number']
        name = f"E{ep_num:02d} - {ep.get('name', 'Episod fără titlu')}"
        thumb = IMG_BASE + ep.get('still_path', '') if ep.get('still_path') else ''
        
        li = xbmcgui.ListItem(name)
        li.setArt({'thumb': thumb})
        li.setInfo('video', {
            'title': ep.get('name'),
            'tvshowtitle': tv_show_title,
            'season': int(season_num),
            'episode': ep_num,
            'mediatype': 'episode'
        })
        li.setProperty('IsPlayable', 'true')
        
        play_params = {
            'mode': 'play',
            'tmdb_id': tmdb_id,
            'type': 'tv',
            'season': season_num,
            'episode': str(ep_num),
            'title': ep.get('name'),
            'tv_show_title': tv_show_title
        }
        play_url = f"{sys.argv[0]}?{urlencode(play_params)}"
        xbmcplugin.addDirectoryItem(HANDLE, play_url, li, False)
    xbmcplugin.endOfDirectory(HANDLE)

def play_item(params):
    tmdb_id = params.get('tmdb_id')
    c_type = params.get('type')
    
    xbmcgui.Dialog().notification("Căutare stream", "Se caută surse disponibile...", xbmcgui.NOTIFICATION_INFO, 5000)
    
    ids = get_ids(c_type, tmdb_id)
    imdb_id = ids.get('imdb_id')
    
    if not imdb_id:
        xbmcgui.Dialog().ok("Eroare", "Nu s-a găsit ID IMDb pentru acest titlu.")
        return

    link = get_stream_link(imdb_id, c_type, params.get('season'), params.get('episode'))
    
    if link:
        play_li = xbmcgui.ListItem(params.get('title') or 'Redare')
        play_li.setPath(link)
        
        meta = {
            'imdbnumber': imdb_id,
            'title': params.get('title') or 'Titlu'
        }
        
        if c_type == 'movie':
            meta['mediatype'] = 'movie'
            if params.get('year') and params['year'].isdigit():
                meta['year'] = int(params['year'])
        else:
            meta.update({
                'mediatype': 'episode',
                'tvshowtitle': params.get('tv_show_title'),
                'season': int(params.get('season') or 1),
                'episode': int(params.get('episode') or 1)
            })
            
        play_li.setInfo('video', meta)
        play_li.setProperty('IsPlayable', 'true')
        
        xbmcplugin.setResolvedUrl(HANDLE, True, listitem=play_li)
    else:
        xbmcgui.Dialog().ok("Eroare", "Nu s-a găsit nicio sursă funcțională.\nÎncearcă mai târziu.")

def search():
    kb = xbmcgui.Keyboard('', 'Caută un film sau serial...')
    kb.doModal()
    if kb.isConfirmed() and kb.getText().strip():
        list_content('movie', 1, kb.getText().strip())

def router():
    params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
    mode = params.get('mode')
    
    if not mode:
        main_menu()
    elif mode == 'list':
        list_content(params.get('type'), int(params.get('page', 1)), params.get('query'))
    elif mode == 'details':
        show_details(params.get('tmdb_id'), params.get('type'))
    elif mode == 'episodes':
        list_episodes(params.get('tmdb_id'), params.get('season'), params.get('tv_show_title'))
    elif mode == 'play':
        play_item(params)
    elif mode == 'search':
        search()
    elif mode == 'classic_movies':
        classic_movies()
    elif mode == 'dsc_vod':
        dsc_vod()
    elif mode == 'live_tv':
        live_tv()

if __name__ == '__main__':
    router()