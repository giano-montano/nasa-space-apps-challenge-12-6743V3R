"""
Astronomical Coordinate Utilities for SPHEREx Sky Viewer.
Handles parsing of sexagesimal, decimal, and common astronomical formats.
"""

import re
from typing import Tuple, Optional
from astropy.coordinates import SkyCoord
import astropy.units as u


def parse_coordinates(ra_str: str, dec_str: str) -> Tuple[float, float]:
    """
    Parses RA and Dec strings in either decimal degrees or sexagesimal formats.
    Returns:
        (ra_deg, dec_deg) as floats.
    """
    ra_clean = str(ra_str).strip()
    dec_clean = str(dec_str).strip()

    # Try pure float first
    try:
        ra_val = float(ra_clean)
        dec_val = float(dec_clean)
        return ra_val % 360.0, max(-90.0, min(90.0, dec_val))
    except ValueError:
        pass

    # Try astropy SkyCoord with standard units
    try:
        # Check if RA has hours ('h', 'm', 's' or ':')
        if any(c in ra_clean for c in ['h', 'm', 's', ':']):
            coord = SkyCoord(f"{ra_clean} {dec_clean}", unit=(u.hourangle, u.deg), frame='icrs')
        else:
            coord = SkyCoord(f"{ra_clean} {dec_clean}", unit=(u.deg, u.deg), frame='icrs')
        return float(coord.ra.deg), float(coord.dec.deg)
    except Exception:
        pass

    # Custom regex fallback for sexagesimal strings like "08h55m10.83s", "-07d14m42.5s"
    ra_deg = _parse_hms_to_deg(ra_clean)
    dec_deg = _parse_dms_to_deg(dec_clean)

    if ra_deg is not None and dec_deg is not None:
        return ra_deg % 360.0, max(-90.0, min(90.0, dec_deg))

    raise ValueError(f"Could not parse celestial coordinates: RA='{ra_str}', Dec='{dec_str}'")


def _parse_hms_to_deg(hms: str) -> Optional[float]:
    # e.g., "08h55m10.83s", "08:55:10.83", "08 55 10.83"
    match = re.search(r'([0-9]+)[\s:hH]+([0-9]+)[\s:mM]+([0-9.]+)', hms)
    if match:
        h, m, s = float(match.group(1)), float(match.group(2)), float(match.group(3))
        return (h + m / 60.0 + s / 3600.0) * 15.0

    match_hm = re.search(r'([0-9]+)[\s:hH]+([0-9.]+)', hms)
    if match_hm:
        h, m = float(match_hm.group(1)), float(match_hm.group(2))
        return (h + m / 60.0) * 15.0

    return None


def _parse_dms_to_deg(dms: str) -> Optional[float]:
    # e.g., "-07°14′42.5″", "-07d14m42.5s", "-07:14:42.5"
    sign = -1.0 if ('-' in dms or '−' in dms) else 1.0
    clean = re.sub(r'[+\-−]', '', dms)

    match = re.search(r'([0-9]+)[\s:dD°]+([0-9]+)[\s:mM′\']+([0-9.]+)', clean)
    if match:
        d, m, s = float(match.group(1)), float(match.group(2)), float(match.group(3))
        return sign * (d + m / 60.0 + s / 3600.0)

    match_dm = re.search(r'([0-9]+)[\s:dD°]+([0-9.]+)', clean)
    if match_dm:
        d, m = float(match_dm.group(1)), float(match_dm.group(2))
        return sign * (d + m / 60.0)

    return None


def deg_to_sexagesimal(ra_deg: float, dec_deg: float) -> Tuple[str, str]:
    """Converts decimal degrees to formatted sexagesimal strings."""
    c = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame='icrs')
    ra_hms = c.ra.to_string(unit=u.hour, sep=('h', 'm', 's'), precision=2)
    dec_dms = c.dec.to_string(unit=u.deg, sep=('°', '′', '″'), alwayssign=True, precision=2)
    return ra_hms, dec_dms

