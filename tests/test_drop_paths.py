"""0.5.0 Task 5: Finder drag-and-drop into path fields. A drop is a bracketed PASTE delivered
to the FOCUSED widget; v0.4.x had focus on the Back button on entry (drop lost) and never
decoded Terminal.app's backslash-escaped form. Real Finder drop = manual check (named in the
release report); this pins everything up to the terminal boundary."""
import os

import pytest
from textual import events
from textual.widgets import Input

from motion_pipeline.tui.app import MenuApp
from motion_pipeline.tui.paths import PathInput, normalize_dropped_path

D = '/Volumes/Work/x'   # fixture prefix (not a real home dir)


@pytest.mark.parametrize('raw, want', [
    (D + '/My\\ Folder ', D + '/My Folder'),                    # Terminal.app
    ("'" + D + "/My Folder'", D + '/My Folder'),                # iTerm2 quoting
    ('"' + D + '/My Folder"', D + '/My Folder'),
    ('file://' + D + '/My%20Folder/', D + '/My Folder'),        # URL form
    (D + '/\\Ünïcode\\ dir', D + '/Ünïcode dir'),
    (D + "/it\\'s\\ here", D + "/it's here"),
    (D + '/a\\ b ' + D + '/c', D + '/a b'),                     # two items -> first
    ('~/Movies', os.path.expanduser('~/Movies')),
    ('  /plain/path\n', '/plain/path'),
])
def test_normalize_dropped_path(raw, want):
    assert normalize_dropped_path(raw) == want


async def test_drop_into_focused_path_field_replaces_and_reports_existence(tmp_path):
    real = tmp_path / 'My Folder'
    real.mkdir()
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['bgtest']()); await pilot.pause()
        f = app.screen.query_one('#outdir', PathInput)
        f.focus(); f.value = 'old'; await pilot.pause()
        f.post_message(events.Paste(str(real).replace(' ', '\\ ') + ' ')); await pilot.pause()
        assert f.value == str(real)                     # replaced, decoded, not appended
        assert '✓' in str(f.border_subtitle)
        f.post_message(events.Paste('/nope/not\\ here')); await pilot.pause()
        assert f.value == '/nope/not here' and '✗' in str(f.border_subtitle)


async def test_drop_while_action_list_has_focus_lands_in_first_path_field(tmp_path):
    real = tmp_path / 'dropped dir'
    real.mkdir()
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        for key, fid in (('bgtest', '#outdir'), ('render', '#outdir'), ('inputs', '#transcript'),
                         ('project', '#dir')):
            app.push_screen(app.SCREENS[key]()); await pilot.pause()
            scr = app.screen
            scr.query_one('#actions').focus(); await pilot.pause()
            # the terminal delivers the paste to the focused widget (the action list)
            scr.focused.post_message(events.Paste(str(real).replace(' ', '\\ ')))
            await pilot.pause()
            f = scr.query_one(fid, Input)
            assert f.value == str(real), (key, f.value)
            assert scr.focused is f, key                 # focus moved to where the path went
            app.pop_screen(); await pilot.pause()


async def test_paste_into_a_non_path_field_is_left_alone(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['project']()); await pilot.pause()
        name = app.screen.query_one('#name', Input)
        name.focus(); await pilot.pause()
        name.post_message(events.Paste('my\\ name')); await pilot.pause()
        assert name.value == 'my\\ name'                 # plain text field: verbatim
