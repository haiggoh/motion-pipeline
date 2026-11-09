"""Task 7 tests: deterministic aligner, G5 schema, DE/EN fixtures, re-align flow."""
import json
import subprocess

import numpy as np
import pytest

from motion_pipeline import align, transcript

TR = transcript.parse('# Intro\nThe *quick* brown fox jumps.\n\n# Main\nOver the lazy dog today.\n')


def make_wav(path, speech_runs):
    """Synthetic VO: speech_runs = [(dur_s, pause_s), ...] of 200 Hz-ish bursts with pauses."""
    sr = 16000
    parts = []
    for dur, pause in speech_runs:
        n = int(sr * dur)
        t = np.arange(n) / sr
        parts.append(0.5 * np.sin(2 * np.pi * 220 * t) * (1 + 0.3 * np.sin(2 * np.pi * 5 * t)))
        parts.append(np.zeros(int(sr * pause), dtype=np.float32))
    pcm = np.concatenate(parts).astype(np.float32)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(sr), '-ac', '1',
                          '-i', '-', '-f', 'wav', str(path)],
                         input=pcm.tobytes(), capture_output=True)
    assert raw.returncode == 0, raw.stderr.decode()[-200:]


def test_align_deterministic_byte_equal(tmp_path):
    wav = tmp_path / 'vo.wav'
    make_wav(wav, [(0.4, 0.2), (0.5, 0.2), (0.6, 0.0)])
    d1 = align.align(str(wav), TR)
    d2 = align.align(str(wav), TR)
    assert json.dumps(d1) == json.dumps(d2)
    align.validate_timing(d1)


def test_align_deterministic_across_processes(tmp_path):
    """PYTHONHASHSEED differs per process — same audio+transcript must still give
    byte-equal output when the aligner runs in two separate interpreters."""
    import sys
    wav = tmp_path / 'vo.wav'
    make_wav(wav, [(0.5, 0.2), (0.5, 0.0)])
    trj = tmp_path / 'tr.json'
    trj.write_text(json.dumps(TR))
    code = ("import json,sys; sys.path.insert(0, '.'); from motion_pipeline import align; "
            "print(json.dumps(align.align(sys.argv[1], json.load(open(sys.argv[2])))))")
    outs = []
    for seed in ('0', '12345'):
        r = subprocess.run([sys.executable, '-c', code, str(wav), str(trj)],
                           capture_output=True, text=True,
                           env={'PYTHONHASHSEED': seed, 'PATH': '/usr/bin:/bin:/opt/homebrew/bin',
                                'HOME': '/Users/bra0002h'})
        assert r.returncode == 0, r.stderr[-300:]
        outs.append(r.stdout)
    assert outs[0] == outs[1], 'aligner output differs across PYTHONHASHSEED values'


def test_align_output_schema_and_ids(tmp_path):
    wav = tmp_path / 'vo.wav'
    make_wav(wav, [(0.5, 0.2), (0.5, 0.2), (0.4, 0.0)])
    doc = align.validate_timing(align.align(str(wav), TR))
    assert set(doc['sections']) == {'Intro', 'Main'}
    assert [w['id'] for w in doc['words']] == [w['id'] for w in TR['words']]
    assert all(w['end'] > w['start'] for w in doc['words'])
    assert doc['words'][-1]['end'] <= (0.5 + 0.2 + 0.5 + 0.2 + 0.4) + 0.05


def test_german_fixture(tmp_path):
    tr = transcript.parse('# Anfang\nDie *schnelle* braune Katze springt.\n')
    wav = tmp_path / 'de.wav'
    make_wav(wav, [(0.9, 0.0)])
    doc = align.validate_timing(align.align(str(wav), tr))
    assert [w['word'] for w in doc['words']] == ['Die', 'schnelle', 'braune', 'Katze', 'springt.']
    assert doc['sections']['Anfang'] == 0.0


def test_estimate_fallback_monotonic_and_marked():
    doc = align.validate_timing(align.estimate_timings(TR, wpm=120))
    assert doc['method'].startswith('estimated')
    assert all(doc['words'][i]['end'] <= doc['words'][i + 1]['start'] + 1e-9
               for i in range(len(doc['words']) - 1))


def test_reattach_vo_keeps_ids_changes_times(tmp_path):
    wav1 = tmp_path / 'a.wav'
    make_wav(wav1, [(1.2, 0.0)])
    wav2 = tmp_path / 'b.wav'
    make_wav(wav2, [(0.6, 0.0)])
    slow = align.align(str(wav1), TR)
    fast = align.align(str(wav2), TR)
    assert [w['id'] for w in slow['words']] == [w['id'] for w in fast['words']]
    assert fast['words'][-1]['end'] < slow['words'][-1]['end']


def test_save_timing_writes_validated_json(tmp_path):
    doc = align.estimate_timings(TR)
    p = tmp_path / 'timing.json'
    align.save_timing(str(p), doc)
    assert json.loads(p.read_text()) == doc
    with pytest.raises(ValueError, match='monotonic'):
        align.save_timing(str(p), {'source': 'x', 'method': 'm', 'sections': {},
                                  'words': [{'id': 'w0', 'word': 'a', 'start': 1.0, 'end': 0.5,
                                             'confidence': 1}]})
