"""
FastAPI Server for SPHEREx Sky Viewer.
Serves astronomical endpoints and mounts the improved frontend.
"""

import os
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .coords import parse_coordinates, deg_to_sexagesimal
from .irsa_client import fetch_spherex_data, clear_cache
from .astronomical_data import TARGET_CATALOG, find_nearest_target, generate_synthetic_spectrum, generate_lightcurve
from .gaia_client import get_gaia_dr3_sources

app = FastAPI(
    title="Drift — SPHEREx Sky Viewer API",
    description="NASA Space Apps Challenge 2026: Multi-epoch infrared sky viewer for fast-moving and variable object detection",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/targets")
def get_benchmark_targets():
    """Returns official NASA challenge benchmark test targets."""
    return list(TARGET_CATALOG.values())


@app.get("/api/frames")
def get_frames(
    ra: str = Query("133.7951", description="Right Ascension (deg or sexagesimal)"),
    dec: str = Query("-7.2451", description="Declination (deg or sexagesimal)"),
    fov: float = Query(5.0, description="Field of View in arcminutes"),
    mode: str = Query("blink", description="'blink', 'diff', or 'stack'"),
    detector: int = Query(1, ge=1, le=6, description="SPHEREx Detector (1 to 6)"),
    stack_detectors: bool = Query(False, description="Combine all 6 detectors for boosted SNR"),
    refresh: bool = Query(False, description="Force invalidate cache and fetch fresh data")
):
    """
    Fetches multi-epoch SPHEREx observation frames for the designated sky patch.
    """
    try:
        data = fetch_spherex_data(
            ra_str=ra,
            dec_str=dec,
            fov_arcmin=fov,
            mode=mode,
            detector_id=detector,
            stack_all_detectors=stack_detectors,
            refresh=refresh
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/spectrum")
def get_spectrum(
    ra: str = Query("133.7951"),
    dec: str = Query("-7.2451"),
    target_id: str = Query(None)
):
    """
    Returns 102-band on-the-fly infrared spectrum (0.75 - 5.0 um).
    """
    if not target_id:
        try:
            r, d = parse_coordinates(ra, dec)
            t = find_nearest_target(r, d)
            target_id = t["id"] if t else "custom"
        except Exception:
            target_id = "custom"

    return generate_synthetic_spectrum(target_id)


@app.get("/api/lightcurve")
def get_lightcurve(
    ra: str = Query("76.9562"),
    dec: str = Query("30.4014"),
    target_id: str = Query(None)
):
    """
    Returns photometric light curve across observation epochs for variable stars.
    """
    if not target_id:
        try:
            r, d = parse_coordinates(ra, dec)
            t = find_nearest_target(r, d)
            target_id = t["id"] if t else "custom"
        except Exception:
            target_id = "custom"

    return generate_lightcurve(target_id)


@app.get("/api/catalog")
def get_catalog(
    ra: str = Query("133.7951"),
    dec: str = Query("-7.2451"),
    fov: float = Query(5.0),
    source: str = Query("gaia")
):
    """
    Fetches Gaia DR3 proper motion catalog overlay.
    """
    try:
        r, d = parse_coordinates(ra, dec)
        sources = get_gaia_dr3_sources(r, d, fov_arcmin=fov)
        return {
            "source": "Gaia DR3",
            "center": {"ra": r, "dec": d},
            "fov_arcmin": fov,
            "count": len(sources),
            "sources": sources
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/refresh")
def refresh_cache():
    """Invalidates the local query cache to discover new data releases."""
    cleared = clear_cache()
    return {"status": "ok", "message": f"Cache cleared successfully. {cleared} files removed."}


# Mount the improved frontend static directory
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

