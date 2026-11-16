"""
Fotometría de apertura sobre recortes reales de SPHEREx.

- Espectro al vuelo: flujo de la fuente en cada exposición frente a la
  longitud de onda de ese píxel (cada exposición mide un "color" distinto).
- Curva de luz: cambio de brillo entre épocas comparando SOLO longitudes de
  onda equivalentes (una variable cambia de brillo distinto en cada color).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS

from . import config
from .processing import _bad_mask

# Ángulo sólido de un píxel en estereorradianes (6,15″ × 6,15″).
PIX_SR = (config.PIXEL_SCALE_ARCSEC / 206264.806) ** 2
AP_RADIUS_PX = 2.0      # ≈ 12″, ~1,6 × FWHM del PSF (~7,5″)
ANN_IN_PX, ANN_OUT_PX = 4.0, 7.0


def aperture_flux(stamp: Dict[str, Any], ra: float, dec: float) -> Optional[Dict[str, Any]]:
    """Flujo (mJy) en una apertura circular con fondo local (anillo). None si no se puede medir."""
    w = WCS(fits.Header.fromstring(stamp["wcs_header"]))
    x, y = (float(v) for v in w.world_to_pixel(SkyCoord(ra, dec, unit="deg")))
    img = stamp["image"] - stamp["zodi"]
    var = stamp["variance"]
    bad = _bad_mask(stamp)
    ny, nx = img.shape
    if not (ANN_OUT_PX <= x < nx - ANN_OUT_PX and ANN_OUT_PX <= y < ny - ANN_OUT_PX):
        return None
    yy, xx = np.mgrid[0:ny, 0:nx]
    r = np.hypot(xx - x, yy - y)
    ap = r <= AP_RADIUS_PX
    ann = (r >= ANN_IN_PX) & (r <= ANN_OUT_PX) & ~bad
    if ann.sum() < 10:
        return None
    sky = float(np.median(img[ann]))
    bad_in_ap = int((ap & bad).sum())
    frac_bad = bad_in_ap / max(1, int(ap.sum()))
    good = ap & ~bad
    if good.sum() == 0 or frac_bad > 0.4:
        return None
    # Píxeles malos dentro de la apertura: se reemplazan por el promedio de los buenos.
    vals = img[good] - sky
    flux_mjysr_px = float(vals.mean() * ap.sum())
    var_sum = float(np.nansum(var[good]) * (ap.sum() / good.sum()) ** 2)
    to_mjy = PIX_SR * 1e6 * 1e3  # MJy/sr·px → mJy
    contam = []
    bits = stamp.get("flag_bits", {})
    flags_ap = np.bitwise_or.reduce(stamp["flags"][ap].astype(np.int64)) if ap.any() else 0
    for name in config.CONTAM_FLAG_NAMES:
        if name in bits and flags_ap & (1 << bits[name]):
            contam.append(name)
    sat = any(n in contam for n in config.SATURATION_FLAG_NAMES)
    return {
        "saturated": sat,
        "flux_mjy": flux_mjysr_px * to_mjy,
        "err_mjy": float(np.sqrt(max(var_sum, 0))) * to_mjy,
        "frac_bad": round(frac_bad, 3),
        "flags": contam,
    }


def spectrum_points(stamps: List[Dict[str, Any]], pos_for: callable) -> List[Dict[str, Any]]:
    """Un punto por exposición: (λ, flujo). pos_for(stamp) da la posición de la fuente en esa fecha."""
    pts = []
    for st in stamps:
        wl = st.get("wavelength_um")
        if wl is None or not np.isfinite(wl):
            continue
        ra, dec = pos_for(st)
        m = aperture_flux(st, ra, dec)
        if m is None:
            continue
        rec = st["record"]
        pts.append({
            "wavelength_um": round(float(wl), 4),
            "bandwidth_um": round(float(st.get("bandwidth_um") or 0), 4),
            "flux_mjy": round(m["flux_mjy"], 4),
            "err_mjy": round(m["err_mjy"], 4),
            "detector": rec["detector"],
            "mjd": round(rec["mjd"], 4),
            "date": rec["date"][:10],
            "flags": m["flags"],
            "saturated": m["saturated"],
        })
    pts.sort(key=lambda p: p["wavelength_um"])
    return pts


def lightcurve_from_epochs(points_by_epoch: Dict[int, List[Dict[str, Any]]],
                           epoch_info: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Para cada época compara su espectro con el de una época de referencia en
    longitudes de onda equivalentes (interpolando). Devuelve Δmag por época y
    detector (negativo = más brillante). Así se ve la variabilidad sin que el
    cambio de color de los filtros la falsee.
    """
    eps = [e for e, p in points_by_epoch.items() if len(p) >= 3]
    if not eps:
        return {"points": [], "reference_epoch": None}
    ref = max(eps, key=lambda e: len(points_by_epoch[e]))
    rp = sorted(points_by_epoch[ref], key=lambda p: p["wavelength_um"])
    rwl = np.array([p["wavelength_um"] for p in rp])
    rfl = np.array([p["flux_mjy"] for p in rp])
    out = []
    for e in sorted(eps):
        for det in range(1, 7):
            pts = [p for p in points_by_epoch[e] if p["detector"] == det]
            ratios, errs = [], []
            for p in pts:
                # referencia: solo vecinos de la misma zona del espectro
                near = np.abs(rwl - p["wavelength_um"]) < max(p["bandwidth_um"], 0.01) * 1.5
                if not near.any():
                    continue
                f_ref = float(np.interp(p["wavelength_um"], rwl[near], rfl[near]))
                if f_ref <= 0 or p["flux_mjy"] <= 0:
                    continue
                ratios.append(p["flux_mjy"] / f_ref)
                errs.append(p["err_mjy"] / p["flux_mjy"])
            if not ratios:
                continue
            ratio = float(np.median(ratios))
            dmag = -2.5 * np.log10(ratio)
            err = float(1.0857 * np.sqrt(np.mean(np.square(errs))) / np.sqrt(len(errs)))
            out.append({
                "epoch": e, "detector": det,
                "mjd": round(epoch_info[e]["mjd_mean"], 3),
                "date": epoch_info[e]["date_start"],
                "delta_mag": round(dmag, 3), "err_mag": round(max(err, 0.005), 3),
                "flux_ratio": round(ratio, 4), "n": len(ratios),
            })
    return {"points": out, "reference_epoch": ref}
