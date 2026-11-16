# Drift — material para el jurado

## Pitch de 60 segundos

**Problema (10 s).** SPHEREx, de NASA, fotografía todo el cielo en 102 colores infrarrojos cada seis meses. Esos datos son públicos, pero llegan como archivos FITS de 70 MB que solo un especialista sabe abrir.

**Por qué importa (10 s).** Plutón se descubrió comparando dos fotos del mismo lugar en fechas distintas. Con esa misma técnica, voluntarios de ciencia ciudadana encontraron la mayoría de las enanas marrones y los cometas conocidos. Si solo los especialistas pueden mirar SPHEREx, se pierden descubrimientos.

**Demo en vivo (25 s).** Escribo "WISE 0855". En segundos aparecen tres fechas reales de SPHEREx (mayo 2025, octubre 2025, abril 2026) en un mini video. En modo **Diferencia**, lo fijo desaparece y queda un par azul–naranja: es la enana marrón moviéndose 8″ por año. Drift lo marca solo como candidato, sobre la trayectoria que predice SIMBAD. Un clic sobre una estrella muestra su espectro de 100 colores.

**Qué nos diferencia (10 s).**
- Datos reales al momento, sin descargar archivos completos.
- Se comparan solo colores equivalentes entre fechas.
- La detección es honesta: dice cuándo no pudo cotejar y cuánto puede detectar.

**Futuro (5 s).** Cada seis meses SPHEREx agrega una fecha más y Drift mejora solo, sin tocar el código. La idea es llevarlo a aulas y a proyectos como Backyard Worlds.

## Guion de video (≈ 60 s)

| Tiempo | Pantalla | Voz |
|---|---|---|
| 0–5 s | Portada de Drift | "Esto es Drift: mira cómo cambia el cielo con fotos reales de SPHEREx." |
| 5–15 s | Escribir `08h55m10.8s −07°14′42″` → Ver | "Escribes una posición del cielo, o un nombre…" |
| 15–25 s | Parpadeo con las tres fechas, zoom al anillo rosa | "…y ves sus fotos de distintas fechas como un video." |
| 25–35 s | Modo Diferencia: dipolo azul/naranja, candidato C1 | "Al restar fechas, lo fijo desaparece. Lo que queda se movió." |
| 35–45 s | Clic en una estrella → espectro | "Un clic y ves su huella de colores: 100 longitudes de onda." |
| 45–52 s | RW Aurigae → pestaña Brillo | "Las estrellas variables no se mueven, pero cambian de brillo." |
| 52–60 s | Compartir → enlace e iframe | "Comparte el enlace o insértalo en tu página. Hecho con datos de NASA IRSA." |

## Descripción del proyecto (≈ 150 palabras)

**Drift** es un visor web público que convierte las imágenes de la misión SPHEREx de NASA en un mini video del cielo. Cualquiera escribe una posición o un nombre y ve fotos reales de ese lugar en distintas fechas. Así puede descubrir lo que se mueve, como las enanas marrones cercanas, o lo que cambia de brillo.

Drift consulta el archivo NASA/IPAC IRSA en cada búsqueda y lee solo los píxeles necesarios desde el bucket público de AWS. Compara solo colores equivalentes, porque SPHEREx usa filtros variables. Además resta la luz zodiacal y descarta los píxeles defectuosos.

Ofrece cuatro modos de comparación, espectros al vuelo, curvas de luz y capas de Gaia DR3 y AllWISE. También marca candidatos automáticos para revisión humana y mide su propia sensibilidad con objetos simulados.

Está hecho con Python, Astropy, FastAPI y JavaScript, y es de código abierto. Se actualiza solo con cada nuevo lanzamiento de datos.

## One-pager (contenido)

- **Captura:** WISE 0855 en modo Diferencia, con el candidato C1 y la trayectoria rosa.
- **Arquitectura:** Navegador (canvas) ⇄ FastAPI ⇄ IRSA SIA2/TAP (búsqueda) + AWS S3 `nasa-irsa-spherex` (píxeles) + Gaia DR3 / AllWISE / Sesame (catálogos).
- **Resultados con datos reales (15-nov-2026):**

  | Objeto | Fechas en SPHEREx | Resultado |
  |---|---|---|
  | Estrella de Barnard | 3 (ago 2025 – ago 2026) | Candidato automático: **11,7 ± 1,0″/año** hacia el norte (real: 10,4″/año) |
  | Epsilon Indi B | 4 (abr 2025 – sep 2026) | Candidato automático: **3,6″/año** (real: 4,7″/año; el par no se separa) |
  | WISE 0855 | 3 (may 2025 – abr 2026) | Dipolo de 4–5σ en la diferencia, sobre la trayectoria esperada (se mezcla con una estrella de fondo) |
  | RW Aurigae | 3 | Cambios de brillo de hasta **0,8 mag**, distintos en cada color |
  | R Draconis | 9 bloques (cerca del polo eclíptico) | Satura el detector; curva de luz aproximada en D6 (~0,7 mag) |

- **Créditos:** NASA/JPL-Caltech/IPAC (SPHEREx, IRSA), ESA Gaia DR3, NASA WISE, CDS (SIMBAD, Aladin Lite), Astropy.

## Honestidad científica (para la sesión de preguntas)

- **Qué es y qué no es:** Drift señala candidatos para que una persona los revise. No "descubre el Planeta X".
- **Límites de resolución:** con píxeles de 6,2″ y unas 3 fechas por lugar, solo se detectan movimientos de ≳1″/año en fuentes brillantes. La prueba de inyección de la pestaña Candidatos lo cuantifica para cada campo.
- **Dipolos en la diferencia:** cuando el desplazamiento es menor que una estrella, el método exagera la velocidad. Por eso se rotula como aproximada; la dirección sí es fiable.
- **Estrellas muy brillantes:** Barnard y R Dra saturan SPHEREx. Su fotometría usa los valores que estima el pipeline y se marca como aproximada.
- **Cotejo con catálogos:** si Gaia no responde, el candidato dice "sin cotejar"; nunca "no catalogado". Los asteroides conocidos no se cotejan automáticamente.
