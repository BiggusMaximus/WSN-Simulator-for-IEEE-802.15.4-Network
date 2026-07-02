# This program is to create a save directory for:
# 1. Initial simulation (output, copy of yaml files)
# 2. Output directory for each periods


import os, datetime
import shutil

global SIMULATION_FOLDER_PATH 

def create_simulation_folder(config_file, config):
    print(config_file)
    info_name = (
              f"{config['Channel']["PathLoss"]['name']}"
             f"_{config['Routing']['name']}"
            f"_N{config['Simulation']['number_of_nodes']}"
            f"_L{config['Simulation']['area_dimensions'][0]}"
        )
    SIMULATION_FOLDER_PATH = os.path.join(OUTPUT_FOLDER_PATH, f'TRIAL - {NUMBER_OF_SIMULATION_PERFORMED + 1} - ({datetime.datetime.now().strftime("%d-%m-%Y")}) - {info_name}')
    os.makedirs(SIMULATION_FOLDER_PATH, exist_ok=True)

    # Folder contains every simulation that had been performed previously
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

    # print(f"\nconfig_path: {config_path}\nconfig_file: {config_path.split('/')[-1]}\ncopy to: {os.path.join(
    #             SIMULATION_FOLDER_PATH, 
    #             config_file
    #         )}")
    shutil.copy(
            config_path, 
            os.path.join(
                SIMULATION_FOLDER_PATH, 
                config_file
            )
        )



    


def create_period_folders(period, config=None):
    # For each period during simulation, its created a new folder
    info_name = (
              f"{config['Channel']["PathLoss"]['name']}"
             f"_{config['Routing']['name']}"
            f"_N{config['Simulation']['number_of_nodes']}"
            f"_L{config['Simulation']['area_dimensions'][0]}"
        )

    SIMULATION_FOLDER_PATH = os.path.join(OUTPUT_FOLDER_PATH, f'TRIAL - {NUMBER_OF_SIMULATION_PERFORMED + 1} - ({datetime.datetime.now().strftime("%d-%m-%Y")}) - {info_name}')
    period = str(period)
    
    
    

    folder_name = f"Period-{period}"
    period_folder = os.path.join(SIMULATION_FOLDER_PATH, folder_name)
    os.makedirs(period_folder, exist_ok=True)
    return period_folder



    
ROOT_DIR = os.getcwd()
OUTPUT_FOLDER_PATH = os.path.join(
                    ROOT_DIR, "output"
                )

os.makedirs(OUTPUT_FOLDER_PATH, exist_ok=True)

NUMBER_OF_SIMULATION_PERFORMED = len(
        [dir for dir in os.listdir(OUTPUT_FOLDER_PATH) if os.path.isdir(os.path.join(OUTPUT_FOLDER_PATH, dir))]
    )
