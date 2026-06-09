
import numpy as np
from abc import ABC, abstractmethod

class InterferenceModel(ABC):
    def __init__(
        self,
        config,
    ):
        self.name = config['name']

    @abstractmethod
    def reception_overlap(self, **kwargs):
        pass

    @abstractmethod
    def capture_effect(self, **kwargs):
        pass
    
    @abstractmethod
    def evaluate(self, **kwargs):
        pass

    @abstractmethod
    def evaluate_all(self, **kwargs):
        pass

    def _SINR_dB(
            self,
            signal_dBm,
            interferers_dBm,
            noise_floor_dBm
        ):
        signal_mW       = self._dBm_to_mW(signal_dBm)
        noise_mW        = self._dBm_to_mW(noise_floor_dBm)
        interferer_mW   = sum(
                                self._dBm_to_mW(interferer) for interferer in interferers_dBm
                            )
        denominator_mW  = interferer_mW + noise_mW
        return self._mW_to_dBm(signal_mW) - self._mW_to_dBm(denominator_mW)

    def _dBm_to_mW(self, dBm):
        return 10.0 ** (dBm / 10.0)

    def _mW_to_dBm(self, mW):
        if mW <= 0:
            return -np.inf
        return 10.0 * np.log10(mW)