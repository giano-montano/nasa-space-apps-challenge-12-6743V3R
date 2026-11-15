/**
 * Celestial Coordinate Parsing and Validation
 * Supports Decimal Degrees and Sexagesimal (HMS / DMS)
 */

const AstronomicalCoords = {
  parse(raInput, decInput) {
    const raStr = String(raInput).trim();
    const decStr = String(decInput).trim();

    // Check direct float
    const raNum = parseFloat(raStr);
    const decNum = parseFloat(decStr);

    if (!isNaN(raNum) && !isNaN(decNum) && !raStr.includes('h') && !raStr.includes(':')) {
      return {
        ra: ((raNum % 360) + 360) % 360,
        dec: Math.max(-90, Math.min(90, decNum)),
        isValid: true
      };
    }

    const raDeg = this.parseHMS(raStr);
    const decDeg = this.parseDMS(decStr);

    if (raDeg !== null && decDeg !== null) {
      return {
        ra: ((raDeg % 360) + 360) % 360,
        dec: Math.max(-90, Math.min(90, decDeg)),
        isValid: true
      };
    }

    return { ra: 0, dec: 0, isValid: false, error: 'Coordenadas no válidas. Usa grados (ej. 133.795, -7.245) o sexagesimal (ej. 08h55m10s, -07d14m42s)' };
  },

  parseHMS(str) {
    const clean = str.replace(/[hmsHMS]/g, ' ').replace(/:/g, ' ').trim();
    const parts = clean.split(/\s+/).map(Number);
    if (parts.length >= 2 && !parts.some(isNaN)) {
      const h = parts[0];
      const m = parts[1];
      const s = parts[2] || 0;
      return (h + m / 60 + s / 3600) * 15.0;
    }
    return null;
  },

  parseDMS(str) {
    const isNegative = str.includes('-') || str.includes('−');
    const clean = str.replace(/[+\-−°′″dmsDMS]/g, ' ').replace(/:/g, ' ').trim();
    const parts = clean.split(/\s+/).map(Number);
    if (parts.length >= 2 && !parts.some(isNaN)) {
      const d = parts[0];
      const m = parts[1];
      const s = parts[2] || 0;
      const deg = d + m / 60 + s / 3600;
      return isNegative ? -deg : deg;
    }
    return null;
  },

  toSexagesimal(raDeg, decDeg) {
    const totalHours = ((raDeg % 360) + 360) % 360 / 15.0;
    const h = Math.floor(totalHours);
    const remM = (totalHours - h) * 60;
    const m = Math.floor(remM);
    const s = ((remM - m) * 60).toFixed(2);

    const sign = decDeg < 0 ? '-' : '+';
    const absDec = Math.abs(decDeg);
    const d = Math.floor(absDec);
    const remDm = (absDec - d) * 60;
    const dm = Math.floor(remDm);
    const ds = ((remDm - dm) * 60).toFixed(2);

    const pad = (n) => String(n).padStart(2, '0');

    return {
      ra: `${pad(h)}h ${pad(m)}m ${s}s`,
      dec: `${sign}${pad(d)}° ${pad(dm)}′ ${ds}″`
    };
  }
};

