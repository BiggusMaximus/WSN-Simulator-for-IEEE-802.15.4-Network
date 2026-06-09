from abstract.packet import PacketModel
from .IEEE import IEEE_802_15_4
from utils.information import console

PACKET_REGISTRY  = {
    'IEEE_802_15_4': IEEE_802_15_4,
}

def create_packet(config) -> PacketModel:
    packet_name = config["Packet"]["name"]

    if packet_name not in PACKET_REGISTRY:
        console.print(f"[bold red]Unknown Packet hardware: {packet_name}. Available: {PACKET_REGISTRY.keys()}[/bold red]")

    return PACKET_REGISTRY[packet_name](config)