# -*- coding: utf-8 -*-

try:
    from sqlite3 import dbapi2 as database
except:
    from pysqlite2 import dbapi2 as database

from resources.lib.modules import control


_MENU_VIEW_DEFAULTS = {'skin.estuary': '55', 'skin.confluence': '500', 'skin.aeon.nox.silvo': '50'}
_ESTUARY_CONTENT_DEFAULTS = {'': '55', 'movies': '500', 'tvshows': '500', 'seasons': '500', 'episodes': '55'}
_KNOWN_VIEW_IDS = frozenset({'50', '51', '52', '53', '54', '55', '500', '501', '502', '503', '504', '505', '507', '508', '509', '510', '511', '512', '513', '514', '515', '516', '517', '518', '519', '520', '521', '522', '523', '524', '525', '526', '527', '528', '529', '530', '531', '532', '533', '534', '535', '536', '537', '538', '539', '540', '541', '542', '543', '544', '545', '546', '547', '548', '549', '550'})


def addView(content):
    try:
        skin = control.skin
        view_id = control.getCurrentViewId()
        if not _valid_view_id(view_id):
            control.infoDialog('Could not detect view mode. Change the view, then try again.', sound=True, icon='WARNING')
            return
        record = (skin, content, str(view_id))
        control.makeFile(control.dataPath)
        dbcon = database.connect(control.viewsFile)
        dbcur = dbcon.cursor()
        dbcur.execute("CREATE TABLE IF NOT EXISTS views (""skin TEXT, ""view_type TEXT, ""view_id TEXT, ""UNIQUE(skin, view_type)"");")
        dbcur.execute("DELETE FROM views WHERE skin = '%s' AND view_type = '%s'" % (record[0], record[1]))
        dbcur.execute("INSERT INTO views Values (?, ?, ?)", record)
        dbcon.commit()
        viewName = control.infoLabel('Container.Viewmode') or ('View %s' % view_id)
        skinName = control.addon(skin).getAddonInfo('name')
        skinIcon = control.addon(skin).getAddonInfo('icon')
        control.infoDialog(viewName, heading=skinName, sound=True, icon=skinIcon)
        control.execute('Container.Refresh')
    except:
        return


def normalize_view_content(content):
    if content in (None, '', 'menus'):
        return control.MENU_FOLDER_CONTENT
    return content


def view_content_param(content):
    if content == control.MENU_FOLDER_CONTENT:
        return 'menus'
    return content


def _expected_container_content(content):
    if content in (None, ''):
        return ''
    return str(content)


def _container_content_matches(content):
    return (control.infoLabel('Container.Content') or '') == _expected_container_content(content)


def _content_visibility(content):
    if content in (None, ''):
        return 'Container.Content()'
    return 'Container.Content(%s)' % content


def _container_ready(content):
    if not (_container_content_matches(content) or control.condVisibility(_content_visibility(content))):
        return False
    if not control.condVisibility('Integer.IsGreater(Container.NumItems,0)'):
        return False
    if control.condVisibility('Window.IsActive(busydialog)'):
        return False
    return True


def _resolve_view_id(view_id, content):
    return str(view_id)


def _valid_view_id(view_id):
    view_id = str(view_id or '').strip()
    if not view_id:
        return False
    if view_id in _KNOWN_VIEW_IDS:
        return True
    try:
        return int(view_id) >= 50
    except:
        return False


def _lookup_saved_view(content):
    try:
        skin = control.skin
        dbcon = database.connect(control.viewsFile)
        dbcur = dbcon.cursor()
        for view_type in (content, 'addons') if content == control.MENU_FOLDER_CONTENT else (content,):
            dbcur.execute("SELECT * FROM views WHERE skin = '%s' AND view_type = '%s'" % (skin, view_type))
            row = dbcur.fetchone()
            if row and row[2] and _valid_view_id(row[2]):
                return _resolve_view_id(row[2], content)
    except:
        pass
    return None


def _menu_view_default():
    skin = (control.skin or '').lower()
    for key, view_id in _MENU_VIEW_DEFAULTS.items():
        if key in skin:
            return view_id
    return None


def _content_view_default(content):
    skin = (control.skin or '').lower()
    if 'estuary' in skin:
        return _ESTUARY_CONTENT_DEFAULTS.get(content)
    if content == control.MENU_FOLDER_CONTENT:
        return _menu_view_default()
    return None


def _resolve_view_for_content(content, apply_default=True):
    view = _lookup_saved_view(content)
    if view:
        return view
    if apply_default:
        if content == control.MENU_FOLDER_CONTENT:
            return _menu_view_default()
        return _content_view_default(content)
    return None


def _current_view_id():
    return control.getCurrentViewId() or ''


def setView(content, apply_default=True):
    """Apply saved view modes; browse menus also share one skin default so layout stays consistent."""
    control.sleep(100)
    view = _resolve_view_for_content(content, apply_default=apply_default)
    if not view:
        return
    view = str(_resolve_view_id(view, content))
    for _ in range(0, 200):
        if not _container_ready(content):
            control.sleep(50)
            continue
        if str(_current_view_id()) == view:
            return
        control.execute('Container.SetViewMode(%s)' % view)
        control.sleep(150)
        return


def setMenuView():
    setView(control.MENU_FOLDER_CONTENT)


def endMenuDirectory(handle):
    """Finish a browse/menu folder with consistent layout across all addon menus."""
    control.content(handle, control.MENU_FOLDER_CONTENT)
    control.directory(handle, cacheToDisc=False)
    setMenuView()


def deleteView():
    try:
        control.makeFile(control.dataPath)
        dbcon = database.connect(control.viewsFile)
        dbcur = dbcon.cursor()
        for t in ['views']:
            try:
                dbcur.execute("DROP TABLE IF EXISTS %s" % t)
                dbcur.execute("VACUUM")
                dbcon.commit()
            except:
                pass
    except:
        pass
