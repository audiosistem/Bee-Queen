# -*- coding: utf-8 -*-
"""
	luc_kodi Add-on
	Application keys of luc_kodi for TMDb, Fanart.tv, OMDb, Trakt, SIMKL,
	MDBList, PunchPlay, OpenSubtitles and TheTVDB, used until a user enters
	their own in Settings.
"""

from base64 import b64decode

_SALT = b'apoyotech/luc_kodi'
_BLOBS = {
	'tmdb': 'B04wCin0652qHmBGYdm83K4WeQpmgq+aswNyKzXP8s0=',
	'fanart': 'BEkzWCbav8+kG3xHJMHrzKZIfnA7y/fDvVN+ETzO9dM=',
	'omdb': 'BUgxXnj2vA==',
	'trakt_id': 'A0hnBSfV67GnB3BQd/TrwKhUaFc41fDevUd+QGyNrtvhl0YtHHrHhIzjR2sXP8m9gaNdPhg5h/SR8FocTyfCoQ==',
	'trakt_secret': 'VE0wAimKu8msDz9ZZNHu3eZOLyo6yvWE+VF5WTfu+pC9oB4vDjDLooeoAHQEJND3jYINOkd6mPTG+ABJQzaK+w==',
	'simkl': 'A01lAzvNtZitSXdfK8rhu6RVPgk6kqucuV94AmPb7s66u0c3B3z35YC0VGJIIcTiirJLfRYn3vaB6Qt9RQ/c+A==',
	'simkl_v2': 'VB1hAyONv7WgVnZWcv7rxflSc1A40O3fuF93FTyJ+oi1lUZ7TXnOgICxR2oOO8vrwK5YJhw40fLB+1ZNTnPDpQ==',
	'mdblist': 'MB0RBW6F5u/zDwVPErCj8us7MWsxp/XK1QkuaTnI/J/NzTc8ASO9pQ==',
	'punchplay': 'EQw2YW2RttWmAWBAa8bp3vkfO0l5ievR7297FQ==',
	'opensubs': 'Aww/a0uCveXmMANcYJ3jxvsYFUJFgb3l+QQiVmPa/KE=',
	'tvdb': 'Vk5mXSj27si2UWoZNsfq2a4XZwVmh/qH5wcgLjTH8I/u7lh9',
}
_cache = {}


def get(name):
	"""Plain value of one application credential, or '' if unknown."""
	try:
		if name not in _cache:
			salt = _SALT + name.encode()
			raw = b64decode(_BLOBS[name])
			_cache[name] = bytes(b ^ salt[(i * 7) % len(salt)] ^ ((i * 31) & 0xff) for i, b in enumerate(raw)).decode('ascii')
		return _cache[name]
	except Exception:
		return ''
