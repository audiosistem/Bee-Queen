# -*- coding: utf-8 -*-
"""Versioned migration dispatch (J4).

Pure orchestration with no Kodi (`xbmc.*`) imports so it stays unit-testable —
`service.py` itself can't be imported in tests because it runs
`ForgeMonitor().waitForAbort()` at module load. The migration callables and the
ordered ``MIGRATIONS`` registry live in `service.py`; this module is handed the
registry plus dependency-injected ``run``/``stamp``/``log`` seams.

Every migration MUST be idempotent (a re-run is a no-op once applied). The
framework leans on this for pre-J4 upgraders re-running the existing migrations
once and for same-version group retry after a partial failure.
"""

from itertools import groupby

from modules.utils import version_tuple


def select_pending(migrations, last_run, current):
	"""Migrations to run, ascending by version: ``last_run < version <= current``."""
	last_t, cur_t = version_tuple(last_run), version_tuple(current)
	ordered = sorted(migrations, key=lambda m: version_tuple(m[0]))
	return [(v, fn) for (v, fn) in ordered if last_t < version_tuple(v) <= cur_t]


def run_migrations(migrations, *, current_version, stored_version, is_fresh_install, stamp, run, log):
	"""Run pending migrations and stamp the new migration version.

	``run(fn)`` invokes a migration, ``stamp(v)`` persists the migration
	version, ``log(msg)`` logs. Returns the version that ended up stamped.

	Version-GROUP-aware failure isolation: migrations are processed in
	ascending version order, grouped by version. The stamp only advances past a
	version once EVERY migration at that version has succeeded. If any migration
	in a group raises, we stamp the last fully-completed version (strictly below
	the failing group) and stop — so the whole failing group retries next boot.
	This is why migrations must be idempotent: a succeeded sibling in a
	partially-failed group re-runs on retry.

	Up-to-date installs skip the stamp write entirely (no redundant DB write
	every boot).
	"""
	# Developer safety net: a migration keyed above the shipped version is
	# silently excluded by select_pending (it would corrupt forward-only
	# semantics to run it early). Surface it so a forgotten addon.xml bump is
	# visible in the log instead of a migration that never runs.
	unreachable = sorted({v for v, _ in migrations if version_tuple(v) > version_tuple(current_version)})
	if unreachable:
		log("WARNING migrations keyed above current version %s will not run until addon.xml is bumped: %s" % (current_version, ", ".join(unreachable)))

	if is_fresh_install and not stored_version:
		if stored_version != current_version:
			stamp(current_version)
		log("fresh install — stamped %s, no migrations run" % current_version)
		return current_version

	last_run = stored_version or "0.0.0"
	pending = select_pending(migrations, last_run, current_version)
	if not pending:
		if stored_version != current_version:
			stamp(current_version)  # first boot on a new version with nothing to do
		return current_version

	safe = last_run  # highest version whose entire group completed
	for version, group in groupby(pending, key=lambda m: m[0]):
		try:
			for item in group:
				run(item[1])
		except Exception as e:
			log("migration %s failed: %s" % (version, e))
			if safe != stored_version:
				stamp(safe)
			return safe
		safe = version

	stamp(current_version)
	log("migrated %s -> %s" % (last_run, current_version))
	return current_version
