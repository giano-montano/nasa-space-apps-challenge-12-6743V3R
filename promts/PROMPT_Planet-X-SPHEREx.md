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
1. Formulario RA/Dec (grados y sexagesimal) + botones de los 5 objetos de prueba.
2. Descarga de cutouts SPHEREx de ese parche, ordenados por fecha.
3. **Reproductor tipo video:** play/pausa, velocidad, deslizador de frames, loop, fecha visible en cada frame.
4. Escalado visual correcto (stretch asinh/log, percentiles) para que se vean fuentes tenues.
5. Marcador fijo en el centro y retícula para ver el desplazamiento.

### Fase 2 — Diferenciadores (~3 h)
6. **Selector de FOV** (con aviso de tiempo de carga a mayor FOV).
7. **Apilado por detector** (sumar los datos de cada uno de los 6 arrays para mejorar S/N) y selector de banda/detector.
8. **Modo resta / suma de épocas:** imagen diferencia entre dos épocas para resaltar lo que se movió.
9. **Estado en la URL** (`?ra=&dec=&fov=&mode=`) y botón "Copiar enlace / Embeber".
10. **Overlay de otros telescopios:** Gaia DR3 (con vectores de movimiento propio, para contrastar el movimiento detectado con el esperado) y WISE (catálogo/imagen) como capa opcional activable.
10b. **Curva de luz para estrellas variables:** al elegir una fuente, graficar su brillo vs. tiempo (RW Aurigae y R Draconis NO se desplazan, cambian de brillo; el video solo no lo muestra bien). Marca claramente los frames usados.
10c. **Panel opcional de contexto con Aladin Lite (CDS)** para ver la misma zona en otros surveys.

### Fase 3 — Para deslumbrar (~2 h)
11. **Espectro al vuelo:** al hacer clic en una fuente, mostrar su espectro (flujo vs. longitud de onda) en un panel lateral.
12. **Panel de metadatos y banderas de contaminación** por frame.
13. **Detección asistida:** resalta automáticamente fuentes que se desplazan entre épocas (comparación simple de centroides) y las lista como "candidatas". Debe decir claramente que son candidatas, no descubrimientos confirmados.
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
- Rendimiento: primera imagen visible en pocos segundos (carga progresiva).

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
