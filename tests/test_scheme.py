"""Task 2 tests: scheme validation, OKLab derivation, contrast floors, round-trip."""
import json
import os

import pytest

from motion_pipeline.scheme import (
    CONTRAST_TEXT,
    PALETTE_KEYS,
    _hex_to_srgb,
    contrast,
    contrast_failures,
    derive_palette,
    load_scheme,
    mix,
    resolve_variant,
    save_scheme,
    srgb_to_oklab,
    suggest_contrast_fix,
    validate_scheme,
    variant_path,
)

DARK = {'name': 'demo-dark', 'background_dark': '#0b1a4c', 'background_light': '#1251a6',
        'accent': '#ffb400', 'text': '#f5f7ff'}
LIGHT = {'name': 'demo-light', 'background_dark': '#f4f6fb', 'background_light': '#c9d6f2',
         'accent': '#0b3d91', 'text': '#101828'}


def test_palette_has_exactly_the_pinned_keys():
    p = derive_palette(DARK)
    assert set(p.keys()) == set(PALETTE_KEYS)
    assert p['gradient_stops'] == [DARK['background_dark'], DARK['background_light']]
    assert p['highlight_bar'] == DARK['accent']
    assert p['particle_colour'] == '#635955'  # accent mixed toward the background


def test_golden_dark_scheme():
    p = derive_palette(DARK)
    assert p == {
        'background_dark': '#0b1a4c', 'background_light': '#1251a6', 'accent': '#ffb400',
        'text': '#f5f7ff', 'secondary_text': '#a6b0c8', 'label_tint': '#a17f4e',
        'particle_colour': '#635955', 'highlight_bar': '#ffb400',
        'gradient_stops': ['#0b1a4c', '#1251a6'],
    }


def test_golden_light_scheme():
    p = derive_palette(LIGHT)
    assert p == {
        'background_dark': '#f4f6fb', 'background_light': '#c9d6f2', 'accent': '#0b3d91',
        'text': '#101828', 'secondary_text': '#4b5261', 'label_tint': '#5c7eb8',
        'particle_colour': '#94abd3', 'highlight_bar': '#0b3d91',
        'gradient_stops': ['#f4f6fb', '#c9d6f2'],
    }
    # light scheme must pass the same contrast floors (design §8a)
    assert contrast(p['text'], p['background_dark']) >= 4.5


def test_contrast_floor_violation_names_the_pair():
    bad = dict(DARK, text='#0b1a4c')  # dark text on dark background
    with pytest.raises(ValueError, match=r'contrast text on background_dark.*#0b1a4c'):
        derive_palette(bad)


def test_accent_contrast_floor_is_enforced():
    bad = dict(DARK, accent='#1a2a6c')  # low-contrast accent on the dark background
    with pytest.raises(ValueError, match=r'contrast accent on background_dark.*3\.0'):
        derive_palette(bad)


def test_save_refuses_contrast_violation(tmp_path):
    p = tmp_path / 'scheme.json'
    with pytest.raises(ValueError, match='contrast'):
        save_scheme(str(p), dict(DARK, text='#0b1a4c'))
    assert not p.exists()


def test_invalid_hex_fails_loudly():
    with pytest.raises(ValueError, match='invalid hex'):
        derive_palette(dict(DARK, accent='blue'))
    with pytest.raises(ValueError, match='missing key'):
        validate_scheme({'name': 'x'})


def test_mix_midpoint_black_white_is_mid_grey():
    # OKLab L=0.5 maps to sRGB ~0x63 (darker than sRGB 0.5 because of the transfer curve)
    assert mix('#000000', '#ffffff', 0.5) == '#636363'


def test_scheme_file_round_trip(tmp_path):
    p = tmp_path / 'scheme.json'
    save_scheme(str(p), DARK)
    assert load_scheme(str(p)) == DARK
    with open(p) as f:
        assert json.load(f) == DARK


# ---- Task 11 (spec B1 second half): contrast failures, smallest-change fix, override ----

def test_contrast_failures_user_case():
    """text #ffff54 on #ffffff is the user's reported 1.07:1 case."""
    s = {'name': 'x', 'background_dark': '#ffffff', 'background_light': '#1251a6',
         'accent': '#ffb400', 'text': '#ffff54'}
    f = contrast_failures(s)
    roles = {d['role'] for d in f}
    assert 'text' in roles
    entry = next(d for d in f if d['role'] == 'text')
    assert abs(entry['ratio'] - 1.07) < 0.03, entry
    assert entry['floor'] == 4.5
    assert entry['fg_key'] == 'text' and entry['bg_key'] == 'background_dark'


def test_contrast_failures_empty_when_both_pass():
    assert contrast_failures(dict(DARK)) == []


def test_suggest_fix_user_case_passes_both_floors():
    s = {'name': 'x', 'background_dark': '#ffffff', 'background_light': '#1251a6',
         'accent': '#ffb400', 'text': '#ffff54'}
    fix = suggest_contrast_fix(s)
    assert fix, 'no fix suggested'
    applied = dict(s)
    for e in fix:
        assert e['old'] == s[e['key']]
        applied[e['key']] = e['new']
    assert contrast_failures(applied) == [], applied


def test_suggest_fix_prefers_smallest_change():
    # only text fails; a text move and a background move both exist — take the smaller |dL|
    s = {'name': 'x', 'background_dark': '#202020', 'background_light': '#1251a6',
         'accent': '#ffb400', 'text': '#303030'}      # dark text on dark bg
    fix = suggest_contrast_fix(s)
    assert fix and contrast_failures({**s, **{e['key']: e['new'] for e in fix}}) == []
    # the suggested move is small (not a jump to pure black/white)
    if fix[0]['key'] == 'text':
        L_old = srgb_to_oklab(_hex_to_srgb(fix[0]['old']))[0]
        L_new = srgb_to_oklab(_hex_to_srgb(fix[0]['new']))[0]
        assert abs(L_new - L_old) < 0.35, (L_old, L_new)


def test_suggest_fix_does_not_break_the_other_pair():
    """The cheapest move for one pair must be discarded when it breaks the other."""
    # accent barely passes; a big background move would push accent under 3:1
    s = {'name': 'x', 'background_dark': '#5a5a5a', 'background_light': '#1251a6',
         'accent': '#7a7a7a', 'text': '#606060'}
    fix = suggest_contrast_fix(s)
    assert fix
    applied = {**s, **{e['key']: e['new'] for e in fix}}
    assert contrast_failures(applied) == [], (fix, applied)


def test_suggest_fix_uses_each_roles_own_floor():
    """Review finding: text fails (needs 4.5) while accent passes at 3.5 (> its 3.0 floor) —
    a fix must still be suggested; and a candidate breaking the OTHER pair's floor is rejected."""
    # accent passes at ~3.5, text fails hard on the dark bg
    s = {'name': 'x', 'background_dark': '#0b1a4c', 'background_light': '#1251a6',
         'accent': '#ffb400', 'text': '#1a2a6b'}     # text dark-on-dark -> fails 4.5
    fix = suggest_contrast_fix(s)
    assert fix, 'no fix suggested although accent passes at >3:1'
    applied = {**s, **{e['key']: e['new'] for e in fix}}
    f = contrast_failures(applied)
    assert f == [] or all(d['ratio'] >= d['floor'] - 1e-9 for d in f)  # floors are per-role
    # and the text floor must actually hold after applying
    assert contrast(applied['text'], applied['background_dark']) >= CONTRAST_TEXT


def test_suggest_fix_empty_when_unfixable():
    # text == accent == background: moving one colour alone cannot satisfy both floors?
    s = {'name': 'x', 'background_dark': '#808080', 'background_light': '#1251a6',
         'accent': '#808080', 'text': '#808080'}
    fix = suggest_contrast_fix(s)
    # whatever it suggests must actually work
    if fix:
        assert contrast_failures({**s, **{e['key']: e['new'] for e in fix}}) == []
    else:
        assert fix == []


def test_derive_palette_override_warns_instead_of_raising():
    s = {'name': 'x', 'background_dark': '#ffffff', 'background_light': '#1251a6',
         'accent': '#ffb400', 'text': '#ffff54', 'contrast_override': True}
    warns = []
    p = derive_palette(s, warn=warns.append)
    assert set(p) == set(PALETTE_KEYS)                      # keys are PINNED
    assert len(warns) == len(contrast_failures(s))
    assert any('override' in w for w in warns), warns


def test_derive_palette_without_override_still_raises():
    s = {'name': 'x', 'background_dark': '#ffffff', 'background_light': '#1251a6',
         'accent': '#ffb400', 'text': '#ffff54'}
    with pytest.raises(ValueError, match='contrast'):
        derive_palette(s)


def test_validate_scheme_rejects_non_bool_override():
    with pytest.raises(ValueError, match='contrast_override'):
        validate_scheme(dict(DARK, contrast_override='yes'))


def test_save_scheme_strips_override_when_colours_pass(tmp_path):
    p = tmp_path / 'scheme.json'
    save_scheme(str(p), dict(DARK, contrast_override=True))   # colours pass -> flag dropped
    assert json.load(open(p)) == DARK


def test_save_scheme_keeps_override_when_colours_fail(tmp_path):
    p = tmp_path / 'scheme.json'
    s = {'name': 'x', 'background_dark': '#ffffff', 'background_light': '#1251a6',
         'accent': '#ffb400', 'text': '#ffff54', 'contrast_override': True}
    save_scheme(str(p), s)
    assert json.load(open(p))['contrast_override'] is True


def test_variant_overlay_carries_its_own_flag(tmp_path):
    d = str(tmp_path / 'proj')
    os.makedirs(d, exist_ok=True)
    save_scheme(os.path.join(d, 'scheme.json'), DARK)          # passing base
    overlay = {'background_dark': '#ffffff', 'text': '#ffff54', 'contrast_override': True}
    os.makedirs(os.path.dirname(variant_path(d, 'loud')), exist_ok=True)
    with open(variant_path(d, 'loud'), 'w') as f:
        json.dump(overlay, f)
    resolved = resolve_variant(d, 'loud')
    assert resolved['contrast_override'] is True               # overlay's flag wins
    warns = []
    derive_palette(resolved, warn=warns.append)                # fails -> warns, no raise
    assert warns
    # a PASSING variant over a flagged base never warns
    save_scheme(os.path.join(d, 'scheme.json'),
                dict(DARK, background_dark='#ffffff', text='#ffff54', contrast_override=True))
    os.makedirs(os.path.dirname(variant_path(d, 'calm')), exist_ok=True)
    with open(variant_path(d, 'calm'), 'w') as f:
        json.dump({'background_dark': '#0b1a4c', 'text': '#f5f7ff'}, f)
    warns2 = []
    derive_palette(resolve_variant(d, 'calm'), warn=warns2.append)
    assert warns2 == []
