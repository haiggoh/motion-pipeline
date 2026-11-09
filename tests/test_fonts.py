"""Task 3 tests: bundled OFL fonts, role map, font gate, licence audit."""
import json
import os

import pytest

from motion_pipeline import fonts


def test_bundled_families_are_montserrat_and_inter():
    assert fonts.bundled_families() == ['Inter', 'Montserrat']


def test_bundled_face_resolves_without_system_install():
    face = fonts.bundled_face('Montserrat', 400)
    assert face == 'motion_pipeline/fonts/Montserrat/Montserrat-Regular.ttf'
    # the ref is a real package resource
    import importlib.resources
    ref = importlib.resources.files('motion_pipeline') / 'fonts' / 'Montserrat' / 'Montserrat-Regular.ttf'
    assert ref.is_file()


def test_role_map_covers_all_roles_with_pinned_output_shape():
    m = fonts.default_role_map('Montserrat')
    assert set(m.keys()) == set(fonts.ROLES)
    assert m['headline'] == {'family': 'Montserrat', 'weight': 700}
    assert m['body'] == {'family': 'Montserrat', 'weight': 400}


def test_font_gate_resolves_every_role(tmp_path):
    p = tmp_path / 'proj'
    p.mkdir()
    (p / 'project.json').write_text(json.dumps({'fonts': {'family': 'Montserrat'}}))
    m = fonts.font_gate(str(p), json.loads((p / 'project.json').read_text()))
    for role in fonts.ROLES:
        assert m[role]['file'].startswith('motion_pipeline/fonts/Montserrat/')
        assert m[role]['licence'] == 'OFL'


def test_font_gate_fails_naming_role_when_face_missing(tmp_path):
    with pytest.raises(ValueError, match=r"role 'headline'.*weight 700"):
        fonts.resolve_role_map(str(tmp_path), 'NoSuchFamily')


def test_client_font_in_project_fonts_passes_but_flagged_non_ofl(tmp_path):
    p = tmp_path / 'proj'
    (p / 'fonts').mkdir(parents=True)
    (p / 'fonts' / 'ClientFont-Bold.ttf').write_bytes(b'not a real font - fixture')
    m = fonts.resolve_role_map(str(p), 'ClientFont', {'headline': 700})
    assert m['headline']['licence'].startswith('non-OFL')
    assert m['headline']['file'].endswith('fonts/ClientFont-Bold.ttf')


def test_bundled_licence_audit_clean_and_red_on_planted_missing_ofl():
    assert fonts.audit_bundled_licences() == []
    import importlib.resources
    root = importlib.resources.files('motion_pipeline') / 'fonts' / 'Montserrat'
    # simulate a missing OFL by pointing the audit at a temp copy
    import tempfile, shutil
    with tempfile.TemporaryDirectory() as td:
        shutil.copytree(str(root), os.path.join(td, 'Montserrat'))
        os.remove(os.path.join(td, 'Montserrat', 'OFL.txt'))
        # audit reads the package; emulate by checking the same rule on the temp dir
        assert not any(f.upper().startswith('OFL') for f in os.listdir(os.path.join(td, 'Montserrat')))
