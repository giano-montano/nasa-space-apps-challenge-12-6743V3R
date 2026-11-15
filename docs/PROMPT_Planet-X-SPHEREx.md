# PROMPT MAESTRO — "Planet X and SPHEREx" (NASA Space Apps 2026, Advanced)

> Pega todo este archivo en tu asistente de código (Claude Code / Cursor / etc.) y trabaja por fases. Tenemos ~10 horas: prioriza que lo básico funcione de punta a punta antes de añadir extras.

---

## 0. ROL

Eres un ingeniero full-stack senior con experiencia en astronomía de datos (astropy, astroquery, FITS/WCS) y en UX de herramientas científicas públicas. Vas a construir, junto conmigo, un proyecto para el NASA Space Apps Challenge 2026 que debe funcionar en vivo, verse profesional y poder ser usado por cualquier persona sin conocimientos de astronomía.

## 1. EL RETO (resumen oficial)

SPHEREx mapea todo el cielo cada seis meses en 102 bandas de infrarrojo cercano. Hay imágenes de más de mil millones de objetos. Cometas, asteroides, estrellas cercanas, enanas marrones e incluso planetas nuevos se delatan porque **cambian de posición entre imágenes**. Nadie puede revisar todo eso solo.

**Objetivo:** crear una **herramienta web pública** donde el usuario ingresa coordenadas (Ascensión Recta y Declinación) de un parche de cielo y la herramienta muestra una **serie de imágenes de SPHEREx de ese parche como un mini-video**, para detectar fácilmente objetos en movimiento.

**Casos de prueba obligatorios (deben funcionar y verse bien):**
- Estrella de Barnard
- Epsilon Indi B (par de enanas marrones que orbitan una estrella)
- WISE 0855 (enana marrón de movimiento rápido): RA 08h55m10.831s, Dec −7°14′42.53″
- Estrellas variables RW Aurigae y R Draconis

**Consideraciones opcionales (nuestra oportunidad de destacar):**
1. Fácil de actualizar con nuevos lanzamientos de datos.
2. Aprovechar las 102 bandas: sumar por separado los datos de cada uno de los 6 detectores para mejorar la señal/ruido. **Puntos extra: generar espectros al vuelo.**
3. Sumar o restar imágenes de distintas épocas para resaltar objetos móviles.
4. Campo de visión (FOV) elegible por el usuario.
5. Superponer catálogos de otros telescopios (Gaia DR3, WISE).
6. Consultas por URL (`?ra=...&dec=...`) para poder embeber la herramienta.
7. Mostrar metadatos (banderas de contaminación).
8. Usar herramientas existentes (astropy, Aladin Lite del CDS).

Modelo de inspiración: **WiseView** (http://byw.tools/wiseview) — la herramienta equivalente para WISE, con la que voluntarios han hecho cientos de descubrimientos. Nuestra meta: "WiseView para SPHEREx", pero mejor.

## 2. FUENTES DE DATOS (todas públicas)

- **NASA/IPAC Infrared Science Archive (IRSA) — SPHEREx:** https://irsa.ipac.caltech.edu/Missions/spherex.html
- **Tutoriales oficiales (Jupyter) para acceder a los datos con Python:** https://caltech-ipac.github.io/irsa-tutorials/spherex/
- **Gaia DR3** (usar el último release): https://archive.stsci.edu/missions-and-data/gaia
- Opcional (socios CSA): NEOSSat (https://data.asc-csa.gc.ca/dataset/neossat), CADC.

**Detalles técnicos de IRSA (tomados de la especificación del reto; verifícalos contra la documentación oficial antes de usarlos):**
- Guía de acceso a datos (SIA2, estándares IVOA, cutouts, explorador web): `caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access`
- Guía de productos de datos (qué contiene cada archivo: extensiones IMAGE, FLAGS, VARIANCE, ZODI, PSF, WCS-WAVE): `caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products`
- **Cutout Tool / servicio de cutouts:** `irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html`. Es la clave para una web liviana: pide recortes pequeños, NUNCA descargues las imágenes completas.
- Acceso en la nube: bucket público de AWS S3 `nasa-irsa-spherex`, región us-east-1 (`irsa.ipac.caltech.edu/cloud_access/`).
- Colecciones SIA2: `spherex_qr` (Wide Survey), `spherex_qr_deep` (Deep Survey), `spherex_qr_cal` (calibración).
- **Quick Release 2 (QR2):** datos recalibrados, publicados semanalmente desde octubre de 2025; reemplaza a QR1. Usa QR2.
- Los archivos son imágenes espectrales calibradas de Nivel 2 (FITS grandes con varias extensiones). Píxeles de 6,2″. Rango 0,75 a 5 µm.
- Los datos de WISE también están en IRSA (sirven para el overlay).
- Servicios de cuerpos menores de JPL: NO están en la lista oficial del reto. Útiles para descartar asteroides/cometas conocidos, pero verifica sus URLs antes de depender de ellos.

**INSTRUCCIÓN CRÍTICA PARA TI (asistente):** antes de escribir código, **lee los tutoriales de IRSA** y determina el servicio exacto (SIA / TAP / cutouts, nombres de tablas, columnas, formato de los FITS, cómo se manejan los 6 detectores y el WCS espectral). **No inventes nombres de endpoints ni columnas.** Si algo no está claro, dímelo y propón la forma más segura de verificarlo. Ten presente que en SPHEREx la longitud de onda varía a lo largo del detector (filtros lineales variables), así que una imagen no es monocromática: investiga cómo obtener el mapa de longitud de onda por píxel y úsalo en los espectros.

## 3. ARQUITECTURA SUGERIDA

- **Backend:** Python + FastAPI. Usa `astropy` y `astroquery` (IRSA, Gaia). Motivos: evitar problemas de CORS desde el navegador, procesar FITS, y cachear resultados.
  - `GET /api/frames?ra=&dec=&fov=&mode=&detector=` → lista de frames (fecha, banda, detector, URL de imagen PNG ya renderizada, metadatos/flags).
  - `GET /api/spectrum?ra=&dec=&radius=` → espectro de la fuente en esa posición.
  - `GET /api/catalog?ra=&dec=&fov=&source=gaia` → fuentes Gaia DR3 con movimiento propio para superponer.
  - Caché en disco por (ra, dec, fov) para que las demos sean instantáneas.
  - **Diseño para datos nuevos (el reto lo pide):** NO escribas épocas, fechas ni nombres de archivos fijos en el código. Descubre las observaciones disponibles consultando el IRSA en cada petición (o con un refresco periódico). La caché debe tener caducidad (TTL) y un endpoint/botón `refresh` para invalidarla. Documenta en el README cómo se incorporan los nuevos lanzamientos sin tocar el código.
- **Frontend:** una sola página, rápida y bonita (React + Vite o JS vanilla). Sin login. Responsive.
- **Modo demo offline:** pre-calcula y guarda en caché los 5 casos de prueba para que la demo no dependa de la red del evento.

## 4. FUNCIONALIDADES (por prioridad)

### Fase 1 — MVP (hacer primero, ~3 h)
1. Formulario RA/Dec (grados y sexagesimal) + botones de los 5 objetos de prueba. **Además, aceptar el nombre de un objeto conocido** (resolución por nombre, por ejemplo con astropy/SIMBAD).
2. Descarga de cutouts SPHEREx de ese parche (usando el servicio de cutouts del IRSA, nunca archivos completos), ordenados por fecha.
2b. **Línea de tiempo:** mostrar qué fechas existen para ese punto del cielo y permitir elegir cuáles usar.
3. **Reproductor tipo video:** play/pausa, **paso a paso (frame anterior/siguiente)**, control de velocidad, deslizador de frames, loop, fecha visible en cada frame.
4. Escalado visual correcto (stretch asinh/log, percentiles) para que se vean fuentes tenues.
5. Marcador fijo en el centro y retícula para ver el desplazamiento.

### Fase 2 — Diferenciadores (~3 h)
6. **Selector de FOV** (con aviso de tiempo de carga a mayor FOV).
7. **Apilado por detector** (sumar los datos de cada uno de los 6 arrays para mejorar S/N) y selector de banda/detector.
8. **Modos de comparación:** blink, **deslizador (swipe) entre dos épocas**, y diferencia (resta); opcionalmente suma o resta de imágenes de épocas distintas, para resaltar lo que se movió.
9. **Estado en la URL** (`?ra=&dec=&fov=&mode=`) y botón "Copiar enlace / Embeber".
10. **Overlay de otros telescopios:** Gaia DR3 (con vectores de movimiento propio, para contrastar el movimiento detectado con el esperado) y WISE (catálogo/imagen) como capa opcional activable.
10b. **Curva de luz para estrellas variables:** al elegir una fuente, graficar su brillo vs. tiempo (RW Aurigae y R Draconis NO se desplazan, cambian de brillo; el video solo no lo muestra bien). Marca claramente los frames usados.
10c. **Panel opcional de contexto con Aladin Lite (CDS)** para ver la misma zona en otros surveys.

### Fase 3 — Para deslumbrar (~2 h)
11. **Espectro al vuelo:** al hacer clic en una fuente, mostrar su espectro (flujo vs. longitud de onda) en un panel lateral.
12. **Panel de metadatos y banderas de contaminación** por frame.
13. **Detección asistida de movimiento (nivel avanzado, y la parte más delicada):**
   - **13a. Emparejamiento de banda (CRÍTICO):** SPHEREx usa filtros variables lineales, así que la longitud de onda cambia a lo largo del detector. Compara SOLO imágenes con longitud de onda equivalente en esa zona del detector (usa la extensión WCS-WAVE). Comparar bandas distintas genera falsos movimientos.
   - **13b. Resta de fondo y máscaras:** usa las extensiones de fondo zodiacal (ZODI) y de banderas (FLAGS) de cada archivo.
   - **13c. Candidatos:** marca fuentes que cambian de posición entre épocas, con puntuación de calidad.
   - **13d. Cotejo con otros datos:** descarta estrellas y objetos ya catalogados con Gaia DR3 y, si verificas que funcionan, con servicios de cuerpos menores de JPL.
   - **13e. Ficha de candidato:** posiciones, fechas, movimiento medido, banderas de contaminación y nivel de confianza, siempre rotulado "candidato para revisión humana", nunca como descubrimiento. El objetivo del reto NO es "descubrir el Planeta X", sino dar una herramienta para explorar y señalar candidatos.
   - **13f. Prueba de honestidad (opcional):** inyectar objetos simulados para medir qué tan débiles y lentos se pueden recuperar.
14. **Modo "ciencia ciudadana":** el usuario puede marcar una fuente y exportar sus coordenadas + capturas (JSON/CSV) para reportarla.
15. Mini-tour guiado de 30 s para usuarios novatos ("¿Qué estoy viendo?").

### Fase 4 — Pulido y entrega (~1.5 h)
16. Diseño visual cuidado: tema oscuro "espacio", tipografía clara, accesibilidad (contraste, teclado).
17. README claro, pasos para actualizar con nuevos datos, y lista de créditos (NASA/IPAC, SPHEREx, Gaia, astropy, Aladin Lite si se usa).
18. Despliegue público (Render/Fly/Railway/Vercel+backend) y verificación de que el enlace funciona desde otra red.

## 5. CRITERIOS DE CALIDAD

- Cada caso de prueba debe mostrar el movimiento o la variabilidad esperada. Verifica con WISE 0855 (alto movimiento propio) y con Barnard.
- Nada de datos inventados: si un dato no está disponible, la UI lo dice con claridad.
- Manejo de errores amigable (sin datos para esas coordenadas, servicio caído, timeout).
- Código modular, comentado donde la astronomía no sea obvia, con tipado y pruebas mínimas del conversor de coordenadas.
- Rendimiento: primera imagen visible en pocos segundos (carga progresiva), usando cutouts.
- Facilidad de uso: sin registro, textos simples, tutorial corto, funciona en celular.
- Accesibilidad: alto contraste, texto grande, uso por teclado.
- Transparencia: mostrar de dónde viene cada imagen (crédito NASA/JPL-Caltech/IPAC vía IRSA) y las limitaciones del método.
- Reproducibilidad: código abierto y pasos para regenerar los resultados.
- Datos precalculados: 2–3 campos de ejemplo listos para que la demo funcione aunque falle la red.
- Prioridad de entrega: un MVP que funcione con los cinco casos de prueba vale más que una detección ambiciosa a medias.

## 6. COMO TRABAJAREMOS

1. Primero confirma que entendiste el reto y haz **solo las preguntas imprescindibles** (máximo 3).
2. Lee los tutoriales de IRSA y resume en 10 líneas cómo se accederá a los datos.
3. Propón la estructura de carpetas y empieza por la Fase 1. Entrega código ejecutable, no pseudocódigo.
4. Al terminar cada fase, dime exactamente cómo ejecutarla y probarla.
5. Si una función opcional pone en riesgo la entrega, recórtala y avísame.

---

## 7. MATERIAL PARA EL JURADO (genera esto al final)

**Pitch de 60 segundos:** problema → por qué importa (Plutón se descubrió comparando dos imágenes; voluntarios han descubierto la mayoría de cometas y enanas marrones conocidas con este método) → demo en vivo con WISE 0855 → qué nos diferencia → visión a futuro.

**Guion de video de 30 s – 1 min** mostrando: ingresar coordenadas, play del "video", resta de épocas, espectro al vuelo, enlace compartible.

**Texto de descripción del proyecto** (≈150 palabras) con: nombre atractivo, problema, solución, datos usados (SPHEREx vía IRSA, Gaia DR3), tecnologías, impacto potencial (ciencia ciudadana, educación) y cómo se actualiza con nuevos datos.

**Slide/one-pager** con captura de pantalla, arquitectura simple y créditos.

**Honestidad científica:** deja claro qué es detección candidata y qué no, y qué limitaciones tiene la herramienta. Eso suma credibilidad ante el jurado.
