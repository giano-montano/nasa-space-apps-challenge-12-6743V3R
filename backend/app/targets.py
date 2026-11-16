"""
Objetivos de prueba obligatorios del reto y resolución de nombres.

Posiciones y movimientos propios copiados de SIMBAD (vía Sesame, CDS) el
2026-11-15. Las posiciones son ICRS en la época J2000; para cada fecha de
observación se propagan con el movimiento propio (ver coords.position_at).
"""

from typing import Any, Dict, Optional
import math
import re

import requests

from . import config

TARGETS: Dict[str, Dict[str, Any]] = {
    "wise0855": {
        "id": "wise0855",
        "detectors": [4, 5, 6],  # detectores donde el objeto brilla más
        "name": "WISE 0855",
        "simbad": "WISEA J085510.74-071442.5",
        "kind": "Enana marrón muy fría (tipo Y)", "category": "ty_dwarf",
        "ra": 133.81890825, "dec": -7.24704800,
        "pmra": -8123.7, "pmdec": 673.2, "parallax": 439.0,  # mas/yr, mas
        "behavior": "moving",
        "description": "Enana marrón a ~7,4 años luz, una de las más frías conocidas. "
                       "Se mueve ~8,1″/año: en SPHEREx (6,2″/píxel) se desplaza cerca de un píxel por año.",
        "ref": "Kirkpatrick et al. 2021 (ApJS 253, 7)",
    },
    "barnard": {
        "id": "barnard",
        "detectors": [1, 2],  # detectores donde el objeto brilla más
        "name": "Estrella de Barnard",
        "simbad": "Barnard's Star",
        "kind": "Enana roja cercana (M4V)", "category": "star",
        "ra": 269.45207696, "dec": 4.69336497,
        "pmra": -801.551, "pmdec": 10362.394, "parallax": 546.9759,
        "behavior": "moving",
        "description": "La estrella con mayor movimiento propio conocido (~10,4″/año hacia el norte), a 6 años luz.",
        "ref": "Gaia DR3 (vía SIMBAD)",
    },
    "eps_indi_b": {
        "id": "eps_indi_b",
        "detectors": [4, 5, 6],  # detectores donde el objeto brilla más
        "name": "Epsilon Indi B",
        "simbad": "eps Ind B",
        "kind": "Par de enanas marrones (T1 + T6)", "category": "ty_dwarf",
        "ra": 331.04414659, "dec": -56.78284420,
        "pmra": 3981.977, "pmdec": -2466.832, "parallax": 270.6580,
        "behavior": "moving",
        "description": "Dos enanas marrones que orbitan juntas a la estrella Epsilon Indi A (a ~6,7′ de distancia). "
                       "SPHEREx no separa el par (están a ~0,7″), se ve como un solo punto que se mueve ~4,7″/año.",
        "ref": "Gaia DR3 (vía SIMBAD)",
    },
    "rw_aur": {
        "id": "rw_aur",
        "detectors": [3],  # detectores donde el objeto brilla más
        "name": "RW Aurigae",
        "simbad": "RW Aur",
        "kind": "Estrella joven variable (T Tauri)", "category": "yso",
        "ra": 76.95652603, "dec": 30.40143817,
        "pmra": 7.23, "pmdec": -20.33, "parallax": 15.42,
        "behavior": "variable",
        "description": "Estrella joven con disco de polvo. No se desplaza de forma visible: cambia de brillo. "
                       "Mira la curva de luz.",
        "ref": "van Leeuwen 2007 (vía SIMBAD)",
    },
    "r_dra": {
        "id": "r_dra",
        "detectors": [2],  # detectores donde el objeto brilla más
        "name": "R Draconis",
        "simbad": "R Dra",
        "kind": "Gigante roja pulsante (tipo Mira)", "category": "star",
        "ra": 248.16761083, "dec": 66.75497942,
        "pmra": -20.643, "pmdec": 6.149, "parallax": 1.2509,
        "behavior": "variable",
        "description": "Gigante roja que pulsa con un periodo de ~245 días. No se desplaza: cambia mucho de brillo "
                       "en el infrarrojo. Mira la curva de luz.",
        "ref": "Gaia DR3 (vía SIMBAD)",
    },
}


def public_targets():
    return list(TARGETS.values())


def find_target(target_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not target_id:
        return None
    return TARGETS.get(target_id)


def find_nearby_target(ra: float, dec: float, max_arcmin: float = 2.0) -> Optional[Dict[str, Any]]:
    """Devuelve el objetivo de prueba más cercano si está a menos de max_arcmin (en J2000)."""
    best, best_d = None, float("inf")
    for t in TARGETS.values():
        dra = (ra - t["ra"]) * math.cos(math.radians(dec))
        d = math.hypot(dra, dec - t["dec"]) * 60.0
        # Los objetivos rápidos se desplazan ~2-4′ desde J2000: margen extra.
        limit = max_arcmin + (4.5 if t["behavior"] == "moving" else 0.0)
        if d < limit and d < best_d:
            best, best_d = t, d
    return best


_SESAME_LINE = re.compile(r"^%(\w)(\.\w+)?\s+(.*)$")


def resolve_name(name: str) -> Dict[str, Any]:
    """
    Resuelve un nombre (p. ej. "Barnard's Star", "M31") con Sesame del CDS
    (SIMBAD, NED, VizieR). Devuelve posición J2000 y, si existe, movimiento propio.
    """
    name = name.strip()
    if not name:
        raise ValueError("Escribe un nombre de objeto.")
    for t in TARGETS.values():
        if name.lower() in (t["name"].lower(), t["simbad"].lower(), t["id"]):
            return {"name": t["name"], "ra": t["ra"], "dec": t["dec"], "pmra": t["pmra"],
                    "pmdec": t["pmdec"], "parallax": t["parallax"], "source": "catálogo local (SIMBAD)",
                    "target_id": t["id"]}

    resp = requests.get(config.SESAME_URL + "?" + requests.utils.quote(name),
                        timeout=config.HTTP_TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    out: Dict[str, Any] = {"name": name, "source": "Sesame (CDS)"}
    for line in resp.text.splitlines():
        m = _SESAME_LINE.match(line.strip())
        if not m:
            continue
        key, rest = m.group(1), m.group(3)
        if key == "J" and "ra" not in out:
            parts = rest.split()
            out["ra"], out["dec"] = float(parts[0]), float(parts[1])
        elif key == "P" and "pmra" not in out:
            parts = rest.split()
            try:
                out["pmra"], out["pmdec"] = float(parts[0]), float(parts[1])
            except (ValueError, IndexError):
                pass
        elif key == "X" and "parallax" not in out:
            try:
                out["parallax"] = float(rest.split()[0])
            except (ValueError, IndexError):
                pass
        elif key == "I" and m.group(2) == ".0":
            out["main_id"] = rest.strip()
    if "ra" not in out:
        raise ValueError(f"No encontré «{name}» en SIMBAD/NED/VizieR. Prueba con coordenadas.")
    return out
