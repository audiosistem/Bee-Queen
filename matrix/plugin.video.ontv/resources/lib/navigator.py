# -*- coding: utf-8 -*-
"""
OnTV — Navigator
  Suporta: Xtream Codes, Stalker/MAC Portal, M3U por URL
  Reprodução via F4mTester
"""

import sys
import os
import re
import json
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

try:
    from urllib.request import urlopen, Request
    from urllib.parse   import urlencode, parse_qsl, quote, unquote
except ImportError:
    from urllib2  import urlopen, Request
    from urllib   import urlencode, quote, unquote
    from urlparse import parse_qsl

ADDON      = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_PATH = ADDON.getAddonInfo('path')
HANDLE     = int(sys.argv[1])
BASE_URL   = sys.argv[0]
ICON       = os.path.join(ADDON_PATH, 'icon.png')
FANART     = os.path.join(ADDON_PATH, 'fanart.png')
UA_STB     = 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stb mergnat/1.1 Safari/533.3'
UA_KODI    = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Kodi/21.0'
# F4M_ID removido — reprodução direta sem F4mTester
_CACHE     = {}

# ── Filtro adulto ─────────────────────────────────────────────────────────
PALAVRAS_ADULTO = [
    'adult', 'adults', 'xxx', 'porn', 'sex', '18+', 'erotic', 'erotica',
    'x-rated', 'xrated', 'hentai', 'playboy', 'nude', 'naked',
    'adulto', 'adultos', 'adulte', 'adultes',
]

def _normalizar(nome):
    """Remove caracteres não-alfanuméricos do início do nome (|, emojis, espaços, etc.)
    e devolve o nome limpo em maiúsculas para comparação."""
    import re
    # Remover qualquer caracter que não seja letra, número ou espaço do início
    return re.sub(r'^[^a-zA-Z0-9]+', '', nome).strip().upper()

def e_adulto(nome):
    n = nome.lower()
    n_norm = _normalizar(nome).lower()
    return any(p in n or n_norm.startswith(p) for p in PALAVRAS_ADULTO)

def filtrar_adulto(lista, campo='category_name'):
    return [i for i in lista if not e_adulto(i.get(campo, ''))]


def log(msg):
    xbmc.log('[OnTV] ' + str(msg), xbmc.LOGDEBUG)

def url_para(params):
    return BASE_URL + '?' + urlencode(params)

def notificar(msg, tipo=xbmcgui.NOTIFICATION_ERROR):
    xbmcgui.Dialog().notification(ADDON_NAME, msg, tipo, 4000)

def http_get(url, headers=None, usar_cache=True):
    if usar_cache and url in _CACHE:
        return _CACHE[url]
    try:
        req  = Request(url, headers=headers or {'User-Agent': UA_STB})
        resp = urlopen(req, timeout=20)
        data = resp.read().decode('utf-8', errors='replace')
        if usar_cache and data:  # só guardar em cache se resposta válida
            _CACHE[url] = data
        return data
    except Exception as e:
        log('ERRO HTTP: ' + str(e) + ' | URL: ' + url)
        # Limpar cache desta URL para forçar retry na próxima chamada
        _CACHE.pop(url, None)
        return None

def api_json(url, headers=None, usar_cache=True):
    data = http_get(url, headers, usar_cache)
    if not data:
        return None
    try:
        return json.loads(data)
    except:
        log('ERRO JSON parse: ' + url)
        return None


# ════════════════════════════════════════════════════════
#  STALKER / MAC — Autenticação e API
# ════════════════════════════════════════════════════════

def stalker_base(host):
    """Obtém a URL base do servidor a partir do host configurado."""
    # Remove /c/ do fim se existir
    base = host.rstrip('/')
    if base.endswith('/c'):
        base = base[:-2]
    return base

def stalker_headers(mac):
    return {
        'User-Agent':   UA_STB,
        'X-User-Agent': 'Model: MAG250; Link: WiFi',
        'Cookie':       'mac=' + mac + '; stb_lang=en; timezone=Europe/Lisbon',
        'Referer':      'http://localhost/c/',
        'Accept':       '*/*',
    }

def stalker_token(host, mac, forcar=False):
    """Obtém ou renova o token do portal Stalker.
    forcar=True renova sempre (usar quando receber erro 458)."""
    cache_key = 'stalker_token_' + mac
    if not forcar and cache_key in _CACHE:
        return _CACHE[cache_key]

    base = stalker_base(host)
    url  = base + '/server/load.php?type=stb&action=handshake&token=&JsHttpRequest=1-xml'
    data = api_json(url, stalker_headers(mac), usar_cache=False)

    if not data:
        log('Stalker handshake falhou: ' + url)
        return None

    token = data.get('js', {}).get('token', '')
    log('Stalker token' + (' (renovado)' if forcar else '') + ': ' + str(token))
    if token:
        _CACHE[cache_key] = token
    return token or None

def stalker_call(host, mac, params_str):
    base  = stalker_base(host)
    token = stalker_token(host, mac)
    if not token:
        return None
    url     = base + '/server/load.php?' + params_str + '&token=' + token + '&JsHttpRequest=1-xml'
    headers = stalker_headers(mac)
    headers['Authorization'] = 'Bearer ' + token
    return api_json(url, headers, usar_cache=False)

def stalker_categorias(host, mac, tipo):
    """Obtém categorias do portal Stalker. tipo: itv | vod | series"""
    action = 'get_genres' if tipo == 'itv' else 'get_categories'
    data   = stalker_call(host, mac, 'type={}&action={}'.format(tipo, action))
    if not data:
        return []
    cats = data.get('js', [])
    if isinstance(cats, dict):
        cats = list(cats.values())
    return [c for c in cats if c.get('title') or c.get('name')]

def stalker_canais(host, mac, tipo, cat_id):
    """Obtém canais/filmes de uma categoria — percorre todas as páginas.
    Usa perpage=14 porque muitos servidores Stalker ignoram valores maiores
    e devolvem sempre o número máximo que suportam (normalmente 14 ou 20).
    """
    todos       = []
    pagina      = 1
    perpage     = 14   # valor conservador — compatível com todos os servidores
    max_paginas = 500  # segurança contra loops infinitos

    while pagina <= max_paginas:
        params = 'type={}&action=get_ordered_list&genre={}&p={}&perpage={}&sortby=number'.format(
            tipo, cat_id, pagina, perpage)
        data = stalker_call(host, mac, params)
        if not data:
            log('Stalker canais p{}: sem resposta — a parar'.format(pagina))
            break
        js = data.get('js', {})
        if not isinstance(js, dict):
            log('Stalker canais p{}: js inválido — a parar'.format(pagina))
            break

        items       = js.get('data', [])
        total_items = int(js.get('total_items', 0) or 0)
        max_page_items = int(js.get('max_page_items', perpage) or perpage)

        todos.extend(items)
        log('Stalker canais p{}/{}: {} itens, total={}, max_page={}'.format(
            pagina, -(-total_items // max(max_page_items,1)),
            len(items), total_items, max_page_items))

        # Parar se: página vazia, ou já temos tudo
        if not items:
            break
        if total_items > 0 and len(todos) >= total_items:
            break
        # Se o servidor devolveu menos itens do que o máximo da página → última página
        if len(items) < max_page_items:
            break

        pagina += 1

    log('Stalker canais total carregado: {}'.format(len(todos)))
    return todos

def _extrair_stream_id(cmd):
    """Extrai o stream ID numérico do cmd original."""
    m = re.search(r'[&?]stream=(\d+)', cmd)
    return m.group(1) if m else ''

def _corrigir_stream_vazio(url, cmd_original):
    """Alguns servidores devolvem stream= vazio no create_link.
    Nesse caso, preenche com o stream ID do cmd original."""
    if 'stream=&' in url or url.endswith('stream='):
        stream_id = _extrair_stream_id(cmd_original)
        if stream_id:
            url = url.replace('stream=&', 'stream=' + stream_id + '&').rstrip('stream=') if url.endswith('stream=') else url.replace('stream=&', 'stream=' + stream_id + '&')
            log('Stalker stream ID corrigido: ' + stream_id)
    return url

def stalker_create_link(host, mac, tipo, cmd):
    """Obtém URL de stream para Stalker/MAG portais.

    Alguns servidores (ex: godofiptv) rejeitam tokens gerados pelo create_link
    com erro 458/459. Nesse caso, o cmd original tem o URL válido — basta
    limpar o prefixo ffmpeg e sanitizar.
    O create_link só é usado se o cmd for localhost.
    """
    cmd_limpo = _limpar_cmd(cmd)
    cmd_limpo = _corrigir_stream_vazio(cmd_limpo, cmd)

    # Se o cmd já é um URL externo válido → usar diretamente
    # (o play_token do portal é mais fiável que o do create_link nestes servidores)
    if cmd_limpo.startswith('http') and 'localhost' not in cmd_limpo and '127.0.0.1' not in cmd_limpo:
        log('Stalker: usando cmd direto: ' + cmd_limpo[:100])
        return cmd_limpo

    # cmd é localhost → precisamos do create_link para obter URL externo
    log('Stalker: cmd é localhost, a chamar create_link...')
    token = stalker_token(host, mac, forcar=True)
    if not token:
        log('Stalker: sem token, fallback para cmd limpo')
        return cmd_limpo

    base    = stalker_base(host)
    cmd_enc = quote(cmd, safe='')
    url_api = (base + '/server/load.php?type={}&action=create_link'
               '&cmd={}&series=&forced_storage=undefined&disable_ad=0&download=0'
               '&token={}&JsHttpRequest=1-xml').format(tipo, cmd_enc, token)
    headers = stalker_headers(mac)
    headers['Authorization'] = 'Bearer ' + token
    data = api_json(url_api, headers, usar_cache=False)

    js  = (data or {}).get('js', {})
    url = (js.get('url', '') or js.get('cmd', '')) if isinstance(js, dict) else ''
    url = _limpar_cmd(url) if url else ''
    url = _corrigir_stream_vazio(url, cmd) if url else ''

    if url and 'localhost' not in url and '127.0.0.1' not in url:
        log('Stalker: create_link OK: ' + url[:100])
        return url

    log('Stalker: create_link falhou, fallback para cmd limpo')
    return cmd_limpo
def _limpar_cmd(cmd):
    """Remove prefixo 'ffmpeg ' e sanitiza o URL (espaços, caracteres inválidos)."""
    cmd = cmd.strip()
    if cmd.startswith('ffmpeg '):
        cmd = cmd[7:].strip()
    # Sanitizar: substituir espaços dentro do URL por %20
    # (alguns servidores devolvem tokens com espaços — ex: play_token=IUhdN DIuBkK)
    if ' ' in cmd:
        # Separar URL de parâmetros e sanitizar cada parte
        parts = cmd.split('?', 1)
        if len(parts) == 2:
            base = parts[0]
            query = parts[1].replace(' ', '%20')
            cmd = base + '?' + query
        else:
            cmd = cmd.replace(' ', '%20')
    return cmd


# ════════════════════════════════════════════════════════
#  ECRÃ 1 — Servidores
# ════════════════════════════════════════════════════════

def mostrar_principal():
    from servers import SERVIDORES
    xbmcplugin.setPluginCategory(HANDLE, 'OnTV')

    for i, srv in enumerate(SERVIDORES):
        li = xbmcgui.ListItem(srv['nome'])
        li.setArt({'thumb': srv.get('icon') or ICON, 'fanart': FANART})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'tipos', 'srv_idx': str(i)}), li, True)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


# ════════════════════════════════════════════════════════
#  ECRÃ 2 — Tipos (Live TV / Movies / Series)
# ════════════════════════════════════════════════════════

def mostrar_tipos(srv_idx):
    from servers import SERVIDORES
    srv  = SERVIDORES[int(srv_idx)]
    tipo = srv.get('tipo', 'xtream')
    xbmcplugin.setPluginCategory(HANDLE, srv['nome'])

    if tipo == 'm3u':
        mostrar_grupos_m3u(srv_idx)
        return

    for nome, acao_cat in [('Live TV', 'live_cats'), ('Filmes', 'vod_cats'), ('Series', 'series_cats')]:
        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': ICON, 'fanart': ''})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': acao_cat, 'srv_idx': srv_idx}), li, True)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  ECRÃ 3 — Categorias
# ════════════════════════════════════════════════════════

def mostrar_categorias(srv_idx, tipo_cat):
    from servers import SERVIDORES
    srv  = SERVIDORES[int(srv_idx)]
    tipo = srv.get('tipo', 'xtream')

    if tipo == 'stalker':
        stalker_tipo = {'live_cats': 'itv', 'vod_cats': 'vod', 'series_cats': 'series'}[tipo_cat]
        acao_canais  = {'live_cats': 'stalker_live', 'vod_cats': 'stalker_vod', 'series_cats': 'stalker_series'}[tipo_cat]
        _mostrar_cats_stalker(srv_idx, srv, stalker_tipo, acao_canais)
        return

    # Xtream Codes
    host = srv['host']
    u    = srv['username']
    p    = srv['password']
    ep   = {
        'live_cats':   '/player_api.php?username={u}&password={p}&action=get_live_categories',
        'vod_cats':    '/player_api.php?username={u}&password={p}&action=get_vod_categories',
        'series_cats': '/player_api.php?username={u}&password={p}&action=get_series_categories',
    }[tipo_cat]

    data = api_json(host + ep.format(u=u, p=p))
    if not data:
        notificar('Erro ao carregar categorias!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    data = filtrar_adulto(data, 'category_name')
    acao = {'live_cats': 'live_canais', 'vod_cats': 'vod_canais', 'series_cats': 'series_canais'}[tipo_cat]

    # Ordenar: PT/Portugal primeiro, resto depois
    # Também deteta quando há um carácter antes (ex: "|PT", "🇵🇹PT")
    def prioridade_cat(c):
        n     = c.get('category_name', '').upper()
        n_lim = _normalizar(c.get('category_name', ''))
        if n.startswith('PT') or n_lim.startswith('PT') or 'PORTUGAL' in n:
            return 0
        return 1
    data = sorted(data, key=prioridade_cat)

    xbmcplugin.setPluginCategory(HANDLE, srv['nome'])
    for cat in data:
        nome   = cat.get('category_name', 'Sem Nome')
        cat_id = str(cat.get('category_id', ''))
        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': ICON, 'fanart': ''})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': acao, 'srv_idx': srv_idx, 'cat_id': cat_id, 'cat_nome': nome}), li, True)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)

def _mostrar_cats_stalker(srv_idx, srv, stalker_tipo, acao_canais):
    cats = stalker_categorias(srv['host'], srv['mac'], stalker_tipo)

    if not cats:
        notificar('Erro ao carregar categorias! Verifica host e MAC.')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    # Filtrar adulto pelo título da categoria
    cats = [c for c in cats if not e_adulto(c.get('title', c.get('name', '')))]

    # Ordenar: PT/Portugal primeiro, resto depois
    # Também deteta quando há um carácter antes (ex: "|PT", "🇵🇹PT")
    def prioridade_cat(c):
        raw   = c.get('title', c.get('name', ''))
        n     = raw.upper()
        n_lim = _normalizar(raw)
        if n.startswith('PT') or n_lim.startswith('PT') or 'PORTUGAL' in n:
            return 0
        return 1
    cats = sorted(cats, key=prioridade_cat)

    xbmcplugin.setPluginCategory(HANDLE, srv['nome'])
    for cat in cats:
        nome   = cat.get('title', cat.get('name', 'Sem Nome'))
        cat_id = str(cat.get('id', cat.get('genre_id', '*')))
        if not nome or nome == '0':
            continue
        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': ICON, 'fanart': ''})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': acao_canais, 'srv_idx': srv_idx, 'cat_id': cat_id, 'cat_nome': nome}), li, True)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  ECRÃ 4 — Canais Stalker
# ════════════════════════════════════════════════════════

def mostrar_canais_stalker(srv_idx, stalker_tipo, cat_id, cat_nome):
    from servers import SERVIDORES
    srv    = SERVIDORES[int(srv_idx)]
    canais = stalker_canais(srv['host'], srv['mac'], stalker_tipo, cat_id)

    if not canais:
        notificar('Sem canais nesta categoria.')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    def _e_separador(ch):
        """Detecta entradas falsas usadas como separadores de secção.
        O critério principal é o cmd — um separador nunca tem um URL
        de stream válido (http://...) no cmd.
        """
        cmd = ch.get('cmd', '').strip()
        # Sem cmd, cmd vazio, ou cmd que não contém um URL de stream
        if not cmd:
            return True
        # Um canal real tem sempre "http" no cmd (directo ou via ffmpeg)
        if 'http' not in cmd.lower():
            return True
        return False

    # Filtrar separadores e adultos
    canais = [ch for ch in canais if not _e_separador(ch) and not e_adulto(ch.get('name', ''))]

    xbmcplugin.setPluginCategory(HANDLE, cat_nome)
    for ch in canais:
        nome = ch.get('name', 'Canal')
        logo = (ch.get('logo', '') or ICON).replace(' ', '%20')
        cmd  = ch.get('cmd', '')

        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': logo, 'fanart': ''})
        li.setProperty('IsPlayable', 'true')
        li.setInfo('video', {'title': nome, 'mediatype': 'video', 'playcount': 0, 'overlay': 0})
        xbmcplugin.addDirectoryItem(
            HANDLE,
            url_para({'acao': 'stalker_play', 'srv_idx': srv_idx,
                      'stalker_tipo': stalker_tipo, 'cmd': cmd, 'nome': nome, 'logo': logo}),
            li, False
        )

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  ECRÃ 4 — Canais Xtream
# ════════════════════════════════════════════════════════

def mostrar_live(srv_idx, cat_id, cat_nome):
    from servers import SERVIDORES
    srv  = SERVIDORES[int(srv_idx)]
    host = srv['host']
    u    = srv['username']
    p    = srv['password']

    data = api_json('{}/player_api.php?username={}&password={}&action=get_live_streams&category_id={}'.format(host, u, p, cat_id))
    if not data:
        notificar('Erro ao carregar canais!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    # Filtrar adultos e separadores (stream_id inválido ou zero)
    data = [ch for ch in data
            if not e_adulto(ch.get('name', ''))
            and int(ch.get('stream_id', 0) or 0) > 0]

    xbmcplugin.setPluginCategory(HANDLE, cat_nome)
    for ch in data:
        nome       = ch.get('name', 'Canal')
        stream_id  = str(ch.get('stream_id', ''))
        logo       = (ch.get('stream_icon', '') or ICON).replace(' ', '%20')
        ext        = ch.get('container_extension', 'ts')
        stream_url = '{}/live/{}/{}/{}.{}'.format(host, u, p, stream_id, ext)

        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': logo, 'fanart': ''})
        li.setProperty('IsPlayable', 'true')
        li.setInfo('video', {'title': nome, 'mediatype': 'video', 'playcount': 0, 'overlay': 0})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'play', 'url': stream_url, 'nome': nome, 'logo': logo}), li, False)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def mostrar_vod(srv_idx, cat_id, cat_nome):
    from servers import SERVIDORES
    srv  = SERVIDORES[int(srv_idx)]
    host = srv['host']
    u    = srv['username']
    p    = srv['password']

    data = api_json('{}/player_api.php?username={}&password={}&action=get_vod_streams&category_id={}'.format(host, u, p, cat_id))
    if not data:
        notificar('Erro ao carregar filmes!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    # Filtrar adultos e separadores
    data = [i for i in data
            if not e_adulto(i.get('name', ''))
            and int(i.get('stream_id', 0) or 0) > 0]

    xbmcplugin.setPluginCategory(HANDLE, cat_nome)
    for item in data:
        nome       = item.get('name', 'Filme')
        stream_id  = str(item.get('stream_id', ''))
        logo       = (item.get('stream_icon', '') or ICON).replace(' ', '%20')
        ext        = item.get('container_extension', 'mp4')
        stream_url = '{}/movie/{}/{}/{}.{}'.format(host, u, p, stream_id, ext)

        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': logo, 'fanart': ''})
        li.setProperty('IsPlayable', 'true')
        li.setInfo('video', {'title': nome, 'mediatype': 'movie', 'playcount': 0, 'overlay': 0})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'play', 'url': stream_url, 'nome': nome, 'logo': logo}), li, False)

    xbmcplugin.setContent(HANDLE, 'movies')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def mostrar_series(srv_idx, cat_id, cat_nome):
    from servers import SERVIDORES
    srv  = SERVIDORES[int(srv_idx)]
    host = srv['host']
    u    = srv['username']
    p    = srv['password']

    data = api_json('{}/player_api.php?username={}&password={}&action=get_series&category_id={}'.format(host, u, p, cat_id))
    if not data:
        notificar('Erro ao carregar séries!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    xbmcplugin.setPluginCategory(HANDLE, cat_nome)
    for serie in data:
        nome      = serie.get('name', 'Série')
        series_id = str(serie.get('series_id', ''))
        logo      = serie.get('cover', '') or ICON

        li = xbmcgui.ListItem(nome)
        li.setArt({'thumb': logo, 'fanart': logo or FANART})
        li.setInfo('video', {'title': nome, 'mediatype': 'tvshow', 'playcount': 0, 'overlay': 0})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'series_eps', 'srv_idx': srv_idx, 'series_id': series_id, 'serie_nome': nome}), li, True)

    xbmcplugin.setContent(HANDLE, 'tvshows')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def mostrar_episodios(srv_idx, series_id, serie_nome):
    from servers import SERVIDORES
    srv  = SERVIDORES[int(srv_idx)]
    host = srv['host']
    u    = srv['username']
    p    = srv['password']

    data = api_json('{}/player_api.php?username={}&password={}&action=get_series_info&series_id={}'.format(host, u, p, series_id))
    if not data:
        notificar('Erro ao carregar episódios!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    xbmcplugin.setPluginCategory(HANDLE, serie_nome)
    episodes = data.get('episodes', {})

    for season_num in sorted(episodes.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        for ep in episodes[season_num]:
            titulo     = 'S{}E{} - {}'.format(str(season_num).zfill(2), str(ep.get('episode_num','')).zfill(2), ep.get('title','Episódio'))
            ep_id      = str(ep.get('id', ''))
            logo       = ep.get('info', {}).get('movie_image', '') or ICON
            ext        = ep.get('container_extension', 'mp4')
            stream_url = '{}/series/{}/{}/{}.{}'.format(host, u, p, ep_id, ext)

            li = xbmcgui.ListItem(titulo)
            li.setArt({'thumb': logo, 'fanart': ''})
            li.setProperty('IsPlayable', 'true')
            li.setInfo('video', {'title': titulo, 'mediatype': 'episode', 'playcount': 0, 'overlay': 0})
            xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'play', 'url': stream_url, 'nome': titulo, 'logo': logo}), li, False)

    xbmcplugin.setContent(HANDLE, 'episodes')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  M3U por URL
# ════════════════════════════════════════════════════════

def parse_m3u(conteudo):
    canais = []
    linhas = conteudo.splitlines()
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        if linha.startswith('#EXTINF'):
            ch = {'nome': 'Canal', 'url': '', 'grupo': 'Sem Grupo', 'logo': ''}
            def atr(padrao, src=linha):
                m = re.search(padrao, src, re.IGNORECASE)
                return m.group(1).strip() if m else ''
            ch['logo']  = atr(r'tvg-logo="([^"]*)"')
            grupo_raw   = atr(r'group-title="([^"]*)"')
            ch['grupo'] = grupo_raw.strip() if grupo_raw.strip() else 'Sem Grupo'
            virgula     = linha.rfind(',')
            ch['nome']  = linha[virgula + 1:].strip() if virgula != -1 else 'Canal'
            i += 1
            while i < len(linhas):
                prox = linhas[i].strip()
                if prox and not prox.startswith('#'):
                    ch['url'] = prox
                    break
                i += 1
            if ch['url']:
                canais.append(ch)
        i += 1
    return canais

def mostrar_grupos_m3u(srv_idx):
    from servers import SERVIDORES
    srv = SERVIDORES[int(srv_idx)]

    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, 'A carregar lista M3U...')
    dp.update(20)
    conteudo = http_get(srv['url'])
    if not conteudo:
        dp.close()
        notificar('Erro ao carregar a lista M3U!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    dp.update(60, 'A processar...')
    canais = parse_m3u(conteudo)
    canais = [ch for ch in canais if not e_adulto(ch['grupo']) and not e_adulto(ch['nome'])]

    grupos = {}
    ordem  = []
    for ch in canais:
        g = ch['grupo']
        if g not in grupos:
            grupos[g] = []
            ordem.append(g)
        grupos[g].append(ch)

    dp.update(100)
    dp.close()

    xbmcplugin.setPluginCategory(HANDLE, srv['nome'])
    for g in ordem:
        thumb = grupos[g][0].get('logo') or ICON
        li = xbmcgui.ListItem(g)
        li.setArt({'thumb': thumb, 'fanart': ''})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'm3u_canais', 'srv_idx': srv_idx, 'grupo': g}), li, True)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)

def mostrar_canais_m3u(srv_idx, grupo):
    from servers import SERVIDORES
    srv      = SERVIDORES[int(srv_idx)]
    conteudo = http_get(srv['url'])
    if not conteudo:
        notificar('Erro ao carregar lista M3U!')
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
        return

    canais = [ch for ch in parse_m3u(conteudo) if ch['grupo'] == grupo]

    xbmcplugin.setPluginCategory(HANDLE, grupo)
    for ch in canais:
        logo = ch.get('logo') or ICON
        li   = xbmcgui.ListItem(ch['nome'])
        li.setArt({'thumb': logo, 'fanart': ''})
        li.setProperty('IsPlayable', 'true')
        li.setInfo('video', {'title': ch['nome'], 'mediatype': 'video', 'playcount': 0, 'overlay': 0})
        xbmcplugin.addDirectoryItem(HANDLE, url_para({'acao': 'play', 'url': ch['url'], 'nome': ch['nome'], 'logo': logo}), li, False)

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


# ════════════════════════════════════════════════════════
#  REPRODUÇÃO via F4mTester
# ════════════════════════════════════════════════════════

def _aplicar_buffer_settings():
    """
    Força advancedsettings.xml com valores óptimos para IPTV ao vivo.
    buffermode=1  — buffer de rede activo
    32MB buffer   — absorve picos e interrupções do servidor
    factor=4.0    — preenche buffer 4x mais rápido que o bitrate
    """
    import xbmcvfs
    dest = xbmcvfs.translatePath('special://userdata/advancedsettings.xml')
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<advancedsettings>\n'
        '  <network>\n'
        '    <buffermode>1</buffermode>\n'
        '    <cachemembuffersize>33554432</cachemembuffersize>\n'
        '    <readbufferfactor>4.0</readbufferfactor>\n'
        '  </network>\n'
        '</advancedsettings>\n'
    )
    try:
        with xbmcvfs.File(dest, 'w') as f:
            f.write(xml)
        import xbmc
        xbmc.log('[OnTV] advancedsettings.xml aplicado (32MB buffer, factor 4.0)', xbmc.LOGINFO)
    except Exception as e:
        import xbmc
        xbmc.log('[OnTV] Erro ao aplicar advancedsettings.xml: ' + str(e), xbmc.LOGWARNING)


def reproduzir(stream_url, nome='', logo=''):
    """
    Reprodução directa via player nativo do Kodi.
    Escreve o stream_url num ficheiro temp para o serviço de background poder reiniciar.
    """
    _aplicar_buffer_settings()
    log('Play: ' + stream_url)

    # Guardar info do stream para o serviço de background
    import json, os
    import xbmcvfs
    info = {'url': stream_url, 'nome': nome, 'logo': logo or ICON}
    tmp  = xbmcvfs.translatePath('special://temp/ontv_stream.json')
    try:
        with open(tmp, 'w') as f:
            json.dump(info, f)
    except Exception:
        pass

    icon = logo or ICON
    li = xbmcgui.ListItem(nome, path=stream_url)
    li.setArt({'thumb': icon, 'icon': icon, 'fanart': '', 'poster': icon})
    li.setProperty('IsPlayable', 'true')
    li.setInfo('video', {'title': nome, 'mediatype': 'video', 'playcount': 0, 'overlay': 0})

    url_lower = stream_url.lower().split('?')[0]

    if '.m3u8' in url_lower:
        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_type', 'hls')
        li.setProperty('mimetype', 'application/x-mpegURL')
        # Buffer/cache para HLS — reduz travamentos
        li.setProperty('inputstream.adaptive.stream_selection_type', 'ask')
        li.setProperty('network.bandwidth', '0')
        log('Player: adaptive (.m3u8)')
    elif url_lower.endswith('.mp4'):
        li.setProperty('mimetype', 'video/mp4')
        log('Player: nativo (.mp4)')
    else:
        li.setProperty('inputstream', 'inputstream.ffmpegdirect')
        li.setProperty('inputstream.ffmpegdirect.stream_mode', 'ffmpegdirect')
        li.setProperty('inputstream.ffmpegdirect.open_mode', 'curl')
        li.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
        li.setProperty('mimetype', 'video/mp2t')
        # Buffer extra para streams .ts — 10MB para absorver picos de rede
        li.setProperty('inputstream.ffmpegdirect.read_chunk_size', '131072')
        li.setProperty('network.buffer_factor', '4.0')
        log('Player: nativo IsLive (.ts)')

    # Configurações globais de rede e buffer para todos os tipos de stream
    li.setProperty('network.curlcachebytes',  '20971520')   # 20 MB cache rede
    li.setProperty('network.bandwidth',       '0')          # sem limite de largura de banda
    li.setProperty('network.readtimeout',     '60')         # 60s timeout de leitura
    li.setProperty('network.connecttimeout',  '10')         # 10s timeout de ligação

    xbmcplugin.setResolvedUrl(HANDLE, True, li)

def reproduzir_stalker(srv_idx, stalker_tipo, cmd, nome='', logo=''):
    from servers import SERVIDORES
    srv        = SERVIDORES[int(srv_idx)]
    stream_url = stalker_create_link(srv['host'], srv['mac'], stalker_tipo, cmd)
    log('Stalker stream final: ' + stream_url)
    reproduzir(stream_url, nome, logo)


# ════════════════════════════════════════════════════════
#  ROTEADOR
# ════════════════════════════════════════════════════════

def run():
    params = dict(parse_qsl(sys.argv[2][1:]))
    acao   = params.get('acao', 'main')
    log('Acao=' + acao)

    # Se o player está activo e não é uma acção de play, ignorar chamada
    # Evita que o Kodi recarregue listas em background durante reprodução
    if acao not in ('play', 'stalker_play'):
        player = xbmc.Player()
        if player.isPlaying():
            log('A reproduzir — ignorar acao=' + acao)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
            return

    # Sinalizar ao serviço para não reiniciar APENAS quando o utilizador
    # abre um novo canal intencionalmente
    if acao in ('play', 'stalker_play'):
        import xbmcvfs as _vfs
        _stop = _vfs.translatePath('special://temp/ontv_user_stop.flag')
        try:
            with open(_stop, 'w') as _f:
                _f.write('1')
        except Exception:
            pass

    if   acao == 'main':           mostrar_principal()
    elif acao == 'tipos':          mostrar_tipos(params['srv_idx'])
    # Xtream
    elif acao == 'live_cats':      mostrar_categorias(params['srv_idx'], 'live_cats')
    elif acao == 'vod_cats':       mostrar_categorias(params['srv_idx'], 'vod_cats')
    elif acao == 'series_cats':    mostrar_categorias(params['srv_idx'], 'series_cats')
    elif acao == 'live_canais':    mostrar_live(params['srv_idx'], params.get('cat_id',''), params.get('cat_nome',''))
    elif acao == 'vod_canais':     mostrar_vod(params['srv_idx'], params.get('cat_id',''), params.get('cat_nome',''))
    elif acao == 'series_canais':  mostrar_series(params['srv_idx'], params.get('cat_id',''), params.get('cat_nome',''))
    elif acao == 'series_eps':     mostrar_episodios(params['srv_idx'], params.get('series_id',''), params.get('serie_nome',''))
    # Stalker/MAC
    elif acao == 'stalker_live':   mostrar_canais_stalker(params['srv_idx'], 'itv',    params.get('cat_id','*'), params.get('cat_nome',''))
    elif acao == 'stalker_vod':    mostrar_canais_stalker(params['srv_idx'], 'vod',    params.get('cat_id','*'), params.get('cat_nome',''))
    elif acao == 'stalker_series': mostrar_canais_stalker(params['srv_idx'], 'series', params.get('cat_id','*'), params.get('cat_nome',''))
    elif acao == 'stalker_play':   reproduzir_stalker(params['srv_idx'], params.get('stalker_tipo','itv'), params.get('cmd',''), params.get('nome',''), params.get('logo',''))
    # M3U
    elif acao == 'm3u_canais':     mostrar_canais_m3u(params['srv_idx'], params.get('grupo',''))
    # Play
    elif acao == 'play':           reproduzir(params.get('url',''), params.get('nome',''), params.get('logo',''))
    else:                          mostrar_principal()
