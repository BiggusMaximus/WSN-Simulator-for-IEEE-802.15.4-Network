# This file are used for loading the simulation configuration by the user


import yaml
import os

ROOT_DIR = os.getcwd()

def load(config_file):
    if config_file == "simulation.yaml":
        config_path = os.path.join(
            ROOT_DIR,
            f"input/config/{config_file}"
        )
        
    else:
        config_file = config_file.split('/')[-1]
        config_path = os.path.join(
            ROOT_DIR,
            f"input/config/{config_file}"
        )

    print(f"load: {config_path}")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)