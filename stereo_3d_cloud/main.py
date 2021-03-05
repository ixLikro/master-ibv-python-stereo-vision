import json
import os
import sys

# load config
if not os.path.exists("../config.json"):
    sys.exit('config.json not found. Expecting the config.json at root-level. See README for more infos.')
json_file = open("../config.json", "r")
config = json.loads(json_file.read())
json_file.close()

# validate config file
if not ("directory" in config):
    sys.exit('config.json error! A "directory" key at root-Level is mandatory. See README for more infos.')
if not ("defaultParameter" in config
        and "blockSize" in config["defaultParameter"]
        and "maxDisparity" in config["defaultParameter"]):
    sys.exit(
        'config.json error! Please provide default parameter blockSize and maxDisparity. See README for more infos.')
if not (config["defaultParameter"]["blockSize"] % 2 != 0 and config["defaultParameter"]["blockSize"] > 0):
    sys.exit('config.json error! blockSize muss be a positive odd integer. See README for more infos.')
if not (config["defaultParameter"]["maxDisparity"] % 16 == 0 and config["defaultParameter"]["maxDisparity"] > 0):
    sys.exit('config.json error! maxDisparity must be positive and divisible by 16. See README for more infos.')
if not ("baseURL" in config):
    print('[WARN] No "baseURL" key found inside config.json. Online lookup will not work. See README for more infos.')
    config["baseURL"] = ""

# create main dir if it dose not exists
if not os.path.exists(config["directory"]):
    print("Directory " + config["directory"] + " dose not exists, let's create it.")
    os.mkdir(config["directory"])

if __name__ == '__main__':
    # start gui
    from gui import init_and_run_gui

    init_and_run_gui()
