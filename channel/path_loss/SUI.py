import math
from abc import ABC, abstractmethod
from typing import Dict, Any
from abstract.channel import ChannelModel
from abstract.node import Node

class SUI_TypeA(ChannelModel):
    def __init__(self, config):
        super().__init__(config)
        self.a = 4.6
        self.b = 0.0075
        self.b = 12.6
    
    def path_loss(self, sender_node: Node, other_node: Node) -> float:
        # Path loss exponent
        distance = sender_node.distance(other_node)
        gamma = self.a - self.b * sender_height + self.c_ / sender_height

        # Frequency correction (GHz)
        f_GHz = self.frequency / 1e9
        X_f = 6 * math.log10(f_GHz / 2.0)

        # Receiver height correction
        X_h = -10.8 * math.log10(receiver_height / 2.0)

        # Reference path loss at d0
        PL_d0 = 20 * math.log10(4 * math.pi * self.d0 * self.frequency / self.c)

        # Total path loss
        PL = PL_d0 + 10 * gamma * math.log10(distance / self.d0) + X_f + X_h

        # Add log-normal shadowing
        shadowing = random.gauss(0, self.shadowing_deviation)
        return PL + shadowing
     
    def path_loss_reference(self, distance) -> float:
        return 20 * math.log10(
            4 * math.pi * self.frequency / self.c
        )