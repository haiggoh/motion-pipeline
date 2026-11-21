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


def normalise_hex(h):
    """Canonical '#rrggbb'. Accepts the user-friendly bare 6-hex ('ffffff'), '#rrggbb', and
    the 3-digit short form ('fff'/'#FfF' -> each digit doubled, '#ffffff'); anything else
    raises ValueError naming the input. ONE place where the two parsers' disagreement (ours
    lstrip's '#', Textual's Color.parse requires it) is resolved — callers hand the result
    to anything that parses colours."""
    h = str(h).strip().lstrip('#')
    ok = '0123456789abcdefABCDEF'
    if len(h) == 6 and all(c in ok for c in h):
        return '#' + h.lower()
    if len(h) == 3 and all(c in ok for c in h):     # short form: fff -> #ffffff (B1)
        return '#' + ''.join(c * 2 for c in h.lower())
    raise ValueError(f"invalid hex colour {str(h)!r} (want #rrggbb, e.g. #ff6a00)")


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
    if 'contrast_override' in scheme and not isinstance(scheme['contrast_override'], bool):
        raise ValueError(f'contrast_override must be true or false, '
                         f'got {scheme["contrast_override"]!r}')
    return scheme


def contrast_failures(scheme):
    """The two contrast pairs (spec B1): [] when both pass, else one dict per failing pair
    {'role', 'fg_key', 'bg_key', 'ratio', 'floor'}."""
    out = []
    dark = scheme.get('background_dark')
    for role, fg_key, floor in (('text', 'text', CONTRAST_TEXT),
                                ('accent', 'accent', CONTRAST_ACCENT)):
        fg = scheme.get(fg_key)
        if not fg or not dark:
            continue
        c = contrast(fg, dark)
        if c < floor:
            out.append({'role': role, 'fg_key': fg_key, 'bg_key': 'background_dark',
                        'ratio': c, 'floor': floor})
    return out


def _oklab_L(hexv):
    return srgb_to_oklab(_hex_to_srgb(hexv))[0]


def _shift_L(hexv, dL):
    """Move a colour's OKLab lightness by dL, hue/chroma kept, clipped to the sRGB gamut."""
    L, a, b = srgb_to_oklab(_hex_to_srgb(hexv))
    return _srgb_to_hex(oklab_to_srgb(L + dL, a, b))


def _search_dL(hexv, direction, reaches):
    """Smallest |dL| >= 0 in the given direction (+1/-1) with _shift_L(hexv, d*|dL|) reaching
    the predicate; None when even |dL|=1 does not. Binary search on |dL| (monotonic)."""
    if reaches(_shift_L(hexv, direction * 1.0)):
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if reaches(_shift_L(hexv, direction * mid)):
                hi = mid
            else:
                lo = mid
        return hi
    return None


def suggest_contrast_fix(scheme):
    """Smallest-change contrast fix (spec B1, user: 'smallest change wins'). For each failing
    pair the candidates move the FOREGROUND's or background_dark's OKLab L in whichever
    direction increases contrast, keeping hue/chroma; the smallest |dL| whose application
    leaves EVERY pair passing wins. Returns a list of {'key', 'old', 'new'} (empty when
    nothing fails or no candidate works); when both pairs fail, one background_dark move
    that fixes both is preferred over two sequential moves."""
    failures = contrast_failures(scheme)
    if not failures:
        return []
    margin = 0.05
    FLOORS = (('text', CONTRAST_TEXT), ('accent', CONTRAST_ACCENT))

    def all_pass(target):
        """EVERY pair over ITS OWN floor (+margin) — one fix must not break the other pair."""
        return all(contrast(target[role], target['background_dark']) >= floor + margin
                   for role, floor in FLOORS)

    def best_move(target, key, direction):
        """Smallest |dL| moving target[key] in the given direction so all pairs pass."""
        hexv = target[key]

        def reaches(new_hex):
            s = dict(target)
            s[key] = new_hex
            return all_pass(s)

        return _search_dL(hexv, direction, reaches)

    def pair_candidates(target, fg_key):
        """(key, direction, dL) options for one failing pair: move the fg or the bg, in the
        direction that increases contrast (bg tried both ways)."""
        out = []
        fg, dark = target[fg_key], target['background_dark']
        lighter_fg = _oklab_L(fg) > _oklab_L(dark)
        for d in ((1, -1) if lighter_fg else (-1, 1)):
            mv = best_move(target, 'background_dark', d)
            if mv is not None:
                out.append(('background_dark', d, mv))
            mv = best_move(target, fg_key, d)
            if mv is not None:
                out.append((fg_key, d, mv))
        return out

    if len(failures) == 1:
        d = failures[0]
        cands = pair_candidates(scheme, d['fg_key'])
        if not cands:
            return []
        key, direction, dL = min(cands, key=lambda c: c[2])
        return [{'key': key, 'old': scheme[key], 'new': _shift_L(scheme[key], direction * dL)}]

    # both pairs fail: prefer ONE background_dark move that fixes both
    dark = scheme['background_dark']
    lighter_text = _oklab_L(scheme['text']) > _oklab_L(dark)
    for d in ((-1, 1) if lighter_text else (1, -1)):
        def both_pass(new_dark):
            return all_pass(dict(scheme, background_dark=new_dark))
        dL = _search_dL(dark, d, both_pass)
        if dL is not None:
            return [{'key': 'background_dark', 'old': dark, 'new': _shift_L(dark, d * dL)}]
    # sequential: fix the worst pair first against the WORKING scheme, then the rest
    working = dict(scheme)
    changes = []
    for _ in range(2):
        remaining = contrast_failures(working)
        if not remaining:
            return changes
        remaining.sort(key=lambda d: d['ratio'])
        d = remaining[0]
        cands = pair_candidates(working, d['fg_key'])
        if not cands:
            return []
        key, direction, dL = min(cands, key=lambda c: c[2])
        changes.append({'key': key, 'old': working[key], 'new': _shift_L(working[key], direction * dL)})
        working[key] = changes[-1]['new']
    return changes if not contrast_failures(working) else []


def derive_palette(scheme, warn=None):
    """scheme (validated) -> Palette dict with exactly PALETTE_KEYS. A failing pair raises
    unless contrast_override is true, in which case each failure is passed to warn
    (default: printed to stderr) and the palette is built anyway."""
    validate_scheme(scheme)
    dark, light, accent, text = (scheme[k] for k in INPUT_KEYS[1:])
    failures = contrast_failures(scheme)
    if failures:
        if scheme.get('contrast_override') is True:
            for d in failures:
                msg = (f"warning: contrast {d['role']} on background dark is {d['ratio']:.2f}:1"
                       f" < {d['floor']}:1 ({scheme[d['fg_key']]} on {dark})"
                       ' (override set in scheme.json)')
                if warn is not None:
                    warn(msg)
                else:
                    import sys
                    print(msg, file=sys.stderr)
        else:
            d = failures[0]
            raise ValueError(f'contrast {d["role"]} on background_dark is {d["ratio"]:.2f}:1 '
                             f'< {d["floor"]}:1 ({scheme[d["fg_key"]]} on {dark}) — raise '
                             f'contrast or darken the background')
    return {
        'background_dark': dark, 'background_light': light, 'accent': accent, 'text': text,
        'secondary_text': mix(text, dark, 0.30),
        'label_tint': mix(accent, dark, 0.35),
        'particle_colour': mix(accent, dark, 0.60),
        'highlight_bar': accent,
        'gradient_stops': [dark, light],
    }


def load_scheme(path):
    try:
        with open(path) as f:
            return validate_scheme(json.load(f))
    except OSError as e:
        # a missing/unreadable scheme.json must name the file (0.6.3 dogfood: generate()
        # crashed with a bare FileNotFoundError instead)
        raise ValueError(f'scheme.json missing or unreadable at {path}: {e}') from e


def save_scheme(path, scheme):
    validate_scheme(scheme)
    derive_palette(scheme)  # enforces the contrast floors (or warns under contrast_override)
    scheme = dict(scheme)
    if not contrast_failures(scheme):
        scheme.pop('contrast_override', None)   # a passing scheme is written WITHOUT the flag
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
    bad = sorted(set(ov) - set(COLOUR_KEYS) - {'contrast_override'})
    if bad:
        raise ValueError(f'{p}: keys {bad} are not colour keys {list(COLOUR_KEYS)}')
    for k, v in ov.items():
        if k == 'contrast_override':
            if not isinstance(v, bool):
                raise ValueError(f'{p}: contrast_override must be true or false, got {v!r}')
        else:
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
    resolved = validate_scheme(dict(base, **overlay, name=name))
    if contrast_failures(resolved):
        if full_colours.get('contrast_override') is not True:
            derive_palette(resolved)          # raises, naming the failing pair
        overlay['contrast_override'] = True   # Save anyway: the flag lives in the overlay
    else:
        derive_palette(resolved)
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
