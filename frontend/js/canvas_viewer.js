/**
 * Visor de imágenes SPHEREx sobre <canvas>.
 * - Muestra los píxeles reales sin suavizar (6,15″/px), norte arriba, este a la izquierda.
 * - Zoom (rueda / pellizco / botones), arrastre, teclado.
 * - Capas: retícula, trayectoria esperada del objetivo, Gaia DR3 y AllWISE
 *   (propagados a la fecha de la imagen), candidatos detectados.
 * - Modo deslizador (swipe) entre dos épocas.
 * - Clic sobre la imagen → evento "skyclick" con RA/Dec para pedir el espectro.
 */

class SkyCanvasViewer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.img = null;          // imagen principal (HTMLImageElement)
    this.imgB = null;         // segunda imagen (modo deslizador)
    this.swipe = null;        // posición 0..1 del divisor, o null
    this.grid = null;         // {npix, pixel_arcsec, crpix, crval:[ra,dec]}
    this.frameYear = null;
    this.track = [];
    this.currentEpoch = null;
    this.gaia = [];
    this.wise = [];
    this.candidates = [];
    this.marker = null;       // posición elegida por el usuario (grid px)
    this.layers = { reticle: true, track: true, gaia: false, wise: false, candidates: true };
    this.zoom = 1; this.panX = 0; this.panY = 0;
    this.message = 'Elige un objeto o escribe coordenadas';
    this._drag = null;
    this._imgCache = new Map();
    this.resize();
    window.addEventListener('resize', () => this.resize());
    this._bind();
  }

  // ---------------------------------------------------------------- geometría
  _fit() {
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    const n = this.grid ? this.grid.npix : 1;
    const base = Math.min(w, h) / n;
    const s = base * this.zoom;
    const ox = (w - n * s) / 2 + this.panX;
    const oy = (h - n * s) / 2 + this.panY;
    return { s, ox, oy, n, w, h };
  }

  /** píxel de la rejilla (x hacia el oeste, y hacia el norte) → canvas */
  gridToCanvas(x, y) {
    const { s, ox, oy, n } = this._fit();
    return { cx: ox + (x + 0.5) * s, cy: oy + (n - 1 - y + 0.5) * s };
  }

  canvasToGrid(cx, cy) {
    const { s, ox, oy, n } = this._fit();
    return { x: (cx - ox) / s - 0.5, y: n - 1 - ((cy - oy) / s - 0.5) };
  }

  /** proyección gnomónica (TAN) igual que la rejilla del backend */
  skyToGrid(ra, dec) {
    const g = this.grid; if (!g) return null;
    const d2r = Math.PI / 180;
    const a0 = g.crval[0] * d2r, d0 = g.crval[1] * d2r, a = ra * d2r, d = dec * d2r;
    const cosc = Math.sin(d0) * Math.sin(d) + Math.cos(d0) * Math.cos(d) * Math.cos(a - a0);
    const xi = Math.cos(d) * Math.sin(a - a0) / cosc;
    const eta = (Math.cos(d0) * Math.sin(d) - Math.sin(d0) * Math.cos(d) * Math.cos(a - a0)) / cosc;
    const scale = g.pixel_arcsec / 3600 * d2r;
    return { x: (g.crpix - 1) - xi / scale, y: (g.crpix - 1) + eta / scale };
  }

  gridToSky(x, y) {
    const g = this.grid; if (!g) return null;
    const d2r = Math.PI / 180;
    const scale = g.pixel_arcsec / 3600 * d2r;
    const xi = -(x - (g.crpix - 1)) * scale, eta = (y - (g.crpix - 1)) * scale;
    const a0 = g.crval[0] * d2r, d0 = g.crval[1] * d2r;
    const rho = Math.hypot(xi, eta), c = Math.atan(rho);
    if (rho === 0) return { ra: g.crval[0], dec: g.crval[1] };
    const dec = Math.asin(Math.cos(c) * Math.sin(d0) + eta * Math.sin(c) * Math.cos(d0) / rho);
    const ra = a0 + Math.atan2(xi * Math.sin(c), rho * Math.cos(d0) * Math.cos(c) - eta * Math.sin(d0) * Math.sin(c));
    return { ra: ((ra / d2r) % 360 + 360) % 360, dec: dec / d2r };
  }

  // ---------------------------------------------------------------- datos
  _load(uri) {
    if (this._imgCache.has(uri)) return Promise.resolve(this._imgCache.get(uri));
    return new Promise((res, rej) => {
      const im = new Image();
      im.onload = () => { this._imgCache.set(uri, im); if (this._imgCache.size > 60) this._imgCache.delete(this._imgCache.keys().next().value); res(im); };
      im.onerror = rej;
      im.src = uri;
    });
  }

  setView(grid) {
    const changed = !this.grid || !grid || this.grid.npix !== grid.npix || this.grid.crval[0] !== grid.crval[0];
    this.grid = grid;
    if (changed) this.resetView(false);
  }

  async show(uri, opts = {}) {
    this.message = null;
    this.frameYear = opts.year ?? this.frameYear;
    this.currentEpoch = opts.epoch ?? null;
    this.img = uri ? await this._load(uri) : null;
    this.imgB = opts.uriB ? await this._load(opts.uriB) : null;
    this.swipe = opts.uriB ? (this.swipe ?? 0.5) : null;
    this.render();
  }

  setMessage(msg) { this.message = msg; this.img = null; this.imgB = null; this.render(); }

  resize() {
    const r = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.max(1, Math.round(r.width * dpr));
    this.canvas.height = Math.max(1, Math.round(r.height * dpr));
    this.render();
  }

  resetView(render = true) { this.zoom = 1; this.panX = 0; this.panY = 0; if (render) this.render(); }
  zoomBy(f, cx, cy) {
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    cx = cx ?? w / 2; cy = cy ?? h / 2;
    const nz = Math.max(0.5, Math.min(12, this.zoom * f));
    // mantener fijo el punto bajo el cursor
    const k = nz / this.zoom;
    this.panX = (this.panX - (cx - w / 2)) * k + (cx - w / 2);
    this.panY = (this.panY - (cy - h / 2)) * k + (cy - h / 2);
    this.zoom = nz; this.render();
  }

  // ---------------------------------------------------------------- eventos
  _bind() {
    const c = this.canvas;
    c.addEventListener('wheel', (e) => { e.preventDefault(); const r = c.getBoundingClientRect(); this.zoomBy(e.deltaY < 0 ? 1.2 : 1 / 1.2, e.clientX - r.left, e.clientY - r.top); }, { passive: false });
    c.addEventListener('pointerdown', (e) => {
      const r = c.getBoundingClientRect(); const x = e.clientX - r.left;
      const onSwipe = this.swipe !== null && Math.abs(x - this.swipe * c.clientWidth) < 14;
      this._drag = { x: e.clientX, y: e.clientY, moved: false, swipe: onSwipe };
      c.setPointerCapture(e.pointerId);
    });
    c.addEventListener('pointermove', (e) => {
      const r = c.getBoundingClientRect();
      if (this.swipe !== null && !this._drag) c.style.cursor = Math.abs(e.clientX - r.left - this.swipe * c.clientWidth) < 14 ? 'ew-resize' : 'crosshair';
      if (!this._drag) { this._hover(e.clientX - r.left, e.clientY - r.top); return; }
      const dx = e.clientX - this._drag.x, dy = e.clientY - this._drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) this._drag.moved = true;
      if (this._drag.swipe) { this.swipe = Math.min(1, Math.max(0, (e.clientX - r.left) / c.clientWidth)); }
      else { this.panX += dx; this.panY += dy; }
      this._drag.x = e.clientX; this._drag.y = e.clientY; this.render();
    });
    c.addEventListener('pointerup', (e) => {
      const d = this._drag; this._drag = null;
      if (d && !d.moved && !d.swipe) {
        const r = c.getBoundingClientRect();
        const g = this.canvasToGrid(e.clientX - r.left, e.clientY - r.top);
        if (this.grid && g.x >= -0.5 && g.y >= -0.5 && g.x < this.grid.npix - 0.5 && g.y < this.grid.npix - 0.5) {
          this.marker = g; this.render();
          const sky = this.gridToSky(g.x, g.y);
          c.dispatchEvent(new CustomEvent('skyclick', { detail: { ...sky, x: g.x, y: g.y } }));
        }
      }
    });
    c.addEventListener('dblclick', () => this.resetView());
    c.addEventListener('pointerleave', () => { this._hoverInfo = null; this.render(); });
  }

  _hover(cx, cy) {
    if (!this.grid) return;
    const g = this.canvasToGrid(cx, cy);
    if (g.x < -0.5 || g.y < -0.5 || g.x > this.grid.npix - 0.5 || g.y > this.grid.npix - 0.5) { this._hoverInfo = null; this.render(); return; }
    const s = this.gridToSky(g.x, g.y);
    this._hoverInfo = { cx, cy, text: `RA ${s.ra.toFixed(5)}°  Dec ${s.dec >= 0 ? '+' : ''}${s.dec.toFixed(5)}°` };
    this.canvas.dispatchEvent(new CustomEvent('skyhover', { detail: s }));
    this.render();
  }

  // ---------------------------------------------------------------- dibujo
  render() {
    const ctx = this.ctx, dpr = window.devicePixelRatio || 1;
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--canvas-bg') || '#05070B';
    ctx.fillRect(0, 0, w, h);
    if (!this.img || !this.grid) {
      ctx.fillStyle = '#9AA3BD'; ctx.font = '15px Schibsted Grotesk, system-ui, sans-serif'; ctx.textAlign = 'center';
      (this.message || '').split('\n').forEach((line, i) => ctx.fillText(line, w / 2, h / 2 + i * 22));
      return;
    }
    const { s, ox, oy, n } = this._fit();
    ctx.imageSmoothingEnabled = false;
    if (this.imgB && this.swipe !== null) {
      const sx = this.swipe * w;
      ctx.save(); ctx.beginPath(); ctx.rect(0, 0, sx, h); ctx.clip(); ctx.drawImage(this.img, ox, oy, n * s, n * s); ctx.restore();
      ctx.save(); ctx.beginPath(); ctx.rect(sx, 0, w - sx, h); ctx.clip(); ctx.drawImage(this.imgB, ox, oy, n * s, n * s); ctx.restore();
    } else {
      ctx.drawImage(this.img, ox, oy, n * s, n * s);
    }
    ctx.strokeStyle = 'rgba(160,170,200,.35)'; ctx.lineWidth = 1; ctx.strokeRect(ox, oy, n * s, n * s);

    if (this.layers.gaia) this._drawCatalog(this.gaia, '#38D9F5', true);
    if (this.layers.wise) this._drawCatalog(this.wise, '#FFC75F', false);
    if (this.layers.track) this._drawTrack();
    if (this.layers.candidates) this._drawCandidates();
    if (this.layers.reticle) this._drawReticle(w, h);
    if (this.marker) { const p = this.gridToCanvas(this.marker.x, this.marker.y); this._ring(p.cx, p.cy, Math.max(8, 1.6 * s), '#FFFFFF', [4, 3]); }
    if (this.swipe !== null && this.imgB) this._drawSwipeHandle(w, h);
    this._drawScale(w, h, s); this._drawCompass(w, h);
    if (this._hoverInfo) {
      ctx.font = '12px ui-monospace, SFMono-Regular, Menlo, monospace'; ctx.textAlign = 'left';
      const t = this._hoverInfo.text, tw = ctx.measureText(t).width;
      ctx.fillStyle = 'rgba(8,10,16,.8)'; ctx.fillRect(8, h - 58, tw + 14, 22);
      ctx.fillStyle = '#E9EAF2'; ctx.fillText(t, 15, h - 43);
    }
  }

  _ring(x, y, r, color, dash = []) {
    const c = this.ctx; c.save(); c.setLineDash(dash); c.strokeStyle = color; c.lineWidth = 1.6;
    c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.stroke(); c.restore();
  }

  _drawReticle(w, h) {
    if (!this.grid) return;
    const c = this.ctx, p = this.gridToCanvas(this.grid.crpix - 1, this.grid.crpix - 1);
    const r1 = 10, r2 = 26; c.save(); c.strokeStyle = 'rgba(255,92,147,.75)'; c.lineWidth = 1.2; c.beginPath();
    c.moveTo(p.cx, p.cy - r2); c.lineTo(p.cx, p.cy - r1); c.moveTo(p.cx, p.cy + r1); c.lineTo(p.cx, p.cy + r2);
    c.moveTo(p.cx - r2, p.cy); c.lineTo(p.cx - r1, p.cy); c.moveTo(p.cx + r1, p.cy); c.lineTo(p.cx + r2, p.cy); c.stroke(); c.restore();
  }

  _drawTrack() {
    if (!this.track || this.track.length < 1) return;
    const c = this.ctx, { s } = this._fit();
    c.save(); c.setLineDash([3, 4]); c.strokeStyle = 'rgba(255,92,147,.8)'; c.lineWidth = 1.4; c.beginPath();
    this.track.forEach((t, i) => { const p = this.gridToCanvas(t.x, t.y); i ? c.lineTo(p.cx, p.cy) : c.moveTo(p.cx, p.cy); });
    c.stroke(); c.setLineDash([]);
    this.track.forEach((t) => {
      const p = this.gridToCanvas(t.x, t.y); const cur = t.epoch === this.currentEpoch;
      c.fillStyle = cur ? '#FF5C93' : 'rgba(255,92,147,.45)'; c.beginPath(); c.arc(p.cx, p.cy, cur ? 3.5 : 2.2, 0, Math.PI * 2); c.fill();
      if (cur) this._ring(p.cx, p.cy, Math.max(10, 2.2 * s), '#FF5C93');
    });
    c.restore();
  }

  _drawCatalog(list, color, withPm) {
    if (!list || !list.length) return;
    const c = this.ctx, { s } = this._fit(); const yr = this.frameYear;
    c.save(); c.strokeStyle = color; c.fillStyle = color; c.lineWidth = 1.2;
    for (const src of list) {
      let ra = src.ra, dec = src.dec;
      if (withPm && yr && (src.pmra || src.pmdec)) {
        const dt = yr - 2016.0; dec += (src.pmdec || 0) / 3.6e6 * dt; ra += (src.pmra || 0) / 3.6e6 * dt / Math.cos(src.dec * Math.PI / 180);
      }
      const g = this.skyToGrid(ra, dec); if (!g) continue;
      const p = this.gridToCanvas(g.x, g.y);
      if (p.cx < -20 || p.cy < -20 || p.cx > this.canvas.clientWidth + 20 || p.cy > this.canvas.clientHeight + 20) continue;
      const r = Math.max(4, 1.1 * s);
      if (withPm) { c.beginPath(); c.arc(p.cx, p.cy, r, 0, Math.PI * 2); c.stroke(); }
      else { c.strokeRect(p.cx - r, p.cy - r, 2 * r, 2 * r); }
      const pm = Math.hypot(src.pmra || 0, src.pmdec || 0);
      if (withPm && pm > 100) {
        // flecha = desplazamiento en 10 años
        const dt = 10, d2 = { ra: ra + (src.pmra / 3.6e6 * dt) / Math.cos(dec * Math.PI / 180), dec: dec + src.pmdec / 3.6e6 * dt };
        const g2 = this.skyToGrid(d2.ra, d2.dec), q = this.gridToCanvas(g2.x, g2.y);
        c.beginPath(); c.moveTo(p.cx, p.cy); c.lineTo(q.cx, q.cy); c.stroke();
        const ang = Math.atan2(q.cy - p.cy, q.cx - p.cx);
        c.beginPath(); c.moveTo(q.cx, q.cy); c.lineTo(q.cx - 7 * Math.cos(ang - 0.45), q.cy - 7 * Math.sin(ang - 0.45));
        c.lineTo(q.cx - 7 * Math.cos(ang + 0.45), q.cy - 7 * Math.sin(ang + 0.45)); c.closePath(); c.fill();
      }
    }
    c.restore();
  }

  _drawCandidates() {
    const c = this.ctx, { s } = this._fit();
    (this.candidates || []).forEach((cand, i) => {
      const pts = cand.positions || [];
      c.save(); c.strokeStyle = '#7CFFB2'; c.lineWidth = 1.6; c.beginPath();
      pts.forEach((p, j) => { const q = this.gridToCanvas(p.x, p.y); j ? c.lineTo(q.cx, q.cy) : c.moveTo(q.cx, q.cy); });
      c.stroke();
      if (pts.length) {
        const last = pts[pts.length - 1], q = this.gridToCanvas(last.x, last.y);
        c.strokeRect(q.cx - Math.max(9, 1.8 * s), q.cy - Math.max(9, 1.8 * s), 2 * Math.max(9, 1.8 * s), 2 * Math.max(9, 1.8 * s));
        c.fillStyle = '#7CFFB2'; c.font = 'bold 12px Schibsted Grotesk, sans-serif'; c.fillText(`C${i + 1}`, q.cx + Math.max(11, 2 * s), q.cy - 6);
      }
      c.restore();
    });
  }

  _drawSwipeHandle(w, h) {
    const c = this.ctx, x = this.swipe * w;
    c.save(); c.strokeStyle = '#FFFFFF'; c.lineWidth = 2; c.beginPath(); c.moveTo(x, 0); c.lineTo(x, h); c.stroke();
    c.fillStyle = '#FFFFFF'; c.beginPath(); c.arc(x, h / 2, 12, 0, Math.PI * 2); c.fill();
    c.fillStyle = '#111'; c.font = 'bold 12px sans-serif'; c.textAlign = 'center'; c.fillText('⇆', x, h / 2 + 4); c.restore();
  }

  _drawScale(w, h, s) {
    if (!this.grid) return;
    const pxPerArcmin = 60 / this.grid.pixel_arcsec * s;
    let arcmin = 1; if (pxPerArcmin > 260) arcmin = 0.5; if (pxPerArcmin < 50) arcmin = 5;
    const len = pxPerArcmin * arcmin, c = this.ctx, x = 16, y = h - 18;
    c.save(); c.strokeStyle = '#E9EAF2'; c.lineWidth = 2; c.beginPath(); c.moveTo(x, y); c.lineTo(x + len, y);
    c.moveTo(x, y - 4); c.lineTo(x, y + 4); c.moveTo(x + len, y - 4); c.lineTo(x + len, y + 4); c.stroke();
    c.fillStyle = '#E9EAF2'; c.font = '11px Schibsted Grotesk, sans-serif'; c.textAlign = 'left';
    c.fillText(arcmin === 0.5 ? '30″' : `${arcmin}′`, x, y - 7); c.restore();
  }

  _drawCompass(w, h) {
    const c = this.ctx, x = w - 22, y = h - 22, L = 22;
    c.save(); c.strokeStyle = '#E9EAF2'; c.fillStyle = '#E9EAF2'; c.lineWidth = 1.4; c.beginPath();
    c.moveTo(x, y); c.lineTo(x, y - L); c.moveTo(x, y); c.lineTo(x - L, y); c.stroke();
    c.font = 'bold 11px sans-serif'; c.textAlign = 'center'; c.fillText('N', x, y - L - 4); c.fillText('E', x - L - 8, y + 4); c.restore();
  }

  /** PNG del canvas actual (para exportar capturas) */
  snapshot() { return this.canvas.toDataURL('image/png'); }
}
