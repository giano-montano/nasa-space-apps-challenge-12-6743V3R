"""Pruebas mínimas sin red: coordenadas, propagación, épocas, emparejamiento de banda, detección."""

import numpy as np
import pytest

from backend.app.coords import parse_coordinates, position_at, deg_to_sexagesimal
from backend.app.irsa_client import ImageRecord, _record_from_path, _dedupe
from backend.app import processing as P
from backend.app import detection as D
from backend.app.targets import find_nearby_target, TARGETS


# --- coordenadas --------------------------------------------------------------

@pytest.mark.parametrize("ra,dec,exp_ra,exp_dec", [
    ("133.7951", "-7.2451", 133.7951, -7.2451),
    ("08h55m10.831s", "-07d14m42.53s", 133.795129, -7.245147),
    ("08:55:10.831", "-07:14:42.53", 133.795129, -7.245147),
    ("08 55 10.831", "−07°14′42.53″", 133.795129, -7.245147),
    ("17h57m48.5s", "+04d41m36s", 269.452083, 4.693333),
    ("0h0m0s", "-0d30m0s", 0.0, -0.5),
])
def test_parse_coordinates(ra, dec, exp_ra, exp_dec):
    r, d = parse_coordinates(ra, dec)
    assert r == pytest.approx(exp_ra, abs=2e-6)
    assert d == pytest.approx(exp_dec, abs=2e-6)


@pytest.mark.parametrize("ra,dec", [("abc", "10"), ("10", "95"), ("25h00m00s", "0"), ("", "1")])
def test_parse_coordinates_invalid(ra, dec):
    with pytest.raises(ValueError):
        parse_coordinates(ra, dec)


def test_sexagesimal_roundtrip():
    ra_s, dec_s = deg_to_sexagesimal(133.795129, -7.245147)
    assert ra_s.startswith("08h55m10.8")
    assert dec_s.startswith("-07°14′42")


def test_proper_motion_propagation_barnard():
    t = TARGETS["barnard"]
    # 26 años después de J2000 Barnard se desplaza ~4,5′ al norte
    ra, dec = position_at(t["ra"], t["dec"], t["pmra"], t["pmdec"], t["parallax"], 51544.5 + 26 * 365.25)
    assert (dec - t["dec"]) * 60 == pytest.approx(10.362 * 26 / 60, rel=0.02)
    assert find_nearby_target(ra, dec)["id"] == "barnard"


def test_wise0855_challenge_position_resolves():
    # Coordenadas que da el enunciado del reto (época ~2014)
    r, d = parse_coordinates("08h55m10.831s", "-07d14m42.53s")
    assert find_nearby_target(r, d)["id"] == "wise0855"


# --- registros y épocas -----------------------------------------------------

def _rec(mjd, det=1, rel="qr3", obs="2026W21_2A_0001_2"):
    p = f"ibe/data/spherex/{rel}/level2/2026W21_2A/l2b-v27/{det}/level2_{obs}D{det}_spx_l2b-v27.fits"
    return _record_from_path(p, mjd)


def test_record_parsing():
    r = _rec(61181.5, det=3)
    assert r.detector == 3 and r.release == "qr3" and r.obsid == "2026W21_2A_0001_2"
    assert r.s3_url.endswith("qr3/level2/2026W21_2A/l2b-v27/3/level2_2026W21_2A_0001_2D3_spx_l2b-v27.fits")


def test_dedupe_prefers_dr1():
    a, b = _rec(61000, rel="qr3"), _rec(61000, rel="dr1")
    out = _dedupe([a, b])
    assert len(out) == 1 and out[0].release == "dr1"


def test_group_epochs_split_by_gap_and_long_spans():
    recs = [_rec(61000 + i, obs=f"A{i}_") for i in range(5)] + [_rec(61180 + i, obs=f"B{i}_") for i in range(3)]
    eps = P.group_epochs(recs)
    assert len(eps) == 2 and eps[0]["n_images"] == 5
    long = [_rec(60000 + 2 * i, obs=f"C{i}_") for i in range(100)]  # 200 días seguidos (polo eclíptico)
    assert len(P.group_epochs(long)) >= 6


def test_band_match_keeps_common_wavelengths():
    mk = lambda wl: {"wavelength_um": wl, "bandwidth_um": 0.02, "record": {"detector": 1}}
    by = {0: [mk(1.00), mk(1.20), mk(1.50)], 1: [mk(1.005), mk(1.40)]}
    out, info = P.band_match(by, min_keep=1)
    assert info["applied"]
    assert [s["wavelength_um"] for s in out[0]] == [1.00]
    assert [s["wavelength_um"] for s in out[1]] == [1.005]


# --- detección --------------------------------------------------------------

def _field(n=49, stars=((10, 10), (30, 35), (40, 12)), mover=None, noise=0.01, seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n]
    img = rng.normal(0, noise, (n, n))
    s = 1.2 / 2.355
    for x, y in stars:
        img += np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * s * s))
    if mover:
        x, y = mover
        img += np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * s * s))
    return {"data": img, "err": np.full((n, n), noise)}


def test_detects_mover_but_not_static_stars():
    grid, n = P.make_grid_wcs(10.0, 10.0, 5.0)
    eps = {0: _field(mover=(20, 20), seed=1), 1: _field(mover=(21.5, 20), seed=2), 2: _field(mover=(23, 20), seed=3)}
    mjd = {0: 61000.0, 1: 61182.0, 2: 61365.0}
    res = D.detect_candidates(eps, mjd, grid, gaia_sources=[])
    assert len(res["candidates"]) == 1
    c = res["candidates"][0]
    assert c["motion_arcsec_yr"] == pytest.approx(3.0 * 6.15, rel=0.15)  # 1,5 px / 0,5 año
    assert c["pmra_mas_yr"] < 0  # x crece hacia el oeste → movimiento al oeste
    assert "No catalogado" in c["quality"]["label"]


def test_injection_recovers_bright_fast_objects():
    grid, n = P.make_grid_wcs(10.0, 10.0, 5.0)
    eps = {0: _field(seed=1), 1: _field(seed=2), 2: _field(seed=3)}
    mjd = {0: 61000.0, 1: 61182.0, 2: 61365.0}
    res = D.injection_test(eps, mjd, grid, n_per_cell=3)
    bright_fast = [r for r in res["grid"] if r["peak_snr"] == 50 and r["speed_arcsec_yr"] == 15.0][0]
    assert bright_fast["fraction"] >= 0.66


def test_band_match_does_not_starve_epochs():
    mk = lambda wl: {"wavelength_um": wl, "bandwidth_um": 0.02, "record": {"detector": 1}}
    by = {0: [mk(1.0 + 0.1 * i) for i in range(8)], 1: [mk(1.005)] + [mk(2.0 + 0.1 * i) for i in range(7)]}
    out, info = P.band_match(by, min_keep=4)
    assert not info["applied"] and len(out[0]) == 8


def test_dipole_finds_blended_mover():
    n = 49
    yy, xx = np.mgrid[0:n, 0:n]
    s = 1.2 / 2.355
    g = lambda x, y, a=1.0: a * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * s * s))
    rng = np.random.default_rng(0)
    star = g(25, 24, 3.0)
    a = star + g(23.3, 24, 0.5) + rng.normal(0, 0.02, (n, n))
    b = star + g(24.6, 24, 0.5) + rng.normal(0, 0.02, (n, n))
    dps = D.find_dipoles(P.difference(b, a))
    assert any(abs(d["neg"][0] - 23) <= 1 and abs(d["pos"][0] - 25) <= 1 for d in dps)
