/**
 * Astronomical Canvas Viewer for SPHEREx Imagery
 * Supports high-resolution rendering, zoom/pan, Gaia vectors,
 * reticle crosshairs, scale bars, and target trajectory overlay.
 */

class SkyCanvasViewer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    this.frameImage = null;
    this.imageElement = new Image();
    this.imageLoaded = false;

    // View state
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.isDragging = false;
    this.lastMouse = { x: 0, y: 0 };

    // Layers & Overlays
    this.showReticle = true;
    this.showGaia = true;
    this.showScale = true;
    this.showTrail = true;

    // Astronomical metadata
    this.fovArcmin = 5.0;
    this.targetInfo = null;
    this.gaiaSources = [];
    this.currentEpoch = 1;
    this.totalEpochs = 8;
    this.mode = 'blink';

    // Set canvas dimensions
    this.resize();
    window.addEventListener('resize', () => this.resize());

    // Mouse events for Zoom and Pan
    this.setupInteractions();
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.render();
  }

  setupInteractions() {
    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
      const newZoom = Math.max(0.7, Math.min(6.0, this.zoom * zoomFactor));

      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      this.panX = mouseX - (mouseX - this.panX) * (newZoom / this.zoom);
      this.panY = mouseY - (mouseY - this.panY) * (newZoom / this.zoom);
      this.zoom = newZoom;
      this.render();
    });

    this.canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.lastMouse = { x: e.clientX, y: e.clientY };
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isDragging) return;
      const dx = e.clientX - this.lastMouse.x;
      const dy = e.clientY - this.lastMouse.y;
      this.panX += dx;
      this.panY += dy;
      this.lastMouse = { x: e.clientX, y: e.clientY };
      this.render();
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    // Double click to reset zoom
    this.canvas.addEventListener('dblclick', () => {
      this.resetView();
    });
  }

  resetView() {
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.render();
  }

  setFrame(imageDataUri, epochIdx = 1, metadata = {}) {
    this.currentEpoch = epochIdx;
    this.mode = metadata.mode || this.mode;
    this.fovArcmin = metadata.fov || this.fovArcmin;
    this.targetInfo = metadata.target || this.targetInfo;

    this.imageLoaded = false;
    this.imageElement.onload = () => {
      this.imageLoaded = true;
      this.render();
    };
    this.imageElement.src = imageDataUri;
  }

  setGaiaSources(sources) {
    this.gaiaSources = sources || [];
    this.render();
  }

  render() {
    if (!this.ctx || !this.canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const ctx = this.ctx;
    const width = this.canvas.width / dpr;
    const height = this.canvas.height / dpr;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    // Deep space background
    ctx.fillStyle = '#0A0D14';
    ctx.fillRect(0, 0, width, height);

    // Render image transformed by zoom & pan
    ctx.save();
    ctx.translate(this.panX, this.panY);
    ctx.scale(this.zoom, this.zoom);

    if (this.imageLoaded && this.imageElement.width > 0) {
      // Draw image filling width x height
      ctx.drawImage(this.imageElement, 0, 0, width, height);
    } else {
      ctx.fillStyle = '#171B26';
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = '#7D85A0';
      ctx.font = '14px Schibsted Grotesk, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Cargando imagen SPHEREx...', width / 2, height / 2);
    }

    // Trajectory trail & Target tracker ring
    if (this.showTrail && this.targetInfo && !this.targetInfo.is_variable) {
      this.renderTrajectoryAndTarget(ctx, width, height);
    }

    // Gaia DR3 vector overlay
    if (this.showGaia && this.gaiaSources.length > 0) {
      this.renderGaiaOverlay(ctx, width, height);
    }

    // Reticle crosshair
    if (this.showReticle) {
      this.renderReticle(ctx, width, height);
    }

    ctx.restore();

    // Screen-space HUD Overlays (Scale bar & Compass orientation)
    if (this.showScale) {
      this.renderScaleBar(ctx, width, height);
    }
    this.renderCompass(ctx, width, height);

    ctx.restore();
  }

  renderReticle(ctx, width, height) {
    const cx = width / 2;
    const cy = height / 2;
    const r1 = 12;
    const r2 = 34;

    ctx.strokeStyle = 'rgba(74, 83, 115, 0.65)';
    ctx.lineWidth = 1;

    // Cross lines
    ctx.beginPath();
    ctx.moveTo(cx, cy - r2);
    ctx.lineTo(cx, cy - r1);
    ctx.moveTo(cx, cy + r1);
    ctx.lineTo(cx, cy + r2);
    ctx.moveTo(cx - r2, cy);
    ctx.lineTo(cx - r1, cy);
    ctx.moveTo(cx + r1, cy);
    ctx.lineTo(cx + r2, cy);
    ctx.stroke();

    // Center dot
    ctx.fillStyle = 'rgba(255, 92, 147, 0.4)';
    ctx.beginPath();
    ctx.arc(cx, cy, 2, 0, Math.PI * 2);
    ctx.fill();
  }

  renderTrajectoryAndTarget(ctx, width, height) {
    const arcsecPerPixel = (this.fovArcmin * 60.0) / width;
    const tYearsStep = 0.5; // 6-month survey epochs
    const pmRa = this.targetInfo.pm_ra || 0.0;
    const pmDec = this.targetInfo.pm_dec || 0.0;

    const cx = width / 2;
    const cy = height / 2;

    const getPos = (epIdx) => {
      const t = epIdx * tYearsStep;
      const dRaArcsec = (pmRa / 1000.0) * t;
      const dDecArcsec = (pmDec / 1000.0) * t;
      const dxPx = - (dRaArcsec / arcsecPerPixel);
      const dyPx = - (dDecArcsec / arcsecPerPixel);
      return { x: cx + dxPx, y: cy + dyPx };
    };

    // Draw dashed path
    ctx.beginPath();
    const start = getPos(0);
    ctx.moveTo(start.x, start.y);
    for (let i = 1; i < this.totalEpochs; i++) {
      const pt = getPos(i);
      ctx.lineTo(pt.x, pt.y);
    }
    ctx.strokeStyle = 'rgba(255, 92, 147, 0.45)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 5]);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw trail dots for prior epochs
    for (let i = 0; i < this.currentEpoch; i++) {
      const pt = getPos(i);
      ctx.fillStyle = 'rgba(255, 92, 147, 0.7)';
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    // Active target pulse marker
    const curPos = getPos(this.currentEpoch - 1);
    ctx.strokeStyle = '#FF5C93';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(curPos.x, curPos.y, 14, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle = '#FF5C93';
    ctx.beginPath();
    ctx.arc(curPos.x, curPos.y, 3.5, 0, Math.PI * 2);
    ctx.fill();
  }

  renderGaiaOverlay(ctx, width, height) {
    const arcsecPerPixel = (this.fovArcmin * 60.0) / width;
    const cx = width / 2;
    const cy = height / 2;

    this.gaiaSources.forEach(src => {
      // Find source relative to target center
      if (!this.targetInfo) return;
      const dRaDeg = (src.ra - this.targetInfo.ra) * Math.cos((this.targetInfo.dec * Math.PI) / 180);
      const dDecDeg = src.dec - this.targetInfo.dec;

      const dRaArcsec = dRaDeg * 3600.0;
      const dDecArcsec = dDecDeg * 3600.0;

      const px = cx - (dRaArcsec / arcsecPerPixel);
      const py = cy - (dDecArcsec / arcsecPerPixel);

      if (px < -20 || px > width + 20 || py < -20 || py > height + 20) return;

      // Draw Gaia star circle
      ctx.strokeStyle = src.is_target ? '#FF5C93' : 'rgba(0, 210, 255, 0.85)';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.arc(px, py, 6, 0, Math.PI * 2);
      ctx.stroke();

      // Proper motion vector arrow (10-year displacement)
      const pmRa = src.pmra || 0.0;   // mas/yr
      const pmDec = src.pmdec || 0.0; // mas/yr
      const totalPm = Math.sqrt(pmRa * pmRa + pmDec * pmDec);

      if (totalPm > 15.0) {
        // Vector displacement in 5 years (scaled for visibility)
        const vRaArcsec = (pmRa / 1000.0) * 5.0;
        const vDecArcsec = (pmDec / 1000.0) * 5.0;

        const vX = px - (vRaArcsec / arcsecPerPixel);
        const vY = py - (vDecArcsec / arcsecPerPixel);

        ctx.strokeStyle = src.is_target ? '#FF5C93' : '#00E676';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(vX, vY);
        ctx.stroke();

        // Arrow head
        const angle = Math.atan2(vY - py, vX - px);
        const headLen = 6;
        ctx.fillStyle = src.is_target ? '#FF5C93' : '#00E676';
        ctx.beginPath();
        ctx.moveTo(vX, vY);
        ctx.lineTo(vX - headLen * Math.cos(angle - Math.PI / 6), vY - headLen * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(vX - headLen * Math.cos(angle + Math.PI / 6), vY - headLen * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
      }
    });
  }

  renderScaleBar(ctx, width, height) {
    // 1 arcminute scale bar in screen pixels
    const arcsecPerPixel = (this.fovArcmin * 60.0) / width;
    const barArcsec = this.fovArcmin <= 2.0 ? 30.0 : 60.0; // 30" or 60"
    const barWidthPx = (barArcsec / arcsecPerPixel) * this.zoom;
    const label = this.fovArcmin <= 2.0 ? '30 arcseg' : '1 arcmin';

    const sx = 28;
    const sy = height - 28;

    ctx.strokeStyle = '#B7BDD2';
    ctx.lineWidth = 2;

    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(sx + barWidthPx, sy);
    ctx.moveTo(sx, sy - 5);
    ctx.lineTo(sx, sy + 5);
    ctx.moveTo(sx + barWidthPx, sy - 5);
    ctx.lineTo(sx + barWidthPx, sy + 5);
    ctx.stroke();

    ctx.fillStyle = '#B7BDD2';
    ctx.font = '11px Schibsted Grotesk, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(label, sx, sy - 8);
  }

  renderCompass(ctx, width, height) {
    const cx = width - 40;
    const cy = height - 40;
    const len = 28;

    ctx.strokeStyle = '#B7BDD2';
    ctx.lineWidth = 1.5;

    // North arrow (up)
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx, cy - len);
    ctx.stroke();

    // East arrow (left in celestial coords)
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx - len, cy);
    ctx.stroke();

    ctx.fillStyle = '#B7BDD2';
    ctx.font = 'bold 11px Schibsted Grotesk, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('N', cx, cy - len - 4);
    ctx.fillText('E', cx - len - 8, cy + 4);
  }
}

