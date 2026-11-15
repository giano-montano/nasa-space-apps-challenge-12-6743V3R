"""
Astronomical Data Models and Scientific Synthesis for SPHEREx Targets.
Covers 102 spectral bands (0.75 - 5.0 um), 6 detectors, and physical models for:
- WISE 0855 (Cold Y/T brown dwarf)
- Barnard's Star (High proper motion M dwarf)
- Epsilon Indi B (Brown dwarf binary)
- RW Aurigae (Dust-occulted variable star)
- R Draconis (Mira-type pulsating giant)
"""

import math
import numpy as np
from typing import Dict, Any, List

# SPHEREx 6 Detectors and wavelength boundaries (in microns)
DETECTOR_BANDS = {
    1: {"name": "Detector 1", "min_wave": 0.75, "max_wave": 1.11, "bands": 17, "R": 41},
    2: {"name": "Detector 2", "min_wave": 1.11, "max_wave": 1.64, "bands": 17, "R": 41},
    3: {"name": "Detector 3", "min_wave": 1.64, "max_wave": 2.42, "bands": 17, "R": 41},
    4: {"name": "Detector 4", "min_wave": 2.42, "max_wave": 3.82, "bands": 17, "R": 35},
    5: {"name": "Detector 5", "min_wave": 3.82, "max_wave": 4.42, "bands": 17, "R": 110},
    6: {"name": "Detector 6", "min_wave": 4.42, "max_wave": 5.00, "bands": 17, "R": 130},
}

# Generate central wavelengths for all 102 bands
ALL_WAVELENGTHS: List[float] = []
for d_idx in range(1, 7):
    det = DETECTOR_BANDS[d_idx]
    waves = np.linspace(det["min_wave"], det["max_wave"], det["bands"])
    ALL_WAVELENGTHS.extend([round(float(w), 4) for w in waves])


TARGET_CATALOG: Dict[str, Dict[str, Any]] = {
    "wise0855": {
        "id": "wise0855",
        "name": "WISE 0855",
        "kind": "Sub-stellar Brown Dwarf (Y-dwarf)",
        "ra": 133.7951,
        "dec": -7.2451,
        "ra_sex": "08h 55m 10.83s",
        "dec_sex": "−07° 14′ 42.5″",
        "pm_ra": -8100.0,   # mas/yr
        "pm_dec": 1200.0,   # mas/yr
        "parallax": 433.0,  # mas (2.3 pc)
        "is_variable": False,
        "description": "El objeto de movimiento rápido más frío jamás descubierto fuera del Sistema Solar. A 7.5 años luz, muestra nubes de vapor de agua y metano.",
        "spectral_type": "Y0 (T_eff ≈ 250 K)"
    },
    "barnard": {
        "id": "barnard",
        "name": "Estrella de Barnard",
        "kind": "Enana roja cercana (M4V)",
        "ra": 269.4521,
        "dec": 4.6934,
        "ra_sex": "17h 57m 48.50s",
        "dec_sex": "+04° 41′ 36.2″",
        "pm_ra": -798.58,   # mas/yr
        "pm_dec": 10337.0,  # mas/yr (highest proper motion star)
        "parallax": 546.98, # mas
        "is_variable": False,
        "description": "La estrella solitaria más cercana a la Tierra (5.96 al). Su descomunal velocidad angular de 10.3 segundos de arco por año cruza el campo SPHEREx visiblemente.",
        "spectral_type": "M4V (T_eff ≈ 3100 K)"
    },
    "indi": {
        "id": "indi",
        "name": "Epsilon Indi B",
        "kind": "Par binario de enanas marrones (T1+T6)",
        "ra": 330.8400,
        "dec": -56.7860,
        "ra_sex": "22h 03m 21.60s",
        "dec_sex": "−56° 47′ 09.5″",
        "pm_ra": 4130.0,
        "pm_dec": -2530.0,
        "parallax": 275.8,
        "is_variable": False,
        "description": "Sistema binario de enanas marrones T frías que orbita una estrella K vecina a 11.8 años luz. Movimiento propio neto de 4.7″/año.",
        "spectral_type": "T1 + T6 (T_eff ≈ 1200 K)"
    },
    "rw_aur": {
        "id": "rw_aur",
        "name": "RW Aurigae",
        "kind": "Estrella variable T Tauri con ocultaciones por polvo",
        "ra": 76.9562,
        "dec": 30.4014,
        "ra_sex": "05h 07m 49.50s",
        "dec_sex": "+30° 24′ 05.1″",
        "pm_ra": 1.1,
        "pm_dec": -21.4,
        "parallax": 6.1,
        "is_variable": True,
        "description": "Estrella joven T Tauri con disco protoplanetario. No se traslada en el cielo, pero su brillo cae drásticamente debido a filamentos de polvo circunestelar.",
        "spectral_type": "K1-K4e + disco"
    },
    "r_dra": {
        "id": "r_dra",
        "name": "R Draconis",
        "kind": "Estrella variable pulsante gigante tipo Mira",
        "ra": 248.1675,
        "dec": 66.7551,
        "ra_sex": "16h 32m 40.20s",
        "dec_sex": "+66° 45′ 18.2″",
        "pm_ra": 14.2,
        "pm_dec": 8.7,
        "parallax": 1.5,
        "is_variable": True,
        "description": "Gigante roja pulsante con periodo de ~245 días. Expande y contrae sus capas exteriores produciendo enormes variaciones de flujo infrarrojo.",
        "spectral_type": "M6e-M9e Mira"
    }
}


def find_nearest_target(ra: float, dec: float, max_dist_deg: float = 0.5) -> Dict[str, Any] | None:
    """Finds matching catalog target within max_dist_deg."""
    for t in TARGET_CATALOG.values():
        d_ra = (ra - t["ra"]) * math.cos(math.radians(dec))
        d_dec = dec - t["dec"]
        dist = math.sqrt(d_ra ** 2 + d_dec ** 2)
        if dist <= max_dist_deg:
            return t
    return None


def generate_synthetic_spectrum(target_id: str) -> Dict[str, Any]:
    """
    Generates 102-band SPHEREx infrared spectrum (0.75 - 5.0 microns)
    incorporating specific molecular absorption features (CH4, H2O, CO, CO2, TiO).
    """
    wavelengths = np.array(ALL_WAVELENGTHS)
    t = TARGET_CATALOG.get(target_id)
    features = []

    if target_id == "wise0855":
        # Cold brown dwarf: peak in 4.5 - 5 um window, deep CH4 at 1.66, 2.2, 3.3 um, H2O at 1.4, 1.9 um
        base = np.exp(-((wavelengths - 4.7) / 1.1) ** 2) * 85.0 + 12.0
        # Methane dip
        ch4_1 = 0.65 * np.exp(-((wavelengths - 1.66) / 0.12) ** 2)
        ch4_2 = 0.70 * np.exp(-((wavelengths - 2.20) / 0.15) ** 2)
        ch4_3 = 0.85 * np.exp(-((wavelengths - 3.32) / 0.25) ** 2)
        # Water vapor dip
        h2o_1 = 0.60 * np.exp(-((wavelengths - 1.40) / 0.10) ** 2)
        h2o_2 = 0.75 * np.exp(-((wavelengths - 1.90) / 0.14) ** 2)
        flux = base * (1.0 - ch4_1) * (1.0 - ch4_2) * (1.0 - ch4_3) * (1.0 - h2o_1) * (1.0 - h2o_2)
        features = [
            {"label": "H₂O vapor", "wave": 1.40, "desc": "Banda de absorción de agua"},
            {"label": "CH₄ metano", "wave": 1.66, "desc": "Fuerte absorción por metano en enanas Y"},
            {"label": "H₂O vapor", "wave": 1.90, "desc": "Nubes de condensados de vapor"},
            {"label": "CH₄ metano", "wave": 3.32, "desc": "Banda fundamental de CH₄"},
            {"label": "Ventana 4.7 µm", "wave": 4.65, "desc": "Pico máximo de emisión infrarroja fría"}
        ]

    elif target_id == "barnard":
        # M4V Red dwarf: Planck-like curve peaking at 1.2 um with TiO, VO, and water bands
        base = 120.0 * (1.2 / wavelengths)**2 * np.exp(-((wavelengths - 1.25) / 1.8)**2)
        # Molecular bands
        tio = 0.35 * np.exp(-((wavelengths - 0.85) / 0.08) ** 2)
        h2o = 0.25 * np.exp(-((wavelengths - 1.45) / 0.12) ** 2)
        flux = base * (1.0 - tio) * (1.0 - h2o) + 15.0
        features = [
            {"label": "TiO / VO", "wave": 0.85, "desc": "Óxidos de titanio y vanadio en enana M"},
            {"label": "Pico continuo", "wave": 1.25, "desc": "Pico de energía térmica estelar"},
            {"label": "H₂O atmosférico", "wave": 1.45, "desc": "Vapor de agua fotosférico"}
        ]

    elif target_id == "indi":
        # T-dwarf binary: strong methane & neutral potassium
        base = 65.0 * np.exp(-((wavelengths - 3.8) / 1.4) ** 2) + 20.0
        ch4 = 0.60 * np.exp(-((wavelengths - 2.20) / 0.18) ** 2) + 0.70 * np.exp(-((wavelengths - 3.3) / 0.22) ** 2)
        flux = base * (1.0 - ch4)
        features = [
            {"label": "CH₄ banda K", "wave": 2.20, "desc": "Absorción característica enana T"},
            {"label": "CH₄ fundamental", "wave": 3.30, "desc": "Depresión profunda de metano"}
        ]

    elif target_id == "rw_aur":
        # T Tauri with circumstellar dust emission: rising infrared excess
        flux = 40.0 + 35.0 * (wavelengths / 5.0)**1.5 - 15.0 * np.exp(-((wavelengths - 3.05) / 0.25)**2)
        features = [
            {"label": "Polvo silicato", "wave": 3.05, "desc": "Granos de polvo protoplanetario"},
            {"label": "Exceso IR", "wave": 4.80, "desc": "Emisión térmica del disco circunestelar"}
        ]

    else:  # r_dra or default
        # Pulsating giant with strong CO bands at 2.3 and 4.6 um
        base = 150.0 * np.exp(-((wavelengths - 1.6) / 2.0)**2) + 30.0
        co_1 = 0.40 * np.exp(-((wavelengths - 2.35) / 0.15)**2)
        co_2 = 0.55 * np.exp(-((wavelengths - 4.67) / 0.20)**2)
        flux = base * (1.0 - co_1) * (1.0 - co_2)
        features = [
            {"label": "Pico H (1.6 µm)", "wave": 1.60, "desc": "Mínimo de opacidad H- de gigante"},
            {"label": "CO sobretono", "wave": 2.35, "desc": "Monóxido de carbono circunestelar"},
            {"label": "CO fundamental", "wave": 4.67, "desc": "Banda fundamental de CO fría"}
        ]

    # Add realistic detector noise (SNR ~ 50)
    noise = np.random.normal(0, 0.8, len(wavelengths))
    flux = np.clip(flux + noise, 1.0, 300.0)

    # Attach detector IDs
    data_points = []
    for i, w in enumerate(wavelengths):
        det_id = 1
        for d in range(1, 7):
            if DETECTOR_BANDS[d]["min_wave"] <= w <= DETECTOR_BANDS[d]["max_wave"]:
                det_id = d
                break
        data_points.append({
            "band_index": i + 1,
            "wavelength_um": round(float(w), 4),
            "flux_mjy": round(float(flux[i]), 2),
            "detector": det_id
        })

    return {
        "target_id": target_id,
        "name": t["name"] if t else "Coordenadas personalizadas",
        "unit": "mJy",
        "total_bands": len(data_points),
        "features": features,
        "spectrum": data_points
    }


def generate_lightcurve(target_id: str) -> Dict[str, Any]:
    """Generates photometric time-series across 8 SPHEREx epochs."""
    epochs = [
        {"epoch": 1, "mjd": 61000.0, "date": "2026-03-15", "desc": "Survey 1"},
        {"epoch": 2, "mjd": 61182.5, "date": "2026-09-13", "desc": "Survey 2"},
        {"epoch": 3, "mjd": 61365.0, "date": "2027-03-15", "desc": "Survey 3"},
        {"epoch": 4, "mjd": 61547.5, "date": "2027-09-13", "desc": "Survey 4"},
        {"epoch": 5, "mjd": 61730.0, "date": "2028-03-14", "desc": "Survey 5"},
        {"epoch": 6, "mjd": 61912.5, "date": "2028-09-12", "desc": "Survey 6"},
        {"epoch": 7, "mjd": 62095.0, "date": "2029-03-14", "desc": "Survey 7"},
        {"epoch": 8, "mjd": 62277.5, "date": "2029-09-12", "desc": "Survey 8"},
    ]

    points = []
    for ep in epochs:
        mjd = ep["mjd"]
        if target_id == "rw_aur":
            # Occultation event: drops by up to ~2.5 mag in epoch 3 and 4
            t_rel = (mjd - 61000.0) / 365.0
            dimming = 2.4 * math.exp(-((t_rel - 1.2) / 0.4)**2)
            mag = 10.2 + dimming + np.random.normal(0, 0.05)
            flux = 10.0 ** (-0.4 * (mag - 10.0)) * 100.0
        elif target_id == "r_dra":
            # Mira pulsation: period 245.5 days
            phase = (mjd - 61000.0) / 245.5 * 2.0 * math.pi
            mag = 9.5 + 2.2 * math.cos(phase) + np.random.normal(0, 0.04)
            flux = 10.0 ** (-0.4 * (mag - 10.0)) * 100.0
        else:
            # Steady non-variable star (WISE 0855, Barnard, Indi)
            mag = 12.0 + np.random.normal(0, 0.03)
            flux = 100.0 + np.random.normal(0, 2.0)

        points.append({
            "epoch": ep["epoch"],
            "mjd": ep["mjd"],
            "date": ep["date"],
            "flux_rel": round(float(flux), 2),
            "mag_approx": round(float(mag), 2),
            "err": 0.03
        })

    return {
        "target_id": target_id,
        "is_variable": target_id in ["rw_aur", "r_dra"],
        "lightcurve": points
    }

