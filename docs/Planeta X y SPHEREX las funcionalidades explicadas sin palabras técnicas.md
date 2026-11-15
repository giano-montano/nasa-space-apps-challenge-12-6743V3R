# Planeta X y SPHEREx: las funcionalidades explicadas sin palabras técnicas

Una idea que se usa varias veces: **las imágenes de SPHEREx son como un álbum gigante de fotos del cielo, tomadas en fechas distintas.** Si algo cambia de lugar entre una foto y otra, es porque se movió.

## Palabras que aparecen mucho

- **Coordenadas (RA y Dec):** la "dirección" de un punto del cielo, como la latitud y la longitud en un mapa. RA es el "de lado a lado" y Dec es el "de arriba a abajo".
- **IRSA:** la biblioteca de NASA donde están guardadas las fotos de SPHEREx.
- **API:** una ventanilla de atención. Un programa se acerca y dice "dame las fotos de este punto del cielo", y la biblioteca se las entrega. No se entra a buscar nada; se pide por la ventanilla.
- **Recorte (cutout):** en vez de pedir la foto entera, que es enorme y pesada, se pide solo el pedacito que interesa. Así carga rápido.

## Funcionalidades del núcleo (F-01 a F-07)

**F-01 Entrada por coordenadas.** Es una casilla donde la persona escribe la "dirección" del cielo que quiere mirar, como escribir una dirección en un mapa. Opcionalmente, también podría escribir el nombre de algo conocido, como "Barnard's Star", y la herramienta busca la dirección sola.

**F-02 Imágenes reales.** La herramienta va a la biblioteca de NASA (usando su ventanilla) y trae los recortes de las fotos de ese lugar. "Reales" quiere decir que no son dibujos: son fotos tomadas por el telescopio.

**F-03 Visor tipo mini video.** Pasa las fotos una tras otra, como un videito. Debe tener pausa, paso a paso y velocidad. Si algo se mueve entre foto y foto, el ojo lo nota enseguida, como en los dibujos animados de libretas que se hojean rápido.

**F-04 Modos de comparación.** Hay tres maneras de comparar dos fotos:

- **Blink:** cambia rápido entre una y otra. Lo que parpadea o salta es lo que se movió.
- **Deslizador (swipe):** una barra que se arrastra. A un lado se ve la foto vieja y al otro la nueva.
- **Diferencia:** la computadora resta una foto de la otra y solo deja lo que cambió.

**F-05 Campo de visión elegible.** Es qué tan grande es el pedazo de cielo que se ve, como acercar o alejar el zoom. Con un pedazo grande se pueden seguir cosas que se mueven muy rápido (no se salen de la foto), pero tarda más en cargar. Con uno chico carga rápido, pero lo veloz se sale de la foto.

**F-06 Línea de tiempo.** Una barrita que muestra en qué fechas el telescopio sacó fotos de ese lugar. Así se eligen qué fechas comparar.

**F-07 Facilidad de uso.** Que no pida crear cuenta, que use palabras simples, que tenga un tutorial cortito y que funcione bien en el celular. Es la parte que hace que cualquiera la pueda usar, que es justo lo que pide el reto.

## Detección de movimiento (F-08 a F-12)

Estas son propuestas, no requisitos del reto. Hacen que la herramienta no solo muestre fotos, sino que ayude a encontrar lo que se mueve.

**F-08 Emparejamiento de banda.** El telescopio no saca fotos "normales". Saca la misma zona en 102 "colores" distintos de luz infrarroja, y cada color se llama banda. Esos colores no se ven con los ojos, pero se comportan como colores. Si se compara una foto en un color con otra en otro color, la misma estrella se ve distinta (más brillante o más tenue) y parecería que cambió, aunque no cambió nada. Por eso hay que comparar solo fotos del mismo color. Es como no comparar una foto con filtro rojo y otra con filtro azul.

**F-09 Resta de fondo y máscaras.** Cada foto trae un "velito de neblina" de luz que viene del polvo de nuestro Sistema Solar (se llama fondo zodiacal), y a veces trae píxeles malos (puntitos dañados). La herramienta quita la neblina para ver mejor y tapa los puntos malos, con ayuda de las etiquetas que el propio archivo ya trae (FLAGS, que quiere decir "banderitas de aviso").

**F-10 Candidatos.** La herramienta marca los puntitos que parecen haberse movido y les pone una nota de qué tan seguros estamos, como "seguro", "dudoso" o "probablemente basura". Se llaman candidatos porque todavía no son descubrimientos.

**F-11 Cotejo con otros datos.** Es "preguntar si ya lo conocemos". Hay listas enormes de estrellas y objetos ya descubiertos (por ejemplo la de Gaia, que es un mapa de estrellas con su posición y cómo se mueven). Si el puntito que se movió ya está en esas listas, no es novedad y se descarta. Si no está, es más interesante.

**F-12 Ficha de candidato.** Una tarjetita para cada candidato con dónde estaba, en qué fechas, cuánto se movió, advertencias de las banderitas y qué tan seguros estamos. Siempre dice "para que una persona lo revise", porque la herramienta ayuda, pero no decide sola.

## Extras

**Espectros al hacer clic:** al tocar una estrella, la herramienta dibuja una gráfica de cuánta luz tiene en cada uno de los 102 colores. Es como la "huella digital de colores" del objeto y dice de qué está hecho. El reto da "extra kudos" (puntos extra) por esto.

**Suma por los seis detectores:** el telescopio tiene seis "ojos" (detectores). Sumar sus fotos junta más luz y la imagen sale menos granulosa, como cuando se sacan fotos de noche y se juntan varias para que se vean mejor.

**Superponer Gaia y WISE:** poner encima de las fotos los puntitos de otros mapas, como una hoja transparente con marcas.

**Coordenadas en la URL:** la URL es la dirección de la página web. Si las coordenadas van escritas ahí, se puede mandar a alguien un enlace que ya abre justo ese lugar del cielo, o pegar la herramienta dentro de otra página.

**Casos de prueba precargados:** los cinco objetos que el reto exige probar (Barnard's Star, Epsilon Indi B, WISE 0855, RW Aurigae y R Draconis) ya listos para elegirlos con un clic.

**Prueba de honestidad:** meter a propósito objetos falsos inventados para ver cuántos encuentra la herramienta. Si no encuentra los débiles y lentos, sabemos hasta dónde llega y lo decimos con sinceridad.

## 4.4 Requisitos no funcionales

"No funcionales" quiere decir que no son botones ni pantallas, sino cómo debe portarse la herramienta.

- **Actualizable:** SPHEREx saca fotos nuevas todo el tiempo. La herramienta debe pedir las fotos a la biblioteca cada vez, en lugar de guardar una copia vieja, para que siempre muestre lo más nuevo sin tener que rehacerla.
- **Rendimiento:** que responda en pocos segundos. Se logra pidiendo recortes (no fotos enteras) y guardando en un lugar rápido (caché, un "cajón a la mano") los lugares de ejemplo, para no pedirlos de nuevo cada vez.
- **Accesibilidad:** que la pueda usar también quien ve con dificultad o no puede usar el mouse: colores con mucho contraste, letras grandes y manejo con el teclado.
- **Transparencia:** decir siempre de dónde viene cada foto (el crédito a NASA/JPL-Caltech/IPAC) y explicar qué cosas la herramienta no puede hacer bien.
- **Reproducibilidad:** que el código sea abierto (cualquiera puede leerlo) y que haya instrucciones para que otra persona consiga los mismos resultados. En ciencia, si otro no puede repetirlo, no cuenta.

## 4.5 Arquitectura sugerida

Imagina un restaurante.

1. **Frontend web:** es el comedor. Lo que la persona ve y toca: la casilla de coordenadas, el visor, la línea de tiempo. Se hace con un visor de imágenes (canvas y WebGL son técnicas para dibujar imágenes y animaciones fluidas en la pantalla).
2. **Backend o función serverless:** es la cocina, que la persona no ve. Recibe el pedido ("este punto del cielo"), va a la biblioteca de NASA por la ventanilla, trae los recortes y los prepara. Una parte importante es convertir los archivos FITS (el formato especial de los astrónomos, que un navegador no entiende) en imágenes comunes como las de internet. "Serverless" es una cocina que solo se enciende cuando llega un pedido, así no hay que mantener una computadora prendida todo el día.
3. **Pipeline de detección (opcional):** una cadena de montaje. Las fotos pasan por estaciones: alinear (que coincidan bien una sobre otra), restar, buscar puntitos, seguirlos entre fechas y compararlos con las listas de lo conocido. Es lo que hace F-08 a F-11.
4. **Datos precalculados:** la tarea hecha de antemano. Dejar listos dos o tres lugares de ejemplo, ya procesados, para que la demostración funcione aunque falle el internet o se demore la biblioteca de NASA. Es como llevar un video grabado por si falla la conexión en vivo.
