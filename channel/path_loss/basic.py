import numpy as np
from abc import ABC, abstractmethod
from abstract.path_loss import PathLossModel


class LogDistance(PathLossModel):
    def __init__(self, config):
        super().__init__(config)
        self.shadowing_deviation = self.params['shadowing_deviation']
        self.PL_d0 = self.params['PL_d0']
        self.d0 = float(self.params['d0'])
        self.n = float(self.params['n'])

    def path_loss(self, distance):
        """
        Compute path loss for a single distance or a NumPy array of distances.
        Returns a float if input is scalar, otherwise a NumPy array.
        """
        # Ensure we work with a NumPy array
        dist = np.asarray(distance, dtype=float)
        scalar_input = dist.ndim == 0

        # Boolean mask: True where distance < d0
        mask = dist < self.d0

        # Pre-allocate output array
        pl = np.empty_like(dist)

        # ---- Distances >= d0 ----
        n_large = np.sum(~mask)
        if n_large > 0:
            # Vectorised log-distance with random shadowing (one value per element)
            pl[~mask] = (self.PL_d0
                         + 10 * self.n * np.log10(dist[~mask] / self.d0)
                         + np.random.normal(0, self.shadowing_deviation, size=n_large))

        # ---- Distances < d0 ----
        if np.any(mask):
            # Use the reference loss (vectorised version)
            pl[mask] = self.path_loss_reference(dist[mask])

        # Return a scalar if input was scalar, otherwise the array
        return float(pl.item()) if scalar_input else pl

    def path_loss_reference(self, distance):
        """
        Reference path loss for distances below d0.
        Handles both scalar and array inputs.
        """
        dist = np.asarray(distance, dtype=float)

        # The original formula is independent of distance; compute once
        ref_loss = 20 * np.log10(4 * np.pi * self.frequency / self.c)

        # Return constant or an array filled with that constant
        if dist.ndim == 0:
            return ref_loss
        else:
            return np.full_like(dist, ref_loss, dtype=float)