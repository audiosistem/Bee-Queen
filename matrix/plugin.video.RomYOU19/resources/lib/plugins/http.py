from ..plugin import Plugin
from ..DI import DI
import urllib,zipfile
class http(Plugin):
    name = "http"
    priority = 0

    def get_list(self, url):
       
        if ".zip" in url:
            filehandle, _ = urllib.request.urlretrieve(url)
            zip_file_object = zipfile.ZipFile(filehandle, 'r')
            first_file = zip_file_object.namelist()[0]
            file = zip_file_object.open(first_file)
            content = file.read().decode('utf-8')
            
            return content
        elif url.startswith("http"):
            try:
                return DI.session.get(url).text
            except : return ("<<<< http plugin failed >>>>")
