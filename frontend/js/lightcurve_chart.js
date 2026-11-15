/**
 * Photometric Light Curve Time-Series Chart for Variable Stars
 * Plots Relative Flux / Magnitude across observation epochs
 */

class LightcurveChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.data = null;
    this.activeEpoch = 1;

    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.render();
  }

  setData(lightcurveData, activeEpoch = 1) {
    this.data = lightcurveData;
    this.activeEpoch = activeEpoch;
    this.render();
  }

  setActiveEpoch(epoch) {
    this.activeEpoch = epoch;
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

    if (!this.data || !this.data.lightcurve || this.data.lightcurve.length === 0) {
      ctx.fillStyle = '#7D85A0';
      ctx.font = '13px Schibsted Grotesk, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Sin datos fotométricos', width / 2, height / 2);
      ctx.restore();
      return;
    }

    const padLeft = 44, padRight = 20, padTop = 20, padBottom = 30;
    const plotW = width - padLeft - padRight;
    const plotH = height - padTop - padBottom;

    const pts = this.data.lightcurve;
    let minF = Math.min(...pts.map(p => p.flux_rel));
    let maxF = Math.max(...pts.map(p => p.flux_rel));
    minF = Math.max(0, minF * 0.7);
    maxF = maxF * 1.25;
    if (maxF <= minF) maxF = minF + 10;

    const getX = (ep) => padLeft + ((ep - 1) / 7.0) * plotW;
    const getY = (val) => padTop + plotH - ((val - minF) / (maxF - minF)) * plotH;

    // Grid lines
    ctx.strokeStyle = '#1F2535';
    ctx.lineWidth = 1;

    // Epoch columns
    for (let e = 1; e <= 8; e++) {
      const gx = getX(e);
      ctx.beginPath();
      ctx.moveTo(gx, padTop);
      ctx.lineTo(gx, padTop + plotH);
      ctx.stroke();

      ctx.fillStyle = '#7D85A0';
      ctx.font = '10px Schibsted Grotesk, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`Ép ${e}`, gx, height - 10);
    }

    // Connect curve
    ctx.beginPath();
    ctx.moveTo(getX(pts[0].epoch), getY(pts[0].flux_rel));
    for (let i = 1; i < pts.length; i++) {
      ctx.lineTo(getX(pts[i].epoch), getY(pts[i].flux_rel));
    }
    ctx.strokeStyle = '#FFB347';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw points & error bars
    pts.forEach(p => {
      const px = getX(p.epoch);
      const py = getY(p.flux_rel);
      const isActive = p.epoch === this.activeEpoch;

      // Point circle
      ctx.fillStyle = isActive ? '#FF5C93' : '#FFB347';
      ctx.beginPath();
      ctx.arc(px, py, isActive ? 6 : 4, 0, Math.PI * 2);
      ctx.fill();

      if (isActive) {
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Label above active point
        ctx.fillStyle = '#E9EAF2';
        ctx.font = 'bold 11px Schibsted Grotesk, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${p.flux_rel.toFixed(1)}%`, px, Math.max(16, py - 10));
      }
    });

    ctx.restore();
  }
}

