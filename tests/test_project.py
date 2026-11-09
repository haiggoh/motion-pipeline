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
