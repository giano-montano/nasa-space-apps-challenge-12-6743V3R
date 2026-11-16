"""
Cliente de IRSA para SPHEREx (datos reales).

1. Descubrimiento: qué imágenes espectrales de Nivel 2 cubren un punto del cielo.
   - Primero TAP (misma consulta que el notebook oficial "spherex-cutouts":
     spherex.artifact JOIN spherex.plane, filtro CONTAINS(POINT, p.poly)).
   - Si TAP falla, SIA2 con las colecciones de config.SPHEREX_COLLECTIONS.
   Nada de fechas ni archivos fijos: cada release nuevo aparece solo.
2. Lectura: recorte ("stamp") de IMAGE, FLAGS, VARIANCE y ZODI alrededor de
   una posición, más la longitud de onda en ese píxel (WCS alternativo "W").
   - Primero lectura parcial por rangos HTTP del bucket público de AWS
     (solo baja los KB necesarios, no la tabla EPSF de ~4 MB).
   - Si falla, servicio de cutouts de IRSA (center/size).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time
import warnings
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from astropy.io import fits
from astropy.io.votable import parse_single_table
from astropy.coordinates import SkyCoord
from astropy.time import Time
from astropy.wcs import WCS, FITSFixedWarning

from . import config

warnings.simplefilter("ignore", FITSFixedWarning)
warnings.filterwarnings("ignore", message=".*SIP distortion.*")

_session = requests.Session()
_session.headers["User-Agent"] = "spherex-sky-viewer/3.0 (NASA Space Apps 2026)"


class IrsaUnavailable(RuntimeError):
    """IRSA no respondió (caído, lento o sin red)."""


# ---------------------------------------------------------------------------
# Descubrimiento
# ---------------------------------------------------------------------------

_FNAME = re.compile(r"level2_(?P<obsid>.+?)D(?P<det>[1-6])_spx_(?P<ver>[^/]+)\.fits$")


@dataclass
class ImageRecord:
    path: str            # ruta relativa: ibe/data/spherex/<release>/level2/...
    release: str         # dr1, qr3, ...
    obsid: str
    detector: int
    mjd: float
    date: str
    bandpass: str = ""

    @property
    def ibe_url(self) -> str:
        return config.IRSA_BASE_URL + self.path

    @property
    def s3_url(self) -> str:
        return config.SPHEREX_S3_HTTP + self.path.split("ibe/data/spherex/", 1)[-1]


def _record_from_path(path: str, mjd: float, bandpass: str = "") -> Optional[ImageRecord]:
    path = path.split("?", 1)[0]
    if path.startswith("http"):
        path = path.split("irsa.ipac.caltech.edu/", 1)[-1]
    if "/level2/" not in path:
        return None
    m = _FNAME.search(path)
    if not m:
        return None
    rel = path.split("ibe/data/spherex/", 1)[-1].split("/", 1)[0]
    return ImageRecord(path=path, release=rel, obsid=m.group("obsid"), detector=int(m.group("det")),
                       mjd=float(mjd), date=Time(mjd, format="mjd").iso[:19], bandpass=bandpass)


def _cache_path(kind: str, key: str, ext: str = "json") -> str:
    h = hashlib.sha1(key.encode()).hexdigest()[:20]
    d = os.path.join(config.CACHE_DIR, kind)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{h}.{ext}")


def _fresh(path: str) -> bool:
    return os.path.exists(path) and (time.time() - os.path.getmtime(path) < config.CACHE_TTL_SECONDS)


def _query_tap(ra: float, dec: float) -> List[ImageRecord]:
    adql = (
        "SELECT a.uri, p.time_bounds_lower, p.energy_bandpassname "
        "FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid "
        f"WHERE 1 = CONTAINS(POINT('ICRS', {ra:.6f}, {dec:.6f}), p.poly) "
        "ORDER BY p.time_bounds_lower"
    )
    r = _session.post(config.IRSA_TAP_URL, data={"QUERY": adql, "FORMAT": "votable", "LANG": "ADQL"},
                      timeout=config.HTTP_TIMEOUT * 2)
    if r.status_code != 200:
        raise IrsaUnavailable(f"TAP respondió HTTP {r.status_code}")
    table = parse_single_table(io.BytesIO(r.content)).to_table(use_names_over_ids=True)
    out = []
    for row in table:
        rec = _record_from_path(str(row["uri"]), float(row["time_bounds_lower"]), str(row["energy_bandpassname"]))
        if rec:
            out.append(rec)
    return out


def _sia_one(coll: str, ra: float, dec: float) -> List[ImageRecord]:
    """
    Una colección SIA2. Columnas verificadas (ObsCore de IRSA, nov-2026):
    access_url, t_min (MJD), energy_bandpassname ("SPHEREx-D3"),
    dataproduct_subtype ("science"), obs_id, cloud_access (JSON con la clave S3).
    """
    r = None
    for attempt in range(config.IRSA_RETRIES):
        try:
            r = _session.get(config.IRSA_SIA_URL, params={
                "COLLECTION": coll, "POS": f"circle {ra:.6f} {dec:.6f} 0.0005", "RESPONSEFORMAT": "VOTABLE",
            }, timeout=config.HTTP_TIMEOUT * 3)
            if r.status_code == 200:
                break
        except requests.RequestException:
            r = None
        time.sleep(2 + 4 * attempt)
    if r is None or r.status_code != 200:
        raise IrsaUnavailable(f"{coll}: HTTP {getattr(r, 'status_code', 'sin respuesta')}")
    t = parse_single_table(io.BytesIO(r.content)).to_table(use_names_over_ids=True)
    cols = set(t.colnames)
    out = []
    for row in t:
        if "dataproduct_subtype" in cols and str(row["dataproduct_subtype"]).strip().lower() != "science":
            continue
        try:
            mjd = float(row["t_min"])
        except (TypeError, ValueError, KeyError):
            continue
        bp = str(row["energy_bandpassname"]) if "energy_bandpassname" in cols else ""
        rec = _record_from_path(str(row["access_url"]), mjd, bp)
        if rec and np.isfinite(rec.mjd):
            out.append(rec)
    return out


def _query_sia(ra: float, dec: float):
    from concurrent.futures import ThreadPoolExecutor
    out: List[ImageRecord] = []
    errors = []
    with ThreadPoolExecutor(max_workers=len(config.SPHEREX_COLLECTIONS) or 1) as ex:
        futs = {c: ex.submit(_sia_one, c, ra, dec) for c in config.SPHEREX_COLLECTIONS}
        for c, f in futs.items():
            try:
                out.extend(f.result())
            except (IrsaUnavailable, requests.RequestException, ValueError) as e:
                errors.append(f"{c}: {e.__class__.__name__}: {e}")
    if errors:
        # Resultado incompleto: mejor fallar (y probar TAP o la caché) que decir "no hay datos".
        if not out:
            raise IrsaUnavailable("SIA2: " + "; ".join(errors))
    warning = ("Algunas colecciones de IRSA no respondieron: " + "; ".join(errors)) if errors else None
    return out, warning


def _dedupe(records: List[ImageRecord]) -> List[ImageRecord]:
    """Una misma exposición puede estar en varios releases: nos quedamos con el preferido."""
    pref = {c.replace("spherex_", "").replace("_deep", ""): i for i, c in enumerate(config.SPHEREX_COLLECTIONS)}
    best: Dict[tuple, ImageRecord] = {}
    for r in records:
        key = (r.obsid, r.detector)
        if key not in best or pref.get(r.release, 99) < pref.get(best[key].release, 99):
            best[key] = r
    return sorted(best.values(), key=lambda r: (r.mjd, r.detector))


def find_images(ra: float, dec: float, refresh: bool = False) -> Dict[str, Any]:
    """
    Lista todas las imágenes L2 de SPHEREx que contienen (ra, dec).
    Devuelve {"images": [...], "service": "TAP"|"SIA2"|"caché", "queried_at": ...}.
    """
    key = f"find:{ra:.4f}:{dec:.4f}:{','.join(config.SPHEREX_COLLECTIONS)}"
    cp = _cache_path("queries", key)
    if not refresh and _fresh(cp):
        with open(cp, encoding="utf-8") as f:
            data = json.load(f)
        data["service"] = data.get("service", "") + " (caché)"
        return data

    errors = []
    records, service, partial = None, None, None
    for name, fn in (("SIA2", _query_sia), ("TAP", _query_tap)):
        try:
            res = fn(ra, dec)
            records, partial = res if isinstance(res, tuple) else (res, None)
            service = name
            break
        except (IrsaUnavailable, requests.RequestException, ValueError) as e:
            errors.append(f"{name}: {e}")
    if records is None:
        # Si hay una respuesta vieja en disco, mejor eso que nada (se avisa).
        if os.path.exists(cp):
            with open(cp, encoding="utf-8") as f:
                data = json.load(f)
            data["service"] = "caché vencida (IRSA no responde)"
            data["warning"] = "IRSA no responde ahora; se muestran resultados guardados anteriormente."
            return data
        raise IrsaUnavailable("IRSA no responde ahora mismo (" + " | ".join(errors) + ")")

    data = {
        "images": [asdict(r) for r in _dedupe(records)],
        "service": service,
        "queried_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if partial:
        data["warning"] = partial  # no se guarda en caché: la próxima vez se reintenta todo
        return data
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def records_from_dicts(items: List[Dict[str, Any]]) -> List[ImageRecord]:
    return [ImageRecord(**it) for it in items]


# ---------------------------------------------------------------------------
# Lectura de recortes
# ---------------------------------------------------------------------------

def _flag_bits(header) -> Dict[str, int]:
    bits = {}
    for k in header:
        if k.startswith("MSKN"):
            try:
                bits[str(header[k]).strip()] = int(k[4:])
            except ValueError:
                pass
    return bits


def _stamp_from_hdul(h, ra: float, dec: float, half: int, sliced: bool) -> Dict[str, Any]:
    hdr = h["IMAGE"].header
    wcs = WCS(hdr)
    x, y = wcs.world_to_pixel(SkyCoord(ra, dec, unit="deg"))
    x, y = float(x), float(y)
    ny, nx = hdr["NAXIS2"], hdr["NAXIS1"]
    xc, yc = int(round(x)), int(round(y))
    if sliced:
        x0, x1 = max(0, xc - half), min(nx, xc + half + 1)
        y0, y1 = max(0, yc - half), min(ny, yc + half + 1)
    else:
        x0, x1, y0, y1 = 0, nx, 0, ny
    if x1 - x0 < 3 or y1 - y0 < 3:
        raise ValueError("La posición cae fuera de la imagen.")

    def sect(name, dtype):
        return np.asarray(h[name].section[y0:y1, x0:x1], dtype=dtype)

    img = sect("IMAGE", np.float32)
    flags = sect("FLAGS", np.int64)
    var = sect("VARIANCE", np.float32)
    zodi = sect("ZODI", np.float32)

    # Longitud de onda central en la posición pedida (WCS alternativo "W", sin SIP).
    wl = bw = float("nan")
    try:
        sw = WCS(hdr, fobj=h, key="W")
        sw.sip = None
        w_q, b_q = sw.pixel_to_world(x, y)
        wl, bw = float(w_q.to_value("um")), float(b_q.to_value("um"))
    except Exception:
        pass

    # WCS del recorte (desplazado al origen del recorte).
    sub = wcs.slice((slice(y0, y1), slice(x0, x1)))
    bits = _flag_bits(h["FLAGS"].header)
    return {
        "image": img, "flags": flags, "variance": var, "zodi": zodi,
        "wcs_header": sub.to_header(relax=True).tostring(),
        "x": x - x0, "y": y - y0,
        "wavelength_um": wl, "bandwidth_um": bw,
        "flag_bits": bits,
        "meta": {
            "date_obs": hdr.get("DATE-OBS"), "mjd": hdr.get("MJD-AVG", hdr.get("MJD-OBS")),
            "detector": hdr.get("DETECTOR"), "obsid": hdr.get("OBSID"),
            "exptime_s": hdr.get("TELAPSE"), "psf_fwhm_arcsec": hdr.get("PSF_FWHM"),
            "qa": hdr.get("L2DQAFLG"), "survey": hdr.get("SPS_FLAGS"),
        },
    }


def _pack(stamp: Dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    meta = {k: v for k, v in stamp.items() if k not in ("image", "flags", "variance", "zodi")}
    np.savez_compressed(buf, image=stamp["image"], flags=stamp["flags"], variance=stamp["variance"],
                        zodi=stamp["zodi"], meta=np.array(json.dumps(meta, default=str)))
    return buf.getvalue()


def _unpack(raw: bytes) -> Dict[str, Any]:
    z = np.load(io.BytesIO(raw), allow_pickle=False)
    st = json.loads(str(z["meta"]))
    for k in ("image", "flags", "variance", "zodi"):
        st[k] = z[k]
    return st


def read_stamp(rec: ImageRecord, ra: float, dec: float, size_arcmin: float) -> Dict[str, Any]:
    """Recorte de size_arcmin centrado en (ra, dec) de una imagen L2. Usa caché en disco."""
    half = int(np.ceil(size_arcmin * 60.0 / config.PIXEL_SCALE_ARCSEC / 2.0)) + 2
    key = f"stamp:{rec.path}:{ra:.5f}:{dec:.5f}:{half}"
    cp = _cache_path("stamps", key, "npz")
    if os.path.exists(cp):  # las imágenes ya publicadas no cambian: sin TTL
        try:
            with open(cp, "rb") as f:
                st = _unpack(f.read())
            st["record"] = asdict(rec)
            return st
        except Exception:
            pass

    stamp, errors = None, []
    # 1) Lectura parcial desde AWS S3 (rangos HTTP).
    try:
        with fits.open(rec.s3_url, use_fsspec=True, lazy_load_hdus=True,
                       fsspec_kwargs={"block_size": 512 * 1024}) as h:
            stamp = _stamp_from_hdul(h, ra, dec, half, sliced=True)
    except Exception as e:
        errors.append(f"S3: {e.__class__.__name__}: {e}")
    # 2) Servicio de cutouts de IRSA.
    if stamp is None:
        try:
            r = _session.get(rec.ibe_url, params={"center": f"{ra:.6f},{dec:.6f}deg",
                                                   "size": f"{2 * half + 1}px", "gzip": "false"},
                             timeout=config.HTTP_TIMEOUT)
            r.raise_for_status()
            with fits.open(io.BytesIO(r.content)) as h:
                stamp = _stamp_from_hdul(h, ra, dec, half, sliced=False)
        except Exception as e:
            errors.append(f"cutout: {e.__class__.__name__}: {e}")
    if stamp is None:
        raise IrsaUnavailable(f"No pude leer {rec.path.rsplit('/', 1)[-1]}: " + " | ".join(errors))

    with open(cp, "wb") as f:
        f.write(_pack(stamp))
    stamp = _unpack(_pack(stamp))
    stamp["record"] = asdict(rec)
    return stamp


def clear_cache(include_stamps: bool = False) -> int:
    """Borra consultas guardadas (y opcionalmente recortes) para ver releases nuevos."""
    n = 0
    kinds = ["queries", "results"] + (["stamps"] if include_stamps else [])
    for kind in kinds:
        d = os.path.join(config.CACHE_DIR, kind)
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            try:
                os.remove(os.path.join(d, fn))
                n += 1
            except OSError:
                pass
    return n
