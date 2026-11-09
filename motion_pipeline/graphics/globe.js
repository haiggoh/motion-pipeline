/* globe.js — realistic spinning globe for Part A (blue) S1. Pure function of absolute film time T.
   Data: window.LAND110 (geo/land-110m.js, Natural Earth 110m land via world-atlas v2, see LICENSES.md).
   Orthographic projection (own code): spin about the polar axis (lonC), view pitch PITCH, axial tilt TILT (pole leans right).
   Land fill = per-pixel inverse projection into an equirectangular land mask (rasterised once, antimeridian-unwrapped,
   polar ring closed to the pole) -> horizon/antimeridian/pole clipping is exact by construction (no polygon fill artefacts).
   Coast hairlines + graticule = vector polylines split at the horizon (z = 0) — strokes only, never filled.
   Rendered at 2x into an offscreen canvas, downsampled with high-quality smoothing (no coastline shimmer).
   v16 entrance build: draw(lonC, k) with k = {sk, gr, oc, ld} (all 0..1, defaults 1 = final look):
     sk = line-art skeleton opacity (rim, graticule, coastlines), gr = graticule draw-on progress (each line truncated to gr of its length),
     oc = ocean disc fill opacity (night shading + outer glow ride with it), ld = land fill opacity (composited over the ocean).
   v17 motion blur: k.lons = [lonC_0..lonC_n-1] (sub-frame centre longitudes across the shutter). When n > 1 the land mask is averaged
     over the n longitudes per pixel (ocean gradient / night shading / rim / glow are computed once -> stay sharp), and graticule +
     coastlines are accumulated additively ('lighter', alpha 1/n each) in their own layers, then composited at their usual opacity.
     n <= 1 (or no k.lons) takes the exact pre-v17 code path.
   k = {1,1,1,1} reproduces the pre-v16 pixels exactly (land-over-ocean 'over' blend collapses to the old mix when oc = 1). */
(function () {
  const D2R = Math.PI / 180, MW = 4096, MH = 2048;
  const hex = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  let MASK = null, RINGS = null;
  function rings() {
    if (RINGS) return RINGS;
    RINGS = window.LAND110.rings.map(f => { const r = []; for (let i = 0; i < f.length; i += 2) r.push([f[i], f[i + 1]]); return r; });
    return RINGS;
  }
  function buildMask() {
    if (MASK) return MASK;
    const c = document.createElement('canvas'); c.width = MW; c.height = MH; const x = c.getContext('2d');
    x.fillStyle = '#000'; x.fillRect(0, 0, MW, MH); x.fillStyle = '#fff'; x.beginPath();
    const P = (lo, la, k) => [(lo + 180 + k * 360) / 360 * MW, (90 - la) / 180 * MH];
    for (const r of rings()) {
      const u = [[r[0][0], r[0][1]]];                                   // unwrap longitudes (continuous across +-180)
      for (let i = 1; i < r.length; i++) { let l = r[i][0]; const pl = u[i - 1][0]; while (l - pl > 180) l -= 360; while (l - pl < -180) l += 360; u.push([l, r[i][1]]); }
      let d = r[0][0] - u[u.length - 1][0]; while (d > 180) d -= 360; while (d < -180) d += 360;
      const total = u[u.length - 1][0] + d - u[0][0];                   // net longitude winding: +-360 => ring encloses a pole
      if (Math.abs(total) > 180) { const pole = u.reduce((s, p) => s + p[1], 0) < 0 ? -90 : 90, cl = u[0][0] + total;
        u.push([cl, u[0][1]], [cl, pole], [u[0][0], pole]); }
      for (let k = -1; k <= 1; k++) { u.forEach((p, i) => { const q = P(p[0], p[1], k); i ? x.lineTo(q[0], q[1]) : x.moveTo(q[0], q[1]); }); x.closePath(); }
    }
    x.fill('evenodd');
    const id = x.getImageData(0, 0, MW, MH).data; MASK = new Float32Array(MW * MH);
    for (let i = 0; i < MW * MH; i++) MASK[i] = id[i * 4] / 255;
    return MASK;
  }
  function create(o) {
    const cx = o.cx, cy = o.cy, R = o.R, M = o.margin || 48, SS = 2;
    const W = Math.ceil(2 * (R + M)), ox = cx - W / 2, oy = cy - W / 2;
    const TILT = (o.tilt != null ? o.tilt : 18) * D2R, PITCH = (o.pitch != null ? o.pitch : 38) * D2R;
    const ct = Math.cos(TILT), st = Math.sin(TILT), cp = Math.cos(PITCH), sp = Math.sin(PITCH);
    const wrap = document.createElement('div'); wrap.style.cssText = `position:absolute;left:${ox}px;top:${oy}px;width:${W}px;height:${W}px;pointer-events:none`;
    const cv = document.createElement('canvas'); cv.width = W; cv.height = W; cv.style.cssText = `width:${W}px;height:${W}px;display:block`; wrap.appendChild(cv);
    const ctx = cv.getContext('2d');
    const S = 2 * Math.ceil(R * SS + 2), R2 = R * SS, c2 = S / 2;            // 2x work canvas around the disc only
    const wk = document.createElement('canvas'); wk.width = S; wk.height = S; const wx = wk.getContext('2d');
    const img = wx.createImageData(S, S), dat = img.data;
    const C = o.colors || {};
    const OC0 = hex(C.ocean0 || '#2456B8'), OC1 = hex(C.ocean1 || '#1E3F96'),
          LAND = hex(C.land || '#4C9CEB'), LA = 0.9, COAST = C.coast || '#A9CCF5';
    let L = [-0.5, 0.45, 0.75]; { const n = Math.hypot(...L); L = L.map(v => v / n); }
    const sm = (a, b, v) => { const u = Math.max(0, Math.min(1, (v - a) / (b - a))); return u * u * (3 - 2 * u); };
    // forward projection (unit sphere -> view x right, y up, z toward viewer)
    function fwd(lo, la, lonC) {
      const dl = (lo - lonC) * D2R, f = la * D2R, X = Math.cos(f) * Math.sin(dl), Y = Math.sin(f), Z = Math.cos(f) * Math.cos(dl);
      const Yp = Y * cp - Z * sp, Zp = Y * sp + Z * cp; return [X * ct + Yp * st, -X * st + Yp * ct, Zp];
    }
    // centre longitude that puts (lon, lat) on the vertical centre line (compensates the axial tilt)
    function lonCentreFor(lon, lat) {
      const Yp = Math.sin((lat * D2R) - PITCH);  // approx: point near centre meridian
      const X = -Yp * Math.tan(TILT); return lon - Math.asin(Math.max(-1, Math.min(1, X / Math.cos(lat * D2R)))) / D2R;
    }
    function polyline(pts, lonC, X) {
      X = X || wx;        // pts [[lon,lat],...]; draws visible parts, split exactly at the horizon
      let prev = null, pen = false;
      const sx = v => c2 + v[0] * R2, sy = v => c2 - v[1] * R2;
      for (const p of pts) {
        const q = fwd(p[0], p[1], lonC);
        if (p.cut) { prev = q; pen = false; continue; }
        if (prev) {
          if (prev[2] >= 0 && q[2] >= 0) { if (!pen) { X.moveTo(sx(prev), sy(prev)); pen = true; } X.lineTo(sx(q), sy(q)); }
          else if (prev[2] >= 0 || q[2] >= 0) {
            const t = prev[2] / (prev[2] - q[2]); let h = [prev[0] + (q[0] - prev[0]) * t, prev[1] + (q[1] - prev[1]) * t]; const n = Math.hypot(h[0], h[1]) || 1; h = [h[0] / n, h[1] / n];
            if (prev[2] >= 0) { if (!pen) X.moveTo(sx(prev), sy(prev)); X.lineTo(sx(h), sy(h)); pen = false; }
            else { X.moveTo(sx(h), sy(h)); X.lineTo(sx(q), sy(q)); pen = true; }
          } else pen = false;
        }
        prev = q;
      }
    }
    let COASTS = null, GRAT = null;
    function prep() {
      if (COASTS) return;
      COASTS = rings().map(r => { const out = [], n = r.length;   // closed ring; antimeridian seam edges (both ends at |lon|=180, or jumps) are cut
        for (let i = 0; i <= n; i++) { const a = r[i % n], b = r[(i + n - 1) % n], p = [a[0], a[1]];
          if (i > 0 && (Math.abs(a[0] - b[0]) > 180 || (Math.abs(Math.abs(a[0]) - 180) < 1e-6 && Math.abs(Math.abs(b[0]) - 180) < 1e-6))) p.cut = true;
          out.push(p); } return out; });
      GRAT = [];
      for (let lo = -180; lo < 180; lo += 30) { const l = []; for (let la = -80; la <= 80; la += 2) l.push([lo, la]); GRAT.push(l); }
      for (let la = -60; la <= 60; la += 30) { const l = []; for (let lo = -180; lo <= 180; lo += 2) l.push([lo, la]); GRAT.push(l); }
    }
    function part(l, g) {                 // first g (0..1) of a polyline, by point count, with an interpolated head point
      if (g >= 1) return l; if (g <= 0) return [];
      const f = g * (l.length - 1), i = Math.floor(f), u = f - i, out = l.slice(0, i + 1);
      if (u > 0 && i + 1 < l.length) out.push([l[i][0] + (l[i + 1][0] - l[i][0]) * u, l[i][1] + (l[i + 1][1] - l[i][1]) * u]);
      return out;
    }
    const accL = {}, mkc = () => { const c = document.createElement('canvas'); c.width = S; c.height = S; return c; };
    function render(lonC, landOnly, k) {
      k = k || {}; const SK = k.sk != null ? k.sk : 1, GR = k.gr != null ? k.gr : 1, OC = k.oc != null ? k.oc : 1, LD = k.ld != null ? k.ld : 1;
      const mask = buildMask(); prep();
      const LONS = k.lons && k.lons.length > 1 ? k.lons.map(v => v - lonC) : null, NB = LONS ? LONS.length : 1;
      for (let py = 0; py < S; py++) {
        const y = (c2 - py - 0.5) / R2;
        for (let px = 0; px < S; px++) {
          const x = (px + 0.5 - c2) / R2, r2 = x * x + y * y, o = (py * S + px) * 4;
          if (r2 >= 1.0 + 2 / R2) { dat[o + 3] = 0; continue; }
          const rr = Math.sqrt(r2), cov = Math.max(0, Math.min(1, (1 - rr) * R2 + 0.5));
          const z = Math.sqrt(Math.max(0, 1 - Math.min(1, r2)));
          const X = x * ct - y * st, Yp = x * st + y * ct, Y = Yp * cp + z * sp, Z = -Yp * sp + z * cp;
          const lat = Math.asin(Math.max(-1, Math.min(1, Y))) / D2R; let lon = lonC + Math.atan2(X, Z) / D2R;
          let v = (90 - lat) / 180 * MH - 0.5; v = Math.max(0, Math.min(MH - 1.001, v));
          const v0 = Math.floor(v), fv = v - v0; let m = 0;
          for (let j = 0; j < NB; j++) {        // v17: land mask averaged over the shutter's sub-frame longitudes
            let u = ((lon + (LONS ? LONS[j] : 0) + 180) / 360) * MW - 0.5; u = ((u % MW) + MW) % MW;
            const u0 = Math.floor(u), fu = u - u0, u1 = (u0 + 1) % MW;
            m += (mask[v0 * MW + u0] * (1 - fu) + mask[v0 * MW + u1] * fu) * (1 - fv) + (mask[(v0 + 1) * MW + u0] * (1 - fu) + mask[(v0 + 1) * MW + u1] * fu) * fv;
          }
          m /= NB;
          if (landOnly) { dat[o] = dat[o + 1] = dat[o + 2] = 255 * m; dat[o + 3] = 255 * cov; continue; }
          const g = Math.min(1, Math.hypot(x + 0.28, y - 0.30) / 1.25), aL = LA * m * LD, ao = aL + OC * (1 - aL);
          if (ao <= 0) { dat[o + 3] = 0; continue; }
          const ndl = x * L[0] + y * L[1] + z * L[2], f = 1 - (0.30 - 0.30 * sm(-0.25, 0.35, ndl)) * OC;   // night shading fades in with the ocean fill
          for (let c = 0; c < 3; c++) { const oc = OC0[c] + (OC1[c] - OC0[c]) * g; dat[o + c] = (LAND[c] * aL + oc * OC * (1 - aL)) / ao * f; }
          dat[o + 3] = 255 * cov * ao;
        }
      }
      wx.putImageData(img, 0, 0);
      if (landOnly) return wk;
      wx.save(); wx.lineJoin = 'round'; wx.lineCap = 'round';
      if (LONS) {                           // v17 blurred strokes: additive accumulation of n sub-frame passes per layer
        const acc = (lines, col, lw) => { const L2 = accL[col] || (accL[col] = mkc()), X2 = L2.getContext('2d');
          X2.setTransform(1, 0, 0, 1, 0, 0); X2.clearRect(0, 0, S, S); X2.globalCompositeOperation = 'lighter'; X2.globalAlpha = 1 / NB;
          X2.lineJoin = 'round'; X2.lineCap = 'round'; X2.strokeStyle = col; X2.lineWidth = lw;
          for (let j = 0; j < NB; j++) { X2.beginPath(); lines.forEach(l => polyline(l, lonC + LONS[j], X2)); X2.stroke(); }
          return L2; };
        if (SK > 0 && GR > 0) { const L2 = acc(GRAT.map(l => part(l, GR)), 'rgb(169,204,245)', 1.4); wx.globalAlpha = SK * 0.10; wx.drawImage(L2, 0, 0); }
        if (SK > 0) { const L2 = acc(COASTS, COAST, 1.5); wx.globalAlpha = SK * 0.62; wx.drawImage(L2, 0, 0); }
      } else {
      if (SK > 0 && GR > 0) { wx.beginPath(); GRAT.forEach(l => polyline(part(l, GR), lonC)); wx.globalAlpha = SK; wx.strokeStyle = 'rgba(169,204,245,0.10)'; wx.lineWidth = 1.4; wx.stroke(); }
      if (SK > 0) { wx.beginPath(); COASTS.forEach(l => polyline(l, lonC)); wx.strokeStyle = COAST; wx.globalAlpha = 0.62 * SK; wx.lineWidth = 1.5; wx.stroke(); }
      }
      wx.restore();
      return wk;
    }
    function draw(lonC, k) {
      k = k || {}; const SK = k.sk != null ? k.sk : 1, OC = k.oc != null ? k.oc : 1;
      render(lonC, false, k);
      ctx.clearRect(0, 0, W, W); ctx.globalAlpha = OC;                                     // glow rides with the ocean fill
      const gl = ctx.createRadialGradient(W / 2, W / 2, R * 0.92, W / 2, W / 2, R + M);   // soft outer glow
      const gc = hex(C.land || '#4C9CEB');
      gl.addColorStop(0, `rgba(${gc[0]},${gc[1]},${gc[2]},0.30)`); gl.addColorStop(0.35, `rgba(${gc[0]},${gc[1]},${gc[2]},0.12)`); gl.addColorStop(1, `rgba(${gc[0]},${gc[1]},${gc[2]},0)`);
      if (OC > 0) { ctx.fillStyle = gl; ctx.beginPath(); ctx.arc(W / 2, W / 2, R + M, 0, 7); ctx.fill(); }
      ctx.globalAlpha = 1; ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(wk, W / 2 - S / (2 * SS), W / 2 - S / (2 * SS), S / SS, S / SS);
      ctx.beginPath(); ctx.arc(W / 2, W / 2, R - 0.6, 0, 7); const rc = hex(C.land || '#4C9CEB'); ctx.strokeStyle = `rgba(${rc[0]},${rc[1]},${rc[2]},0.95)`; ctx.lineWidth = 1.6; ctx.globalAlpha = SK; ctx.stroke(); ctx.globalAlpha = 1;  // thin rim (skeleton)
    }
    return { el: wrap, canvas: cv, draw, render, fwd, lonCentreFor, R, W };
  }
  window.GLOBE = { create, buildMask, VERSION: '1.2' };
})();
