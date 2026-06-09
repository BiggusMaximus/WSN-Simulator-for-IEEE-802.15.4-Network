from abstract.rf import RF
from .IEEE import IEEE_802_15_4
from utils.information import console

RF_REGISTRY  = {
    'IEEE_802_15_4': IEEE_802_15_4,
}

def create_RF(config) -> RF:
    RF_name = config["RF"]["name"]

    if RF_name not in RF_REGISTRY:
        console.print(f"[bold red]Unknown RF hardware: {RF_name}. Available: {RF_REGISTRY.keys()}[/bold red]")

    return RF_REGISTRY[RF_name](config)