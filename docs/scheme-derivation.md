# Scheme derivation rules

Input keys: `name, background_dark, background_light, accent, text` (hex).
Derived in OKLab: `secondary_text = mix(text, dark, 0.30)`, `label_tint = mix(accent, dark,
0.35)`, `particle_colour = mix(accent, dark, 0.60)` (kept near the background chroma so dot
edges don't band — measured), `highlight_bar = accent`, `gradient_stops = [dark, light]`.
Contrast floors (fail loudly, naming the pair): text on background_dark >= 4.5:1, accent
>= 3.0:1. Works for light backgrounds too. Golden values pinned in tests/test_scheme.py.
