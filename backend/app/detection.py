"""
Detección asistida de movimiento sobre las imágenes combinadas por época.

Pasos (todo sobre datos reales, en la rejilla común):
 1. Detectar fuentes en cada época (picos > umbral·σ) y medir su centroide.
 2. Enlazar cada fuente entre épocas (vecino más cercano dentro de un radio).
 3. Ajustar un movimiento lineal (posición vs tiempo) y su incertidumbre.
 4. Marcar como candidato lo que se mueve de forma significativa.
 5. Cotejar con Gaia DR3 (posición propagada a la fecha) para separar lo ya
    conocido de lo no catalogado.
Siempre son CANDIDATOS PARA REVISIÓN HUMANA, nunca descubrimientos.

Limitaciones: píxeles de 6,2″ y pocas épocas (~6 meses entre visitas): solo
movimientos de ≳ 1″/año en fuentes brillantes. Campos densos generan
confusiones. Los cuerpos del Sistema Solar se cotejan con JPL sb_ident desde
un observador geocéntrico (aproximado: SPHEREx no tiene código MPC propio);
un objeto que aparece en una sola época se reporta como "transitorio".
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from astropy.wcs import WCS
from scipy import ndimage

from . import config
from .catalogs import gaia_position_at
from .processing import robust_sigma
from .solar_system import crossmatch_solar_system

YEAR = 365.25


def find_sources(data: np.ndarray, err: Optional[np.ndarray], nsigma: float = 5.0, max_n: int = 300) -> List[Dict[str, float]]:
    d = np.nan_to_num(data - np.nanmedian(data), nan=0.0)
    sig = robust_sigma(d)
    smooth = ndimage.gaussian_filter(d, 0.8)
    peaks = (smooth == ndimage.maximum_filter(smooth, size=3)) & (smooth > nsigma * sig * 0.6) & (d > nsigma * sig)
    ys, xs = np.nonzero(peaks)
    out = []
    n = d.shape[0]
    for y, x in zip(ys, xs):
        if x < 2 or y < 2 or x > n - 3 or y > n - 3:
            continue
        cut = np.clip(d[y - 1:y + 2, x - 1:x + 2], 0, None)
        tot = cut.sum()
        if tot <= 0:
            continue
        oy, ox = np.mgrid[-1:2, -1:2]
        cx, cy = x + (cut * ox).sum() / tot, y + (cut * oy).sum() / tot
        snr = float(d[y, x] / sig)
        out.append({"x": float(cx), "y": float(cy), "peak": float(d[y, x]), "snr": snr,
                    # precisión del centroide ≈ FWHM / (2,35·S/N), FWHM ≈ 1,2 px
                    "pos_err_px": float(max(1.2 / (2.35 * max(snr, 1)), 0.03))})
    out.sort(key=lambda s: -s["snr"])
    return out[:max_n]


def link_and_fit(sources_by_epoch: Dict[int, List[Dict[str, float]]], epoch_mjd: Dict[int, float],
                 link_radius_px: float = 3.0) -> List[Dict[str, Any]]:
    """Enlaza fuentes desde la época con más detecciones y ajusta movimiento lineal."""
    eps = sorted(e for e in sources_by_epoch if sources_by_epoch[e])
    if len(eps) < 2:
        return []
    ref = max(eps, key=lambda e: len(sources_by_epoch[e]))
    tracks = []
    used = {e: set() for e in eps}
    for s in sources_by_epoch[ref]:
        track = {ref: s}
        for e in eps:
            if e == ref:
                continue
            best, bd = None, link_radius_px
            for i, o in enumerate(sources_by_epoch[e]):
                if i in used[e]:
                    continue
                dd = np.hypot(o["x"] - s["x"], o["y"] - s["y"])
                if dd < bd:
                    best, bd = i, dd
            if best is not None:
                used[e].add(best)
                track[e] = sources_by_epoch[e][best]
        if len(track) >= 2:
            tracks.append(track)

    fits = []
    for tr in tracks:
        es = sorted(tr)
        t = np.array([(epoch_mjd[e] - epoch_mjd[es[0]]) / YEAR for e in es])
        x = np.array([tr[e]["x"] for e in es])
        y = np.array([tr[e]["y"] for e in es])
        w = 1.0 / np.array([tr[e]["pos_err_px"] for e in es]) ** 2
        if np.ptp(t) < 0.05:
            continue
        vx, vy, evx, evy = _wfit2(t, x, y, w)
        speed_px = float(np.hypot(vx, vy))
        speed_err = float(np.hypot(evx, evy))
        fits.append({"track": {int(e): tr[e] for e in es}, "vx_px_yr": vx, "vy_px_yr": vy,
                     "speed_px_yr": speed_px, "speed_err_px_yr": speed_err,
                     "span_yr": float(np.ptp(t)), "snr": float(np.median([tr[e]["snr"] for e in es])),
                     "n_epochs": len(es)})
    return fits


def _wfit2(t, x, y, w):
    def one(v):
        W = np.sum(w)
        tm = np.sum(w * t) / W
        vm = np.sum(w * v) / W
        stt = np.sum(w * (t - tm) ** 2)
        slope = np.sum(w * (t - tm) * (v - vm)) / stt
        resid = v - (vm + slope * (t - tm))
        # error: formal o por residuos (lo que sea mayor); suelo por error astrométrico ~0,05 px
        formal = np.sqrt(1.0 / stt)
        scatter = np.sqrt(np.sum(resid ** 2) / max(len(t) - 2, 1) / np.sum((t - tm) ** 2)) if len(t) > 2 else 0
        floor = 0.08 / max(np.ptp(t), 0.1)
        return float(slope), float(max(formal, scatter, floor))
    vx, evx = one(x)
    vy, evy = one(y)
    return vx, vy, evx, evy


def detect_candidates(coadds: Dict[int, Dict[str, np.ndarray]], epoch_mjd: Dict[int, float], grid: WCS,
                      gaia_sources: Optional[List[Dict[str, Any]]] = None, nsigma: float = 5.0,
                      min_sig: float = 5.0, min_motion_px: float = 0.5,
                      center_target: Optional[Dict[str, Any]] = None,
                      solar_system: bool = False) -> Dict[str, Any]:
    srcs = {e: find_sources(c["data"], c.get("err"), nsigma) for e, c in coadds.items()}
    fits_ = link_and_fit(srcs, epoch_mjd)
    cands = []
    px_as = config.PIXEL_SCALE_ARCSEC
    mean_mjd = float(np.mean(list(epoch_mjd.values()))) if epoch_mjd else 0
    year_mean = 2000.0 + (mean_mjd - 51544.5) / YEAR
    for f in fits_:
        sig = f["speed_px_yr"] / max(f["speed_err_px_yr"], 1e-6)
        moved = f["speed_px_yr"] * f["span_yr"]
        if sig < min_sig or moved < min_motion_px:
            continue
        e0 = min(f["track"])
        p0 = f["track"][e0]
        sky = grid.pixel_to_world(p0["x"], p0["y"])
        # convención astronómica: x crece al oeste (este a la izquierda)
        pmra = -f["vx_px_yr"] * px_as * 1000.0
        pmdec = f["vy_px_yr"] * px_as * 1000.0
        cand = {
            "ra_deg": round(float(sky.ra.deg), 6), "dec_deg": round(float(sky.dec.deg), 6),
            "pmra_mas_yr": round(pmra, 0), "pmdec_mas_yr": round(pmdec, 0),
            "motion_arcsec_yr": round(f["speed_px_yr"] * px_as, 2),
            "motion_err_arcsec_yr": round(f["speed_err_px_yr"] * px_as, 2),
            "significance_sigma": round(float(sig), 1),
            "snr": round(f["snr"], 1), "n_epochs": f["n_epochs"], "span_yr": round(f["span_yr"], 2),
            "positions": [{"epoch": e, "x": round(s["x"], 2), "y": round(s["y"], 2)} for e, s in sorted(f["track"].items())],
            "status": "Candidato para revisión humana",
        }
        cand["known_match"] = _gaia_match(cand, gaia_sources, year_mean) if gaia_sources is not None else None
        cand["gaia_checked"] = gaia_sources is not None
        cand["quality"] = _quality(cand)
        cands.append(cand)

    # Transitorios: fuentes brillantes que aparecen en una sola época (posibles asteroides, artefactos).
    transients = []
    if len(srcs) >= 2:
        for e, ss in srcs.items():
            for s in ss[:60]:
                if s["snr"] < 8:
                    continue
                elsewhere = any(np.hypot(o["x"] - s["x"], o["y"] - s["y"]) < 3.0 for oe, os_ in srcs.items() if oe != e for o in os_)
                covered = all(np.isfinite(coadds[oe]["data"][int(round(s["y"])), int(round(s["x"]))]) for oe in srcs if oe != e)
                if not elsewhere and covered:
                    sky = grid.pixel_to_world(s["x"], s["y"])
                    transients.append({"epoch": e, "ra_deg": round(float(sky.ra.deg), 6), "dec_deg": round(float(sky.dec.deg), 6),
                                       "snr": round(s["snr"], 1), "x": round(s["x"], 2), "y": round(s["y"], 2),
                                       "status": "Aparece en una sola época: posible asteroide, cometa o artefacto. Revisar."})
    # Dipolos en la diferencia última − primera época: un objeto que se mueve
    # deja un hueco (negativo) donde estaba y un pico (positivo) donde está.
    # Encuentra movimientos de objetos débiles o pegados a otra estrella.
    eps_sorted = sorted(epoch_mjd)
    if len(eps_sorted) >= 2:
        from .processing import difference
        first, last = eps_sorted[0], eps_sorted[-1]
        span = (epoch_mjd[last] - epoch_mjd[first]) / YEAR
        d = difference(coadds[last]["data"], coadds[first]["data"])
        # estrellas brillantes presentes en ambas fechas: sus residuos imitan dipolos
        bright = [s_ for s_ in srcs.get(first, []) if s_["snr"] > 40 and
                  any(np.hypot(o["x"] - s_["x"], o["y"] - s_["y"]) < 1.0 for o in srcs.get(last, []))]
        # halos de estrellas muy brillantes (saturadas): zona de exclusión según su brillo
        halos = [(s_["x"], s_["y"], min(4.0 + s_["snr"] / 100.0, 15.0))
                 for e_ in (first, last) for s_ in srcs.get(e_, []) if s_["snr"] > 300]
        for dp in find_dipoles(d):
            if any(min(np.hypot(hx - dp["pos"][0], hy - dp["pos"][1]),
                       np.hypot(hx - dp["neg"][0], hy - dp["neg"][1])) < hr for hx, hy, hr in halos):
                continue
            if any(min(np.hypot(b["x"] - dp["pos"][0], b["y"] - dp["pos"][1]),
                       np.hypot(b["x"] - dp["neg"][0], b["y"] - dp["neg"][1])) < 2.5 for b in bright):
                continue
            if any(np.hypot(c["positions"][-1]["x"] - dp["pos"][0], c["positions"][-1]["y"] - dp["pos"][1]) < 2.0 for c in cands):
                continue
            sky0 = grid.pixel_to_world(*dp["neg"])
            vx = (dp["pos"][0] - dp["neg"][0]) / max(span, 1e-3)
            vy = (dp["pos"][1] - dp["neg"][1]) / max(span, 1e-3)
            speed = float(np.hypot(vx, vy))
            cand = {
                "ra_deg": round(float(sky0.ra.deg), 6), "dec_deg": round(float(sky0.dec.deg), 6),
                "pmra_mas_yr": round(-vx * px_as * 1000.0, 0), "pmdec_mas_yr": round(vy * px_as * 1000.0, 0),
                "motion_arcsec_yr": round(speed * px_as, 2),
                # Con desplazamientos menores que la estrella (~1,5 px) los lóbulos del dipolo
                # quedan separados ~2σ del PSF: la velocidad sale exagerada. Se reporta como cota.
                "motion_err_arcsec_yr": round(max(0.5 * speed * px_as, 0.5 * px_as / max(span, 1e-3)), 2),
                "motion_note": ("Aproximada: si el objeto se movió menos que el tamaño de una estrella (~9″), "
                                "el dipolo exagera la distancia. La dirección es fiable."
                                if np.hypot(dp["pos"][0] - dp["neg"][0], dp["pos"][1] - dp["neg"][1]) < 3.0 else None),
                "significance_sigma": round(min(dp["pos_sig"], dp["neg_sig"]), 1),
                "snr": round(dp["pos_sig"], 1), "n_epochs": 2, "span_yr": round(span, 2),
                "positions": [{"epoch": first, "x": round(dp["neg"][0], 2), "y": round(dp["neg"][1], 2)},
                              {"epoch": last, "x": round(dp["pos"][0], 2), "y": round(dp["pos"][1], 2)}],
                "method": "dipolo en la imagen de diferencia",
                "status": "Candidato para revisión humana (dipolo en la diferencia: comprobar en modo Diferencia)",
            }
            cand["known_match"] = _gaia_match(cand, gaia_sources, year_mean) if gaia_sources is not None else None
            cand["gaia_checked"] = gaia_sources is not None
            q = _quality(cand)
            # dipolo: solo dos fechas; la confianza depende sobre todo de su significancia
            score = min(0.3 + 0.06 * min(dp["pos_sig"], dp["neg_sig"]), 0.8)
            if cand["known_match"] and "falso" in q["label"]:
                score *= 0.4
            q["score"] = round(score, 2)
            q["level"] = "alta" if score > 0.7 else "media" if score > 0.45 else "baja"
            cand["quality"] = q
            cands.append(cand)

    transients = transients[:20]
    ss_info = _solar_system_check(cands, transients, coadds, epoch_mjd, grid) if solar_system else None
    cands.sort(key=lambda c: (-c["quality"]["score"]))
    return {"candidates": cands, "transients": transients, "solar_system": ss_info,
            "n_sources": {int(e): len(v) for e, v in srcs.items()},
            "method": "Picos > {}σ por época, enlace ≤3 px, ajuste lineal; candidato si movimiento ≥{} px y ≥{}σ."
                      .format(nsigma, min_motion_px, min_sig)}


def _solar_system_check(cands, transients, coadds, epoch_mjd, grid) -> Dict[str, Any]:
    """Cotejo con asteroides/cometas conocidos (JPL). Nunca dice "no hay" si JPL no respondió."""
    n = next(iter(coadds.values()))["data"].shape[0]
    cen = grid.pixel_to_world((n - 1) / 2.0, (n - 1) / 2.0)
    radius = n * config.PIXEL_SCALE_ARCSEC / 3600.0 / 2.0 * 1.45 + 0.01
    tol = 2.0 * config.PIXEL_SCALE_ARCSEC
    items = []
    for c in cands:
        by_ep = {}
        for p in c["positions"]:
            w = grid.pixel_to_world(p["x"], p["y"])
            by_ep[p["epoch"]] = (float(w.ra.deg), float(w.dec.deg))
        items.append({"ref": c, "ra_deg": c["ra_deg"], "dec_deg": c["dec_deg"],
                      "epochs": list(by_ep), "positions_by_epoch": by_ep})
    for t in transients:
        items.append({"ref": t, "ra_deg": t["ra_deg"], "dec_deg": t["dec_deg"],
                      "epochs": [t["epoch"]], "positions_by_epoch": {t["epoch"]: (t["ra_deg"], t["dec_deg"])}})
    info = crossmatch_solar_system(items, epoch_mjd, float(cen.ra.deg), float(cen.dec.deg), radius, tol)
    for it in items:
        o = it["ref"]
        o["ss_match"], o["ss_checked"] = it["ss_match"], it["ss_checked"]
        m = it["ss_match"]
        if "quality" in o:
            q = o["quality"]
            if m:
                q["label"] = f"Coincide con cuerpo conocido del Sistema Solar: {m['name']}"
                q["score"] = round(q["score"] * 0.4, 2)
                q["level"] = "alta" if q["score"] > 0.7 else "media" if q["score"] > 0.45 else "baja"
            elif not it["ss_checked"]:
                q["label"] += " · Sistema Solar: sin cotejar (JPL no respondió)"
        else:
            if m:
                o["status"] = f"Coincide con cuerpo conocido del Sistema Solar: {m['name']} (cotejo automático y aproximado)."
            elif not it["ss_checked"]:
                o["status"] += " Sin cotejar con JPL (no respondió)."
            else:
                o["status"] += " Sin coincidencia en JPL: revisar."
    return info


def find_dipoles(diff: np.ndarray, nsigma: float = 3.5, min_sep: float = 0.7, max_sep: float = 4.0,
                 max_n: int = 10) -> List[Dict[str, Any]]:
    """
    Pares (negativo, positivo) cercanos y de amplitud parecida en una imagen de
    diferencia. Se descartan los pares alrededor de estrellas muy brillantes
    que no restaron bien (residuos simétricos en forma de anillo).
    """
    d = np.nan_to_num(diff, nan=0.0)
    sig = robust_sigma(d)
    sm = ndimage.gaussian_filter(d, 0.7)
    s_sig = robust_sigma(sm) or sig
    pos = (sm == ndimage.maximum_filter(sm, 3)) & (sm > nsigma * s_sig)
    neg = (sm == ndimage.minimum_filter(sm, 3)) & (sm < -nsigma * s_sig)
    def refine(x, y, sign):
        # centroide subpíxel 3×3 sobre la parte del signo correspondiente
        if not (1 <= x < sm.shape[1] - 1 and 1 <= y < sm.shape[0] - 1):
            return float(x), float(y)
        cut = np.clip(sign * sm[y - 1:y + 2, x - 1:x + 2], 0, None)
        tot = cut.sum()
        if tot <= 0:
            return float(x), float(y)
        oy, ox = np.mgrid[-1:2, -1:2]
        return float(x + (cut * ox).sum() / tot), float(y + (cut * oy).sum() / tot)

    P_ = [(*refine(x, y, 1), float(sm[y, x] / s_sig)) for y, x in zip(*np.nonzero(pos))]
    N_ = [(*refine(x, y, -1), float(-sm[y, x] / s_sig)) for y, x in zip(*np.nonzero(neg))]
    out, used = [], set()
    n = d.shape[0]
    for px_, py_, ps in sorted(P_, key=lambda p: -p[2]):
        best = None
        for j, (nx_, ny_, ns) in enumerate(N_):
            if j in used:
                continue
            sep = np.hypot(px_ - nx_, py_ - ny_)
            if min_sep <= sep <= max_sep and 0.33 < ps / ns < 3.0 and (best is None or sep < best[1]):
                best = (j, sep)
        if best is None or not (2 <= px_ < n - 2 and 2 <= py_ < n - 2):
            continue
        j = best[0]
        # un anillo de residuos tiene varios negativos alrededor del positivo: se descarta
        ring = sum(1 for (nx_, ny_, _) in N_ if np.hypot(px_ - nx_, py_ - ny_) <= max_sep)
        if ring > 2:
            continue
        used.add(j)
        out.append({"pos": (px_, py_), "neg": (N_[j][0], N_[j][1]), "pos_sig": ps, "neg_sig": N_[j][2]})
        if len(out) >= max_n:
            break
    return out


def _gaia_match(c, gaia, year):
    best = None
    for g in gaia:
        gra, gdec = gaia_position_at(g, year)
        d = np.hypot((gra - c["ra_deg"]) * np.cos(np.radians(c["dec_deg"])), gdec - c["dec_deg"]) * 3600
        if d < 2.0 * config.PIXEL_SCALE_ARCSEC and (best is None or d < best["sep_arcsec"]):
            gp = np.hypot(g.get("pmra") or 0, g.get("pmdec") or 0) / 1000.0
            best = {"catalog": "Gaia DR3", "id": g["id"], "sep_arcsec": round(float(d), 1),
                    "gaia_motion_arcsec_yr": round(float(gp), 3), "mag_g": g.get("mag")}
    return best


def _quality(c):
    s = 0.0
    s += min(c["significance_sigma"] / 20.0, 1.0) * 0.4
    s += min(c["snr"] / 30.0, 1.0) * 0.3
    s += min((c["n_epochs"] - 1) / 3.0, 1.0) * 0.3
    km = c.get("known_match")
    if km and km["gaia_motion_arcsec_yr"] > 0.3:
        label = "Conocido (Gaia DR3 confirma movimiento)"
    elif km:
        label = "Coincide con estrella de Gaia casi fija: probable falso movimiento"
        s *= 0.4
    elif not c.get("gaia_checked", True):
        label = "Sin cotejar: Gaia DR3 no respondió (revisar a mano o reintentar)"
    else:
        label = "No catalogado en Gaia: interesante, revisar a mano"
    level = "alta" if s > 0.7 else "media" if s > 0.45 else "baja"
    return {"score": round(s, 2), "level": level, "label": label}


# ---------------------------------------------------------------------------
# Prueba de honestidad: inyectar objetos simulados y ver cuántos se recuperan
# ---------------------------------------------------------------------------

def injection_test(coadds: Dict[int, Dict[str, np.ndarray]], epoch_mjd: Dict[int, float], grid: WCS,
                   n_per_cell: int = 6, seed: int = 1) -> Dict[str, Any]:
    """
    Añade fuentes SIMULADAS (PSF gaussiana, FWHM 7,5″) que se mueven en línea
    recta sobre las imágenes reales, con distintos brillos y velocidades, y
    mide qué fracción recupera el detector. Los objetos simulados nunca se
    muestran como datos.
    """
    rng = np.random.default_rng(seed)
    eps = sorted(coadds)
    if len(eps) < 2:
        return {"error": "Hace falta más de una época."}
    n = coadds[eps[0]]["data"].shape[0]
    sigma_noise = np.median([robust_sigma(coadds[e]["data"]) for e in eps])
    snrs = [5, 10, 20, 50]
    speeds_as = [1.0, 3.0, 8.0, 15.0]
    t0 = epoch_mjd[eps[0]]
    yy, xx = np.mgrid[0:n, 0:n]
    psf_sig = (7.5 / config.PIXEL_SCALE_ARCSEC) / 2.355
    peak_per_flux = 1.0
    results = []
    for snr in snrs:
        for sp in speeds_as:
            found = 0
            for _ in range(n_per_cell):
                ang = rng.uniform(0, 2 * np.pi)
                v = sp / config.PIXEL_SCALE_ARCSEC
                x0, y0 = rng.uniform(6, n - 6), rng.uniform(6, n - 6)
                fake = {}
                for e in eps:
                    dt = (epoch_mjd[e] - t0) / YEAR
                    x, y = x0 + v * np.cos(ang) * dt, y0 + v * np.sin(ang) * dt
                    blob = np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * psf_sig ** 2)) * snr * sigma_noise * peak_per_flux
                    fake[e] = {"data": coadds[e]["data"] + blob, "err": coadds[e]["err"]}
                res = detect_candidates(fake, epoch_mjd, grid, gaia_sources=None)
                xe, ye = x0, y0
                if any(np.hypot(c["positions"][0]["x"] - xe, c["positions"][0]["y"] - ye) < 2.5 for c in res["candidates"]):
                    found += 1
            results.append({"peak_snr": snr, "speed_arcsec_yr": sp, "recovered": found, "injected": n_per_cell,
                            "fraction": round(found / n_per_cell, 2)})
    span = (epoch_mjd[eps[-1]] - t0) / YEAR
    return {"grid": results, "span_yr": round(span, 2), "n_epochs": len(eps),
            "note": "Objetos SIMULADOS añadidos a imágenes reales solo para medir sensibilidad. "
                    "No se muestran como datos."}
