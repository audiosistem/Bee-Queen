# -*- coding: utf-8 -*-
"""Free Flow background service.

Scans the chains24 directory tree every 30 seconds, builds an index of every
item, and tracks newly-added entries so the addon can show a "What's New"
section and power universal search.
"""
import os
import sys
import time

import xbmc
import xbmcgui
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
sys.path.insert(0, os.path.join(ADDON_PATH, 'resources', 'lib'))

import feed  # noqa: E402
import debug as dbg  # noqa: E402

SCAN_INTERVAL = 30  # seconds

LOG_TAG = '[plugin.video.freeflow.service]'


def log(msg, level=xbmc.LOGINFO):
    try:
        xbmc.log('%s %s' % (LOG_TAG, msg), level)
    except Exception:
        pass


def run_scan(http_cache):
    """One full scan cycle: walk tree, diff against known, persist."""
    monitor = xbmc.Monitor()
    items = feed.walk_tree(
        root_url=feed.ROOT_URL,
        http_cache=http_cache,
        cache_ttl=25,
        abort_check=lambda: monitor.abortRequested(),
    )
    if monitor.abortRequested():
        return

    known = feed.load_json(feed.known_path(), {})
    bootstrapped = bool(known.get('_bootstrapped'))
    now = time.time()
    new_keys = []

    for it in items:
        k = feed.item_key(it)
        if not k or k.startswith('_'):
            continue
        if k not in known:
            it['first_seen'] = now
            known[k] = it
            if bootstrapped:
                new_keys.append(k)
        else:
            # refresh artwork/plot if it changed upstream
            stored = known[k]
            for f in ('thumbnail', 'fanart', 'plot', 'sublinks',
                      'parent_title'):
                if it.get(f):
                    stored[f] = it[f]
            known[k] = stored

    known['_bootstrapped'] = True
    known['_last_scan'] = now
    feed.save_json(feed.known_path(), known)

    if new_keys:
        new_list = feed.load_json(feed.new_path(), [])
        new_keys_existing = {feed.item_key(x) for x in new_list}
        for k in new_keys:
            if k not in new_keys_existing:
                new_list.append(known[k])
        cutoff = now - feed.NEW_WINDOW_SECONDS
        new_list = [x for x in new_list if x.get('first_seen', 0) > cutoff]
        feed.save_json(feed.new_path(), new_list)
        log('scan: %d total items, %d NEW' % (len(items), len(new_keys)))

        # Pop-up notification: ping user with what just dropped
        try:
            first = known[new_keys[0]]
            first_title = first.get('title', '')
            parent = first.get('parent_title', '')
            if len(new_keys) == 1:
                msg = '%s  -  in %s' % (first_title, parent)
            else:
                msg = '%s  +%d more' % (first_title, len(new_keys) - 1)
            icon = os.path.join(ADDON_PATH, 'icon.png')
            xbmcgui.Dialog().notification(
                'Free Flow - New release', msg,
                icon, 6000, False)
        except Exception as e:
            log('notify error: %s' % e, xbmc.LOGERROR)
    else:
        # still prune expired entries from new.json
        new_list = feed.load_json(feed.new_path(), [])
        if new_list:
            cutoff = now - feed.NEW_WINDOW_SECONDS
            pruned = [x for x in new_list if x.get('first_seen', 0) > cutoff]
            if len(pruned) != len(new_list):
                feed.save_json(feed.new_path(), pruned)
        log('scan: %d total items' % len(items))


def main():
    log('service starting (scan every %ds)' % SCAN_INTERVAL)
    dbg.session_banner(reason='service start')
    monitor = xbmc.Monitor()
    http_cache = {}
    cycle = 0
    while not monitor.abortRequested():
        cycle += 1
        try:
            t0 = time.time()
            run_scan(http_cache)
            dbg.dlog('scan cycle #%d done in %.2fs (cache=%d)' % (
                cycle, time.time() - t0, len(http_cache)),
                level='INFO', component='service')
        except Exception as e:
            log('scan error: %s' % e, xbmc.LOGERROR)
            dbg.dump_exception('service', context='scan cycle #%d' % cycle)
        if len(http_cache) > 2000:
            http_cache.clear()
        if monitor.waitForAbort(SCAN_INTERVAL):
            break
    log('service stopping')
    dbg.dlog('service stopping', level='INFO', component='service')


if __name__ == '__main__':
    main()
