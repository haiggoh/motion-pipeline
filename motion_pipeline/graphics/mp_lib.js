/* mp_lib.js — P&G-style animation helpers for AI graphics, all on window.MP.tl (the scene's
 * registered paused timeline). Never create your own timeline; never use rAF/setTimeout/Date/
 * unseeded Math.random or the network — the renderer seeks frames deterministically.
 * Loaded by the generator BEFORE any ai_graphics script (Task 22). */
(function () {
  const MP = window.MP;
  if (!MP) { console.error('MP_LIB_NO_MP'); return; }
  const at = (ref, offset) => MP.at(ref, offset || 0);

  MP.el = function (tag, style, parent, html) {
    const el = document.createElement(tag);
    if (style) Object.assign(el.style, style);
    if (html != null) el.innerHTML = html;
    (parent || document.getElementById('root')).appendChild(el);
    return el;
  };

  MP.enter = function (el, ref, o) {
    o = o || {};
    const t = at(ref, o.at);
    MP.tl.fromTo(el, { opacity: 0, y: o.y != null ? o.y : 24 },
                 { opacity: 1, y: 0, duration: o.d != null ? o.d : 0.5, ease: o.ease || 'power2.out', delay: t });
    return el;
  };

  MP.exit = function (el, ref, o) {
    o = o || {};
    MP.tl.to(el, { opacity: 0, duration: o.d != null ? o.d : 0.3, ease: 'power2.in', delay: at(ref) });
    return el;
  };

  MP.drawOn = function (svgEl, ref, o) {
    o = o || {};
    if (!window.DrawSVGPlugin) { console.error('MP_DRAWSVG_MISSING'); return svgEl; }
    MP.tl.fromTo(svgEl, { drawSVG: '0%' }, { drawSVG: '100%', duration: o.d != null ? o.d : 0.8,
                                            ease: o.ease || 'power1.inOut', delay: at(ref) });
    return svgEl;
  };

  MP.float = function (el, fromRef, toRef, o) {
    o = o || {};
    const a = at(fromRef), b = at(toRef);
    MP.tl.to(el, { y: '+=' + (o.amp != null ? o.amp : 6), duration: Math.max(0.01, b - a) * (o.per || 0.5),
                   yoyo: true, repeat: -1, ease: 'sine.inOut', delay: a });
    return el;
  };

  MP.inZone = function (el, i) {
    i = i || 0;
    const z = (MP.zones || [])[i];
    if (!z) { console.error('MP_ZONE_MISSING ' + i); return el; }
    Object.assign(el.style, { position: 'absolute', left: z[0] + 'px', top: z[1] + 'px',
                              width: z[2] + 'px', height: z[3] + 'px' });
    return el;
  };

  // deterministic PRNG (mulberry32) — the renderer seeks frames, so Math.random is banned
  MP.random = function (seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };
})();
