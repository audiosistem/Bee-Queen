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