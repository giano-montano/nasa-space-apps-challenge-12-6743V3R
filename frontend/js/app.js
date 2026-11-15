/**
 * Main Application Controller for Drift — SPHEREx Sky Viewer
 * NASA Space Apps Challenge 2026
 */

class AppController {
  constructor() {
    this.viewer = null;
    this.spectrumChart = null;
    this.lightcurveChart = null;

    // Core State
    this.state = {
      targetId: 'wise0855',
      ra: 133.7951,
      dec: -7.2451,
      fov: 5.0,
      mode: 'blink',      // 'blink' | 'diff' | 'stack'
      detector: 1,        // 1 to 6
      stackDetectors: false,
      currentFrame: 1,
      isPlaying: true,
      playSpeed: 1000,    // ms per frame
      totalFrames: 8,
      isOfflineDemo: false
    };

    this.playTimer = null;
    this.targetsData = {};
    this.currentData = null;

    this.init();
  }

  async init() {
    // Initialize Visualizers
    this.viewer = new SkyCanvasViewer('skyCanvas');
    this.spectrumChart = new SpectrumChart('spectrumCanvas');
    this.lightcurveChart = new LightcurveChart('lightcurveCanvas');

    // Parse URL parameters
    this.readUrlParams();

    // Bind UI Event Listeners
    this.bindEvents();

    // Load initial target data
    await this.loadTarget(this.state.targetId);

    // Start video playback
    if (this.state.isPlaying && this.state.mode === 'blink') {
      this.startPlayback();
    }
  }

  readUrlParams() {
    const params = new URLSearchParams(window.location.search);
    if (params.has('target')) this.state.targetId = params.get('target');
    if (params.has('ra')) this.state.ra = parseFloat(params.get('ra'));
    if (params.has('dec')) this.state.dec = parseFloat(params.get('dec'));
    if (params.has('fov')) this.state.fov = parseFloat(params.get('fov'));
    if (params.has('mode')) this.state.mode = params.get('mode');
    if (params.has('det')) this.state.detector = parseInt(params.get('det'), 10);
  }

  syncUrlParams() {
    const params = new URLSearchParams();
    params.set('ra', this.state.ra.toFixed(4));
    params.set('dec', this.state.dec.toFixed(4));
    params.set('fov', this.state.fov);
    params.set('mode', this.state.mode);
    if (this.state.targetId) params.set('target', this.state.targetId);
    window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);
  }

  bindEvents() {
    // Target buttons
    document.querySelectorAll('.target-item').forEach(btn => {
      btn.addEventListener('click', () => {
        const tid = btn.getAttribute('data-target-id');
        this.selectTarget(tid);
      });
    });

    // Coordinates Search Form
    const searchForm = document.getElementById('coordsForm');
    if (searchForm) {
      searchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.handleCoordsSubmit();
      });
    }

    // Playback Controls
    const playBtn = document.getElementById('btnPlay');
    if (playBtn) playBtn.addEventListener('click', () => this.togglePlayback());

    const prevBtn = document.getElementById('btnPrevFrame');
    if (prevBtn) prevBtn.addEventListener('click', () => this.stepFrame(-1));

    const nextBtn = document.getElementById('btnNextFrame');
    if (nextBtn) nextBtn.addEventListener('click', () => this.stepFrame(1));

    // Scrubber frame pills
    document.querySelectorAll('.frame-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        const ep = parseInt(pill.getAttribute('data-epoch'), 10);
        this.setFrame(ep);
      });
    });

    // Speed Selector
    const speedSelect = document.getElementById('playbackSpeed');
    if (speedSelect) {
      speedSelect.addEventListener('change', (e) => {
        const factor = parseFloat(e.target.value);
        this.state.playSpeed = Math.round(1000 / factor);
        if (this.state.isPlaying) {
          this.stopPlayback();
          this.startPlayback();
        }
      });
    }

    // Modes (Blink, Diff, Stack)
    document.querySelectorAll('.mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const mode = btn.getAttribute('data-mode');
        this.setMode(mode);
      });
    });

    // Field of View
    document.querySelectorAll('.fov-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const fov = parseFloat(btn.getAttribute('data-fov'));
        this.setFov(fov);
      });
    });

    // Detectors 1-6
    document.querySelectorAll('.det-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const det = parseInt(btn.getAttribute('data-det'), 10);
        this.setDetector(det);
      });
    });

    // Co-add All Detectors Button
    const stackDetBtn = document.getElementById('btnStackAllDetectors');
    if (stackDetBtn) {
      stackDetBtn.addEventListener('click', () => {
        this.state.stackDetectors = !this.state.stackDetectors;
        stackDetBtn.classList.toggle('active', this.state.stackDetectors);
        this.refreshCurrentData();
      });
    }

    // Overlays (Reticle, Gaia, Scale)
    const toggleReticle = document.getElementById('toggleReticle');
    if (toggleReticle) {
      toggleReticle.addEventListener('click', () => {
        this.viewer.showReticle = !this.viewer.showReticle;
        toggleReticle.classList.toggle('active', this.viewer.showReticle);
        this.viewer.render();
      });
    }

    const toggleGaia = document.getElementById('toggleGaia');
    if (toggleGaia) {
      toggleGaia.addEventListener('click', () => {
        this.viewer.showGaia = !this.viewer.showGaia;
        toggleGaia.classList.toggle('active', this.viewer.showGaia);
        this.viewer.render();
      });
    }

    const btnResetView = document.getElementById('btnResetZoom');
    if (btnResetView) {
      btnResetView.addEventListener('click', () => this.viewer.resetView());
    }

    // Tabs in Analysis Column
    document.querySelectorAll('.tab-btn').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        const targetTab = document.getElementById(tab.getAttribute('data-tab'));
        if (targetTab) targetTab.classList.add('active');

        // Trigger chart resize on tab switch
        if (tab.getAttribute('data-tab') === 'tabSpectrum') this.spectrumChart.resize();
        if (tab.getAttribute('data-tab') === 'tabLightcurve') this.lightcurveChart.resize();
        if (tab.getAttribute('data-tab') === 'tabAladin') this.initAladinLite();
      });
    });

    // Copy Share Link Button
    const copyBtn = document.getElementById('btnCopyLink');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => this.copyShareLink());
    }

    // Guided Tour Modal
    const tourBtn = document.getElementById('btnStartTour');
    if (tourBtn) tourBtn.addEventListener('click', () => this.openTourModal());

    const closeTourBtn = document.getElementById('btnCloseTour');
    if (closeTourBtn) closeTourBtn.addEventListener('click', () => this.closeTourModal());

    // Citizen Science Export
    const exportBtn = document.getElementById('btnExportCandidate');
    if (exportBtn) exportBtn.addEventListener('click', () => this.exportCitizenScienceData());

    // Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.code === 'Space') {
        e.preventDefault();
        this.togglePlayback();
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        this.stepFrame(-1);
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        this.stepFrame(1);
      }
    });
  }

  async loadTarget(targetId) {
    this.state.targetId = targetId;

    // Update active state in Target list
    document.querySelectorAll('.target-item').forEach(item => {
      item.classList.toggle('active', item.getAttribute('data-target-id') === targetId);
    });

    await this.fetchData();
  }

  async selectTarget(targetId) {
    this.state.targetId = targetId;
    await this.loadTarget(targetId);
  }

  handleCoordsSubmit() {
    const raVal = document.getElementById('raInput').value;
    const decVal = document.getElementById('decInput').value;
    const parsed = AstronomicalCoords.parse(raVal, decVal);

    if (!parsed.isValid) {
      alert(parsed.error);
      return;
    }

    this.state.ra = parsed.ra;
    this.state.dec = parsed.dec;
    this.state.targetId = null; // custom coordinates

    // Deselect target list
    document.querySelectorAll('.target-item').forEach(item => item.classList.remove('active'));

    this.fetchData();
  }

  async fetchData() {
    this.syncUrlParams();

    // First attempt: API endpoint
    try {
      const url = `/api/frames?ra=${this.state.ra}&dec=${this.state.dec}&fov=${this.state.fov}&mode=${this.state.mode}&detector=${this.state.detector}&stack_detectors=${this.state.stackDetectors}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        this.handleDataSuccess(data);
        return;
      }
    } catch (e) {
      console.warn('Backend API unavailable. Falling back to offline demo data.', e);
    }

    // Fallback attempt: Offline Demo JSON bundle
    const tid = this.state.targetId || 'wise0855';
    try {
      const demoRes = await fetch(`./demo_data/${tid}.json`);
      if (demoRes.ok) {
        const bundle = await demoRes.json();
        const modeData = bundle[this.state.mode] || bundle['blink'];
        this.handleDataSuccess(modeData, bundle.gaia);
        return;
      }
    } catch (e2) {
      console.error('Failed to load demo data:', e2);
    }
  }

  handleDataSuccess(data, preloadedGaia = null) {
    this.currentData = data;

    // Update Input fields
    const raInput = document.getElementById('raInput');
    const decInput = document.getElementById('decInput');
    if (raInput && data.coordinates) raInput.value = data.coordinates.ra_deg.toFixed(4);
    if (decInput && data.coordinates) decInput.value = data.coordinates.dec_deg.toFixed(4);

    // Update target info
    const t = data.target;
    if (t) {
      this.state.ra = t.ra;
      this.state.dec = t.dec;
      const targetLabel = document.getElementById('hudTargetName');
      if (targetLabel) targetLabel.textContent = t.name;
      const targetDesc = document.getElementById('targetDescription');
      if (targetDesc) targetDesc.textContent = t.description;
      const metaType = document.getElementById('metaType');
      if (metaType) metaType.textContent = t.kind;
    }

    // Update mode badge
    const modeBadge = document.getElementById('hudModeName');
    if (modeBadge) {
      const modeNames = { blink: 'Blink (Parpadeo)', diff: 'Diferencia (Iₖ - I₀)', stack: 'Apilado Profundo' };
      modeBadge.textContent = modeNames[this.state.mode] || this.state.mode;
    }

    // Render Spectrum and Lightcurve
    if (data.spectrum) this.spectrumChart.setData(data.spectrum);
    if (data.lightcurve) this.lightcurveChart.setData(data.lightcurve, this.state.currentFrame);

    // Render Gaia vectors
    if (preloadedGaia) {
      this.viewer.setGaiaSources(preloadedGaia);
    } else {
      this.fetchGaiaSources(this.state.ra, this.state.dec, this.state.fov);
    }

    // Update assisted candidates list
    this.updateCandidatesList(data.candidates);

    // Set first frame
    this.state.totalFrames = data.frames ? data.frames.length : 1;
    this.setFrame(1);
  }

  async fetchGaiaSources(ra, dec, fov) {
    try {
      const res = await fetch(`/api/catalog?ra=${ra}&dec=${dec}&fov=${fov}&source=gaia`);
      if (res.ok) {
        const cat = await res.json();
        this.viewer.setGaiaSources(cat.sources);
      }
    } catch (e) {
      // Ignore gaia catalog network errors
    }
  }

  setFrame(frameNum) {
    if (!this.currentData || !this.currentData.frames || this.currentData.frames.length === 0) return;

    this.state.currentFrame = Math.max(1, Math.min(this.state.totalFrames, frameNum));
    const frameObj = this.currentData.frames[this.state.currentFrame - 1];

    if (frameObj) {
      this.viewer.setFrame(frameObj.image_data, this.state.currentFrame, {
        mode: this.state.mode,
        fov: this.state.fov,
        target: this.currentData.target
      });

      // Update HUD Labels
      const frameTitle = document.getElementById('hudFrameTitle');
      if (frameTitle) frameTitle.textContent = `Fotograma ${this.state.currentFrame} de ${this.state.totalFrames}`;
      const frameDesc = document.getElementById('hudFrameDesc');
      if (frameDesc) frameDesc.textContent = frameObj.caption || frameObj.date;

      // Update Scrubber Pills
      document.querySelectorAll('.frame-pill').forEach(pill => {
        const ep = parseInt(pill.getAttribute('data-epoch'), 10);
        pill.classList.toggle('active', ep === this.state.currentFrame);
      });

      // Update Lightcurve active epoch
      if (this.lightcurveChart) {
        this.lightcurveChart.setActiveEpoch(this.state.currentFrame);
      }
    }
  }

  togglePlayback() {
    this.state.isPlaying = !this.state.isPlaying;
    const playBtn = document.getElementById('btnPlay');
    if (playBtn) {
      playBtn.innerHTML = this.state.isPlaying ? 
        '<svg width="18" height="18" viewBox="0 0 18 18"><rect x="3" y="2" width="4" height="14" fill="#0F1219"></rect><rect x="11" y="2" width="4" height="14" fill="#0F1219"></rect></svg>' :
        '<svg width="18" height="18" viewBox="0 0 18 18"><path d="M4 2 L16 9 L4 16 Z" fill="#0F1219"></path></svg>';
    }

    if (this.state.isPlaying) {
      this.startPlayback();
    } else {
      this.stopPlayback();
    }
  }

  startPlayback() {
    this.stopPlayback();
    this.playTimer = setInterval(() => {
      let next = this.state.currentFrame + 1;
      if (next > this.state.totalFrames) next = 1;
      this.setFrame(next);
    }, this.state.playSpeed);
  }

  stopPlayback() {
    if (this.playTimer) {
      clearInterval(this.playTimer);
      this.playTimer = null;
    }
  }

  stepFrame(delta) {
    let next = this.state.currentFrame + delta;
    if (next > this.state.totalFrames) next = 1;
    if (next < 1) next = this.state.totalFrames;
    this.setFrame(next);
  }

  setMode(mode) {
    this.state.mode = mode;
    document.querySelectorAll('.mode-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
    });

    // Scrubber is only meaningful in Blink & Difference modes
    const scrubber = document.getElementById('playerScrubber');
    if (scrubber) {
      scrubber.style.display = mode === 'stack' ? 'none' : 'flex';
    }

    this.fetchData();
  }

  setFov(fov) {
    this.state.fov = fov;
    document.querySelectorAll('.fov-btn').forEach(btn => {
      btn.classList.toggle('active', parseFloat(btn.getAttribute('data-fov')) === fov);
    });
    this.fetchData();
  }

  setDetector(det) {
    this.state.detector = det;
    document.querySelectorAll('.det-btn').forEach(btn => {
      btn.classList.toggle('active', parseInt(btn.getAttribute('data-det'), 10) === det);
    });
    this.fetchData();
  }

  refreshCurrentData() {
    this.fetchData();
  }

  updateCandidatesList(candidates) {
    const listEl = document.getElementById('candidatesList');
    if (!listEl) return;

    if (!candidates || candidates.length === 0) {
      listEl.innerHTML = '<p class="text-muted" style="font-size: 13px;">No se han detectado desplazamientos anómalos superiores al umbral.</p>';
      return;
    }

    listEl.innerHTML = candidates.map(c => `
      <div style="padding: 10px 12px; background: var(--bg-base); border-radius: var(--radius-md); border-left: 3px solid var(--accent-rose);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <strong style="color: #FFFFFF; font-size: 13px;">${c.name}</strong>
          <span style="font-size: 11px; color: var(--accent-green);">Confianza: ${(c.confidence * 100).toFixed(0)}%</span>
        </div>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
          Movimiento propio: <strong class="text-rose">${c.proper_motion_arcsec_yr} ″/año</strong> | Clase: ${c.spectral_class}
        </div>
      </div>
    `).join('');
  }

  copyShareLink() {
    const shareUrl = window.location.href;
    navigator.clipboard.writeText(shareUrl).then(() => {
      const btn = document.getElementById('btnCopyLink');
      const orig = btn.textContent;
      btn.textContent = '¡Enlace Copiado!';
      btn.style.borderColor = 'var(--accent-green)';
      btn.style.color = 'var(--accent-green)';
      setTimeout(() => {
        btn.textContent = orig;
        btn.style.borderColor = '';
        btn.style.color = '';
      }, 2000);
    });
  }

  openTourModal() {
    const modal = document.getElementById('tourModal');
    if (modal) modal.classList.add('open');
  }

  closeTourModal() {
    const modal = document.getElementById('tourModal');
    if (modal) modal.classList.remove('open');
  }

  exportCitizenScienceData() {
    if (!this.currentData) return;
    const report = {
      mission: 'SPHEREx Sky Viewer — NASA Space Apps Challenge 2026',
      target: this.currentData.target,
      coordinates: this.currentData.coordinates,
      mode: this.state.mode,
      detector_band: this.state.detector,
      candidates: this.currentData.candidates,
      export_timestamp: new Date().toISOString()
    };

    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `SPHEREx_Discovery_Report_${this.state.targetId || 'custom'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  initAladinLite() {
    const aladinContainer = document.getElementById('aladinLiteContainer');
    if (!aladinContainer || window.aladinInstance) return;

    if (typeof A !== 'undefined' && A.aladin) {
      try {
        window.aladinInstance = A.aladin('#aladinLiteContainer', {
          survey: 'P/DSS2/color',
          fov: this.state.fov / 60.0,
          target: `${this.state.ra} ${this.state.dec}`
        });
      } catch (e) {
        console.warn('Aladin Lite initialization notice:', e);
      }
    }
  }
}

// Bootstrap on DOM load
window.addEventListener('DOMContentLoaded', () => {
  window.app = new AppController();
});

