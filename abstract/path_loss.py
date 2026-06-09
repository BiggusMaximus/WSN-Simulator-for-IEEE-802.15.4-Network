
from abc import abstractmethod, ABC

class PathLossModel(ABC):
    def __init__(
        self,
        config
    ):
        self.config = config
        self.name = config["name"]
        self.params = config[self.name]
        self.frequency = self.params['frequency']
        self.c = self.params['c']


    @abstractmethod
    def path_loss(self, **kwargs) -> float:
        pass


