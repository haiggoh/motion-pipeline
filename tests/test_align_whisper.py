"""Task 17 tests (plan 2026-11-16): whisper engine — no download; a fake whisper-cli writes the
recorded fixture (tests/fixtures/whisper_ojf_sample.json). U2 probe NOT run (needs the user's
model-download permission); the parser is pinned to that fixture instead."""
import json
import os

import pytest

from motion_pipeline import align, align_whisper

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures',
                       'whisper_ojf_sample.json')

TR_WORDS = [{'id': 'w0', 'text': 'Das', 'section': 'S'},
            {'id': 'w1', 'text': 'ist', 'section': 'S'},
            {'id': 'w2', 'text': 'ein', 'section': 'S'},
            {'id': 'w3', 'text': 'Test.', 'section': 'S'},
            {'id': 'w4', 'text': 'Zweiter', 'section': 'S'},
            {'id': 'w5', 'text': 'Satz', 'section': 'S'},
            {'id': 'w6', 'text': 'hier.', 'section': 'S'}]

CLASSICAL = {'sections': {'S': 0.0},
             'words': [{'id': f'w{i}', 'start': 0.0 + i * 0.3, 'end': 0.3 + i * 0.3}
                       for i in range(7)]}


def test_snap_matches_transcript_words(tmp_path):
    rec = json.load(open(FIXTURE))['words']
    model = tmp_path / 'ggml-base.bin'
    model.write_bytes(b'x' * 100)
    doc = align_whisper.snap(rec, TR_WORDS, CLASSICAL, str(model))
    align = doc['words']
    # matched words take the recognised times
    assert abs(align[0]['start'] - 1.0) < 1e-6
    assert abs(align[3]['end'] - 1.94) < 1e-6
    assert 'classical fallback for 0 words' in doc['method']
    assert 'sha256' in doc['method'][:40]


def test_snap_fills_unmatched_with_classical(tmp_path):
    rec = json.load(open(FIXTURE))['words'][:2]  # recognise only 'Das ist'
    model = tmp_path / 'ggml-base.bin'
    model.write_bytes(b'x')
    doc = align_whisper.snap(rec, TR_WORDS, CLASSICAL, str(model))
    assert 'classical fallback for 5 words' in doc['method']
    assert doc['words'][5]['start'] == CLASSICAL['words'][5]['start']  # classical time
    # monotonic overall
    align.validate_timing({'source': 'x', 'method': 'm', 'sections': {}, 'words': doc['words']})


def test_auto_falls_back_without_engine(tmp_path, monkeypatch):
    monkeypatch.delenv('MP_WHISPER_CLI', raising=False)
    monkeypatch.delenv('MP_WHISPER_MODEL', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))  # no fnm pin / models in this HOME
    if os.path.exists(os.path.expanduser('~/.local/share/fnm')):
        pytest.skip('fnm pin present on this machine')
    assert align_whisper.find_engine() is None  # no cli on PATH, no model -> auto uses classical


def test_explicit_whisper_without_engine_fails_named(tmp_path, monkeypatch):
    monkeypatch.delenv('MP_WHISPER_CLI', raising=False)
    monkeypatch.delenv('MP_WHISPER_MODEL', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))
    from motion_pipeline import align
    tr = {'sections': [{'name': 'S'}], 'words': TR_WORDS}
    with pytest.raises(align_whisper.Missing, match='speech model — install it in step 5'):
        align.align_auto('/no/audio.wav', tr, {'aligner': 'whisper'})


def test_bad_model_env_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setenv('MP_WHISPER_MODEL', str(tmp_path / 'nope.bin'))
    with pytest.raises(ValueError, match='MP_WHISPER_MODEL'):
        align_whisper.find_engine()


def test_transcribe_parses_recorded_fixture(tmp_path):
    """A fake whisper-cli writes the recorded -ojf fixture; the parser reads word times."""
    fake = tmp_path / 'whisper-cli'
    fake.write_text('#!/bin/bash\n'
                    'base=""\n'
                    'while [ $# -gt 0 ]; do case "$1" in -of) base="$2"; break;; esac; shift; done\n'
                    f'cp "{FIXTURE}" "$base.ojf.json"\n')
    fake.chmod(0o755)
    model = tmp_path / 'ggml-base.bin'
    model.write_bytes(b'x')
    rec = align_whisper.transcribe(str(fake), str(model), '/tmp/vo.wav', 'de', 'Das ist ein Test.')
    assert len(rec) == 7 and rec[0]['text'] == 'Das' and abs(rec[0]['start'] - 1.0) < 1e-6


# ---- Task 18 (spec B4): the speech model installs itself (sha256-pinned, no network in tests) ----

def _fake_model(tmp_path, monkeypatch, content=b'fake-model-bytes'):
    import hashlib
    src = tmp_path / 'fake.bin'
    src.write_bytes(content)
    monkeypatch.setattr(align_whisper, 'MODEL_SHA256', hashlib.sha256(content).hexdigest())
    monkeypatch.setattr(align_whisper, 'MODEL_SIZE', len(content))
    return src


def test_ensure_model_places_file_atomically(tmp_path, monkeypatch):
    src = _fake_model(tmp_path, monkeypatch)
    mdir = str(tmp_path / 'models')
    seen = []
    out = align_whisper.ensure_model(mdir, url='file://' + str(src),
                                     progress=lambda d, t: seen.append((d, t)))
    assert out == os.path.join(mdir, 'ggml-base.bin')
    assert os.path.isfile(out) and open(out, 'rb').read() == b'fake-model-bytes'
    assert not os.path.exists(out + '.part')
    assert seen and seen[-1][0] == seen[-1][1]   # progress reached 100%


def test_ensure_model_bad_sha_deletes_part_and_names_hashes(tmp_path, monkeypatch):
    src = _fake_model(tmp_path, monkeypatch, content=b'wrong')
    monkeypatch.setattr(align_whisper, 'MODEL_SHA256', '0' * 64)
    mdir = str(tmp_path / 'models')
    with pytest.raises(ValueError) as ei:
        align_whisper.ensure_model(mdir, url='file://' + str(src))
    assert 'sha256' in str(ei.value) and '0' * 64 in str(ei.value)
    assert not os.path.exists(os.path.join(mdir, 'ggml-base.bin.part'))
    assert not os.path.exists(os.path.join(mdir, 'ggml-base.bin'))


def test_ensure_model_existing_file_not_rehashed(tmp_path, monkeypatch):
    _fake_model(tmp_path, monkeypatch)
    mdir = str(tmp_path / 'models')
    os.makedirs(mdir)
    dst = os.path.join(mdir, 'ggml-base.bin')
    dst_bytes = b'x' * align_whisper.MODEL_SIZE   # right size, WRONG sha — must still be accepted
    open(dst, 'wb').write(dst_bytes)
    out = align_whisper.ensure_model(mdir, url='file:///nonexistent/unreachable')
    assert out == dst and open(dst, 'rb').read() == dst_bytes   # unreachable url never opened


def test_ensure_model_bad_mp_model_url_is_loud(tmp_path, monkeypatch):
    monkeypatch.setenv('MP_MODEL_URL', 'ftp://x')
    with pytest.raises(ValueError, match='MP_MODEL_URL'):
        align_whisper.ensure_model(str(tmp_path / 'm'), url=None)


def test_ensure_model_explicit_url_beats_env(tmp_path, monkeypatch):
    """Review finding: an explicit url argument must win over MP_MODEL_URL."""
    src = _fake_model(tmp_path, monkeypatch)
    monkeypatch.setenv('MP_MODEL_URL', 'file:///nonexistent/env-url')
    out = align_whisper.ensure_model(str(tmp_path / 'm'), url='file://' + str(src))
    assert open(out, 'rb').read() == b'fake-model-bytes'   # the explicit url was used
