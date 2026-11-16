"""
¿Qué tipo de objeto es? Clasificación en tres capas, de más a menos fiable:

1. Catálogo: si SIMBAD (o la ficha local de los objetivos del reto) ya conoce el
   objeto, esa es la respuesta.
2. Espectro: el espectro de SPHEREx (0,75–5 µm) se ajusta con plantillas físicas
   de cada clase (estrella, enana marrón L, enana marrón T/Y, cuásar, galaxia,
   objeto estelar joven). También prueba "mezcla con una estrella de fondo",
   porque con píxeles de 6″ dos fuentes cercanas se suman.
3. Contexto: movimiento propio, cambio de brillo y latitud galáctica ajustan las
   probabilidades del espectro (p. ej. algo que se mueve no puede ser un cuásar).

Las plantillas son aproximaciones físicas (cuerpo negro + bandas de absorción y
emisión típicas), no modelos entrenados: las probabilidades son "qué plantilla
ajusta mejor", no probabilidades calibradas. Por eso el resultado se rotula como
sugerencia para revisión humana.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
from astropy.coordinates import SkyCoord
from astropy.io.votable import parse_single_table

from . import config

CLASSES = ["star", "l_dwarf", "ty_dwarf", "yso", "quasar", "galaxy"]
LABELS = {
    "star": "Estrella",
    "l_dwarf": "Enana marrón tipo L (o enana roja ultrafría)",
    "ty_dwarf": "Enana marrón tipo T/Y",
    "yso": "Estrella joven con disco de polvo",
    "quasar": "Cuásar o núcleo activo de galaxia",
    "galaxy": "Galaxia",
}
SHORT = {"star": "estrella", "l_dwarf": "enana L", "ty_dwarf": "enana T/Y", "yso": "estrella joven",
         "quasar": "cuásar", "galaxy": "galaxia"}

# ---------------------------------------------------------------------------
# Capa 2: plantillas físicas (Fν en función de λ en µm)
# ---------------------------------------------------------------------------


def _bb(lam, T):
    x = np.minimum(14387.77 / (lam * T), 700.0)
    return lam ** -3 / np.expm1(x)


def _ab(lam, c, w, depth):
    return 1.0 - depth * np.exp(-0.5 * ((lam - c) / w) ** 2)


def _em(lam, c, w, amp):
    return amp * np.exp(-0.5 * ((lam - c) / w) ** 2)


def _star(T):
    def f(l):
        s = _bb(l, T)
        if T <= 3400:  # enanas M y gigantes frías: agua y CO
            s = s * _ab(l, 1.4, 0.06, 0.15) * _ab(l, 1.9, 0.08, 0.15) * _ab(l, 2.7, 0.15, 0.15) * _ab(l, 2.35, 0.05, 0.1)
        return s
    return f


def _ldwarf(T):
    def f(l):
        s = (_bb(l, T) * _ab(l, 1.4, 0.07, 0.5) * _ab(l, 1.9, 0.1, 0.5) * _ab(l, 2.75, 0.2, 0.4)
             * _ab(l, 2.35, 0.05, 0.2) * _ab(l, 4.65, 0.15, 0.25))
        if T < 1600:
            s = s * _ab(l, 3.35, 0.08, 0.25)
        return s
    return f


def _tydwarf(T):
    def f(l):
        return (_bb(l, T) * _ab(l, 1.15, 0.05, 0.6) * _ab(l, 1.4, 0.08, 0.85) * _ab(l, 1.7, 0.1, 0.6)
                * _ab(l, 1.9, 0.12, 0.85) * _ab(l, 2.25, 0.25, 0.7) * _ab(l, 2.8, 0.2, 0.85)
                * _ab(l, 3.35, 0.25, 0.9) * _ab(l, 4.3, 0.08, 0.3) * _ab(l, 4.65, 0.15, 0.3))
    return f


def _quasar(alpha, dust, warm):
    """Disco de acreción (ley de potencias) + polvo caliente (~1400 K) + polvo templado (~700 K)."""
    def f(l):
        disk = l ** alpha / 3.0 ** alpha
        hot = _bb(l, 1400.0) / _bb(np.array(3.0), 1400.0)
        tw = _bb(l, 700.0) / _bb(np.array(4.5), 700.0)
        return disk + dust * hot + warm * tw
    return f


def _galaxy(z, sf):
    def f(l):
        r = l / (1 + z)
        s = _bb(r, 3600.0) * (1 + 0.15 * np.exp(-0.5 * ((r - 1.6) / 0.35) ** 2))
        s = s / _bb(np.array(1.6), 3600.0)
        if sf:  # formación estelar: PAH 3,3 µm y polvo templado
            s = s + _em(r, 3.3, 0.03, 0.15) + 0.4 * _bb(r, 500.0) / _bb(np.array(4.5), 500.0) * (r / 4.5) ** 0
        return s
    return f


def _yso(Td, excess, ice):
    def f(l):
        st = _bb(l, 4000.0) / _bb(np.array(3.0), 4000.0)
        d = _bb(l, Td) / _bb(np.array(3.0), Td)
        return (st + excess * d) * _ab(l, 3.05, 0.12, ice)
    return f


TEMPLATES: Dict[str, List[Tuple[str, Any]]] = {
    "star": [(f"T={T} K", _star(T)) for T in (2600, 3000, 3400, 4000, 5000, 6500, 9000, 15000)],
    "l_dwarf": [(f"T={T} K", _ldwarf(T)) for T in (1400, 1700, 2000)],
    "ty_dwarf": [(f"T={T} K", _tydwarf(T)) for T in (400, 550, 750, 1000, 1250)],
    "yso": [(f"polvo {Td} K ×{e}{' + hielo' if ice else ''}", _yso(Td, e, ice))
            for Td in (700, 1000, 1400) for e in (0.5, 2.0, 8.0) for ice in (0.0, 0.3)],
    "quasar": [(f"α={a}, polvo ×{d}+{w}", _quasar(a, d, w)) for a in (-0.3, 0.0, 0.5)
               for d in (0.5, 2.0, 6.0) for w in (0.0, 2.0, 6.0)],
    "galaxy": [(f"z={z}{' con formación estelar' if sf else ''}", _galaxy(z, sf))
               for z in (0.0, 0.1, 0.3) for sf in (False, True)],
}
BACKGROUND_STARS = [_star(T) for T in (3400, 5000, 9000)]
RANGES = [(0.7, 1.5), (1.5, 2.5), (2.5, 3.8), (3.8, 5.1)]


def _robust_fit(A: np.ndarray, f: np.ndarray, s: np.ndarray, iters: int = 4):
    """Mínimos cuadrados no negativos con pesos robustos (Cauchy, c=3). A: (n, k)."""
    from scipy.optimize import nnls
    w = np.ones_like(f)
    coef = np.zeros(A.shape[1])
    for _ in range(iters):
        sw = np.sqrt(w) / s
        coef, _ = nnls(A * sw[:, None], f * sw)
        r = (f - A @ coef) / s
        w = 1.0 / (1.0 + (r / 3.0) ** 2)
    r = (f - A @ coef) / s
    loss = float(np.sum(9.0 * np.log1p((r / 3.0) ** 2)))
    return coef, loss


def classify_spectrum(points: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Capa 2. Devuelve probabilidades por clase y el mejor ajuste (para dibujarlo)."""
    good = [p for p in points if not p.get("saturated") and np.isfinite(p["flux_mjy"]) and p["err_mjy"] > 0]
    n_sat = len(points) - len(good)
    out: Dict[str, Any] = {"available": False, "n_points": len(good), "n_saturated": n_sat}
    if points and n_sat / len(points) > 0.5:
        out["reason"] = (f"{n_sat} de {len(points)} colores están saturados: la forma del espectro no es fiable "
                         "y no se clasifica por espectro.")
        return out
    lam = np.array([p["wavelength_um"] for p in good])
    flx = np.array([p["flux_mjy"] for p in good])
    err = np.array([p["err_mjy"] for p in good])
    covered = sum(1 for a, b in RANGES if ((lam >= a) & (lam < b)).sum() >= 3)
    if len(good) < 15 or covered < 3:
        out["reason"] = "Hay pocos colores medidos (hacen falta al menos 15 repartidos en 0,75–5 µm)."
        return out
    snr = float(np.median(flx / err))
    if snr < 3:
        out["reason"] = f"La fuente es demasiado débil (S/R mediana {snr:.1f}) para leer la forma del espectro."
        return out

    # Error con un piso sistemático: las plantillas son aproximadas (~10 %).
    scale = float(np.median(np.abs(flx)))
    sig = np.sqrt(err ** 2 + (0.10 * np.abs(flx)) ** 2 + (0.02 * scale) ** 2)
    n = len(flx)
    bgs = np.array([b(lam) / np.median(b(lam)) for b in BACKGROUND_STARS])

    results = {}
    for cls, fams in TEMPLATES.items():
        best = None
        for name, fn in fams:
            t = fn(lam)
            t = t / np.median(t)
            coef, loss = _robust_fit(t[:, None], flx, sig)
            cand = {"loss": loss, "template": name, "fn": fn, "coef": coef, "blend": None}
            if cls != "star":  # ¿mezcla con una estrella de fondo?
                for j, b in enumerate(bgs):
                    c2, l2 = _robust_fit(np.column_stack([t, b]), flx, sig)
                    l2 += 2.0 * np.log(n)  # penalización por el parámetro extra (BIC)
                    if c2[0] > 0 and c2[1] > 0 and l2 < cand["loss"]:
                        cand = {"loss": l2, "template": name, "fn": fn, "coef": c2, "blend": j}
            if best is None or cand["loss"] < best["loss"]:
                best = cand
        results[cls] = best

    lmin = min(r["loss"] for r in results.values())
    dof = max(n - 2, 1)
    # Temperatura: si ninguna plantilla ajusta bien, las diferencias pesan menos (κ=5 por ser plantillas aproximadas).
    temp = 2.0 * 5.0 * max(1.0, lmin / dof)
    w = {c: np.exp(-(r["loss"] - lmin) / temp) for c, r in results.items()}
    tot = sum(w.values())
    probs = {c: round(float(v / tot), 3) for c, v in w.items()}
    top = max(probs, key=probs.get)
    b = results[top]

    # Curva del mejor ajuste para dibujar sobre el espectro.
    grid = np.linspace(0.72, 5.05, 160)
    lt = b["fn"](lam)
    tg = b["fn"](grid) / np.median(lt)
    model = b["coef"][0] * tg
    bg_curve = None
    if b["blend"] is not None:
        bf = BACKGROUND_STARS[b["blend"]]
        bg_curve = b["coef"][1] * bf(grid) / np.median(bf(lam))
        model = model + bg_curve
    blend_frac = None
    if b["blend"] is not None:
        main = b["coef"][0] * lt / np.median(lt)
        bgp = b["coef"][1] * BACKGROUND_STARS[b["blend"]](lam) / np.median(BACKGROUND_STARS[b["blend"]](lam))
        blend_frac = round(float(np.sum(bgp) / np.sum(main + bgp)), 2)

    out.update({
        "available": True, "probabilities": probs, "top": top, "label": LABELS[top],
        "template": b["template"], "reduced_loss": round(lmin / dof, 2), "median_snr": round(snr, 1),
        "blend": ({"background_fraction": blend_frac,
                   "note": "El espectro se explica mejor como mezcla con una estrella de fondo "
                           f"(~{round(100 * blend_frac)} % de la luz): con píxeles de 6″ dos fuentes cercanas se suman."}
                  if b["blend"] is not None else None),
        "model_curve": [[round(float(x), 3), round(float(y), 5)] for x, y in zip(grid, model)],
        "background_curve": ([[round(float(x), 3), round(float(y), 5)] for x, y in zip(grid, bg_curve)]
                             if bg_curve is not None else None),
        "fit_quality": ("bueno" if lmin / dof < 2 else "regular" if lmin / dof < 6 else "malo: ninguna plantilla describe bien este espectro"),
    })
    return out


# ---------------------------------------------------------------------------
# Capa 1: catálogo (SIMBAD; ficha local de los objetivos del reto)
# ---------------------------------------------------------------------------

_YSO = {"Y*O", "Y*?", "TT*", "TT?", "Or*", "Ae*", "Ae?", "pr*", "pr?", "HH", "out"}
_QSO = {"QSO", "Q?", "AGN", "AG?", "Sy1", "Sy2", "SyG", "Bla", "BLL", "Bz?", "BL?", "LIN", "Sy?"}
_GAL = {"G", "G?", "GiC", "GiG", "GiP", "BiC", "SBG", "SB?", "EmG", "rG", "IG", "PaG", "H2G", "LSB", "bCG",
        "GrG", "ClG", "CGG", "C?G", "Gr?"}
_BD = {"BD*", "BD?"}


def simbad_category(otype: str, sp_type: str = "") -> Optional[str]:
    o, sp = (otype or "").strip(), (sp_type or "").strip().upper()
    if o in _BD:
        return "ty_dwarf" if sp[:1] in ("T", "Y") else "l_dwarf"
    if sp[:1] in ("T", "Y") and o in ("*", "PM*", "BD*", "BD?", "LM*"):
        return "ty_dwarf"
    if sp[:1] == "L" and o in ("*", "PM*", "LM*", "BD*"):
        return "l_dwarf"
    if o in _YSO:
        return "yso"
    if o in _QSO:
        return "quasar"
    if o in _GAL:
        return "galaxy"
    if o.endswith("*") or o in ("**", "SB*", "EB*", "PM*", "HS*", "V*", "Mi*", "LP*", "C*", "S*", "WD*"):
        return "star"
    return None


def _cache_path(key: str) -> str:
    d = os.path.join(config.CACHE_DIR, "catalogs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "simbad_" + hashlib.sha1(key.encode()).hexdigest()[:20] + ".json")


def simbad_near(ra: float, dec: float, year: float, radius_arcsec: float = 9.0) -> Dict[str, Any]:
    """Objeto de SIMBAD más cercano a (ra, dec) en la fecha `year`, propagando movimientos propios."""
    key = f"{ra:.5f}:{dec:.5f}:{year:.1f}"
    p = _cache_path(key)
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 7 * 86400:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    # Radio amplio solo para objetos rápidos (se desplazan minutos de arco desde J2000).
    adql = (
        "SELECT TOP 60 b.main_id, b.ra, b.dec, b.otype, b.sp_type, b.pmra, b.pmdec, b.plx_value, d.description "
        "FROM basic AS b LEFT JOIN otypedef AS d ON d.otype = b.otype "
        f"WHERE 1=CONTAINS(POINT('ICRS', b.ra, b.dec), CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, 0.085)) "
        f"AND (1=CONTAINS(POINT('ICRS', b.ra, b.dec), CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, 0.006)) "
        "OR b.pmra*b.pmra + b.pmdec*b.pmdec > 250000)"
    )
    try:
        r = requests.post(config.SIMBAD_TAP_URL, data={"QUERY": adql, "FORMAT": "votable", "LANG": "ADQL",
                                                      "REQUEST": "doQuery"}, timeout=(5, 12))
        if r.status_code != 200 or b"VOTABLE" not in r.content[:2000].upper():
            raise RuntimeError(f"HTTP {r.status_code}")
        t = parse_single_table(io.BytesIO(r.content)).to_table(use_names_over_ids=True)
    except Exception as e:  # SIMBAD caído o lento: no se guarda en caché
        return {"available": False, "error": "SIMBAD (CDS) no responde ahora", "detail": f"{e.__class__.__name__}: {str(e)[:80]}"}
    dt = year - 2000.0
    best, bd = None, radius_arcsec
    cosd = np.cos(np.radians(dec))
    for row in t:
        pmra = float(row["pmra"]) if np.isfinite(_f(row["pmra"])) else 0.0
        pmdec = float(row["pmdec"]) if np.isfinite(_f(row["pmdec"])) else 0.0
        rra = float(row["ra"]) + pmra / 3.6e6 * dt / max(cosd, 1e-6)
        rde = float(row["dec"]) + pmdec / 3.6e6 * dt
        sep = float(np.hypot((rra - ra) * cosd, rde - dec) * 3600)
        if sep < bd:
            bd = sep
            best = {"main_id": str(row["main_id"]), "otype": str(row["otype"]), "sp_type": _s(row["sp_type"]),
                    "description": _s(row["description"]), "sep_arcsec": round(sep, 1),
                    "pm_arcsec_yr": round(float(np.hypot(pmra, pmdec)) / 1000, 3) if (pmra or pmdec) else None,
                    "parallax_mas": _f(row["plx_value"]) if np.isfinite(_f(row["plx_value"])) else None}
    res = {"available": True, "match": best, "service": "SIMBAD (CDS)"}
    if best:
        best["category"] = simbad_category(best["otype"], best["sp_type"])
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(res, fh)
    return res


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _s(v):
    s = "" if v is None else str(v)
    return "" if s in ("--", "None", "nan") else s


# ---------------------------------------------------------------------------
# Capa 3: contexto + decisión final
# ---------------------------------------------------------------------------

def combine(spec: Dict[str, Any], catalog: Optional[Dict[str, Any]], pm_arcsec_yr: Optional[float],
            pm_source: Optional[str], var_mag: Optional[float], ra: float, dec: float) -> Dict[str, Any]:
    reasons: List[str] = []
    # Piso del 10 %: las plantillas son aproximadas, el contexto debe poder corregirlas.
    p = ({c: 0.9 * v + 0.1 / len(CLASSES) for c, v in spec["probabilities"].items()} if spec.get("available")
         else {c: 1.0 / len(CLASSES) for c in CLASSES})
    if spec.get("available"):
        top = spec["top"]
        reasons.append(f"Espectro: se parece más a «{SHORT[top]}» ({round(100 * spec['probabilities'][top])} % entre "
                       f"las plantillas; ajuste {spec['fit_quality']}).")
        if spec.get("blend"):
            reasons.append(spec["blend"]["note"])
    else:
        reasons.append("Espectro: " + (spec.get("reason") or "no disponible."))

    def mult(m: Dict[str, float]):
        for c, f in m.items():
            p[c] *= f

    if pm_arcsec_yr is not None:
        src = f" ({pm_source})" if pm_source else ""
        if pm_arcsec_yr >= 0.05:
            mult({"quasar": 0.02, "galaxy": 0.02})
            if pm_arcsec_yr >= 1.0:
                mult({"yso": 0.2, "l_dwarf": 1.5, "ty_dwarf": 1.5})
                reasons.append(f"Movimiento: {pm_arcsec_yr:.2f}″/año{src}. Algo tan rápido está muy cerca (decenas de "
                               "años luz): descarta cuásares y galaxias y favorece enanas rojas o marrones.")
            else:
                reasons.append(f"Movimiento: {pm_arcsec_yr:.2f}″/año{src}: está en nuestra galaxia (descarta cuásar y galaxia).")
        else:
            reasons.append(f"Movimiento: ~0″/año{src}; no descarta nada (Drift solo ve ≳1″/año).")
    unreliable_var = bool(spec.get("blend")) or (pm_arcsec_yr or 0) >= 1.0
    if var_mag is not None and unreliable_var:
        reasons.append(f"Brillo: cambió {var_mag:.2f} mag, pero no se usa como pista: al moverse o mezclarse con una "
                       "fuente vecina, la medida incluye luz ajena que cambia entre fechas.")
    elif var_mag is not None:
        if var_mag >= 0.2:
            mult({"yso": 2.0, "quasar": 1.5, "l_dwarf": 0.5, "ty_dwarf": 0.5, "galaxy": 0.3})
            reasons.append(f"Brillo: cambió {var_mag:.2f} mag entre fechas. Típico de estrellas jóvenes, variables o cuásares.")
        elif var_mag < 0.05:
            mult({"yso": 0.7})
            reasons.append(f"Brillo: estable (cambio < {max(var_mag, 0.01):.2f} mag).")
    b = float(SkyCoord(ra, dec, unit="deg").galactic.b.deg)
    if abs(b) < 10:
        mult({"quasar": 0.3, "galaxy": 0.3, "yso": 1.5})
        reasons.append(f"Posición: latitud galáctica {b:+.0f}°, en el plano de la Vía Láctea (más estrellas jóvenes; "
                       "el polvo oculta galaxias lejanas).")
    elif abs(b) > 30:
        mult({"yso": 0.4})
        reasons.append(f"Posición: latitud galáctica {b:+.0f}°, lejos del plano (pocas estrellas jóvenes).")

    tot = sum(p.values()) or 1.0
    p = {c: round(v / tot, 3) for c, v in p.items()}
    ranked = sorted(p, key=p.get, reverse=True)
    top, second = ranked[0], ranked[1]
    method = "espectro + contexto"
    cat = (catalog or {}).get("category")
    if cat:
        conf = "alta"
        method = "catálogo"
        agree = spec.get("available") and spec["top"] == cat
        reasons.insert(0, f"Catálogo: {catalog['name']} es «{catalog.get('kind') or SHORT[cat]}» "
                          f"({catalog['source']}).")
        if spec.get("available"):
            reasons.append("El espectro de SPHEREx coincide con el catálogo." if agree else
                           f"El espectro de SPHEREx no coincide del todo (sugiere «{SHORT[spec['top']]}»): puede deberse "
                           "a saturación, a una fuente vecina mezclada o a que la plantilla es aproximada.")
        final, prob = cat, None
    else:
        final, prob = top, p[top]
        conf = "media" if prob >= 0.6 else "baja"
        if not spec.get("available") and prob < 0.4:
            final, conf = None, "ninguna"
    if final is None:
        verdict = "No se puede clasificar con los datos disponibles."
    elif method == "catálogo":
        verdict = f"{LABELS[final]} (conocido en catálogo)."
    elif conf == "media":
        verdict = f"Probablemente: {LABELS[final][0].lower() + LABELS[final][1:]}."
    else:
        verdict = f"Incierto: quizá {SHORT[top]} ({round(100 * p[top])} %) o {SHORT[second]} ({round(100 * p[second])} %)."
    return {"category": final, "label": LABELS.get(final) if final else None, "verdict": verdict,
            "confidence": conf, "method": method, "probabilities": p, "reasons": reasons,
            "galactic_b": round(b, 1)}
