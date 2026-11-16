/**
 * Gráficas sobre <canvas> (sin librerías): base común + espectro + curva de luz.
 * Colores por detector SPHEREx (D1 azul → D6 rojo) con texto alternativo en la tabla.
 */

const DET_COLORS = ['#4C8DFF', '#3CC8E8', '#43D18A', '#E8C547', '#FF9A4D', '#FF5C7A'];

class BaseChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.hover = null;
    this.pad = { l: 54, r: 14, t: 16, b: 38 };
    window.addEventListener('resize', () => this.resize());
    this.canvas.addEventListener('pointermove', (e) => this._move(e));
    this.canvas.addEventListener('pointerleave', () => { this.hover = null; this.render(); });
    this.resize();
  }
  resize() {
    const r = this.canvas.getBoundingClientRect(), d = window.devicePixelRatio || 1;
    if (r.width === 0) return;
    this.canvas.width = r.width * d; this.canvas.height = r.height * d; this.render();
  }
  _frame() {
    const d = window.devicePixelRatio || 1, w = this.canvas.width / d, h = this.canvas.height / d;
    this.ctx.setTransform(d, 0, 0, d, 0, 0);
    this.ctx.clearRect(0, 0, w, h);
    return { w, h, pw: w - this.pad.l - this.pad.r, ph: h - this.pad.t - this.pad.b };
  }
  _axes(f, xr, yr, xlab, ylab, xticks, yticks, invertY = false) {
    const c = this.ctx, css = getComputedStyle(document.documentElement);
    const grid = css.getPropertyValue('--chart-grid').trim() || '#2A3042';
    const txt = css.getPropertyValue('--text-muted').trim() || '#B7BDD2';
    const X = (v) => this.pad.l + (v - xr[0]) / (xr[1] - xr[0]) * f.pw;
    const Y = (v) => invertY ? this.pad.t + (v - yr[0]) / (yr[1] - yr[0]) * f.ph : this.pad.t + f.ph - (v - yr[0]) / (yr[1] - yr[0]) * f.ph;
    c.strokeStyle = grid; c.lineWidth = 1; c.fillStyle = txt; c.font = '11px Atkinson Hyperlegible Next, sans-serif';
    c.textAlign = 'center';
    xticks.forEach((t) => { const x = X(t.v); c.beginPath(); c.moveTo(x, this.pad.t); c.lineTo(x, this.pad.t + f.ph); c.stroke(); c.fillText(t.l, x, this.pad.t + f.ph + 15); });
    c.textAlign = 'right';
    yticks.forEach((t) => { const y = Y(t.v); c.beginPath(); c.moveTo(this.pad.l, y); c.lineTo(this.pad.l + f.pw, y); c.stroke(); c.fillText(t.l, this.pad.l - 6, y + 4); });
    c.textAlign = 'center'; c.fillText(xlab, this.pad.l + f.pw / 2, f.h - 4);
    c.save(); c.translate(12, this.pad.t + f.ph / 2); c.rotate(-Math.PI / 2); c.fillText(ylab, 0, 0); c.restore();
    return { X, Y };
  }
  _empty(msg) {
    const f = this._frame(), c = this.ctx;
    c.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-faint').trim() || '#7D85A0';
    c.font = '13px Atkinson Hyperlegible Next, sans-serif'; c.textAlign = 'center';
    String(msg || '').split('\n').forEach((l, i) => c.fillText(l, f.w / 2, f.h / 2 + i * 18));
  }
  _tooltip(x, y, lines) {
    const c = this.ctx; c.font = '12px Atkinson Hyperlegible Next, sans-serif';
    const w = Math.max(...lines.map((l) => c.measureText(l).width)) + 14, h = lines.length * 16 + 8;
    const d = window.devicePixelRatio || 1, W = this.canvas.width / d;
    const bx = Math.min(x + 10, W - w - 4), by = Math.max(4, y - h - 6);
    c.fillStyle = 'rgba(10,13,20,.92)'; c.fillRect(bx, by, w, h); c.strokeStyle = '#3A4260'; c.strokeRect(bx, by, w, h);
    c.fillStyle = '#E9EAF2'; c.textAlign = 'left'; lines.forEach((l, i) => c.fillText(l, bx + 7, by + 18 + i * 16));
  }
  _nice(lo, hi, n = 5) {
    const span = hi - lo || 1, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= n) || 10 * mag;
    const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toPrecision(6)); return out;
  }
}

/** Bandas de referencia: dónde ESPERARÍAMOS absorciones típicas (no son detecciones). */
const REFERENCE_BANDS = [
  { w: 1.4, l: 'H₂O' }, { w: 1.9, l: 'H₂O' }, { w: 2.3, l: 'CO' }, { w: 2.7, l: 'H₂O' },
  { w: 3.05, l: 'hielo H₂O' }, { w: 3.3, l: 'CH₄' }, { w: 4.27, l: 'CO₂' }, { w: 4.67, l: 'CO' },
];

class SpectrumChart extends BaseChart {
  setData(d) { this.data = d; this.model = null; this.render(); }
  setMessage(m) { this.data = null; this.model = null; this.msg = m; this.render(); }
  setModel(curve, bg, label) { this.model = curve ? { curve, bg, label } : null; this.render(); }
  _move(e) {
    if (!this.data || !this.data.points || !this._pos) return;
    const r = this.canvas.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    let best = null, bd = 18;
    this._pos.forEach((p) => { const d = Math.hypot(p.x - x, p.y - y); if (d < bd) { bd = d; best = p; } });
    this.hover = best; this.render();
  }
  render() {
    if (!this.ctx) return;
    const d = this.data;
    if (!d || !d.points || !d.points.length) return this._empty(this.msg || (d && d.message) || 'Haz clic en una fuente de la imagen\npara medir su espectro.');
    const f = this._frame(), pts = d.points;
    const ys = pts.map((p) => p.flux_mjy), es = pts.map((p) => p.err_mjy);
    let lo = Math.min(...ys.map((y, i) => y - es[i])), hi = Math.max(...ys.map((y, i) => y + es[i]));
    const padY = (hi - lo) * 0.08 || 1; lo -= padY; hi += padY;
    const xr = [0.7, 5.1];
    const xt = [0.75, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5].map((v) => ({ v, l: String(v) }));
    const yt = this._nice(lo, hi).map((v) => ({ v, l: Math.abs(v) >= 100 ? v.toFixed(0) : v.toPrecision(3) }));
    const { X, Y } = this._axes(f, xr, [lo, hi], 'Longitud de onda (µm)', 'Flujo (mJy)', xt, yt);
    const c = this.ctx;
    if (this.showBands !== false) {
      c.save(); c.setLineDash([2, 4]); c.strokeStyle = 'rgba(183,189,210,.35)'; c.fillStyle = 'rgba(183,189,210,.6)'; c.font = '10px sans-serif'; c.textAlign = 'center';
      REFERENCE_BANDS.forEach((b) => { const x = X(b.w); c.beginPath(); c.moveTo(x, this.pad.t); c.lineTo(x, this.pad.t + f.ph); c.stroke(); c.fillText(b.l, x, this.pad.t + 9); });
      c.restore();
    }
    if (lo < 0 && hi > 0) { c.strokeStyle = 'rgba(255,255,255,.35)'; c.beginPath(); c.moveTo(this.pad.l, Y(0)); c.lineTo(this.pad.l + f.pw, Y(0)); c.stroke(); }
    if (this.model) {
      const clampY = (v) => Y(Math.min(Math.max(v, lo), hi));
      const line = (cv, col, dash) => { c.save(); c.strokeStyle = col; c.lineWidth = 2; c.setLineDash(dash); c.beginPath(); cv.forEach(([x, y], i) => { const px = X(x), py = clampY(y); i ? c.lineTo(px, py) : c.moveTo(px, py); }); c.stroke(); c.restore(); };
      if (this.model.bg) line(this.model.bg, 'rgba(183,189,210,.55)', [3, 4]);
      line(this.model.curve, 'rgba(255,92,147,.85)', []);
      c.save(); c.fillStyle = 'rgba(255,106,61,.95)'; c.font = '11px Atkinson Hyperlegible Next, sans-serif'; c.textAlign = 'right';
      c.fillText(this.model.label + (this.model.bg ? ' · gris: estrella de fondo' : ''), this.pad.l + f.pw - 4, this.pad.t + f.ph - 6); c.restore();
    }
    this._pos = [];
    pts.forEach((p) => {
      const x = X(p.wavelength_um), y = Y(p.flux_mjy), col = DET_COLORS[(p.detector || 1) - 1];
      c.strokeStyle = col; c.globalAlpha = 0.6; c.beginPath(); c.moveTo(x, Y(p.flux_mjy - p.err_mjy)); c.lineTo(x, Y(p.flux_mjy + p.err_mjy)); c.stroke();
      c.globalAlpha = p.flags && p.flags.length ? 0.45 : 1; c.fillStyle = col; c.beginPath(); c.arc(x, y, 3, 0, Math.PI * 2); c.fill(); c.globalAlpha = 1;
      this._pos.push({ x, y, p });
    });
    if (this.hover) {
      const p = this.hover.p;
      this._tooltip(this.hover.x, this.hover.y, [`λ = ${p.wavelength_um.toFixed(3)} µm (D${p.detector})`, `${p.flux_mjy.toFixed(3)} ± ${p.err_mjy.toFixed(3)} mJy`, `${p.date}${p.flags && p.flags.length ? ' · ' + p.flags.join(', ') : ''}`]);
    }
  }
}

class LightcurveChart extends BaseChart {
  setData(d) { this.data = d; this.render(); }
  setMessage(m) { this.data = null; this.msg = m; this.render(); }
  setActiveMjd(mjd) { this.activeMjd = mjd; this.render(); }
  _move(e) {
    if (!this._pos) return;
    const r = this.canvas.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    let best = null, bd = 18; this._pos.forEach((p) => { const d = Math.hypot(p.x - x, p.y - y); if (d < bd) { bd = d; best = p; } });
    this.hover = best; this.render();
  }
  render() {
    if (!this.ctx) return;
    const d = this.data;
    if (!d || !d.points || !d.points.length) return this._empty(this.msg || (d && d.message) || 'Sin curva de luz todavía.');
    const f = this._frame(), pts = d.points, c = this.ctx;
    const mj = pts.map((p) => p.mjd); let x0 = Math.min(...mj) - 20, x1 = Math.max(...mj) + 20;
    let lo = Math.min(...pts.map((p) => p.delta_mag - p.err_mag)), hi = Math.max(...pts.map((p) => p.delta_mag + p.err_mag));
    const pad = Math.max((hi - lo) * 0.15, 0.05); lo -= pad; hi += pad;
    const toDate = (m) => { const dt = new Date((m - 40587) * 86400000); return dt.toISOString().slice(0, 7); };
    const xt = this._nice(x0, x1, 4).map((v) => ({ v, l: toDate(v) }));
    const yt = this._nice(lo, hi, 5).map((v) => ({ v, l: (v > 0 ? '+' : '') + v.toFixed(2) }));
    const { X, Y } = this._axes(f, [x0, x1], [lo, hi], 'Fecha', 'Δ magnitud (arriba = más brillante)', xt, yt, true);
    c.strokeStyle = 'rgba(255,255,255,.35)'; c.beginPath(); c.moveTo(this.pad.l, Y(0)); c.lineTo(this.pad.l + f.pw, Y(0)); c.stroke();
    if (this.activeMjd) { c.strokeStyle = 'rgba(255,92,147,.6)'; c.setLineDash([4, 4]); c.beginPath(); c.moveTo(X(this.activeMjd), this.pad.t); c.lineTo(X(this.activeMjd), this.pad.t + f.ph); c.stroke(); c.setLineDash([]); }
    this._pos = [];
    for (let det = 1; det <= 6; det++) {
      const ps = pts.filter((p) => p.detector === det).sort((a, b) => a.mjd - b.mjd); if (!ps.length) continue;
      const col = DET_COLORS[det - 1], off = (det - 3.5) * 2.2;
      c.strokeStyle = col; c.globalAlpha = 0.5; c.beginPath(); ps.forEach((p, i) => { const x = X(p.mjd) + off, y = Y(p.delta_mag); i ? c.lineTo(x, y) : c.moveTo(x, y); }); c.stroke(); c.globalAlpha = 1;
      ps.forEach((p) => {
        const x = X(p.mjd) + off, y = Y(p.delta_mag);
        c.beginPath(); c.moveTo(x, Y(p.delta_mag - p.err_mag)); c.lineTo(x, Y(p.delta_mag + p.err_mag)); c.stroke();
        c.fillStyle = col; c.beginPath(); c.arc(x, y, 3.5, 0, Math.PI * 2); c.fill(); this._pos.push({ x, y, p });
      });
    }
    if (this.hover) { const p = this.hover.p; this._tooltip(this.hover.x, this.hover.y, [`${p.date} · D${p.detector}`, `Δm = ${p.delta_mag > 0 ? '+' : ''}${p.delta_mag.toFixed(3)} ± ${p.err_mag.toFixed(3)}`, `${p.n} colores comparados`]); }
  }
}
