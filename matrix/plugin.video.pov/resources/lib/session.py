import urllib3
import requests
from requests.adapters import HTTPAdapter, Retry

retry = urllib3.util.Retry(total=None, status=1, status_forcelist=(429, 502, 503, 504), backoff_factor=1)
http = urllib3.PoolManager(maxsize=10, retries=retry, timeout=urllib3.util.Timeout(connect=3.05, read=6.05))
http.headers.update(urllib3.util.make_headers(keep_alive=True, accept_encoding=True))

class TimeoutSession(requests.Session):
	CUSTOM_ERRORS = requests.exceptions.ConnectionError, requests.exceptions.Timeout
	def __init__(self, timeout=None):
		requests.Session.__init__(self)
		self.timeout = timeout or (3.05, 6.05)

	def request(self, *args, **kwargs):
		kwargs.setdefault('timeout', self.timeout)
		return requests.Session.request(self, *args, **kwargs)

session = TimeoutSession()

