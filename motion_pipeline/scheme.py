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
        'particle_colour': accent,
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
