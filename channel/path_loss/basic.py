import math
from abc import ABC, abstractmethod
from abstract.path_loss import PathLossModel


class LogDistance(PathLossModel):
    def __init__(
        self, config
    ):
        super().__init__(config)
        self.shadowing_deviation = self.params['shadowing_deviation']
        self.PL_d0 = self.params['PL_d0']
        self.d0 = self.params['d0']
        self.n = self.params['n']


    def path_loss(self, distance) -> float:
        if distance < self.d0:
            return self.path_loss_reference(distance)
        else:
            import random
            return self.PL_d0 + 10 * self.n * math.log10(distance/self.d0) + random.gauss(0, self.shadowing_deviation)
     
    def path_loss_reference(self, distance) -> float:
        return 20 * math.log10(
            4 * math.pi * self.frequency / self.c
        )


    