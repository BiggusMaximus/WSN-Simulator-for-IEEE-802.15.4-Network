from abstract.routing import RoutingProtocol
from utils.information import console

from .direct import DirectUnslottedCSMA

ROUTING_PROTOCOL_REGISTRY = {
    'DirectUnslottedCSMA':  DirectUnslottedCSMA,
}

def create_routing_protocol(config, nodes, channel) -> RoutingProtocol:
    name = config['Routing']['name']
    if name not in ROUTING_PROTOCOL_REGISTRY:
        console.print(
            f"[bold red]Unknown Routing Protocol: {name}. "
            f"Available: {list(ROUTING_PROTOCOL_REGISTRY.keys())}[/bold red]"
        )
    return ROUTING_PROTOCOL_REGISTRY[name](config, nodes, channel)
