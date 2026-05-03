Free Flow Kodi Addon
====================
Author: Chains
Version: 1.0.0

A Kodi video addon that streams Movies, TV Shows, WWE, Documentaries, Kids
content and more by reading the public directory feeds at thechains24.com.

Features
--------
- Browses the full directory tree (recursively follows nested .txt feeds).
- Plays items via ResolveURL (script.module.resolveurl).
- Falls back to TMDB to enrich missing posters / fanart / plots.
- Multi-source items show a "Choose source" dialog.

Dependencies (installed by Kodi automatically)
----------------------------------------------
- script.module.resolveurl
- script.module.requests

TMDB API key is bundled. The addon does not host any media; it only links
to publicly listed sources.

Install
-------
In Kodi: Settings -> Add-ons -> Install from zip file -> select
plugin.video.freeflow-1.0.0.zip
