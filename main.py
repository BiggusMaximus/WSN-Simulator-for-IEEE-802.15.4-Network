
# =============================================================================
#
# This simulation was an improvement from the previous version, which includes:
#
# =============================================================================
#
# 1. A new separates config files for simulation, testing and plotting
# 2. MAC, Interference, and Discrete Event Simulator modelling was added
# 3. Uniform console for every classes



import traceback

# Import supporting files from utils
from utils.config import *
from utils.information import *
from utils.save_manager import *

# Import main deployment program
from abstract.channel import ChannelModel
from deployment import create_deployment
from routing import create_routing_protocol
from simulation.simulator import Engine

def main(
        config_file  
    ):
    # Create a simulation folder for the output

    # If something happen during the simulation
    try:
        simulation_config = load(config_file)

        create_simulation_folder(config_file, simulation_config)

        simulation_summaries(simulation_config)


        deployment = create_deployment(simulation_config)
        nodes = deployment.deploy_nodes()

        channel = ChannelModel(simulation_config, nodes)
        routing = create_routing_protocol(simulation_config, nodes, channel)


        Engine(simulation_config, channel, routing).run()




    # Print the output if there are something wrong during simulation
    except Exception as e:
        tb = traceback.format_exc() 
        panel = Panel(tb, title="Error message", title_align="center", border_style="red")
        centered_panel = Align.center(panel)
        console.print(centered_panel)





if __name__ == "__main__":
    import sys
    config = sys.argv[1] if len(sys.argv) > 1 else "simulation.yaml"
    main(config_file=config)