from abc import ABC, abstractmethod

'''
    Sensor hardware related functionalities:
    1. Sensing data
'''
class Sensor(ABC):
    def __init__(
        self,
        config,
    ):
        self.name = config["Sensor"]["name"]
        self.params = config["Sensor"]['params'][self.name]
        self.data_size = self.params["data_size"]
        self.V_sensing = self.params["V_sensing"]
        self.I_sensing = self.params["I_sensing"]
        self.T_sensing = self.params["T_sensing"]
    
    @abstractmethod
    def energy_sensing(self) -> float:
        pass
    
    @abstractmethod
    def power_sensing(self) -> float:
        pass