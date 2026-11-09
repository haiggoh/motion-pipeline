# Notices and licences

- **Our code:** Apache-2.0 (see `LICENSE`).
- **HyperFrames** (renderer, pinned 0.8.31): Apache-2.0 — https://github.com/heyimsylvester/hyperframes
- **GSAP 3.14.2** (used inside generated pages): Standard "No Charge" licence,
  https://gsap.com/standard-license — its clause "may not be used in tools that compete
  with Webflow" was reviewed; the user accepts the risk for a small tool with few users
  (decision recorded 2026-11-08).
- **Bundled fonts:** SIL Open Font License 1.1 only (Montserrat, Inter) — each face ships
  with its OFL file under `motion_pipeline/fonts/`. Client fonts are never committed to
  this repo; a project may reference one from its own gitignored `fonts/` folder (the
  menu shows a licence warning).
- **Map data** (sample project globe): Natural Earth 110m (public domain) via world-atlas
  (ISC), converted with the same approach as the source explainer project's geo tool.
- **Never published:** any client logos, copy, voiceover, SFX, or a client brand's
  measured background constants — `tools/audit_assets.py` (Task 12) fails the build if any
  tracked file matches those patterns.
