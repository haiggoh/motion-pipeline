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


async def _wait_for(predicate, pilot, tries=60):
    for _ in range(tries):
        await pilot.pause(0.1)
        if predicate():
            return True
    return False


@pytest.mark.asyncio
async def test_save_reports_prepare_failure_with_named_error(tmp_path):
    """Task 5 (A5a/b): a failing prepare-only job must surface its named error line and must
    not leave the status stuck on 'computing timings…'."""
    d = mk_project(tmp_path / 'proj')
    cmd = ['bash', '-c', 'echo "missing dependency: transcript /x — set it in step 5 (Transcript + voiceover)" >&2; exit 3']
    app = MenuApp(test_prepare_cmd=cmd)
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_inputs(pilot, app, d)
        await save(pilot, scr)
        ok = await _wait_for(
            lambda: 'missing dependency' in str(scr.query_one('#error', Static).render()), pilot)
        err = str(scr.query_one('#error', Static).render())
        status = str(scr.query_one('#status', Static).render())
        assert ok, f'error line never appeared: error={err!r} status={status!r}'
        assert 'missing dependency: transcript /x' in err, err
        assert 'computing timings' not in status, status


@pytest.mark.asyncio
async def test_save_success_reports_timing_counts(tmp_path):
    """Task 5 (A5a): a successful prepare-only job reports the saved counts."""
    d = mk_project(tmp_path / 'proj')
    helper = tmp_path / 'fake_prepare.sh'
    helper.write_text(
        '#!/bin/bash\n'
        f'printf \'{{"method": "estimated", "inputs": "x"}}\' > "{d}/timing.json"\n'
        f'printf \'{{"words": [{{"id": "w1"}}, {{"id": "w2"}}], "sections": [{{"name": "A"}}]}}\' '
        f'> "{d}/transcript_model.json"\n'
        'exit 0\n')
    app = MenuApp(test_prepare_cmd=['bash', str(helper)])
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_inputs(pilot, app, d)
        await save(pilot, scr)
        ok = await _wait_for(
            lambda: 'timings saved' in str(scr.query_one('#status', Static).render()), pilot)
        status = str(scr.query_one('#status', Static).render())
        assert ok, f'status never updated: {status!r}'
        assert 'timings saved — 2 words, 1 sections, engine estimated' in status, status


@pytest.mark.asyncio
async def test_save_with_docx_transcript_reports_sections_and_words(tmp_path):
    """Task 15 (B4) delivery level: a .docx transcript set in the field saves through the REAL
    prepare-only job and the status reports 'N sections, M words'."""
    import shutil
    from motion_pipeline.scheme import save_scheme
    from projfix import DARK
    d = mk_project(tmp_path / 'proj', fonts={'family': 'Montserrat'})
    save_scheme(os.path.join(d, 'scheme.json'), DARK)
    docx = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'fixtures', 'transcripts', 'sample.docx')
    shutil.copy(docx, os.path.join(d, 'transcript.docx'))
    app = MenuApp()          # real prepare-only command
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_inputs(pilot, app, d)
        scr.query_one('#transcript', Input).value = 'transcript.docx'
        await save(pilot, scr)
        ok = await _wait_for(
            lambda: 'timings saved' in str(scr.query_one('#status', Static).render()), pilot)
        status = str(scr.query_one('#status', Static).render())
        assert ok, f'status: {status!r}'
        assert '1 sections' in status and '7 words' in status, status   # docx: Intro + 7 words


@pytest.mark.asyncio
@pytest.mark.parametrize('corrupt', ['{', 'foreign-key'])
async def test_corrupt_project_json_is_named_and_save_refuses(tmp_path, corrupt):
    """Task 6 (X2): a corrupt or invalid project.json must be NAMED in #error on the inputs
    screen — never shown as silent defaults — and Save must refuse (file bytes unchanged)."""
    d = mk_project(tmp_path / 'proj')
    pj = os.path.join(d, 'project.json')
    if corrupt == '{':
        open(pj, 'w').write('{')
    else:
        p = project_json(d)
        p['ai_extra'] = 1                      # a key the menu does not own
        json.dump(p, open(pj, 'w'))
    original = open(pj, 'rb').read()
    app = MenuApp()
    async with app.run_test(size=(100, 40)) as pilot:
        scr = await open_inputs(pilot, app, d)
        err = str(scr.query_one('#error', Static).render())
        assert 'project.json' in err, f'error does not name project.json: {err!r}'
        await save(pilot, scr)
        await pilot.pause(0.3)
        assert open(pj, 'rb').read() == original, 'Save rewrote a corrupt project.json'
