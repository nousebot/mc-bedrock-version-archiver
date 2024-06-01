import os
import gzip
import json
import base64
import subprocess
import packaging.version

from datetime import datetime

class Play:
    path = os.path.dirname(os.path.abspath(__file__))
    get_url_data = {
        "NeedSplitApk": False,
        "PackageName": "",
        "PackageIds": []
    }
    get_detail_data = {
        "PackageName": ""
    }
    app_config = {}
    data_path = ""
    package_name = ""
    version_codes = []

    arch_order = {
        "x86_64": 0,
        "arm64-v8a": 1,
        "x86": 2,
        "armeabi-v7a": 3
    }
    split_apk_order = {
        "com.mojang.minecraftpe": 0,
        "install_pack": 1,
        "config.x86_64": 2,
        "config.arm64_v8a": 3,
        "config.x86": 4,
        "config.armeabi_v7a": 5,
        "config.ldpi": 6,
        "config.mdpi": 7,
        "config.hdpi": 8,
        "config.xhdpi": 9,
        "config.xxhdpi": 10,
        "config.xxxhdpi": 11,
        "config.ar": 12,
        "config.bg": 13,
        "config.ca": 14,
        "config.cs": 15,
        "config.da": 16,
        "config.de": 17,
        "config.el": 18,
        "config.en": 19,
        "config.es": 20,
        "config.fi": 21,
        "config.fr": 22,
        "config.hi": 23,
        "config.hr": 24,
        "config.hu": 25,
        "config.in": 26,
        "config.it": 27,
        "config.iw": 28,
        "config.ja": 29,
        "config.ko": 30,
        "config.lt": 31,
        "config.lv": 32,
        "config.nb": 33,
        "config.nl": 34,
        "config.pl": 35,
        "config.pt": 36,
        "config.ro": 37,
        "config.ru": 38,
        "config.sk": 39,
        "config.sl": 40,
        "config.sr": 41,
        "config.sv": 42,
        "config.th": 43,
        "config.tr": 44,
        "config.uk": 45,
        "config.vi": 46,
        "config.zh": 47
    }

    def setup_config(self, config, data_path=None):
        self.app_config = config
        self.data_path = config["DataPath"] if data_path is None else data_path
        self.package_name = config["PackageName"]
        self.get_url_data["PackageName"] = self.package_name
        self.get_detail_data["PackageName"] = self.package_name

    def error_output(self, e):
        print(f"Error: {e}\n")
        with open(os.path.join(self.path, "error.log"), "a+", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] Error: {e}\n")
            f.close()

    def get_url_info(self, split=False):
        if split:
            print("Checking split apk...\n")
        else:
            print("Checking full apk...\n")
        self.get_url_data["NeedSplitApk"] = split
        compress = gzip.compress(json.dumps(self.get_url_data).encode())
        value = base64.b64encode(compress).decode("utf-8")
        process = subprocess.Popen([os.path.join(self.path, "bin", "gpappdetail", "GetGPAppDetail.exe"), "-m", "1", "-u", "beta.json", "-c", value], stdout=subprocess.PIPE)
        res = process.stdout.read().decode("utf-8")
        process.kill()
        decompress = gzip.decompress(base64.b64decode(res))
        data = decompress.decode('unicode_escape')
        return json.loads(data)
    
    def get_package_info(self, beta=False):
        user_data_name = "beta.json" if beta else "release.json"
        compress = gzip.compress(json.dumps(self.get_detail_data).encode())
        value = base64.b64encode(compress).decode("utf-8")
        process = subprocess.Popen([os.path.join(self.path, "bin", "gpappdetail", "GetGPAppDetail.exe"), "-m", "2", "-u", user_data_name, "-c", value], stdout=subprocess.PIPE)
        res = process.stdout.read().decode("utf-8")
        decompress = gzip.decompress(base64.b64decode(res))
        data = decompress.decode('unicode_escape')
        return json.loads(data)

    def checker(self, beta=False): 
        archive = {}
        try:
            with open(os.path.join(self.data_path, f"{self.package_name}.json"), "r", encoding="utf-8") as f:
                archive = json.load(f)
                f.close()
        except:
            open(os.path.join(self.data_path, f"{self.package_name}.json"), "w").close()

        data = self.get_package_info(beta)
        if data["Success"]:
            
            # threads = []
            # threads.append(threading.Thread(target=self.get_url_info, args=(self, False)))
            # threads.append(threading.Thread(target=self.get_url_info, args=(self, True)))
            # for thread in threads:
            #     thread.start()
            # wait = True
            # while wait:
            #     wait = False
            #     for thread in threads:
            #         if thread.is_alive():
            #             wait = True
            #             time.sleep(1)
            self.updater(data, archive)
            for version in archive:
                archive[version] = dict(sorted(archive[version].items(), key=lambda x: self.arch_order[x[0]], reverse=False))
            archive = dict(sorted(archive.items(), key=lambda x: packaging.version.parse(x[0]), reverse=False))
            with open(os.path.join(self.data_path, f"{self.package_name}.json"), "w") as f:
                f.write(json.dumps(archive, indent=4))
                f.close()
        else:
            self.error_output(Exception(data["Message"]))
        
    def updater(self, data, archive, type="all"):
        url_data = ""
        version_name = data["Data"]["VersionName"]
        if version_name not in archive:
            archive[version_name] = {}
            self.version_codes.clear()
            for key in data["Data"]["VersionCodeList"]:
                self.version_codes.append(data["Data"]["VersionCodeList"][key])
        else:
            for key in data["Data"]["VersionCodeList"]:
                if data["Data"]["VersionCodeList"][key] not in archive[version_name]:
                    self.version_codes.append(data["Data"]["VersionCodeList"][key])
        
        print(f"Latest version: {version_name}\n")
        if len(self.version_codes) == 0:
            return
        self.get_url_data["PackageIds"] = self.version_codes
        full_apk_info = self.get_url_info(False) if type == "full" or type == "all" else {"Success": False, "Message": "Skip ckeck full apk", "Data": {}}
        split_apk_info = self.get_url_info(True) if type == "split" or type == "all" else {"Success": False, "Message": "Skip ckeck split apk", "Data": {}}
        for key in data["Data"]["VersionCodeList"]:
            version_code = data["Data"]["VersionCodeList"][key]
            file_name = f"{self.package_name}_{data['Data']['VersionName']}_{data['Data']['VersionCodeList'][key]}.apk"
            if full_apk_info["Data"] != {}:
                print("Full apk:")
                file_size = full_apk_info["Data"][f"{version_code}"]["Size"]
                download_url = full_apk_info["Data"][f"{version_code}"]["DownloadUrl"]
                url_data += f"File Name: {file_name}\nFile Size: {file_size}\nDownload URL: {download_url}\n"
                print(f"File Name: {file_name}\nFile Size: {file_size}\nDownload URL: {download_url}\n")
                if key not in archive[version_name]:
                    archive[version_name][key] = {
                        "VersionCode": version_code,
                        "FullApkData": {
                            "FileName": file_name,
                            "FileSize": file_size,
                            "Hashes": {
                                "MD5": "",
                                "SHA256": ""
                            }
                        },
                        "SplitApkData": {}
                    }
                else:
                    archive[version_name][key]["FullApkData"] = {
                        "FileName": file_name,
                        "FileSize": file_size,
                        "Hashes": {
                            "MD5": "",
                            "SHA256": ""
                        }
                    }
            if not full_apk_info["Success"]:
                if full_apk_info["Message"] != "Skip ckeck full apk":
                    self.error_output(Exception(full_apk_info["Message"]))
            if split_apk_info["Data"] != {}:
                if f"{version_code}" not in split_apk_info["Data"] or split_apk_info["Data"][f"{version_code}"]["SplitApkData"] == {}:
                    continue
                else:
                    print("Split apks:")
                    if key not in archive[version_name]:
                        archive[version_name][key] = {
                            "VersionCode": version_code,
                            "FullApkData": {},
                            "SplitApkData": {}
                        }
                    file_name = f"{self.package_name}_{data['Data']['VersionCodeList'][key]}.apk"
                    file_size = split_apk_info["Data"][f"{version_code}"]["Size"]
                    download_url = split_apk_info["Data"][f"{version_code}"]["DownloadUrl"]
                    url_data += f"File Name: {file_name}\nFile Size: {file_size}\nDownload URL: {download_url}\n"
                    print(f"File Name: {file_name}\nFile Size: {file_size}\nDownload URL: {download_url}\n")
                    split_data = {}
                    split_data[self.package_name] = {
                        "FileName": file_name,
                        "FileSize": file_size,
                        "Hashes": {
                            "MD5": "",
                            "SHA256": ""
                        }
                    }
                    for split_key in split_apk_info["Data"][f"{version_code}"]["SplitApkData"]:
                        file_name = f"{split_key}_{data['Data']['VersionCodeList'][key]}.apk"
                        file_size = split_apk_info["Data"][f"{version_code}"]["SplitApkData"][split_key]["Size"]
                        download_url = split_apk_info["Data"][f"{version_code}"]["SplitApkData"][split_key]["DownloadUrl"]
                        url_data += f"File Name: {file_name}\nFile Size: {file_size}\nDownload URL: {download_url}\n"
                        print(f"File Name: {file_name}\nFile Size: {file_size}\nDownload URL: {download_url}\n")
                        split_data[split_key] = {
                            "FileName": file_name,
                            "FileSize": file_size,
                            "Hashes": {
                                "MD5": "",
                                "SHA256": ""
                            }
                        }
                    split_data = dict(sorted(split_data.items(), key=lambda x: self.split_apk_order[x[0]], reverse=False))
                    archive[version_name][key]["SplitApkData"] = split_data
            if not split_apk_info["Success"]:
                if split_apk_info["Message"] != "Skip ckeck split apk":
                    self.error_output(Exception(split_apk_info["Message"]))
        return url_data
    
        