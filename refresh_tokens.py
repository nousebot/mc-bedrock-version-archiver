import json
from ms_xbox import Xbox
from ms_store import Store

xbox = Xbox()
store = Store()

tokens = {}
with open("tokens.json", "r") as f:
    tokens = json.load(f)
    f.close()

access_token, last_used, expires = xbox.get_access_token()
tokens["Xbox"]["AccessToken"]["Jwt"] = access_token
tokens["Xbox"]["AccessToken"]["LastUsed"] = last_used.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
tokens["Xbox"]["AccessToken"]["Expires"] = expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

user_token, last_used, expires = xbox.get_user_token(access_token)
tokens["Xbox"]["UserToken"]["Jwt"] = user_token
tokens["Xbox"]["UserToken"]["LastUsed"] = last_used.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
tokens["Xbox"]["UserToken"]["Expires"] = expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

x_token, user_hashcode, last_used, expires = xbox.get_x_token(user_token)
tokens["Xbox"]["XToken"]["Jwt"] = x_token
tokens["Xbox"]["XToken"]["LastUsed"] = last_used.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
tokens["Xbox"]["XToken"]["Expires"] = expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
tokens["Xbox"]["UserHashCode"] = user_hashcode

last_used_time, expires_time, token = store.get_token()
user_token = token
tokens["Store"]["AccessToken"]["Jwt"] = token
tokens["Store"]["AccessToken"]["LastUsed"] = last_used_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
tokens["Store"]["AccessToken"]["Expires"] = expires_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

with open("tokens.json", "w") as f:
    f.write(json.dumps(tokens, indent=4))
    f.close()
