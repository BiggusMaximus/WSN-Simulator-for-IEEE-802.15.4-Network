import random
from typing import Tuple
from abstract.node import Node
from abstract.rf import RF
from abstract.memory import Memory
from abstract.sensor import Sensor
from abstract.mcu import MCU

class HomogenousNode(Node):
    def __init__(
        self, 
        node_id: int,
        position: Tuple[float, float, float],
        node_type: str = "node",
        config=None
    ):
        super().__init__(
            node_id,
            position,
            node_type,
            config
        )

        self._initial_battery = self.compute_initial_battery()
        self._remaining_battery = self._initial_battery
    
    def attach_RF(self, rf: RF):
        self._rf = rf
    
    def attach_sensors(self, sensor: Sensor):
        self._sensors = sensor

    def attach_memory(self, memory: Memory):
        self._memory = memory

    def attach_mcu(self, mcu: MCU):
        self._mcu = mcu
    
    def compute_initial_battery(self):
        return self.config["Node"]["battery_capacity"]

class BaseStation(Node):
    def __init__(
        self, 
        node_id: int,
        position: Tuple[float, float, float],
        node_type: str = "base_station",
        config=None
    ):
        super().__init__(
            node_id,
            position,
            node_type,
            config
        )
        self.is_base_station = True
        self._initial_battery = self.compute_initial_battery()
        self._remaining_battery = self._initial_battery
    
    def attach_RF(self, rf: RF):
        self._rf = rf
    
    def attach_sensors(self, sensor: Sensor):
        self._sensors = sensor

    def attach_memory(self, memory: Memory):
        self._memory = memory

    def attach_mcu(self, mcu: MCU):
        self._mcu = mcu
    
    def compute_initial_battery(self):
        return 9999999

    

class HeterogenousNode(Node):
    def __init__(
        self, 
        node_id: int,
        position: Tuple[float, float, float],
        node_type: str = "node",
        config=None
    ):
        super().__init__(
            node_id,
            position,
            node_type,
            config
        )
        self._initial_battery = self.compute_initial_battery()
        self._remaining_battery = self._initial_battery()
    
    def attach_RF(self, rf: RF):
        self._rf = rf
    
    def attach_sensors(self, sensor: Sensor):
        self._sensors = sensor

    def attach_memory(self, memory: Memory):
        self._memory = memory

    def attach_mcu(self, mcu: MCU):
        self._mcu = mcu
    
    def compute_initial_battery(self):
        battery_capacity = self.config["Node"]["battery_capacity"]
        standard_deviation = self.config["Node"]["battery_deviation"]
        min_battery = max(0, battery_capacity * (1 -standard_deviation))
        max_battery = battery_capacity * (1 + standard_deviation)
        
        return random.uniform(min_battery, max_battery)
