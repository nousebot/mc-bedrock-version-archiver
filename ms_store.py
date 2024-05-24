import os
import re
import time
import gzip
import html
import json
import base64
import hashlib
import requests
import datetime
import subprocess
import packaging.version

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from xml.dom import minidom
from requests import Session
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse

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

    tokens_file = os.path.join(path, "tokens.json")
    tokens = {}
    if os.path.exists(tokens_file):
        with open(tokens_file, "r") as f:
            tokens = json.load(f)
            f.close()
    else:
        cur_time = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        tokens = {
            "Xbox": {
                "AccessToken": {
                    "Jwt": "",
                    "LastUsed": cur_time,
                    "Expires": cur_time
                },
                "UserToken": {
                    "Jwt": "",
                    "LastUsed": cur_time,
                    "Expires": cur_time
                },
                "XToken": {
                    "Jwt": "",
                    "LastUsed": cur_time,
                    "Expires": cur_time
                },
                "UserHashCode": 0
            },
            "Store": {
                "AccessToken": {
                    "Jwt": "",
                    "LastUsed": cur_time,
                    "Expires": cur_time
                }
            }
        }
        with open(tokens_file, "w") as f:
            f.write(json.dumps(tokens, indent=4))
            f.close()

    user_token = tokens["Store"]["AccessToken"]["Jwt"]

    def setup_config(self, config):
        self.app_config = config
        self.catagory_id = config["CataGoryID"]
        self.package_family_name = config["PackageFamilyName"]

    def error_output(self, e):
        print(f"Error: {e}\n")
        with open(os.path.join(self.path, "error.log"), "a+", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] Error: {e}\n")
            f.close()

    def set_data_path(self, data_path: str) -> None:
        data_path = data_path

    def update_token(self):
        with open(self.tokens_file, "r") as f:
            self.tokens = json.load(f)
            f.close()
        self.user_token = self.tokens["Store"]["AccessToken"]["Jwt"]

    def get_token(self):
        last_used_time = datetime.now(timezone(timedelta(hours=8)))
        expires_time = datetime.fromtimestamp(last_used_time.timestamp() + 86400).astimezone(timezone(timedelta(hours=8)))
        login_url = "https://login.live.com/ppsecure/InlineConnect.srf?id=80604&platform=android2.1.0510.1018&client_id=android-app://com.mojang.minecraftearth.H62DKCBHJP6WXXIV7RBFOGOL4NAK4E6Y"

        service = Service(os.path.join(self.path, "bin", "chromedriver", "chromedriver.exe"))
        option = webdriver.ChromeOptions()
        option.add_argument("--headless")
        option.binary_location = os.path.join(self.path, "bin", "centbrowser", "chrome.exe")
        driver = webdriver.Chrome(service=service, options=option)
        driver.get(login_url)
        time.sleep(10)
        driver.find_element("id", "i0116").send_keys("fuchuangguai623154@outlook.com")
        time.sleep(5)
        driver.find_element("id", "idSIButton9").click()
        while driver.find_element("id", "i0118") == None:
            time.sleep(1)
        driver.find_element("id", "i0118").send_keys("JimP2yB0XV")
        time.sleep(5)
        try:
            driver.find_element("id", "idSIButton9").click()
        except Exception as e:
            pass
        count = 0
        while login_url == driver.current_url:
            count += 1
            time.sleep(1)
            if count % 30 == 0:
                driver.find_element("id", "idSIButton9").click()
        cookies = driver.get_cookies()
        driver.quit()
        property = None
        for item in cookies:
            if item["name"] == "Property":
                property = item["value"]
                break
        property = json.loads(property)
        compress = gzip.compress(json.dumps(property).encode())
        value = base64.b64encode(compress).decode("utf-8")
        process = subprocess.Popen([os.path.join(self.path, "bin", "getmstoken", "GetMicrosoftToken.exe"), value], stdout=subprocess.PIPE)
        process.wait()
        token = process.stdout.read().replace(b"\r\n", b"")
        return last_used_time, expires_time, token.decode("utf-8")

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
            cur_time = datetime.now(timezone(timedelta(hours=8)))
            if cur_time > datetime.strptime(self.tokens["Store"]["AccessToken"]["Expires"], "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(timezone(timedelta(hours=8))):
                last_used_time, expires_time, token = self.get_token()
                self.user_token = token
                self.tokens["Store"]["AccessToken"]["Jwt"] = token
                self.tokens["Store"]["AccessToken"]["LastUsed"] = last_used_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                self.tokens["Store"]["AccessToken"]["Expires"] = expires_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            else:
                self.user_token = self.tokens["Store"]["AccessToken"]["Jwt"]
                self.tokens["Store"]["AccessToken"]["LastUsed"] = cur_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            with open(self.tokens_file, "w") as f:
                f.write(json.dumps(self.tokens, indent=4))
                f.close()
        else:
            self.user_token = ""
        # set flag
        is_modified = False
        global release_id

        archive = {}
        try:
            with open(os.path.join(self.data_path, f"{self.package_family_name.split("_")[0]}.json"), "r") as f:
                archive = json.load(f)
                f.close()
        except:
            open(os.path.join(self.data_path, f"{self.package_family_name.split("_")[0]}.json"), "w").close()
        
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
                url = self.get_url(self.user_token, item["UpdateID"], item["RevisionNumber"], release_type)
                print(f"FileName: {item["FileName"]}\nURL: {url}\n")

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
            with open(os.path.join(self.data_path, f"{self.package_family_name.split("_")[0]}.json"), "w") as f:
                f.write(json.dumps(archive, indent=4))
                f.close()