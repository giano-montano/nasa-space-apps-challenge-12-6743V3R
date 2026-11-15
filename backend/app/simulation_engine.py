"""
Physical Simulation Engine for SPHEREx Astronomical Observations.
Generates realistic multi-epoch, multi-detector FITS/pixel arrays
with point-spread functions (PSF), Poisson photon noise, and proper motion.
"""

import math
import numpy as np
from typing import Dict, Any, List, Tuple
from .astronomical_data import TARGET_CATALOG, find_nearest_target, generate_lightcurve


def generate_field_frames(
    ra: float,
    dec: float,
    fov_arcmin: float = 5.0,
    detector_id: int = 1,
    resolution: int = 512,
    num_epochs: int = 8,
    stack_all_detectors: bool = False
) -> Dict[str, Any]:
    """
    Generates time-series of astronomical observation frames for given sky patch.
    Returns:
        Dict with frame metadata, numpy data arrays, and discovery candidates.
    """
    target = find_nearest_target(ra, dec, max_dist_deg=0.3)
    target_id = target["id"] if target else "custom"
    
    # Pixel scale in arcseconds per pixel
    arcsec_per_pixel = (fov_arcmin * 60.0) / resolution
    center_px = resolution / 2.0

    # Deterministic background stars based on sky patch
    seed = int(abs(ra * 1000) + abs(dec * 1000)) % 1000000 + 42
    rng = np.random.RandomState(seed)

    # 40-70 static background stars
    num_stars = rng.randint(45, 75)
    static_stars: List[Tuple[float, float, float, float]] = []  # (x, y, peak_flux, fwhm)
    for _ in range(num_stars):
        sx = rng.uniform(10, resolution - 10)
        sy = rng.uniform(10, resolution - 10)
        flux = rng.exponential(scale=35.0) + 12.0
        fwhm = rng.uniform(2.2, 3.8)
        static_stars.append((sx, sy, flux, fwhm))

    # Target motion parameters
    has_target = target is not None
    pm_ra = target["pm_ra"] if has_target else 0.0      # mas/yr
    pm_dec = target["pm_dec"] if has_target else 0.0    # mas/yr
    is_variable = target["is_variable"] if has_target else False

    lightcurve_data = generate_lightcurve(target_id)["lightcurve"]

    # 8 epochs (semi-annual surveys over 4 years: 0.5 year delta)
    epoch_dates = [
        "2026-03-15", "2026-09-13", "2027-03-15", "2027-09-13",
        "2028-03-14", "2028-09-12", "2029-03-14", "2029-09-12"
    ]

    raw_frames = []
    candidates = []

    # Coordinate grids
    y_grid, x_grid = np.mgrid[0:resolution, 0:resolution]

    # Pre-render static stars to avoid repeating heavy math
    static_canvas = np.zeros((resolution, resolution), dtype=np.float32)
    for sx, sy, sflux, sfwhm in static_stars:
        sigma = sfwhm / 2.355
        r2 = (x_grid - sx)**2 + (y_grid - sy)**2
        # Cutoff at 4 sigma
        mask = r2 < (4.0 * sigma)**2
        static_canvas[mask] += sflux * np.exp(-0.5 * r2[mask] / (sigma**2))

    for epoch_idx in range(num_epochs):
        t_years = epoch_idx * 0.5  # 6-month survey cadence
        frame_data = np.copy(static_canvas)

        # Baseline zodiacal / instrumental background (SPHEREx operates in low-background L2 orbit)
        bg_level = 8.0 if not stack_all_detectors else 14.0
        frame_data += bg_level

        # Calculate target position and flux for this epoch
        if has_target:
            # Proper motion displacement in arcseconds
            # pm_ra is mas/yr -> arcsec/yr = pm_ra / 1000
            # RA increases eastward (left in sky coordinates), Dec increases northward (up)
            d_ra_arcsec = (pm_ra / 1000.0) * t_years
            d_dec_arcsec = (pm_dec / 1000.0) * t_years

            # Convert to pixel displacement
            # Note: Astronomy image convention: North is Up (-y in pixel coords usually, or +y)
            dx_px = - (d_ra_arcsec / arcsec_per_pixel)
            dy_px = - (d_dec_arcsec / arcsec_per_pixel)

            tgt_x = center_px + dx_px
            tgt_y = center_px + dy_px

            # Flux
            if is_variable:
                tgt_flux = lightcurve_data[epoch_idx]["flux_rel"] * 1.5
            else:
                tgt_flux = 180.0 if target_id == "barnard" else 85.0

            # Render target PSF
            sigma = 2.8 / 2.355
            r2 = (x_grid - tgt_x)**2 + (y_grid - tgt_y)**2
            mask = r2 < (5.0 * sigma)**2
            frame_data[mask] += tgt_flux * np.exp(-0.5 * r2[mask] / (sigma**2))

        # Detector stacking effect: stacking 6 detectors reduces noise by sqrt(6) ~ 2.45
        noise_sigma = 3.5 if not stack_all_detectors else (3.5 / math.sqrt(6.0))
        noise = np.random.normal(0, noise_sigma, (resolution, resolution)).astype(np.float32)
        frame_data += noise

        raw_frames.append(frame_data)

    # Detect motion candidate
    if has_target and abs(pm_ra) + abs(pm_dec) > 500.0:
        total_pm = math.sqrt(pm_ra**2 + pm_dec**2) / 1000.0  # arcsec/yr
        candidates.append({
            "id": f"cand-{target_id}",
            "name": f"Candidato de Alto Movimiento: {target['name']}",
            "ra_deg": target["ra"],
            "dec_deg": target["dec"],
            "proper_motion_arcsec_yr": round(total_pm, 3),
            "status": "Candidato Asistido (Verificado)",
            "confidence": 0.98,
            "spectral_class": target.get("spectral_type", "Desconocido")
        })

    return {
        "target": target,
        "raw_frames": raw_frames,
        "epoch_dates": epoch_dates,
        "candidates": candidates,
        "fov_arcmin": fov_arcmin,
        "arcsec_per_pixel": round(arcsec_per_pixel, 4),
        "is_stacked": stack_all_detectors
    }

