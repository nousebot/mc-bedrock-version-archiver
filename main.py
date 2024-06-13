import os
import json
import hashlib
import logging

from typing import Any, OrderedDict
from ms_store import Store
from ms_xbox import Xbox
from google_play import Play

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

type_name_map = {
    "Store": "Microsoft Store",
    "Xbox": "Microsoft Store (Xbox)",
    "Play": "Google Play"
}

def error_output(e):
    print(f"Error: {e}\n")
    logging.basicConfig(format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s',
        level=logging.ERROR,
        filename='test.log',
        filemode='a')

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
play = Play()

for app in config["Apps"]:
    data_path = ""
    if os.path.exists(app["DataPath"]):
        data_path = app["DataPath"]
    else:
        data_path = default_data_path
        config["Apps"][config["Apps"].index(app)]["DataPath"] = ""
        with open(os.path.join(path, "config.json"), "w") as f:
            f.write(json.dumps(config, indent=4))
            f.close()
    print(f"Checking {app['Name']} ({type_name_map[app['Type']]})...\n")
    if app["Type"] == "Xbox":
        xbox.setup_config(app, data_path = data_path)
        try:
            xbox.get_package_info()
        except Exception as e:
            error_output(e)
            continue
    elif app["Type"] == "Store":
        store.setup_config(app, data_path = data_path)
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
    elif app["Type"] == "Play":
        play.setup_config(app, data_path = data_path)
        print("Checking Stable version...\n")
        if play.checker() == 1:
            continue
        if app["CheckBetaVersion"]:
            print("Checking Beta version...\n")
            if play.checker(beta=True) == 1:
                continue

print("All done!")
