"""
Utilidades de coordenadas: lectura de RA/Dec en grados o sexagesimal,
formato de salida y propagación de movimiento propio a una fecha.
"""

import re
from typing import Optional, Tuple

import astropy.units as u
from astropy.coordinates import SkyCoord, Distance
from astropy.time import Time


def parse_coordinates(ra_str: str, dec_str: str) -> Tuple[float, float]:
    """
    Convierte RA y Dec a grados. Acepta:
      - grados decimales: "133.79", "-7.245"
      - sexagesimal: "08h55m10.8s" / "08:55:10.8" / "08 55 10.8" y "-07d14m42s" / "-07:14:42" / "−07°14′42″"
    RA en sexagesimal se interpreta en horas; en decimal, en grados.
    Lanza ValueError si no se puede interpretar o está fuera de rango.
    """
    ra_clean = str(ra_str).strip().replace("−", "-")
    dec_clean = str(dec_str).strip().replace("−", "-")
    if not ra_clean or not dec_clean:
        raise ValueError("Faltan RA o Dec.")

    try:
        ra_val, dec_val = float(ra_clean), float(dec_clean)
    except ValueError:
        ra_val = _parse_hms_to_deg(ra_clean)
        dec_val = _parse_dms_to_deg(dec_clean)
        if ra_val is None or dec_val is None:
            raise ValueError(
                f"No pude leer las coordenadas RA='{ra_str}', Dec='{dec_str}'. "
                "Usa grados (133.795, -7.245) o sexagesimal (08h55m10s, -07d14m42s)."
            )

    if not -90.0 <= dec_val <= 90.0:
        raise ValueError("La declinación debe estar entre -90° y +90°.")
    if not 0.0 <= ra_val < 360.0:
        if -360.0 < ra_val < 720.0:
            ra_val %= 360.0
        else:
            raise ValueError("La ascensión recta debe estar entre 0° y 360° (o 0h y 24h).")
    return ra_val, dec_val


_NUM = r"(\d+(?:\.\d*)?)"


def _parse_hms_to_deg(text: str) -> Optional[float]:
    m = re.fullmatch(rf"\s*{_NUM}\s*[hH:\s]\s*{_NUM}\s*(?:[mM:\s]\s*{_NUM}\s*[sS]?)?\s*", text)
    if not m:
        return None
    h, mi, s = float(m.group(1)), float(m.group(2)), float(m.group(3) or 0.0)
    if h >= 24 or mi >= 60 or s >= 60:
        return None
    return (h + mi / 60.0 + s / 3600.0) * 15.0


def _parse_dms_to_deg(text: str) -> Optional[float]:
    t = text.strip()
    sign = -1.0 if t.startswith("-") else 1.0
    t = t.lstrip("+-").strip()
    m = re.fullmatch(rf"{_NUM}\s*[dD°:\s]\s*{_NUM}\s*(?:[mM′':\s]\s*{_NUM}\s*[sS″\"]?)?\s*", t)
    if not m:
        return None
    d, mi, s = float(m.group(1)), float(m.group(2)), float(m.group(3) or 0.0)
    if mi >= 60 or s >= 60:
        return None
    return sign * (d + mi / 60.0 + s / 3600.0)


def deg_to_sexagesimal(ra_deg: float, dec_deg: float) -> Tuple[str, str]:
    c = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
    ra_hms = c.ra.to_string(unit=u.hour, sep=("h", "m", "s"), precision=2, pad=True)
    dec_dms = c.dec.to_string(unit=u.deg, sep=("°", "′", "″"), alwayssign=True, precision=1, pad=True)
    return ra_hms, dec_dms


def position_at(ra: float, dec: float, pmra: float, pmdec: float, parallax: Optional[float],
                mjd: float, ref_epoch: str = "J2000") -> Tuple[float, float]:
    """
    Posición (ICRS, grados) de un objeto con movimiento propio en la fecha MJD.
    pmra incluye el factor cos(dec) (convención de Gaia/SIMBAD), en mas/año.
    No incluye paralaje anual (≤0,55″ para Barnard, < 0,1 píxel de SPHEREx).
    """
    if not pmra and not pmdec:
        return ra, dec
    dist = Distance(parallax=parallax * u.mas) if parallax and parallax > 0 else 100 * u.pc
    c = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, pm_ra_cosdec=pmra * u.mas / u.yr,
                 pm_dec=pmdec * u.mas / u.yr, distance=dist, obstime=Time(ref_epoch), frame="icrs")
    moved = c.apply_space_motion(new_obstime=Time(mjd, format="mjd"))
    return float(moved.ra.deg), float(moved.dec.deg)
