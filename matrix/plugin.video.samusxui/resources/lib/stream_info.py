"""Contract intern pentru URL, headere Kodi și expirarea linkului semnat."""
from dataclasses import dataclass, field
import time
import urllib.parse


@dataclass(frozen=True)
class StreamInfo:
    url: str
    headers: dict = field(default_factory=dict)
    raw_headers: str = ''
    expires_at: float = 0.0

    @classmethod
    def parse(cls, value):
        base, separator, raw = (value or '').partition('|')
        headers = {}
        if separator:
            for pair in raw.split('&'):
                key, equals, header_value = pair.partition('=')
                if equals and key:
                    # Valorile Kodi sunt brute; '+' poate aparține UA/tokenului.
                    headers[urllib.parse.unquote(key)] = urllib.parse.unquote(header_value)
        expiry = 0.0
        try:
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(base).query)
            expiry = float(query['s'][0]) + float(query['e'][0])
        except Exception:
            pass
        return cls(base, headers, raw if separator else '', expiry)

    def is_expired(self, margin=30.0):
        return bool(self.expires_at and time.time() + margin >= self.expires_at)

    @property
    def is_hls(self):
        return '.m3u8' in self.url.lower()

    def kodi_value(self):
        return self.url + (('|' + self.raw_headers) if self.raw_headers else '')

    def apply(self, list_item):
        if self.is_hls:
            list_item.setMimeType('application/vnd.apple.mpegurl')
            list_item.setContentLookup(False)
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            list_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
            if self.raw_headers:
                list_item.setProperty('inputstream.adaptive.stream_headers', self.raw_headers)
                list_item.setProperty('inputstream.adaptive.manifest_headers', self.raw_headers)
            list_item.setPath(self.url)
        else:
            list_item.setPath(self.kodi_value())
        return list_item
