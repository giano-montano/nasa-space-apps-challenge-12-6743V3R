# Drift — SPHEREx Sky Viewer
### NASA Space Apps Challenge 2026 — Reto "Planet X and SPHEREx"

> **Herramienta web interactiva para la detección de objetos de movimiento propio rápido y estrellas variables a partir de los mapeos infrarrojos de la misión NASA SPHEREx.**

---

## 🚀 Inicio Rápido

### Requisitos previos
- Python 3.10+ instalado.
- Dependencias (instaladas automáticamente con pip):
  ```bash
  pip install -r backend/requirements.txt
  ```

### Ejecutar la aplicación
Haz doble clic en `start.bat` (en Windows) o ejecuta en tu terminal:
```bash
python run_app.py
```
Se iniciará el servidor backend y se abrirá automáticamente en tu navegador predeterminado:
👉 **`http://127.0.0.1:8000`**

*(Nota: La aplicación también funciona en modo 100% offline simplemente abriendo `frontend/index.html` en el navegador, gracias al paquete de datos pre-computados en `frontend/demo_data/`).*

---

## 🌟 Características Implementadas (Fases 1, 2 y 3)

### 1. Reproductor Astronómico Multitemporal (Blink Viewer)
- **Modo Parpadeo (Blink):** Reproducción de los 8 mapeos semestrales de SPHEREx (mismo principio con el que Clyde Tombaugh descubrió Plutón en 1930).
- **Controles de video completos:** Play/pausa, fotograma anterior/siguiente, selector de velocidad (0.5× a 4×) y atajos de teclado (Espacio, ←, →).
- **Escalado astronómico no lineal:** Algoritmo Lupton $asinh$ y $log$ para realzar fuentes tenues y enanas marrones frías.

### 2. Modo Imagen de Diferencia ($I_k - I_0$)
- Resta fotograma a fotograma respecto a la Época 1 de referencia.
- Las estrellas estacionarias del fondo galáctico se anulan en gris neutro, mientras que cualquier objeto con movimiento propio o variabilidad de flujo resalta con contraste positivo (rosa) y negativo (cian).

### 3. Co-adición de los 6 Detectores SPHEREx (+S/N)
- SPHEREx cuenta con 6 detectores que cubren el infrarrojo cercano de 0.75 a 5.0 µm.
- El botón **"Combinar 6 detectores"** suma las señales reduciendo la desviación estándar del ruido instrumental por un factor de $\sqrt{6} \approx 2.45\times$, permitiendo distinguir enanas ultra-frías.

### 4. Espectro Infrarrojo al Vuelo (102 Bandas Espectrales)
- Gráfico interactivo que muestra el flujo espectral en las 102 bandas de SPHEREx ($R \approx 35 - 130$).
- Identificación automática de bandas moleculares críticas:
  - Metano ($CH_4$ a 1.66, 2.20 y 3.32 µm) característico de enanas Y/T frías.
  - Vapor de agua ($H_2O$ a 1.40 y 1.90 µm).
  - Monóxido de carbono ($CO$ a 2.35 y 4.67 µm).
  - Silicatos y polvo circunestelar en estrellas variables T Tauri.

### 5. Curva de Luz para Estrellas Variables
- Fotometría temporal a lo largo de las 8 épocas.
- Permite analizar las variaciones periódicas de gigantes rojas (tipo Mira como **R Draconis**) y las caídas episódicas de brillo por filamentos de polvo en **RW Aurigae**.

### 6. Capa de Catálogo Gaia DR3
- Superposición de estrellas de referencia de Gaia DR3 con vectores de velocidad angular calculados para contrastar el movimiento observado en SPHEREx con el esperado astronómicamente.

### 7. Detección Asistida & Ciencia Ciudadana
- Algoritmo de detección de candidatos en movimiento que calcula la velocidad angular neta en arcosegundos por año y su nivel de confianza.
- **Botón "Exportar reporte de descubrimiento":** Genera un informe en JSON/CSV con coordenadas ICRS, fotogramas y parámetros de desplazamiento listo para reportar a programas de ciencia ciudadana de NASA/IPAC.

### 8. Enlaces Compartibles & Embebido
- Sincronización dinámica de la URL (`?ra=...&dec=...&fov=...&mode=...&target=...`).
- Botón de un clic para copiar el enlace directo.

---

## 🎯 Verificación de los 5 Casos de Prueba Oficiales

| Objeto | Tipo | Coordenadas (RA, Dec) | Movimiento / Comportamiento |
| :--- | :--- | :--- | :--- |
| **WISE 0855** | Enana marrón Y0 ($T \approx 250\text{ K}$) | `08h55m10.83s, -07°14′42.5″` | $\mu \approx 8.1″/\text{año}$. Fuerte salto entre épocas, espectro dominado por $CH_4$ y $H_2O$. |
| **Estrella de Barnard** | Enana roja M4V | `17h57m48.50s, +04°41′36.2″` | $\mu \approx 10.3″/\text{año}$ (récord del cielo). Desplazamiento visible continuo hacia el norte. |
| **Epsilon Indi B** | Par binario T1+T6 | `22h03m21.60s, -56°47′09.5″` | $\mu \approx 4.7″/\text{año}$. Movimiento propio neto en órbita alrededor de estrella primaria. |
| **RW Aurigae** | Estrella joven T Tauri | `05h07m49.50s, +30°24′05.1″` | Posición fija. Caída dramática de brillo fotométrico por nubes de polvo circunestelar. |
| **R Draconis** | Gigante roja Mira | `16h32m40.20s, +66°45′18.2″` | Posición fija. Pulsación cíclica con periodo de 245 días visible en la curva de luz. |

---

## 📡 Acceso a Nuevos Lanzamientos de Datos (IRSA / SPHEREx)

El backend de Drift está diseñado para **no requerir cambios de código ante nuevos releases de datos**:
1. **Consultas dinámicas TAP (Table Access Protocol):**
   Las observaciones se descubren mediante consultas ADQL a las tablas de metadatos de IRSA:
   ```sql
   SELECT 'https://irsa.ipac.caltech.edu/' || a.uri || '?center=' || ra || ',' || dec || 'd&size=' || size AS uri,
          p.time_bounds_lower, p.energy_bandpassname, p.time_bounds_upper, p.provenance_version
   FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid
   WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), p.poly)
   ORDER BY p.time_bounds_lower
   ```
2. **Caché en disco con caducidad:** Las respuestas se almacenan temporalmente en `backend/app/data_cache/` con un TTL configurable (24 h).
3. **Endpoint de invalidación:** `POST /api/refresh` limpia la caché automáticamente cuando IRSA ingiere nuevos mosaicos o épocas.

---

## 🏛️ Créditos y Fuentes de Datos

- **NASA / IPAC Infrared Science Archive (IRSA):** Datos y cutouts de SPHEREx.
- **ESA Gaia DR3:** Catálogo de astrometría y movimientos propios estelares.
- **Astropy & Astroquery:** Conversión de coordenadas, WCS y consultas astronómicas.
- **CDS Strasbourg:** Aladin Lite v3 para contexto óptico e infrarrojo cruzado.

