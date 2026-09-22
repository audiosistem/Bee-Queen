"""
	gearsscrapers Project
"""

# Per-user Telegram login for the providers/torrents/telegrambot.py source
# -- ported from Starfleet's resources/lib/telegram_auth.py, same
# shared-app-identity API_ID/API_HASH (registered once at my.telegram.org
# under the app name "Starfleet" -- identifies the app to Telegram, not
# any individual account) so each gears installer links their OWN
# Telegram account and searches run under their own account rather than
# one shared login.
#
# QR-scan login (same "Log in by QR Code" mechanism Telegram Desktop/Web
# use), auto-refreshed for as long as the dialog is open. Real finding
# from testing this live (in Starfleet, same underlying library and
# credentials): Telegram's QR login token expires in well under a minute
# -- a first live attempt that spent too long just transferring the QR
# image to a phone for scanning failed with the token already expired
# ("auth expired"); a second attempt with the phone's scanner already
# open before the QR was generated succeeded immediately. So this can't
# just show one QR and wait -- it actively regenerates the QR (new token
# + new image swapped into the same dialog) every time a wait() call
# times out.
#
# Real bug also confirmed and fixed here, same root cause as Starfleet's:
# Kodi runs plugin actions off the main thread, and constructing a bare
# TelegramClient there crashes with "ValueError: set_wakeup_fd only works
# in main thread" deep inside asyncio's implicit event-loop lookup --
# Windows' DEFAULT event loop (ProactorEventLoop) does self-pipe/signal
# setup that's hard-restricted to the process's real main thread. The fix
# is forcing the alternative SelectorEventLoop instead, which has no such
# setup -- confirmed live (in Starfleet) on an actual background thread,
# including across multiple concurrent threads at once (matching how
# sources() calls run here too). ensure_selector_event_loop() below must
# be called before every single TelegramClient() construction, in both
# this module and providers/torrents/telegrambot.py.

import asyncio
import sys
import xbmcgui
from gearsscrapers.modules import control

API_ID = 39892797
API_HASH = '628d934e42a2663cc64025a2852a9f1d'

_QR_WAIT_S = 25       # comfortably under the token's real expiry (see
                      # module docstring) so a refresh always lands
                      # before Telegram would have rejected the old one.
_QR_MAX_TOTAL_S = 300  # 5 minutes of the user's own time.


def _session_path():
	profile = control.dataPath
	if not control.existsPath(profile):
		control.makeDirs(profile)
	return control.joinPath(profile, 'telegram')


def is_paired():
	return control.existsPath(_session_path() + '.session')


def unpair():
	p = _session_path() + '.session'
	try:
		if control.existsPath(p):
			control.deleteFile(p)
	except Exception:
		from gearsscrapers.modules import log_utils
		log_utils.error()


def ensure_selector_event_loop():
	"""Call before constructing a TelegramClient on any thread that isn't
	guaranteed to be the process main thread (Kodi's plugin actions never
	are) -- see this module's own docstring for why. Safe to call more
	than once per thread; only replaces the loop the first time.

	The probe below must catch a bare Exception, not just RuntimeError:
	if a loop was never set for this thread yet, asyncio.get_event_loop()
	itself is exactly the call that auto-creates the crashing
	ProactorEventLoop and raises the real bug's ValueError -- that
	failure means "no usable loop exists yet", same as the probe simply
	finding none, so either way the fix below is to create and set our
	own."""
	if sys.platform != 'win32':
		return
	try:
		loop = asyncio.get_event_loop()
		if loop.is_closed():
			loop = None
	except Exception:
		loop = None
	if not isinstance(loop, asyncio.SelectorEventLoop):
		new_loop = asyncio.SelectorEventLoop()
		asyncio.set_event_loop(new_loop)


class _QRDialog(xbmcgui.WindowDialog):
	"""Minimal QR display -- gears has no shared qr_dialog.py precedent
	(unlike Starfleet), so this is a compact from-scratch version. No
	opaque background panel (Starfleet's own version needed a bundled
	skin texture for that, which gears has no equivalent of) -- purely
	cosmetic difference, doesn't affect function."""

	def __init__(self, qr_path):
		super(_QRDialog, self).__init__()
		self._cancelled = False
		self._qr_image = xbmcgui.ControlImage(490, 140, 300, 300, qr_path)
		self.addControl(self._qr_image)
		self._heading = xbmcgui.ControlLabel(390, 90, 500, 40, 'Link Telegram Account',
			alignment=2, font='font30', textColor='FFFFFFFF')
		self.addControl(self._heading)
		self._instr = xbmcgui.ControlLabel(390, 450, 500, 60,
			'Telegram app > Settings > Devices > Link Desktop Device, then scan',
			alignment=2, textColor='FFB0BEC8')
		self.addControl(self._instr)
		self._status = xbmcgui.ControlLabel(390, 510, 500, 40, 'Waiting for you to scan...',
			alignment=2, textColor='FFB0BEC8')
		self.addControl(self._status)

	def onAction(self, action):
		if action.getId() in (10, 92):  # ACTION_PREVIOUS_MENU, ACTION_NAV_BACK
			self._cancelled = True
			self.close()

	def update(self, message):
		self._status.setLabel(message)

	def set_qr(self, qr_path):
		try:
			self._qr_image.setImage(qr_path)
		except Exception:
			pass

	def iscanceled(self):
		return self._cancelled


def _make_qr(url, filename):
	try:
		import pyqrcode
		qr_path = control.transPath('special://temp/%s' % filename)
		pyqrcode.create(url).png(qr_path, scale=6)
		return qr_path
	except Exception:
		from gearsscrapers.modules import log_utils
		log_utils.error()
		return ''


def pair_with_telegram():
	"""Bound to the telegram_pair action (see lib/default.py). QR scan,
	auto-refreshed for as long as the dialog stays open."""
	try:
		from telethon.sync import TelegramClient
		from telethon.errors import SessionPasswordNeededError
	except Exception:
		from gearsscrapers.modules import log_utils
		log_utils.error()
		control.notification(message='Telegram login unavailable (see gearsscrapers log)')
		return

	ensure_selector_event_loop()
	client = TelegramClient(_session_path(), API_ID, API_HASH)
	qr_dlg = None
	try:
		client.connect()
		if client.is_user_authorized():
			control.notification(message='Telegram already linked')
			return

		qr_login = client.qr_login()
		qr_path = _make_qr(qr_login.url, 'gearsscrapers_telegram_qr.png')
		if not qr_path:
			control.notification(message='Could not generate QR code (see gearsscrapers log)')
			return
		qr_dlg = _QRDialog(qr_path)
		qr_dlg.show()

		waited = 0
		linked = False
		while waited < _QR_MAX_TOTAL_S:
			if qr_dlg.iscanceled():
				return
			try:
				# qr_login.wait() is a real coroutine even under
				# telethon.sync (confirmed live in Starfleet's own
				# testing -- telethon.sync's synchronous patching
				# doesn't extend to QRLoginManager, only to
				# TelegramClient's own methods), so it needs the
				# client's own loop to actually run it.
				client.loop.run_until_complete(qr_login.wait(_QR_WAIT_S))
				linked = True
				break
			except SessionPasswordNeededError:
				qr_dlg.close()
				qr_dlg = None
				password = control.dialog.input('Enter your Telegram 2FA password',
					option=xbmcgui.ALPHANUM_HIDE_INPUT)
				if password:
					client.sign_in(password=password)
					linked = True
				break
			except Exception:
				# This round's token expired before being scanned --
				# get a fresh one and swap it into the same dialog.
				waited += _QR_WAIT_S
				if waited >= _QR_MAX_TOTAL_S:
					break
				client.loop.run_until_complete(qr_login.recreate())
				new_qr_path = _make_qr(qr_login.url, 'gearsscrapers_telegram_qr.png')
				if new_qr_path:
					qr_dlg.set_qr(new_qr_path)
				qr_dlg.update('QR refreshed - waiting... (%ds)' % waited)

		if qr_dlg:
			qr_dlg.close()
			qr_dlg = None

		if linked:
			me = client.get_me()
			name = me.username or me.first_name or 'your account'
			control.notification(message='Telegram linked as %s' % name)
		else:
			control.notification(message='Telegram linking timed out')
	except Exception:
		from gearsscrapers.modules import log_utils
		log_utils.error()
		control.notification(message='Telegram login failed (see gearsscrapers log)')
	finally:
		if qr_dlg:
			qr_dlg.close()
		client.disconnect()


def show_status():
	"""Bound to the telegram_status action."""
	if is_paired():
		if control.yesnoDialog('Telegram account is linked.\n\nUnlink?'):
			unpair()
			control.notification(message='Telegram unlinked')
	else:
		control.dialog.ok(control.addonName(), 'Not linked yet. Use "Link Telegram Account" in Settings.')
