
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

        self.duration = config['Simulation']['duration']
        self.display_period = config['Simulation']['display_period']


    def run(self):
        console.print(
            Panel(
                f"[bold cyan]Starting Simulation with {self.routing.routing_name}[/bold cyan]"
            ),
            justify="center"
        )

        for duration_period in range(1, self.duration + 1):
            

            console.print(
                Panel(
                    f"[bold cyan]Period {duration_period} / {self.duration}[/bold cyan]"
                ),
                justify="center"
            )
            

            if self.channel.n_alive == 0 and duration_period > 1:
                console.print(
                    Panel(
                        f"[bold red]All nodes are dead at period {duration_period}! Ending simulation.[/bold red]"
                    ),
                    justify="center"
                )
                break
            else:
                create_period_folders(duration_period, self.config)
                self.routing.run(duration_period)
            

