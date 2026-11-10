"""scheme.py — colour scheme model + OKLab derivation (Task 2).

A scheme file is JSON: {"name": str, "background_dark": hex, "background_light": hex,
"accent": hex, "text": hex} — the "few main colours" (G3). derive_palette() fills the
derived roles (Palette keys are pinned in the plan's "Pinned interfaces"):
  secondary_text, label_tint, particle_colour, highlight_bar, gradient_stops
Derivation rules (documented per G3):
  gradient_stops  = [background_dark, background_light]
  particle_colour = accent
  highlight_bar   = accent
  label_tint      = mix(accent, background_dark, 0.35)   (in OKLab)
  secondary_text  = mix(text, background_dark, 0.30)     (dimmed body text)
  particle_colour = mix(accent, background_dark, 0.60)   (dots stay close to the background
                                                         chroma — a full-accent dot edge would
                                                         band in the chroma gate, measured)
Contrast floors (fail loudly, naming the pair): text on background_dark >= 4.5:1,
accent on background_dark >= 3.0:1 (WCAG relative luminance).
"""
import json
import os

INPUT_KEYS = ('name', 'background_dark', 'background_light', 'accent', 'text')
PALETTE_KEYS = ('background_dark', 'background_light', 'accent', 'text',
                'secondary_text', 'label_tint', 'particle_colour', 'highlight_bar',
                'gradient_stops')
CONTRAST_TEXT = 4.5
CONTRAST_ACCENT = 3.0


def _hex_to_srgb(h):
    h = h.lstrip('#')
    if len(h) != 6 or any(c not in '0123456789abcdefABCDEF' for c in h):
        raise ValueError(f'invalid hex colour {h!r} (want #rrggbb)')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def hex_to_hsl(h):
    """#rrggbb -> (h 0-360, s 0-100, l 0-100)."""
    import colorsys
    r, g, b = _hex_to_srgb(h)
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return (round(hh * 360), round(ss * 100), round(ll * 100))


def hsl_to_hex(h, s, l):
    """(h 0-360, s 0-100, l 0-100) -> #rrggbb. Raises on out-of-range."""
    import colorsys
    h = float(h) % 360
    s = min(max(float(s), 0.0), 100.0) / 100.0
    li = min(max(float(l), 0.0), 100.0) / 100.0
    r, g, b = colorsys.hls_to_rgb(h / 360.0, li, s)
    return _srgb_to_hex((r, g, b))


def _srgb_to_hex(rgb):
    return '#' + ''.join(f'{round(min(max(c, 0.0), 1.0) * 255):02x}' for c in rgb)


def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c):
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def srgb_to_oklab(rgb):
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    lc = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = lc ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def oklab_to_srgb(L, a, b):
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    lc, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = +4.0767416621 * lc - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * lc + 2.6097574011 * m - 0.3413193965 * s
    b2 = -0.0041960863 * lc - 0.7034186147 * m + 1.7076147010 * s
    return tuple(_linear_to_srgb(c) for c in (r, g, b2))


def mix(hex_a, hex_b, t):
    """Mix two hex colours at t (0=a, 1=b) in OKLab; returns hex."""
    la = srgb_to_oklab(_hex_to_srgb(hex_a))
    lb = srgb_to_oklab(_hex_to_srgb(hex_b))
    return _srgb_to_hex(oklab_to_srgb(*(la[i] + (lb[i] - la[i]) * t for i in range(3))))


def _luminance(rgb):
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(hex_a, hex_b):
    la = _luminance(_hex_to_srgb(hex_a))
    lb = _luminance(_hex_to_srgb(hex_b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def validate_scheme(scheme):
    if not isinstance(scheme, dict):
        raise ValueError('scheme must be a JSON object')
    for k in INPUT_KEYS:
        if k not in scheme:
            raise ValueError(f'scheme missing key {k!r}')
    for k in INPUT_KEYS[1:]:
        _hex_to_srgb(scheme[k])  # raises on invalid hex
    return scheme


def derive_palette(scheme):
    """scheme (validated) -> Palette dict with exactly PALETTE_KEYS."""
    validate_scheme(scheme)
    dark, light, accent, text = (scheme[k] for k in INPUT_KEYS[1:])
    pairs = [('text', text, dark, CONTRAST_TEXT), ('accent', accent, dark, CONTRAST_ACCENT)]
    for role, fg, bg, floor in pairs:
        c = contrast(fg, bg)
        if c < floor:
            raise ValueError(f'contrast {role} on background_dark is {c:.2f}:1 < {floor}:1 '
                             f'({fg} on {bg}) — raise contrast or darken the background')
    return {
        'background_dark': dark, 'background_light': light, 'accent': accent, 'text': text,
        'secondary_text': mix(text, dark, 0.30),
        'label_tint': mix(accent, dark, 0.35),
        'particle_colour': mix(accent, dark, 0.60),
        'highlight_bar': accent,
        'gradient_stops': [dark, light],
    }


def load_scheme(path):
    with open(path) as f:
        return validate_scheme(json.load(f))


def save_scheme(path, scheme):
    validate_scheme(scheme)
    derive_palette(scheme)  # enforces the contrast floors: a set-but-invalid scheme fails loudly
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(scheme, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)


# --- colour variants as overlays (0.5.0 Task 4b, design §8a) ------------------------------
# <project>/scheme.json is the base scheme (variant "default"). Each extra variant is
# <project>/variants/<name>.json holding ONLY the colour keys it overrides; every other
# project setting (transcript, fonts, zones, timing) is shared, so variants never drift.
import re as _re

COLOUR_KEYS = INPUT_KEYS[1:]
_VARIANT_NAME = _re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')


def base_scheme_path(project_dir):
    return os.path.join(project_dir, 'scheme.json')


def variant_path(project_dir, name):
    return os.path.join(project_dir, 'variants', f'{name}.json')


def check_variant_name(name):
    if name == 'default' or not _VARIANT_NAME.match(name or ''):
        raise ValueError(f'invalid variant name {name!r}: want lowercase letters/digits/-/_ '
                         '(max 32), not "default"')
    return name


def load_overlay(project_dir, name):
    p = variant_path(project_dir, name)
    if not os.path.isfile(p):
        raise ValueError(f'unknown variant {name!r} (no {p})')
    with open(p) as f:
        ov = json.load(f)
    if not isinstance(ov, dict):
        raise ValueError(f'{p}: want a JSON object of colour overrides')
    bad = sorted(set(ov) - set(COLOUR_KEYS))
    if bad:
        raise ValueError(f'{p}: keys {bad} are not colour keys {list(COLOUR_KEYS)}')
    for k, v in ov.items():
        _hex_to_srgb(v)
    return ov


def resolve_variant(project_dir, variant='default'):
    """Base scheme with the variant's overrides applied (validated)."""
    base = load_scheme(base_scheme_path(project_dir))
    if variant == 'default':
        return dict(base, name='default')
    check_variant_name(variant)
    return validate_scheme(dict(base, **load_overlay(project_dir, variant), name=variant))


def save_variant(project_dir, name, full_colours):
    """Store ONLY the keys that differ from the base; enforce the contrast floors on the
    resolved scheme. Returns the overlay written."""
    check_variant_name(name)
    base = load_scheme(base_scheme_path(project_dir))
    overlay = {k: full_colours[k] for k in COLOUR_KEYS
               if k in full_colours and full_colours[k].lower() != base[k].lower()}
    for v in overlay.values():
        _hex_to_srgb(v)
    derive_palette(dict(base, **overlay, name=name))
    p = variant_path(project_dir, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(overlay, f, indent=2)
        f.write('\n')
    os.replace(tmp, p)
    return overlay


def list_variants(project_dir):
    d = os.path.join(project_dir, 'variants')
    names = sorted(f[:-5] for f in os.listdir(d) if f.endswith('.json')) if os.path.isdir(d) else []
    return ['default'] + names
