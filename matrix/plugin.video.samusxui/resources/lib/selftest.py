"""Smoke test Kodi: RunScript(.../resources/lib/selftest.py[,URL_BYSE])."""
import os
import sys
import threading
import time

import xbmc

ADDON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ADDON_PATH not in sys.path:
    sys.path.insert(0, ADDON_PATH)

from resources.lib import db
from resources.lib.stream_info import StreamInfo
from resources.lib.task_group import TaskGroup


def run():
    started = time.monotonic()
    stream = StreamInfo.parse(
        'https://example.invalid/a.m3u8|User-Agent=A+B Test&Referer=https%3A%2F%2Fx%2F'
    )
    assert stream.headers['User-Agent'] == 'A+B Test'
    assert stream.headers['Referer'] == 'https://x/'

    db.provider_health_ok('[SELFTEST]', latency=2.5, had_results=True)
    assert 2.4 <= db.provider_health_score('[SELFTEST]') <= 2.6
    connection = db._connect()
    connection.execute('DELETE FROM provider_health WHERE provider=?', ('[SELFTEST]',))
    connection.commit()
    connection.close()

    group = TaskGroup('selftest')
    group.start(lambda: time.sleep(0.05), name='selftest-short')
    assert group.close(timeout=2.0)

    byse_times = None
    if len(sys.argv) > 1 and sys.argv[1].startswith(('http://', 'https://')):
        from resources.lib.resolvers import byse
        mark = time.monotonic()
        first = byse.resolve(sys.argv[1])
        first_time = time.monotonic() - mark
        mark = time.monotonic()
        second = byse.resolve(sys.argv[1])
        cache_time = time.monotonic() - mark
        assert first == second and cache_time < 0.1
        byse_times = (first_time, cache_time)

    xbmc.log('[Samus/selftest] OK elapsed={:.3f}s byse={} threads={}'.format(
        time.monotonic() - started, byse_times,
        ['{}(daemon={})'.format(t.name, t.daemon) for t in threading.enumerate()],
    ), xbmc.LOGINFO)


if __name__ == '__main__':
    run()
