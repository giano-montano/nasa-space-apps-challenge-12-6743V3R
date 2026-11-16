# Drift — visor de cambios en el cielo con SPHEREx

**NASA Space Apps Challenge 2026 · reto "Planet X and SPHEREx"**

Escribe una posición del cielo (o el nombre de un objeto) y mira las **imágenes reales** de la misión SPHEREx de NASA de ese lugar, tomadas en fechas distintas, como un mini video. Lo que salta de lugar se está moviendo: así se descubrió Plutón y así voluntarios han encontrado enanas marrones y cometas.

Todas las imágenes vienen de NASA/IPAC IRSA en el momento de la consulta. Nada es simulado, salvo la prueba de sensibilidad, que se rotula como tal.

---

## Inicio rápido

Requisitos: Python 3.10 o superior.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r backend/requirements.txt
python run_app.py                  # abre http://127.0.0.1:8000
```

En Windows también puedes hacer doble clic en `start.bat`.

**Sin servidor:** si abres `frontend/` como página estática (o IRSA no responde), los 5 casos de prueba se cargan desde `frontend/demo_data/`. Es una copia de datos reales que indica la fecha en que se descargó.

**Primera consulta de un lugar:** puede tardar entre 30 s y 1 min, porque busca las imágenes en IRSA y lee un recorte de cada una. Después queda en caché y carga en menos de 1 s.

---

## Qué hace (y cómo cumple el reto)

| Requisito del reto | Cómo lo resuelve Drift |
|---|---|
| Herramienta web pública | Una sola página, sin registro, funciona en celular. `Dockerfile` y `render.yaml` incluidos para publicarla. |
| Ingresar RA/Dec | Grados o sexagesimal (`08h55m10.8s`, `-07d14m42s`, `−07°14′42″`). También **por nombre** (SIMBAD/Sesame). |
| Imágenes de SPHEREx como mini video | Reproductor con play/pausa, paso a paso, velocidad, teclado y **línea de tiempo con las fechas reales** disponibles. |
| Los 5 casos de prueba | Botones para WISE 0855, Estrella de Barnard, Epsilon Indi B, RW Aurigae y R Draconis, con posiciones y movimientos propios de SIMBAD. |
| *Opcional:* actualizable | No hay fechas ni archivos fijos en el código: cada consulta descubre las imágenes en IRSA (SIA2/TAP). Ver abajo. |
| *Opcional:* 102 bandas y 6 detectores | Se elige qué detectores sumar (D1–D6 o los 6). **Espectro al vuelo** al hacer clic en cualquier fuente. |
| *Opcional:* sumar/restar épocas | Modos **Parpadeo, Deslizador, Diferencia y Suma**. |
| *Opcional:* campo de visión | 2′, 5′, 10′ o 20′ (avisa que lo grande tarda más). |
| *Opcional:* otros telescopios | Capas de **Gaia DR3** (propagada a la fecha de cada imagen, con flechas de movimiento) y **AllWISE**. Pestaña con **Aladin Lite** (DSS2, 2MASS, WISE). |
| *Opcional:* coordenadas en la URL | `?ra=&dec=&fov=&mode=&det=` y botón "Compartir / insertar" con código `<iframe>` (`&embed=1`). |
| *Opcional:* metadatos y banderas | Pestaña **Datos**: cada foto usada, su longitud de onda, release, control de calidad y píxeles marcados por bandera (FLAGS). |
| *Opcional:* Astropy / Aladin | Astropy para WCS, FITS, coordenadas y tiempos. Aladin Lite para el contexto. |

### Ciencia detrás de cada imagen
1. **Búsqueda:** SIA2 de IRSA en las colecciones `spherex_dr1` y `spherex_qr3` (TAP de respaldo). Se eliminan duplicados entre releases.
2. **Lectura liviana:** de cada FITS (2040×2040, ~70 MB) se leen solo los píxeles necesarios desde el bucket público de AWS `nasa-irsa-spherex`, por rangos HTTP. Se omite la tabla EPSF de ~4 MB. Como respaldo se usa el servicio de cutouts de IRSA.
3. **Épocas:** las exposiciones se agrupan por visitas separadas en el tiempo. Cerca de los polos de la eclíptica, donde SPHEREx observa casi a diario, se agrupan en bloques de ~30 días.
4. **Emparejamiento de banda:** SPHEREx usa filtros lineales variables, así que cada píxel ve otra longitud de onda (tabla `WCS-WAVE`). Se comparan solo exposiciones de color equivalente entre fechas. Si eso deja muy pocas fotos, se usan todas y se avisa.
5. **Limpieza:** se resta el fondo zodiacal (`ZODI`) y se descartan los píxeles marcados en `FLAGS` (calientes, rayos, reflejos…). Luego cada foto se reproyecta a una rejilla común (6,15″/px, norte arriba) y se combina ponderando por la inversa de la `VARIANCE`.
6. **Movimiento propio:** para los objetivos rápidos, el recorte se centra en su posición a la fecha media de las imágenes y se dibuja su **trayectoria esperada**. Barnard se movió ~4,5′ desde J2000: sin esto quedaría fuera del recorte.

### Detección asistida (candidatos para revisión humana)
- Detecta fuentes en cada fecha, las enlaza entre fechas y ajusta un movimiento lineal con su incertidumbre.
- Marca como candidato lo que se mueve ≥ 0,5 px y ≥ 5σ. Lo coteja con Gaia DR3 en la misma fecha: "conocido", "probable falso movimiento" o "no catalogado, revisar".
- Lista aparte las fuentes que aparecen en **una sola fecha** (posibles asteroides o artefactos).
- Cada candidato y fuente de una sola fecha se coteja con **JPL Small-Body Identification** (asteroides y cometas predichos en esa fecha): "coincide con cuerpo conocido: NOMBRE".
- **Prueba de honestidad:** inyecta objetos simulados con distintos brillos y velocidades sobre las imágenes reales y muestra qué fracción se recupera.
- Exporta los candidatos a JSON o CSV, y una captura a PNG.

### Espectro y curva de luz
- **Espectro:** fotometría de apertura (12″, con fondo local) en cada exposición de una fecha. Cada punto es una foto, en la longitud de onda de ese píxel.
- **Curva de luz:** cada fecha se compara con una fecha de referencia **en la misma longitud de onda**, por detector, y se expresa como Δmag. Así se ve la variabilidad de RW Aur y R Dra sin que el cambio de filtro la falsee.

---

## Nuevos lanzamientos de datos (sin tocar código)
- Las imágenes se descubren en IRSA en cada consulta. La caché de búsquedas dura 24 h (`CACHE_TTL_SECONDS`).
- El botón **"↻ Buscar datos nuevos en IRSA"** o `POST /api/refresh` la borran antes.
- Si IRSA publica una colección nueva (p. ej. `spherex_qr4`), basta con añadirla a la variable de entorno `SPHEREX_COLLECTIONS=spherex_dr1,spherex_qr3,spherex_qr4`. El orden indica cuál se prefiere cuando una exposición aparece en varias.
- `python generate_demo_data.py --refresh` regenera la copia sin conexión de los 5 casos.

## API
| Endpoint | Para qué |
|---|---|
| `GET /api/targets` | Casos de prueba |
| `GET /api/resolve?name=` | Nombre → coordenadas (Sesame) |
| `GET /api/epochs?ra=&dec=` | Fechas disponibles (solo metadatos, rápido) |
| `GET /api/frames?ra=&dec=&fov=&detectors=&match_bands=&ref=&stretch=` | Imágenes por fecha, diferencias, suma, trayectoria y candidatos |
| `GET /api/spectrum?ra=&dec=` | Espectro al vuelo |
| `GET /api/lightcurve?ra=&dec=` | Curva de luz por color |
| `GET /api/catalog?source=gaia\|wise` | Gaia DR3 / AllWISE del campo |
| `GET /api/injection-test` | Prueba de sensibilidad con objetos simulados |
| `POST /api/refresh` | Invalida la caché |

Documentación interactiva en `/docs`.

## Despliegue público
- **Docker:** `docker build -t drift . && docker run -p 8000:8000 drift`
- **Render:** "New → Blueprint" con este repositorio (usa `render.yaml`, con un disco para la caché).
- Después de publicar, conviene abrir los 5 casos una vez para dejarlos en caché, y probar el enlace desde otra red.

## Pruebas
```bash
pip install pytest
python -m pytest tests
```
Cubren el conversor de coordenadas, la propagación del movimiento propio, la agrupación en épocas, el emparejamiento de banda, la detección y la inyección.

## Limitaciones (honestas)
- Píxeles de 6,2″: solo se ven movimientos de ≳1″/año en fuentes brillantes, y dos fuentes a menos de ~10″ se confunden. Epsilon Indi B se ve como un solo punto.
- SPHEREx observa cada punto pocas veces por año desde mayo de 2025: hoy hay ~3 fechas por lugar. Con los años la herramienta mejora sola.
- Los candidatos son sugerencias automáticas, no descubrimientos. El cotejo con asteroides y cometas conocidos (JPL `sb_ident`, observador geocéntrico) es automático y aproximado; si JPL no responde, el candidato queda "sin cotejar".
- La primera consulta de un lugar depende de la velocidad de IRSA y AWS.

## Créditos
- Imágenes: **NASA/JPL-Caltech/IPAC — SPHEREx**, vía NASA/IPAC Infrared Science Archive (IRSA).
- Catálogos: **ESA Gaia DR3** (copias de IRSA, ESA y VizieR) y **NASA/JPL-Caltech WISE (AllWISE)**.
- Resolución de nombres: **SIMBAD/Sesame** (CDS, Estrasburgo). Visor de contexto: **Aladin Lite** (CDS).
- Software: Astropy, NumPy, SciPy, FastAPI, fsspec.

Proyecto de hackathon, no es un producto oficial de NASA.
