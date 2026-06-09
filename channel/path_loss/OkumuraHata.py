import math
from abc import ABC, abstractmethod
from typing import Dict, Any
from abstract.path_loss import PathLossModel

from abstract.node import Node

class SUI_TypeA(PathLossModel):
    '''
        SUI model suitable for
            cell < 10 km
            Receiver Height (15m < h < 40m)
            Receiver Height (15m < h < 40m)
    
    '''
    def __init__(self, config):
        super().__init__(config)
        self.a = 4.6
        self.b = 0.0075
        self.c = 12.6
    
    def path_loss(self, sender_node: Node, other_node: Node) -> float:
        # Path loss exponent
        distance = sender_node.distance(other_node)
        sender_height = sender_node.position[2]
        receiver_height = other_node.position[2]

        gamma = self.a - self.b * sender_height + self.c_ / sender_height

        L_bf = 6 * math.log10(self.frequency / 2000)
        L_bh = -10.8 * math.log10(receiver_height / 2.0)


        # Total path loss
        PL = PL_d0 + 10 * gamma * math.log10(distance / self.d0) + X_f + X_h

        # Add log-normal shadowing
        shadowing = random.gauss(0, self.shadowing_deviation)
        return PL + shadowing
     
    def path_loss_reference(self, distance) -> float:
        return 20 * math.log10(
            4 * math.pi * self.frequency / self.c
        )


class Ericsson_Urban(ChannelModel):
    def __init__(self, config):
        super().__init__(config)
        self.a0 = 36.2
        self.a1 = 30.2
        self.a2 = 12.0
        self.a3 = 0.1

    def path_loss(self, sender_node: Node, other_node: Node) -> float:
        distance = sender_node.distance(other_node)
        sender_height = sender_node.position[2]
        receiver_height = other_node.position[2]


        # Frequency in MHz
        f_MHz = self.frequency / 1e6

        # Frequency correction term
        g_f = 44.49 * math.log10(f_MHz) - 4.78 * (math.log10(f_MHz)) ** 2

        # Path loss according to Ericsson model
        PL = (
            self.a0
            + self.a1 * math.log10(distance)
            + self.a2 * math.log10(sender_height)
            + self.a3 * math.log10(sender_height) * math.log10(distance)
            - 3.2 * (math.log10(11.75 * receiver_height)) ** 2
            + g_f
        )

        # Add log-normal shadowing
        shadowing = random.gauss(0, self.shadowing_deviation)
        return PL + shadowing
    
    def path_loss_reference(self, distance) -> float:
        return 20 * math.log10(
            4 * math.pi * self.frequency / self.c
        )
    
    