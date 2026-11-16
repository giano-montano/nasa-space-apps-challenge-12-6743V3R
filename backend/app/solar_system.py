"""
Cotejo con cuerpos conocidos del Sistema Solar (asteroides y cometas) usando la
API de identificación de cuerpos menores de JPL (sb_ident).

Se consulta una vez por fecha (época) el campo completo del recorte, y luego cada
candidato/transitorio se compara con los cuerpos que JPL predice en esa fecha.
El observador es geocéntrico (código MPC 500): SPHEREx está en órbita baja, así
que la paralaje es pequeña salvo para objetos cercanos a la Tierra. Es un cotejo
AUTOMÁTICO Y APROXIMADO; el candidato sigue siendo para revisión humana.
Si JPL no responde se devuelve None y el candidato queda "sin cotejar".
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from astropy.time import Time

from . import config

_session = requests.Session()
_session.headers["User-Agent"] = "spherex-sky-viewer/3.0 (NASA Space Apps 2026)"


def _sexa_ra(ra_deg: float) -> str:
    h = (ra_deg % 360.0) / 15.0
    hh = int(h)
    m = (h - hh) * 60
    mm = int(m)
    ss = (m - mm) * 60
    return f"{hh:02d}-{mm:02d}-{ss:05.2f}"


def _sexa_dec(dec_deg: float) -> str:
    sign = "-" if dec_deg < 0 else "+"
    a = abs(dec_deg)
    dd = int(a)
    m = (a - dd) * 60
    mm = int(m)
    ss = (m - mm) * 60
    return f"{sign}{dd:02d}-{mm:02d}-{ss:05.2f}"


def _parse_ra(s: str) -> float:
    h, m, sec = s.split(":")
    return (float(h) + float(m) / 60 + float(sec) / 3600) * 15.0


def _parse_dec(s: str) -> float:
    mt = re.match(r"([+-])(\d+)\s+(\d+)'([\d.]+)\"", s.strip())
    if not mt:
        raise ValueError(s)
    v = int(mt.group(2)) + int(mt.group(3)) / 60 + float(mt.group(4)) / 3600
    return -v if mt.group(1) == "-" else v


def _cache_path(key: str) -> str:
    d = os.path.join(config.CACHE_DIR, "solar_system")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, hashlib.sha1(key.encode()).hexdigest()[:20] + ".json")


def known_bodies(ra: float, dec: float, radius_deg: float, mjd: float, vmag_lim: float = 22.0,
                 timeout: float = 25.0) -> Optional[List[Dict[str, Any]]]:
    """
    Cuerpos menores que JPL predice dentro del campo en la fecha dada.
    Devuelve None si el servicio no responde (distinto de lista vacía = "no hay ninguno").
    """
    key = f"{ra:.3f}:{dec:.3f}:{radius_deg:.3f}:{mjd:.2f}:{vmag_lim}"
    p = _cache_path(key)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    when = Time(mjd, format="mjd", scale="utc").utc.strftime("%Y-%m-%dT%H:%M:%S")
    hw_dec = min(radius_deg, 89.0)
    hw_ra = min(radius_deg / max(np.cos(np.radians(dec)), 0.02), 179.0)
    params = {
        "mpc-code": "500", "obs-time": when,
        "fov-ra-center": _sexa_ra(ra), "fov-dec-center": _sexa_dec(dec),
        "fov-ra-hwidth": f"{hw_ra:.4f}", "fov-dec-hwidth": f"{hw_dec:.4f}",
        "vmag-lim": str(vmag_lim),
    }
    try:
        r = _session.get(config.JPL_SBIDENT_URL, params=params, timeout=timeout)
        if r.status_code != 200:
            return None
        js = r.json()
        rows = js.get("data_first_pass") or js.get("data_second_pass") or []
        fields = js.get("fields_first") or js.get("fields_second") or []
        if rows and not fields:
            return None
        out = []
        for row in rows:
            d = dict(zip(fields, row))
            out.append({
                "name": str(d.get("Object name", "")).strip(),
                "ra_deg": round(_parse_ra(d["Astrometric RA (hh:mm:ss)"]), 6),
                "dec_deg": round(_parse_dec(d["Astrometric Dec (dd mm'ss\")"]), 6),
                "vmag": _f(d.get("Visual magnitude (V)")),
                "ra_rate_arcsec_h": _f(d.get('RA rate ("/h)')),
                "dec_rate_arcsec_h": _f(d.get('Dec rate ("/h)')),
            })
    except Exception:
        return None
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(out, f)
    except OSError:
        pass
    return out


def _f(v):
    try:
        x = float(v)
        return x if np.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def match_body(ra: float, dec: float, bodies: List[Dict[str, Any]], tol_arcsec: float) -> Optional[Dict[str, Any]]:
    """Cuerpo predicho más cercano a (ra, dec) dentro de la tolerancia."""
    best = None
    cosd = np.cos(np.radians(dec))
    for b in bodies:
        d = np.hypot((b["ra_deg"] - ra) * cosd, b["dec_deg"] - dec) * 3600.0
        if d <= tol_arcsec and (best is None or d < best["sep_arcsec"]):
            rate = float(np.hypot((b.get("ra_rate_arcsec_h") or 0), (b.get("dec_rate_arcsec_h") or 0)))
            best = {"catalog": "JPL SBDB (sb_ident)", "name": b["name"], "sep_arcsec": round(float(d), 1),
                    "vmag": b.get("vmag"), "motion_arcsec_h": round(rate, 2)}
    return best


def crossmatch_solar_system(items: List[Dict[str, Any]], epoch_mjd: Dict[int, float], center_ra: float,
                            center_dec: float, radius_deg: float, tol_arcsec: float) -> Dict[str, Any]:
    """
    items: dicts con ra_deg, dec_deg y 'epochs' (lista de épocas en las que se ve).
    Rellena item['ss_match'] (dict o None) e item['ss_checked'] (bool). Devuelve un resumen.
    """
    cache: Dict[int, Optional[List[Dict[str, Any]]]] = {}
    n_ok = n_fail = 0
    for it in items:
        matches, failed = [], False
        for e in it["epochs"]:
            if e not in cache:
                cache[e] = known_bodies(center_ra, center_dec, radius_deg, epoch_mjd[e])
            bodies = cache[e]
            if bodies is None:
                failed = True
                continue
            # La posición medida en la época e se compara con la predicha en esa misma fecha.
            pos = it["positions_by_epoch"].get(e, (it["ra_deg"], it["dec_deg"]))
            m = match_body(pos[0], pos[1], bodies, tol_arcsec)
            if m:
                m["epoch"] = e
                matches.append(m)
        if matches:
            it["ss_match"] = min(matches, key=lambda m: m["sep_arcsec"])
            it["ss_checked"] = True
            n_ok += 1
        else:
            it["ss_match"] = None
            it["ss_checked"] = not failed
            n_fail += int(failed)
    return {"service": "JPL SBDB sb_ident", "epochs_queried": len(cache),
            "epochs_failed": sum(1 for v in cache.values() if v is None), "n_matched": n_ok}
