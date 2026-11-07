# -*- coding: utf-8 -*-
"""Short IPv6 probe, then IPv4 for the rest of the Kodi session if IPv6 is a black hole."""
import socket
from time import monotonic

ipv6_probe_budget = 2.0
failed_prop = 'gratisred.ipv6_failed'
_home = None
_failed = None


def _home_window():
    global _home
    if _home is None:
        from kodi_six import xbmcgui
        _home = xbmcgui.Window(10000)
    return _home


def ipv6_failed():
    global _failed
    if _failed is not None:
        return _failed
    try:
        _failed = _home_window().getProperty(failed_prop) == 'true'
    except Exception:
        _failed = False
    return _failed


def mark_ipv6_failed():
    global _failed
    _failed = True
    try:
        _home_window().setProperty(failed_prop, 'true')
    except Exception:
        pass
    try:
        from kodi_six import xbmc
        xbmc.log('###Gratis Red###: IPv6 connect failed; this session will use IPv4', 1)
    except Exception:
        pass


def numeric_timeout(timeout):
    if timeout is None or isinstance(timeout, (int, float)):
        return timeout
    try:
        value = timeout.connect_timeout
        if isinstance(value, (int, float)):
            return value
    except Exception:
        pass
    return None


def apply_timeout(sock, timeout):
    if timeout is None or isinstance(timeout, (int, float)):
        sock.settimeout(timeout)
    else:
        sock.settimeout(socket.getdefaulttimeout())


def connect(entry, timeout, source_address, socket_options):
    family, socktype, proto, _, sockaddr = entry
    sock = socket.socket(family, socktype, proto)
    try:
        for option in socket_options or ():
            sock.setsockopt(*option)
        apply_timeout(sock, timeout)
        if source_address:
            sock.bind(source_address)
        sock.connect(sockaddr)
        return sock
    except BaseException:
        sock.close()
        raise


def connect_first(entries, timeout, source_address, socket_options):
    error = OSError('getaddrinfo returns an empty list')
    for entry in entries:
        try:
            return connect(entry, timeout, source_address, socket_options)
        except OSError as e:
            error = e
    raise error


def connect_ipv6(entries, budget, restore_timeout, source_address, socket_options):
    error = OSError('getaddrinfo returns an empty list')
    deadline = monotonic() + budget
    for entry in entries:
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        try:
            sock = connect(entry, remaining, source_address, socket_options)
            apply_timeout(sock, restore_timeout)
            return sock
        except OSError as e:
            error = e
    raise error


def create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, socket_options=None, **kwargs):
    host, port = address[0].strip('[]'), address[1]
    entries = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    ipv6 = [i for i in entries if i[0] == socket.AF_INET6]
    ipv4 = [i for i in entries if i[0] == socket.AF_INET]
    if not (ipv6 and ipv4):
        return connect_first(entries, timeout, source_address, socket_options)
    if ipv6_failed():
        return connect_first(ipv4, timeout, source_address, socket_options)
    probe = ipv6_probe_budget
    limit = numeric_timeout(timeout)
    if isinstance(limit, (int, float)) and limit >= 0:
        probe = min(probe, limit)
    try:
        return connect_ipv6(ipv6, probe, timeout, source_address, socket_options)
    except OSError:
        pass
    sock = connect_first(ipv4, timeout, source_address, socket_options)
    mark_ipv6_failed()
    return sock


def install():
    if getattr(socket.create_connection, '_gratisred_ipv4_fallback', False):
        return
    create_connection._gratisred_ipv4_fallback = True
    ipv6_failed()
    socket.create_connection = create_connection
    try:
        from urllib3.util import connection
        connection.create_connection = create_connection
    except ImportError:
        pass
    try:
        import http.client as http_client
    except ImportError:
        try:
            import httplib as http_client
        except ImportError:
            http_client = None
    if http_client is not None:
        try:
            http_client.HTTPConnection._create_connection = staticmethod(create_connection)
        except Exception:
            pass
