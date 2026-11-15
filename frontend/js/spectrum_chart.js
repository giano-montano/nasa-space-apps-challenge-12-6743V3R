/**
 * Interactive 102-Band SPHEREx Infrared Spectrum Visualizer
 * HTML5 Canvas renderer with molecular fingerprint annotations
 */

class SpectrumChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.data = null;
    this.hoverPoint = null;

    // Handle high DPI displays
    this.resize();
    window.addEventListener('resize', () => this.resize());

    // Hover interaction
    this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
    this.canvas.addEventListener('mouseleave', () => {
      this.hoverPoint = null;
      this.render();
    });
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.render();
  }

  setData(spectrumData) {
    this.data = spectrumData;
    this.render();
  }

  onMouseMove(e) {
    if (!this.data || !this.data.spectrum || this.data.spectrum.length === 0) return;
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const padLeft = 46, padRight = 20, padTop = 24, padBottom = 30;
    const w = rect.width - padLeft - padRight;

    // Find nearest point
    const minW = 0.75, maxW = 5.0;
    let closest = null;
    let minDist = 999;

    this.data.spectrum.forEach(pt => {
      const px = padLeft + ((pt.wavelength_um - minW) / (maxW - minW)) * w;
      const dist = Math.abs(px - x);
      if (dist < minDist && dist < 20) {
        minDist = dist;
        closest = pt;
      }
    });

    this.hoverPoint = closest;
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

    if (!this.data || !this.data.spectrum || this.data.spectrum.length === 0) {
      ctx.fillStyle = '#7D85A0';
      ctx.font = '13px Schibsted Grotesk, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Sin datos de espectro disponibles', width / 2, height / 2);
      ctx.restore();
      return;
    }

    const padLeft = 46, padRight = 20, padTop = 26, padBottom = 32;
    const plotW = width - padLeft - padRight;
    const plotH = height - padTop - padBottom;

    const minW = 0.75, maxW = 5.0;
    const pts = this.data.spectrum;

    let minF = Math.min(...pts.map(p => p.flux_mjy));
    let maxF = Math.max(...pts.map(p => p.flux_mjy));
    minF = Math.max(0, minF * 0.85);
    maxF = maxF * 1.15;
    if (maxF <= minF) maxF = minF + 10;

    const getX = (wVal) => padLeft + ((wVal - minW) / (maxW - minW)) * plotW;
    const getY = (fVal) => padTop + plotH - ((fVal - minF) / (maxF - minF)) * plotH;

    // Draw detector backgrounds (Detectors 1 to 6)
    const detBounds = [
      { id: 1, min: 0.75, max: 1.11, color: 'rgba(255, 92, 147, 0.06)' },
      { id: 2, min: 1.11, max: 1.64, color: 'rgba(0, 210, 255, 0.06)' },
      { id: 3, min: 1.64, max: 2.42, color: 'rgba(0, 230, 118, 0.06)' },
      { id: 4, min: 2.42, max: 3.82, color: 'rgba(255, 179, 71, 0.06)' },
      { id: 5, min: 3.82, max: 4.42, color: 'rgba(186, 104, 200, 0.06)' },
      { id: 6, min: 4.42, max: 5.00, color: 'rgba(255, 82, 82, 0.06)' }
    ];

    detBounds.forEach(det => {
      const x1 = getX(det.min);
      const x2 = getX(det.max);
      ctx.fillStyle = det.color;
      ctx.fillRect(x1, padTop, x2 - x1, plotH);

      // Detector label
      ctx.fillStyle = 'rgba(183, 189, 210, 0.4)';
      ctx.font = '9px Schibsted Grotesk, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`Det ${det.id}`, (x1 + x2) / 2, padTop + 11);
    });

    // Grid lines
    ctx.strokeStyle = '#1F2535';
    ctx.lineWidth = 1;

    // Wavelength vertical lines
    [1.0, 2.0, 3.0, 4.0, 5.0].forEach(wv => {
      const gx = getX(wv);
      ctx.beginPath();
      ctx.moveTo(gx, padTop);
      ctx.lineTo(gx, padTop + plotH);
      ctx.stroke();

      ctx.fillStyle = '#7D85A0';
      ctx.font = '10px Schibsted Grotesk, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`${wv} µm`, gx, height - 10);
    });

    // Flux horizontal lines
    [0.25, 0.5, 0.75, 1.0].forEach(fFrac => {
      const val = minF + (maxF - minF) * fFrac;
      const gy = getY(val);
      ctx.beginPath();
      ctx.moveTo(padLeft, gy);
      ctx.lineTo(padLeft + plotW, gy);
      ctx.stroke();

      ctx.fillStyle = '#7D85A0';
      ctx.font = '10px Schibsted Grotesk, sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(val.toFixed(0), padLeft - 6, gy + 3);
    });

    // Draw molecular absorption bands
    if (this.data.features) {
      this.data.features.forEach(feat => {
        const fx = getX(feat.wave);
        ctx.strokeStyle = 'rgba(255, 92, 147, 0.35)';
        ctx.setLineDash([2, 4]);
        ctx.beginPath();
        ctx.moveTo(fx, padTop);
        ctx.lineTo(fx, padTop + plotH);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = '#FF5C93';
        ctx.font = '9px Schibsted Grotesk, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(feat.label, fx, padTop + 24);
      });
    }

    // Spectrum Area & Line
    ctx.beginPath();
    ctx.moveTo(getX(pts[0].wavelength_um), getY(pts[0].flux_mjy));
    for (let i = 1; i < pts.length; i++) {
      ctx.lineTo(getX(pts[i].wavelength_um), getY(pts[i].flux_mjy));
    }

    // Stroke
    ctx.strokeStyle = '#00D2FF';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Area fill
    ctx.lineTo(getX(pts[pts.length - 1].wavelength_um), padTop + plotH);
    ctx.lineTo(getX(pts[0].wavelength_um), padTop + plotH);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, padTop, 0, padTop + plotH);
    grad.addColorStop(0, 'rgba(0, 210, 255, 0.25)');
    grad.addColorStop(1, 'rgba(0, 210, 255, 0.0)');
    ctx.fillStyle = grad;
    ctx.fill();

    // Hover tooltip
    if (this.hoverPoint) {
      const hx = getX(this.hoverPoint.wavelength_um);
      const hy = getY(this.hoverPoint.flux_mjy);

      ctx.fillStyle = '#FF5C93';
      ctx.beginPath();
      ctx.arc(hx, hy, 5, 0, Math.PI * 2);
      ctx.fill();

      // Tooltip box
      const tipText = `λ: ${this.hoverPoint.wavelength_um} µm | F: ${this.hoverPoint.flux_mjy} mJy (Det ${this.hoverPoint.detector})`;
      ctx.font = '11px Schibsted Grotesk, sans-serif';
      const textW = ctx.measureText(tipText).width + 16;
      const tipX = Math.min(width - textW - 10, Math.max(10, hx - textW / 2));
      const tipY = Math.max(12, hy - 32);

      ctx.fillStyle = '#171B26';
      ctx.strokeStyle = '#FF5C93';
      ctx.lineWidth = 1;
      ctx.fillRect(tipX, tipY, textW, 24);
      ctx.strokeRect(tipX, tipY, textW, 24);

      ctx.fillStyle = '#E9EAF2';
      ctx.textAlign = 'left';
      ctx.fillText(tipText, tipX + 8, tipY + 16);
    }

    ctx.restore();
  }
}

