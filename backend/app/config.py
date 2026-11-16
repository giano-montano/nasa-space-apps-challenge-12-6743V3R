"""
Configuración central. Todo lo que cambia con un nuevo lanzamiento de datos
se ajusta aquí o con variables de entorno, sin tocar el resto del código.
"""

import os

# --- IRSA / SPHEREx --------------------------------------------------------
IRSA_TAP_URL = os.getenv("IRSA_TAP_URL", "https://irsa.ipac.caltech.edu/TAP/sync")
IRSA_SIA_URL = os.getenv("IRSA_SIA_URL", "https://irsa.ipac.caltech.edu/SIA")
IRSA_BASE_URL = os.getenv("IRSA_BASE_URL", "https://irsa.ipac.caltech.edu/")

# Colecciones SIA2 en orden de preferencia (la primera gana si una misma
# observación aparece en varias). Al salir un release nuevo basta con
# añadirlo aquí o en la variable de entorno SPHEREX_COLLECTIONS.
SPHEREX_COLLECTIONS = [
    c.strip() for c in os.getenv("SPHEREX_COLLECTIONS", "spherex_dr1,spherex_qr3").split(",") if c.strip()
]

# Bucket público de AWS (lectura parcial por rangos HTTP, evita bajar la EPSF).
SPHEREX_S3_HTTP = os.getenv("SPHEREX_S3_HTTP", "https://nasa-irsa-spherex.s3.amazonaws.com/")

# --- Catálogos externos ----------------------------------------------------
GAIA_ESA_TAP = os.getenv("GAIA_ESA_TAP", "https://gea.esac.esa.int/tap-server/tap/sync")
GAIA_VIZIER_TAP = os.getenv("GAIA_VIZIER_TAP", "https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync")
SESAME_URL = os.getenv("SESAME_URL", "https://cds.unistra.fr/cgi-bin/nph-sesame/-oIp/SNV")
SIMBAD_TAP_URL = os.getenv("SIMBAD_TAP_URL", "https://simbad.cds.unistra.fr/simbad/sim-tap/sync")
JPL_SBIDENT_URL = os.getenv("JPL_SBIDENT_URL", "https://ssd-api.jpl.nasa.gov/sb_ident.api")

# --- Instrumento -----------------------------------------------------------
PIXEL_SCALE_ARCSEC = 6.15  # medido en los encabezados WCS de las imágenes L2

# Bits de FLAGS que invalidan un píxel para la imagen (nombres según MSKNnnnn
# del encabezado FLAGS). SOURCE (21) NO se enmascara: marca fuentes conocidas.
BAD_FLAG_NAMES = [
    "TRANSIENT", "OVERFLOW", "SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD",
    "PERSIST", "OUTLIER", "GHOST", "GHOST_FPA", "GHOST_EXT", "STREAK", "SNOWBALL",
]
# En píxeles de fuentes conocidas (bit SOURCE) las estrellas brillantes saturan:
# el pipeline marca OVERFLOW/TRANSIENT/SUR_ERROR pero da un valor estimado con las
# lecturas previas a la saturación. Ahí solo se descartan defectos del detector.
HARD_BAD_FLAG_NAMES = ["NONFUNC", "MISSING_DATA", "HOT", "COLD"]
SATURATION_FLAG_NAMES = ["OVERFLOW", "SUR_ERROR"]
# Banderas que solo se reportan como "contaminación" en los metadatos.
CONTAM_FLAG_NAMES = BAD_FLAG_NAMES + ["NONLINEAR", "CROSSTALK", "BLOOM", "HALO", "DICHROIC"]

# --- Rendimiento -----------------------------------------------------------
CACHE_DIR = os.getenv("CACHE_DIR", os.path.join(os.path.dirname(__file__), "data_cache"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", str(24 * 3600)))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "16"))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "60"))
IRSA_RETRIES = int(os.getenv("IRSA_RETRIES", "3"))
CATALOG_WAIT_SECONDS = float(os.getenv("CATALOG_WAIT_SECONDS", "45"))
# Máximo de imágenes por época y detector que se bajan para el visor.
MAX_IMAGES_PER_EPOCH_DET = int(os.getenv("MAX_IMAGES_PER_EPOCH_DET", "24"))
# Separación mínima (días) entre dos épocas consecutivas.
EPOCH_GAP_DAYS = float(os.getenv("EPOCH_GAP_DAYS", "45"))

FOV_CHOICES_ARCMIN = [2.0, 5.0, 10.0, 20.0]
MAX_FOV_ARCMIN = 30.0

os.makedirs(CACHE_DIR, exist_ok=True)
