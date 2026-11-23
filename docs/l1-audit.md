# L1 audit — what enters the shared graphics library (Task 3, 0.8.0)

Rule (spec, verbatim): a helper enters L1 only if **(a) ≥2 existing projects use it, AND (b)
it contains no project-specific constant**. Audit result is this receipt. Existing projects
with `ai_graphics/`: the dogfood project (`~/motion-pipeline/projects/sevenone adf test
(dogfood)/src/ai_graphics/{welcome,explore}.js`) and P&G Cube One r04
(`pgcube-adapter/PGCubeOne_project/revisions/r04-regular-weights/src/**/lib.js`). The
shipped sample (`samples/globe`) has no `ai_graphics/`. MP API actually used across both:
`MP.tl` (18), `MP.at` (8), `MP.scene` (4), `MP.palette` (2), `MP.el` (1).

## Existing L1 surface — KEPT (additive compat; names and signatures unchanged)

`MP.el`, `MP.enter`, `MP.exit`, `MP.drawOn`, `MP.float`, `MP.inZone`, `MP.random`, `MP.at`
(`motion_pipeline/graphics/mp_lib.js:10-66`). Pinned by `tests/test_page_api.py`.

## Candidate set {sv, layer, text, tin, tout, icon} — verdict per helper

| Candidate | Used by | Brand constants | Verdict |
|---|---|---|---|
| `sv(tag, attrs, parent)` | P&G r04 only (shared/lib.js:20, partB/blue/lib.js:22, partC/blue/lib.js) | default stroke `C.blue` (tokens) | OUT — fails (a): 1 project; fails (b) |
| `layer(parent)` (svg 1920×1080) | P&G r04 only (shared/lib.js:21, partB:23) | hardcoded 1920×1080 viewBox | OUT — fails (a) and (b) |
| `text` (`T(p, text, x, y, o)`) | P&G r04 only (shared/lib.js:23, partB:24) | Inter/Montserrat families, `C.navy` | OUT — fails (a) and (b) |
| `tin` / `tout` | P&G r04 only (shared:35-36, partB:43-44) | eases from `K.ease`, `K.stagger` | OUT — fails (a) and (b) |
| `icon` (`ICON`) | P&G r04 only (shared:37, partB:45) | `K.icons` brand path data | OUT — fails (a) and (b) |

A helper used by P&G only stays in P&G (HF namespace, brand glue: `HF.setup`, `unitHeading`,
`scene` transitions, `K.zone` clip rects — all brand).

## Dogfood re-implementations (found while reading, because mp_lib.js 404'd until Task 1)

| Pattern | Where | Verdict |
|---|---|---|
| local mulberry32 PRNG | welcome.js:19-27, explore.js:14-22 (identical) | already exists as `MP.random` (mp_lib.js:58) — migrations use it, no new helper |
| `shape(cx, cy, r, style)` div factory | welcome.js:41-49, explore.js:36-44 | OUT — 1 project |
| full-frame div layer + arming (`document.fonts.ready`) | welcome.js:36-39,122-126, explore.js:31-34,111-115 | OUT — 1 project; the arming order is documented in the playbook instead |

## Conclusion

No candidate passes rule (a): the two graphics-bearing projects use disjoint helper sets, and
every P&G helper carries brand constants. **L1 adds nothing new; the surface is the 7 existing
helpers + `MP.at`.** The Task 3 rewrite therefore (1) keeps every name/signature, (2) enforces
the placement rules on those helpers — explicit absolute position (3rd timeline arg, never
vars `delay`) and finite `repeat` only (no `repeat: -1`, which sets gsap's 10^10 duration
marker and buries later tweens — measured, see welcome.js:8-9) — and (3) is pinned by
placement-rule tests in `tests/test_mp_lib_rules.py`. The declarative `shapes:` vocabulary
(Task 6) becomes the second consumer when Task 7 migrates the dogfood project onto it.
