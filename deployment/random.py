import random
from typing import List, Tuple
from node import Node
from abstract.deployment import Deployment


class Random(Deployment):
    def __init__(self, config):
        super().__init__(config)
        self.height_default = self.params['height_default']
        self.height_deviation = self.params['height_deviation']
        self.rng = random.Random(42)


    def _generate_position(self) -> List[Tuple[float, float, float]]:
        width, height, depth = self.area_dimensions
        
        positions = []

        for _ in range(self.number_of_nodes):
            x = self.rng.uniform(0, width)
            y = self.rng.uniform(0, height)
            z = self.rng.uniform(0, depth) if self.is_3d else 5
            positions.append((x, y, z))

        return positions

    def deploy_nodes(self) -> List[Node]:
        """
            The nodes matrix should look like this:
            - with row or column have the same value as node-id.
        
                 _  BS   1   2   .   .   .   N _
            BS  |                               |
            1   |                               |
            2   |                               |
            .   |                               |
            .   |                               |
            .   |                               |
            N   |_                             _|

        
        """
        nodes = []

        for position in self.base_station_locations:
            base_station = self._create_node(self.base_station_id, tuple(position))
            nodes.append(base_station)
            self.base_station_id += 1
        
        positions = self._generate_position()
        for node_id in range(1, self.number_of_nodes + 1):
            node = self._create_node(node_id, positions[node_id-1])
            nodes.append(node)
        
        self._attach_hardware_to_nodes(nodes)
        return nodes
    
    

