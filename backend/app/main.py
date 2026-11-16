"""
API de Drift — SPHEREx Sky Viewer (datos reales de NASA/IPAC IRSA).
"""

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .catalogs import CatalogUnavailable
from .coords import deg_to_sexagesimal, parse_coordinates
from .irsa_client import IrsaUnavailable, clear_cache
from .targets import public_targets, resolve_name
from . import chat, viewer
from pydantic import BaseModel
import requests

app = FastAPI(
    title="Drift — SPHEREx Sky Viewer API",
    description="Visor público de imágenes reales de SPHEREx en el tiempo (NASA Space Apps 2026, reto Planet X and SPHEREx).",
    version="3.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=2000)


def _coords(ra: str, dec: str):
    try:
        return parse_coordinates(ra, dec)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _dets(detectors: str):
    if detectors in ("all", "*"):
        return list(range(1, 7))
    try:
        d = sorted({int(x) for x in detectors.split(",") if x.strip()})
    except ValueError:
        raise HTTPException(422, "detectors debe ser una lista como 1,2 o 'all'.")
    if not d or any(x < 1 or x > 6 for x in d):
        raise HTTPException(422, "Los detectores van del 1 al 6.")
    return d


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except IrsaUnavailable as e:
        raise HTTPException(status_code=503, detail=f"IRSA (NASA) no responde ahora: {e}. Prueba de nuevo en unos minutos.")
    except CatalogUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/health")
def health():
    return {"status": "ok", "collections": config.SPHEREX_COLLECTIONS}


@app.get("/api/targets")
def targets():
    """Los cinco objetivos de prueba del reto (posiciones de SIMBAD)."""
    return public_targets()


@app.get("/api/resolve")
def resolve(name: str = Query(..., min_length=1, max_length=120)):
    """Nombre → coordenadas (SIMBAD/NED/VizieR vía Sesame)."""
    try:
        r = resolve_name(name)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(503, f"El servicio de nombres (CDS) no responde: {e.__class__.__name__}")
    r["ra_sex"], r["dec_sex"] = deg_to_sexagesimal(r["ra"], r["dec"])
    return r


@app.get("/api/epochs")
def epochs(ra: str, dec: str, target: Optional[str] = None, refresh: bool = False):
    """Fechas disponibles en IRSA para un punto (rápido, solo metadatos)."""
    r, d = _coords(ra, dec)
    info = _guard(viewer.list_epochs, r, d, target, refresh)
    return {k: v for k, v in info.items() if not k.startswith("_")}


@app.get("/api/frames")
def frames(
    ra: str, dec: str,
    target: Optional[str] = None,
    fov: float = Query(5.0, ge=1.0, le=config.MAX_FOV_ARCMIN, description="Campo de visión en minutos de arco"),
    detectors: Optional[str] = Query(None, description="Detectores a combinar: '1', '1,2' o 'all'. Vacío = recomendado para el objetivo"),
    match_bands: bool = Query(True, description="Comparar solo longitudes de onda equivalentes entre épocas"),
    epochs: Optional[str] = Query(None, description="Índices de época a usar, p. ej. '0,2'"),
    ref: Optional[int] = Query(None, description="Época de referencia para la diferencia"),
    stretch: str = Query("asinh", pattern="^(asinh|log|sqrt|linear)$"),
    refresh: bool = False,
    job: Optional[str] = None,
):
    r, d = _coords(ra, dec)
    ep = None
    if epochs:
        try:
            ep = sorted({int(x) for x in epochs.split(",") if x.strip()})
        except ValueError:
            raise HTTPException(422, "epochs debe ser una lista de números.")
    res = _guard(viewer.build_view, r, d, target, fov, _dets(detectors) if detectors else None, match_bands, ep, ref, stretch, refresh, job)
    return res


@app.get("/api/spectrum")
def spectrum(ra: str, dec: str, target: Optional[str] = None, epoch: Optional[int] = None,
             refresh: bool = False, job: Optional[str] = None):
    """Espectro al vuelo (flujo vs longitud de onda) en una posición."""
    r, d = _coords(ra, dec)
    return _guard(viewer.build_spectrum, r, d, target, epoch, refresh, job)


@app.get("/api/classify")
def classify(ra: str, dec: str, target: Optional[str] = None, epoch: Optional[int] = None,
             pm: Optional[float] = Query(None, ge=0, description="Movimiento propio medido (″/año), si se conoce"),
             var: Optional[float] = Query(None, ge=0, description="Cambio de brillo máximo medido (mag), si se conoce"),
             refresh: bool = False, job: Optional[str] = None):
    """¿Qué tipo de objeto es? Catálogo (SIMBAD) → plantillas del espectro → contexto (movimiento, brillo, posición)."""
    r, d = _coords(ra, dec)
    return _guard(viewer.build_classification, r, d, target, pm, var, epoch, refresh, job)


@app.get("/api/lightcurve")
def lightcurve(ra: str, dec: str, target: Optional[str] = None, refresh: bool = False, job: Optional[str] = None):
    """Curva de luz comparando longitudes de onda equivalentes entre épocas."""
    r, d = _coords(ra, dec)
    return _guard(viewer.build_lightcurve, r, d, target, refresh, job)


@app.get("/api/catalog")
def catalog(ra: str, dec: str, fov: float = Query(5.0, ge=1.0, le=config.MAX_FOV_ARCMIN),
            source: str = Query("gaia", pattern="^(gaia|wise)$")):
    """Fuentes de Gaia DR3 o AllWISE en el campo."""
    r, d = _coords(ra, dec)
    return _guard(viewer.catalog_overlay, r, d, fov, source)


@app.get("/api/injection-test")
def injection(ra: str, dec: str, target: Optional[str] = None, fov: float = 5.0, detectors: str = "1",
              job: Optional[str] = None):
    """Prueba de honestidad: sensibilidad del detector con objetos simulados inyectados."""
    r, d = _coords(ra, dec)
    return _guard(viewer.run_injection, r, d, target, fov, _dets(detectors), job)


@app.get("/api/progress")
def progress(job: str):
    return viewer.get_progress(job)


@app.post("/api/refresh")
def refresh(stamps: bool = False):
    """Borra consultas guardadas para incorporar nuevos lanzamientos de datos de IRSA."""
    n = clear_cache(include_stamps=stamps)
    return {"status": "ok", "removed": n,
            "message": f"Caché borrada ({n} archivos). La próxima consulta irá a IRSA y verá los datos nuevos."}


class ChatIn(BaseModel):
    messages: list[dict]
    context: dict = {}


@app.get("/api/chat/status")
def chat_status():
    return {"enabled": chat.available()}


@app.post("/api/chat")
def chat_endpoint(body: ChatIn):
    """Copiloto IA (Groq). Recibe el historial y el estado de la vista."""
    if not chat.available():
        raise HTTPException(503, "El copiloto no está configurado (falta GROQ_API_KEY en el servidor).")
    try:
        return {"reply": chat.ask(body.messages, body.context)}
    except requests.RequestException:
        raise HTTPException(503, "No pude responder ahora. Prueba de nuevo en un momento.")


@app.exception_handler(Exception)
async def unhandled(request, exc):
    return JSONResponse(status_code=500, content={"detail": f"Error interno: {exc.__class__.__name__}: {exc}"})


frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
