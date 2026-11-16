# Propuesta 1: Cotejo con cuerpos conocidos del Sistema Solar

Drift · NASA Space Apps Challenge 2026 · Reto 12 · Planeta X y SPHEREx

## Qué es

Cuando Drift marca un candidato o una fuente de una sola fecha, consulta a JPL (Small-Body Database o Horizons) si ahí hay un asteroide o cometa conocido y lo etiqueta ("coincide con 2004 XY" o "sin coincidencia").

## Por qué suma

El propio README admite que hoy no se cotejan asteroides conocidos, y la especificación lo pedía en F-11. Cierra la limitación científica más visible y hace que la herramienta pase de "algo se movió" a "esto es nuevo o ya lo conocemos". Encaja con *Best Use of Science*.

## Esfuerzo y riesgo

Medio. La especificación dice que esas URLs no están en la lista oficial del reto, así que hay que verificarlas y dejar un fallback ("sin cotejar"), como ya se hace con Gaia. Es la propuesta más valiosa, pero la más riesgosa si queda poco tiempo.

## Cómo encajaría en el repo

- **Dónde se aplica:** a los candidatos que ya genera `backend/app/detection.py` y a la lista de fuentes que aparecen en una sola fecha.
- **Qué se envía:** la posición de cada candidato y la fecha de cada imagen donde aparece.
- **Qué se muestra:** una etiqueta junto a la que ya existe para Gaia ("conocido", "probable falso movimiento", "no catalogado, revisar"), con una opción nueva: "coincide con cuerpo conocido del Sistema Solar".
- **Fallback:** si el servicio de JPL no responde, el candidato dice "sin cotejar", nunca "no catalogado" (misma regla que ya se aplica con Gaia).
- **Pruebas:** añadir un caso en `tests/` con respuesta simulada del servicio, para no depender de la red.

## Antes de implementarla

- Verificar las URLs y los parámetros actuales de los servicios de JPL, porque no figuran en la lista oficial del reto.
- Probar con al menos un campo donde se sepa que hay un asteroide conocido.
- Rotular en la interfaz que el cotejo es automático y aproximado, y que el candidato sigue siendo para revisión humana.

## Cuándo conviene hacerla

Solo si alguien del equipo conoce la API de JPL y puede probarla bien: un cotejo que falla en vivo hace más daño que no tenerlo. Si no alcanza el tiempo, mencionarla como "siguiente paso" en la slide final.
