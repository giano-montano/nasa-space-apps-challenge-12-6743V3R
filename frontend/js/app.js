/**
 * Drift — controlador principal.
 * Todo lo que se muestra viene de la API (datos reales de IRSA) o, si no hay
 * servidor, de la copia guardada en demo_data/ (también datos reales, con fecha).
 */

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const mjdToYear = (m) => 2000 + (m - 51544.5) / 365.25;
const DET_RANGES = ['0,75–1,09', '1,10–1,62', '1,63–2,42', '2,42–3,82', '3,82–4,42', '4,42–5,00'];

const MODE_HINTS = {
  blink: 'Las fechas pasan una tras otra. Lo que salta de lugar se está moviendo.',
  swipe: 'Arrastra la barra blanca sobre la imagen para comparar la fecha A (izquierda) con la B (derecha).',
  diff: 'Se resta la fecha de referencia. Lo fijo desaparece; naranja = apareció o brilla más, azul = estaba antes.',
  sum: 'Se suman todas las fechas: se ven objetos más débiles, pero lo que se mueve queda borroso o se borra.',
};
const MODE_NAMES = { blink: 'Parpadeo', swipe: 'Deslizador', diff: 'Diferencia', sum: 'Suma' };

class App {
  constructor() {
    this.state = { target: null, ra: null, dec: null, fov: 5, mode: 'blink', detectors: null, match: true,
      stretch: 'asinh', epochs: null, ref: null, a: null, b: null };
    this.view = null; this.frameIdx = 0; this.playing = false; this.timer = null;
    this.offline = false; this.targets = []; this.demo = {};
    this.viewer = new SkyCanvasViewer('skyCanvas');
    this.spec = new SpectrumChart('spectrumCanvas');
    this.lc = new LightcurveChart('lightcurveCanvas');
    this._req = 0;
    this.init();
  }

  async init() {
    this.applyTheme();
    this.bind();
    this.renderLegend();
    await this.loadTargets();
    this.readUrl();
    if (new URLSearchParams(location.search).get('embed') === '1') document.body.classList.add('embed');
    if (this.state.ra === null && !this.state.target) this.state.target = 'wise0855';
    if (this.state.target && this.state.ra === null) {
      const t = this.targets.find((x) => x.id === this.state.target);
      if (t) { this.state.ra = t.ra; this.state.dec = t.dec; }
    }
    this.syncControls();
    this.load();
    try { if (!localStorage.getItem('drift-tour-seen') && !document.body.classList.contains('embed')) this.openTour(); } catch (e) { /* sin almacenamiento */ }
  }

  // ------------------------------------------------------------------ API
  async api(path, params, { job } = {}) {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ''));
    if (job) q.set('job', job);
    const ctrl = new AbortController(); const to = setTimeout(() => ctrl.abort(), 300000);
    try {
      const r = await fetch(`/api/${path}?${q}`, { signal: ctrl.signal });
      const ct = r.headers.get('content-type') || '';
      if (!ct.includes('json')) throw Object.assign(new Error('Sin servidor'), { offline: true });
      const data = await r.json();
      if (!r.ok) throw Object.assign(new Error(data.detail || `Error ${r.status}`), { status: r.status });
      return data;
    } catch (e) {
      if (e.name === 'AbortError') throw new Error('La consulta tardó demasiado. Prueba un recorte más chico o menos detectores.');
      if (e instanceof TypeError || e.offline) throw Object.assign(new Error('No hay conexión con el servidor.'), { offline: true });
      throw e;
    } finally { clearTimeout(to); }
  }

  pollProgress(job) {
    let stop = false;
    const tick = async () => {
      if (stop) return;
      try {
        const p = await (await fetch(`/api/progress?job=${job}`)).json();
        if (p.stage) $('loaderText').textContent = p.stage + (p.total ? ` (${p.done}/${p.total})` : '');
        $('loaderBar').style.width = p.total ? `${Math.round(100 * p.done / p.total)}%` : '8%';
      } catch (e) { /* ignorar */ }
      if (!stop) setTimeout(tick, 700);
    };
    tick();
    return () => { stop = true; };
  }

  async loadTargets() {
    try { this.targets = await this.api('targets', {}); }
    catch (e) {
      try { this.targets = await (await fetch('./demo_data/targets.json')).json(); this.offline = true; }
      catch (e2) { this.targets = []; }
    }
    const el = $('targetsList');
    el.innerHTML = this.targets.map((t) => `
      <button class="target-item" role="listitem" data-target="${esc(t.id)}" aria-pressed="false">
        <span class="target-header"><span class="target-name">${esc(t.name)}</span>
        <span class="target-badge ${t.behavior === 'variable' ? 'variable' : ''}">${t.behavior === 'variable' ? 'Cambia de brillo' : `${(Math.hypot(t.pmra, t.pmdec) / 1000).toFixed(1)}″/año`}</span></span>
        <span class="target-kind">${esc(t.kind)}</span>
      </button>`).join('');
    el.querySelectorAll('.target-item').forEach((b) => b.addEventListener('click', () => this.selectTarget(b.dataset.target)));
  }

  // ------------------------------------------------------------------ URL
  readUrl() {
    const p = new URLSearchParams(location.search), s = this.state;
    if (p.get('target')) s.target = p.get('target');
    if (p.get('ra') && p.get('dec')) {
      const c = AstronomicalCoords.parse(p.get('ra'), p.get('dec'));
      if (c.isValid) { s.ra = c.ra; s.dec = c.dec; }
    }
    if (p.get('fov')) s.fov = Math.min(30, Math.max(1, parseFloat(p.get('fov')) || 5));
    if (MODE_NAMES[p.get('mode')]) s.mode = p.get('mode');
    if (p.get('det')) s.detectors = p.get('det') === 'all' ? [1, 2, 3, 4, 5, 6] : p.get('det').split(',').map(Number).filter((d) => d >= 1 && d <= 6);
    if (p.get('match') === '0') s.match = false;
    if (p.get('stretch')) s.stretch = p.get('stretch');
    if (p.get('ref')) s.ref = parseInt(p.get('ref'), 10);
  }

  shareUrl(embed = false) {
    const s = this.state, p = new URLSearchParams();
    if (s.target) p.set('target', s.target);
    if (s.ra !== null) { p.set('ra', (+s.ra).toFixed(5)); p.set('dec', (+s.dec).toFixed(5)); }
    p.set('fov', s.fov); p.set('mode', s.mode);
    if (s.detectors) p.set('det', s.detectors.length === 6 ? 'all' : s.detectors.join(','));
    if (!s.match) p.set('match', '0');
    if (s.stretch !== 'asinh') p.set('stretch', s.stretch);
    if (s.ref !== null) p.set('ref', s.ref);
    if (embed) p.set('embed', '1');
    return `${location.origin}${location.pathname}?${p}`;
  }

  writeUrl() { history.replaceState(null, '', this.shareUrl().replace(location.origin, '')); }

  // ------------------------------------------------------------------ eventos
  bind() {
    $('searchForm').addEventListener('submit', (e) => { e.preventDefault(); this.search(); });
    document.querySelectorAll('[data-mode]').forEach((b) => b.addEventListener('click', () => this.setMode(b.dataset.mode)));
    document.querySelectorAll('.fov-btn').forEach((b) => b.addEventListener('click', () => { this.state.fov = +b.dataset.fov; this.syncControls(); this.load(); }));
    document.querySelectorAll('.det-btn').forEach((b) => b.addEventListener('click', () => {
      const d = +b.dataset.det; let cur = new Set(this.state.detectors || this.currentDetectors());
      if (cur.has(d) && cur.size > 1) cur.delete(d); else cur.add(d);
      this.state.detectors = [...cur].sort(); this.syncControls(); this.load();
    }));
    $('btnAllDets').addEventListener('click', () => { this.state.detectors = [1, 2, 3, 4, 5, 6]; this.syncControls(); this.load(); });
    $('optMatch').addEventListener('change', (e) => { this.state.match = e.target.checked; this.load(); });
    $('optStretch').addEventListener('change', (e) => { this.state.stretch = e.target.value; this.load(); });
    $('btnRefresh').addEventListener('click', () => this.load({ refresh: true }));
    $('btnPlay').addEventListener('click', () => this.togglePlay());
    $('btnPrev').addEventListener('click', () => this.step(-1));
    $('btnNext').addEventListener('click', () => this.step(1));
    $('speed').addEventListener('change', () => { if (this.playing) { this.stop(); this.play(); } });
    $('btnZoomIn').addEventListener('click', () => this.viewer.zoomBy(1.4));
    $('btnZoomOut').addEventListener('click', () => this.viewer.zoomBy(1 / 1.4));
    $('btnZoomReset').addEventListener('click', () => this.viewer.resetView());
    $('selA').addEventListener('change', (e) => { this.state.a = +e.target.value; this.state.ref = this.state.a; this.renderFrame(); });
    $('selB').addEventListener('change', (e) => { this.state.b = +e.target.value; this.renderFrame(); });
    document.querySelectorAll('[data-layer]').forEach((b) => b.addEventListener('click', () => {
      const k = b.dataset.layer; this.viewer.layers[k] = !this.viewer.layers[k];
      b.classList.toggle('active', this.viewer.layers[k]); b.setAttribute('aria-pressed', this.viewer.layers[k]);
      if ((k === 'gaia' || k === 'wise') && this.viewer.layers[k]) this.loadCatalog(k);
      this.viewer.render();
    }));
    document.querySelectorAll('.tab-btn').forEach((t) => t.addEventListener('click', () => this.openTab(t.dataset.tab)));
    this.viewer.canvas.addEventListener('skyclick', (e) => this.spectrumAt(e.detail.ra, e.detail.dec, null));
    $('btnSpecTarget').addEventListener('click', () => this.spectrumCenter());
    $('btnLightcurve').addEventListener('click', () => this.lightcurve());
    $('btnExportJson').addEventListener('click', () => this.exportReport('json'));
    $('btnExportCsv').addEventListener('click', () => this.exportReport('csv'));
    $('btnSnapshot').addEventListener('click', () => this.download(this.viewer.snapshot(), `spherex_${this.fileTag()}.png`, true));
    $('btnInjection').addEventListener('click', () => this.injection());
    $('btnShare').addEventListener('click', () => this.openShare());
    $('btnTour').addEventListener('click', () => this.openTour());
    $('btnTheme').addEventListener('click', () => this.toggleTheme());
    $('btnCopyUrl').addEventListener('click', () => this.copy($('shareUrl').value, $('btnCopyUrl')));
    $('btnCopyEmbed').addEventListener('click', () => this.copy($('embedCode').value, $('btnCopyEmbed')));
    document.querySelectorAll('dialog [data-close]').forEach((b) => b.addEventListener('click', () => b.closest('dialog').close()));
    document.querySelectorAll('#aladinSurveys [data-survey]').forEach((b) => b.addEventListener('click', () => {
      document.querySelectorAll('#aladinSurveys .seg-btn').forEach((x) => x.classList.toggle('active', x === b));
      if (this.aladin) this.aladin.setImageSurvey(b.dataset.survey);
    }));
    window.addEventListener('keydown', (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) || e.target.closest('dialog')) return;
      if (e.code === 'Space') { e.preventDefault(); this.togglePlay(); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); this.step(-1); }
      else if (e.key === 'ArrowRight') { e.preventDefault(); this.step(1); }
      else if (e.key === '+' || e.key === '=') this.viewer.zoomBy(1.3);
      else if (e.key === '-') this.viewer.zoomBy(1 / 1.3);
      else if (e.key === '0') this.viewer.resetView();
      else if (['1', '2', '3', '4'].includes(e.key)) this.setMode(['blink', 'swipe', 'diff', 'sum'][+e.key - 1]);
    });
  }

  currentDetectors() {
    if (this.state.detectors) return this.state.detectors;
    if (this.view && this.view.detectors) return this.view.detectors;
    const t = this.targets.find((x) => x.id === this.state.target);
    return t && t.detectors ? t.detectors : [1];
  }

  syncControls() {
    const s = this.state;
    document.querySelectorAll('[data-mode]').forEach((b) => { const on = b.dataset.mode === s.mode; b.classList.toggle('active', on); b.setAttribute('aria-checked', on); });
    document.querySelectorAll('.fov-btn').forEach((b) => { const on = +b.dataset.fov === s.fov; b.classList.toggle('active', on); b.setAttribute('aria-checked', on); });
    const dets = this.currentDetectors();
    document.querySelectorAll('.det-btn').forEach((b) => { const on = dets.includes(+b.dataset.det); b.classList.toggle('active', on); b.setAttribute('aria-pressed', on); });
    document.querySelectorAll('.target-item').forEach((b) => { const on = b.dataset.target === s.target; b.classList.toggle('active', on); b.setAttribute('aria-pressed', on); });
    $('optMatch').checked = s.match; $('optStretch').value = s.stretch;
    $('modeHint').textContent = MODE_HINTS[s.mode]; $('hudMode').textContent = MODE_NAMES[s.mode];
    $('fovHint').textContent = s.fov >= 10 ? `Recorte de ${s.fov}′: sigue objetos rápidos, pero tarda más en cargar.` : 'Más grande sirve para seguir objetos rápidos, pero tarda más en cargar.';
    $('compareBar').hidden = !(s.mode === 'swipe' || s.mode === 'diff');
    if (s.ra !== null) {
      const sx = AstronomicalCoords.toSexagesimal(s.ra, s.dec);
      if (document.activeElement !== $('raInput')) $('raInput').value = sx.ra.replace(/ /g, '');
      if (document.activeElement !== $('decInput')) $('decInput').value = sx.dec.replace(/ /g, '');
    }
  }

  // ------------------------------------------------------------------ búsqueda
  async search() {
    const name = $('nameInput').value.trim(), ra = $('raInput').value.trim(), dec = $('decInput').value.trim();
    this.clearNotices();
    if (name) {
      this.notice('info', `Buscando «${esc(name)}»…`);
      try {
        const r = await this.api('resolve', { name });
        this.clearNotices();
        this.notice('ok', `«${esc(name)}» → RA ${r.ra.toFixed(5)}°, Dec ${r.dec.toFixed(5)}° (${esc(r.source)})`);
        this.state.target = r.target_id || null; this.state.ra = r.ra; this.state.dec = r.dec; this.state.detectors = null;
        $('nameInput').value = '';
        this.syncControls(); this.load(); return;
      } catch (e) {
        this.clearNotices(); this.notice('error', e.offline ? 'Para buscar por nombre hace falta el servidor. Prueba con coordenadas o con los casos de prueba.' : esc(e.message)); return;
      }
    }
    const c = AstronomicalCoords.parse(ra, dec);
    if (!c.isValid) { this.notice('error', esc(c.error)); $('raInput').focus(); return; }
    this.state.target = null; this.state.ra = c.ra; this.state.dec = c.dec; this.state.detectors = this.state.detectors || null;
    this.syncControls(); this.load();
  }

  selectTarget(id) {
    const t = this.targets.find((x) => x.id === id); if (!t) return;
    this.state.target = id; this.state.ra = t.ra; this.state.dec = t.dec; this.state.detectors = null; this.state.ref = null;
    this.clearNotices(); this.syncControls(); this.load();
  }

  // ------------------------------------------------------------------ carga
  async load({ refresh = false } = {}) {
    const s = this.state, my = ++this._req;
    this.stop(); this.writeUrl(); this.clearNotices();
    const job = Math.random().toString(36).slice(2);
    this.showLoader(true);
    const stopPoll = this.offline ? () => {} : this.pollProgress(job);
    const t = this.targets.find((x) => x.id === s.target);
    $('hudTarget').textContent = t ? t.name : `RA ${(+s.ra).toFixed(3)}° Dec ${(+s.dec).toFixed(3)}°`;
    $('targetDescription').textContent = t ? t.description : 'Lugar elegido por ti.';
    let data = null;
    try {
      if (refresh && !this.offline) { await fetch('/api/refresh', { method: 'POST' }); }
      data = await this.api('frames', { ra: s.ra, dec: s.dec, target: s.target, fov: s.fov,
        detectors: s.detectors ? (s.detectors.length === 6 ? 'all' : s.detectors.join(',')) : null,
        match_bands: s.match, ref: s.ref, stretch: s.stretch, refresh: refresh || null }, { job });
      this.offline = false;
    } catch (e) {
      if (e.offline || e.status === 503) {
        data = await this.loadDemo(s.target, e);
      } else {
        this.notice('error', esc(e.message));
      }
    } finally { stopPoll(); }
    if (my !== this._req) return; // llegó otra petición después
    this.showLoader(false);
    if (!data) { this.viewer.setMessage('No se pudo cargar.\nRevisa el aviso de abajo.'); return; }
    this.applyView(data);
  }

  async loadDemo(target, err) {
    const why = err.offline ? 'No hay conexión con el servidor' : 'IRSA (NASA) no responde ahora';
    if (!target) {
      this.notice('error', `${why}. Sin servidor solo funcionan los 5 casos de prueba guardados.`);
      return null;
    }
    try {
      if (!this.demo[target]) this.demo[target] = await (await fetch(`./demo_data/${target}.json`)).json();
      const b = this.demo[target];
      if (!b.view || b.view.status !== 'ok') throw new Error('sin copia');
      this.offline = !!err.offline;
      this.notice('warn', `${why}: se muestra la copia guardada de datos reales del ${esc((b.generated_at || '').slice(0, 10))} (5′, detectores recomendados). Los cambios de opciones no aplican sin servidor.`);
      return b.view;
    } catch (e2) {
      this.notice('error', `${why} y no hay copia guardada de este objeto.`);
      return null;
    }
  }

  applyView(v) {
    this.view = v;
    if (v.status !== 'ok') {
      this.viewer.setMessage(v.message || 'Sin datos.');
      this.notice('warn', esc(v.message || 'Sin datos.'));
      $('timeline').innerHTML = ''; this.renderMeta(); return;
    }
    (v.warnings || []).forEach((w) => this.notice('warn', esc(w)));
    if (v.from_cache) this.notice('info', `Datos de IRSA guardados el ${esc((v.generated_at || '').replace('T', ' ').slice(0, 16))} UTC. «Buscar datos nuevos» vuelve a consultar.`);
    this.state.detectors = this.state.detectors || null;
    this.viewer.setView(v.grid);
    this.viewer.track = v.track || [];
    this.viewer.candidates = (v.detection && v.detection.candidates) || [];
    this.viewer.gaia = (v.gaia && v.gaia.sources) || [];
    this.viewer.wise = [];
    if (this.viewer.layers.wise) this.loadCatalog('wise');
    const eps = v.frames.map((f) => f.epoch);
    if (!eps.includes(this.state.a)) this.state.a = v.reference_epoch ?? eps[0];
    if (!eps.includes(this.state.b) || this.state.b === this.state.a) this.state.b = eps[eps.length - 1];
    this.frameIdx = 0;
    this.renderTimeline(); this.renderCompareSelects(); this.renderCandidates(); this.renderMeta(); this.renderLimitations();
    this.syncControls();
    this.renderFrame();
    if (this.state.mode === 'blink' && v.frames.length > 1) this.play();
    // análisis automáticos del objeto central (desde caché si existe)
    const t = this.targets.find((x) => x.id === this.state.target);
    this.spec.setMessage('Haz clic en una fuente de la imagen\no usa «Espectro del objeto central».');
    $('classifyBox').hidden = true;
    this.lc.setMessage(t && t.behavior === 'variable' ? 'Pulsa «Medir brillo» para ver si cambió.' : 'Pulsa «Medir brillo del objeto central».');
    if (this.offline && this.demo[this.state.target]) {
      const b = this.demo[this.state.target];
      if (b.spectrum) this.showSpectrum(b.spectrum);
      if (b.classification) this.showClassification(b.classification);
      if (b.lightcurve) this.showLightcurve(b.lightcurve);
    }
    if (this.aladin) this.aladin.gotoRaDec(v.center.ra_deg, v.center.dec_deg);
  }

  // ------------------------------------------------------------------ visor
  renderTimeline() {
    const v = this.view, el = $('timeline');
    const used = new Set(v.frames.map((f) => f.epoch));
    el.innerHTML = (v.epochs_available || []).map((e) => {
      const fi = v.frames.findIndex((f) => f.epoch === e.index);
      const label = e.date_start.slice(0, 7);
      return `<button class="frame-pill ${fi === this.frameIdx ? 'active' : ''}" ${fi < 0 ? 'disabled' : ''} data-fi="${fi}"
        aria-label="Fecha ${esc(e.date_start)}, ${e.n_images} fotos${fi < 0 ? ' (sin fotos en los detectores elegidos)' : ''}"
        title="${esc(e.date_start)} → ${esc(e.date_end)} · ${e.n_images} fotos (D${e.detectors.join(',D')})">
        <span>${label}</span><span class="frame-pill-date">${used.has(e.index) ? v.frames[fi].n_used + ' fotos' : '—'}</span></button>`;
    }).join('');
    el.querySelectorAll('.frame-pill:not([disabled])').forEach((b) => b.addEventListener('click', () => { this.stop(); this.frameIdx = +b.dataset.fi; this.renderFrame(); }));
  }

  renderCompareSelects() {
    const opts = this.view.frames.map((f) => `<option value="${f.epoch}">${esc(f.date)} (época ${f.epoch})</option>`).join('');
    $('selA').innerHTML = opts; $('selB').innerHTML = opts;
    $('selA').value = this.state.a; $('selB').value = this.state.b;
  }

  async renderFrame() {
    const v = this.view; if (!v || v.status !== 'ok') return;
    const s = this.state, n = v.frames.length;
    this.frameIdx = ((this.frameIdx % n) + n) % n;
    const f = v.frames[this.frameIdx];
    const fa = v.frames.find((x) => x.epoch === s.a) || v.frames[0];
    const fb = v.frames.find((x) => x.epoch === s.b) || v.frames[n - 1];
    let title = '', sub = '';
    if (s.mode === 'blink') {
      await this.viewer.show(f.image, { epoch: f.epoch, year: mjdToYear(f.mjd) });
      title = `Fecha ${this.frameIdx + 1} de ${n}: ${f.date}`; sub = `${f.n_used} fotos sumadas · ${f.detectors.map((d) => 'D' + d).join(' ')}`;
      this.lc.setActiveMjd(f.mjd);
    } else if (s.mode === 'swipe') {
      await this.viewer.show(fa.image, { epoch: fa.epoch, year: mjdToYear(fa.mjd), uriB: fb.image });
      title = `A: ${fa.date}  ⇆  B: ${fb.date}`; sub = 'Arrastra la barra blanca';
      $('compareHint').textContent = '';
    } else if (s.mode === 'diff') {
      // la diferencia del backend es contra reference_epoch; si el usuario eligió otra A, se recarga
      if (v.reference_epoch !== s.a) { this.state.ref = s.a; this.load(); return; }
      const d = v.diffs.find((x) => x.epoch === s.b) || v.diffs[v.diffs.length - 1];
      await this.viewer.show(d.image, { epoch: d.epoch, year: mjdToYear(fb.mjd) });
      title = `Diferencia: ${fb.date} − ${fa.date}`; sub = 'Naranja = está ahora · Azul = estaba antes';
      $('compareHint').textContent = 'A es la referencia que se resta.';
    } else {
      await this.viewer.show(v.sum.image, { epoch: null, year: mjdToYear(v.frames[0].mjd) });
      title = `Suma de ${v.sum.epochs.length} fechas`; sub = 'Más señal; lo que se mueve se borra';
    }
    $('hudTitle').textContent = title; $('hudSub').textContent = sub;
    document.querySelectorAll('#timeline .frame-pill').forEach((b) => b.classList.toggle('active', +b.dataset.fi === this.frameIdx && s.mode === 'blink'));
    this.renderFrameMeta(s.mode === 'blink' ? f : fb);
  }

  setMode(m) {
    if (!MODE_NAMES[m]) return;
    this.state.mode = m; this.stop(); this.syncControls(); this.writeUrl();
    if (this.view && this.view.status === 'ok') { this.renderFrame(); if (m === 'blink') this.play(); }
  }

  play() {
    if (!this.view || this.view.status !== 'ok' || this.view.frames.length < 2) return;
    if (this.state.mode !== 'blink') { this.setMode('blink'); return; } // setMode('blink') ya llama a play()
    this.stop(); this.playing = true; $('btnPlay').textContent = '❚❚'; $('btnPlay').setAttribute('aria-label', 'Pausar'); this.timer = setInterval(() => { this.frameIdx++; this.renderFrame(); }, +$('speed').value); }
  stop() { this.playing = false; clearInterval(this.timer); $('btnPlay').textContent = '▶'; $('btnPlay').setAttribute('aria-label', 'Reproducir'); }
  togglePlay() { this.playing ? this.stop() : this.play(); }
  step(d) { this.stop(); if (this.state.mode !== 'blink') this.setMode('blink'); this.frameIdx += d; this.renderFrame(); }

  async loadCatalog(kind) {
    if (!this.view || this.view.status !== 'ok') return;
    if (kind === 'gaia' && this.viewer.gaia.length) return;
    const c = this.view.center;
    try {
      const r = await this.api('catalog', { ra: c.ra_deg, dec: c.dec_deg, fov: this.state.fov, source: kind });
      if (kind === 'gaia') this.viewer.gaia = r.sources; else this.viewer.wise = r.sources;
      this.notice('ok', `${esc(r.catalog)}: ${r.sources.length} fuentes (${esc(r.service)}).${kind === 'gaia' ? ' Círculos en la posición de la fecha mostrada; flechas = movimiento en 10 años.' : ' Cuadrados = posición de WISE en ~2010.'}`);
      this.viewer.render();
    } catch (e) { this.notice('warn', `No se pudo cargar ${kind === 'gaia' ? 'Gaia DR3' : 'AllWISE'}: ${esc(e.message)}`); }
  }

  // ------------------------------------------------------------------ análisis
  centerPosition() {
    const v = this.view; if (!v || v.status !== 'ok') return null;
    return { ra: v.center.ra_deg, dec: v.center.dec_deg };
  }

  spectrumCenter() { const t = this.state.target, s = this.state; this.spectrumAt(s.ra, s.dec, t); }

  async spectrumAt(ra, dec, target, extra = {}) {
    this.openTab('tabSpectrum');
    $('classifyBox').hidden = true;
    if (this.offline) { $('specStatus').textContent = 'Sin servidor solo está el espectro guardado del objeto central.'; return; }
    $('specStatus').textContent = `Midiendo en RA ${ra.toFixed(4)}°, Dec ${dec.toFixed(4)}°…`;
    this.spec.setMessage('Leyendo ~100 fotos de SPHEREx (una por color)…\nla primera vez tarda hasta un minuto.');
    const job = Math.random().toString(36).slice(2);
    const poll = setInterval(async () => { try { const p = await (await fetch(`/api/progress?job=${job}`)).json(); if (p.total) $('specStatus').textContent = `${p.stage} (${p.done}/${p.total})`; } catch (e) { /* */ } }, 800);
    try {
      const r = await this.api('spectrum', { ra, dec, target }, { job });
      this.showSpectrum(r);
      if (r.status === 'ok') this.classifyAt(ra, dec, target, extra);
    } catch (e) { this.spec.setMessage(e.message); $('specStatus').textContent = ''; }
    finally { clearInterval(poll); }
  }

  async classifyAt(ra, dec, target, extra = {}) {
    const box = $('classifyBox'); box.hidden = false;
    box.innerHTML = '<p class="hint">Clasificando: catálogo SIMBAD, plantillas del espectro y contexto…</p>';
    try { this.showClassification(await this.api('classify', { ra, dec, target, pm: extra.pm })); }
    catch (e) { box.innerHTML = `<p class="hint">No se pudo clasificar: ${esc(e.message)}</p>`; }
  }

  showClassification(c) {
    const box = $('classifyBox'); if (!c) { box.hidden = true; return; }
    box.hidden = false;
    const f = c.final, sp = c.spectral || {}, L = c.labels || {};
    this.spec.setModel(sp.available ? sp.model_curve : null, sp.available ? sp.background_curve : null, sp.available ? `Plantilla: ${L[sp.top] || ''} (${sp.template})` : '');
    const bars = Object.entries(f.probabilities).sort((a, b) => b[1] - a[1]).map(([k, v]) =>
      `<div class="prob-row"><span>${esc(L[k] || k)}</span><span class="prob-bar"><i style="width:${Math.round(v * 100)}%"></i></span><span class="mono">${Math.round(v * 100)}%</span></div>`).join('');
    box.innerHTML = `
      <header><h3 class="sub">¿Qué es?</h3> <span class="pill ${f.confidence === 'alta' ? 'alta' : f.confidence === 'media' ? 'media' : 'baja'}">confianza ${esc(f.confidence)} · ${esc(f.method)}</span></header>
      <p class="cand-label">${esc(f.verdict)}</p>
      <ul class="limits">${f.reasons.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>
      <details><summary>Probabilidades por clase (espectro + contexto)</summary>${bars}</details>
      <p class="hint">${esc(c.note)}</p>`;
  }

  showSpectrum(r) {
    if (r.status !== 'ok') { this.spec.setMessage(r.message || 'Sin datos'); $('specStatus').textContent = ''; return; }
    this.spec.setData(r);
    $('specStatus').textContent = `${r.points.length} colores medidos · ${r.epoch.date_start}${r.target ? ' · ' + r.target.name : ''}${r.warning ? ' · ⚠ ' + r.warning : ''}`;
  }

  async lightcurve() {
    this.openTab('tabLightcurve');
    if (this.offline) { $('lcStatus').textContent = 'Sin servidor solo está la curva guardada.'; return; }
    const s = this.state; $('lcStatus').textContent = 'Midiendo…';
    this.lc.setMessage('Leyendo fotos de cada fecha…\nla primera vez tarda hasta un minuto.');
    const job = Math.random().toString(36).slice(2);
    const poll = setInterval(async () => { try { const p = await (await fetch(`/api/progress?job=${job}`)).json(); if (p.total) $('lcStatus').textContent = `${p.stage} (${p.done}/${p.total})`; } catch (e) { /* */ } }, 800);
    try { this.showLightcurve(await this.api('lightcurve', { ra: s.ra, dec: s.dec, target: s.target }, { job })); }
    catch (e) { this.lc.setMessage(e.message); $('lcStatus').textContent = ''; }
    finally { clearInterval(poll); }
  }

  showLightcurve(r) {
    if (r.status !== 'ok') { this.lc.setMessage(r.message || 'Sin datos'); $('lcStatus').textContent = ''; return; }
    this.lc.setData(r);
    const amp = Math.max(...r.points.map((p) => Math.abs(p.delta_mag)));
    $('lcStatus').textContent = `${r.points.length} medidas · referencia: época ${r.reference_epoch} · cambio máximo ${amp.toFixed(2)} mag${r.warning ? ' · ⚠ ' + r.warning : ''}`;
  }

  renderCandidates() {
    const v = this.view, el = $('candidatesList');
    const det = v.detection || {}; const cands = det.candidates || []; const tr = det.transients || [];
    const t = this.targets.find((x) => x.id === this.state.target);
    let html = '';
    if (!cands.length) html += `<p class="muted">No se detectaron fuentes con movimiento significativo${v.frames.length < 2 ? ' (hace falta más de una fecha)' : ''}.</p>`;
    html += cands.map((c, i) => `
      <article class="cand-card">
        <header><strong>C${i + 1}</strong> <span class="pill ${c.quality.level}">confianza ${c.quality.level}</span></header>
        <p class="cand-label">${esc(c.quality.label)}</p>
        <dl class="meta-grid small">
          <dt>Posición (1.ª fecha)</dt><dd>${c.ra_deg.toFixed(5)}°, ${c.dec_deg.toFixed(5)}°</dd>
          <dt>Movimiento</dt><dd>${c.motion_arcsec_yr} ± ${c.motion_err_arcsec_yr} ″/año (${c.significance_sigma}σ)${c.motion_note ? `<br><span class="hint-inline">${esc(c.motion_note)}</span>` : ''}</dd>
          <dt>Método</dt><dd>${esc(c.method || 'seguimiento de la fuente en cada fecha')}</dd>
          <dt>μ<sub>α*</sub>, μ<sub>δ</sub></dt><dd>${c.pmra_mas_yr}, ${c.pmdec_mas_yr} mas/año</dd>
          <dt>Fechas</dt><dd>${c.n_epochs} en ${c.span_yr} años · S/R ${c.snr}</dd>
          ${c.known_match ? `<dt>Gaia DR3</dt><dd>${esc(c.known_match.id)} a ${c.known_match.sep_arcsec}″ (μ ${c.known_match.gaia_motion_arcsec_yr}″/año)</dd>` : ''}
        </dl>
        <p class="hint">${esc(c.status)}</p>
        <button class="btn-secondary btn-small" type="button" data-classify="${i}">¿Qué es? (espectro y clasificación)</button>
      </article>`).join('');
    if (t && t.behavior === 'moving') {
      const exp = (Math.hypot(t.pmra, t.pmdec) / 1000).toFixed(2);
      html += `<p class="hint">Referencia: ${esc(t.name)} se mueve ${exp}″/año según SIMBAD (${esc(t.ref)}). Su trayectoria esperada está en rosa.</p>`;
    }
    if (tr.length) html += `<h3 class="sub">Aparecen en una sola fecha (${tr.length})</h3><ul class="limits">${tr.map((x) => `<li>Época ${x.epoch}: ${x.ra_deg.toFixed(5)}°, ${x.dec_deg.toFixed(5)}° (S/R ${x.snr}) — ${esc(x.status)}</li>`).join('')}</ul>`;
    if (det.solar_system) html += `<p class="hint">Cotejo con asteroides/cometas: ${esc(det.solar_system.service)}, automático y aproximado${det.solar_system.epochs_failed ? ` (${det.solar_system.epochs_failed} fecha(s) sin respuesta: marcadas "sin cotejar")` : ''}. Los candidatos siguen siendo para revisión humana.</p>`;
    html += `<p class="hint">Método: ${esc(det.method || '')}</p>`;
    el.innerHTML = html;
    el.querySelectorAll('[data-classify]').forEach((b) => b.addEventListener('click', () => {
      const c = cands[+b.dataset.classify];
      this.spectrumAt(c.ra_deg, c.dec_deg, null, { pm: c.motion_arcsec_yr });
    }));
  }

  renderMeta() {
    const v = this.view, el = $('viewMeta');
    if (!v || v.status !== 'ok') { el.innerHTML = v ? `<dt>Estado</dt><dd>${esc(v.message)}</dd>` : ''; return; }
    const bm = v.band_matching || {};
    el.innerHTML = `
      <dt>Centro</dt><dd>${esc(v.center.ra_sex)} ${esc(v.center.dec_sex)}${v.center.note ? `<br><span class="hint-inline">${esc(v.center.note)}</span>` : ''}</dd>
      <dt>Fotos en IRSA</dt><dd>${v.n_images_total} en ${v.epochs_available.length} fechas · servicio ${esc(v.service)}</dd>
      <dt>Recorte</dt><dd>${v.fov_arcmin}′ (${v.grid.npix}×${v.grid.npix} píxeles de ${v.grid.pixel_arcsec}″)</dd>
      <dt>Detectores</dt><dd>${v.detectors.map((d) => `D${d} (${DET_RANGES[d - 1]} µm)`).join(', ')}</dd>
      <dt>Colores</dt><dd>${bm.applied ? `emparejados: ${bm.kept} de ${bm.total} fotos (${esc(bm.level)})` : esc(bm.reason || 'sin emparejar')}</dd>`;
  }

  renderFrameMeta(f) {
    if (!f) return;
    const flags = Object.entries(f.flag_pixel_counts || {}).sort((a, b) => b[1] - a[1]);
    $('frameMeta').innerHTML = `
      <h3 class="sub">Fecha ${esc(f.date)} → ${esc(f.date_end)}</h3>
      <dl class="meta-grid small">
        <dt>Fotos sumadas</dt><dd>${f.n_used}</dd>
        <dt>Cobertura</dt><dd>${Math.round(f.coverage * 100)}% del recorte</dd>
        <dt>Control de calidad</dt><dd>${esc((f.qa || []).join(', '))}</dd>
        <dt>Banderas</dt><dd>${flags.length ? flags.map(([k, n]) => `<span class="flag">${esc(k)}: ${n} px</span>`).join(' ') : '<span class="ok">sin píxeles marcados</span>'}</dd>
      </dl>
      <p class="hint">Banderas = avisos que trae cada foto (píxel caliente, rayo cósmico, reflejo…). Esos píxeles no se usan.</p>
      <div class="table-wrap"><table class="data-table"><caption class="sr-only">Fotos usadas</caption>
        <thead><tr><th>Fecha</th><th>Det.</th><th>λ (µm)</th><th>Release</th><th>Archivo</th></tr></thead>
        <tbody>${(f.images || []).map((im) => `<tr><td>${esc((im.date || '').slice(0, 16).replace('T', ' '))}</td><td>D${im.detector}</td><td>${im.wavelength_um ?? '—'}</td><td>${esc(im.release)}</td><td class="mono">${esc(im.file)}</td></tr>`).join('')}</tbody>
      </table></div>`;
  }

  renderLimitations() {
    const v = this.view; if (!v) return;
    if (v.credits) $('creditsText').textContent = v.credits;
    $('limitationsList').innerHTML = (v.limitations || []).map((l) => `<li>${esc(l)}</li>`).join('');
  }

  renderLegend() {
    $('detLegend').innerHTML = DET_COLORS.map((c, i) => `<span><i style="background:${c}"></i>D${i + 1} ${DET_RANGES[i]} µm</span>`).join('');
  }

  async injection() {
    if (this.offline) { $('injectionResult').innerHTML = '<p class="hint">Necesita el servidor.</p>'; return; }
    const s = this.state, el = $('injectionResult'); el.innerHTML = '<p class="hint">Inyectando objetos simulados… (≈30 s)</p>';
    try {
      const r = await this.api('injection-test', { ra: s.ra, dec: s.dec, target: s.target, fov: s.fov, detectors: this.currentDetectors().join(',') });
      if (r.error) { el.innerHTML = `<p class="hint">${esc(r.error)}</p>`; return; }
      const snrs = [...new Set(r.grid.map((g) => g.peak_snr))], sp = [...new Set(r.grid.map((g) => g.speed_arcsec_yr))];
      el.innerHTML = `<div class="table-wrap"><table class="data-table"><caption>Fracción recuperada (${r.n_epochs} fechas en ${r.span_yr} años)</caption>
        <thead><tr><th>Brillo (S/R) ↓ · Velocidad →</th>${sp.map((x) => `<th>${x}″/año</th>`).join('')}</tr></thead>
        <tbody>${snrs.map((n) => `<tr><th>${n}</th>${sp.map((x) => { const g = r.grid.find((q) => q.peak_snr === n && q.speed_arcsec_yr === x); return `<td class="heat" style="--f:${g.fraction}">${Math.round(g.fraction * 100)}%</td>`; }).join('')}</tr>`).join('')}</tbody></table></div>
        <p class="hint">${esc(r.note)}</p>`;
    } catch (e) { el.innerHTML = `<p class="hint">${esc(e.message)}</p>`; }
  }

  // ------------------------------------------------------------------ exportar
  fileTag() { return (this.state.target || `${(+this.state.ra).toFixed(3)}_${(+this.state.dec).toFixed(3)}`).replace(/[^\w.-]/g, '_'); }

  exportReport(fmt) {
    const v = this.view; if (!v || v.status !== 'ok') return;
    const cands = (v.detection && v.detection.candidates) || [];
    if (fmt === 'json') {
      const rep = { tool: 'Drift — visor SPHEREx (NASA Space Apps 2026)', url: this.shareUrl(), exported_at: new Date().toISOString(),
        note: 'Candidatos automáticos para revisión humana. No son descubrimientos confirmados.',
        center: v.center, fov_arcmin: v.fov_arcmin, detectors: v.detectors, band_matching: v.band_matching,
        epochs: v.frames.map((f) => ({ epoch: f.epoch, date_start: f.date, date_end: f.date_end, images: f.images })),
        candidates: cands, transients: v.detection.transients, credits: v.credits };
      this.download(new Blob([JSON.stringify(rep, null, 2)], { type: 'application/json' }), `spherex_candidatos_${this.fileTag()}.json`);
    } else {
      const head = ['id', 'ra_deg', 'dec_deg', 'motion_arcsec_yr', 'motion_err_arcsec_yr', 'pmra_mas_yr', 'pmdec_mas_yr', 'significance_sigma', 'snr', 'n_epochs', 'span_yr', 'quality', 'gaia_match', 'status'];
      const rows = cands.map((c, i) => [`C${i + 1}`, c.ra_deg, c.dec_deg, c.motion_arcsec_yr, c.motion_err_arcsec_yr, c.pmra_mas_yr, c.pmdec_mas_yr, c.significance_sigma, c.snr, c.n_epochs, c.span_yr, c.quality.level, c.known_match ? c.known_match.id : '', c.status]);
      const csv = [head, ...rows].map((r) => r.map((x) => `"${String(x).replace(/"/g, '""')}"`).join(',')).join('\n');
      this.download(new Blob(['﻿' + csv], { type: 'text/csv' }), `spherex_candidatos_${this.fileTag()}.csv`);
    }
  }

  download(blobOrUrl, name, isDataUrl = false) {
    const a = document.createElement('a');
    a.href = isDataUrl ? blobOrUrl : URL.createObjectURL(blobOrUrl); a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    if (!isDataUrl) setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  // ------------------------------------------------------------------ UI varios
  openTab(id) {
    document.querySelectorAll('.tab-btn').forEach((t) => { const on = t.dataset.tab === id; t.classList.toggle('active', on); t.setAttribute('aria-selected', on); });
    document.querySelectorAll('.tab-content').forEach((c) => { const on = c.id === id; c.classList.toggle('active', on); c.hidden = !on; });
    if (id === 'tabSpectrum') this.spec.resize();
    if (id === 'tabLightcurve') this.lc.resize();
    if (id === 'tabAladin') this.initAladin();
  }

  initAladin() {
    const c = this.centerPosition() || { ra: this.state.ra, dec: this.state.dec };
    if (this.aladin) { this.aladin.gotoRaDec(c.ra, c.dec); return; }
    $('aladinStatus').textContent = 'Cargando Aladin Lite…';
    const start = () => window.A.init.then(() => {
      this.aladin = window.A.aladin('#aladinLiteContainer', { survey: 'P/DSS2/color', fov: this.state.fov / 60 * 2, target: `${c.ra} ${c.dec}`, showReticle: true, showLayersControl: false });
      $('aladinStatus').textContent = 'Aladin Lite (CDS). Arrastra y usa la rueda para explorar.';
    }).catch(() => { $('aladinStatus').textContent = 'No se pudo iniciar Aladin Lite.'; });
    if (window.A) return start();
    const sc = document.createElement('script');
    sc.src = 'https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js'; sc.charset = 'utf-8';
    sc.onload = start; sc.onerror = () => { $('aladinStatus').textContent = 'Aladin Lite necesita conexión a internet.'; };
    document.head.appendChild(sc);
  }

  showLoader(on) { $('loader').hidden = !on; if (on) { $('loaderText').textContent = 'Buscando imágenes en IRSA…'; $('loaderBar').style.width = '5%'; } }
  notice(kind, html) { const d = document.createElement('div'); d.className = `notice ${kind}`; d.innerHTML = html; $('notices').appendChild(d); }
  clearNotices() { $('notices').innerHTML = ''; }

  openShare() {
    $('shareUrl').value = this.shareUrl();
    $('embedCode').value = `<iframe src="${this.shareUrl(true)}" width="720" height="560" style="border:0" title="Visor SPHEREx" loading="lazy" allowfullscreen></iframe>`;
    $('shareDialog').showModal();
  }

  async copy(text, btn) {
    try { await navigator.clipboard.writeText(text); const o = btn.textContent; btn.textContent = '¡Copiado!'; setTimeout(() => { btn.textContent = o; }, 1500); }
    catch (e) { /* el texto queda seleccionable */ }
  }

  openTour() {
    const steps = [
      ['Fotos del mismo lugar en distintas fechas', 'SPHEREx, un telescopio de NASA, fotografía todo el cielo en infrarrojo cada seis meses. Aquí ves fotos <strong>reales</strong> del mismo pedacito de cielo, tomadas en fechas distintas.'],
      ['Lo que se mueve, salta', 'En <strong>Parpadeo</strong> las fechas pasan como un video. Las estrellas lejanas no se mueven; una estrella cercana, una enana marrón o un asteroide sí. Así se descubrió Plutón en 1930.'],
      ['Cada píxel es grande', 'Cada cuadradito mide 6,2″ (el grosor de un cabello a 3 metros). WISE 0855 avanza ~8″ por año: solo un poco más de un píxel. Usa el zoom y la <strong>trayectoria esperada</strong> rosa como guía.'],
      ['Comparar de otras formas', '<strong>Deslizador</strong>: arrastra para ver dos fechas. <strong>Diferencia</strong>: se resta una fecha y queda solo lo que cambió. <strong>Suma</strong>: junta todas para ver más débil.'],
      ['Colores invisibles', 'SPHEREx ve 102 "colores" infrarrojos. Haz clic en una estrella para ver su <strong>espectro</strong>: su huella de colores. En <strong>Brillo</strong> verás si cambió con el tiempo.'],
      ['Candidatos, no descubrimientos', 'La herramienta señala lo que parece moverse, lo coteja con el catálogo Gaia y te deja exportarlo. Siempre hace falta que una persona lo revise.'],
    ];
    let i = 0; const d = $('tourDialog');
    const draw = () => {
      $('tourSteps').innerHTML = `<h4 class="tour-h">${steps[i][0]}</h4><p>${steps[i][1]}</p>`;
      $('tourCount').textContent = `${i + 1} de ${steps.length}`;
      $('tourPrev').disabled = i === 0; $('tourNext').textContent = i === steps.length - 1 ? 'Empezar' : 'Siguiente';
    };
    $('tourPrev').onclick = () => { i = Math.max(0, i - 1); draw(); };
    $('tourNext').onclick = () => { if (i === steps.length - 1) { d.close(); try { localStorage.setItem('drift-tour-seen', '1'); } catch (e) { /* */ } } else { i++; draw(); } };
    draw(); d.showModal();
  }

  applyTheme() {
    let t = null; try { t = localStorage.getItem('drift-theme'); } catch (e) { /* */ }
    if (t) document.documentElement.dataset.theme = t;
  }
  toggleTheme() {
    const cur = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('drift-theme', next); } catch (e) { /* */ }
    this.viewer.render(); this.spec.render(); this.lc.render();
  }
}

window.addEventListener('DOMContentLoaded', () => { window.app = new App(); });
