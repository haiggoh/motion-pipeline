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


async def test_role_label_shows_the_picked_weight(tmp_path, ttc_fonts):
    """Screenshot finding (0.8.3): the role row's label kept saying 'Regular (400)' while its
    dropdown said 'Bold (700)' — the label always showed the family's FIRST face."""
    from textual.widgets import Static
    pd = str(tmp_path / 'proj')
    project_mod.save(pd, project_mod.default_project('p'))
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_fonts(app, pilot)
        scr._set_role_family('headline', 'Montserrat')
        def label():
            return str(scr.query_one('#role-headline-family', Static).render())
        # the headline DEFAULT is Bold, so each pick must visibly MOVE the label (mutation-proof)
        _pick(scr, 'headline', 'Regular')
        await pilot.pause()
        assert 'Regular (400)' in label(), label()
        _pick(scr, 'headline', 'Condensed Bold')
        await pilot.pause()
        assert 'Condensed Bold (700)' in label(), label()
        _pick(scr, 'headline', 'Bold')
        await pilot.pause()
        assert label().endswith('· Bold (700)'), label()


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


async def test_user_flow_by_keys_only(tmp_path, ttc_fonts):
    """M1 QC (R4): drive the shipped bindings — focus the dropdown, Enter, arrows, Enter, then the
    '1' action digit (Save) — instead of calling screen methods. Proves the change event, the
    label refresh and the save binding are wired, not just the methods behind them."""
    from textual.widgets import Select, Static
    pd = str(tmp_path / 'proj')
    p = project_mod.default_project('p')
    project_mod.save(pd, p)
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_fonts(app, pilot)
        for role in ROLES:
            scr._set_role_family(role, 'Montserrat')
            _pick(scr, role, 'Regular')                      # starting state: 4x Regular
        await pilot.pause()
        # the headline DEFAULT is Bold: the label must read Regular now, or the key pick below
        # could 'pass' without the label ever moving (that mutation survived once)
        before = str(scr.query_one('#role-headline-family', Static).render())
        assert before.endswith('· Regular (400)'), before
        sel = scr.query_one('#role-headline-weight', Select)
        sel.focus()
        await pilot.pause()
        await pilot.press('enter')                           # open the dropdown
        await pilot.pause()
        prompts = [str(p) for p, _v in sel._options]
        here, there = prompts.index('Regular (400)'), prompts.index('Bold (700)')
        for _ in range(there - here):
            await pilot.press('down')
        await pilot.press('enter')                           # choose Bold
        await pilot.pause()
        label = str(scr.query_one('#role-headline-family', Static).render())
        assert label.endswith('· Bold (700)'), label
        scr.query_one('#fonts').focus()                      # digits act when no text field has focus
        await pilot.press('1')                               # 1) Save font config
        await pilot.pause(0.3)
    roles = _saved_roles(pd)
    assert (roles['headline']['index'], roles['headline']['weight']) == (1, 700), roles['headline']
    assert all(roles[r]['index'] == 0 for r in ROLES if r != 'headline'), roles
