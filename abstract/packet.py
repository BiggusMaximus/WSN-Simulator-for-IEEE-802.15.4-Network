from abc import abstractmethod, ABC
import numpy as np

class PacketModel(ABC):
    def __init__(
        self,
        config
    ):
        self.config = config
        self.name = config["Packet"]["name"]
        self.params = config["Packet"]["params"][self.name]


    