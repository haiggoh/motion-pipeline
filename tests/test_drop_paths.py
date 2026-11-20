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


# ---- Task 3 (spec A2): a drop routes by WHAT was dropped, not by focus ----

@pytest.mark.parametrize('path,accepts,dirs,want', [
    ('/x/vo.wav', ('.wav', '.mp3'), False, True),
    ('/x/VO.WAV', ('.wav',), False, True),            # case-insensitive
    ('/x/t.txt', ('.wav',), False, False),
    ('/x/t.txt', (), False, True),                     # no accept set = any file
    ('/x/noext', (), False, True),
    ('/x/noext', (), True, False),                     # dirs-only field rejects files
])
def test_accepts_path(path, accepts, dirs, want):
    f = PathInput(accepts=accepts, accepts_dirs=dirs)
    assert f.accepts_path(path) is want


def test_accepts_path_dirs(tmp_path):
    d = tmp_path / 'a folder'; d.mkdir()
    f = PathInput(accepts_dirs=True)
    assert f.accepts_path(str(d)) is True
    f2 = PathInput(accepts=('.txt',))
    assert f2.accepts_path(str(d)) is False


async def test_drop_wav_with_action_list_focus_lands_in_vo_not_transcript(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['inputs']()); await pilot.pause()
        scr = app.screen
        scr.query_one('#actions').focus(); await pilot.pause()
        scr.focused.post_message(events.Paste('/tmp/x\\ y/vo\\ take.wav '))  # Terminal.app escapes every space
        await pilot.pause()
        assert scr.query_one('#vo', PathInput).value == '/tmp/x y/vo take.wav'
        assert scr.query_one('#transcript', PathInput).value == 'transcript.txt'
        assert scr.focused is scr.query_one('#vo', PathInput)


async def test_drop_wav_while_transcript_focused_still_lands_in_vo(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['inputs']()); await pilot.pause()
        scr = app.screen
        tr = scr.query_one('#transcript', PathInput)
        tr.focus(); await pilot.pause()
        tr.post_message(events.Paste("'/tmp/vo take.wav'"))               # iTerm-quoted
        await pilot.pause()
        assert scr.query_one('#vo', PathInput).value == '/tmp/vo take.wav'
        assert tr.value == 'transcript.txt'
        assert scr.focused is scr.query_one('#vo', PathInput)


async def test_drop_docx_while_vo_focused_lands_in_transcript(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['inputs']()); await pilot.pause()
        scr = app.screen
        vo = scr.query_one('#vo', PathInput)
        vo.focus(); await pilot.pause()
        vo.post_message(events.Paste('/tmp/report.docx')); await pilot.pause()
        assert scr.query_one('#transcript', PathInput).value == '/tmp/report.docx'
        assert vo.value == ''


async def test_drop_unknown_extension_while_vo_focused_stays_in_vo(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['inputs']()); await pilot.pause()
        scr = app.screen
        vo = scr.query_one('#vo', PathInput)
        vo.focus(); await pilot.pause()
        vo.post_message(events.Paste('/tmp/mystery.xyz')); await pilot.pause()
        assert vo.value == '/tmp/mystery.xyz'          # zero accepting fields -> focus decides


async def test_two_item_drop_fills_first_and_says_so(tmp_path):
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['inputs']()); await pilot.pause()
        scr = app.screen
        scr.query_one('#actions').focus(); await pilot.pause()
        scr.focused.post_message(events.Paste('/tmp/a.wav /tmp/b.wav')); await pilot.pause()
        vo = scr.query_one('#vo', PathInput)
        assert vo.value == '/tmp/a.wav'
        assert str(vo.border_subtitle) == '2 items dropped — used the first'


async def test_folder_drop_regression_project_and_colours_screens(tmp_path):
    real = tmp_path / 'proj dir'; real.mkdir()
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(app.SCREENS['project']()); await pilot.pause()
        scr = app.screen
        scr.query_one('#actions').focus(); await pilot.pause()
        scr.focused.post_message(events.Paste(str(real).replace(' ', '\\ '))); await pilot.pause()
        # #dir and #root both accept dirs -> ambiguous -> first visible field (as before)
        assert scr.query_one('#dir', PathInput).value == str(real)
        app.pop_screen(); await pilot.pause()
        app.push_screen(app.SCREENS['colours']()); await pilot.pause()
        scr = app.screen
        assert not list(scr.query(PathInput))           # no path fields: drop is a no-op, no crash
        scr.query_one('#actions').focus(); await pilot.pause()
        scr.focused.post_message(events.Paste(str(real))); await pilot.pause()


def test_transcript_load_rejects_non_txt_md_with_named_error(tmp_path):
    from motion_pipeline import transcript
    p = tmp_path / 'x.docx'
    p.write_bytes(b'not really a docx')
    with pytest.raises(ValueError) as ei:
        transcript.load(str(p))
    assert '.docx' in str(ei.value) and '0.7.0' in str(ei.value)
