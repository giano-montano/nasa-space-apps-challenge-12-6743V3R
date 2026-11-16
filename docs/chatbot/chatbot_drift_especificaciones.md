# Asistente de Drift: especificaciones y funcionalidades

NASA Space Apps Challenge 2026 · Reto 12 · Planeta X y SPHEREx

Estado: propuesta para después de la entrega. No forma parte de la versión que se presenta hoy.

## 1. Objetivo

Un asistente de texto que explica lo que el usuario ve en Drift y responde preguntas sobre el campo consultado, usando únicamente los datos que Drift ya calcula. No es un asistente general de astronomía.

## 2. Principio de diseño

El modelo no conoce el cielo por sí mismo. Toda afirmación debe salir de una herramienta fija que llama a un endpoint existente de Drift. Si la herramienta no devuelve el dato, el asistente responde "no lo sé con los datos actuales" y no completa la respuesta con conocimiento general.

## 3. Cómo funciona

Flujo de una pregunta:

1. El usuario escribe en la caja de texto de la interfaz (o en la pestaña "Asistente").
2. El navegador envía la pregunta y el estado actual de la vista (`ra`, `dec`, `fov`, `mode`, `det`, candidato seleccionado, fecha visible) al backend.
3. El backend arma el mensaje para el modelo, con las instrucciones del sistema y la lista de herramientas permitidas.
4. El modelo decide qué herramienta llamar, si alguna. El backend ejecuta la herramienta contra los endpoints de Drift y devuelve el resultado.
5. El modelo redacta la respuesta usando solo esos resultados y cita de qué herramienta sale cada dato.
6. El backend valida la respuesta antes de mostrarla (ver sección 6) y la envía a la interfaz.

La llamada al modelo siempre sale del backend. La clave nunca llega al navegador.

## 4. Herramientas permitidas

Solo estas, con parámetros validados por el backend:

| Herramienta | Endpoint de Drift | Para qué |
|---|---|---|
| `resolver_objeto(nombre)` | `GET /api/resolve?name=` | Convertir un nombre en coordenadas |
| `fechas_disponibles(ra, dec)` | `GET /api/epochs` | Saber en qué fechas hay imágenes del lugar |
| `prueba_sensibilidad(ra, dec, fov)` | `GET /api/injection-test` | Qué brillo y velocidad se recuperan en el campo |
| `curva_de_luz(ra, dec)` | `GET /api/lightcurve` | Cambios de brillo por color |
| `catalogo(ra, dec, fuente)` | `GET /api/catalog?source=gaia\|wise` | Qué hay catalogado en el campo |
| `candidatos(ra, dec, fov, mode)` | `GET /api/frames` (campo `candidates`) | Candidatos del campo y su confianza |
| `construir_enlace(parametros)` | Ninguno; arma la URL con `?ra=&dec=&fov=&mode=&det=` | Abrir la vista pedida |

Ninguna herramienta escribe datos, borra caché ni llama a `POST /api/refresh`. Eso queda fuera del alcance del asistente.

## 5. Funcionalidades

### 5.1 Explicar lo que se ve
- Explica un candidato o una zona de la imagen usando la ficha de `candidatos` y la vista actual.
- Ejemplo: "El par azul-naranja aparece en modo Diferencia porque el objeto cambió de posición entre dos fechas. El fondo fijo se cancela."
- Debe usar el lenguaje de la pestaña "Datos" y la especificación F-12.

### 5.2 Responder sobre sensibilidad
- Responde "¿se detectaría un asteroide lento aquí?" con los resultados de `prueba_sensibilidad`.
- Debe decir el brillo y la velocidad mínimos recuperados, y que el resultado vale solo para ese campo y esas fechas.

### 5.3 Armar la vista desde una frase
- "Muéstrame la Estrella de Barnard en diferencia con 10′" → `resolver_objeto` + `construir_enlace` → enlace que abre la vista.
- El usuario siempre ve el enlace antes de que la vista cambie.

### 5.4 Explicar datos de una curva de luz
- Describe la variación de brillo de RW Aurigae o R Draconis con los datos de `curva_de_luz`.
- No predice cambios futuros.

### 5.5 Responder sobre el proyecto
- Preguntas sobre cómo funciona Drift, qué datos usa y qué limitaciones tiene. Las respuestas salen del README y de `MATERIAL_JURADO.md`, no del conocimiento general del modelo.

## 6. Reglas de respuesta

Obligatorias. El backend las valida y, si una falla, descarta la respuesta y muestra un mensaje fijo.

1. **Sin datos, sin respuesta.** Toda cifra, fecha o nombre de objeto debe venir de una herramienta llamada en esa conversación.
2. **Sin lenguaje de descubrimiento.** Prohibido usar "descubrimos", "es un nuevo objeto" o "confirmado". Los candidatos se llaman siempre "candidatos para revisión humana".
3. **Incertidumbre visible.** Si la prueba de sensibilidad no cubre el brillo o la velocidad preguntados, debe decirlo.
4. **Idioma.** Responde en el idioma de la pregunta.
5. **Longitud.** Máximo 120 palabras por respuesta, salvo que el usuario pida más.
6. **Sin consejos médicos, legales ni financieros, y sin temas fuera de astronomía y de Drift.** Responde con una frase que redirige.
7. **Sin contenido de otras fuentes.** No cita páginas web ni libros.

## 7. Límites y controles

- **Cuota por visitante:** máximo N preguntas por hora por dirección IP, configurable.
- **Tiempo máximo por respuesta:** 15 segundos. Si se excede, se muestra "no pude responder ahora".
- **Registro:** guardar pregunta, herramientas llamadas y respuesta, sin datos personales, para revisar errores.
- **Desactivación:** variable de entorno `ASISTENTE_ACTIVO=0` para apagarlo sin tocar el código.
- **Modo sin conexión:** en `frontend/` estático, el asistente se oculta y la app sigue funcionando con `demo_data`.

## 8. Interfaz

- Pestaña o panel "Asistente", con un aviso fijo: "Asistente de IA. Responde solo con los datos de esta vista."
- Cada respuesta muestra debajo las herramientas usadas (por ejemplo: "Fuente: prueba de sensibilidad del campo").
- Botón para reportar una respuesta incorrecta.
- Textos en español e inglés, según el idioma de la interfaz.

## 9. Requisitos técnicos

- Backend: nuevo endpoint `POST /api/asistente` en FastAPI, que recibe la pregunta y el estado de la vista.
- Llamadas a herramientas: solo las de la sección 4, con validación de tipos y rangos (RA entre 0 y 360, Dec entre -90 y 90, fov entre 2 y 20).
- Modelo: el proveedor se elige por variable de entorno. La clave va en el servidor.
- Pruebas en `tests/`: un caso por herramienta y uno por cada regla de la sección 6, con respuestas simuladas del modelo.
- Documentación: añadir el endpoint a la tabla de la API del README y al campo de IA de la entrega.

## 10. Criterios de aceptación

- Ninguna respuesta de las pruebas contiene una cifra que no venga de una herramienta.
- Las preguntas fuera de alcance reciben la frase de redirección, no una respuesta general.
- Con el asistente apagado, la app funciona igual que antes.
- La cuota por visitante corta el uso antes de llegar al límite del proveedor.
- Ninguna respuesta usa lenguaje de descubrimiento.

## 11. Riesgos

- **Respuestas que suenan bien pero no tienen respaldo:** mitigado con las reglas de la sección 6 y las pruebas.
- **Costo:** mitigado con cuota por visitante y límite de tiempo.
- **Confusión entre candidato y descubrimiento:** mitigado con el vocabulario fijo y el aviso de la interfaz.
- **Dependencia de la red:** si IRSA o el proveedor no responden, el asistente debe decir que no puede responder en este momento.

## 12. Fases sugeridas

1. **Fase 1:** herramientas de solo lectura y respuestas sobre la vista actual (5.1 y 5.4).
2. **Fase 2:** sensibilidad y explicaciones del proyecto (5.2 y 5.5).
3. **Fase 3:** armar vistas desde una frase (5.3), solo si las dos anteriores pasan las pruebas.
