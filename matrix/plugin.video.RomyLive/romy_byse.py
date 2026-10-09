# -*- coding: utf-8 -*-
"""Use the official Byse resolver, with a longer cancellable PoW budget."""
import time


class UserCancelled(Exception):
    pass


class ByseFailed(Exception):
    pass


def resolve_byse(url, seconds=90, quiet=False):
    from resolveurl.plugins.byse import ByseResolver
    import xbmc
    import xbmcgui
    resolver = ByseResolver()
    host_id = resolver.get_host_and_id(url)
    if not host_id:
        return False, ''
    original_solver = resolver.er

    def solve(nonce, difficulty, r=90):
        if difficulty <= 0:
            return '0'
        dialog = None if quiet else xbmcgui.DialogProgress()
        if dialog:
            dialog.create('Byse', 'Verificarea serverului. Poti anula si alege alt server.')
        monitor = xbmc.Monitor()
        deadline = time.monotonic() + seconds
        counter = 0
        try:
            while time.monotonic() < deadline:
                if (dialog and dialog.iscanceled()) or monitor.abortRequested():
                    raise UserCancelled('Verificare anulata')
                for _ in range(16):
                    digest = resolver.gr((nonce + ':' + str(counter)).encode('ascii'))
                    if resolver.wr(digest) >= difficulty:
                        return str(counter)
                    counter += 1
                elapsed = seconds - max(0, deadline - time.monotonic())
                if dialog:
                    dialog.update(min(99, int(elapsed * 100 / seconds)),
                              'Verificarea serverului: %d / %d secunde. Anulare pentru alt server.'
                              % (elapsed, seconds))
            return None
        finally:
            if dialog:
                dialog.close()

    # Instance-local override: never change the installed ResolveURL files.
    resolver.er = solve
    try:
        return True, resolver.get_media_url(*host_id)
    except UserCancelled:
        raise
    except Exception as exc:
        raise ByseFailed(str(exc)) from exc
    finally:
        resolver.er = original_solver