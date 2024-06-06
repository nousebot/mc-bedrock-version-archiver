import os
import time
import gzip
import json
import base64
import requests
import datetime
import threading
import subprocess

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from dateutil.parser import parse
from datetime import datetime, timedelta, timezone

class Store:
    def get_token(path):
        last_used_time = datetime.now(timezone(timedelta(hours=8)))
        expires_time = datetime.fromtimestamp(last_used_time.timestamp() + 86400).astimezone(timezone(timedelta(hours=8)))
        login_url = "https://login.live.com/ppsecure/InlineConnect.srf?id=80604&platform=android2.1.0510.1018&client_id=android-app://com.mojang.minecraftearth.H62DKCBHJP6WXXIV7RBFOGOL4NAK4E6Y"

        service = Service(os.path.join(os.getenv("CHROMEWEBDRIVER"), "chromedriver"))
        option = webdriver.ChromeOptions()
        option.add_argument("--headless")
        driver = webdriver.Chrome(service=service, options=option)
        driver.get(login_url)
        time.sleep(10)
        driver.find_element("id", "i0116").send_keys(os.getenv("ACCOUNT"))
        time.sleep(5)
        driver.find_element("id", "idSIButton9").click()
        while driver.find_element("id", "i0118") == None:
            time.sleep(1)
        driver.find_element("id", "i0118").send_keys(os.getenv("PASSWORD"))
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
        process = subprocess.Popen([os.path.join(path, "bin", "getmstoken", "GetMicrosoftToken"), value], stdout=subprocess.PIPE)
        process.wait()
        token = process.stdout.read().replace(b"\r\n", b"")
        return last_used_time, expires_time, token.decode("utf-8")

class Xbox:
    def get_access_token(path):
        get_access_token_url = "https://login.live.com/oauth20_authorize.srf?response_type=token&scope=service::user.auth.xboxlive.com::MBI_SSL&redirect_uri=https://login.live.com/oauth20_desktop.srf&client_id=00000000402b5328&display=touch&locale=en"
        service = Service(os.path.join(os.getenv("CHROMEWEBDRIVER"), "chromedriver"))
        option = webdriver.ChromeOptions()
        option.add_argument("--headless")
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

    def get_user_token(access_token):
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

    def get_x_token(user_token):
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

def updater():
    access_token, last_used, expires = Xbox.get_access_token(path)
    tokens["Xbox"]["AccessToken"]["Jwt"] = access_token
    tokens["Xbox"]["AccessToken"]["LastUsed"] = last_used.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    tokens["Xbox"]["AccessToken"]["Expires"] = expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    user_token, last_used, expires = Xbox.get_user_token(access_token)
    tokens["Xbox"]["UserToken"]["Jwt"] = user_token
    tokens["Xbox"]["UserToken"]["LastUsed"] = last_used.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    tokens["Xbox"]["UserToken"]["Expires"] = expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    x_token, user_hashcode, last_used, expires = Xbox.get_x_token(user_token)
    tokens["Xbox"]["XToken"]["Jwt"] = x_token
    tokens["Xbox"]["XToken"]["LastUsed"] = last_used.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    tokens["Xbox"]["XToken"]["Expires"] = expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    tokens["Xbox"]["UserHashCode"] = user_hashcode

    last_used_time, expires_time, token = Store.get_token(path)
    tokens["Store"]["AccessToken"]["Jwt"] = token
    tokens["Store"]["AccessToken"]["LastUsed"] = last_used_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    tokens["Store"]["AccessToken"]["Expires"] = expires_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    with open("tokens.json", "w") as f:
        f.write(json.dumps(tokens, indent=4))
        f.close()

def __main__():
    path = os.path.dirname(os.path.abspath(__file__))
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
    thread = threading.Thread(target=updater)
    thread.start()
    thread.join(120)
    if thread.is_alive():
        thread._stop()
        print("Timeout")

__main__()
