# -*- coding: UTF-8 -*-

import webbrowser
from kodi_six import xbmc, xbmcgui

def platform():
    if xbmc.getCondVisibility('system.platform.android'):
        return 'android'
    return 'pc'

myplatform = platform()
# Folosim ghilimele pentru a proteja URL-ul în comanda Android
mycommand = 'StartAndroidActivity("","android.intent.action.VIEW","","%s")'

def start_imdb_flow():
    dialog = xbmcgui.Dialog()
    
    # 1. Deschidem browserul pentru navigare
    link_imdb = 'https://www.imdb.com'
    if myplatform == 'android':
        xbmc.executebuiltin(mycommand % link_imdb)
    else:
        webbrowser.open(link_imdb)

    # 2. Caseta de confirmare persistentă
    if dialog.yesno("[B]IMDB FIX 404[/B]", "Copiați URL-ul filmului/serialului și apăsați [B]DA[/B]."):
        
        # 3. Caseta de input pentru URL
        url_copiat = dialog.input('Lipește URL-ul aici:', type=xbmcgui.INPUT_ALPHANUM)
        
        if url_copiat:
            # --- LOGICĂ DE CURĂȚARE PENTRU SERIALE ---
            # Verificăm dacă link-ul conține rădăcina validă[cite: 1]
            if 'imdb.com/title/' in url_copiat:
                # Eliminăm parametrii de tip ?ref_ sau alte query-uri[cite: 1]
                base_url = url_copiat.split('?')[0]
                
                # Despărțim URL-ul pentru a izola ID-ul 'tt0000000'
                parts = base_url.split('/')
                try:
                    # Găsim indexul unde se află ID-ul de titlu (începe cu 'tt')
                    tt_index = [i for i, s in enumerate(parts) if s.startswith('tt')][0]
                    # Reconstruim URL-ul doar până la ID, ignorând /episodes sau alte sub-pagini
                    clean_id = parts[tt_index]
                    
                    # Construim link-ul final curat
                    link_final = "https://playimdb.com/title/%s" % clean_id
                    
                    # 4. Execuția[cite: 1]
                    if myplatform == 'android':
                        xbmc.executebuiltin(mycommand % link_final)
                    else:
                        webbrowser.open(link_final)
                except (IndexError, ValueError):
                    dialog.ok("Eroare", "Link-ul nu conține un ID valid (ex: tt1234567).")
            else:
                dialog.ok("Eroare", "Acesta nu este un link valid de IMDB.")
    return

if __name__ == '__main__':
    start_imdb_flow()