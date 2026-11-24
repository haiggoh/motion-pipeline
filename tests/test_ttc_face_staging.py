"""0.8.3 bug 1, delivery half: the page referenced the WHOLE .ttc via @font-face, and a browser
cannot pick a face index from a collection — so a correctly saved 'Bold = face 1' still rendered
whichever face the browser took (face 0). generate() must stage the CHOSEN face as a standalone
font file."""
import os
import shutil

from fontTools.ttLib import TTFont
from projfix import make_project
from ttc_fixture import BOLD, REGULAR, build_ttc

from motion_pipeline import fonts as fonts_mod
from motion_pipeline import generate
from motion_pipeline import project as project_mod


def _ttc_project(tmp_path, headline_index):
    pd = make_project(str(tmp_path / 'proj'))
    os.makedirs(os.path.join(pd, 'fonts'), exist_ok=True)
    build_ttc(os.path.join(pd, 'fonts', 'Duo.ttc'), [REGULAR, BOLD])
    p = project_mod.load(pd)
    p['fonts'] = {'roles': {r: {'family': 'Montserrat', 'weight': 400, 'index': 0,
                                'file': 'fonts/Duo.ttc'} for r in fonts_mod.ROLES}}
    p['fonts']['roles']['headline'].update(weight=700, index=headline_index)
    project_mod.save(pd, p)
    return pd


def _staged(pd, role):
    d = os.path.join(pd, 'src', 'fonts')
    names = [n for n in os.listdir(d) if n.startswith(role + '-')]
    assert len(names) == 1, names
    return os.path.join(d, names[0])


def test_headline_ttc_face_1_is_staged_as_its_own_font(tmp_path):
    pd = _ttc_project(tmp_path, headline_index=1)
    generate.generate(pd)
    head, body = _staged(pd, 'headline'), _staged(pd, 'body')
    for path in (head, body):
        with open(path, 'rb') as f:
            assert f.read(4) != b'ttcf', f'{path}: still a collection — the browser cannot pick a face'
    assert TTFont(head)['OS/2'].usWeightClass == 700
    assert TTFont(body)['OS/2'].usWeightClass == 400
    page = open(os.path.join(pd, 'src', 'scene_00_welcome.html')).read()
    assert f"url('fonts/{os.path.basename(head)}')" in page


def test_extracted_face_keeps_every_glyph(tmp_path):
    """The extraction is not a lossy copy: same glyph set as the source face."""
    pd = _ttc_project(tmp_path, headline_index=1)
    generate.generate(pd)
    assert TTFont(_staged(pd, 'headline')).getGlyphOrder() == TTFont(BOLD).getGlyphOrder()


def test_single_face_files_are_copied_unchanged(tmp_path):
    pd = make_project(str(tmp_path / 'proj'))
    os.makedirs(os.path.join(pd, 'fonts'), exist_ok=True)
    shutil.copy(BOLD, os.path.join(pd, 'fonts', 'B.ttf'))
    p = project_mod.load(pd)
    p['fonts'] = {'roles': {r: {'family': 'Montserrat', 'weight': 700, 'index': 0,
                                'file': 'fonts/B.ttf'} for r in fonts_mod.ROLES}}
    project_mod.save(pd, p)
    generate.generate(pd)
    with open(_staged(pd, 'headline'), 'rb') as a, open(BOLD, 'rb') as b:
        assert a.read() == b.read()
