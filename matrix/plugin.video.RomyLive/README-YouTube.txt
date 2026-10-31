RomyLive 3.3.23+matrix - YouTube integrat cu Muzica pe genuri
=======================================

INSTALARE
1. Kodi -> Add-ons -> Instaleaza din fisier ZIP.
2. Selecteaza plugin.video.RomyLive-3.3.23+matrix-youtube-fara-autentificare.zip.
3. Versiunea actualizeaza RomyLive existent, cu acelasi ID. Nu sterge profilul.
4. Reporneste Kodi pentru a porni si serviciul local YouTube.
5. In meniul principal, YouTube apare imediat dupa MuzicaX.Net / Muzica.

Nu trebuie instalat plugin.video.youtube separat. Nu trebuie cont Google,
logare OAuth, cookie-uri de cont sau chei API personale pentru cautarea
publica si redarea prin motorul inclus.

ACCES ANONIM SI PREFERINTE COOKIE (3.3.23)
Cautarile si playlisturile folosesc o sesiune HTTP noua, fara cont Google,
fara import de cookie-uri din browser si fara Authorization/OAuth.
Se trimit numai preferintele anonime initiale SOCS=CAE si PREF (limba/fus)
pentru YouTube, in memoria sesiunii, nu cookie-uri de autentificare.
Nu se selecteaza Accept all (SOCS=CAI) si nu se trimite un formular de logare.
La redirectionare spre pagina regionala de consimtamant cookie, cererea
publica este repetata o singura data cu preferintele anonime initiale.
Eroarea de consimtamant este acum separata de refuzul accesului anonim;
addonul nu cere utilizatorului sa introduca un cont Google.
Acest lucru nu face accesibile playlisturile private sau restrictionate.

MENIU YOUTUBE
- Muzica: prima intrare; genuri si videoclipuri administrate prin fisiere TXT.
- Cauta videoclipuri: titluri, autori, miniaturi si paginare.
- Cauta muzica: cauta artistul sau melodia.
- Deschide link / ID: watch, youtu.be, shorts, live sau playlist public.
- Setari: redare adaptiva, selectarea calitatii, numai sunet, port HTTP.

AUTOPLAY (3.3.19)
Activ implicit. Selectarea unui videoclip creeaza o lista de redare Kodi
cu acel videoclip si urmatoarele din lista afisata, in ordinea lor.
Functioneaza in Manele/Romanesti/alte genuri, cautari si playlisturi publice.
La finalul listei se opreste; nu trece in alt gen si nu se repeta.
Pentru cautari/playlisturi paginate, autoplay acopera numai pagina curenta.
Un link video deschis individual nu are o lista de videoclipuri urmatoare.
Stop opreste lista. Redarea pornita inlocuieste lista video Kodi activa;
nu modifica setarea globala Kodi de redare automata.
Dezactivare: Setari -> YouTube (fara cont) -> Autoplay.
Listele TXT si default.py de pe server nu necesita modificari.

MUZICA PE GENURI
Incarca fisierul muzica.txt livrat separat la:
https://documentarys.do.am/2026/kodinou/muzica/muzica.txt
Acesta contine categorii <channel> cu <name> si <externallink> spre
manele.txt, romanesti.txt si orice alte genuri adaugi ulterior.
Fisierul este citit la fiecare deschidere; nu trebuie reinstalat addonul.
URL-ul indexului poate fi schimbat in Setari -> YouTube (fara cont).
Pana la incarcarea indexului implicit, addonul foloseste lista initiala
inclusa local (Manele si Romanesti). Erorile listelor de videoclipuri
sunt afisate, nu ascunse printr-un fallback.
Listele fiecarui gen contin blocuri <item> cu <title>, <link>,
<thumbnail>, <fanart>, <info>. Se accepta linkuri YouTube standard,
ID video in <utube> sau ruta integrata RomyLive /youtube/play/.
Nu sunt executate cod Python, comenzi Kodi sau alte addonuri din liste.
Toate fisierele TXT trebuie salvate UTF-8. Sunt acceptate si subcategorii.

PLAYLISTURI YOUTUBE IN LISTELE TXT (3.3.22)
Insereaza acest bloc in manele.txt, romanesti.txt sau alta lista Muzica:

<item>
    <title>Muzica romaneasca - playlist YouTube</title>
    <playlist>https://www.youtube.com/playlist?list=PLCb6RHtVpJNY-F234AaLSij08HsMQxf_C</playlist>
    <thumbnail>https://i.ytimg.com/vi/xaPoQvqjM9k/hqdefault.jpg</thumbnail>
    <info>Deschide toate paginile playlistului.</info>
</item>

Intrarea apare ca folder. Se citesc videoclipurile publice direct de pe
YouTube la deschidere, fara copiere manuala in TXT si fara cont Google.
Se accepta si link watch?v=...&amp;list=... sau numai ID-ul playlistului
in <playlist>. <thumbnail>, <fanart> si <info> sunt optionale.
Pentru <channel>, foloseste <name> in loc de <title>.
Nu combina <playlist> cu <externallink> in acelasi bloc.
Un <link> normal ramane videoclip individual, chiar daca are si list=.
Playlisturile lungi au Pagina urmatoare. Autoplay acopera pagina afisata;
nu incarca automat toate paginile intr-o singura lista de redare.
Playlisturile private sau restrictionate pot fi refuzate de YouTube.
default.py de pe server nu trebuie modificat.

CE S-A SCHIMBAT
- 3.3.23: preferinte cookie anonime la cautari/playlisturi si continuari,
  o singura reincercare pentru pagina cookie si mesaje distincte pentru
  consimtamant versus refuzul accesului anonim. Fara login si API keys.
- 3.3.22: suport <playlist> in <item>/<channel>, inclusiv linkul complet
  watch?v=...&list=... si ID simplu. Folder separat cu paginarea publica
  existenta; exclus din autoplay-ul videoclipurilor categoriei parinte.
- 3.3.21: corectat routerul intern la redirectionari si contexte clonate:
  /youtube/play/ este normalizat la /play/, nu mai este tratat ca folder.
  In 3.3.20, uri_action genera gresit /kodion/route/youtube/play/, ceea ce
  provoca "Mapping for path /youtube/play/ not found". Corectat si accesul
  la setarea audio_only din aceeasi ramura de redirectionare.
- 3.3.20: actiunea Autoplay anuleaza navigarea in folderul temporar
  inainte de a porni playlistul. Pagina sursa ramane deschisa, evitand
  reinvocarea rutei Autoplay la revenirea din fullscreen dupa Stop.
  Nu exista callback care sa reporneasca redarea la onPlayBackStopped.
  Comportamentul Stop trebuie confirmat in Kodi, nu doar prin teste simulate.
- 3.3.18: corectata conversia numelor UTF-8 bytes din meniul remote;
  TypeError in adaptor provoca notificarea generica de incarcare a datelor.
- 3.3.18: eliminat ANDROID_VR din clientii de redare; logul utilizatorului
  arata HTTP 403 la segmentele audio itag 140 si video, urmat de blocaj.
  Raman clientii publici Android/iOS; fara cont Google sau addon separat.
  Referinte: https://github.com/anxdpanic/plugin.video.youtube/issues/1481
  si https://github.com/anxdpanic/plugin.video.youtube/issues/1483
- Motorul YouTube 7.4.4+unofficial.1 din arhiva furnizata este inclus in
  resources/lib/romy_youtube_engine, nu apelat ca addon extern.
- Motorul foloseste aceeasi logica upstream pentru clienti publici ai
  playerului, semnaturi, selectarea fluxurilor si InputStream Adaptive.
- Cautarea si listele publice folosesc raspunsurile paginilor YouTube si
  endpointurile de continuare WEB; nu depind de YouTube Data API v3.
- Rutele motorului sunt izolate sub plugin://plugin.video.RomyLive/youtube/.
- Logo-ul este cel original din arhiva YouTube furnizata; iconul general
  RomyLive ramane neschimbat.
- Profilul YouTube este separat in addon_data/plugin.video.RomyLive/youtube.
- Portul local implicit este 50153, diferit de 50152 al addonului YouTube.
- Serviciul audio RomyLive existent ramane activ.
- Wizard-ul fortat de configurare upstream este dezactivat; integrarea nu
  expune optiuni de autentificare. Nu ocoleste restrictiile de varsta.
- Loaderul decodeaza static invelisul base64/zlib al sursei de pe server
  inainte de aplicarea corectiilor locale pentru meniu si DeseneFaine.
- A fost inclus un fallback al codului remote disponibil la momentul
  modificarii. YouTube nu asteapta descarcarea codului remote.

LIMITARI
Fara logare inseamna acces la continutul public permis de YouTube, nu
garantia redarii oricarui videoclip. Continutul privat, cu autentificare,
restrictii de varsta/regiune, CAPTCHA sau blocaj de IP poate fi refuzat.
Nu exista mecanisme pentru evitarea autentificarii ori restrictiilor DRM.
Modificarile viitoare YouTube pot necesita actualizarea motorului/parserului.
Modificarile majore ale structurii meniului remote RomyLive pot necesita
actualizarea adaptorului local; fallback-ul este folosit la eroare.

VERIFICARI EFECTUATE
- 33 teste automate cu API Kodi simulate: meniul si ordinea, logo, rutele,
  linkurile, JSON vechi/nou, paginarea, importurile motorului si setarile,
  integrarea loaderului, compilarea Python si structura XML.
- 3.3.23: cookie-uri initiale numai pe HTTPS YouTube, fara cookie-uri de cont,
  retry limitat pentru consent, eroare separata pentru accounts.google.com,
  continuari anonime. Live: playlist pagina 1/2 cate 100 videoclipuri;
  cautare publica 21 videoclipuri. Reteaua utilizatorului si Kodi efectiv
  nu sunt disponibile aici; corectia pe acea conexiune trebuie confirmata.
- Cercetare: https://stackoverflow.com/questions/74127649/
  si https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/youtube/_base.py
  documenteaza preferinta SOCS separat de cookie-urile de autentificare.
- Regresii 3.3.21: clone cu ruta publica, invocari succesive ale aceluiasi
  context, redirectionarea redarii versus listare si navigare provider.
  Comparatie cu sursele 3.3.20: ruta gresita reprodusa, apoi normalizata.
- 3.3.22: formate playlist, validare linkuri, folder, ruta publica,
  continuare paginare si excludere playlist din autoplay-ul parintelui.
  Playlistul PLCb6RHtVpJNY-F234AaLSij08HsMQxf_C verificat live fara cont:
  100 videoclipuri pe prima pagina si 100 pe pagina a doua, cu continuare.
- Verificari online: cautare publica si pagina a doua; playlist public
  si pagina a doua, fara cont sau chei API personale.
- 3.3.18: videoclipul 7Ho6htGh350 verificat live cu client ANDROID:
  cereri Range la 80% din fisierele video si audio: HTTP 206, 65536 bytes
  fiecare. Test de transport, nu redare completa pe dispozitivul utilizatorului.
- Redarea audio/video efectiva NU a fost verificata intr-o instalare Kodi;
  acest mediu de lucru nu are Kodi. Este necesar testul pe dispozitiv.

ATRIBUIRE SI LICENTA
Motorul inclus provine din plugin.video.youtube 7.4.4+unofficial.1.
Autori upstream: bromix, anxdpanic, MoojMidge si contributorii proiectului.
Sursa: https://github.com/anxdpanic/plugin.video.youtube
Motorul si adaptarile lui pastreaza licenta GPL-2.0-only; textul este inclus
in LICENSES/GPL-2.0-only. Antetele de copyright originale sunt pastrate.
Adaptoarele noi romy_youtube.py, romy_youtube_public.py,
romy_youtube_catalog.py, romy_youtube_autoplay.py si youtube_script.py
sunt furnizate sub GPL-2.0-only. Fisierele RomyLive preexistente provin din
arhiva utilizatorului; drepturile asupra lor raman ale autorilor originali.
Nu este un produs oficial Google/YouTube si nu este sustinut de Google.