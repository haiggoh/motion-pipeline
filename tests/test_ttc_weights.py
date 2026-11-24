"""0.8.3 bug 1 (user, 2026-11-24: 'font weight selection doesn't stick'): every face of a .ttc
collection read as weight 400 — read_os2_weight looked for the table directory at byte 12 of the
FILE instead of byte 12 of the face. Faces in .ttf files were fine, so only collections broke."""
from ttc_fixture import BOLD, REGULAR, SEMIBOLD, build_ttc, os2_weights

from motion_pipeline import font_index


def test_fixture_instrument_has_two_distinct_weights(tmp_path):
    p = build_ttc(str(tmp_path / 'f' / 'Duo.ttc'), [REGULAR, BOLD])
    assert os2_weights(p) == [400, 700]


def test_read_os2_weight_reads_each_ttc_face(tmp_path):
    p = build_ttc(str(tmp_path / 'f' / 'Duo.ttc'), [REGULAR, BOLD])
    assert font_index.read_os2_weight(p, 0) == 400
    assert font_index.read_os2_weight(p, 1) == 700


def test_read_os2_weight_single_ttf_unchanged():
    assert font_index.read_os2_weight(BOLD, 0) == 700
    assert font_index.read_os2_weight(REGULAR, 0) == 400


def test_scan_reports_real_weights_for_ttc_faces(tmp_path):
    d = tmp_path / 'f'
    build_ttc(str(d / 'Duo.ttc'), [REGULAR, BOLD])
    faces = font_index.scan(dirs=[str(d)], cache_path=str(tmp_path / 'cache.json'))
    got = sorted((f['index'], f['style'], f['weight']) for f in faces)
    assert got == [(0, 'Regular', 400), (1, 'Bold', 700)], got


def test_missing_os2_weight_inferred_from_style_name(tmp_path):
    """No OS/2 table: the weight comes from the style name, never a silent 400 for 'Bold'."""
    d = tmp_path / 'f'
    build_ttc(str(d / 'NoOS2.ttc'), [REGULAR, BOLD], strip_os2=(1,))
    assert font_index.read_os2_weight(str(d / 'NoOS2.ttc'), 1) is None
    faces = font_index.scan(dirs=[str(d)], cache_path=str(tmp_path / 'cache.json'))
    assert {f['style']: f['weight'] for f in faces} == {'Regular': 400, 'Bold': 700}


def test_style_fallback_prefers_the_longest_weight_word(tmp_path):
    """M1 QC: 'SemiBold' contains 'bold' — the table must be checked longest-first (600, not 700)."""
    d = tmp_path / 'f'
    build_ttc(str(d / 'Semi.ttc'), [REGULAR, SEMIBOLD], strip_os2=(1,))
    faces = font_index.scan(dirs=[str(d)], cache_path=str(tmp_path / 'cache.json'))
    assert {f['style']: f['weight'] for f in faces} == {'Regular': 400, 'SemiBold': 600}
    assert font_index.weight_from_style('Demi Bold') == 600
    assert font_index.weight_from_style('Extra Bold') == 800
    assert font_index.weight_from_style('Ultra Light Italic') == 200
