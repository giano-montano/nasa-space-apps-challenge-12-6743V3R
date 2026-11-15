# Especificación – Planeta X y SPHEREx (Reto 12)

*NASA Space Apps Challenge 2026 · Dificultad: Avanzado · Materias: Astrofísica, Planetas y lunas, Software*

Herramienta web pública donde cualquiera ingresa coordenadas del cielo (RA y Dec) y ve una serie de imágenes reales de SPHEREx como un mini video, para detectar objetos que se mueven.

**Fuentes:** enunciado oficial completo del reto (apartados *Background*, *Objectives* y *Potential Considerations*) y su pestaña *Resources*, más la documentación oficial de IRSA/IPAC. Lo marcado como **Propuesta** es diseño propio, no requisito de NASA.

## 1. Lo que piden sí o sí

Requisitos tomados del apartado *Objectives* del enunciado oficial. Lo que figura en *Potential Considerations* es opcional ("puedes, pero no estás obligado") y va después de la tabla.

| # | Requisito | Origen |
|---|---|---|
| O-1 | Herramienta web **pública** (public-facing) | Objectives |
| O-2 | Mostrar imágenes del cielo de la misión SPHEREx | Objectives |
| O-3 | Que **cualquiera** vea rápido cómo cambian esas imágenes en el tiempo | Objectives |
| O-4 | El usuario ingresa las coordenadas de un parche de cielo: ascensión recta (RA) y declinación (Dec) | Objectives |
| O-5 | Mostrar una serie de imágenes de ese parche como un pequeño video, para facilitar ver objetos que se mueven | Objectives |
| O-6 | Probar la herramienta con: Barnard's Star, Epsilon Indi B (par de enanas marrones que orbitan una estrella), WISE 0855 (enana marrón de movimiento rápido, RA 08h55m10.831s, Dec −7°14′42.53″), y las variables RW Aurigae y R Draconis | Objectives |
| O-7 | Usar datos reales de SPHEREx | Contexto del enunciado |

**Opcionales según el enunciado (Potential Considerations):**

- Diseñar la herramienta para actualizarla fácilmente con los nuevos lanzamientos de datos.
- Aprovechar las 102 bandas: por ejemplo sumar los datos de cada uno de los seis arreglos de detectores para mejorar la señal/ruido. Extra: generar espectros al vuelo.
- Permitir sumar o restar imágenes tomadas en momentos distintos.
- Dejar elegir el campo de visión: uno mayor permite seguir fuentes más rápidas, a cambio de transferencias más lentas.
- Superponer datos de otros telescopios, como Gaia o WISE.
- Aceptar coordenadas en la URL para poder incrustar la herramienta en otros sitios.
- Mostrar metadatos, como las banderas de contaminación.
- Apoyarse en herramientas públicas: Astropy para manejar datos astronómicos y Aladin (CDS, Estrasburgo) para visualizarlos.

Reglas generales del hackathon que también aplican:

- Equipos de 1 a 6 personas; no es obligatorio llegar con equipo.
- 48 horas: 14–15 de noviembre de 2026.
- Hay que registrarse en spaceappschallenge.org y elegir un evento local (o participación universal/virtual).
- Según los términos de participación, la solución debe abordar directamente el enunciado del reto para ser elegible.
- Evaluación: local → global (top 60) → ganadores globales (top 10). Los premios del taller incluyen Best Use of Data, Best Use of Technology, Best Use of Science, Galactic Impact, entre otros.

## 2. Resumen del reto

**Resumen oficial:** desde 2025, SPHEREx mapea todo el cielo cada seis meses en 102 bandas de infrarrojo cercano y devuelve imágenes de más de mil millones de objetos. Cometas, asteroides, estrellas, enanas marrones e incluso planetas nuevos se revelan al cambiar de posición entre imágenes, pero nadie puede revisar solo tanto dato. El reto es crear una herramienta web pública que muestre imágenes del cielo de SPHEREx y deje a cualquiera ver rápido cómo cambian con el tiempo.

**Contexto del enunciado:** los asteroides y cometas orbitan el Sol, las estrellas cercanas se desplazan por la galaxia y la Tierra también orbita el Sol, lo que cambia la posición aparente de los objetos cercanos. Comparar imágenes de fechas distintas sirve para descubrir objetos y medir distancias: así se descubrió Plutón. Voluntarios de proyectos como backyardworlds.org han encontrado con esta técnica la mayoría de los cometas y enanas marrones conocidos. El reto busca herramientas para que más gente pueda sumarse.

**Por qué SPHEREx:** observa de 0,75 a 5 µm, así que es muy sensible a objetos ricos en hidrógeno, agua, dióxido y monóxido de carbono y otras moléculas. Entrega datos desde mayo de 2025; IRSA los publica en lanzamientos rápidos semanales (QR2, con calibración mejorada, desde octubre de 2025). Los píxeles son de 6,2″ y los archivos son imágenes espectrales calibradas de Nivel 2.

**Por qué es avanzado:** las imágenes son archivos FITS grandes con varias extensiones, la longitud de onda cambia a lo largo del detector, y detectar movimiento real exige separarlo de artefactos.

**Honestidad científica (importante para el jurado):** el objetivo no es "descubrir el Planeta X". Es dar una herramienta para explorar y señalar candidatos que un humano debería revisar.

## 3. Fuentes de datos y páginas oficiales

### 3.1 Recursos oficiales del reto (pestaña Resources)

NASA no avala entidades fuera del Gobierno de EE. UU. ni se responsabiliza de sus sitios; en esos sitios hay que cumplir sus condiciones de uso de datos.

- [NASA/IPAC Infrared Science Archive (IRSA)](https://irsa.ipac.caltech.edu/Missions/spherex.html): recursos de SPHEREx.
- [SPHEREx Tutorial Notebooks](https://caltech-ipac.github.io/irsa-tutorials/spherex/): notebooks Jupyter de ejemplo para acceder a los datos con Python.
- [WiseView](http://byw.tools/wiseview): visor similar para datos de la misión WISE, usado por el público en cientos de descubrimientos. Sirve de modelo e inspiración.
- [Datos de la misión Gaia](https://archive.stsci.edu/missions-and-data/gaia): usar la última versión, Data Release 3 (DR3).

**Recursos de agencias socias (CSA, Canadá):**

- [NEOSSat](https://www.asc-csa.gc.ca/eng/satellites/neossat/): primer telescopio espacial dedicado a detectar y seguir asteroides, cometas, satélites y basura espacial.
- [Canadian Astronomy Data Centre (CADC)](https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/): observaciones de telescopios y misiones canadienses e internacionales.
- [Tutorial de datos NEOSSat](https://github.com/asc-csa/NEOSSAT_Tutorial): cómo visualizar datos de NEOSSat con Python.
- [Dataset NEOSSat](https://data.asc-csa.gc.ca/dataset/neossat): observaciones para detectar y seguir asteroides, cometas y objetos cercanos a la Tierra.

### 3.2 Acceso técnico a los datos de SPHEREx (IRSA / IPAC, Caltech)

| Recurso | Para qué sirve | Dónde |
|---|---|---|
| Página de la misión SPHEREx en IRSA | Punto de entrada: releases, herramientas, notebooks | irsa.ipac.caltech.edu/Missions/spherex.html |
| Guía de acceso a datos SPHEREx | APIs (SIA2, estándares IVOA), cutouts, explorador web | caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access |
| Guía de productos de datos | Qué contiene cada archivo (IMAGE, FLAGS, VARIANCE, ZODI, PSF, WCS-WAVE) | caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products |
| SPHEREx Data Explorer | Interfaz web para buscar, visualizar y descargar vía IRSA | vía IRSA |
| Cutout Tool / servicio de cutouts | Recortes espaciales de las imágenes grandes (clave para una web liviana) | irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html |
| Acceso en la nube (AWS S3) | Bucket público `nasa-irsa-spherex`, región us-east-1 | irsa.ipac.caltech.edu/cloud_access/ |
| Quick Release 2 (QR2) | Datos recalibrados, publicados semanalmente desde octubre de 2025; reemplaza a QR1 | IRSA |
| Notebooks Python de IRSA | Introducción, cutouts y PSF de imágenes espectrales | Página de misión en IRSA |

Colecciones SIA2 de IRSA: `spherex_qr` (Wide Survey), `spherex_qr_deep` (Deep Survey) y `spherex_qr_cal` (calibración).

### 3.3 Datos de apoyo para contrastar y superponer

- **Gaia DR3 (oficial):** posiciones y movimientos propios para distinguir fuentes fijas de móviles y superponerlas en las imágenes.
- **WISE:** WiseView sirve de modelo; los datos de WISE también están en IRSA para superponerlos.
- **Astropy y Aladin (CDS):** herramientas públicas que el enunciado sugiere para manejar y mostrar datos astronómicos.
- **Servicios de cuerpos menores de JPL:** no figuran en la lista oficial del reto. Son útiles para comprobar si un objeto es un asteroide o cometa conocido; verifica sus URLs antes de depender de ellos.

### 3.4 Fuentes del taller (PDF "De la idea al pitch")

NASA, NASA Earthdata, NASA APIs, NASA Worldview, NASA Open Data, Landsat y Sentinel. Para este reto la fuente natural es IRSA, no Earthdata (que es mayormente de la Tierra).

## 4. Especificaciones

### 4.1 Problema (qué, a quién, dónde, por qué importa)

- **Qué está mal:** los datos de SPHEREx son públicos pero llegan como archivos FITS pesados y técnicos; ver cómo cambia un punto del cielo exige programar o dominar herramientas de astronomía.
- **A quién afecta:** estudiantes, aficionados a la astronomía, docentes, ciencia ciudadana y científicos que quieren una revisión visual rápida.
- **Dónde y cuándo:** en la web, con datos que se actualizan semanalmente; el cielo se re-observa cada pocos meses.
- **Por qué importa:** los objetos que se mueven (cuerpos lejanos del Sistema Solar, asteroides, cometas) solo se descubren comparando imágenes de épocas distintas. Si solo especialistas pueden hacerlo, se pierde potencial de descubrimiento y de educación.

### 4.2 Idea

Una web pública donde cualquiera escribe una posición del cielo y ve imágenes reales de SPHEREx de ese lugar tomadas en fechas distintas, como una animación corta ("blink"), con ayudas para notar qué se movió.

### 4.3 Solución: funcionalidades

**Núcleo (obligatorio, ver sección 1):**

- **F-01 Entrada por coordenadas (obligatorio):** campos RA y Dec del parche de cielo. Propuesta: aceptar también el nombre de un objeto conocido.
- **F-02 Imágenes reales:** consulta a IRSA y descarga de recortes (cutouts) pequeños, no de archivos completos.
- **F-03 Visor tipo mini video (obligatorio):** reproducción de la serie de imágenes con pausa, paso a paso y velocidad.
- **F-04 Modos de comparación:** blink, deslizador (swipe) y diferencia; opcional: sumar o restar imágenes de épocas distintas.
- **F-05 Campo de visión elegible:** más grande para seguir fuentes rápidas, avisando que tarda más en cargar.
- **F-06 Línea de tiempo:** mostrar qué fechas existen para ese punto y permitir elegir.
- **F-07 Facilidad de uso:** sin registro, textos simples, tutorial corto, funciona en celular.

**Detección de movimiento (propuesta, nivel avanzado):**

- **F-08 Emparejamiento de banda:** comparar solo imágenes con longitud de onda equivalente en esa zona del detector. SPHEREx usa filtros variables lineales, así que comparar bandas distintas genera falsos movimientos.
- **F-09 Resta de fondo y máscaras:** usar las extensiones de fondo zodiacal y de banderas (FLAGS) que trae cada archivo.
- **F-10 Candidatos:** marcar fuentes que cambian de posición entre épocas, con puntuación de calidad.
- **F-11 Cotejo con otros datos:** descartar estrellas y objetos ya catalogados con Gaia DR3 y objetos conocidos del Sistema Solar.
- **F-12 Ficha de candidato:** posiciones, fechas, movimiento medido, banderas de contaminación y nivel de confianza, siempre como "candidato para revisión humana".

**Extras (propuesta):**

- Espectros al vuelo al hacer clic sobre una fuente (el enunciado da "extra kudos").
- Suma de datos por cada uno de los seis arreglos de detectores para mejorar la señal/ruido.
- Superposición de Gaia DR3 y WISE.
- Coordenadas en la URL para compartir e incrustar la vista.
- Casos de prueba precargados: Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae y R Draconis.
- Prueba de honestidad: inyectar objetos simulados para medir qué tan débiles y lentos se pueden recuperar.

### 4.4 Requisitos no funcionales (propuesta)

- **Actualizable:** consultar IRSA de forma dinámica para incorporar cada nuevo lanzamiento sin reescribir la herramienta (el enunciado destaca que llegan datos nuevos rápido).
- **Rendimiento:** respuesta en segundos usando cutouts; caché de los campos de ejemplo.
- **Accesibilidad:** alto contraste, texto grande, uso por teclado.
- **Transparencia:** mostrar de dónde viene cada imagen (crédito NASA/JPL-Caltech/IPAC vía IRSA) y las limitaciones del método.
- **Reproducibilidad:** código abierto y pasos para regenerar los resultados.

### 4.5 Arquitectura sugerida (propuesta)

1. **Frontend web:** visor de imágenes (canvas/WebGL), buscador, línea de tiempo.
2. **Backend o función serverless:** recibe la posición, consulta IRSA (SIA2 / cutouts), convierte FITS a imágenes web.
3. **Pipeline de detección (opcional):** alineación, resta, detección de fuentes, enlace entre épocas, cotejo con catálogos.
4. **Datos precalculados:** 2–3 campos de ejemplo listos para que la demo funcione aunque falle la red.

### 4.6 Plan para 48 horas (propuesta)

- **MVP (primeras ~20 h):** F-01 a F-07, probado con los cinco objetos obligatorios (Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae, R Draconis).
- **Siguiente (~15 h):** F-08 a F-12, espectros al vuelo y superposición de Gaia DR3.
- **Cierre (~10 h):** pulir interfaz, probar en celular, grabar demo, preparar el pitch.
- **Prioridad:** un MVP que funcione con los cinco casos de prueba vale más que una detección ambiciosa a medias.

### 4.7 Pitch (ruta del taller)

Estructura sugerida de 3–5 minutos:

1. **Problema:** los datos de SPHEREx existen pero casi nadie puede mirarlos.
2. **A quién afecta y por qué importa:** educación y descubrimiento de objetos móviles.
3. **Solución en vivo:** escribir una coordenada y ver el blink en segundos.
4. **Datos y ciencia:** SPHEREx vía IRSA, emparejamiento de banda, límites honestos.
5. **Impacto y siguientes pasos:** ciencia ciudadana, uso en aulas.

Premios que encajan: *Best Use of Data* (hacer accesibles los datos espaciales), *Best Use of Technology*, *Best Use of Science* y *Galactic Impact*.
