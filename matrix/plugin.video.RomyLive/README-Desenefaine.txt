RomyLive+ 3.3.15 - VaVoo independent, API-ul paginii web

- Analizat in browser https://vavoo.to/#/channels si cererile reale ale
  aplicatiei. Site-ul actual foloseste GET /live/catalog/live/channels.json
  si GET /live/resolve?region=US&language=en&url=.../live/play/<IDnumeric>.
- Foloseste aceste endpoint-uri direct de pe aparatul Kodi, fara ThraxTV,
  api.derzis.xyz, semnatura Lokke, inregistrare sau token de aparat.
  Modulele Thrax au fost eliminate din noul ZIP. Un token vechi existent
  in userdata nu este citit/folosit si nu este sters (poate fi comun altor addonuri).
- Catalogul este inlocuit cu cel actual al site-ului: paginare cu nextCursor,
  ID numeric, tara din tags, deduplicare. Test live: 10129 canale / 17 tari.
  Numele/variantele sunt cele ale site-ului, ex. ACASA GOLD (7), nu .s.
- Favoritele vechi cu ID numeric + sufix hex de 12 caractere sunt convertite
  la ID-ul numeric. Conversia nu promite disponibilitatea sursei vechi.
- URL nou generat la fiecare redare. Fara URL-uri sunshine/tokenuri statice,
  fara proxy, fara preflight blocant. Player nativ, User-Agent browser si
  Referer site; antetele API explicite au prioritate. TLS verificat.
- Test initial ACASA GOLD: resolve HTTP200, playlist HTTP200, segment
  HTTP200 si MPEG-TS valid (1395524 octeti). La repetare, CDN ReadTimeout;
  6 TV a returnat playlist HTTP502. Disponibilitatea ramane intermitenta.
  Acestea sunt teste HTTP/media, NU redare verificata in Kodi Windows.
- 124 teste automate, inclusiv noul API, catalog, favorite si hook-ul activ.
  Audio romana/Latin, DaddyLive si Desenefaine pastrate neschimbate.
- Instaleaza peste addon si reporneste Kodi. Reintre in meniul VaVooTV
  pentru lista actuala. default.py remote nu trebuie modificat.

RomyLive+ 3.3.14 - VaVoo metoda ThraxTV

- Analizat plugin.video.thraxtv trimis de utilizator: vavoo_resolver.py,
  thrax_auth.py si ramura reala de redare VaVoo din default.py.
- Fluxul activ VaVoo ia semnatura de la api.derzis.xyz/livetv/vavoo/sig.
  Foloseste protocolul public de inregistrare anonima /auth/register,
  fara cheie inclusa in cod si fara numele aparatului. Tokenul se pastreaza
  in special://profile/addon_data/thrax.auth/token.json, ca in ThraxTV.
- Dependenta explicita: serviciul Thrax trebuie sa fie disponibil si sa
  accepte inregistrarea/tokenul. Semnatura nu mai vine din ping-ul local.
- Rezolvare LOCAL pe aparatul Kodi cu http.client, TLS verificat, fara
  Accept-Encoding explicit; acelasi body si URL /vavoo-iptv/play/<CID>.
  Nu este proxy video si nu obtine URL-ul video de pe serverul Thrax.
- Player NATIV: URL direct, fara User-Agent/Origin/Referer inventate,
  fara ISA, fara MIME fortat si fara preflight-ul blocant din 3.3.13.
  Antetele oferite explicit de API sunt pastrate daca exista.
- Nu reincarca intregul catalog la pornire: rezolva direct ID-ul selectat.
  Meniul, tarile, canalele, favoritele si logo-ul local sunt pastrate.
- Test live: inregistrare HTTP200, semnatura obtinuta, resolve local HTTP200.
  Verificarea CDN facuta separat DOAR in test a expirat (ReadTimeout).
  Redarea efectiva Kodi Windows NU este confirmata; nu garantam canalele.
- 124 teste automate; audio romana/Latin, DaddyLive si Desenefaine pastrate.
- Referinta ThraxTV declara GPL-2.0-only; adaptoarele au atribuire in cod.
  Instaleaza ZIP peste addon si reporneste Kodi. Remote default.py neschimbat.

RomyLive+ 3.3.13 - VaVoo verificare stream si reincercare

- Logul complet confirma HTTP 502 Bad Gateway de la serverul video,
  cu User-Agent, Referer si Origin ajunse in playerul nativ Kodi.
  Schimbarea playerului in 3.3.12 nu a rezolvat aceasta eroare upstream.
- Verifica HTTP si continutul HLS/MPEG-TS inainte de predarea la Kodi.
  La playlist master verifica si prima varianta media. Nu testeaza fiecare
  segment si nu garanteaza ca CDN-ul va ramane disponibil dupa verificare.
- La esec incearca celelalte URL-uri oferite de API pentru acelasi canal,
  apoi reautorizeaza si rezolva din nou. Nu schimba canalul selectat,
  nu inventeaza domenii si nu dezactiveaza verificarea TLS.
- Maximum doua runde de autorizare/rezolvare, buget 60 secunde pentru
  aceasta faza (nu include incarcarea catalogului), timeout-uri scurte si
  oprire la inchiderea Kodi. Erorile HTTP/tipurile exceptiilor apar in log
  si notificare, fara tokenuri sau URL-uri semnate.
- 107 teste automate trecute, inclusiv HTTP502 persistent, recuperare dupa
  HTTP502, timeout, HTML fals, playlist master si regresiile existente.
- Test live A7 TV .s: API a returnat URL, toate cele patru verificari CDN
  au expirat (ReadTimeout), inclusiv dupa reautorizare. Redarea NU este
  confirmata; aceasta versiune imbunatateste verificarea/reincercarea,
  nu poate repara un server VaVoo indisponibil.
- Audio romana/Latin, DaddyLive, Desenefaine, catalog si logo pastrate.
  Instaleaza peste versiunea existenta si reporneste Kodi. Nu dezinstala.
  default.py remote nu trebuie schimbat.

RomyLive+ 3.3.12 - VaVoo player nativ

- Log utilizator: rezolvarea returneaza URL, dar ISA esueaza OpenInputStream.
  Nu dovedeste cauza exacta HTTP. VaVoo este trecut pe playerul HLS nativ
  Kodi, fara fortarea InputStream Adaptive. DaddyLive ramane neschimbat.
- Adauga Referer https://vavoo.to/ si Origin https://vavoo.to daca API-ul
  nu le furnizeaza. Antetele explicite API au prioritate.
- Test live A7 TV .s (3111955796a4be6430e3aa): playlist HTTP200, segment
  HTTP200, octeti MPEG-TS verificati. A 7 TV .b a expirat la conectare.
- 95 teste automate trecute. Redarea efectiva in Kodi Windows nu a fost
  verificata aici; nu garanteaza toate canalele sau stabilitatea CDN.
- Instaleaza ZIP 3.3.12 si reporneste Kodi; testeaza intai A7 TV .s.
  default.py remote nu trebuie schimbat. Audio/logo/catalog pastrate.

RomyLive+ 3.3.11 - VaVoo sesiune si logo

- Sesiune HTTP comuna pentru autorizare si rezolvare, reautorizare la
  raspuns fara stream, antete API pastrate si HLS prin InputStream Adaptive.
- Nu forteaza MIME HLS pentru URL fara extensie HLS; esecul inchide corect
  callback-ul Kodi si este descris in log [RomyLive VaVoo].
- Sigla locala RomyLive in meniul VaVooTV in locul favicon-ului lipsa.
- 91 teste automate. API catalog/resolve a raspuns HTTP200 in mediu;
  streamul de proba a expirat la conectare. Redarea NU este confirmata,
  cauza exacta pe dispozitivul utilizatorului necesita kodi.log.
- Instaleaza ZIP si reporneste Kodi; default.py remote neschimbat.

RomyLive+ 3.3.10 - DaddyLive toate ID-urile

- Resolver DaddyLive nou, pe baza formatelor analizate din daddyCode din
  arhiva MandraKodi trimisa. Nu importa meniul sau lista italiana.
- Pastreaza lista existenta si toate ID-urile din Live TV / Canale sport /
  DaddyLive 24/7 Channels. Nu exista filtru de tara in resolver.
- Incearca stream, cast, watch, plus, casting, player, hub pe originile
  dlive.sx, dlhd.st, dlstreams.st, dlhd.pk. Urmareste iframe-uri relative.
- Suporta _econfig, atob, SRC si URL-uri m3u8 directe. Verifica playlistul
  si variantele media; respinge HTML/playlisturi PNG-HLS incompatibile.
- Sesiune HTTP comuna pentru rezolvare, antete Referer/Origin/User-Agent
  transmise catre InputStream Adaptive pentru manifest si segmente.
- Nu importa proxy-ul PNG extern Mandra (absent din arhiva trimisa).
  Daca un canal ofera exclusiv PNG-HLS, acesta ramane indisponibil.
- 86 teste automate trecute. Test live: ID 1, 45, 877 au rezolvat prin
  cast si au playlisturi HLS valide. Nu este test de redare Kodi Windows
  si nu garanteaza disponibilitatea fiecarui canal sau durata redarii.
- Audio romana/Latin, Desenefaine si paginarea sunt pastrate.
- Instaleaza ZIP 3.3.10 si reporneste Kodi. Remote default.py neschimbat.
- Diagnostic: cauta [RomyLive DaddyLive] in kodi.log.

RomyLive+ 3.3.9 - Rezerva audio Latin/Latine

- Setare noua in Audio RomyLive, langa preferinta pentru romana:
  Foloseste pista Latin/Latine daca lipseste romana (implicit activata).
- Pista identificata romana are intotdeauna prioritate. Daca nu exista,
  optiunea permite selectia la/lat/Latin/Latine sau a numelui Latin/Latine.
- Este doar o regula pentru surse etichetate gresit: o pista cu aceasta
  eticheta nu este garantat romana. Dezactiveaza rezerva cand nu este potrivita.
- Dezactivarea selectiei automate romana opreste si rezerva Latin/Latine.
- Regula se aplica la pornire si in serviciul audio, doar pentru RomyLive;
  nu modifica preferintele globale Kodi si nu ghiceste piste fara eticheta.
- 77 teste automate trecute. Instaleaza ZIP si reporneste Kodi.
  Nu este necesara schimbarea default.py pe server.

RomyLive+ 3.3.8 - Corectie detectie Cloudflare in filtrul Byse

- 3.3.7 confunda scriptul pasiv Cloudflare (prezent si pe pagini normale)
  cu o pagina de verificare. Acest lucru putea ascunde toate filmele.
- 3.3.8 verifica mai intai optiunea Byse si recunoaste interstitialul dupa
  titlu/formular, nu dupa simpla prezenta a scriptului challenge-platform.
- Audio, contor, redare directa si paginare raman neschimbate.
- 68 teste automate trecute. Nu este test de redare efectiva Kodi Windows.
- Instaleaza ZIP 3.3.8 peste addon si reporneste Kodi. default.py remote
  nu trebuie schimbat. Erorile din 3.3.7 nu au fost memorate in cache.

RomyLive+ 3.3.7 - Mai mult si filme numai cu ByseWihe

NOU IN 3.3.7
- Paginarea citeste si <link rel="next">, prezent in HTML-ul real trimis
  pentru /serial/. In Kodi apare folderul "Mai mult - Pagina N".
  Urmareste linkul real pentru fiecare categorie, nu inventeaza pagini/AJAX.
- Filmele (/film/) sunt afisate numai dupa confirmarea optiunii Byse/ByseWihe
  in pagina detaliului. Serialele si celelalte tipuri nu sunt filtrate.
- Verificare cu maximum 4 cereri simultane, sesiuni HTTP separate pe fir.
  Prima deschidere a unei liste cu filme poate dura mai mult.
- Cache local: prezenta 6 ore; absenta 30 minute. Erorile HTTP/Cloudflare
  nu sunt memorate ca absenta. Filmele neverificate sunt ascunse temporar,
  cu notificare. O pagina fara filme eligibile pastreaza folderul Mai mult.
- Prezenta ByseWihe nu garanteaza ca playerul/CAPTCHA functioneaza.
- Redarea directa, mesajul "Incearca mai tarziu :))", contorul si selectia
  pistei romane sunt pastrate. Nu modifica preferintele audio globale.
- 65 teste automate trecute, inclusiv HTML-ul real trimis (15 seriale,
  link pagina 2), filtrare, cache si regresiile de redare/audio.
  Nu reprezinta verificare de redare efectiva in Kodi Windows.
- Instaleaza ZIP 3.3.7 peste addon si reporneste Kodi. Actualizarea exclusiv
  a fisierului remote NU instaleaza noul modul local romy_catalog.py.
- default.py pentru server pastreaza schema obfuscarii originale si hook-ul
  local. Codul remote nu necesita schimbare pentru aceste corectii locale.

RomyLive+ 3.3.6 - Desenefaine, ByseWihe direct si audio romana

NOU IN 3.3.6
- Filmele din Desenefaine pornesc direct prin serverul Byse/ByseWihe din pagina.
  Nu afiseaza lista serverelor pentru filme. Serialele raman neschimbate.
- Daca serverul lipseste, verificarea esueaza sau playerul nu porneste in
  intervalul de asteptare: mesaj "Incearca mai tarziu :))".
- Contor simplu cu secundele scurse (1, 2, 3...), inchis la pornirea video.
  Nu este timp ramas si nu poate garanta momentul conectarii.
- Pista romana selectata la pornirea efectiva a playerului, fara compararea
  stricta a URL-ului CDN care poate fi redirectionat. Serviciul audio ramane.
- 48 teste automate trecute; redarea efectiva in Kodi Windows nu este
  verificata aici. Instaleaza ZIP-ul nou si reporneste Kodi.
- Pentru server foloseste default.py obfuscat livrat impreuna cu acest ZIP.
  Fișierul remote foloseste modulele locale noi: necesita versiunea 3.3.6.

INSTALARE
Instaleaza ZIP-ul peste RomyLive existent din Kodi -> Add-ons -> Install from
ZIP. Nu dezinstala addonul. Pastreaza ResolveURL actualizat si InputStream
Adaptive activ. RE PORNESTE KODI dupa instalare pentru serviciul audio.

MODIFICARI
- API nativ pentru domeniile reale identificate in noul kodi.log:
  player4me.embed4me.com, streamp2p.p2pplay.online,
  seeksreaming.embedseek.com. Foloseste ID-ul real din link, nu unul ghicit.
- Formatul AES de transport API este cel public din player si ResolveURL.
- Antete HTTP si parametri de sesiune transmisi catre InputStream Adaptive.
- Byse foloseste acelasi algoritm de verificare din ResolveURL, cu pana la
  90 secunde in locul bugetului de 20 secunde. Afiseaza progres si Anulare.
  Nu garanteaza reusita CAPTCHA. Nu modifica instalarea ResolveURL.
- Pista audio romana este selectata automat dupa ce Kodi incarca pistele,
  pentru redarile marcate de RomyLive. Poate dura cateva secunde de la pornire.
  Nu schimba preferintele audio globale si nu forteaza audio la alte addonuri.
- Recunoaste etichetele ro/ron/rum/Romanian/romana si numele de piste romana.
  Daca nu exista o pista identificabila, lasa audio neschimbat; nu ghiceste
  dupa numarul pistei. Nu traduce si nu creeaza dublaj.
- Optiune in setarile RomyLive: Audio RomyLive -> Selecteaza automat pista
  romana cand este disponibila (implicit activata).
- Corectiile raman locale chiar cand addonul descarca actualizari remote.

VERIFICARE SI LIMITARI
44 teste automate cu module Kodi simulate au trecut: API, transport AES,
antete, parametri de segment, subtitrari lipsa, callback, alegerea audio,
izolarea fata de alte redari si anularea verificarii Byse.
Acestea nu sunt teste de redare efectiva in Kodi Windows.
API-urile Streamp2p/Seek au fost accesibile aici; pagina Player4me a raspuns
HTTP 502. Desenefaine blocheaza accesul din acest mediu prin Cloudflare.
Nu se garanteaza ca toate serverele sunt functionale. Nu ocoleste DRM,
restrictii de acces sau CAPTCHA; verificarea Byse ramane cea oficiala.
Unele sesiuni video pot necesita reinnoirea tokenului; daca redarea porneste
dar se opreste ulterior, trimite logul complet de la acel moment.

DIAGNOSTIC WINDOWS
Log: de obicei %APPDATA%\Kodi\kodi.log
Cauta [RomyLive Desenefaine fix 1.1.0] si [RomyLive Audio].
Trimite hostul, identificatorul playerului, eroarea API/Byse si erorile Kodi.
"Pista romana selectata" confirma ca Kodi a acceptat selectia.
"Sursa rezolvata; predare catre playerul Kodi" nu confirma redarea efectiva.

SURSE DEPENDENTE
https://github.com/Gujal00/ResolveURL
https://github.com/Gujal00/smrzips