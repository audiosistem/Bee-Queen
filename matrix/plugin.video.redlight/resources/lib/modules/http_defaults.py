# -*- coding: utf-8 -*-
"""Shared HTTP defaults for meta account APIs (Trakt, Simkl, MDBList, PunchPlay)."""
from hashlib import sha256
from requests.adapters import Retry

# Single request wait for meta sync / list / scrobble calls.
META_API_TIMEOUT = 20

# Bundled tokens are scoped to the installing addon id (hash compare, not a string match).
_H = '8e84859c7d61979587c6ab81194fdbc9b9c49b8c02521690cd44eb496988efdf'
_T = frozenset((
	'0f108c5be6d22d4a9d55e8f049e7046fc9fe46722f930230e0b37e95323463dc',
	'269daf09b2665e33622eebeb9d58712b7cea4edeac83460175530b51ae6f5e20',
	'5dbbda943ae00547fefc48852263eb5c7adf8ff0cd539ebfd19a057222799053',
	'662b6d8b9d4cf782c5bfe3b72b8a1aa4b3756b84874e0539415cb0953ee04be6',
	'7a81013bf027e1e7ae5eea8e97af3aa16a64bb4caca6908b3c301c3d085b19f4',
	'81d3511cad24f03bcfa85da1742b6d3ff5a50e8a7bb2f514b14c2f19de727963',
	'86cad6febdcdae657ae2bfa2d0d94648739116dec18e1822a8e315dd4683f502',
	'96f0afe8cd97320d13cb68db7c7ab5acdfb24840259daad1bf0d53e41128f7fe',
	'bff2515d75563cd495795017672de4fa15cfd01ae0dab5cad43a664d50ec89dc',
	'fdc5db497bb621f86747453fdab276baba6294f5515ce2a70a00a05a2ab35954',
))
# Sealed bundled credentials. Only unseal for the official addon id.
_BLOBS = {
	'simkl.client': '859568b119aeebb7aba0d10bd068f0e19969fde20e6a9e0a0cec5ebea95440f987c338e64cf4eee2fff0d20ed76ca0b09c38fde90d3ecf5854b108b9a8004cac',
	'trakt.client': '80c66ce419a1bce5aaa2d75ed33ba6e09b3bf6e85d3e99090cb60beaac0517fbd6c031eb4fa3bab7f8a0840ad738f2e7cd65aee35a3b9c0c5ee65ae3ab0717ac',
	'trakt.secret': '84c43fb44cf4bee7f8abd20dd73dfbe6c865fae10a3bcb5b5db009efa20344a881c36ab64eaeb8b6fbf4d608d369a7b7c96afeb50e3e980e5be601eeac0017aa',
	'tmdb_api': 'd2c66bb448a6b8b6acf4d20b843aa1e39c3faeb25b3f9b0e08e601b8ab5610ad',
	'tmdb.lists_read_token': 'd68f43ba18d1ecbcd6fbfe74b2708bb3b33485e84569d07305b16f8bf37a1dd5dbbb4e9817dbe594aacbce6b8a50a8d89710889f0355fe73058c429be0781efbdfbb73be13dbd89bf2dfdd749443afb79407a6985d41fd6c1a9842b1aa7a30decbbb4ae649d8db84eadbda73d653abcbcb14a5845e55fd685f8c0a8fae6c0ed1dbbb738b4edbc89ce1dfde7c9047a8e58504a6981845c77707b70b98f6560dd685a1709812f5c8b9fff1d96b8f5081c899118c9b5956f17317b46fe3ef7c1ef0cb9058fc48e6d6b4d4c4ce6a9e2796cc9a6f9c930767f9662ea7618dea540cfce6c1458833ccc385fdf5fe4dde60b5',
	'mdblist.client': 'f9b053910ad3c68cdfe6c44ba061f6b58d188aa11966ec5235af548ad60d1cd5e1c23cb80bf2eb9f',
	'punchplay.client': 'c3866a8d48a6e9e1aaf1870b8339f1e4cc6aabe15a3e9d0808b100e9',
	'playback.opensubs_api_key': 'f4867cb002d0bae5eef8ec67bf7e90ee8c65fc990e64904a08a75eb0d9730dd6',
	'rpdb_api': 'c7c624b408f3eaf8ebe2d05f',
}
_SIMKL_ALT = '82c76fb11ca1b8b6a9aa8c09de68f4e39f68acb0096e9b5c5cb75dbcac5741a8d2c13bb71ef5eae2fba28c58d13fa6b6cd6ef6b55b6fcf0e5db40fbeab0c4cfd'
SHIPPED_SETTING_IDS = frozenset(_BLOBS)
_host_ok = None
_unsealed = {}

def _running_addon_id():
	try:
		import xbmcaddon
		return xbmcaddon.Addon().getAddonInfo('id') or ''
	except Exception:
		return ''

def _official_host():
	global _host_ok
	if _host_ok is None:
		_host_ok = sha256(_running_addon_id().encode('utf-8')).hexdigest() == _H
	return _host_ok

def scoped_token(value):
	"""Pass through values unless they are bundled tokens on a foreign invoker."""
	if _official_host():
		return value
	text = '' if value is None else str(value)
	if text in ('', 'empty_setting'):
		return value
	if sha256(text.encode('utf-8')).hexdigest() in _T:
		return ''
	return value

def _unseal(blob_hex):
	"""XOR blob with the running addon id. Foreign ids yield empty, not a usable key."""
	if blob_hex in _unsealed:
		return _unsealed[blob_hex]
	out = ''
	host = _running_addon_id()
	if _official_host() and host:
		try:
			raw = bytes.fromhex(blob_hex)
			material = sha256((_H + host).encode('utf-8')).digest()
			text = bytes(b ^ material[i % len(material)] for i, b in enumerate(raw)).decode('ascii')
			if sha256(text.encode('utf-8')).hexdigest() in _T:
				out = text
		except Exception:
			out = ''
	if out or _host_ok is not None:
		_unsealed[blob_hex] = out
	return out

def shipped_setting(setting_id):
	blob = _BLOBS.get(setting_id)
	if not blob: return ''
	return _unseal(blob)

def shipped_simkl_client():
	return shipped_setting('simkl.client')

def shipped_simkl_alt():
	return _unseal(_SIMKL_ALT)

def shipped_simkl_ids():
	return tuple(i for i in (shipped_simkl_client(), shipped_simkl_alt()) if i)

def meta_status_retry():
	"""Retry flaky server responses only — not connect/read failures (airplane/offline)."""
	return Retry(
		total=2,
		connect=0,
		read=0,
		status=2,
		backoff_factor=0.5,
		status_forcelist=(429, 500, 502, 503, 504),
		allowed_methods=frozenset({'GET', 'HEAD', 'OPTIONS', 'PUT', 'DELETE', 'POST', 'PATCH'}),
	)
