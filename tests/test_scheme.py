"""Task 2 tests: scheme validation, OKLab derivation, contrast floors, round-trip."""
import json

import pytest

from motion_pipeline.scheme import (PALETTE_KEYS, contrast, derive_palette, load_scheme,
                                    mix, save_scheme, validate_scheme)

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
