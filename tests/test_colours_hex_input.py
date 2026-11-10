"""0.5.1 bug fix: typing a bare hex (no '#', e.g. 'ffffff') into a CI colour field crashed
the whole TUI with an unhandled StyleValueError (scheme.py accepts bare hex via lstrip('#'),
but Textual's styles.background parser requires '#'). User report 2026-11-10 09:23 CET via
bin/motion-pipeline-dev.

Delivered behaviour: bare 6-hex is accepted and normalised to '#rrggbb' in the field, the
swatch + H/S/L update, nothing crashes; invalid input leaves the visible empty swatch and
no crash; Save stores the canonical '#rrggbb' on disk."""
import json

from textual.widgets import Input, Static

from motion_pipeline import project as project_mod
from motion_pipeline import scheme as scheme_mod
from motion_pipeline.tui.app import MenuApp


async def _open_colours(pilot, app, root):
    pd = root / 'acme'
    project_mod.save(str(pd), project_mod.default_project('acme'))
    scheme_mod.save_scheme(str(pd / 'scheme.json'),
                           {'name': 'acme', 'background_dark': '#0b1a4c',
                            'background_light': '#1251a6', 'accent': '#ffb400', 'text': '#f5f7ff'})
    app.project_dir = str(pd)
    app.push_screen(app.SCREENS['colours']())
    await pilot.pause(0.5)
    return app.screen


async def test_bare_hex_is_normalised_and_does_not_crash(_isolated_config, tmp_path):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_colours(pilot, app, tmp_path)
        hexf = scr.query_one('#background_dark', Input)
        hexf.value = 'ffffff'          # no '#', the exact input from the crash report
        await pilot.pause()
        assert hexf.value == 'ffffff'  # the field keeps the raw text (never rewritten mid-edit)
        sw = scr.query_one('#swatch-background_dark', Static)
        assert not sw.has_class('-empty'), 'swatch should be filled'
        assert '255, 255, 255' in str(sw.styles.background), sw.styles.background
        assert scr.query_one('#h-background_dark', Input).value == '0'
        assert scr.query_one('#s-background_dark', Input).value == '0'
        assert scr.query_one('#l-background_dark', Input).value == '100'


async def test_invalid_hex_leaves_empty_swatch_and_no_crash(_isolated_config, tmp_path):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_colours(pilot, app, tmp_path)
        hexf = scr.query_one('#accent', Input)
        hexf.value = 'zz'
        await pilot.pause()
        sw = scr.query_one('#swatch-accent', Static)
        assert sw.has_class('-empty'), 'invalid input must show the empty marker'
        assert hexf.value == 'zz'       # the user's text is kept so they can fix it


async def test_save_stores_canonical_hash_hex_on_disk(_isolated_config, tmp_path):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = await _open_colours(pilot, app, tmp_path)
        scr.query_one('#accent', Input).value = 'ff6a00'   # bare hex
        await pilot.pause()
        from tui_probe import choose
        await choose(pilot, scr, 'save')
        on_disk = json.loads((tmp_path / 'acme' / 'scheme.json').read_text())
        assert on_disk['accent'] == '#ff6a00', on_disk['accent']
        assert scheme_mod.validate_scheme(on_disk)  # loads clean next time
