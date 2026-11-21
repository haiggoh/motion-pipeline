"""0.5.1 bug fix: typing a bare hex (no '#', e.g. 'ffffff') into a CI colour field crashed
the whole TUI with an unhandled StyleValueError (scheme.py accepts bare hex via lstrip('#'),
but Textual's styles.background parser requires '#'). User report 2026-11-10 09:23 CET via
bin/motion-pipeline-dev.

Delivered behaviour: bare 6-hex is accepted and normalised to '#rrggbb' in the field, the
swatch + H/S/L update, nothing crashes; invalid input leaves the visible empty swatch and
no crash; Save stores the canonical '#rrggbb' on disk."""
import json

import pytest
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


# ---- Task 10 (spec B1 first half): field restrictions + the 3-digit short form ----

def test_normalise_hex_short_forms():
    assert scheme_mod.normalise_hex('abc') == '#aabbcc'
    assert scheme_mod.normalise_hex('#FfF') == '#ffffff'
    with pytest.raises(ValueError):
        scheme_mod.normalise_hex('ab')     # 2 digits: incomplete, not a short form
    with pytest.raises(ValueError):
        scheme_mod.normalise_hex('abcd')   # 4 digits: incomplete


async def test_typing_disallowed_characters_changes_nothing(_isolated_config, tmp_path):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        scr = await _open_colours(pilot, app, tmp_path)
        hexf = scr.query_one('#background_dark', Input)
        hexf.value = ''                 # clear the prefill; then typing is what shows up
        await pilot.pause()
        hexf.focus()
        for ch in ('g', '#', 'z'):
            await pilot.press(ch)
        assert hexf.value == '', repr(hexf.value)
        h = scr.query_one('#h-background_dark', Input)
        h.value = ''                  # clear the prefill
        await pilot.pause()
        h.focus()
        for ch in ('a', '-', '.'):
            await pilot.press(ch)
        assert h.value == '', repr(h.value)


async def test_seventh_hex_char_refused(_isolated_config, tmp_path):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        scr = await _open_colours(pilot, app, tmp_path)
        hexf = scr.query_one('#accent', Input)
        hexf.focus()
        for ch in 'ff6a00f':
            await pilot.press(ch)
        assert hexf.value == 'ff6a00', repr(hexf.value)


async def test_paste_hash_uppercase_accepted_whole(_isolated_config, tmp_path):
    """Review Focus #2: pasting '#FF6A00' (with '#', uppercase) is accepted as 'ff6a00' —
    not rejected and not truncated to '#ff6a0'."""
    from textual import events
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        scr = await _open_colours(pilot, app, tmp_path)
        hexf = scr.query_one('#accent', Input)
        hexf.focus(); await pilot.pause()
        hexf.post_message(events.Paste('#FF6A00'))
        await pilot.pause()
        assert hexf.value == 'ff6a00', repr(hexf.value)
        sw = scr.query_one('#swatch-accent', Static)
        assert not sw.has_class('-empty')
        assert '255, 106, 0' in str(sw.styles.background), sw.styles.background


async def test_three_digit_short_form_updates_swatch_and_hsl(_isolated_config, tmp_path):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        scr = await _open_colours(pilot, app, tmp_path)
        hexf = scr.query_one('#background_dark', Input)
        hexf.value = 'fff'
        await pilot.pause()
        sw = scr.query_one('#swatch-background_dark', Static)
        assert not sw.has_class('-empty')
        assert '255, 255, 255' in str(sw.styles.background), sw.styles.background
        assert scr.query_one('#h-background_dark', Input).value == '0'
        assert scr.query_one('#s-background_dark', Input).value == '0'
        assert scr.query_one('#l-background_dark', Input).value == '100'


async def test_incomplete_hex_lengths_leave_empty_swatch(_isolated_config, tmp_path):
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        scr = await _open_colours(pilot, app, tmp_path)
        hexf = scr.query_one('#accent', Input)
        for v in ('f', 'ff', 'ffff', 'fffff'):
            hexf.value = v
            await pilot.pause()
            assert scr.query_one('#swatch-accent', Static).has_class('-empty'), v
        assert 'error' not in str(scr.query_one('#error', Static).render()).lower()


async def test_hsl_ranges_refused_at_input(_isolated_config, tmp_path):
    """H >360 and S/L >100 are refused at input (the field keeps the previous value),
    never clamped silently."""
    app = MenuApp()
    async with app.run_test(size=(80, 24)) as pilot:
        scr = await _open_colours(pilot, app, tmp_path)
        h = scr.query_one('#h-background_dark', Input)
        h.focus()
        for ch in '361':
            await pilot.press(ch)
        assert h.value == '36', repr(h.value)          # the third digit is refused
        h.value = ''
        await pilot.pause()
        h.focus()
        for ch in '360':
            await pilot.press(ch)
        assert h.value == '360', repr(h.value)         # 360 itself is accepted
        s = scr.query_one('#s-background_dark', Input)
        s.focus()
        for ch in '101':
            await pilot.press(ch)
        assert s.value == '10', repr(s.value)
