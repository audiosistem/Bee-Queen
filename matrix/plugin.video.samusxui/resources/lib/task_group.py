"""Fire de lucru cu proprietar explicit pentru ferestrele Kodi.

Un fir daemon este tot un fir viu pentru Py_EndInterpreter. TaskGroup împiedică
taskuri noi după close(), semnalează anularea și reunește firele cunoscute.
Worker-ele trebuie în continuare să aibă timeouturi finite pentru I/O.
"""
import threading
import time

import xbmc


class TaskGroup:
    def __init__(self, owner):
        self.owner = owner
        self.cancelled = threading.Event()
        self._lock = threading.Lock()
        self._threads = set()

    def start(self, target, args=(), name=None):
        if self.cancelled.is_set():
            return None

        def run():
            try:
                if not self.cancelled.is_set():
                    target(*args)
            except Exception as exc:
                xbmc.log('[Samus/tasks] {}: {}'.format(name or target.__name__, exc),
                         xbmc.LOGWARNING)
            finally:
                with self._lock:
                    self._threads.discard(threading.current_thread())

        thread = threading.Thread(
            target=run,
            name=name or '{}:{}'.format(self.owner, target.__name__),
            daemon=True,
        )
        with self._lock:
            if self.cancelled.is_set():
                return None
            self._threads.add(thread)
        thread.start()
        return thread

    def close(self, timeout=8.0):
        self.cancelled.set()
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                current = threading.current_thread()
                alive = [thread for thread in self._threads
                         if thread.is_alive() and thread is not current]
            if not alive:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                xbmc.log('[Samus/tasks] {}: fire rămase după {:.1f}s: {}'.format(
                    self.owner, timeout, [thread.name for thread in alive]), xbmc.LOGERROR)
                return False
            for thread in alive:
                thread.join(min(0.1, remaining))

    def is_cancelled(self):
        return self.cancelled.is_set()
