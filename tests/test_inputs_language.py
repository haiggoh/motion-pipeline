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
