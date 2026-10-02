# -*- coding: utf-8 -*-

import threading

from resources.lib.modules import control
from resources.lib.modules import log_utils


def syncTraktLibrary():
    try:
        control.execute('RunPlugin(plugin://%s)' % 'plugin.video.gratisred/?action=movies_to_library_silent&url=trakt_collection')
        control.execute('RunPlugin(plugin://%s)' % 'plugin.video.gratisred/?action=tvshows_to_library_silent&url=trakt_collection')
        log_utils.log('Trakt Library Sync Successful.')
    except Exception:
        log_utils.log('syncTraktLibrary', 1)
        pass


def syncMdblistWatched():
    try:
        from resources.lib.modules import mdblist
        if mdblist.syncMdblistWatched(silent=True, force_update=False):
            log_utils.log('MDBList Watched Sync Successful.')
        else:
            log_utils.log('MDBList Watched Sync Skipped.')
    except Exception:
        log_utils.log('MDBList Watched Sync Failed.', 1)
        pass


def syncSimklWatched():
    try:
        from resources.lib.modules import simkl
        if simkl.syncSimklWatched(silent=True):
            log_utils.log('Simkl Watched Sync Successful.')
        else:
            log_utils.log('Simkl Watched Sync Skipped.')
    except Exception:
        log_utils.log('Simkl Watched Sync Failed.', 1)
        pass


try:
    from resources.lib.modules import simkl
    simkl.ensure_indicators_valid()
    if simkl.getSimklCredentialsInfo():
        threading.Thread(target=simkl.refresh_simkl_account_plan, daemon=True).start()
except Exception:
    pass


# New providers in 1.3.9. Set once so an update turns them on. A later
# untick is left alone. VidLove stays at its default, off.
_NEW_PROVIDERS = (
    'cinetaro', 'databasegdriveplayer', 'vidking',
    'vidnest', 'vidrock', 'vidsrc', 'watchepisodes',
)
# Set once so an update turns them off. A later tick is left alone.
_OFF_PROVIDERS = (
    'fzmovies_live', 'tvseries_video', 'tvmovieflix_com',
)
try:
    if control.setting('providers.forced.139') != 'true':
        for _name in _NEW_PROVIDERS:
            control.setSetting('provider.' + _name, 'true')
        control.setSetting('providers.forced.139', 'true')
except Exception:
    log_utils.log('Force new providers failed.', 1)

try:
    if control.setting('providers.forced.off.139') != 'true':
        for _name in _OFF_PROVIDERS:
            control.setSetting('provider.' + _name, 'false')
        control.setSetting('providers.forced.off.139', 'true')
except Exception:
    log_utils.log('Force providers off failed.', 1)


# Enable Fanart.tv Artwork. Set once so an update turns it on. A later untick is left alone.
try:
    if control.setting('fanart.artwork.forced.200') != 'true':
        control.setSetting('fanart.artwork', 'true')
        control.setSetting('fanart.artwork.forced.200', 'true')
except Exception:
    log_utils.log('Force Fanart.tv artwork failed.', 1)


try:
    from resources.lib.apis import opensubs_api
    opensubs_api.ensure_api_key_migrated()
except Exception:
    pass


try:
    control.execute('RunPlugin(plugin://%s)' % 'plugin.video.gratisred/?action=service')
    log_utils.log('Service Process Successful.')
except Exception:
    log_utils.log('Service Process Failed.', 1)
    pass


try:
    from resources.lib.modules import changelog_notice
    changelog_notice.service_check()
except Exception:
    log_utils.log('Changelog Notice Check Failed.', 1)
    pass


try:
    if control.setting('trakt.sync') == 'true':
        synctime = control.setting('trakt.synctime') or '0'
        if int(synctime) > 0:
            timeout = 3600 * int(synctime)
            log_utils.log('Trakt Library Sync Delayed: ' + str(synctime) + ' Hours.')
            schedTrakt = threading.Timer(timeout, syncTraktLibrary)
            schedTrakt.start()
        else:
            syncTraktLibrary()
except Exception:
    log_utils.log('Trakt Library Sync Failed.', 1)
    pass


try:
    if control.setting('simkl.sync') == 'true':
        synctime = control.setting('simkl.synctime') or '0'
        if int(synctime) > 0:
            timeout = 3600 * int(synctime)
            log_utils.log('Simkl Watched Sync Delayed: ' + str(synctime) + ' Hours.')
            schedSimkl = threading.Timer(timeout, syncSimklWatched)
            schedSimkl.start()
        else:
            syncSimklWatched()
except Exception:
    log_utils.log('Simkl Watched Sync Failed.', 1)
    pass


try:
    if control.setting('mdblist.sync') == 'true':
        synctime = control.setting('mdblist.synctime') or '0'
        if int(synctime) > 0:
            timeout = 3600 * int(synctime)
            log_utils.log('MDBList Watched Sync Delayed: ' + str(synctime) + ' Hours.')
            schedMdblist = threading.Timer(timeout, syncMdblistWatched)
            schedMdblist.start()
        else:
            syncMdblistWatched()
except Exception:
    log_utils.log('MDBList Watched Sync Failed.', 1)
    pass


