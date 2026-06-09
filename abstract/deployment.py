# =====================================================================
#                    This program is used:
# =====================================================================
# 1. Create a deployment based on the user configuration
# 2. Assign the role of the sensor (base station or normal node)
# 3. Attach the hardware for the node

import random

from abc import ABC, abstractmethod
from typing import List, Tuple
from abstract.node import Node

from node.sensor import create_sensor
from node.rf import create_RF
from node.memory import create_memory
from node.mcu import create_MCU

class Deployment(ABC):
    def __init__(
        self,
        config,
    ):
        # Simulation configurations
        self.area_dimensions        = config["Simulation"]["area_dimensions"]
        self.number_of_nodes        = config["Simulation"]["number_of_nodes"]
        self.use_multiple_sensor    = config["Simulation"]["use_multiple_sensor"]
        self.is_homogenous          = config["Simulation"]["is_homogenous"]
        self.is_3d                  = config["Simulation"]["is_3d"]

        # Deployment configurations
        self.name                   = config["Deployment"]["name"]
        self.base_station_locations = config["Deployment"]["base_station_locations"]
        self.params                 = config["Deployment"]["params"][self.name]

        # Arbitrary values
        self.base_station_id        = 100000
        self.config                 = config
    
    @abstractmethod
    def deploy_nodes(self, **kwargs) -> List[Node]:
        pass

    @abstractmethod
    def _generate_position(self) -> List[Tuple[float, float, float]]:
        pass

    def _create_node(
        self, 
        node_id: int,
        position: tuple
    ) -> Node:
        from node import HomogenousNode, HeterogenousNode, BaseStation
        if node_id >= self.base_station_id:
            return BaseStation(node_id, position, 'base_station', self.config)

        if self.is_homogenous:
            return HomogenousNode(node_id, position, 'node', self.config)
        else:
            return HeterogenousNode(node_id, position, 'node', self.config)
    
    def _attach_hardware_to_nodes(
        self,
        nodes: List[Node]
    ):
        for node in nodes:
            # Attach RF module
            # if node.node_type != 'base_station':
            #     rf = create_RF(self.config)
            #     node.attach_RF(rf)
            rf      = create_RF(self.config)
            memory  = create_memory(self.config)
            mcu     = create_MCU(self.config)

            node.attach_RF(rf)
            node.attach_memory(memory)
            node.attach_mcu(mcu)

            if self.is_homogenous:
                sensor = create_sensor(self.config)
                node.attach_sensors(sensor)
            else:
                available_sensors = SENSOR_REGISTRY.keys()
                sensor_name = random.choice(available_sensors)
                sensor = create_sensor(self.config)