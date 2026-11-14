"""Difference-stamp providers used by the focus-curve dial."""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from astropy.time import Time


class StampProvider(ABC):
    """Source of star-subtracted image stamps centered at a requested sky position."""

    @abstractmethod
    def get_diff_stamp(self, ra_deg: float, dec_deg: float, t: Time) -> np.ndarray | None:
        """Return epoch-t1 minus template image, or None when no cutout is available."""


class SyntheticProvider(StampProvider):
    """Deterministic synthetic sky with static stars removed by template subtraction."""

    def __init__(self, body_ra_deg: float, body_dec_deg: float, *, pixel_scale_arcsec: float = 6.15,
                 stamp_size: int = 64, seed: int = 42, flux: float = 160.0):
        self.body_ra_deg = float(body_ra_deg)
        self.body_dec_deg = float(body_dec_deg)
        self.pixel_scale_arcsec = float(pixel_scale_arcsec)
        self.stamp_size = int(stamp_size)
        self.flux = float(flux)
        rng = np.random.default_rng(seed)
        self._stars = [(float(rng.uniform(-30, 30)), float(rng.uniform(-30, 30)),
                        float(rng.uniform(10, 80))) for _ in range(90)]

    def _render(self, ra_deg: float, dec_deg: float, *, include_body: bool, noise_seed: int) -> np.ndarray:
        n = self.stamp_size
        yy, xx = np.mgrid[:n, :n]
        cx = cy = (n - 1) / 2
        image = np.zeros((n, n), dtype=float)
        # Identical static-star rendering in both epochs makes the template subtraction exact.
        for dx, dy, flux in self._stars:
            image += flux * np.exp(-((xx - cx - dx) ** 2 + (yy - cy - dy) ** 2) / (2 * 1.2 ** 2))
        if include_body:
            dra = ((self.body_ra_deg - ra_deg + 180) % 360 - 180) * np.cos(np.radians(dec_deg))
            dx = -dra * 3600 / self.pixel_scale_arcsec
            dy = (self.body_dec_deg - dec_deg) * 3600 / self.pixel_scale_arcsec
            image += self.flux * np.exp(-((xx - cx - dx) ** 2 + (yy - cy - dy) ** 2) / (2 * 1.2 ** 2))
        image += np.random.default_rng(noise_seed).normal(0, 0.8, image.shape)
        return image

    def get_diff_stamp(self, ra_deg: float, dec_deg: float, t: Time) -> np.ndarray:
        epoch = self._render(ra_deg, dec_deg, include_body=True, noise_seed=1)
        template = self._render(ra_deg, dec_deg, include_body=False, noise_seed=2)
        return epoch - template


class SpherexProvider(StampProvider):
    """SPHEREx cutout adapter placeholder; implement with archive cutouts and template epochs."""

    def get_diff_stamp(self, ra_deg: float, dec_deg: float, t: Time) -> np.ndarray | None:
        raise NotImplementedError("SPHEREx cutout retrieval and epoch-template subtraction are not implemented yet.")
