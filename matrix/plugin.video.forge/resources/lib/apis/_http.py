# -*- coding: utf-8 -*-
"""Shared HTTP constants for the `apis/` clients.

Centralizes the four timeout tiers that were previously inlined as
5/10/20/30s literals across the seven API modules (D7). Picking a tier
should be by *behavior*, not by guessed seconds:

- TIMEOUT_FAST (5s): single low-latency lookups (e.g. IMDb suggest).
- TIMEOUT_MEDIUM (10s): paginated GraphQL or list endpoints where 5s is too
  tight but the standard tier is overkill.
- TIMEOUT_STANDARD (20s): the workhorse — debrid/TMDb/OMDb/AllDebrid/Torbox.
- TIMEOUT_LONG (30s): auth or large-payload endpoints (Trakt extended=full
  list pulls, OAuth refresh).

The 90s outlier on `tmdblist_api`'s session.request is intentional — slow
list-write paths — and stays inline.
"""

TIMEOUT_FAST = 5
TIMEOUT_MEDIUM = 10
TIMEOUT_STANDARD = 20
TIMEOUT_LONG = 30
