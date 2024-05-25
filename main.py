import hashlib
import os
import json
import logging
import time
import datetime

from typing import Any, OrderedDict
from ms_store import Store
from ms_xbox import Xbox

class Prop(OrderedDict):
    def __init__(self, props: str = ...) -> None:
        super().__init__()
        for i, line in enumerate(props.splitlines(False)):
            if '=' in line:
                k, v = line.split('=', 1)
                self[k] = v
            else:
                self[f".{i}"] = line

    def __setattr__(self, __name: str, __value: Any) -> None:
        self[__name] = __value

    def __repr__(self):
        return '\n'.join(f'{item}={self[item]}' for item in self)

timer = 60
logging.captureWarnings(True)
path = os.path.dirname(os.path.abspath(__file__))
parent_path = os.path.dirname(path)
default_data_path = ""

def error_output(e):
    print(f"Error: {e}\n")
    with open(os.path.join(path, "error.log"), "a+", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now()}] Error: {e}\n")
        f.close()

def calculate_hash(file_path, algorithm):
    hash_function = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        while chunk := f.read(4096):
            hash_function.update(chunk)
    return hash_function.hexdigest()

config = {}
with open(os.path.join(path, "config.json"), "r") as f:
    config = json.loads(f.read())
    f.close()
if os.path.dirname(config["DefaultDataPath"]) != os.path.join(path, "data"):
    default_data_path = os.path.join(path, "data")
    config["DefaultDataPath"] = default_data_path
    if not os.path.exists(os.path.join(path, "data")):
        os.makedirs(os.path.join(path, "data"))
    with open(os.path.join(path, "config.json"), "w") as f:
        json.dump(config, f, indent=4)
        f.close()

print("Processing...")
store = Store()
xbox = Xbox()

for app in config["Apps"]:
    app_is_xbox = False
    if "xvc" in app["FileExtension"] or "msixvc" in app["FileExtension"]:
        app_is_xbox = True
    data_path = ""
    if os.path.exists(app["DataPath"]):
        data_path = app["DataPath"]
    else:
        data_path = default_data_path
        config["Apps"][config["Apps"].index(app)]["DataPath"] = ""
        with open(os.path.join(path, "config.json"), "w") as f:
            f.write(json.dumps(config, indent=4))
            f.close()
    print(f"Checking {app['Name']}...\n")
    if app_is_xbox:
        xbox.setup_config(app)
        xbox.data_path = data_path
        xbox.get_package_info()
        # try:
        #     xbox.get_package_info()
        # except Exception as e:
        #     error_output(e)
        #     continue
    else:
        store.setup_config(app)
        store.data_path = data_path
        print("Checking Stable version...\n")
        if store.checker("Stable") == 1:
            continue
        if app["CheckWIF"]:
            print("Checking Windows Insider version...\n")
            if store.checker("Windows Insider") == 1:
                continue
        if app["CheckBetaVersion"]:
            print("Checking Beta version...\n")
            if store.checker("Beta") == 1:
                continue

print("All done!")
