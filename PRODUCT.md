# Product

<!-- impeccable:product-schema 1 -->

> Hechos inferidos del README, el reto y el pedido del usuario (sin entrevista, a petición suya). Marcados [inferido] donde no están confirmados.

## Platform

web

## Users
Entusiastas científicos [inferido]: aficionados avanzados, estudiantes y ciencia ciudadana (tipo Backyard Worlds) que saben qué son RA/Dec, una enana marrón o un movimiento propio, pero no son astrónomos profesionales ni conocen SPHEREx, IRSA o sus detectores. Usan el visor en escritorio y, para mostrarlo, en celular. También lo evalúa un jurado del NASA Space Apps Challenge 2026 que lo prueba en pocos minutos.

## Product Purpose
Drift deja escribir una posición del cielo (o el nombre de un objeto) y muestra las imágenes reales de SPHEREx de ese lugar en fechas distintas, como un mini video, para que lo que se mueve salte a la vista. Reto "Planet X and SPHEREx": ayudar a encontrar objetos que se mueven o cambian. Éxito: una persona sin formación llega, en menos de un minuto, a ver algo moverse y entiende por qué importa.

## Positioning
Imágenes reales de SPHEREx servidas al vuelo desde IRSA, con detección asistida y cotejo con Gaia y con cuerpos del Sistema Solar (JPL). Nada simulado salvo la prueba de sensibilidad, que se rotula.

## Operating Context
Se abre con coordenadas o un nombre; la primera consulta de un lugar tarda 30–60 s. Resultados reproducibles por URL (`?ra=&dec=&fov=&mode=&det=`) y embebibles (`&embed=1`). Hay 5 casos de prueba del reto (WISE 0855, Barnard, Epsilon Indi B, RW Aurigae, R Draconis).

## Capabilities and Constraints
- Modos Parpadeo, Deslizador, Diferencia, Suma; campo 2′–20′; 6 detectores; espectro y curva de brillo al clic; capas Gaia/AllWISE; Aladin Lite; exportar JSON/CSV/PNG; compartir/insertar; copiloto IA; tour.
- Los candidatos son para revisión humana, nunca descubrimientos. Todo cotejo que falla se muestra como "sin cotejar".
- Interfaz en español. El modo `embed` debe seguir funcionando. No cambiar API ni lógica del backend.

## Brand Commitments
Nombre "Drift". Aviso obligatorio: no es producto oficial de NASA. Créditos NASA/JPL-Caltech/IPAC, ESA Gaia, CDS.

## Evidence on Hand
Datos reales de IRSA y copias de demostración en `frontend/demo_data/`. No hay testimonios ni cifras de uso: no inventarlos.

## Product Principles
1. La imagen es el protagonista; la interfaz se aparta.
2. Un camino claro primero (elegir lugar → ver moverse); lo avanzado queda a un clic, no desaparece.
3. Lenguaje de aficionado: explicar el término en el sitio, sin jerga de instrumento por defecto.
4. Honestidad visible: qué es real, qué es candidato, qué no se pudo cotejar.
5. Nunca bloquear la espera: la carga de 1 minuto informa y es útil.

## Accessibility & Inclusion
Contraste AA, foco visible, teclado completo, `prefers-reduced-motion`, funciona en celular.
