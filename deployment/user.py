import pandas as pd
from typing import List, Tuple
from node import Node
from abstract.deployment import Deployment


class UserInput(Deployment):
    def __init__(self, config):
        super().__init__(config)
        self.filename = self.params['FILE_INPUT']

    def _generate_position(self) -> List[Tuple[float, float, float]]:
        pass

    def deploy_nodes(self) -> List[Node]:
        nodes = []

        for position in self.base_station_locations:
            base_station = self._create_node(self.base_station_id, tuple(position))
            nodes.append(base_station)
            self.base_station_id += 1
        
        import pandas as pd
        
        df = pd.read_csv(self.filename)

        for row in df.index:
            data = df.iloc[row]
            x = data['x']
            y = data['y']
            z = data['z']
            id = data['id']
            

            node = self._create_node(id, (x, y, z))
            nodes.append(node)

        
        self._attach_hardware_to_nodes(nodes)
        return nodes
    
    

