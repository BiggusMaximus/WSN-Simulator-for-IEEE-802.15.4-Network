from abstract.memory import Memory
from .micro_sd import microSD
from utils.information import console

Memory_REGISTRY  = {
    'microSD': microSD,
}

def create_memory(config) -> Memory:
    memory_name = config["Memory"]["name"]

    if memory_name not in Memory_REGISTRY:
        console.print(f"[bold red]Unknown Memory hardware: {memory_name}. Available: {Memory_REGISTRY.keys()}[/bold red]")

    return Memory_REGISTRY[memory_name](config)