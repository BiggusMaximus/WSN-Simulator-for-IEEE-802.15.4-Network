from abc import ABC, abstractmethod

'''
    MCU related functionalities:
    1. Processing data
    2. Wakeup
'''
class MCU(ABC):
    def __init__(
        self,
        config,
    ):
        mcu_name = config['MCU']['name']
        self.params = config['MCU']['params'][mcu_name]
    
    @abstractmethod
    def energy_transmit(duration):
        pass

    @abstractmethod
    def energy_receive(duration):
        pass

    @abstractmethod
    def energy_sleep(duration):
        pass
    
    @abstractmethod
    def energy_sensing(duration):
        pass
    
    @abstractmethod
    def energy_writting_and_logging(duration):
        pass
    