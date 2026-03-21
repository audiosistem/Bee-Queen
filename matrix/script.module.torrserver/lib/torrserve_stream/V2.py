class V2toV1Adapter(object):

    key_equivalents = {
        'TorrentStatusString': 'stat_string',
        'TorrentStatus': 'stat',
        'Length': 'torrent_size',
        'Files': 'file_stats',
        'FileStats': 'file_stats',
    }

    deprecated = {
        'UploadSpeed':  0,
    }

    def __init__(self, v2):
        self.v2 = v2

    def __str__(self):
        return self.v2.__str__()

    def get(self, key, def_val=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return def_val

    def _get_v2_key(self, key):
        v2key = key[0].lower()
        for ch in key[1:]:
            if ch.isupper():
                v2key += '_' + ch.lower()
            else:
                v2key += ch
        return v2key

    def __contains__(self, item):
        if item in self.v2:
            return True

        ke = self.key_equivalents
        if item in ke and ke[item] in self.v2:
            return True

        return self._get_v2_key(item) in self.v2

    def __getitem__(self, key):
        if key in self.v2:
            return self.v2[key]

        if key in self.deprecated:
            return self.deprecated[key]

        def get_element(value):
            if isinstance(value, dict):
                return self.__class__(value)
            elif isinstance(value, list):
                return [ get_element(item) for item in value ]
            return value

        def get_value(v2key):
            if v2key in self.v2:
                value = self.v2[v2key]
                return get_element(value)
            else:
                raise KeyError

        if key in ['Files', 'file_stats', 'FileStats']:
            try:
                files = [ V2toV1FilesAdapter(item) for item in self.v2['file_stats'] ]
                return files
            except (KeyError, TypeError):
                return []

        ke = self.key_equivalents
        if key in ke:
            try:
                return get_value(ke[key])
            except KeyError:
                pass

        v2key = self._get_v2_key(key)

        return get_value(v2key)


class V2toV1ListAdapter(V2toV1Adapter):
    key_equivalents = {
        #'TorrentStatusString': 'stat_string',
        #'TorrentStatus': 'stat',
        'Length': 'torrent_size',
        'Files': 'file_stats',
        'FileStats': 'file_stats',
        #'Name': 'title',
    }

class V2toV1FilesAdapter(V2toV1Adapter):
    key_equivalents = {
        'Name': 'path',
        'Size': 'length',
    }
