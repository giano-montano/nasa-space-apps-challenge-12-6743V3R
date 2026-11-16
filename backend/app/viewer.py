"""
Orquestación: de una posición del cielo a una respuesta lista para el visor.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Dict, List, Optional

import numpy as np
from astropy.time import Time

from . import config
from .catalogs import CatalogUnavailable, allwise, gaia_dr3
from .coords import deg_to_sexagesimal, position_at
from .detection import detect_candidates, injection_test
from .irsa_client import ImageRecord, find_images, records_from_dicts
from .photometry import lightcurve_from_epochs, spectrum_points
from .processing import (band_match, coadd, difference, fetch_stamps, flatten, group_epochs, make_grid_wcs,
                         pick_records, robust_sigma, shared_limits, stretch, to_png)
from .targets import find_nearby_target, find_target

CREDITS = ("Imágenes: NASA/JPL-Caltech/IPAC — SPHEREx, vía NASA/IPAC Infrared Science Archive (IRSA). "
           "Catálogos: ESA Gaia DR3; NASA/JPL-Caltech WISE (AllWISE). Nombres: SIMBAD/Sesame (CDS, Estrasburgo).")

LIMITATIONS = [
    "Píxeles de 6,2″: solo se ven movimientos de ≳1″/año en objetos brillantes, y dos fuentes a menos de ~10″ se confunden.",
    "SPHEREx observa cada punto unas pocas veces por año desde 2025: hay pocas épocas.",
    "Cada exposición mide un color distinto (filtros lineales variables); se comparan solo colores equivalentes.",
    "Los candidatos son sugerencias automáticas para revisión humana, no descubrimientos.",
    "El cotejo con asteroides y cometas conocidos (JPL) es automático y aproximado (observador geocéntrico); si JPL no responde, el candidato queda \"sin cotejar\".",
]

# ---------------------------------------------------------------------------
# Progreso (para la barra de carga del frontend)
# ---------------------------------------------------------------------------

_PROGRESS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()


def set_progress(job: Optional[str], stage: str, done: int = 0, total: int = 0):
    if not job:
        return
    with _LOCK:
        _PROGRESS[job] = {"stage": stage, "done": done, "total": total, "t": time.time()}
        for k in [k for k, v in _PROGRESS.items() if time.time() - v["t"] > 600]:
            _PROGRESS.pop(k, None)


def get_progress(job: str) -> Dict[str, Any]:
    with _LOCK:
        return dict(_PROGRESS.get(job, {"stage": "esperando", "done": 0, "total": 0}))


# ---------------------------------------------------------------------------

def _result_cache(key: str):
    h = hashlib.sha1(key.encode()).hexdigest()[:24]
    d = os.path.join(config.CACHE_DIR, "results")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, h + ".json")


def _load_cached(key: str, refresh: bool):
    p = _result_cache(key)
    if not refresh and os.path.exists(p) and time.time() - os.path.getmtime(p) < config.CACHE_TTL_SECONDS:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cached(key: str, data):
    with open(_result_cache(key), "w", encoding="utf-8") as f:
        json.dump(data, f)


def _year(mjd: float) -> float:
    return float(Time(mjd, format="mjd").decimalyear)


def resolve_center(ra: float, dec: float, target_id: Optional[str]) -> Dict[str, Any]:
    t = find_target(target_id) if target_id else find_nearby_target(ra, dec, max_arcmin=0.5)
    return {"target": t, "ra": t["ra"] if t else ra, "dec": t["dec"] if t else dec}


def _epoch_public(e: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in e.items() if k != "records"}


def list_epochs(ra: float, dec: float, target_id: Optional[str] = None, refresh: bool = False) -> Dict[str, Any]:
    """Respuesta rápida (solo metadatos): qué fechas hay para este punto. Sirve para la línea de tiempo."""
    c = resolve_center(ra, dec, target_id)
    t = c["target"]
    qra, qdec = (position_at(t["ra"], t["dec"], t["pmra"], t["pmdec"], t["parallax"], 61000.0)
                 if t else (c["ra"], c["dec"]))
    found = find_images(qra, qdec, refresh=refresh)
    recs = records_from_dicts(found["images"])
    eps = group_epochs(recs)
    return {"service": found["service"], "queried_at": found.get("queried_at"), "warning": found.get("warning"),
            "n_images": len(recs), "epochs": [_epoch_public(e) for e in eps], "target": t,
            "query_ra": qra, "query_dec": qdec, "_records": recs, "_epochs": eps}


def build_view(ra: float, dec: float, target_id: Optional[str] = None, fov_arcmin: float = 5.0,
               detectors: Optional[List[int]] = None, match_bands: bool = True,
               epoch_sel: Optional[List[int]] = None, ref_epoch: Optional[int] = None,
               stretch_kind: str = "asinh", refresh: bool = False, job: Optional[str] = None) -> Dict[str, Any]:
    fov_arcmin = float(min(max(fov_arcmin, 1.0), config.MAX_FOV_ARCMIN))
    if not detectors:
        tt = find_target(target_id) if target_id else None
        detectors = tt["detectors"] if tt else [1]
    detectors = sorted(set(detectors))
    key = json.dumps(["view-v7", round(ra, 5), round(dec, 5), target_id, fov_arcmin, detectors, match_bands,
                      epoch_sel, ref_epoch, stretch_kind, config.SPHEREX_COLLECTIONS])
    cached = _load_cached(key, refresh)
    if cached:
        cached["from_cache"] = True
        return cached

    set_progress(job, "Buscando imágenes en IRSA…")
    info = list_epochs(ra, dec, target_id, refresh=refresh)
    t = info["target"]
    all_epochs = info["_epochs"]
    warnings: List[str] = [info["warning"]] if info.get("warning") else []

    if not all_epochs:
        return {"status": "no_data", "message": "SPHEREx todavía no tiene imágenes publicadas que cubran este punto del cielo.",
                "service": info["service"], "epochs": [], "credits": CREDITS}

    epochs = [e for e in all_epochs if (epoch_sel is None or e["index"] in epoch_sel)]
    epochs = [e for e in epochs if any(r.detector in detectors for r in e["records"])]
    if len(epochs) > 12:  # zonas observadas casi a diario: repartir 12 épocas
        idx = np.unique(np.linspace(0, len(epochs) - 1, 12).round().astype(int))
        epochs = [epochs[i] for i in idx]
        warnings.append("Este punto tiene muchísimas visitas; se muestran 12 épocas repartidas en el tiempo.")
    if not epochs:
        return {"status": "no_data", "message": "No hay imágenes de los detectores elegidos en las fechas elegidas.",
                "service": info["service"], "epochs": [_epoch_public(e) for e in all_epochs], "credits": CREDITS}

    # Centro fijo: para un objetivo con movimiento propio, su posición en la fecha media.
    mjd_mean = float(np.mean([e["mjd_mean"] for e in epochs]))
    if t:
        cra, cdec = position_at(t["ra"], t["dec"], t["pmra"], t["pmdec"], t["parallax"], mjd_mean)
    else:
        cra, cdec = ra, dec
    grid, npix = make_grid_wcs(cra, cdec, fov_arcmin)
    stamp_size = fov_arcmin * 1.45 + 0.5  # margen para la rotación del detector

    # Gaia en paralelo con las descargas (sus servicios pueden tardar).
    radius = fov_arcmin / 60.0 * 0.75
    gaia_pool = ThreadPoolExecutor(max_workers=1)
    gaia_future = gaia_pool.submit(gaia_dr3, cra, cdec, radius)

    jobs = []
    per_epoch_recs = {}
    for e in epochs:
        recs = pick_records(e["records"], detectors, config.MAX_IMAGES_PER_EPOCH_DET)
        per_epoch_recs[e["index"]] = recs
        jobs.extend((r, cra, cdec) for r in recs)
    set_progress(job, "Descargando recortes de SPHEREx", 0, len(jobs))
    stamps, errors = fetch_stamps(jobs, stamp_size, progress=lambda d, n: set_progress(job, "Descargando recortes de SPHEREx", d, n))
    if errors:
        warnings.append(f"{len(errors)} de {len(jobs)} imágenes no se pudieron leer y se omitieron.")
    by_path = {st["record"]["path"]: st for st in stamps}
    by_epoch = {e["index"]: [by_path[r.path] for r in per_epoch_recs[e["index"]] if r.path in by_path] for e in epochs}

    match_info = {"applied": False, "reason": "Desactivado por el usuario."}
    if match_bands:
        by_epoch, match_info = band_match(by_epoch)
        if not match_info["applied"] and match_info.get("reason"):
            warnings.append(match_info["reason"])

    set_progress(job, "Combinando y alineando imágenes", len(jobs), len(jobs))
    coadds, frames_meta = {}, {}
    for e in epochs:
        sts = by_epoch.get(e["index"], [])
        if not sts:
            continue
        coadds[e["index"]] = coadd(sts, grid, npix)
        flags = {}
        for st in sts:
            bits = st.get("flag_bits", {})
            fl = st["flags"].astype(np.int64)
            for name in config.CONTAM_FLAG_NAMES:
                if name in bits:
                    c = int(((fl & (1 << bits[name])) != 0).sum())
                    if c:
                        flags[name] = flags.get(name, 0) + c
        frames_meta[e["index"]] = {
            "n_used": len(sts),
            "wavelengths_um": sorted(round(st["wavelength_um"], 3) for st in sts if np.isfinite(st["wavelength_um"])),
            "detectors": sorted({st["record"]["detector"] for st in sts}),
            "qa": sorted({str(st["meta"].get("qa")) for st in sts}),
            "flag_pixel_counts": flags,
            "images": [{"obsid": st["meta"].get("obsid"), "date": st["meta"].get("date_obs"),
                        "detector": st["record"]["detector"], "release": st["record"]["release"],
                        "wavelength_um": round(st["wavelength_um"], 4) if np.isfinite(st["wavelength_um"]) else None,
                        "exptime_s": st["meta"].get("exptime_s"), "qa": st["meta"].get("qa"),
                        "file": st["record"]["path"].rsplit("/", 1)[-1]} for st in sts],
        }
    used = [e for e in epochs if e["index"] in coadds]
    if not used:
        return {"status": "error", "message": "No se pudo leer ninguna imagen (IRSA/AWS no respondieron).",
                "service": info["service"], "epochs": [_epoch_public(e) for e in all_epochs], "credits": CREDITS}

    # Escala común para que el parpadeo no "titile" por cambios de contraste.
    lo, hi = shared_limits([coadds[e["index"]]["data"] for e in used])
    frames = []
    for e in used:
        c = coadds[e["index"]]
        frames.append({
            "epoch": e["index"], "date": e["date_start"], "date_end": e["date_end"], "mjd": round(e["mjd_mean"], 3),
            "image": to_png(stretch(c["data"], lo, hi, stretch_kind), nan_mask=~c["coverage"]),
            "coverage": round(float(c["coverage"].mean()), 3),
            **frames_meta[e["index"]],
        })

    # Diferencias contra la época de referencia (F-04), con escala simétrica común.
    ref = ref_epoch if ref_epoch in coadds else used[0]["index"]
    diffs_raw = {e["index"]: (difference(coadds[e["index"]]["data"], coadds[ref]["data"]) if e["index"] != ref
                              else np.where(np.isfinite(coadds[ref]["data"]), 0.0, np.nan)) for e in used}
    sig = np.median([robust_sigma(d) for k, d in diffs_raw.items() if k != ref] or [1.0])
    diffs = []
    for e in used:
        d = diffs_raw[e["index"]]
        arr = np.clip(128 + np.nan_to_num(d) / (6 * sig) * 127, 0, 255).astype(np.uint8)
        diffs.append({"epoch": e["index"], "date": e["date_start"], "image": to_png(arr, "diff", nan_mask=~np.isfinite(d))})

    # Suma de todas las épocas elegidas (más señal, borra lo que se mueve).
    num = sum(np.nan_to_num(coadds[e["index"]]["data"]) * coadds[e["index"]]["coverage"] for e in used)
    den = sum(coadds[e["index"]]["coverage"].astype(float) for e in used)
    with np.errstate(invalid="ignore", divide="ignore"):
        summed = np.where(den > 0, num / den, np.nan)
    lo_s, hi_s = shared_limits([summed])
    sum_frame = {"image": to_png(stretch(summed, lo_s, hi_s, stretch_kind), nan_mask=~np.isfinite(summed)),
                 "epochs": [e["index"] for e in used]}

    # Trayectoria esperada del objetivo (según SIMBAD), en píxeles de la rejilla.
    track = []
    if t:
        for e in used:
            pra, pdec = position_at(t["ra"], t["dec"], t["pmra"], t["pmdec"], t["parallax"], e["mjd_mean"])
            x, y = grid.world_to_pixel_values(pra, pdec)
            track.append({"epoch": e["index"], "x": round(float(x), 2), "y": round(float(y), 2),
                          "ra": round(pra, 6), "dec": round(pdec, 6)})

    # Catálogos de contexto y cotejo.
    set_progress(job, "Consultando Gaia DR3 y buscando candidatos", len(jobs), len(jobs))
    gaia, gaia_err = None, None
    try:
        gaia = gaia_future.result(timeout=config.CATALOG_WAIT_SECONDS)
    except (CatalogUnavailable, FutureTimeout) as e:
        gaia_err = str(e) or "tiempo de espera agotado"
        warnings.append("Gaia DR3 no respondió a tiempo: no se pudo cotejar candidatos con estrellas conocidas.")
    finally:
        gaia_pool.shutdown(wait=False)
    epoch_mjd = {e["index"]: e["mjd_mean"] for e in used}
    flat = {k: {"data": flatten(coadds[k]["data"]), "err": coadds[k]["err"]} for k in epoch_mjd}
    det = detect_candidates(flat, epoch_mjd, grid,
                            gaia_sources=gaia["sources"] if gaia else None, solar_system=True) if len(used) >= 2 else \
        {"candidates": [], "transients": [], "method": "Hace falta más de una época para medir movimiento."}

    ra_s, dec_s = deg_to_sexagesimal(cra, cdec)
    result = {
        "status": "ok",
        "service": info["service"], "queried_at": info.get("queried_at"),
        "center": {"ra_deg": round(cra, 6), "dec_deg": round(cdec, 6), "ra_sex": ra_s, "dec_sex": dec_s,
                   "note": "Centro propagado con el movimiento propio a la fecha media de las imágenes." if t else None},
        "target": t,
        "fov_arcmin": fov_arcmin,
        "grid": {"npix": npix, "pixel_arcsec": config.PIXEL_SCALE_ARCSEC, "crpix": float(grid.wcs.crpix[0]),
                 "crval": [cra, cdec]},
        "detectors": detectors,
        "band_matching": match_info,
        "epochs_available": [_epoch_public(e) for e in all_epochs],
        "n_images_total": info["n_images"],
        "frames": frames, "diffs": diffs, "reference_epoch": ref, "sum": sum_frame,
        "track": track,
        "detection": det,
        "gaia": ({"service": gaia["service"], "epoch": gaia["epoch"],
                  "sources": [s for s in gaia["sources"]]} if gaia else {"error": gaia_err}),
        "warnings": warnings,
        "credits": CREDITS, "limitations": LIMITATIONS,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _save_cached(key, result)
    set_progress(job, "Listo", len(jobs), len(jobs))
    return result


def _pos_func(t):
    if not t:
        return None
    return lambda st: position_at(t["ra"], t["dec"], t["pmra"], t["pmdec"], t["parallax"], st["record"]["mjd"])


def build_spectrum(ra: float, dec: float, target_id: Optional[str] = None, epoch: Optional[int] = None,
                   refresh: bool = False, job: Optional[str] = None, max_images: int = 140) -> Dict[str, Any]:
    """Espectro al vuelo con todas las exposiciones (los 6 detectores) de una época."""
    key = json.dumps(["spec-v4", round(ra, 5), round(dec, 5), target_id, epoch, config.SPHEREX_COLLECTIONS])
    cached = _load_cached(key, refresh)
    if cached:
        return cached
    set_progress(job, "Buscando imágenes en IRSA…")
    t = find_target(target_id) if target_id else None
    info = list_epochs(ra, dec, target_id if t else None, refresh=refresh)
    eps = info["_epochs"]
    if not eps:
        return {"status": "no_data", "message": "No hay imágenes de SPHEREx en este punto.", "points": []}
    if epoch is None:
        # la época con más detectores y más imágenes
        e = max(eps, key=lambda e: (len(e["detectors"]), e["n_images"]))
    else:
        e = next((x for x in eps if x["index"] == epoch), eps[-1])
    recs = pick_records(e["records"], list(range(1, 7)), max(4, max_images // 6))
    pos = _pos_func(t)
    if pos:
        jobs = [(r, *position_at(t["ra"], t["dec"], t["pmra"], t["pmdec"], t["parallax"], r.mjd)) for r in recs]
    else:
        jobs = [(r, ra, dec) for r in recs]
    stamps, errors = fetch_stamps(jobs, 1.6, progress=lambda d, n: set_progress(job, "Midiendo el brillo en cada color", d, n))
    pts = spectrum_points(stamps, pos or (lambda st: (ra, dec)))
    n_sat = sum(1 for p in pts if p.get("saturated"))
    result = {"status": "ok" if pts else "no_data", "epoch": _epoch_public(e), "points": pts,
              "saturated_fraction": round(n_sat / len(pts), 2) if pts else 0,
              "warning": ("La fuente satura los detectores de SPHEREx en parte del espectro: esos puntos (más tenues) "
                          "son estimaciones del pipeline y pueden subestimar el brillo.") if n_sat else None,
              "unit": "mJy", "n_images": len(recs), "n_failed": len(errors),
              "position": {"ra_deg": ra, "dec_deg": dec}, "target": t,
              "method": "Fotometría de apertura (r=12″) con fondo local, tras restar el fondo zodiacal. "
                        "Cada punto es una exposición; su longitud de onda sale de la tabla WCS-WAVE en ese píxel.",
              "message": None if pts else "No se pudo medir la fuente (fuera de imagen o píxeles marcados)."}
    _save_cached(key, result)
    set_progress(job, "Listo")
    return result


def build_lightcurve(ra: float, dec: float, target_id: Optional[str] = None, refresh: bool = False,
                     job: Optional[str] = None, per_det: int = 4) -> Dict[str, Any]:
    key = json.dumps(["lc-v4", round(ra, 5), round(dec, 5), target_id, per_det, config.SPHEREX_COLLECTIONS])
    cached = _load_cached(key, refresh)
    if cached:
        return cached
    set_progress(job, "Buscando imágenes en IRSA…")
    t = find_target(target_id) if target_id else None
    info = list_epochs(ra, dec, target_id if t else None, refresh=refresh)
    eps = info["_epochs"]
    if len(eps) > 12:
        idx = np.unique(np.linspace(0, len(eps) - 1, 12).round().astype(int))
        eps = [eps[i] for i in idx]
    jobs, owner = [], {}
    for e in eps:
        for r in pick_records(e["records"], list(range(1, 7)), per_det):
            p = position_at(t["ra"], t["dec"], t["pmra"], t["pmdec"], t["parallax"], r.mjd) if t else (ra, dec)
            jobs.append((r, *p))
            owner[r.path] = e["index"]
    stamps, errors = fetch_stamps(jobs, 1.6, progress=lambda d, n: set_progress(job, "Midiendo el brillo en cada fecha", d, n))
    pos = _pos_func(t) or (lambda st: (ra, dec))
    by_epoch: Dict[int, List[Dict[str, Any]]] = {}
    for st in stamps:
        by_epoch.setdefault(owner[st["record"]["path"]], []).append(st)
    pts_by_epoch = {e: spectrum_points(sts, pos) for e, sts in by_epoch.items()}
    lc = lightcurve_from_epochs(pts_by_epoch, {e["index"]: e for e in eps})
    raw = [dict(p, epoch=e) for e, ps in pts_by_epoch.items() for p in ps]
    n_sat = sum(1 for p in raw if p.get("saturated"))
    lc["warning"] = ("Parte de las medidas usan píxeles saturados (estimados por el pipeline): la amplitud es aproximada."
                     if n_sat else None)
    result = {"status": "ok" if lc["points"] else "no_data", **lc, "raw": raw,
              "epochs": [_epoch_public(e) for e in eps], "n_failed": len(errors), "target": t,
              "method": "Para cada época se compara el brillo con el de la época de referencia en la MISMA longitud de "
                        "onda (interpolando), por detector. Δmag negativo = más brillante.",
              "message": None if lc["points"] else "Hacen falta al menos dos épocas medibles para una curva de luz."}
    _save_cached(key, result)
    set_progress(job, "Listo")
    return result


def run_injection(ra, dec, target_id=None, fov_arcmin=5.0, detectors=None, job=None) -> Dict[str, Any]:
    """Reutiliza las imágenes del visor (desde caché) y mide la sensibilidad con objetos simulados."""
    detectors = detectors or [1]
    info = list_epochs(ra, dec, target_id)
    t = info["target"]
    eps = [e for e in info["_epochs"] if any(r.detector in detectors for r in e["records"])][:12]
    if len(eps) < 2:
        return {"error": "Hace falta más de una época en este punto."}
    mjd_mean = float(np.mean([e["mjd_mean"] for e in eps]))
    cra, cdec = (position_at(t["ra"], t["dec"], t["pmra"], t["pmdec"], t["parallax"], mjd_mean) if t else (ra, dec))
    grid, npix = make_grid_wcs(cra, cdec, fov_arcmin)
    jobs, per = [], {}
    for e in eps:
        per[e["index"]] = pick_records(e["records"], detectors, config.MAX_IMAGES_PER_EPOCH_DET)
        jobs.extend((r, cra, cdec) for r in per[e["index"]])
    stamps, _ = fetch_stamps(jobs, fov_arcmin * 1.45 + 0.5, progress=lambda d, n: set_progress(job, "Leyendo imágenes", d, n))
    byp = {s["record"]["path"]: s for s in stamps}
    coadds = {}
    for e in eps:
        sts = [byp[r.path] for r in per[e["index"]] if r.path in byp]
        if sts:
            c = coadd(sts, grid, npix)
            coadds[e["index"]] = {"data": flatten(c["data"]), "err": c["err"]}
    set_progress(job, "Inyectando objetos simulados")
    res = injection_test(coadds, {k: next(e["mjd_mean"] for e in eps if e["index"] == k) for k in coadds}, grid)
    set_progress(job, "Listo")
    return res


def catalog_overlay(ra: float, dec: float, fov_arcmin: float, source: str) -> Dict[str, Any]:
    radius = fov_arcmin / 60.0 * 0.75
    if source == "wise":
        return allwise(ra, dec, radius)
    return gaia_dr3(ra, dec, radius)
