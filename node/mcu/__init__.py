from abstract.mcu import MCU
from .STM32 import STM32L476RG
from .ESP32 import ESP32_C6
from utils.information import console

MCU_REGISTRY  = {
    'STM32L476RG': STM32L476RG,
    'ESP32_C6': ESP32_C6,
}

def create_MCU(config) -> MCU:
    MCU_name = config["MCU"]["name"]

    if MCU_name not in MCU_REGISTRY:
        console.print(f"[bold red]Unknown MCU hardware: {MCU_name}. Available: {MCU_REGISTRY.keys()}[/bold red]")

    return MCU_REGISTRY[MCU_name](config)