"""0.8.1 spec item 1 (user crash report 2026-11-23): a project WITHOUT a fonts config used the
bundled-Montserrat fallback, but generate() took the BARE role map (relative
'motion_pipeline/fonts/...' refs) and shutil.copy'd them — crashing with FileNotFoundError
unless CWD happened to be the repo root. The menu also surfaced
'font gate: project.json has no fonts.family' as an error on such projects.

RED before the fix: the fallback role map carries non-absolute refs; generate from a
foreign CWD crashes; the fonts screen shows the error text.
"""
import os

import pytest
from projfix import make_project

from motion_pipeline import fonts as fonts_mod
from motion_pipeline import generate
from motion_pipeline import project as project_mod


def _fontsless_project(tmp_path):
    pd = make_project(str(tmp_path / 'proj'))
    p = project_mod.load(pd)
    p['fonts'] = {}
    project_mod.save(pd, p)
    return pd


def test_bundled_fallback_role_map_files_are_absolute_and_exist(tmp_path):
    pd = _fontsless_project(tmp_path)
    roles = fonts_mod.resolve_role_map(pd, {'family': 'Montserrat'})
    assert roles, 'fallback role map empty'
    for role, r in roles.items():
        assert os.path.isabs(r['file']), f'{role}: ref not absolute: {r["file"]}'
        assert os.path.isfile(r['file']), f'{role}: missing on disk: {r["file"]}'


def test_generate_fonts_less_project_from_foreign_cwd(tmp_path, monkeypatch):
    pd = _fontsless_project(tmp_path)
    monkeypatch.chdir(tmp_path)          # NOT the repo root — this is the user's crash
    generate.generate(pd)                 # FileNotFoundError pre-fix
    src = os.path.join(pd, 'src')
    fonts_out = os.path.join(src, 'fonts')
    assert os.path.isdir(fonts_out) and os.listdir(fonts_out), 'faces not embedded'
    with open(os.path.join(src, 'scene_00_welcome.html')) as f:
        page = f.read()
    assert '@font-face' in page


@pytest.mark.asyncio
async def test_fonts_screen_shows_bundled_fallback_not_an_error(tmp_path):
    from motion_pipeline.tui.app import MenuApp
    from motion_pipeline.tui.fonts_screen import FontsScreen
    pd = _fontsless_project(tmp_path)
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = FontsScreen()
        app.push_screen(scr)
        await pilot.pause(0.5)
        err = str(scr.query_one('#error').render())
        assert 'font gate' not in err and 'fonts.family' not in err, err
