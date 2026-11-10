"""0.5.0 Task 4b: colour variants are OVERLAYS on the one project (design §8a + user
2026-11-10): one scheme by default; a checkbox adds variants that override only colours,
so every other change stays shared. Declared in v0.1-0.4 (generate ignored the variant)."""
import json
import os

import pytest
from textual.widgets import Checkbox, Input, Select

from motion_pipeline import generate, scheme
from motion_pipeline.tui.app import MenuApp
from projfix import DARK, make_project
from tui_probe import choose


def test_overlay_changes_only_its_keys_and_follows_base_edits(tmp_path):
    pd = make_project(tmp_path / 'p')
    scheme.save_variant(pd, 'warm', dict(DARK, accent='#ff6a00'))
    assert json.loads(open(scheme.variant_path(pd, 'warm')).read()) == {'accent': '#ff6a00'}
    base, warm = scheme.resolve_variant(pd), scheme.resolve_variant(pd, 'warm')
    assert {k for k in scheme.COLOUR_KEYS if base[k] != warm[k]} == {'accent'}
    # editing the BASE text colour reaches the variant too (in sync, not a copy)
    scheme.save_scheme(scheme.base_scheme_path(pd), dict(DARK, text='#eef2ff'))
    assert scheme.resolve_variant(pd, 'warm')['text'] == '#eef2ff'
    assert scheme.resolve_variant(pd, 'warm')['accent'] == '#ff6a00'


def test_bad_overlays_fail_loudly_naming_the_problem(tmp_path):
    pd = make_project(tmp_path / 'p')
    with pytest.raises(ValueError, match="unknown variant 'nope'"):
        scheme.resolve_variant(pd, 'nope')
    os.makedirs(os.path.join(pd, 'variants'))
    open(scheme.variant_path(pd, 'x'), 'w').write('{"fonts": "Arial"}')
    with pytest.raises(ValueError, match='not colour keys'):
        scheme.resolve_variant(pd, 'x')
    with pytest.raises(ValueError, match='invalid variant name'):
        scheme.save_variant(pd, 'Bad Name', DARK)
    with pytest.raises(ValueError, match='contrast'):
        scheme.save_variant(pd, 'dim', dict(DARK, text='#0c1b4d'))


def test_generate_per_variant_differs_exactly_in_overridden_colour(tmp_path):
    pd = make_project(tmp_path / 'p')
    scheme.save_variant(pd, 'warm', dict(DARK, accent='#ff6a00'))
    generate.generate(pd, 'default')
    a = open(os.path.join(pd, 'src', 'scene_Welcome.html')).read()
    generate.generate(pd, 'warm')
    b = open(os.path.join(pd, 'src', 'scene_Welcome.html')).read()
    assert '#ffb400' in a and '#ff6a00' not in a
    assert '#ff6a00' in b and '#ffb400' not in b
    assert a.replace('#ffb400', 'X').count('X') == b.replace('#ff6a00', 'X').count('X')
    assert DARK['text'] in a and DARK['text'] in b   # shared colours unchanged


async def test_menu_checkbox_off_by_default_variant_saved_as_overlay(tmp_path):
    pd = make_project(tmp_path / 'p')
    app = MenuApp()
    app.project_dir = pd
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(app.SCREENS['colours']()); await pilot.pause()
        scr = app.screen
        assert scr.query_one('#multi', Checkbox).value is False
        assert not scr.query_one('#variant', Select).display
        scr.query_one('#multi', Checkbox).value = True; await pilot.pause()
        scr.query_one('#variant', Select).value = '__new__'; await pilot.pause()
        scr.query_one('#variant-name', Input).value = 'warm'
        scr.query_one('#accent', Input).value = '#ff6a00'; await pilot.pause()
        await choose(pilot, scr, 'save')
        assert 'warm' in str(scr.query_one('#preview').render()), str(scr.query_one('#error').render())
        assert json.loads(open(scheme.variant_path(pd, 'warm')).read()) == {'accent': '#ff6a00'}
        assert json.loads(open(os.path.join(pd, 'project.json')).read())['variants'] == ['default', 'warm']
        assert json.loads(open(scheme.base_scheme_path(pd)).read())['accent'] == DARK['accent']  # base untouched
        # switching back to default shows the base colours
        scr.query_one('#variant', Select).value = 'default'; await pilot.pause()
        assert scr.query_one('#accent', Input).value == DARK['accent']
        # an unsaved edit + Back leaves variants/ untouched
        scr.query_one('#variant', Select).value = 'warm'; await pilot.pause()
        assert scr.query_one('#accent', Input).value == '#ff6a00'
        scr.query_one('#accent', Input).value = '#00ff00'; await pilot.pause()
        await choose(pilot, scr, 'back')
    assert json.loads(open(scheme.variant_path(pd, 'warm')).read()) == {'accent': '#ff6a00'}
