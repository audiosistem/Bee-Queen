# -*- coding: utf-8 -*-
import threading
import traceback
import xbmc
from romy_audio import run_service

def youtube_service():
    try:
        from romy_youtube import run_service as run_youtube_service
        run_youtube_service()
    except Exception:
        xbmc.log('[RomyLive YouTube] Serviciu oprit:\n' + traceback.format_exc(), xbmc.LOGERROR)

if __name__ == '__main__':
    youtube_thread = threading.Thread(target=youtube_service, name='RomyLive-YouTube')
    youtube_thread.daemon = True
    youtube_thread.start()
    run_service()
    youtube_thread.join(timeout=5)