"""
Procesamiento de imágenes reales de SPHEREx.

- Agrupa las exposiciones en épocas (visitas separadas en el tiempo).
- Emparejamiento de banda (F-08): SPHEREx usa filtros lineales variables, la
  longitud de onda cambia a lo largo del detector. Para comparar épocas solo se
  usan exposiciones cuya longitud de onda en ese punto coincide entre épocas.
- Resta del fondo zodiacal (extensión ZODI) y máscara de píxeles malos (FLAGS) (F-09).
- Reproyección de cada recorte a una rejilla común (TAN, 6,15″/px, norte arriba,
  este a la izquierda) y combinación ponderada por la inversa de la varianza.
"""

from __future__ import annotations

import base64
import io
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from PIL import Image
from scipy import ndimage

from . import config
from .irsa_client import ImageRecord, read_stamp

logging.getLogger("astropy").setLevel(logging.WARNING)
try:
    from astropy import log as _alog
    _alog.setLevel("WARNING")
except Exception:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Épocas
# ---------------------------------------------------------------------------

def group_epochs(records: List[ImageRecord], max_span_days: float = 60.0) -> List[Dict[str, Any]]:
    """
    Agrupa por huecos de tiempo > EPOCH_GAP_DAYS. Cerca de los polos de la
    eclíptica SPHEREx observa casi continuamente; ahí las visitas largas se
    parten en bloques de ~30 días para poder ver cambios.
    """
    recs = sorted(records, key=lambda r: r.mjd)
    groups: List[List[ImageRecord]] = []
    for r in recs:
        if groups and r.mjd - groups[-1][-1].mjd <= config.EPOCH_GAP_DAYS:
            groups[-1].append(r)
        else:
            groups.append([r])

    final: List[List[ImageRecord]] = []
    for g in groups:
        span = g[-1].mjd - g[0].mjd
        if span <= max_span_days:
            final.append(g)
            continue
        nbins = int(np.ceil(span / 30.0))
        edges = np.linspace(g[0].mjd, g[-1].mjd + 1e-6, nbins + 1)
        for i in range(nbins):
            part = [r for r in g if edges[i] <= r.mjd < edges[i + 1]]
            if part:
                final.append(part)

    epochs = []
    for i, g in enumerate(final):
        mjds = np.array([r.mjd for r in g])
        epochs.append({
            "index": i,
            "mjd_mean": float(mjds.mean()),
            "mjd_min": float(mjds.min()),
            "mjd_max": float(mjds.max()),
            "date_start": g[0].date[:10],
            "date_end": g[-1].date[:10],
            "n_images": len(g),
            "detectors": sorted({r.detector for r in g}),
            "releases": sorted({r.release for r in g}),
            "records": g,
        })
    return epochs


def pick_records(records: List[ImageRecord], detectors: List[int], max_per_det: int) -> List[ImageRecord]:
    """Hasta max_per_det exposiciones por detector, repartidas en el tiempo."""
    out = []
    for d in detectors:
        rs = sorted([r for r in records if r.detector == d], key=lambda r: r.mjd)
        if len(rs) > max_per_det:
            idx = np.unique(np.linspace(0, len(rs) - 1, max_per_det).round().astype(int))
            rs = [rs[i] for i in idx]
        out.extend(rs)
    return out


def fetch_stamps(jobs: List[Tuple[ImageRecord, float, float]], size_arcmin: float,
                 progress: Optional[Callable[[int, int], None]] = None) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Lee recortes en paralelo. jobs = [(registro, ra, dec)]. Devuelve (stamps, errores)."""
    stamps, errors = [], []
    if not jobs:
        return stamps, errors
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as ex:
        futs = {ex.submit(read_stamp, rec, ra, dec, size_arcmin): rec for rec, ra, dec in jobs}
        for n, fut in enumerate(as_completed(futs), 1):
            try:
                st = fut.result()
                st["_ra"], st["_dec"] = None, None
                stamps.append(st)
            except Exception as e:  # una imagen mala no tumba todo
                errors.append(str(e)[:200])
            if progress:
                progress(n, len(jobs))
    return stamps, errors


# ---------------------------------------------------------------------------
# Emparejamiento de banda
# ---------------------------------------------------------------------------

def band_match(stamps_by_epoch: Dict[int, List[Dict[str, Any]]], tol_frac: float = 1.0, min_keep: int = 4) -> Tuple[Dict[int, List[Dict[str, Any]]], Dict[str, Any]]:
    """
    Emparejamiento de banda. Dos niveles:
      1. Estricto: solo exposiciones cuya longitud de onda tiene pareja en TODAS
         las demás épocas (|Δλ| < tol_frac × ancho de banda, ≈ 1 elemento de resolución).
      2. Si no alcanza: cada época se compara con una época de referencia y solo
         se usan los colores que ambas comparten.
    Así una diferencia de brillo por cambiar de "color" no parece un cambio real.
    """
    epochs = [e for e, s in stamps_by_epoch.items() if s]
    if len(epochs) < 2:
        return stamps_by_epoch, {"applied": False, "reason": "Hace falta más de una época."}

    def ok(st, other):
        wl, bw = st["wavelength_um"], st["bandwidth_um"] or 0.02
        if not np.isfinite(wl):
            return False
        return any(np.isfinite(o["wavelength_um"]) and abs(o["wavelength_um"] - wl) < tol_frac * max(bw, 0.005)
                   and o["record"]["detector"] == st["record"]["detector"] for o in other)

    total = sum(len(stamps_by_epoch[e]) for e in epochs)

    def summary(matched, level):
        kept = sum(len(v) for v in matched.values())
        wls = sorted({round(st["wavelength_um"], 3) for v in matched.values() for st in v})
        return matched, {"applied": True, "level": level, "kept": kept, "total": total, "wavelengths_um": wls}

    strict = {e: [st for st in stamps_by_epoch[e] if all(ok(st, stamps_by_epoch[o]) for o in epochs if o != e)]
              for e in epochs}
    ref = max(epochs, key=lambda e: len(stamps_by_epoch[e]))
    pair = {e: [st for st in stamps_by_epoch[e] if ok(st, stamps_by_epoch[ref])] for e in epochs if e != ref}
    pair[ref] = [st for st in stamps_by_epoch[ref] if any(ok(st, stamps_by_epoch[o]) for o in epochs if o != ref)]

    # Se prefiere el nivel más estricto, pero sin dejar épocas casi vacías:
    # con muy pocas fotos la señal cae y los objetos débiles desaparecen.
    def enough(m):
        return all(len(m[e]) >= min(min_keep, len(stamps_by_epoch[e])) for e in epochs)

    for m, level in ((strict, "todas las épocas comparten los mismos colores"),
                     (pair, f"cada época comparte colores con la época de referencia {ref}")):
        if enough(m):
            return summary(m, level)
    return stamps_by_epoch, {
        "applied": False,
        "reason": "Hay pocas longitudes de onda comunes entre fechas; se usan todas las fotos para no perder señal "
                  "(un cambio de brillo puede deberse al color, no a la fuente; la posición no se ve afectada).",
    }


# ---------------------------------------------------------------------------
# Rejilla común y combinación
# ---------------------------------------------------------------------------

def make_grid_wcs(ra: float, dec: float, fov_arcmin: float) -> Tuple[WCS, int]:
    n = int(np.ceil(fov_arcmin * 60.0 / config.PIXEL_SCALE_ARCSEC))
    n += (n + 1) % 2  # impar: el centro cae en un píxel
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(n + 1) / 2.0, (n + 1) / 2.0]
    s = config.PIXEL_SCALE_ARCSEC / 3600.0
    w.wcs.cdelt = [-s, s]  # este a la izquierda, norte arriba
    return w, n


def _bits(stamp: Dict[str, Any], names) -> int:
    bits = stamp.get("flag_bits", {})
    m = 0
    for name in names:
        if name in bits:
            m |= (1 << bits[name])
    return m


def _bad_mask(stamp: Dict[str, Any]) -> np.ndarray:
    flags = stamp["flags"].astype(np.int64)
    bad = (flags & _bits(stamp, config.BAD_FLAG_NAMES)) != 0
    src = (flags & _bits(stamp, ["SOURCE"])) != 0
    if src.any():  # núcleo de estrellas brillantes: solo defectos duros
        hard = (flags & _bits(stamp, config.HARD_BAD_FLAG_NAMES)) != 0
        bad = np.where(src, hard, bad)
    bad |= ~np.isfinite(stamp["image"]) | ~np.isfinite(stamp["variance"]) | (stamp["variance"] <= 0)
    return bad


def reproject(stamp: Dict[str, Any], grid: WCS, n: int) -> Tuple[np.ndarray, np.ndarray]:
    """Devuelve (imagen sin zodi, peso=1/var) en la rejilla común; peso 0 = sin dato."""
    sw = WCS(fits.Header.fromstring(stamp["wcs_header"]))
    yy, xx = np.mgrid[0:n, 0:n]
    world = grid.pixel_to_world(xx, yy)
    sx, sy = sw.world_to_pixel(world)
    img = np.nan_to_num(stamp["image"] - stamp["zodi"], nan=0.0)
    var = np.nan_to_num(stamp["variance"], nan=np.inf, posinf=np.inf)
    bad = _bad_mask(stamp)
    coords = np.array([sy, sx])
    out = ndimage.map_coordinates(img, coords, order=1, mode="constant", cval=np.nan)
    v = ndimage.map_coordinates(np.where(np.isfinite(var), var, 0), coords, order=1, mode="constant", cval=0)
    b = ndimage.map_coordinates(bad.astype(np.float32), coords, order=1, mode="constant", cval=1.0) > 0.25
    inside = (sx >= -0.5) & (sx <= img.shape[1] - 0.5) & (sy >= -0.5) & (sy <= img.shape[0] - 0.5)
    w = np.where(inside & ~b & (v > 0) & np.isfinite(out), 1.0 / np.where(v > 0, v, 1), 0.0)
    return np.where(w > 0, out, 0.0), w


def coadd(stamps: List[Dict[str, Any]], grid: WCS, n: int) -> Dict[str, np.ndarray]:
    """
    Combinación ponderada por inversa de varianza. Antes de sumar se quita a
    cada exposición su nivel de fondo (mediana) para que cambios de longitud
    de onda no dejen escalones.
    """
    num = np.zeros((n, n))
    den = np.zeros((n, n))
    for st in stamps:
        img, w = reproject(st, grid, n)
        if w.sum() == 0:
            continue
        sky = np.median(img[w > 0])
        num += (img - sky) * w
        den += w
    with np.errstate(invalid="ignore", divide="ignore"):
        data = np.where(den > 0, num / den, np.nan)
        err = np.where(den > 0, 1.0 / np.sqrt(den), np.nan)
    return {"data": data, "err": err, "coverage": den > 0}


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def shared_limits(arrays: List[np.ndarray], pmin: float = 1.0, pmax: float = 99.7) -> Tuple[float, float]:
    vals = np.concatenate([a[np.isfinite(a)].ravel() for a in arrays if a is not None and np.isfinite(a).any()]) \
        if arrays else np.array([0.0, 1.0])
    if vals.size == 0:
        return 0.0, 1.0
    lo, hi = np.percentile(vals, [pmin, pmax])
    if hi <= lo:
        hi = lo + 1e-6
    return float(lo), float(hi)


def stretch(data: np.ndarray, lo: float, hi: float, kind: str = "asinh", soft: float = 0.08) -> np.ndarray:
    norm = np.clip((np.nan_to_num(data, nan=lo) - lo) / (hi - lo), 0, 1)
    if kind == "asinh":
        out = np.arcsinh(norm / soft) / np.arcsinh(1 / soft)
    elif kind == "log":
        out = np.log1p(norm * 99) / np.log1p(99)
    elif kind == "sqrt":
        out = np.sqrt(norm)
    else:
        out = norm
    return (out * 255).astype(np.uint8)


def to_png(arr: np.ndarray, kind: str = "gray", nan_mask: Optional[np.ndarray] = None) -> str:
    """PNG base64 (data URI). Se dibuja con el norte arriba (fila 0 = arriba)."""
    a = np.flipud(arr)
    m = np.flipud(nan_mask) if nan_mask is not None else None
    if kind == "diff":
        # 128 = sin cambio. Positivo (más brillante ahora) en naranja, negativo en azul.
        f = (a.astype(np.float32) - 128) / 127
        pos, neg = np.clip(f, 0, 1), np.clip(-f, 0, 1)
        base = 24
        rgb = np.stack([base + (255 - base) * pos, base + (150 - base) * pos + (170 - base) * neg,
                        base + (255 - base) * neg], -1).astype(np.uint8)
    else:
        rgb = np.stack([a, a, a], -1)
    rgba = np.dstack([rgb, np.full(a.shape, 255, np.uint8)])
    if m is not None:
        rgba[m] = [40, 20, 30, 255]
    img = Image.fromarray(rgba, "RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def flatten(data: np.ndarray, size: int = 15) -> np.ndarray:
    """Quita el fondo que varía suavemente (gradientes de luz zodiacal residual)."""
    d = np.where(np.isfinite(data), data, np.nanmedian(data) if np.isfinite(data).any() else 0)
    bg = ndimage.median_filter(d, size=min(size, max(3, d.shape[0] // 3)))
    return np.where(np.isfinite(data), data - bg, np.nan)


def difference(a: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """
    a − k·ref. Antes se quita el fondo y se ajusta la escala k con las fuentes
    brillantes (cada época mide colores algo distintos): así lo fijo se anula y
    queda lo que se movió o cambió de brillo distinto que su entorno.
    """
    fa, fr = flatten(a), flatten(ref)
    ok = np.isfinite(fa) & np.isfinite(fr)
    k = 1.0
    if ok.sum() > 20:
        thr = 10.0 * robust_sigma(fr[ok])  # solo píxeles con señal clara de estrellas
        sel = ok & (fr > thr) & (fa > 0)
        if sel.sum() >= 8:
            # mediana de cocientes: un objeto móvil pegado a una estrella no arrastra la escala
            k = float(np.clip(np.median(fa[sel] / fr[sel]), 0.5, 2.0))
    return fa - k * fr


def robust_sigma(a: np.ndarray) -> float:
    v = a[np.isfinite(a)]
    if v.size == 0:
        return 1.0
    return float(1.4826 * np.median(np.abs(v - np.median(v)))) or float(np.std(v)) or 1.0
