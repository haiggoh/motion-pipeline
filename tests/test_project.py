"""Task 5 tests: project.json validation (loud, key-naming) + defaults."""
import pytest

from motion_pipeline import project


def test_default_project_is_valid():
    p = project.default_project('demo')
    assert project.validate(p) == p
    assert p['resolution'] == [1920, 1080] and p['fps'] == 60 and p['aspect'] == '16:9'


def test_each_aspect_and_fps_and_uhd():
    for aspect, res in project.ASPECTS.items():
        p = project.default_project('d', aspect=aspect, fps=25)
        assert p['resolution'] == list(res)
        assert project.validate(p)
    assert project.validate(project.default_project('u', uhd=True))['resolution'] == [3840, 2160]


def test_invalid_values_fail_naming_the_key():
    with pytest.raises(ValueError, match="invalid aspect '3:2'"):
        project.validate(project.default_project('d', aspect='3:2'))
    bad = project.default_project('d')
    bad['fps'] = 24
    with pytest.raises(ValueError, match="invalid fps 24"):
        project.validate(bad)
    bad = project.default_project('d')
    bad['resolution'] = [1280, 720]  # 16:9, valid ratio but not a preset — now allowed
    assert project.validate(bad)  # any resolution matching the aspect is a valid setting
    bad['resolution'] = [1000, 1000]
    with pytest.raises(ValueError, match='invalid resolution'):
        project.validate(bad)
    bad = project.default_project('d')
    bad['zones'] = [{'section': 'intro'}]
    with pytest.raises(ValueError, match="zone missing key 'rect'"):
        project.validate(bad)
    bad = project.default_project('d')
    del bad['fps']
    with pytest.raises(ValueError, match="missing key 'fps'"):
        project.validate(bad)


def test_save_load_round_trip(tmp_path):
    d = tmp_path / 'projects' / 'demo'
    p = project.default_project('demo')
    project.save(str(d), p)
    assert project.load(str(d)) == p
    with pytest.raises(ValueError, match='no project.json'):
        project.load(str(tmp_path / 'projects' / 'nope'))


def test_zone_rect_and_aspect_validation_loud():
    p = project.default_project('d')  # 16:9 -> 1920x1080
    p['zones'] = [{'section': 'a', 'rect': [0, 0, 10, 'x']}]
    with pytest.raises(ValueError, match='integers'):
        project.validate(p)
    p['zones'] = [{'section': 'a', 'rect': [-1, 0, 10, 10]}]
    with pytest.raises(ValueError, match='>= 0'):
        project.validate(p)
    p['zones'] = [{'section': 'a', 'rect': [0, 0, 0, 10]}]
    with pytest.raises(ValueError, match='w,h > 0'):
        project.validate(p)
    p['zones'] = [{'section': 'a', 'rect': [0, 0, 10, 10], 'aspect': '3:2'}]
    with pytest.raises(ValueError, match='invalid zone aspect'):
        project.validate(p)
    p['zones'] = [{'section': 'a', 'rect': [1900, 0, 100, 100]}]
    with pytest.raises(ValueError, match='outside the 1920×1080 frame'):
        project.validate(p)
    # an INACTIVE-aspect zone is kept (Apply-format), not frame-checked against this aspect
    p['zones'] = [{'section': 'a', 'rect': [1900, 0, 100, 100], 'aspect': '9:16'}]
    assert project.validate(p)


def test_active_zones_aspect_filter():
    p = project.default_project('d')  # 16:9
    p['zones'] = [
        {'section': 'a', 'rect': [0, 0, 10, 10]},                    # legacy: no aspect -> active
        {'section': 'b', 'rect': [0, 0, 10, 10], 'aspect': '16:9'},   # active
        {'section': 'c', 'rect': [0, 0, 10, 10], 'aspect': '9:16'},   # inactive
    ]
    assert [z['section'] for z in project.active_zones(p)] == ['a', 'b']


# ---- Task 16 (B4): language defaults to auto ----

def test_default_project_language_is_auto():
    assert project.default_project('x')['language'] == 'auto'


def test_existing_project_keeps_saved_language(tmp_path):
    d = str(tmp_path / 'p')
    p = project.default_project('old')
    p['language'] = 'de'
    project.save(d, p)
    assert project.load(d)['language'] == 'de'   # untouched by the new default
    project.validate(project.default_project('new'))  # 'auto' validates
