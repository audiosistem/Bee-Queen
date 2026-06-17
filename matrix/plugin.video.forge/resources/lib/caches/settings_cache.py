# -*- coding: utf-8 -*-
import json
import os

from caches.base_cache import connect_database
from modules import kodi_utils

_SCHEMA_PATH = os.path.join(
	os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
	"data",
	"settings_schema.json",
)
_SCHEMA_CACHE = None


class SettingsCache:
	def get(self, setting_id):
		try:
			dbcon = connect_database("settings_db")
			setting_id = setting_id.replace("forge.", "")
			setting_value = dbcon.execute("SELECT setting_value from settings WHERE setting_id = ?", (setting_id,)).fetchone()[0]
			self.set_memory_cache(setting_id, setting_value)
		except:
			setting_value = None
		return setting_value

	def remove_setting(self, setting_id):
		dbcon = connect_database("settings_db")
		dbcon.execute("DELETE FROM settings WHERE setting_id = ?", (setting_id,))

	def get_many(self, settings_list):
		try:
			dbcon = connect_database("settings_db")
			results = dict(
				dbcon.execute(
					"SELECT setting_id, setting_value FROM settings WHERE setting_id in (%s)" % (", ".join("?" for _ in settings_list)), settings_list
				).fetchall()
			)
			return results
		except:
			results = {}
		return results

	def get_all(self):
		dbcon = connect_database("settings_db")
		try:
			all_settings = dict(dbcon.execute("SELECT setting_id, setting_value FROM settings").fetchall())
		except:
			all_settings = {}
		return all_settings

	def set(self, setting_id, setting_value=None):
		dbcon = connect_database("settings_db")
		setting_info = default_setting_values(setting_id)
		setting_type, setting_default = setting_info["setting_type"], setting_info["setting_default"]
		if setting_value is None:
			setting_value = setting_default
		dbcon.execute("INSERT OR REPLACE INTO settings VALUES (?, ?, ?, ?)", (setting_id, setting_type, setting_default, setting_value))
		self.set_memory_cache(setting_id, setting_value)
		if setting_type == "action" and "settings_options" in setting_info:
			name_setting_id = "%s_name" % setting_id
			name_setting_value = setting_info["settings_options"][setting_value]
			dbcon.execute("INSERT OR REPLACE INTO settings VALUES (?, ?, ?, ?)", (name_setting_id, "name", "", name_setting_value))
			self.set_memory_cache(name_setting_id, name_setting_value)

	def set_many(self, settings_list):
		dbcon = connect_database("settings_db")
		dbcon.executemany("INSERT OR REPLACE INTO settings VALUES (?, ?, ?, ?)", settings_list)
		for item in settings_list:
			self.set_memory_cache(item[0], item[3] or item[2])

	def set_memory_cache(self, setting_id, setting_value):
		kodi_utils.set_property("forge.%s" % setting_id, setting_value)

	def delete_memory_cache(self, setting_id):
		kodi_utils.clear_property("forge.%s" % setting_id)

	def setting_info(self, setting_id):
		d_settings = default_settings()
		return [i for i in d_settings if i["setting_id"] == setting_id][0]

	def clean_database(self):
		try:
			dbcon = connect_database("settings_db")
			dbcon.execute("VACUUM")
			return True
		except:
			return False


settings_cache = SettingsCache()


def set_setting(setting_id, value):
	settings_cache.set(setting_id, value)


def get_setting(setting_id, fallback=""):
	return kodi_utils.get_property(setting_id) or settings_cache.get(setting_id) or fallback


def get_many(settings_list):
	return settings_cache.get_many(settings_list)


def sync_settings(params={}):
	silent = params.get("silent", "true") == "true"
	insert_list = []
	insert_list_append = insert_list.append
	currentsettings = settings_cache.get_all()
	# J4: a brand-new install has an empty settings DB at this point (the
	# rows below are inserted from the schema). Signal the migration runner
	# (OnUpdateChanges, which runs next this boot) so it stamps the current
	# version and skips migrations instead of running them against already-
	# correct fresh state. Per-boot window prop; cleared by ClearStaleProperties.
	if not currentsettings:
		kodi_utils.set_property("forge.fresh_install", "true")
	d_settings = default_settings()
	defaultsettings_ids = [i["setting_id"] for i in d_settings]
	defaultsettings_names = [i["setting_id"] for i in d_settings if "settings_options" in i]
	defaultsettings_ids.extend(["%s_name" % i for i in defaultsettings_names])
	try:
		c_settings = currentsettings.items()
		obsoletesettings_ids = [k for k, v in c_settings if k not in defaultsettings_ids]
		if obsoletesettings_ids:
			for item in obsoletesettings_ids:
				settings_cache.remove_setting(item)
	except:
		pass
	if currentsettings:
		c_settings = currentsettings.items()
		for k, v in c_settings:
			settings_cache.set_memory_cache(k, v)
	for item in d_settings:
		setting_id = item["setting_id"]
		if setting_id in currentsettings:
			continue
		setting_type = item["setting_type"]
		setting_default = item["setting_default"]
		if setting_type == "action" and "settings_options" in item:
			name_default = item["settings_options"][setting_default]
			insert_list_append(("%s_name" % setting_id, "name", name_default, name_default))
		insert_list_append((setting_id, setting_type, setting_default, setting_default))
	if insert_list:
		settings_cache.set_many(insert_list)
	settings_cache.clean_database()
	if not silent:
		kodi_utils.notification("Settings Cache Remade")


def set_default(setting_ids):
	if not isinstance(setting_ids, list):
		setting_ids = [setting_ids]
	if not kodi_utils.confirm_dialog(text="Are You Sure?", ok_label="Yes", cancel_label="No", default_control=11):
		return
	for setting_id in setting_ids:
		try:
			set_setting(setting_id, default_setting_values(setting_id)["setting_default"])
		except:
			pass


def set_boolean(params):
	boolean_dict = {"true": "false", "false": "true"}
	setting = params["setting_id"]
	set_setting(setting, boolean_dict[get_setting("forge.%s" % setting)])


def set_string(params):
	current_value = get_setting("forge.%s" % params["setting_id"])
	current_value = current_value.replace("empty_setting", "")
	new_value = kodi_utils.kodi_dialog().input("", defaultt=current_value)
	if not new_value and not kodi_utils.confirm_dialog(text="Enter Blank Value?", ok_label="Yes", cancel_label="Re-Enter Value", default_control=11):
		return set_string(params)
	set_setting(params["setting_id"], new_value or "empty_setting")


def set_numeric(params):
	setting_id = params["setting_id"]
	setting_values = default_setting_values(setting_id)
	values_get = setting_values.get
	min_value, max_value = int(values_get("min_value", "0")), int(values_get("max_value", "100000000000000"))
	negative_included = any((n < 0 for n in [min_value, max_value]))
	if negative_included:
		multiplier_values = [("Positive(+)", 1), ("Negative(-)", -1)]
		list_items = [{"line1": item[0]} for item in multiplier_values]
		kwargs = {"items": json.dumps(list_items), "narrow_window": "true", "heading": "Will this be a positive or negative number?"}
		multiplier = kodi_utils.select_dialog(multiplier_values, **kwargs)
	else:
		multiplier = None
	new_value = kodi_utils.kodi_dialog().input("Range [B]%s - %s[/B]." % (min_value, max_value), type=1)
	if not new_value:
		return
	if multiplier:
		new_value = str(int(float(new_value) * multiplier[1]))
	if int(new_value) < min_value or int(new_value) > max_value:
		kodi_utils.ok_dialog(text="Please Choose Between the Range [B]%s - %s[/B]." % (min_value, max_value))
		return set_numeric(params)
	set_setting(setting_id, new_value)


def set_path(params):
	setting_id = params["setting_id"]
	browse_mode = int(default_setting_values(setting_id)["browse_mode"])
	new_value = kodi_utils.kodi_dialog().browse(browse_mode, "", "", defaultt=get_setting("forge.%s" % setting_id))
	set_setting(setting_id, new_value)


def set_from_list(params):
	setting_id = params["setting_id"]
	settings_options = default_setting_values(setting_id)["settings_options"].items()
	settings_list = [(v, k) for k, v in settings_options]
	new_value = kodi_utils.select_dialog(settings_list, **{"items": json.dumps([{"line1": item[0]} for item in settings_list]), "narrow_window": "true"})
	if not new_value:
		return
	setting_value = new_value[1]
	set_setting(setting_id, setting_value)


def set_source_folder_path(params):
	setting_id = params["setting_id"]
	current_setting = get_setting("forge.%s" % setting_id)
	if current_setting not in (None, "None", ""):
		if kodi_utils.confirm_dialog(text="Enter Blank Value?", ok_label="Yes", cancel_label="Re-Enter Value", default_control=11):
			return set_setting(setting_id, "None")
	return set_path(params)


def restore_setting_default(params):
	silent = params.get("silent", "false") == "true"
	if not silent and not kodi_utils.confirm_dialog():
		return
	try:
		setting_id = params["setting_id"]
		setting_default = default_setting_values(setting_id)["setting_default"]
		set_setting(setting_id, setting_default)
	except:
		if not silent:
			kodi_utils.ok_dialog(text="Error restoring default setting")


def default_setting_values(setting_id):
	if "forge." in setting_id:
		setting_id = setting_id.replace("forge.", "")
	d_settings = default_settings()
	return next((i for i in d_settings if i["setting_id"] == setting_id), None)


def default_settings():
	"""Return the canonical schema of every Forge setting.

	The schema is declared in ``resources/data/settings_schema.json``; this
	loader strips section markers (``{"_section": "..."}`` entries kept for
	readability in the JSON).
	"""
	global _SCHEMA_CACHE
	if _SCHEMA_CACHE is None:
		with open(_SCHEMA_PATH, encoding="utf-8") as f:
			_SCHEMA_CACHE = [e for e in json.load(f) if "_section" not in e]
	return _SCHEMA_CACHE
