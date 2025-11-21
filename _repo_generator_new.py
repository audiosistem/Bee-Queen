""" 
    Put this script in the root folder of your repo and it will
    zip up all addon folders, create a new zip in your zips folder
    and then update the md5 and addons.xml file
"""

import re
import os
import shutil
import hashlib
import zipfile
from xml.etree import ElementTree

# Lista versiunilor suportate
KODI_VERSIONS = ["krypton", "leia", "matrix", "repo"]

# Foldere si fisiere de ignorat
IGNORE = [
    ".git",
    ".github",
    ".gitignore",
    ".DS_Store",
    "thumbs.db",
    ".idea",
    "venv",
    "_repo_generator.py",
    ".vscode"
]

def color_text(text, color):
    """
    Adauga culori textului pentru consola.
    """
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "end": "\033[0m"
    }
    return f"{colors.get(color, '')}{text}{colors['end']}"

class Generator:
    """
    Generates a new addons.xml file from each addons addon.xml file
    and a new addons.xml.md5 hash file. Must be run from the root of
    the checked-out repo.
    """

    def __init__(self, release):
        self.release_path = release
        self.zips_path = os.path.join(self.release_path, "zips")

        if not os.path.exists(self.zips_path):
            os.makedirs(self.zips_path)

        print(color_text(f"\n--- Processing Folder: {release} ---", "blue"))
        self._remove_binaries()
        self._generate_addons_file()
        self._generate_md5_file()
        # Nou: Generam index.html pentru navigare
        self._generate_index_files()

    def _remove_binaries(self):
        """
        Removes any and all compiled Python files before operations.
        """
        print(color_text("Cleaning up binaries...", "yellow"))
        for parent, dirnames, filenames in os.walk(self.release_path):
            for fn in filenames:
                if fn.lower().endswith("pyo") or fn.lower().endswith("pyc"):
                    compiled = os.path.join(parent, fn)
                    try:
                        os.remove(compiled)
                        print(color_text(f"  - Deleted file: {fn}", "red"))
                    except:
                        pass
            for dir in dirnames:
                if "pycache" in dir.lower():
                    compiled = os.path.join(parent, dir)
                    try:
                        shutil.rmtree(compiled)
                        print(color_text(f"  - Deleted folder: {dir}", "red"))
                    except:
                        pass

    def _create_zip(self, addon_id, version):
        """
        Creates a zip file in the zips directory for the given addon.
        """
        addon_folder = os.path.join(self.release_path, addon_id)
        zip_folder = os.path.join(self.zips_path, addon_id)
        if not os.path.exists(zip_folder):
            os.makedirs(zip_folder)

        final_zip = os.path.join(zip_folder, "{0}-{1}.zip".format(addon_id, version))
        
        if not os.path.exists(final_zip):
            print(color_text(f"Creating package: {addon_id} v{version}", "green"))
            zip = zipfile.ZipFile(final_zip, "w", compression=zipfile.ZIP_DEFLATED)
            root_len = len(os.path.dirname(os.path.abspath(addon_folder)))

            for root, dirs, files in os.walk(addon_folder):
                for i in IGNORE:
                    if i in dirs:
                        dirs.remove(i)
                    for f in files:
                        if f.startswith(i):
                            files.remove(f)

                archive_root = os.path.abspath(root)[root_len:]

                for f in files:
                    fullpath = os.path.join(root, f)
                    archive_name = os.path.join(archive_root, f)
                    print(color_text(f"    + Zipping: {f}", "cyan"))
                    zip.write(fullpath, archive_name, zipfile.ZIP_DEFLATED)

            zip.close()
        else:
            print(color_text(f"Skipping zip (exists): {addon_id} v{version}", "yellow"))

    def _copy_meta_files(self, addon_id, addon_folder):
        """
        Copy the addon.xml and relevant art files.
        """
        tree = ElementTree.parse(os.path.join(self.release_path, addon_id, "addon.xml"))
        root = tree.getroot()

        copyfiles = ["addon.xml"]
        for ext in root.findall("extension"):
            if ext.get("point") == "xbmc.addon.metadata":
                assets = ext.find("assets")
                if assets is None:
                    continue
                for art in assets:
                    if art.text:
                        copyfiles.append(os.path.normpath(art.text))

        src_folder = os.path.join(self.release_path, addon_id)
        for file in copyfiles:
            addon_path = os.path.join(src_folder, file)
            zips_path = os.path.join(addon_folder, file)
            asset_path = os.path.split(zips_path)[0]
            
            if not os.path.exists(asset_path):
                os.makedirs(asset_path)

            try:
                shutil.copy(addon_path, zips_path)
                print(color_text(f"    > Copying asset: {file}", "blue"))
            except Exception as e:
                pass

    def _generate_addons_file(self):
        """
        Generates addons.xml.
        """
        print(color_text("Generating addons.xml...", "yellow"))
        addons_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n'

        folders = [
            i
            for i in os.listdir(self.release_path)
            if os.path.isdir(os.path.join(self.release_path, i))
            and i != "zips"
            and not i.startswith(".")
            and os.path.exists(os.path.join(self.release_path, i, "addon.xml"))
        ]

        for addon in folders:
            _path = os.path.join(self.release_path, addon, "addon.xml")
            try:
                xml_lines = open(_path, "r", encoding="utf-8").read().splitlines()
                addon_xml = ""

                ver_found = False
                for line in xml_lines:
                    if line.find("<?xml") >= 0:
                        continue
                    if 'version="' in line and not ver_found:
                        version = re.compile('version="(.+?)"').findall(line)[0]
                        ver_found = True
                    addon_xml += line.rstrip() + "\n"
                addons_xml += addon_xml.rstrip() + "\n\n"

                self._create_zip(addon, version)
                self._copy_meta_files(addon, os.path.join(self.zips_path, addon))
            except Exception as e:
                print(color_text("Excluding {0}: {1}".format(_path, e), "red"))

        addons_xml = addons_xml.strip() + "\n</addons>\n"
        self._save_file(
            addons_xml.encode("utf-8"),
            file=os.path.join(self.zips_path, "addons.xml"),
            decode=True,
        )
        print(color_text(f"Successfully updated addons.xml", "green"))

    def _generate_md5_file(self):
        try:
            m = hashlib.md5(
                open(os.path.join(self.zips_path, "addons.xml"), "r", encoding="utf-8")
                .read()
                .encode("utf-8")
            ).hexdigest()
            self._save_file(m, file=os.path.join(self.zips_path, "addons.xml.md5"))
            print(color_text(f"Successfully updated addons.xml.md5", "green"))
        except Exception as e:
            print(color_text("An error occurred creating addons.xml.md5 file!\n{0}".format(e), "red"))

    def _generate_index_files(self):
        """
        Genereaza fisierul index.html in fiecare folder pentru ca Kodi sa poata naviga.
        """
        print(color_text("Generating index.html files for directory browsing...", "yellow"))
        
        # Mergem recursiv doar in folderul zips
        for root, dirs, files in os.walk(self.zips_path):
            # Construim continutul HTML
            html_content = "<html><body><h1>Directory listing</h1><hr><ul>"
            
            # Link catre folderul parinte
            html_content += '<li><a href="../">..</a></li>'
            
            # Linkuri catre foldere
            for d in dirs:
                html_content += f'<li><a href="{d}/">{d}/</a></li>'
            
            # Linkuri catre fisiere
            for f in files:
                if f != "index.html":
                    html_content += f'<li><a href="{f}">{f}</a></li>'
            
            html_content += "</ul><hr></body></html>"
            
            try:
                with open(os.path.join(root, "index.html"), "w", encoding="utf-8") as index_file:
                    index_file.write(html_content)
            except Exception as e:
                print(color_text(f"Error creating index.html in {root}: {e}", "red"))

    def _save_file(self, data, file, decode=False):
        try:
            if decode:
                open(file, "w", encoding="utf-8").write(data.decode("utf-8"))
            else:
                open(file, "w").write(data)
        except Exception as e:
            print(color_text("An error occurred saving {0} file!\n{1}".format(file, e), "red"))


# --- Generare Index pentru ROOT ---
def generate_root_index():
    """
    Creaza un index.html in radacina proiectului care pointeaza catre folderele versiunilor.
    """
    print(color_text("\n--- Generating Root Index ---", "blue"))
    root_dirs = [d for d in KODI_VERSIONS if os.path.exists(d)]
    
    html_content = "<html><body><h1>Bee-Queen Repository</h1><hr><ul>"
    for d in root_dirs:
        html_content += f'<li><a href="{d}/zips/">{d}/</a></li>'
    html_content += "</ul><hr></body></html>"
    
    try:
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print(color_text("Successfully created root index.html", "green"))
    except Exception as e:
        print(color_text(f"Error creating root index: {e}", "red"))


if __name__ == "__main__":
    for release in [r for r in KODI_VERSIONS if os.path.exists(r)]:
        Generator(release)
    
    # Generam si indexul principal
    generate_root_index()

    print("\n" + "="*40)
    print(color_text("Procesul complet s-a încheiat.", "green"))
    print("="*40)
    input("\nApasă tasta ENTER pentru a închide fereastra...")