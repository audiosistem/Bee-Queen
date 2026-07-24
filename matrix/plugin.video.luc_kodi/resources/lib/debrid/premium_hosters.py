"""
	luc_kodi Add-on
"""

# Debrid service endpoints this add-on resolves through.
# NOTE: the large cocoscrapers-inherited file-host domain list was removed in
# v1.0.40. It was never consulted by any scraper in this add-on (every source
# here is torrent/debrid based, so the host whitelist was passed around but
# never read) and it carried many dead and unrelated domains. Kept minimal and
# meaningful: only the debrid services this add-on actually supports.
hostprDict = ('real-debrid.com', 'alldebrid.com', 'premiumize.me', 'torbox.app')

sourcecfDict = ('maxrls', 'rapidmoviez', 'rlsbb', 'scenerls', 'extratorrent', 'limetorrents', 'torrentgalaxy')
