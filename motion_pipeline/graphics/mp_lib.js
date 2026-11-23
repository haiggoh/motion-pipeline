/* mp_lib.js — P&G-style animation helpers for AI graphics, all on window.MP.tl (the scene's
 * registered paused timeline). Never create your own timeline; never use rAF/setTimeout/Date/
 * unseeded Math.random or the network — the renderer seeks frames deterministically.
 * Loaded by the generator BEFORE any ai_graphics script (Task 22).
 *
 * Placement rules (0.8.0 — audited in docs/l1-audit.md, pinned by tests/test_mp_lib_rules.py):
 *   1. Every tween goes on MP.tl at an EXPLICIT ABSOLUTE position (the call's last argument) —
 *      never through a vars delay, which appends at the timeline end and buries later tweens.
 *   2. The repeat count is always finite — the -1 marker sets gsap's 10^10 duration and
 *      buries anything appended afterwards (measured against the vendored gsap 3.14.2).
 */
(() => {
  const MP = window.MP;
  if (!MP) { console.error('MP_LIB_NO_MP'); return; }
  const at = (ref, offset) => MP.at(ref, offset || 0);

  MP.el = (tag, style, parent, html) => {
    const el = document.createElement(tag);
    if (style) Object.assign(el.style, style);
    if (html != null) el.innerHTML = html;
    (parent || document.getElementById('root')).appendChild(el);
    return el;
  };

  MP.enter = (el, ref, o) => {
    o = o || {};
    MP.tl.fromTo(el, { opacity: 0, y: o.y != null ? o.y : 24 },
                 { opacity: 1, y: 0, duration: o.d != null ? o.d : 0.5, ease: o.ease || 'power2.out' },
                 at(ref, o.at));
    return el;
  };

  MP.exit = (el, ref, o) => {
    o = o || {};
    MP.tl.to(el, { opacity: 0, duration: o.d != null ? o.d : 0.3, ease: 'power2.in' }, at(ref, o.at));
    return el;
  };

  MP.drawOn = (svgEl, ref, o) => {
    o = o || {};
    if (!window.DrawSVGPlugin) { console.error('MP_DRAWSVG_MISSING'); return svgEl; }
    MP.tl.fromTo(svgEl, { drawSVG: '0%' }, { drawSVG: '100%', duration: o.d != null ? o.d : 0.8,
                                            ease: o.ease || 'power1.inOut' }, at(ref, o.at));
    return svgEl;
  };

  MP.float = (el, fromRef, toRef, o) => {
    o = o || {};
    const a = at(fromRef), b = at(toRef);
    const span = Math.max(0.01, b - a);
    const fdur = Math.max(0.2, span * (o.per || 0.5));
    const amp = o.amp != null ? o.amp : 6;
    MP.tl.to(el, { y: `+=${amp}`, duration: fdur, yoyo: true,
                   repeat: Math.max(1, Math.ceil(span / fdur) - 1), ease: 'sine.inOut' }, a);
    return el;
  };

  MP.inZone = (el, i) => {
    i = i || 0;
    const z = (MP.zones || [])[i];
    if (!z) { console.error(`MP_ZONE_MISSING ${i}`); return el; }
    Object.assign(el.style, { position: 'absolute', left: `${z[0]}px`, top: `${z[1]}px`,
                              width: `${z[2]}px`, height: `${z[3]}px` });
    return el;
  };

  // deterministic PRNG (mulberry32) — the renderer seeks frames, so Math.random is banned
  MP.random = (seed) => {
    let a = seed >>> 0;
    return () => {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };
})();
