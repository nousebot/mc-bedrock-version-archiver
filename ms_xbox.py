import logging
import os
import re
import json
import hashlib
import requests
import packaging.version

from datetime import datetime

class Xbox:
    path = os.path.dirname(os.path.realpath(__file__))
    package_url = "https://packagespc.xboxlive.com/GetBasePackage/"
    package_spec_url = "https://packagespc.xboxlive.com/GetSpecificBasePackage/"
    app_config = {}
    data_path = ""
    content_id = ""
    package_family_name = ""
    access_token = ""
    user_token = ""
    x_token = ""
    user_hashcode = ""

    sort_map = {
        "xboxone": 0,
        "xss/xsx": 1,
        "pc": 2
    }
    platform_map = {
        "xboxone": "Xbox One",
        "xss/xsx": "Xbox Series S/X",
        "pc": "PC"
    }

    def setup_config(self, config, data_path=None):
        self.app_config = config
        self.data_path = config["DataPath"] if data_path is None else data_path
        self.content_id = config["ContentID"]
        self.package_family_name = config["PackageFamilyName"]

    def error_output(self, e):
        print(f"Error: {e}\n")
        logging.basicConfig(format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s',
            level=logging.ERROR,
            filename='test.log',
            filemode='a')

    def calculate_hashes(self, data):
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()
        for chunk in data.iter_content(8192):
            md5_hash.update(chunk)
            sha256_hash.update(chunk)
        return md5_hash.hexdigest(), sha256_hash.hexdigest()
    
    def update_token(self):
        with open(os.path.join(self.path, "tokens.json"), "r") as f:
            self.tokens = json.load(f)
            f.close()
        self.access_token = self.tokens["Xbox"]["AccessToken"]["Jwt"]
        self.user_token = self.tokens["Xbox"]["UserToken"]["Jwt"]
        self.x_token = self.tokens["Xbox"]["XToken"]["Jwt"]
        self.user_hashcode = self.tokens["Xbox"]["UserHashCode"]

    def get_package_info(*args):
        self = args[0]
        version_id = None
        if len(args) == 2:
            version_id = args[1]
        archive = {}
        try:
            with open(os.path.join(self.data_path, f"{self.package_family_name.split('_')[0]}.json"), "r") as f:
                archive = json.load(f)
                f.close()
        except:
            open(os.path.join(self.data_path, f"{self.package_family_name.split('_')[0]}.json"), "w").close()
        is_modify = False

        self.update_token()
        url = self.package_url + self.content_id
        if version_id != None:
            url = self.package_spec_url + self.content_id + "/" + version_id
        headers = {
            "Authorization": f"XBL3.0 x={self.user_hashcode};{self.x_token}",
            "User-Agent": ""
        }
        response = requests.get(url, headers=headers)
        data = json.loads(response.text)
        package_found = data["PackageFound"]
        if not package_found:
            self.error_output("Package not found! Please check the content id and try again.")
            return
        temp_data = {}
        for i in range(len(data["PackageFiles"])):
            if not self.package_family_name.split("_")[0] in data["PackageFiles"][i]["FileName"]:
                continue
            version_id = data["VersionId"]
            version = re.search(r"[0-9]{1,}\.[0-9]{1,}\.[0-9]{1,}\.[0-9]{1,}", data["Version"]).group(0)
            file_name = data["PackageFiles"][0]["FileName"]
            file_size = data["PackageFiles"][0]["FileSize"]
            download_url = []
            download_url.append(data["PackageFiles"][0]["CdnRootPaths"][0] + data["PackageFiles"][0]["RelativeUrl"])
            download_url.append(data["PackageFiles"][0]["CdnRootPaths"][1] + data["PackageFiles"][0]["RelativeUrl"])
            download_url.append(data["PackageFiles"][0]["BackgroundCdnRootPaths"][0] + data["PackageFiles"][0]["RelativeUrl"])
            download_url.append(data["PackageFiles"][0]["BackgroundCdnRootPaths"][1] + data["PackageFiles"][0]["RelativeUrl"])
            type = "xboxone"
            if file_name.endswith("_x.xvc"):
                type = "xboxone"
            elif file_name.endswith("_xs.xvc"):
                type = "xss/xsx"
            elif file_name.endswith(".msixvc"):
                type = "pc"
            item = {
                "FileName": file_name,
                "FileSize": file_size,
                "Hashes": {
                    "MD5": None,
                    "SHA256": None
                },
                "VersionID": version_id,
                "DownloadURLs": download_url
            }
            temp_data[version] = {}
            temp_data[version][type] = item
            if not version in archive:
                if self.app_config["CalculateHash"]:
                    temp = requests.get(download_url[0])
                    md5, sha256 = self.calculate_hashes(temp)
                    temp_data[version][type]["Hashes"]["MD5"] = md5
                    temp_data[version][type]["Hashes"]["SHA256"] = sha256
                is_modify = True
                archive[version] = {}
            if not type in archive[version]:
                is_modify = True
                archive[version][type] = item

        for version in temp_data:
            for type in temp_data[version]:
                version_id = temp_data[version][type]["VersionID"]
                file_name = temp_data[version][type]["FileName"]
                file_size = temp_data[version][type]["FileSize"]
                download_url = temp_data[version][type]["DownloadURLs"]
                print(f"Platform: {self.platform_map[type]}")
                print(f"Version: {version}")
                print(f"File Name: {file_name}")
                print(f"File Size: {file_size}")
                print(f"Download URL: ")
                for url in download_url:
                    print(url)
        print()
        if is_modify:
            for version in archive:
                archive[version] = dict(sorted(archive[version].items(), key=lambda x: self.sort_map[x[0]], reverse=False))
            archive = dict(sorted(archive.items(), key=lambda x: packaging.version.parse(x[0]), reverse=False))
            with open(os.path.join(self.data_path, f"{self.package_family_name.split('_')[0]}.json"), "w") as f:
                f.write(json.dumps(archive, indent=4))
                f.close()
        
