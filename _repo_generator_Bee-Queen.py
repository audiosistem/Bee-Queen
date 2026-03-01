import os
import shutil
import hashlib
import zipfile
import re
from xml.etree import ElementTree

SCRIPT_VERSION = 8
# Am inclus si prefixele comune pentru module in scanare
KODI_VERSIONS = ["krypton", "leia", "matrix", "nexusrepo", "omega", "repo", "all"]
IGNORE = [
    ".git", ".github", ".gitignore", ".DS_Store", "thumbs.db", 
    ".idea", "venv", "__pycache__", "bin", ".pytest_cache"
]
MAIN_REPO_ID = "Bee-Queen"

def _setup_colors():
    color = os.system("color")
    console = 0
    if os.name == 'nt':
        from ctypes import windll
        k = windll.kernel32
        console = k.SetConsoleMode(k.GetStdHandle(-11), 7)
    return color == 1 or console == 1

_COLOR_ESCAPE = "\x1b[{}m"
_COLORS = {"black": "30", "red": "31", "green": "4;32", "yellow": "3;33", "blue": "34", "magenta": "35", "cyan": "1;36", "grey": "37", "endc": "0"}
_SUPPORTS_COLOR = _setup_colors()

def color_text(text, color):
    return '{}{}{}'.format(_COLOR_ESCAPE.format(_COLORS[color]), text, _COLOR_ESCAPE.format(_COLORS["endc"])) if _SUPPORTS_COLOR else text

def convert_bytes(num):
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0: return "%3.1f %s" % (num, x)
        num /= 1024.0

class Generator:
    def __init__(self, release):
        self.release_path = release
        self.zips_path = os.path.join(self.release_path, "zips")
        
        if not os.path.exists(self.zips_path):
            os.makedirs(self.zips_path)

        self._remove_binaries()
        
        addons_xml_path = os.path.join(self.zips_path, "addons.xml")
        md5_path = os.path.join(self.zips_path, "addons.xml.md5")

        if self._generate_addons_file(addons_xml_path):
            print("Successfully updated {}".format(color_text(addons_xml_path, 'yellow')))
            if self._generate_md5_file(addons_xml_path, md5_path):
                print("Successfully updated {}".format(color_text(md5_path, 'yellow')))

    def _remove_binaries(self):
        """ Curăță fișierele reziduale înainte de ambalare """
        for parent, dirnames, filenames in os.walk(self.release_path):
            for fn in filenames:
                if fn.lower().endswith(("pyo", "pyc")):
                    try: os.remove(os.path.join(parent, fn))
                    except: pass
            for d in list(dirnames):
                if d.lower() in ["__pycache__", ".pytest_cache"]:
                    try: shutil.rmtree(os.path.join(parent, d))
                    except: pass

    def _create_zip(self, folder, addon_id, version):
        addon_folder = os.path.join(self.release_path, folder)
        zip_folder = os.path.join(self.zips_path, addon_id)
        if not os.path.exists(zip_folder):
            os.makedirs(zip_folder)

        zip_name = "{0}-{1}.zip".format(addon_id, version)
        final_zip = os.path.join(zip_folder, zip_name)
        
        # Curățare versiuni vechi
        for f in os.listdir(zip_folder):
            if f.endswith(".zip") and f != zip_name:
                try: os.remove(os.path.join(zip_folder, f))
                except: pass

        if not os.path.exists(final_zip):
            with zipfile.ZipFile(final_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
                # Calculăm calea relativă corectă pentru a include folderul rădăcină în ZIP
                base_dir = os.path.dirname(os.path.abspath(addon_folder))
                for root, dirs, files in os.walk(addon_folder):
                    dirs[:] = [d for d in dirs if d not in IGNORE]
                    for f in files:
                        if any(f.startswith(i) for i in IGNORE): continue
                        full_path = os.path.join(root, f)
                        archive_name = os.path.relpath(full_path, base_dir)
                        z.write(full_path, archive_name)
            
            print("Zip created: {} ({})".format(color_text(addon_id, 'cyan'), color_text(version, 'green')))

    def _copy_meta_files(self, addon_id, target_folder):
        """ Copiază addon.xml, icon.png, fanart.png în folderul de zips pentru afișare în Kodi """
        src_path = os.path.join(self.release_path, addon_id)
        meta_files = ["addon.xml", "icon.png", "fanart.png", "changelog.txt"]
        
        for file in meta_files:
            s_file = os.path.join(src_path, file)
            if os.path.exists(s_file):
                shutil.copy(s_file, os.path.join(target_folder, file))

    def _generate_addons_file(self, addons_xml_path):
        # Colectăm toate folderele care au addon.xml (inclusiv script.module.*)
        folders = [d for d in os.listdir(self.release_path) 
                  if os.path.isdir(os.path.join(self.release_path, d)) 
                  and d != "zips" and not d.startswith(".")
                  and os.path.exists(os.path.join(self.release_path, d, "addon.xml"))]

        root = ElementTree.Element("addons")
        
        for addon in folders:
            try:
                xml_path = os.path.join(self.release_path, addon, "addon.xml")
                with open(xml_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                
                addon_xml_node = ElementTree.fromstring(content)
                root.append(addon_xml_node)
                
                # Generăm ZIP și copiem meta-datele
                self._create_zip(addon, addon_xml_node.get('id'), addon_xml_node.get('version'))
                self._copy_meta_files(addon, os.path.join(self.zips_path, addon_xml_node.get('id')))
                
                # Dacă e repo-ul principal, îl punem și în root
                if addon_xml_node.get('id') == MAIN_REPO_ID:
                    self._update_root_files(addon_xml_node.get('id'), addon_xml_node.get('version'))

            except Exception as e:
                print(f"Error processing {addon}: {e}")

        # Salvăm addons.xml
        tree = ElementTree.ElementTree(root)
        tree.write(addons_xml_path, encoding="utf-8", xml_declaration=True)
        return True

    def _update_root_files(self, addon_id, version):
        """ Menține o copie a zip-ului repo-ului în rădăcină pentru instalare ușoară """
        zip_name = f"{addon_id}-{version}.zip"
        src = os.path.join(self.zips_path, addon_id, zip_name)
        if os.path.exists(src):
            shutil.copy(src, zip_name)
            # Ștergem versiunile vechi din root
            for f in os.listdir("."):
                if f.startswith(addon_id) and f.endswith(".zip") and f != zip_name:
                    os.remove(f)

    def _generate_md5_file(self, xml_path, md5_path):
        with open(xml_path, "rb") as f:
            m = hashlib.md5(f.read()).hexdigest()
        with open(md5_path, "w") as f:
            f.write(m)
        return True

if __name__ == "__main__":
    for release in [r for r in KODI_VERSIONS if os.path.exists(r)]:
        print(f"\nProcessing version: {color_text(release, 'magenta')}")
        Generator(release)
    print("\n" + "="*40)
    print(color_text("GATA! Acum poți face Push pe GitHub.", "green"))
    print("="*40)
    input("\nENTER pentru închidere...")