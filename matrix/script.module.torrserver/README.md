# script.module.torrserver

Modul Kodi pentru streaming de torrenți prin [TorrServer](https://github.com/YouROK/TorrServer).

Descarcă torrenții secvențial și îi distribuie ca stream HTTP către playerul Kodi, fără a fi nevoie de descărcarea completă a fișierului.

## Configurare

În setările modulului (`Configurare TorrServer`):

- **Host** — adresa IP unde rulează TorrServer (implicit: `127.0.0.1`)
- **Port** — portul TorrServer (implicit: `8090`)
- **Save torrent in DB** — păstrează torrentul în baza de date TorrServer după redare
- **Use Authentication** — activează autentificarea HTTP Basic dacă TorrServer e protejat cu parolă

## Credit

Forked from [script.module.torrserver](https://github.com/vlmaksime/script.module.torrserver) by **-=Vd=-**
Modificat și adaptat pentru **plugin.video.sarmis** de **derzis**
