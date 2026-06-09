from abc import ABC, abstractmethod
from .packet import PacketModel

class RF(ABC):
    def __init__(
            self,
            config
    ):
        RF_name = config['RF']['name']
        self.params = config['RF']['params'][RF_name]
        self._packet = None


        """
            Different RF modes:
                1. (TX) Transmit (Unicast/Broadcast)
                2. (RX) Receiving (Listening)
                3. (Sleep) Sleep
        """
        self.mode = "transmit"

    @abstractmethod
    def setup_packet_model():
        pass

    @abstractmethod
    def overlaps(self, **kwargs):
        pass
    
    @abstractmethod
    def packet_duration(self, **kwargs) -> float:
        pass
