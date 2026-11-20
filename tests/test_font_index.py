"""Task 7 (plan 2026-11-16): font_index — recursive scan, real OS/2 weights, cache, loud env."""
import os
import shutil

import pytest
from PIL import ImageFont

from motion_pipeline import font_index
from motion_pipeline.font_index import BUNDLED_DIR

MONTSERRAT_SEMIBOLD = os.path.join(BUNDLED_DIR, 'Montserrat', 'Montserrat-SemiBold.ttf')
INTER_BOLD = os.path.join(BUNDLED_DIR, 'Inter', 'Inter-Bold.otf')


def test_recursive_scan_finds_nested_family(tmp_path):
    nested = tmp_path / 'Fonts' / 'Vendor_2024'
    nested.mkdir(parents=True)
    shutil.copy(MONTSERRAT_SEMIBOLD, nested / 'X.ttf')
    faces = font_index.scan(dirs=[str(tmp_path)], cache_path=str(tmp_path / 'cache.json'))
    assert any('Montserrat' in f['family'] for f in faces), faces


def test_ttc_all_faces_indexed(tmp_path):
    ttc = '/System/Library/Fonts/Helvetica.ttc'
    if not os.path.exists(ttc):
        pytest.skip('Helvetica.ttc not present')
    d = tmp_path / 'fonts'
    d.mkdir()
    os.symlink(ttc, d / 'Helvetica.ttc')
    faces = font_index.scan(dirs=[str(d)], cache_path=str(tmp_path / 'c.json'))
    helv = [f for f in faces if 'Helvetica' in f['family']]
    assert len(helv) > 1 and len({f['index'] for f in helv}) > 1, helv


def test_os2_weight_read():
    assert font_index.read_os2_weight(MONTSERRAT_SEMIBOLD, 0) == 600
    assert font_index.read_os2_weight(INTER_BOLD, 0) == 700
    assert font_index.read_os2_weight('/nonexistent.ttf', 0) is None


def test_weight_label():
    f = {'family': 'X', 'style': 'SemiBold', 'weight': 600, 'italic': False, 'path': 'p', 'index': 0, 'bundled': False}
    assert font_index.weight_label(f) == 'SemiBold (600)'
    f2 = dict(f, style='')
    assert font_index.weight_label(f2) == 'SemiBold (600)'  # CSS name table fallback
    f3 = dict(f, style='', weight=250)
    assert font_index.weight_label(f3) == '250 (250)'


def test_families_sorted_weight_upright_first():
    faces = [
        {'family': 'X', 'style': 'Bold', 'weight': 700, 'italic': False, 'path': 'p', 'index': 0, 'bundled': False},
        {'family': 'X', 'style': 'Regular', 'weight': 400, 'italic': False, 'path': 'p', 'index': 0, 'bundled': False},
        {'family': 'X', 'style': 'Bold Italic', 'weight': 700, 'italic': True, 'path': 'p', 'index': 1, 'bundled': False},
    ]
    fams = font_index.families(faces)
    assert [f['weight'] for f in fams['X']] == [400, 700, 700]
    assert fams['X'][1]['italic'] is False and fams['X'][2]['italic'] is True


def test_families_hides_apple_private_dot_families():
    # Apple marks private UI/fallback families with a leading '.' (e.g. .SF NS, .Al Bayan PUA);
    # Font Book hides them — the menu must too (spec A6). The cache keeps them.
    def face(fam):
        return {'family': fam, 'style': 'Regular', 'weight': 400, 'italic': False,
                'path': 'p', 'index': 0, 'bundled': False}
    faces = [face('.SF NS'), face('.Al Bayan PUA'), face('Arial')]
    fams = font_index.families(faces)
    assert list(fams) == ['Arial']
    assert len(font_index.families(faces, include_hidden=True)) == 3


def test_cache_hit_opens_no_font(tmp_path):
    d = tmp_path / 'fonts'
    d.mkdir()
    shutil.copy(MONTSERRAT_SEMIBOLD, d / 'X.ttf')
    cache = str(tmp_path / 'cache.json')
    first = font_index.scan(dirs=[str(d)], cache_path=cache)
    assert first
    calls = {'n': 0}
    real = ImageFont.truetype

    def counting(*a, **k):
        calls['n'] += 1
        return real(*a, **k)

    import motion_pipeline.font_index as fi
    # attribute swap for the warm-scan assertion (must un-patch in finally)
    old = fi.ImageFont.truetype
    fi.ImageFont.truetype = counting
    try:
        second = font_index.scan(dirs=[str(d)], cache_path=cache)
    finally:
        fi.ImageFont.truetype = old
    assert second == first
    assert calls['n'] == 0, f'warm scan opened {calls["n"]} fonts'


def test_bad_font_dirs_env_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setenv('MP_FONT_DIRS', str(tmp_path / 'does-not-exist-xyz'))
    with pytest.raises(ValueError, match='MP_FONT_DIRS'):
        font_index.scan(cache_path=str(tmp_path / 'c.json'))


def test_sevenone_found_when_installed(tmp_path):
    e3 = '/Library/Fonts/P7S1_Hausschriften_2024_2'
    if not os.path.isdir(e3):
        pytest.skip('SevenOne fonts not installed on this Mac')
    faces = font_index.scan(dirs=['/Library/Fonts'], cache_path=str(tmp_path / 'c.json'))
    seven = [f for f in faces if f['family'] == 'SevenOne Highlight TT']
    assert sorted({f['weight'] for f in seven}) == [600, 800], seven
