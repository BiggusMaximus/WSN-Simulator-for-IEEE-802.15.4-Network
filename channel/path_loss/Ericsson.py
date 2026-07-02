"""
Ericsson Urban path loss model.

Reference:
    Ericsson internal model, widely described in:
    T. S. Rappaport, "Wireless Communications: Principles and Practice,"
    2nd ed., Prentice Hall, 2002, §3.7.
    Also in A. F. Molisch, "Wireless Communications," Wiley, 2005.

Model
-----
    PL = a0 + a1·log10(d) + a2·log10(h_BS)
         + a3·log10(h_BS)·log10(d)
         − 3.2·(log10(11.75·h_MS))²
         + g(f)

    g(f) = 44.49·log10(f_MHz) − 4.78·(log10(f_MHz))²

Urban coefficients:  a0=36.2, a1=30.2, a2=−12.0, a3=0.1

Applicability
-------------
  * Macro-cell environments (d : 1 – 20 km)
  * Frequency  f    : 150 MHz – 1.5 GHz (original), extended to 2.4 GHz here
  * BS height h_BS  : 30 – 200 m
  * MS height h_MS  : 1  – 10  m

  **Note:** This model is designed for macro-cell scenarios with tall base
  stations.  For short-range WSN deployments (h_BS ~ 5 m, d < 500 m) it
  will produce over-estimated path loss values.  It is included for
  comparative analysis; prefer ITU_P1411 or SUI for WSN.

Usage in simulation.yaml
------------------------
    PathLoss:
      name: EricssonUrban
      EricssonUrban:
        frequency: 2.4e9
        c: 3e8
        h_BS: 30.0             # base-station height [m]
        h_MS: 1.5              # mobile height [m]
        shadowing_sigma: 8.0   # log-normal shadowing std-dev [dB]
"""

import numpy as np
from abstract.path_loss import PathLossModel


class EricssonUrban(PathLossModel):
    """Ericsson Urban empirical path loss model."""

    # Urban environment coefficients
    _A0 =  36.2
    _A1 =  30.2
    _A2 = -12.0
    _A3 =   0.1

    def __init__(self, config):
        super().__init__(config)

        self.h_BS     = float(self.params.get("h_BS",           30.0))
        self.h_MS     = float(self.params.get("h_MS",            1.5))
        self.sigma_db = float(self.params.get("shadowing_sigma",  8.0))

        # Pre-compute frequency-dependent term g(f)  (constant per run)
        f_MHz = self.frequency / 1e6
        self._g_f = (
            44.49 * np.log10(f_MHz)
            - 4.78 * (np.log10(f_MHz)) ** 2
        )

        # Pre-compute height-dependent term (constant per run)
        self._h_MS_term = -3.2 * (np.log10(11.75 * self.h_MS)) ** 2
        self._h_BS_A2   = self._A2 * np.log10(self.h_BS)

    # ------------------------------------------------------------------
    def path_loss(self, distance) -> float:
        """Scalar or ndarray deterministic path loss [dB]."""
        if isinstance(distance, np.ndarray):
            return self.path_loss_array(distance)

        if distance <= 0:
            return 0.0

        return (
            self._A0
            + self._A1       * np.log10(distance)
            + self._h_BS_A2
            + self._A3       * np.log10(self.h_BS) * np.log10(distance)
            + self._h_MS_term
            + self._g_f
        )

    def path_loss_array(self, d_m: np.ndarray) -> np.ndarray:
        """Vectorised path loss for the entire distance matrix."""
        with np.errstate(divide="ignore", invalid="ignore"):
            log_d = np.where(d_m > 0, np.log10(np.maximum(d_m, 1e-9)), 0.0)

        PL = np.where(
            d_m <= 0,
            0.0,
            self._A0
            + self._A1       * log_d
            + self._h_BS_A2
            + self._A3       * np.log10(self.h_BS) * log_d
            + self._h_MS_term
            + self._g_f,
        )
        return PL
