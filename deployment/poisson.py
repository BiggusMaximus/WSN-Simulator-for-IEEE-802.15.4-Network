import random
import math
from typing import List, Tuple
from node import Node
from abstract.deployment import Deployment


class PoissonLineCox(Deployment):
    def __init__(self, config):
        super().__init__(config)
        plc_cfg = config.get("PoissonLineCox", {})
        self.line_density = self.params["line_density"]
        self.point_linear_intensity = self.params["point_linear_intensity"]
        self.height_default = self.params['height_default']
        self.height_deviation = self.params['height_deviation']
        
    def _generate_position(self) -> List[Tuple[float, float, float]]:
        width, height, depth = self.area_dimensions

        positions = []

        R = 0.5 * math.sqrt(width * width + height * height)
    
        mean_number_of_lines = self.line_density * 2.0 * math.pi * R
        num_lines = _poisson(mean_number_of_lines)

        for _ in range(num_lines):
            # sample line parameters (chord method)
            theta = random.uniform(0.0, 2.0 * math.pi)
            p = random.uniform(0.0, R)
            q = math.sqrt(max(0.0, R * R - p * p))  # half-chord length
            chord_length = 2.0 * q

            # number of points on this chord
            mean_points_on_chord = self.point_linear_intensity * chord_length
            n_points = _poisson(mean_points_on_chord)

            for _ in range(n_points):
                # uniform along chord: U in [-1, 1]
                U = random.uniform(-1.0, 1.0)
                x_disk = p * math.cos(theta) + U * q * math.sin(theta)
                y_disk = p * math.sin(theta) - U * q * math.cos(theta)

                # translate disk-centered coords to rectangle coords (centered)
                x = x_disk + width / 2.0
                y = y_disk + height / 2.0

                # keep only points inside rectangle
                if 0.0 <= x <= width and 0.0 <= y <= height:
                    min_height = max(0, self.height_default * (1 -self.height_deviation))
                    max_height = self.height_default * (1 + self.height_deviation)
  
                    z = random.uniform(min_height, max_height)
                    positions.append((x, y, z))

        return positions

    def deploy_nodes(self) -> List[Node]:
        nodes = []

        for position in self.base_station_locations:
            base_station = self._create_node(self.base_station_id, tuple(position))
            nodes.append(base_station)
            self.base_station_id += 1
        
        positions = self._generate_position()
        for node_id in range(1, self.number_of_nodes + 1):
            # if generated fewer positions than requested, stop at available count (same simple behavior as Random)
            if node_id - 1 >= len(positions):
                break
            node = self._create_node(node_id, positions[node_id-1])
            nodes.append(node)
        
        self._attach_hardware_to_nodes(nodes)
        return nodes


# simple Poisson sampler (Knuth) used by the class above
def _poisson(lmbda: float) -> int:
    if lmbda <= 0:
        return 0
    L = math.exp(-lmbda)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1
