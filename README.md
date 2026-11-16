# Drift — SPHEREx Sky Viewer

**NASA Space Apps Challenge 2026 · challenge "Planet X and SPHEREx"**

Enter a sky position (or the name of an object) and see the **real images** from NASA's SPHEREx mission of that place, taken on different dates, as a mini video. What jumps from place to place is moving: this is how Pluto was discovered, and how volunteers have found brown dwarfs and comets.

All images come from NASA/IPAC IRSA at the time of the query. Nothing is simulated, except the sensitivity test, which is labeled as such.

---

## Quick start

Requirements: Python 3.10 or higher.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r backend/requirements.txt
python run_app.py                  # opens http://127.0.0.1:8000
```

On Windows you can also double-click `start.bat`.

**Without a server:** if you open `frontend/` as a static page (or IRSA does not respond), the 5 test cases load from `frontend/demo_data/`. This is a copy of real data that shows the date it was downloaded.

**First query for a place:** it can take between 30 s and 1 min, because it searches for the images in IRSA and reads a cutout of each one. After that it is cached and loads in under 1 s.

---

## What it does (and how it meets the challenge)

| Challenge requirement | How Drift addresses it |
|---|---|
| Public web tool | A single page, no sign-up, works on mobile. `Dockerfile` and `render.yaml` included for publishing it. |
| Enter RA/Dec | Degrees or sexagesimal (`08h55m10.8s`, `-07d14m42s`, `−07°14′42″`). Also **by name** (SIMBAD/Sesame). |
| SPHEREx images as a mini video | Player with play/pause, step-by-step, speed, keyboard, and a **timeline with the real available dates**. |
| The 5 test cases | Buttons for WISE 0855, Barnard's Star, Epsilon Indi B, RW Aurigae and R Draconis, with positions and motions taken from SIMBAD. |
| *Optional:* updatable | There are no fixed dates or files in the code: each query discovers the images in IRSA (SIA2/TAP). See below. |
| *Optional:* 102 bands and 6 detectors | You choose which detectors to stack (D1–D6 or all 6). **On-the-fly spectrum** when you click any source. |
| *Optional:* add/subtract epochs | **Blink (Parpadeo), Swipe (Deslizador), Difference (Diferencia) and Stack (Suma)** modes. |
| *Optional:* field of view | 2′, 5′, 10′ or 20′ (larger is slower, and the app warns you). |
| *Optional:* other telescopes | **Gaia DR3** layers (propagated to the date of each image, with motion arrows) and **AllWISE**. A tab with **Aladin Lite** (DSS2, 2MASS, WISE). |
| *Optional:* coordinates in the URL | `?ra=&dec=&fov=&mode=&det=` and a "Share / embed" button with an `<iframe>` code (`&embed=1`). |
| *Optional:* metadata and flags | **Data** tab: every photo used, its wavelength, release, quality control and pixels flagged by FLAGS. |
| *Optional:* Astropy / Aladin | Astropy for WCS, FITS, coordinates and times. Aladin Lite for context. |

### The science behind each image
1. **Search:** IRSA SIA2 on the `spherex_dr1` and `spherex_qr3` collections (TAP as a fallback). Duplicates between releases are removed.
2. **Light reading:** from each FITS file (2040×2040, ~70 MB) only the needed pixels are read from the public AWS bucket `nasa-irsa-spherex`, using HTTP range requests. The ~4 MB EPSF table is skipped. As a fallback, IRSA's cutout service is used.
3. **Epochs:** exposures are grouped into visits separated in time. Near the ecliptic poles, where SPHEREx observes almost daily, they are grouped into blocks of ~30 days.
4. **Band matching:** SPHEREx uses variable linear filters, so each pixel sees a different wavelength (`WCS-WAVE` table). Only exposures of equivalent color are compared between dates. If that leaves too few photos, all are used and a warning is shown.
5. **Cleaning:** the zodiacal background (`ZODI`) is subtracted and pixels flagged in `FLAGS` (hot pixels, cosmic rays, reflections…) are discarded. Each photo is then reprojected onto a common grid (6.15″/px, north up) and combined, weighted by the inverse of `VARIANCE`.
6. **Proper motion:** for fast-moving targets, the cutout is centered on their position at the mean date of the images, and their **expected track** is drawn. Barnard's Star moved ~4.5′ since J2000: without this it would fall outside the cutout.

### Assisted detection (candidates for human review)
- Detects sources on each date, links them across dates and fits a linear motion with its uncertainty.
- Flags as a candidate anything that moves ≥ 0.5 px and ≥ 5σ. Cross-matches it with Gaia DR3 on the same date: "known", "probable false motion" or "not cataloged, review".
- Lists separately the sources that appear on **only one date** (possible asteroids or artifacts).
- Each candidate and single-date source is cross-matched with **JPL Small-Body Identification** (asteroids and comets predicted for that date): "matches known body: NAME".
- **Honesty test:** injects simulated objects with different brightnesses and speeds into the real images and shows what fraction is recovered.
- Exports the candidates to JSON or CSV, and a snapshot to PNG.

### Spectrum and light curve
- **Spectrum:** aperture photometry (12″, with local background) on each exposure of a date. Each point is one photo, at the wavelength of that pixel.
- **Light curve:** each date is compared with a reference date **at the same wavelength**, per detector, and expressed as Δmag. This shows the variability of RW Aur and R Dra without the filter change faking it.

---

## New data releases (no code changes)
- Images are discovered in IRSA on each query. The search cache lasts 24 h (`CACHE_TTL_SECONDS`).
- The **"↻ Buscar datos nuevos en IRSA"** button (Search IRSA for new data) or `POST /api/refresh` clears it first.
- If IRSA publishes a new collection (e.g. `spherex_qr4`), just add it to the environment variable `SPHEREX_COLLECTIONS=spherex_dr1,spherex_qr3,spherex_qr4`. The order sets which one is preferred when an exposure appears in several.
- `python generate_demo_data.py --refresh` regenerates the offline copy of the 5 cases.

## API
| Endpoint | Purpose |
|---|---|
| `GET /api/targets` | Test cases |
| `GET /api/resolve?name=` | Name → coordinates (Sesame) |
| `GET /api/epochs?ra=&dec=` | Available dates (metadata only, fast) |
| `GET /api/frames?ra=&dec=&fov=&detectors=&match_bands=&ref=&stretch=` | Images per date, differences, stack, track and candidates |
| `GET /api/spectrum?ra=&dec=` | On-the-fly spectrum |
| `GET /api/lightcurve?ra=&dec=` | Light curve per color |
| `GET /api/catalog?source=gaia\|wise` | Gaia DR3 / AllWISE for the field |
| `GET /api/injection-test` | Sensitivity test with simulated objects |
| `POST /api/refresh` | Invalidates the cache |

Interactive documentation at `/docs`.

## Public deployment
- **Docker:** `docker build -t drift . && docker run -p 8000:8000 drift`
- **Render:** "New → Blueprint" with this repository (uses `render.yaml`, with a disk for the cache).
- After publishing, it is worth opening the 5 cases once so they are cached, and testing the link from another network.

## Tests
```bash
pip install pytest
python -m pytest tests
```
They cover the coordinate converter, proper-motion propagation, epoch grouping, band matching, detection and injection.

## Limitations (honest)
- 6.2″ pixels: only motions of ≳1″/year are visible in bright sources, and two sources less than ~10″ apart get confused. Epsilon Indi B appears as a single point.
- SPHEREx has observed each point only a few times per year since May 2025: today there are ~3 dates per place. The tool improves on its own as years go by.
- Candidates are automatic suggestions, not discoveries. The cross-match with known asteroids and comets (JPL `sb_ident`, geocentric observer) is automatic and approximate; if JPL does not respond, the candidate is marked "not cross-matched".
- The first query for a place depends on the speed of IRSA and AWS.

## AI Use (Super Intelligence)

Drift was built with the help of AI tools, following the NASA Space Apps SI policy. Where they were used:

- **Ideation or brainstorming:** [TODO: describe]
- **Research or information gathering:** [TODO: describe]
- **Data analysis and interpretation:** [TODO: describe, or "Not used"]
- **Building SI/ML into the project:** the **Copiloto** tab is a chat assistant. The server (`backend/app/chat.py`) sends the user's question, the recent conversation and the current view state to the Groq API, using the model `openai/gpt-oss-120b` by default (configurable with `GROQ_MODEL`). The key (`GROQ_API_KEY`) stays on the server. Without that key the tab is hidden. [TODO: confirm with the team]
- **Coding, debugging, or troubleshooting:** [TODO: name the tools and what they did]
- **Writing, editing, or translation:** the English translation of the code, UI, and documentation was done with AI assistance. [TODO: name the tools]
- **Visual design or image creation:** [TODO: describe, or "Not used"]
- **Presentation, video, or audio:** [TODO: describe, or "Not used"]

Commitments:
- Images and videos generated with AI carry a visible "SI-generated" watermark.
- Code and documentation generated or substantially revised with AI carry a header note. Files marked with this note: [TODO: list the files]
- No NASA logos, flags, or mission identifiers were generated with AI.

Human review: every AI output was reviewed, tested, and edited by the team. The team is responsible for all scientific claims in this project.

## Credits
- Images: **NASA/JPL-Caltech/IPAC — SPHEREx**, via the NASA/IPAC Infrared Science Archive (IRSA).
- Catalogs: **ESA Gaia DR3** (copies from IRSA, ESA and VizieR) and **NASA/JPL-Caltech WISE (AllWISE)**.
- Name resolution: **SIMBAD/Sesame** (CDS, Strasbourg). Context viewer: **Aladin Lite** (CDS).
- Software: Astropy, NumPy, SciPy, FastAPI, fsspec.

Hackathon project, not an official NASA product.
