"""Task 2 (plan 2026-11-16): InputsScreen prefill + wpm/language/aligner fields; saving the
transcript must not clear the saved voiceover (the data-loss bug). Pilot tests, real screen."""
import json
import os

import pytest
from textual.widgets import Input, Select, Static

from motion_pipeline import project
from motion_pipeline.tui.app import MenuApp
from tui_probe import choose


def mk_project(d, **over):
    d = str(d)
    p = project.default_project('demo')
    p.update(over)
    project.save(d, p)
    with open(os.path.join(d, 'transcript.txt'), 'w') as f:
        f.write('# A\nhello world\n')
    return d


def project_json(d):
    with open(os.path.join(d, 'project.json')) as f:
        return json.load(f)


async def open_inputs(pilot, app, d):
    app.project_dir = d
    app.push_screen(app.SCREENS['inputs']())
    await pilot.pause()
    return app.screen


async def save(pilot, scr):
    await choose(pilot, scr, 'save')
    await pilot.pause()


@pytest.mark.asyncio
async def test_inputs_prefilled_from_project(tmp_path):
    d = mk_project(tmp_path / 'proj', vo='audio/vo.wav', wpm=180, language='en', aligner='classical')
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_inputs(pilot, app, d)
        assert scr.query_one('#transcript', Input).value == 'transcript.txt'
        assert scr.query_one('#vo', Input).value == 'audio/vo.wav'
        assert scr.query_one('#wpm', Input).value == '180'
        assert scr.query_one('#language', Select).value == 'en'
        assert scr.query_one('#aligner', Select).value == 'classical'


@pytest.mark.asyncio
async def test_saving_transcript_keeps_vo(tmp_path):
    d = mk_project(tmp_path / 'proj', vo='audio/vo.wav')
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_inputs(pilot, app, d)
        scr.query_one('#transcript', Input).value = 'transcript.txt'  # touch transcript only
        await save(pilot, scr)
        assert project_json(d)['vo'] == 'audio/vo.wav'


@pytest.mark.asyncio
async def test_wpm_out_of_range_refused(tmp_path):
    d = mk_project(tmp_path / 'proj')
    before = open(os.path.join(d, 'project.json')).read()
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_inputs(pilot, app, d)
        scr.query_one('#wpm', Input).value = '20'
        await save(pilot, scr)
        err = str(scr.query_one('#error', Static).render())
        assert 'wpm' in err, err
        assert open(os.path.join(d, 'project.json')).read() == before  # nothing written


@pytest.mark.asyncio
async def test_language_and_aligner_saved(tmp_path):
    d = mk_project(tmp_path / 'proj')
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_inputs(pilot, app, d)
        scr.query_one('#language', Select).value = 'en'
        scr.query_one('#aligner', Select).value = 'whisper'
        await save(pilot, scr)
        pj = project_json(d)
        assert pj['language'] == 'en' and pj['aligner'] == 'whisper' and pj['wpm'] == 140
