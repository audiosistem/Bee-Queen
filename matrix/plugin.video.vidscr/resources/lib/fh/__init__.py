"""File-host site scrapers.

Each module in this folder implements ONE indexer site and exposes:

    def resolve(media_type, tmdb_id, imdb_id, title=None, year=None,
                season=None, episode=None) -> list[dict]:
        '''Return a list of file-host stream candidates for the title.'''

Every returned stream MUST set:
    needs_resolveurl  = True
    proto             = 'HOSTER'
    source_site       = '<pretty name of site>'   # shown in picker
    host_name         = '<hoster name>'           # filemoon / voe / etc.
    label             = '[<quality> <ext>] <host> via <site>'

Optional fields that improve the picker display:
    filename, filesize, quality

The aggregator in ``../filehosts.py`` iterates every module here in
parallel; a slow or dead site never blocks the others.
"""
