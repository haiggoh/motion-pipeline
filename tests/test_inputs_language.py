"""0.8.3 bug 3 through the shipped screen: a saved 'de' that the loaded transcript contradicts
shows Auto-detect with a visible note — and project.json is NOT rewritten until the user saves
(no hidden change). A saved choice the transcript agrees with is kept."""
import os

import pytest
from test_language_detect import DE, EN
from tui_probe import on_screen

from motion_pipeline import project as project_mod
from motion_pipeline.tui.app import MenuApp


def _project(tmp_path, language, text):
    pd = str(tmp_path / 'proj')
    p = project_mod.default_project('p')
    p['language'] = language
    project_mod.save(pd, p)
    with open(os.path.join(pd, 'transcript.txt'), 'w') as f:
        f.write(text)
    return pd


async def _inputs(pd):
    app = MenuApp()
    app.project_dir = pd
    return app


@pytest.mark.parametrize(('saved', 'text', 'shown', 'note'), [
    ('de', EN, 'auto', True),       # the user's case
    ('de', DE, 'de', False),        # a deliberate matching choice is kept
    ('en', EN, 'en', False),
    ('en', DE, 'auto', True),
])
async def test_language_field_follows_the_transcript(tmp_path, saved, text, shown, note):
    from textual.widgets import Select, Static
    pd = _project(tmp_path, saved, text)
    before = open(os.path.join(pd, 'project.json'), 'rb').read()
    app = await _inputs(pd)
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(app.SCREENS['inputs']()); await pilot.pause(0.3)
        assert app.screen.query_one('#language', Select).value == shown
        status = app.screen.query_one('#status', Static)
        txt = ' '.join(str(status.render()).split())
        if note:
            assert 'Auto-detect' in txt and 'Save to keep' in txt, txt
            assert on_screen(app, status), status.region
        else:
            assert 'Auto-detect' not in txt, txt
    assert open(os.path.join(pd, 'project.json'), 'rb').read() == before, 'project.json rewritten on load'


def _project_file(tmp_path, language, fname, content_bytes):
    pd = str(tmp_path / 'proj')
    p = project_mod.default_project('p')
    p['language'] = language
    p['transcript'] = fname
    project_mod.save(pd, p)
    with open(os.path.join(pd, fname), 'wb') as f:
        f.write(content_bytes)
    return pd


async def test_docx_transcript_contradicting_saved_de_shows_auto(tmp_path):
    """The real user input is a .docx (routed through transcript_formats.to_markup): a saved
    'de' + English docx shows Auto-detect, the field's rendered LABEL reads 'Auto-detect'
    (not just the internal value), and project.json is untouched on load."""
    import io

    from docx_fixture import build_docx
    from textual.widgets import Select, Static
    buf = io.BytesIO()
    build_docx(buf, [{'text': EN}, {'text': EN}])   # two 66-word English paragraphs
    pd = _project_file(tmp_path, 'de', 'transcript.docx', buf.getvalue())
    before = open(os.path.join(pd, 'project.json'), 'rb').read()
    app = await _inputs(pd)
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(app.SCREENS['inputs']()); await pilot.pause(0.3)
        sel = app.screen.query_one('#language', Select)
        assert sel.value == 'auto'
        labels = {v: str(l) for l, v in sel._options}   # Select displays the current value's label
        assert labels.get('auto') == 'Auto-detect', labels  # the label the user reads
        status = app.screen.query_one('#status', Static)
        txt = ' '.join(str(status.render()).split())
        assert 'Auto-detect' in txt and 'Save to keep' in txt, txt
        assert on_screen(app, status), status.region
    assert open(os.path.join(pd, 'project.json'), 'rb').read() == before, 'project.json rewritten on load'


async def test_corrupt_docx_keeps_saved_choice_without_crash(tmp_path):
    """A corrupt .docx (not a zip) must not crash the screen load — BadZipFile is not a
    ValueError, so the guard must name it: saved choice stays, no note."""
    from textual.widgets import Select, Static
    pd = _project_file(tmp_path, 'de', 'transcript.docx', b'not a zip at all')
    app = await _inputs(pd)
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(app.SCREENS['inputs']()); await pilot.pause(0.3)
        assert app.screen.query_one('#language', Select).value == 'de'
        txt = ' '.join(str(app.screen.query_one('#status', Static).render()).split())
        assert 'Auto-detect' not in txt, txt


async def test_language_check_reached_via_default_entry_point(tmp_path, monkeypatch):
    """Shipped wiring, not injected: MenuApp() with no project_dir resolves the project via
    config.last_project() in on_mount — the path the installed binary actually runs."""
    from textual.widgets import Select

    from motion_pipeline import config as config_mod
    cfg = tmp_path / 'cfg'
    cfg.mkdir()
    monkeypatch.setenv('MP_CONFIG_DIR', str(cfg))
    pd = _project(tmp_path, 'de', EN)
    config_mod.set_projects_root(str(tmp_path))   # outside the package -> accepted
    config_mod.set_last_project(pd)
    app = MenuApp()                               # no project_dir injection
    async with app.run_test(size=(80, 24)) as pilot:
        assert app.project_dir == pd, 'default ctor did not resolve last_project'
        app.push_screen(app.SCREENS['inputs']()); await pilot.pause(0.3)
        assert app.screen.query_one('#language', Select).value == 'auto'
