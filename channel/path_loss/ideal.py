"""
Ideal (free-space, no path loss) channel model.

Returns 0 dB path loss for every distance and sets sigma_db = 0
so no shadowing is added in ChannelModel._update_parameter().
This gives every node maximum RSSI regardless of distance, which
is useful as a baseline / upper-bound reference simulation.
"""

import numpy as np
from abstract.path_loss import PathLossModel


class Ideal(PathLossModel):
    """
    Zero path-loss model.

    RSSI = P_TX + G_TX + G_RX  (no subtracted path loss, no shadowing).

    Config entry (simulation.yaml):
        PathLoss:
          name: Ideal
          Ideal:
            frequency: 2.4e9   # kept for interface compatibility, not used
            c: 3e8             # kept for interface compatibility, not used
    """

    def __init__(self, config):
        super().__init__(config)
        # No shadowing — ChannelModel._update_parameter() uses self._path_loss.sigma_db
        self.sigma_db = 0.0

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------
    def path_loss(self, distance) -> float:
        """
        Return 0 dB path loss for any distance (scalar or ndarray).
        The ChannelModel precomputes the entire distance matrix at once,
        so we must handle both a scalar float and a 2-D numpy array.
        """
        if isinstance(distance, np.ndarray):
            return np.zeros_like(distance, dtype=float)
        return 0.0
