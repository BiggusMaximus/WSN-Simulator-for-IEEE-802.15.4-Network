
from abc import abstractmethod, ABC

class PathLossModel(ABC):
    def __init__(
        self,
        config
    ):
        self.config = config
        self.name = config["name"]
        self.params = config['params'][self.name]
        self.frequency = float(self.params['frequency'])
        self.c = float(self.params['c'])

        # Default shadowing std-dev; subclasses override as needed.
        # Set to 0 for models that handle their own shadowing internally
        # (e.g. LogDistance already adds Gaussian noise inside path_loss()).
        self.sigma_db: float = 0.0

    @abstractmethod
    def path_loss(self, **kwargs) -> float:
        pass

