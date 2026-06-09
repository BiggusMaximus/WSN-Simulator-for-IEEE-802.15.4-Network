from abstract.interference import InterferenceModel
from .IEEE import IEEE_802_15_4
from utils.information import console

INTERFERENCE_REGISTRY = {
    'IEEE_802_15_4': IEEE_802_15_4,
}

def create_interference(config) -> InterferenceModel:
    interference_name = config['name']

    if interference_name not in INTERFERENCE_REGISTRY:
        console.print(
            f"[bold red]Unknown interference model: {interference_name}. Available: {INTERFERENCE_REGISTRY.keys()}[/bold red]"
        )
    return INTERFERENCE_REGISTRY[interference_name](config)