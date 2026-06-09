# channel/itu_p1411.py
import math
import numpy as np
from abc import ABC, abstractmethod
from abstract.path_loss import PathLossModel
from scipy.stats import norm

class ITU_P1411(PathLossModel):
    def __init__(self, config):
        super().__init__(config)
        self.f_MHz = float(self.params['frequency']) / 1e6
        self.p = self.params.get("p", 50)
        self.urban_class = self.params.get("urban_class", "urban")
        self.sigma_db = float(self.params.get("shadowing_sigma", 7.0))
        self.w = 20.0
        
        # Urban lookup table
        self.Lurban = {
            "suburban": 0.0,
            "urban": 6.8,
            "dense": 2.3
        }[self.urban_class]
        
        # Cache for deterministic path loss
        self._deterministic_cache = {}
        
        # Precompute d_LoS_boundary once
        self._d_LoS_boundary = self._compute_d_LoS_boundary()
        
        # Precompute location corrections
        self._L_LoS_loc_corr_val = self._compute_L_LoS_loc_corr()
        self._L_NLoS_loc_corr_val = self._compute_L_NLoS_loc_corr()

    def _compute_d_LoS_boundary(self):
        if self.p < 45:
            return 10 ** ((64 - 212*(self.p/100)) / (45 - 79.2*(self.p/100)))
        else:
            return 79.2 * (self.p/100) - 70

    def _compute_L_LoS_loc_corr(self):
        return 1.5624 * 7.0 * (np.sqrt(-2*np.log(1 - self.p/100.0)) - 1.1774)

    def _compute_L_NLoS_loc_corr(self):
        return 7.0 * norm.ppf(self.p/100.0)

    # def path_loss(self, d_m):
    #     """Compute only deterministic path loss (no shadowing)"""
    #     # Check cache first
    #     if d_m in self._deterministic_cache:
    #         return self._deterministic_cache[d_m]
        
    #     d_los = self._d_LoS_boundary
    #     d_km = d_m * 1e-3
        
    #     # Compute LoS path loss
    #     L_los = 32.45 + 20 * math.log10(self.f_MHz) + 20 * math.log10(d_km) + self._L_LoS_loc_corr_val
        
    #     # Compute NLoS path loss
    #     L_nlos = (9.5 + 45 * math.log10(self.f_MHz) + 
    #               40 * math.log10(d_km) + self.Lurban + self._L_NLoS_loc_corr_val)
        
    #     # Apply interpolation
    #     if d_m < d_los:
    #         result = L_los
    #     elif d_m > d_los + self.w:
    #         result = L_nlos
    #     else:
    #         # Edge values
    #         L_los_edge = (32.45 + 20 * math.log10(self.f_MHz) + 
    #                       20 * math.log10(d_los * 1e-3) + self._L_LoS_loc_corr_val)
    #         L_nlos_edge = (9.5 + 45 * math.log10(self.f_MHz) + 
    #                        40 * math.log10((d_los + self.w) * 1e-3) + 
    #                        self.Lurban + self._L_NLoS_loc_corr_val)
    #         result = L_los_edge + (d_m - d_los) * ((L_nlos_edge - L_los_edge) / self.w)
        
    #     # Cache the result
    #     self._deterministic_cache[d_m] = result
    #     return result

    def path_loss(self, d_m):
        """Scalar interface – can remain for backward compatibility."""
        if isinstance(d_m, np.ndarray):
            return self.path_loss_array(d_m)
        # scalar logic (with caching) unchanged
        if d_m in self._deterministic_cache:
            return self._deterministic_cache[d_m]
        result = self.path_loss_array(np.array([d_m]))[0]
        self._deterministic_cache[d_m] = result
        return result
    
    def path_loss_array(self, d_m: np.ndarray) -> np.ndarray:
        """
        Compute deterministic path loss for an array of distances d_m (meters).
        Returns array of same shape.
        """
        d_km = d_m * 1e-3
        f_MHz = self.f_MHz
        d_los = self._d_LoS_boundary
        w = self.w

        # LoS formula
        L_los = 32.45 + 20 * np.log10(f_MHz) + 20 * np.log10(d_km) + self._L_LoS_loc_corr_val

        # NLoS formula
        L_nlos = (9.5 + 45 * np.log10(f_MHz) +
                  40 * np.log10(d_km) + self.Lurban + self._L_NLoS_loc_corr_val)

        # Edge values for interpolation region
        L_los_edge = (32.45 + 20 * np.log10(f_MHz) +
                      20 * np.log10(d_los * 1e-3) + self._L_LoS_loc_corr_val)
        L_nlos_edge = (9.5 + 45 * np.log10(f_MHz) +
                       40 * np.log10((d_los + w) * 1e-3) +
                       self.Lurban + self._L_NLoS_loc_corr_val)

        # Vectorised condition
        result = np.where(
            d_m < d_los,
            L_los,
            np.where(
                d_m > d_los + w,
                L_nlos,
                L_los_edge + (d_m - d_los) * ((L_nlos_edge - L_los_edge) / w)
            )
        )
        return result

    def get_shadowing(self, size=1):
        """Get random shadowing values"""
        return np.random.normal(0, self.sigma_db, size)

    # Keep original path_loss for backward compatibility
    # def path_loss(self, d_m):
    #     """Full path loss with shadowing"""
    #     pl_det = self.deterministic_path_loss(d_m)
        
    #     if isinstance(d_m, np.ndarray):
    #         shadowing = np.random.normal(0, self.sigma_db, d_m.shape)
    #         return pl_det + shadowing
    #     else:
    #         return pl_det + np.random.normal(0, self.sigma_db)