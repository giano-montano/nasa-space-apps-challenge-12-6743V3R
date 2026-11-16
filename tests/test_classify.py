import numpy as np

from backend.app.classify import TEMPLATES, classify_spectrum, combine, simbad_category


def _fake(fn, n=110, snr=40, seed=0, sat=False):
    rng = np.random.default_rng(seed)
    lam = np.sort(rng.uniform(0.75, 5.0, n))
    f = fn(lam)
    f = f / np.median(f) * 10.0
    err = np.abs(f) / snr + 0.05
    flux = f + rng.normal(0, 1, n) * err
    return [{"wavelength_um": float(l), "flux_mjy": float(x), "err_mjy": float(e), "detector": 1 + int(l // 0.85),
             "saturated": sat} for l, x, e in zip(lam, flux, err)]


def test_templates_recover_their_class():
    for cls, member in (("star", 4), ("ty_dwarf", 2), ("quasar", 13), ("yso", 10)):
        name, fn = TEMPLATES[cls][member]
        r = classify_spectrum(_fake(fn))
        assert r["available"]
        assert r["top"] == cls, (cls, name, r["probabilities"])


def test_saturated_spectrum_is_not_classified():
    r = classify_spectrum(_fake(TEMPLATES["star"][3][1], sat=True))
    assert not r["available"] and "saturad" in r["reason"]


def test_simbad_categories():
    assert simbad_category("BD*", "T6") == "ty_dwarf"
    assert simbad_category("BD*", "L3") == "l_dwarf"
    assert simbad_category("TT*") == "yso"
    assert simbad_category("QSO") == "quasar"
    assert simbad_category("GiG") == "galaxy"
    assert simbad_category("Mi*") == "star"
    assert simbad_category("IR") is None


def test_motion_rules_out_extragalactic():
    spec = classify_spectrum(_fake(TEMPLATES["quasar"][13][1]))
    moving = combine(spec, None, 2.0, "test", None, 150.0, 60.0)
    assert max(moving["probabilities"], key=moving["probabilities"].get) != "quasar"
    assert moving["probabilities"]["quasar"] < 0.3


def test_catalog_wins():
    spec = classify_spectrum(_fake(TEMPLATES["quasar"][13][1]))
    out = combine(spec, {"name": "X", "kind": "Estrella", "category": "star", "source": "test"}, None, None, None, 10.0, 10.0)
    assert out["category"] == "star" and out["method"] == "catálogo"
