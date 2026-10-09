"""
	Fenomscrapers Module
"""

from random import choice
import requests
from magneto.modules.dom_parser import parseDOM


class TimeoutSession(requests.Session):
	CUSTOM_ERRORS = requests.exceptions.ConnectionError, requests.exceptions.Timeout
	def __init__(self, timeout=None):
		requests.Session.__init__(self)
		self.timeout = timeout or (3.05, 6.05)

	def request(self, *args, **kwargs):
		kwargs.setdefault('timeout', self.timeout)
		return requests.Session.request(self, *args, **kwargs)

session = TimeoutSession()

def randomagent():
	RAND_UAS = [
		'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
		'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/116.0',
		'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
		'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
		'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.82',
		'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188',
	]
	return choice(RAND_UAS)

