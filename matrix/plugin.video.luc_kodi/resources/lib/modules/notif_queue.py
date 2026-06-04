# -*- coding: utf-8 -*-
"""
    luc_kodi Add-on — notif_queue.py

    Cola de notificaciones thread-safe.
    Muestra las notificaciones en orden FIFO, una tras otra,
    con un hueco de GAP_MS ms entre ellas para que no se solapen.

    Uso:
        from resources.lib.modules import notif_queue
        notif_queue.push(message='Texto', title='luc_kodi', time=3000)
"""

from __future__ import absolute_import

import threading
from collections import deque

from resources.lib.modules import control
from resources.lib.modules import log_utils

# Hueco entre notificaciones en milisegundos
GAP_MS = 400

_queue   = deque()
_lock    = threading.Lock()
_running = threading.Event()
_worker  = None


def _show_loop():
    while True:
        with _lock:
            if not _queue:
                _running.clear()
                return
            item = _queue.popleft()
        try:
            control.notification(
                title   = item.get('title', 'luc_kodi'),
                message = item.get('message', ''),
                time    = item.get('time', 3000),
            )
        except Exception:
            log_utils.error()
        # esperar a que termine la notificación + hueco
        duration_ms = item.get('time', 3000)
        control.sleep(duration_ms + GAP_MS)


def push(message, title='luc_kodi', time=3000):
    """
    Encola una notificación. Si el worker no está corriendo, lo arranca.
    thread-safe, puede llamarse desde cualquier hilo.
    """
    global _worker
    with _lock:
        _queue.append({'title': title, 'message': message, 'time': time})
        already_running = _running.is_set()
        if not already_running:
            _running.set()

    if not already_running:
        _worker = threading.Thread(target=_show_loop, daemon=True)
        _worker.start()
