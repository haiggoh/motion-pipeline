"""Task 2 TUI tests: colours screen with live swatches + HSL sync + save/re-edit."""
import json

import pytest
from textual.widgets import Input, Static

from tui_probe import choose
from motion_pipeline.tui.app import MenuApp
from motion_pipeline import scheme as scheme_mod

DARK = {'name': 'tui-demo', 'background_dark': '#0b1a4c', 'background_light': '#1251a6',
        'accent': '#ffb400', 'text': '#f5f7ff'}
COLOUR_KEYS = scheme_mod.INPUT_KEYS[1:]


def _bg_rgb(style):
    # Static.render() yields Textual Style (.background: Color) — not Rich (.bgcolor)
    c = getattr(style, 'background', None)
    return tuple(c.rgb) if c is not None else None


def text_of(widget):
    return str(widget.render())


@pytest.mark.asyncio
async def test_swatches_and_hsl_sync_live(tmp_path, monkeypatch):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test() as pilot:
        app.push_screen(app.SCREENS['colours']())
        await pilot.pause()
        scr = app.screen
        # typing a hex updates the swatch AND the HSL fields live
        scr.query_one('#background_dark', Input).value = '#ff0000'
        await pilot.pause()
        sw = scr.query_one('#swatch-background_dark', Static)
        assert '255, 0, 0' in str(sw.styles.background), sw.styles.background
        assert scr.query_one('#h-background_dark', Input).value == '0'
        assert scr.query_one('#s-background_dark', Input).value == '100'
        assert scr.query_one('#l-background_dark', Input).value == '50'
        # editing an HSL field updates the hex + swatch
        scr.query_one('#h-accent', Input).value = '120'
        scr.query_one('#s-accent', Input).value = '100'
        scr.query_one('#l-accent', Input).value = '50'
        await pilot.pause()
        assert scr.query_one('#accent', Input).value == '00ff00'   # B1: bare hex in the field
        assert '0, 255, 0' in str(scr.query_one('#swatch-accent', Static).styles.background)


@pytest.mark.asyncio
async def test_derive_preview_save_and_reedit(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test() as pilot:
        app.push_screen(app.SCREENS['colours']())
        await pilot.pause()
        scr = app.screen
        for k in COLOUR_KEYS:
            scr.query_one(f'#{k}', Input).value = DARK[k]
        await pilot.pause()
        await choose(pilot, scr, 'derive')
        await pilot.pause()
        prev = scr.query_one('#preview', Static).render()
        assert 'secondary text' in str(prev)
        assert any(_bg_rgb(sp.style) == (0xa6, 0xb0, 0xc8) for sp in prev.spans), prev.spans  # secondary-text swatch painted
        await choose(pilot, scr, 'save')
        await pilot.pause()
        p = tmp_path / 'scheme.json'   # directly in the project (v0.4.x nested <project>/<name>/)
        saved = json.loads(p.read_text())
        assert {k: saved[k] for k in COLOUR_KEYS} == {k: DARK[k] for k in COLOUR_KEYS}
        # re-edit: change accent, save again -> persisted
        scr.query_one('#accent', Input).value = '00c2ff'   # B1: bare hex in the field
        await pilot.pause()
        await choose(pilot, scr, 'save')
        await pilot.pause()
        await pilot.pause()
        assert json.loads(p.read_text())['accent'] == '#00c2ff'
        # re-edit: re-opening the screen prefills the saved values (bare hex, '#' in the label)
        app.pop_screen(); await pilot.pause()
        app.push_screen(app.SCREENS['colours']()); await pilot.pause()
        assert app.screen.query_one('#accent', Input).value == '00c2ff'
        assert '0, 194, 255' in str(app.screen.query_one('#swatch-accent', Static).styles.background)


@pytest.mark.asyncio
async def test_invalid_hex_shows_error_not_crash(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test() as pilot:
        app.push_screen(app.SCREENS['colours']())
        await pilot.pause()
        scr = app.screen
        for k in COLOUR_KEYS:
            scr.query_one(f'#{k}', Input).value = '#0b1a4c'
        scr.query_one('#accent', Input).value = 'nope'
        await choose(pilot, scr, 'save')
        await pilot.pause()
        await pilot.pause()
        assert 'invalid hex' in text_of(scr.query_one('#error', Static))
        assert not (tmp_path / 'scheme.json').exists()


@pytest.mark.asyncio
async def test_colour_rows_labelled_swatches_visible_hex_fully_shown(tmp_path):
    sm = scheme_mod
    sm.save_scheme(str(tmp_path / 'scheme.json'), DARK)
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(app.SCREENS['colours']()); await pilot.pause()
        scr = app.screen
        from tui_probe import on_screen
        labels = [str(l.render()) for l in scr.query('.colour-label')]
        assert labels == ['background dark', 'background light', 'accent', 'text']
        for k in COLOUR_KEYS:
            inp = scr.query_one(f'#{k}', Input)
            # B1: the '#' moved OUTSIDE the field (a .hash-label) — the field holds bare hex
            assert inp.value == DARK[k].lstrip('#'), (k, inp.value)
            assert inp.content_region.width >= len(DARK[k]), f'{k}: hex cut off ({inp.content_region})'
            sw = scr.query_one(f'#swatch-{k}', Static)
            assert on_screen(app, sw) and sw.region.width >= 4
            assert tuple(sw.styles.background.rgb) == sm._hex_to_srgb(DARK[k]) or \
                '#%02x%02x%02x' % tuple(sw.styles.background.rgb) == DARK[k]
            assert sw.styles.border_top[0] in ('', 'none'), f'{k}: filled swatch still framed'
            for f in ('h', 's', 'l'):
                assert scr.query_one(f'#{f}-{k}', Input).value == str(dict(zip('hsl', sm.hex_to_hsl(DARK[k])))[f])
        # variants ON (+ the new-variant name field) must not push the action rows / hint off-screen
        scr.query_one('#multi').value = True; await pilot.pause()
        from textual.widgets import Select
        scr.query_one('#variant', Select).value = '__new__'; await pilot.pause()
        for sel in ('#actions', '.hint', '#variant', '#variant-name'):
            assert on_screen(app, scr.query_one(sel)), f'{sel} off-screen with variants on at 80x24'
        # an empty swatch is still visible: framed + marker
        scr.query_one('#accent', Input).value = 'zz'; await pilot.pause()
        sw = scr.query_one('#swatch-accent', Static)
        assert sw.styles.border_top[0] == 'round' and '░' in str(sw.render())


# ---- Task 11 (spec B1 second half): contrast markers, actionable message, Fix/Save anyway ----

FAIL_SCHEME = {'name': 'demo', 'background_dark': '#ffffff', 'background_light': '#1251a6',
               'accent': '#ffb400', 'text': '#ffff54'}   # text 1.07:1, accent ~2.2:1 on white


async def _open_colours_scheme(pilot, app, root, scheme):
    from motion_pipeline import project as project_mod
    pd = root / 'acme'
    project_mod.save(str(pd), project_mod.default_project('acme'))
    with open(pd / 'scheme.json', 'w') as f:
        json.dump(scheme, f)
    app.project_dir = str(pd)
    app.push_screen(app.SCREENS['colours']())
    await pilot.pause(0.5)
    return app.screen


async def test_contrast_markers_actionable_message_and_fix_action(tmp_path):
    sm = scheme_mod
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        scr = await _open_colours_scheme(pilot, app, tmp_path, dict(FAIL_SCHEME))
        # red ! on exactly the rows involved in a failing pair (background_dark + text + accent)
        flags = {k: str(scr.query_one(f'#flag-{k}', Static).render()) for k in sm.COLOUR_KEYS}
        assert flags['text'] == '!' and flags['background_dark'] == '!', flags
        assert flags['accent'] == '!', flags      # accent 2.2:1 < 3.0 also fails on white
        assert flags['background_light'] == '', flags
        err = str(scr.query_one('#error', Static).render())
        assert 'text on background dark: 1.07:1 — needs at least 4.5:1' in err, err
        assert 'Fix: ' in err and '→ #' in err, err   # the suggested concrete change
        menu = scr.query_one('#actions')
        assert not menu.get_option('fix').disabled
        assert not menu.get_option('force').disabled
        # Fix applies the suggestion without saving
        before = (tmp_path / 'acme' / 'scheme.json').read_text()
        await choose(pilot, scr, 'fix')
        await pilot.pause()
        assert (tmp_path / 'acme' / 'scheme.json').read_text() == before   # no save
        assert str(scr.query_one('#flag-text', Static).render()) == ''
        assert 'contrast' not in str(scr.query_one('#error', Static).render()).lower()


async def test_save_anyway_writes_override_and_later_save_clears_it(tmp_path):
    sm = scheme_mod
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        scr = await _open_colours_scheme(pilot, app, tmp_path, dict(FAIL_SCHEME))
        await choose(pilot, scr, 'force')
        await pilot.pause(); await pilot.pause()
        on_disk = json.loads((tmp_path / 'acme' / 'scheme.json').read_text())
        assert on_disk.get('contrast_override') is True, on_disk
        # fix the colours (light text on dark bg passes), then plain Save -> flag gone
        scr.query_one('#text', Input).value = 'f5f7ff'
        scr.query_one('#background_dark', Input).value = '0b1a4c'
        await pilot.pause()
        await choose(pilot, scr, 'save')
        await pilot.pause(); await pilot.pause()
        on_disk = json.loads((tmp_path / 'acme' / 'scheme.json').read_text())
        assert 'contrast_override' not in on_disk, on_disk
