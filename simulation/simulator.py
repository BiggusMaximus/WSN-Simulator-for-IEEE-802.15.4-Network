
from utils.information import *
from utils.save_manager import *
import pickle


class Engine:
    def __init__(
        self,
        config,
        channel, 
        routing
    ):
        self.config = config
        self.channel = channel
        self.routing = routing

        self.rounds = config['Simulation']['rounds']
        self.display_period = config['Simulation']['display_period']


    def run(self):
        console.print(
            Panel(
                f"[bold cyan]Starting Simulation with {self.routing.routing_name}[/bold cyan]"
            ),
            justify="center"
        )

        for simulation_round in range(1, self.rounds + 1):
            

            console.print(
                Panel(
                    f"[bold cyan]Round {simulation_round}[/bold cyan]"
                ),
                justify="center"
            )
            

            if self.channel.n_alive == 0 and simulation_round > 1:
                console.print(
                    Panel(
                        f"[bold red]All nodes are dead at round {simulation_round}! Ending simulation.[/bold red]"
                    ),
                    justify="center"
                )
                break
            else:
                create_period_folders(simulation_round, self.config)
                self.routing.run(simulation_round)
            

