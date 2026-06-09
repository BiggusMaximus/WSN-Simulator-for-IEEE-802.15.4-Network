# =====================================================================
#                    This program is used:
# =====================================================================
# 1. Attach the hardware for the node
# 2. Assign node ID, position and role for the node


import math
from abc import ABC, abstractmethod
from typing import Tuple
from abstract.rf import RF
from abstract.memory import Memory
from abstract.sensor import Sensor
from abstract.mcu import MCU

class Node(ABC):
    def __init__(
        self,
        id: int,
        position: Tuple[float, float, float],
        node_type: str = "node",
        config=None
    ):
        
        self.id = id
        self.position = position
        self.node_type = node_type
        self.config = config


        # Hardware components
        self._rf = None
        self._sensors = None
        self._memory = None
        self._mcu = None
        self._packet = None

        # Routing protocol parameters
        self.cluster_id = -1
        self.is_cluster_head = False
        self.is_orphan = False
        self.is_base_station = False
        self.neighbor_table = {}   
        self.degree = 0 

        self.alive = True
        self.eligible_round = 0
    

    
    @abstractmethod
    def attach_RF(self, RF: RF):
        pass

    @abstractmethod
    def attach_sensors(self, sensor: Sensor):
        pass

    @abstractmethod
    def attach_memory(self, memory: Memory):
        pass

    @abstractmethod
    def attach_mcu(self, mcu: MCU):
        pass
    

    @abstractmethod
    def compute_initial_battery(self):
        pass

    def distance(self, other_node: Tuple[float, float, float]) -> float:
        return math.dist(self.position, other_node)
    
    def set_cluster_head(self, cluster_id: int):
        self.is_cluster_head = True
        self.is_orphan = False
        self.cluster_id = cluster_id
        self.node_type = "cluster_head"
    
    def set_orphan(self):
        self.is_orphan = True
        self.is_cluster_head = False
        self.cluster_id = -1
        self.node_type = "orphan_node"
    
    def set_member(self, cluster_id: int):
        self.is_cluster_head = False
        self.is_orphan = False
        self.cluster_id = cluster_id
        self.node_type = "member_node"

    def reset_network_state(self):
        self.cluster_id = -1
        self.is_cluster_head = False
        self.is_orphan = False
        self.eligible_round = 0
        self.N_C = 0
        self.data_received = 0

        if self._remaining_battery < self._initial_battery * 0.1:
            self.node_type = "dead_node"
            self.alive = False

    def _remaining_energy(self, consumed_energy: float):
        if self._remaining_battery > 0.1 * self._initial_battery and self.alive and not self.is_base_station:
            self._remaining_battery -= consumed_energy
        else:
            self.alive = False


    
