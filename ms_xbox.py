import hashlib
import os
import re
import json
import time
import requests
import packaging.version

from datetime import datetime, timedelta, timezone
from dateutil.parser import parse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

class Xbox:
    path = os.path.dirname(os.path.realpath(__file__))
    aria2 = None
    app_config = {}
    data_path = ""
    content_id = ""
    package_family_name = ""
    package_url = "https://packagespc.xboxlive.com/GetBasePackage/"
    package_spec_url = "https://packagespc.xboxlive.com/GetSpecificBasePackage/"

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

    access_token = tokens["Xbox"]["AccessToken"]["Jwt"]
    user_token = tokens["Xbox"]["UserToken"]["Jwt"]
    x_token = tokens["Xbox"]["XToken"]["Jwt"]
    user_hashcode = tokens["Xbox"]["UserHashCode"]

    def setup_config(self, config):
        self.app_config = config
        self.content_id = config["CataGoryID"]
        self.package_family_name = config["PackageFamilyName"]

    def error_output(self, e):
        print(f"Error: {e}\n")
        with open(os.path.join(self.path, "error.log"), "a+", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] Error: {e}\n")
            f.close()

    def calculate_hashes(self, data):
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()
        for chunk in data.iter_content(8192):
            md5_hash.update(chunk)
            sha256_hash.update(chunk)
        return md5_hash.hexdigest(), sha256_hash.hexdigest()
    
    def update_token(self):
        with open(self.tokens_file, "r") as f:
            self.tokens = json.load(f)
            f.close()
        self.access_token = self.tokens["Xbox"]["AccessToken"]["Jwt"]
        self.user_token = self.tokens["Xbox"]["UserToken"]["Jwt"]
        self.x_token = self.tokens["Xbox"]["XToken"]["Jwt"]
        self.user_hashcode = self.tokens["Xbox"]["UserHashCode"]

    def get_access_token(self):
        get_access_token_url = "https://login.live.com/oauth20_authorize.srf?response_type=token&scope=service::user.auth.xboxlive.com::MBI_SSL&redirect_uri=https://login.live.com/oauth20_desktop.srf&client_id=00000000402b5328&display=touch&locale=en"
        service = Service(os.path.join(self.path, "bin", "chromedriver", "chromedriver.exe"))
        option = webdriver.ChromeOptions()
        option.add_argument("--headless")
        option.binary_location = os.path.join(self.path, "bin", "centbrowser", "chrome.exe")
        driver = webdriver.Chrome(service=service, options=option)
        driver.get(get_access_token_url)
        time.sleep(10)
        driver.find_element("id", "i0116").send_keys(os.getenv("ACCOUNT"))
        driver.find_element("id", "idSIButton9").click()
        time.sleep(5)
        driver.find_element("id", "i0118").send_keys(os.getenv("PASSWORD"))
        time.sleep(5)
        driver.find_element("id", "idSIButton9").click()
        count = 0
        while get_access_token_url == driver.current_url:
            count += 1
            time.sleep(1)
            if count % 30 == 0:
                driver.find_element("id", "idSIButton9").click()
        redricet_url = driver.current_url
        driver.quit()
        values = redricet_url.split("#")[1].split("&")
        access_token = ""
        expires_in = 0
        for value in values:
            if value.startswith("access_token="):
                access_token = value.split("=")[1]
            if value.startswith("expires_in="):
                expires_in = int(value.split("=")[1])
        last_used_time = datetime.now(timezone(timedelta(hours=8)))
        expires_time = datetime.fromtimestamp(last_used_time.timestamp() + expires_in).astimezone(timezone(timedelta(hours=8)))
        return access_token, last_used_time, expires_time

    def get_user_token(self, access_token):
        get_user_token_url = "https://user.auth.xboxlive.com/user/authenticate"
        headers = {"x-xbl-contract-version": "1"}
        data = {
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT",
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": access_token,
            },
        }
        xasu_response = requests.post(get_user_token_url, headers=headers, json=data)
        xasu_json = json.loads(xasu_response.text)
        user_token = xasu_json["Token"]
        last_used_time = parse(xasu_json["IssueInstant"]).astimezone(timezone(timedelta(hours=8)))
        expires_time = parse(xasu_json["NotAfter"]).astimezone(timezone(timedelta(hours=8)))
        return user_token, last_used_time, expires_time

    def get_x_token(self, user_token):
        get_authorization_url = "https://xsts.auth.xboxlive.com/xsts/authorize"
        headers = {"x-xbl-contract-version": "1"}
        data = {
            "RelyingParty": "http://update.xboxlive.com",
            "TokenType": "JWT",
            "Properties": {
                "UserTokens": [user_token],
                "SandboxId": "RETAIL",
            },
        }
        xsts_response = requests.post(get_authorization_url, headers=headers, json=data)
        xsts_json = json.loads(xsts_response.text)
        x_token = xsts_json["Token"]
        user_hashcode = xsts_json["DisplayClaims"]["xui"][0]["uhs"]
        last_used_time = parse(xsts_json["IssueInstant"]).astimezone(timezone(timedelta(hours=8)))
        expires_time = parse(xsts_json["NotAfter"]).astimezone(timezone(timedelta(hours=8)))
        return x_token, user_hashcode, last_used_time, expires_time


    def get_package_info(*args):
        self = args[0]
        version_id = None
        if len(args) == 2:
            version_id = args[1]
        archive = {}
        try:
            with open(os.path.join(self.data_path, f"{self.package_family_name.split("_")[0]}.json"), "r") as f:
                archive = json.load(f)
                f.close()
        except:
            open(os.path.join(self.data_path, f"{self.package_family_name.split("_")[0]}.json"), "w").close()
        is_modify = False

        self.update_token()
        refresh = False
        cur_time = datetime.now(timezone(timedelta(hours=8)))
        if cur_time >= datetime.strptime(self.tokens["Xbox"]["AccessToken"]["Expires"], "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(timezone(timedelta(hours=8))):
            refresh = True
            access_token, last_used, expires = self.get_access_token()
            self.tokens["Xbox"]["AccessToken"]["Jwt"] = access_token
            self.tokens["Xbox"]["AccessToken"]["LastUsed"] = last_used.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            self.tokens["Xbox"]["AccessToken"]["Expires"] = expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            access_token = self.tokens["Xbox"]["AccessToken"]["Jwt"]
            self.tokens["Xbox"]["AccessToken"]["LastUsed"] = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        if refresh or cur_time > datetime.strptime(self.tokens["Xbox"]["UserToken"]["Expires"], "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(timezone(timedelta(hours=8))):
            user_token, last_used, expires = self.get_user_token(access_token)
            self.tokens["Xbox"]["UserToken"]["Jwt"] = user_token
            self.tokens["Xbox"]["UserToken"]["LastUsed"] = last_used.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            self.tokens["Xbox"]["UserToken"]["Expires"] = expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            user_token = self.tokens["Xbox"]["UserToken"]["Jwt"]
            self.tokens["Xbox"]["UserToken"]["LastUsed"] = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        if refresh or cur_time > datetime.strptime(self.tokens["Xbox"]["XToken"]["Expires"], "%Y-%m-%dT%H:%M:%S.%fZ").astimezone(timezone(timedelta(hours=8))):
            x_token, user_hashcode, last_used, expires = self.get_x_token(user_token)
            self.tokens["Xbox"]["XToken"]["Jwt"] = x_token
            self.tokens["Xbox"]["XToken"]["LastUsed"] = last_used.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            self.tokens["Xbox"]["XToken"]["Expires"] = expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            self.tokens["Xbox"]["UserHashCode"] = user_hashcode
        else:
            x_token = self.tokens["Xbox"]["XToken"]["Jwt"]
            user_hashcode = self.tokens["Xbox"]["UserHashCode"]
            self.tokens["Xbox"]["XToken"]["LastUsed"] = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        if refresh:
            with open(self.tokens_file, "w") as f:
                f.write(json.dumps(self.tokens, indent=4))
                f.close()

        url = self.package_url + self.content_id
        if version_id != None:
            url = self.package_spec_url + self.content_id + "/" + version_id
        headers = {
            "Authorization": f"XBL3.0 x={user_hashcode};{x_token}",
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
            with open(os.path.join(self.data_path, f"{self.package_family_name.split("_")[0]}.json"), "w") as f:
                f.write(json.dumps(archive, indent=4))
                f.close()
        
