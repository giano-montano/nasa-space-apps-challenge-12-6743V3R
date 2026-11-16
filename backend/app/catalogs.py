"""
Catálogos externos reales para superponer y cotejar (F-11):
- Gaia DR3 (posiciones en época J2016.0 + movimiento propio): ESA, con VizieR de respaldo.
- AllWISE (época ~2010.5, sin movimiento propio fiable): IRSA, con VizieR de respaldo.
Nunca se inventan fuentes: si ningún servicio responde, se devuelve error.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import time
from typing import Any, Dict, List

import numpy as np
import requests
from astropy.io.votable import parse_single_table

from . import config

_session = requests.Session()
_session.headers["User-Agent"] = "spherex-sky-viewer/3.0 (NASA Space Apps 2026)"


class CatalogUnavailable(RuntimeError):
    pass


def _tap(url: str, adql: str, extra: Dict[str, str] | None = None):
    data = {"QUERY": adql, "FORMAT": "votable", "LANG": "ADQL", "REQUEST": "doQuery"}
    data.update(extra or {})
    r = _session.post(url, data=data, timeout=(8, 40))
    if r.status_code != 200:
        raise CatalogUnavailable(f"HTTP {r.status_code}")
    return parse_single_table(io.BytesIO(r.content)).to_table(use_names_over_ids=True)


def _cached(kind: str, key: str, fn):
    h = hashlib.sha1(key.encode()).hexdigest()[:20]
    d = os.path.join(config.CACHE_DIR, "catalogs")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{kind}_{h}.json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 7 * 86400:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    data = fn()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def _num(v):
    try:
        f = float(v)
        return None if not np.isfinite(f) else f
    except (TypeError, ValueError):
        return None


def gaia_dr3(ra: float, dec: float, radius_deg: float, max_rows: int = 2000) -> Dict[str, Any]:
    def run():
        errors = []
        try:  # copia de Gaia DR3 en IRSA (misma institución que SPHEREx)
            t = _tap(config.IRSA_TAP_URL,
                     f"SELECT TOP {max_rows} source_id, ra, dec, pmra, pmdec, parallax, phot_g_mean_mag "
                     f"FROM gaia_dr3_source WHERE 1=CONTAINS(POINT('ICRS', ra, dec), "
                     f"CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius_deg:.5f}))")
            rows = [{"id": str(r["source_id"]), "ra": float(r["ra"]), "dec": float(r["dec"]),
                     "pmra": _num(r["pmra"]), "pmdec": _num(r["pmdec"]), "parallax": _num(r["parallax"]),
                     "mag": _num(r["phot_g_mean_mag"])} for r in t]
            return {"catalog": "Gaia DR3", "service": "IRSA (gaia_dr3_source)", "epoch": 2016.0, "sources": rows}
        except Exception as e:
            errors.append(f"IRSA: {e.__class__.__name__}")
        try:
            t = _tap(config.GAIA_ESA_TAP,
                     f"SELECT TOP {max_rows} source_id, ra, dec, pmra, pmdec, parallax, phot_g_mean_mag "
                     f"FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS', ra, dec), "
                     f"CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius_deg:.5f}))")
            rows = [{"id": str(r["source_id"]), "ra": float(r["ra"]), "dec": float(r["dec"]),
                     "pmra": _num(r["pmra"]), "pmdec": _num(r["pmdec"]), "parallax": _num(r["parallax"]),
                     "mag": _num(r["phot_g_mean_mag"])} for r in t]
            return {"catalog": "Gaia DR3", "service": "ESA Gaia Archive", "epoch": 2016.0, "sources": rows}
        except Exception as e:
            errors.append(f"ESA: {e.__class__.__name__}")
        try:
            t = _tap(config.GAIA_VIZIER_TAP,
                     f'SELECT TOP {max_rows} Source, RA_ICRS, DE_ICRS, pmRA, pmDE, Plx, Gmag FROM "I/355/gaiadr3" '
                     f"WHERE 1=CONTAINS(POINT('ICRS', RA_ICRS, DE_ICRS), CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius_deg:.5f}))")
            rows = [{"id": str(r["Source"]), "ra": float(r["RA_ICRS"]), "dec": float(r["DE_ICRS"]),
                     "pmra": _num(r["pmRA"]), "pmdec": _num(r["pmDE"]), "parallax": _num(r["Plx"]),
                     "mag": _num(r["Gmag"])} for r in t]
            return {"catalog": "Gaia DR3", "service": "VizieR (CDS) I/355", "epoch": 2016.0, "sources": rows}
        except Exception as e:
            errors.append(f"VizieR: {e.__class__.__name__}")
        raise CatalogUnavailable("Gaia DR3 no disponible: " + " | ".join(errors))

    return _cached("gaia", f"{ra:.4f}:{dec:.4f}:{radius_deg:.4f}", run)


def allwise(ra: float, dec: float, radius_deg: float, max_rows: int = 2000) -> Dict[str, Any]:
    def run():
        errors = []
        try:
            t = _tap(config.IRSA_TAP_URL,
                     f"SELECT TOP {max_rows} designation, ra, dec, w1mpro, w2mpro FROM allwise_p3as_psd "
                     f"WHERE 1=CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius_deg:.5f}))")
            rows = [{"id": str(r["designation"]), "ra": float(r["ra"]), "dec": float(r["dec"]),
                     "w1": _num(r["w1mpro"]), "w2": _num(r["w2mpro"])} for r in t]
            return {"catalog": "AllWISE", "service": "IRSA", "epoch": 2010.5, "sources": rows}
        except Exception as e:
            errors.append(f"IRSA: {e.__class__.__name__}")
        try:
            t = _tap(config.GAIA_VIZIER_TAP,
                     f'SELECT TOP {max_rows} AllWISE, RAJ2000, DEJ2000, W1mag, W2mag FROM "II/328/allwise" '
                     f"WHERE 1=CONTAINS(POINT('ICRS', RAJ2000, DEJ2000), CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {radius_deg:.5f}))")
            rows = [{"id": str(r["AllWISE"]), "ra": float(r["RAJ2000"]), "dec": float(r["DEJ2000"]),
                     "w1": _num(r["W1mag"]), "w2": _num(r["W2mag"])} for r in t]
            return {"catalog": "AllWISE", "service": "VizieR (CDS) II/328", "epoch": 2010.5, "sources": rows}
        except Exception as e:
            errors.append(f"VizieR: {e.__class__.__name__}")
        raise CatalogUnavailable("AllWISE no disponible: " + " | ".join(errors))

    return _cached("allwise", f"{ra:.4f}:{dec:.4f}:{radius_deg:.4f}", run)


def gaia_position_at(src: Dict[str, Any], year: float):
    """Posición de una fuente Gaia (época 2016.0) en otra fecha, ignorando paralaje."""
    dt = year - 2016.0
    pmra, pmdec = src.get("pmra") or 0.0, src.get("pmdec") or 0.0
    dec = src["dec"] + pmdec / 3.6e6 * dt
    ra = src["ra"] + pmra / 3.6e6 * dt / max(np.cos(np.radians(src["dec"])), 1e-6)
    return ra, dec
