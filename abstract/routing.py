
"""

    The data is stored in nodes.pkl, so then the user can analyze manually 

"""


from abc import ABC, abstractmethod
import os
import numpy as np
from utils.information import console


class RoutingProtocol(ABC):
    def __init__(self, config, nodes, channel):
        self.config = config
        self.routing_name = config['Routing']['name']
        self.params = config['Routing']['params'][self.routing_name]
        self.nodes = nodes
        self.channel = channel
        self.console = console
    

        self.results = {}

    @abstractmethod
    def run(self, **kwargs):
        pass

    @abstractmethod
    def empty_metrics(self):
        pass

    @abstractmethod
    def saving_metrics(self):
        pass


    def _update_energy_mask(self):
        """Update which nodes are alive based on energy"""

        # Extract arrays once (faster than repeated attribute access)
        try:
            remaining = np.fromiter(
                (float(n._remaining_battery) for n in self.nodes),
                dtype=float
            )
        except Exception as e:
            for i, n in enumerate(self.nodes):
                if isinstance(n._remaining_battery, np.ndarray):
                    print(
                        f"Node {i} battery is array!",
                        n._remaining_battery.shape,
                        n._remaining_battery
                    )
        initial = np.fromiter(
            (n._initial_battery for n in self.nodes),
            dtype=float
        )
        # initial[0] = 0
        # remaining[0] = 0

        is_bs = np.fromiter(
            (n.is_base_station for n in self.nodes),
            dtype=bool
        )
       
        # Vectorized alive mask
        self.energy_adjacency = (remaining > 0.1 * initial)
        self.energy_mask = (remaining > 0.1 * initial) & (~is_bs)

        # Total energy of alive nodes (vectorized)
        self._remaining_energy = remaining[self.energy_mask & (~is_bs)]
        self.total_energy_alive = np.sum(self.energy_mask)
        self.energy_deviation = np.std(self._remaining_energy) 
        self.energy_mean = np.mean(self._remaining_energy) 

        # Get dead nodes
        dead_indices = np.where(~self.energy_adjacency)[0]

        if dead_indices.size > 0:
            self.adjacency_matrix[dead_indices, :] = False
            self.adjacency_matrix[:, dead_indices] = False

    def compute_energy_sensing(self):
        total_energy_sensing = 0
        for node in self.nodes:
            energy_sensing = node._sensors.energy_sensing() + node._mcu.energy_sensing(node._sensors.T_sensing)
            node._remaining_energy(energy_sensing)
            total_energy_sensing += energy_sensing
        return total_energy_sensing

    def compute_energy_logging(self):
        total_energy_logging = 0
        for node in self.nodes:
            energy_logging = node._memory.energy_writting_and_logging() + node._mcu.energy_writting_and_logging(
                    node._memory.T_write + node._memory.T_read
                )
            node._remaining_energy(energy_logging)
            total_energy_logging += energy_logging
        return total_energy_logging
