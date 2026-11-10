"""0.5.0 Task 4c: projects live where the user chose (asked once, remembered), never inside
the installed package (brew replaces libexec on upgrade); app.project_dir always means the
CURRENT project folder, and every screen reads/writes directly inside it (v0.4.x nested
schemes at <project>/<name>/scheme.json and the inputs screen wrote to PROJECTS/default)."""
import json
import os

import pytest
from textual.widgets import Input

from motion_pipeline import config
from motion_pipeline.tui.app import MenuApp, MenuScreen
from tui_probe import choose


async def test_first_run_asks_for_projects_root_and_remembers_it(fresh_config, tmp_path):
    root = tmp_path / 'myprojects'
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert type(app.screen).__name__ == 'FirstRunScreen'
        inp = app.screen.query_one('#root', Input)
        assert '~/motion-pipeline/projects' in inp.value  # suggested default, editable
        inp.value = str(root)
        await choose(pilot, app.screen, 'save')
        assert isinstance(app.screen, MenuScreen)
    assert json.loads((fresh_config / 'config.json').read_text())['projects_root'] == str(root)
    app2 = MenuApp()
    async with app2.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert isinstance(app2.screen, MenuScreen)  # asked once
        assert str(root) in str(app2.screen.query_one('#subtitle').render()) or \
            'myprojects' in str(app2.screen.query_one('#subtitle').render())


def test_config_dir_override_set_but_missing_fails_loudly(monkeypatch, tmp_path):
    monkeypatch.setenv('MP_CONFIG_DIR', str(tmp_path / 'nope'))
    with pytest.raises(ValueError, match='MP_CONFIG_DIR'):
        config.projects_root()


def test_package_internal_projects_root_is_refused():
    with pytest.raises(ValueError, match='inside the installed package'):
        config.set_projects_root(os.path.join(config.PKG_ROOT, 'projects'))


async def test_project_created_under_root_and_screens_write_inside_it(_isolated_config):
    app = MenuApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.push_screen(app.SCREENS['project']()); await pilot.pause()
        app.screen.query_one('#name', Input).value = 'acme'
        await choose(pilot, app.screen, 'create')
        proj = _isolated_config / 'acme'
        assert app.project_dir == str(proj) and (proj / 'project.json').is_file()
        assert config.last_project() == str(proj)
        app.pop_screen(); await pilot.pause()
        # colours save lands at <project>/scheme.json — not nested
        app.push_screen(app.SCREENS['colours']()); await pilot.pause()
        scr = app.screen
        for k, v in {'background_dark': '#0b1020', 'background_light': '#f4f6fb',
                     'accent': '#ff6a00', 'text': '#ffffff'}.items():
            scr.query_one(f'#{k}', Input).value = v
        await pilot.pause()
        await choose(pilot, scr, 'save')
        assert (proj / 'scheme.json').is_file(), os.listdir(proj)
        assert not any((proj / d).is_dir() and (proj / d / 'scheme.json').exists() for d in os.listdir(proj))
        app.pop_screen(); await pilot.pause()
        # inputs save uses the current project
        app.push_screen(app.SCREENS['inputs']()); await pilot.pause()
        app.screen.query_one('#transcript', Input).value = 'script.txt'
        await choose(pilot, app.screen, 'save')
        assert json.loads((proj / 'project.json').read_text())['transcript'] == 'script.txt'
    # next launch reopens the last project
    app2 = MenuApp()
    async with app2.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app2.project_dir == str(proj)


async def test_screens_refuse_to_save_without_a_project(_isolated_config):
    app = MenuApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.project_dir is None
        app.push_screen(app.SCREENS['inputs']()); await pilot.pause()
        await choose(pilot, app.screen, 'save')
        assert 'step 0' in str(app.screen.query_one('#error').render())
        assert os.listdir(_isolated_config) == []
