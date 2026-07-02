#!/usr/bin/env python3

"""
parametric_study.py  (with repetitions)

Automates simulation runs across:
  - node counts: 1, 51, 101, 151, 201
  - area sides:   1, 21, 41, 61, 81
  - routing protocols: DirectUnslottedCSMA

Each (nodes, area, protocol) combination is repeated REPETITIONS times.


python parametric_study.py --parallel 8 --repetitions 100

"""

import os
import sys
import subprocess
import itertools
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import yaml
import copy
import time

# ----------------------------------------------------------------------
TEMPLATE_YAML = Path("input/config/simulation.yaml")
OUTPUT_DIR = TEMPLATE_YAML.parent
MAIN_SCRIPT = Path("main.py")

# Parameter sweep values
# NODE_COUNTS = [1, 5, 10, 20, 30, 40, 50]
# AREA_SIDES  = [10]
# NODE_COUNTS = range(5, 55, 5)

NODE_COUNTS = [10, 20, 50, 100, 200, 250, 500]
AREA_SIDES  = [10, 20, 50, 100, 200, 500, 600, 750, 1000]

PROTOCOLS   = ["DirectUnslottedCSMA"]
# CHANNEL = ["Ideal"]
CHANNEL = ["Ideal", "SUI_TypeC", "ITU_P1411"]


# ----------------------------------------------------------------------
def load_template():
    if not TEMPLATE_YAML.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_YAML}")
    with open(TEMPLATE_YAML, "r") as f:
        return yaml.safe_load(f)

def generate_config(template, nodes, area, protocol, pathloss, run_id):
    config = copy.deepcopy(template)
    config["Simulation"]["number_of_nodes"] = nodes
    config["Simulation"]["duration"] = 1

    config["Channel"]["PathLoss"]["name"] = pathloss


    config["Simulation"]["area_dimensions"] = [area, area, 5]
    config["Deployment"]["base_station_locations"] = [[area/2, area/2, 5]]
    config["Simulation"]["name"] = f"{protocol}_n{nodes}_a{area}_run{run_id:03d}"
    config["Routing"]["name"] = protocol
    return config

def run_single_simulation(nodes, area, protocol, pathloss, template, run_id):
    config = generate_config(template, nodes, area, protocol, pathloss, run_id)
    filename = f"{pathloss}_{protocol}_n{nodes}_a{area}_run{run_id:03d}.yaml"
    filepath = OUTPUT_DIR / filename

    try:
        with open(filepath, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
    except Exception as e:
        return False, f"Failed to write config {filename}: {e}"

    cmd = [sys.executable, str(MAIN_SCRIPT), filename]
    try:
        time.sleep(0.1)  # short pause to avoid filesystem conflicts
        subprocess.run(cmd, check=True, capture_output=False, text=True)

        os.remove(filepath)

        return True, f"Completed: {filename}"
    except subprocess.CalledProcessError as e:
        os.remove(filepath)

        return False, f"Simulation failed for {filename}: {e}"
    
    except FileNotFoundError:
        os.remove(filepath)

        return False, f"Could not find {MAIN_SCRIPT}. Are you in the project root?"

def main(parallel=1, repetitions=1):
    template = load_template()
    combinations = list(itertools.product(NODE_COUNTS, AREA_SIDES, PROTOCOLS, CHANNEL))
    total = len(combinations) * repetitions
    print(f"Starting parametric study: {total} simulations to run")
    print(f"Parameters: {len(NODE_COUNTS)} nodes × {len(AREA_SIDES)} areas × {len(PROTOCOLS)} protocols × {repetitions} reps")
    print("-" * 60)

    tasks = []
    for nodes, area, proto, pathloss in combinations:
        for r in range(1, repetitions + 1):
            tasks.append((nodes, area, proto, pathloss, r))

    if parallel <= 1:
        for nodes, area, proto, pathloss, run_id in tasks:
            success, msg = run_single_simulation(nodes, area, proto, pathloss, template, run_id)
            print(msg)
    else:
        with ProcessPoolExecutor(max_workers=parallel) as executor:
            futures = {
                executor.submit(run_single_simulation, n, a, p, pl, template, rid): (n, a, p, pl, rid)
                for n, a, p, pl, rid in tasks
            }
            for future in as_completed(futures):
                n, a, p, pl,  rid = futures[future]
                try:
                    success, msg = future.result()
                except Exception as exc:
                    success, msg = False, f"Exception for {p} n{n} a{a} pl{pl} run{rid}: {exc}"
                print(msg)

    print("-" * 60)
    print("Parametric study finished.")

def notify_done():
    for _ in range(3):
        os.system('play -nq -t alsa synth 0.2 sine 880')
        time.sleep(0.1)
        os.system('play -nq -t alsa synth 0.2 sine 600')


if __name__ == "__main__":
    start_time = time.perf_counter()
    parser = argparse.ArgumentParser(
        description="Run parametric sweep with repetitions for WSN simulations."
    )
    parser.add_argument("--parallel", "-p", type=int, default=1,
                        help="Number of parallel simulations")
    parser.add_argument("--repetitions", "-r", type=int, default=1,
                        help="Number of independent runs per parameter set")
    args = parser.parse_args()
    main(parallel=args.parallel, repetitions=args.repetitions)

    end_time = time.perf_counter()

    # Calculate elapsed time in seconds
    elapsed_time = end_time - start_time
    print(f"Elapsed time: {elapsed_time:.6f} seconds")
    notify_done()