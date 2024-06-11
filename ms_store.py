import logging
import os
import re
import html
import json
import hashlib
import requests
import packaging.version

from datetime import datetime
from xml.dom import minidom
from requests import Session

class Store:
    path = os.path.dirname(os.path.abspath(__file__))
    session = Session()
    session.verify = False
    aria2 = None
    # check if release UpdateID is the same as the beta one
    app_config = {}
    release_id = ""
    data_path = ""
    package_family_name = ""
    catagory_id = ""
    user_token = ""

    release_type_map = {
        "Stable": "retail",
        "Windows Insider": "WIF",
        "Beta": "WIF"
    }
    file_extension_map = {
        "appx": "Appx",
        "appxbundle": "AppxBundle",
        "eappx": "EAppx",
        "eappxbundle": "EAppxBundle",
        "msix": "Msix",
        "msixbundle": "Msixbundle"
    }
    arch_order = {
        "neutral": 0,
        "x64": 1,
        "x86": 2,
        "arm64": 3,
        "arm": 4
    }

    def setup_config(self, config, data_path=None):
        self.app_config = config
        self.data_path = config["DataPath"] if data_path is None else data_path
        self.catagory_id = config["CataGoryID"]
        self.package_family_name = config["PackageFamilyName"]

    def error_output(self, e):
        print(f"Error: {e}\n")
        logging.basicConfig(format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s',
            level=logging.ERROR,
            filename='test.log',
            filemode='a')

    def update_token(self):
        with open(self.tokens_file, "r") as f:
            self.tokens = json.load(f)
            f.close()
        self.user_token = self.tokens["Store"]["AccessToken"]["Jwt"]

    def get_url(self, user, UpdateID, RevisionNumber, ReleaseType):
        with open(os.path.join(self.path, "xml", "FE3FileUrl.xml"), "r") as f:
            FE3_file_content = f.read()
            f.close()
        try:
            out = self.session.post(
                'https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx/secured',
                data=FE3_file_content.format(user, UpdateID, RevisionNumber, ReleaseType),
                headers={'Content-Type': 'application/soap+xml; charset=utf-8'}
            )
            if len(out.text) < 1500:
                raise Exception(f"The response is invaild in get_url() from UpdateID {UpdateID}.\n")
        except Exception as e:
            self.error_output(e)
            return None
        doc = minidom.parseString(out.text)
        for l in doc.getElementsByTagName("FileLocation"):
            url = l.getElementsByTagName("Url")[0].firstChild.nodeValue
            if url.split("/")[2] == "tlu.dl.delivery.mp.microsoft.com":
                return url

    def calculate_hashes(self, data):
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()
        for chunk in data.iter_content(8192):
            md5_hash.update(chunk)
            sha256_hash.update(chunk)
        return md5_hash.hexdigest(), sha256_hash.hexdigest()

    def checker(self, check_type):
        # set check type
        release_type = self.release_type_map[check_type]
        if check_type == "Beta":
            self.update_token()
        else:
            self.user_token = ""
        # set flag
        is_modified = False
        global release_id

        archive = {}
        try:
            with open(os.path.join(self.data_path, f"{self.package_family_name.split('_')[0]}.json"), "r") as f:
                archive = json.load(f)
                f.close()
        except:
            open(os.path.join(self.data_path, f"{self.package_family_name.split('_')[0]}.json"), "w").close()
        
        with open(os.path.join(self.path, "xml", "GetCookie.xml"), "r") as f:
            cookie_content = f.read().format(self.user_token)
            f.close()
        try:
            out = self.session.post(
                'https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx',
                data=cookie_content,
                headers={'Content-Type': 'application/soap+xml; charset=utf-8'}
            )
        except Exception as e:
            self.error_output(e)
            return 1
        doc = minidom.parseString(out.text)
        cookie = doc.getElementsByTagName('EncryptedData')[0].firstChild.nodeValue
        with open(os.path.join(self.path, "xml", "WUIDRequest.xml"), "r") as f:
            cat_id_content = f.read().format(self.user_token, cookie, self.catagory_id, release_type)
            f.close()
        try:
            out = self.session.post(
                'https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx',
                data=cat_id_content,
                headers={'Content-Type': 'application/soap+xml; charset=utf-8'}
            )
        except Exception as e:
            self.error_output(e)
            return 1
        if out.status_code != 200:
            self.error_output(f"Status code is {out.status_code} in checker() from catagory id {self.catagory_id}.\n")
            return 1
        doc = minidom.parseString(html.unescape(out.text))
        filenames = {}
        for node in doc.getElementsByTagName('ExtendedUpdateInfo')[0].getElementsByTagName('Updates')[0].getElementsByTagName('Update'):
            node_xml = node.getElementsByTagName('Xml')[0]
            node_files = node_xml.getElementsByTagName('Files')
            if not node_files:
                continue
            else:
                for node_file in node_files[0].getElementsByTagName('File'):
                    if node_file.hasAttribute('InstallerSpecificIdentifier') and node_file.hasAttribute('FileName'):
                        filenames[node.getElementsByTagName('ID')[0].firstChild.nodeValue] = (f"{node_file.attributes['InstallerSpecificIdentifier'].value}_{node_file.attributes['FileName'].value}",
                                                                                            node_xml.getElementsByTagName('ExtendedProperties')[0].attributes['PackageIdentityName'].value)
        identities = {}
        for node in doc.getElementsByTagName('NewUpdates')[0].getElementsByTagName('UpdateInfo'):
            node_xml = node.getElementsByTagName('Xml')[0]
            if not node_xml.getElementsByTagName('SecuredFragment'):
                continue
            else:
                id = node.getElementsByTagName('ID')[0].firstChild.nodeValue
                update_identity = node_xml.getElementsByTagName('UpdateIdentity')[0]
                if id in filenames:
                    fileinfo = filenames[id]
                    if fileinfo[0] not in identities:
                        identities[fileinfo[0]] = ([update_identity.attributes['UpdateID'].value,
                                                update_identity.attributes['RevisionNumber'].value], fileinfo[1])

        dependencies = {}
        packages = {}
        for file in identities:
            identity_name = file.split("_")[0]
            version = file.split("_")[1]
            architecture = file.split("_")[2]
            file_extension = file.split(".")[-1]
            pattern = re.compile("_[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
            file_name = file.replace(pattern.search(file).group(0), "").replace(file_extension, self.file_extension_map[file_extension])
            item = {
                "FileName": file_name,
                "UpdateID": identities[file][0][0],
                "RevisionNumber": identities[file][0][1]
            }
            if self.package_family_name.split("_")[0].upper() != identities[file][1].upper():
                if identity_name not in dependencies:
                    dependencies[identity_name] = {}
                if version not in dependencies[identity_name]:
                    dependencies[identity_name][version] = {}
                dependencies[identity_name][version][architecture] = item
            else:
                if identity_name not in packages:
                    packages[identity_name] = {}
                if version not in packages[identity_name]:
                    packages[identity_name][version] = {}
                packages[identity_name][version][architecture] = item

        if len(packages) == 0:
            self.error_output(f"No packages found! Maybe the catagory id is not correct.\n")
            return 1

        for identity_name in dependencies:
            for version in dependencies[identity_name]:
                dependencies[identity_name][version] = dict(sorted(dependencies[identity_name][version].items(), key=lambda x: self.arch_order[x[0]], reverse=False))
            dependencies[identity_name] = dict(sorted(dependencies[identity_name].items(), key=lambda x: packaging.version.parse(x[0]), reverse=False))
        for identity_name in packages:
            for version in packages[identity_name]:
                packages[identity_name][version] = dict(sorted(packages[identity_name][version].items(), key=lambda x: self.arch_order[x[0]], reverse=False))
            packages[identity_name] = dict(sorted(packages[identity_name].items(), key=lambda x: packaging.version.parse(x[0]), reverse=False))

        for version in packages[self.package_family_name.split("_")[0]]:
            print(f"Version {version}...")
            if version not in archive:
                archive[version] = {}
            for arch in packages[self.package_family_name.split("_")[0]][version]:
                item = packages[self.package_family_name.split("_")[0]][version][arch]
                file_name = item["FileName"]
                url = self.get_url(self.user_token, item["UpdateID"], item["RevisionNumber"], release_type)
                print(f"FileName: {file_name}\nURL: {url}\n")

                if arch not in archive[version]:
                    archive[version][arch] = {
                        "FileName": item["FileName"],
                        "Hashes": {
                            "MD5": None,
                            "SHA256": None
                        },
                        "UpdateID": [
                            item["UpdateID"]
                        ]
                    }
                    if self.app_config["CalculateHash"]:
                        data = requests.get(url)
                        md5, sha256 = self.calculate_hashes(data)
                        archive[version][arch]["Hashes"]["MD5"] = md5
                        archive[version][arch]["Hashes"]["SHA256"] = sha256
                        # self.aria2.post_download(url, item["FileName"])
                    is_modified = True
                elif item["UpdateID"] not in archive[version][arch]["UpdateID"]:
                    archive[version][arch]["UpdateID"].append(item["UpdateID"])
                    is_modified = True
                else:
                    continue
            archive[version] = dict(sorted(archive[version].items(), key=lambda x: self.arch_order[x[0]], reverse=False))
        archive = dict(sorted(archive.items(), key=lambda x: packaging.version.parse(x[0]), reverse=False))
        if is_modified:
            with open(os.path.join(self.data_path, f"{self.package_family_name.split('_')[0]}.json"), "w") as f:
                f.write(json.dumps(archive, indent=4))
                f.close()