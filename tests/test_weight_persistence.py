"""0.8.3 bug 1 (user, 2026-11-24): 'font weight selection doesn't stick — all 4 started as
regular, set one to bold, it stayed regular'. The 0.8.2-era repro of this flow went GREEN because
its fonts were single-face files; the real family (Avenir Next) is ONE .ttc whose faces differ
only by index. So the fixture here is a 3-face TTC: Regular 400 / Bold 700 / Condensed Bold 700
(two faces with the SAME weight — a weight-keyed picker cannot tell them apart)."""
import json
import os

import pytest
from ttc_fixture import BOLD, REGULAR, SEMIBOLD, build_ttc

from motion_pipeline import font_index
from motion_pipeline import project as project_mod
from motion_pipeline.tui.app import MenuApp

ROLES = ('headline', 'label', 'body', 'emphasis')


@pytest.fixture
def ttc_fonts(tmp_path, monkeypatch):
    d = tmp_path / 'fontdir'
    build_ttc(str(d / 'Trio.ttc'), [REGULAR, BOLD, SEMIBOLD],
              weights=[400, 700, 700], styles=['Regular', 'Bold', 'Condensed Bold'])
    monkeypatch.setattr(font_index, 'default_dirs', lambda: [str(d)])
    monkeypatch.setenv('MP_FONT_CACHE', str(tmp_path / 'font-index.json'))
    return d


async def _open_fonts(app, pilot):
    from motion_pipeline.tui.fonts_screen import FontsScreen
    scr = FontsScreen()
    app.push_screen(scr)
    for _ in range(100):
        await pilot.pause(0.05)
        if scr._all:
            break
    assert scr._all, 'font scan never finished'
    await pilot.pause(0.3)
    return scr


def _pick(scr, role, style):
    """Choose the option the USER sees as `style` (by its label), like a click would."""
    from textual.widgets import Select
    sel = scr.query_one(f'#role-{role}-weight', Select)
    matches = [v for prompt, v in sel._options if str(prompt).startswith(style + ' (')]
    assert len(matches) == 1, f'{role}: options {sel._options}'
    sel.value = matches[0]


def _shown(scr, role):
    from textual.widgets import Select
    sel = scr.query_one(f'#role-{role}-weight', Select)
    return next(str(p) for p, v in sel._options if v == sel.value)


def _saved_roles(pd):
    return json.load(open(os.path.join(pd, 'project.json')))['fonts']['roles']


async def test_setting_one_role_to_bold_sticks(tmp_path, ttc_fonts):
    pd = str(tmp_path / 'proj')
    project_mod.save(pd, project_mod.default_project('p'))
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_fonts(app, pilot)
        scr._set_role_family('headline', 'Montserrat')       # family chosen for every role
        for role in ROLES:
            scr._set_role_family(role, 'Montserrat')
            _pick(scr, role, 'Regular')                      # "all 4 started as regular"
        scr.on_action('save')
        await pilot.pause()
        assert {r: v['index'] for r, v in _saved_roles(pd).items()} == dict.fromkeys(ROLES, 0)

        _pick(scr, 'headline', 'Bold')                       # "set one of them to bold"
        scr.on_action('save')
        await pilot.pause()
        roles = _saved_roles(pd)
        assert (roles['headline']['index'], roles['headline']['weight']) == (1, 700), roles['headline']
        assert all(roles[r]['index'] == 0 for r in ROLES if r != 'headline'), roles

        app.pop_screen()
        scr2 = await _open_fonts(app, pilot)                 # the user comes back to the step
        assert _shown(scr2, 'headline').startswith('Bold ('), _shown(scr2, 'headline')
        assert _shown(scr2, 'label').startswith('Regular ('), _shown(scr2, 'label')


async def test_same_weight_faces_stay_distinct(tmp_path, ttc_fonts):
    """Bold and Condensed Bold are both 700: picking Condensed Bold must save ITS face."""
    pd = str(tmp_path / 'proj')
    project_mod.save(pd, project_mod.default_project('p'))
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_fonts(app, pilot)
        for role in ROLES:
            scr._set_role_family(role, 'Montserrat')
        _pick(scr, 'label', 'Condensed Bold')
        scr.on_action('save')
        await pilot.pause()
        assert _saved_roles(pd)['label']['index'] == 2, _saved_roles(pd)['label']
        app.pop_screen()
        scr2 = await _open_fonts(app, pilot)
        assert _shown(scr2, 'label').startswith('Condensed Bold ('), _shown(scr2, 'label')
