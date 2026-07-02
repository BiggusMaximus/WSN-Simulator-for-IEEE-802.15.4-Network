"""
Stanford University Interim (SUI) path loss models.

Reference:
    V. Erceg et al., "An empirically based path loss model for wireless
    channels in suburban environments," IEEE JSAC, vol. 17, no. 7, 1999.

Terrain categories
------------------
  Type A – Hilly terrain with moderate-to-heavy tree density.
           Gives the highest (most pessimistic) path loss.
  Type B – Hilly terrain with light tree density, or flat terrain
           with moderate-to-heavy tree density.
  Type C – Flat terrain with light tree density (most optimistic).

Model applicability
-------------------
  * Designed for fixed broadband wireless access (FBWA / 802.16).
  * Base-station height h_BS : 10 – 80 m
  * Subscriber height   h_MS :  2 –  10 m
  * Frequency           f    : 1.9 – 11 GHz
  * Reference distance  d0   : 100 m (standard)
  * Range               d    : d0 … ~10 km

For short-range WSN deployments (h_BS ~ 5 m, d < 200 m) the model still
produces physically meaningful relative path-loss gradients; absolute
values should be treated as conservative upper bounds.

Usage in simulation.yaml
------------------------
    PathLoss:
      name: SUI_TypeA          # or SUI_TypeB / SUI_TypeC
      SUI_TypeA:
        frequency: 2.4e9
        c: 3e8
        d0: 100
        h_BS: 5.0              # base-station (transmitter) height [m]
        h_MS: 2.0              # mobile/subscriber (receiver) height [m]
        shadowing_sigma: 8.2   # log-normal shadowing std-dev [dB]
"""

import numpy as np
from abstract.path_loss import PathLossModel


# ---------------------------------------------------------------------------
# SUI terrain coefficients
# ---------------------------------------------------------------------------
_SUI_COEFFICIENTS = {
    #         a       b        c
    "TypeA": (4.6,  0.0075, 12.6),   # most pessimistic
    "TypeB": (4.0,  0.0065, 17.1),
    "TypeC": (3.6,  0.0050, 20.0),   # most optimistic
}


class _SUIBase(PathLossModel):
    """
    Internal base shared by SUI Type A / B / C.
    Subclasses only differ in the (a, b, c) terrain coefficients.
    """

    _TERRAIN: str = NotImplemented   # set by each subclass

    def __init__(self, config):
        super().__init__(config)
        a, b, c_coef = _SUI_COEFFICIENTS[self._TERRAIN]
        self._a = a
        self._b = b
        self._c = c_coef

        self.d0          = float(self.params.get("d0",          100.0))
        self.h_BS        = float(self.params.get("h_BS",          5.0))
        self.h_MS        = float(self.params.get("h_MS",          2.0))
        self.sigma_db    = float(self.params.get("shadowing_sigma", 8.2))

        # Path-loss exponent γ (depends only on h_BS → constant per run)
        self._gamma = self._a - self._b * self.h_BS + self._c / self.h_BS

        # Frequency-correction term X_f [dB]  (constant per run)
        f_MHz = self.frequency / 1e6
        self._X_f = 6.0 * np.log10(f_MHz / 2000.0)

        # Height-correction term X_h [dB]  (Type A & B use -10.8, Type C uses -20)
        self._X_h = self._height_correction(self.h_MS)

        # Reference path loss at d0 [dB]
        self._PL_d0 = 20.0 * np.log10(
            4.0 * np.pi * self.d0 * self.frequency / self.c
        )

    # ------------------------------------------------------------------
    def _height_correction(self, h_MS: float) -> float:
        """
        Receiver-height correction.
        Type A and B use −10.8 · log10(h_MS / 2).
        Subclasses override for Type C (−20 · log10(h_MS / 2)).
        """
        return -10.8 * np.log10(h_MS / 2.0)

    # ------------------------------------------------------------------
    def path_loss(self, distance) -> float:
        """
        Scalar or ndarray deterministic path loss [dB].
        Shadowing is added separately by ChannelModel._update_parameter().
        """
        if isinstance(distance, np.ndarray):
            return self.path_loss_array(distance)

        if distance <= 0:
            return 0.0
        if distance < self.d0:
            # Below reference distance: free-space reference
            return self._PL_d0

        return (
            self._PL_d0
            + 10.0 * self._gamma * np.log10(distance / self.d0)
            + self._X_f
            + self._X_h
        )

    def path_loss_array(self, d_m: np.ndarray) -> np.ndarray:
        """Vectorised path loss for the entire distance matrix."""
        with np.errstate(divide="ignore", invalid="ignore"):
            log_ratio = np.where(d_m > self.d0, np.log10(d_m / self.d0), 0.0)

        PL = np.where(
            d_m <= 0,
            0.0,
            np.where(
                d_m < self.d0,
                self._PL_d0,
                self._PL_d0
                + 10.0 * self._gamma * log_ratio
                + self._X_f
                + self._X_h,
            ),
        )
        return PL


# ---------------------------------------------------------------------------
# Public model classes
# ---------------------------------------------------------------------------

class SUI_TypeA(_SUIBase):
    """
    SUI Type A — Hilly with moderate-to-heavy tree density.
    Highest path-loss terrain category; conservative (pessimistic) baseline.
    """
    _TERRAIN = "TypeA"


class SUI_TypeB(_SUIBase):
    """
    SUI Type B — Hilly with light trees, or flat with moderate trees.
    Intermediate terrain category.
    """
    _TERRAIN = "TypeB"


class SUI_TypeC(_SUIBase):
    """
    SUI Type C — Flat terrain with light tree density.
    Lowest path-loss (optimistic) terrain category.
    Uses a different height-correction coefficient (−20 instead of −10.8).
    """
    _TERRAIN = "TypeC"

    def _height_correction(self, h_MS: float) -> float:
        return -20.0 * np.log10(h_MS / 2.0)
