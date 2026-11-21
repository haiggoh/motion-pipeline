"""Task 7 tests: deterministic aligner, G5 schema, DE/EN fixtures, re-align flow."""
import json
import os
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


def _synthetic_vo(path, phrases):
    """numpy burst fixture: 200 Hz-modulated 1 kHz tone, 120 ms per syllable, planted pauses."""
    import numpy as np
    sr = 16000
    parts = [np.zeros(int(1.0 * sr), dtype=np.float32)]  # 1.0 s leading silence
    for phrase_words, pause_after in phrases:
        for _ in range(phrase_words):  # one 120 ms burst per syllable
            t = np.arange(int(0.120 * sr)) / sr
            parts.append(0.6 * np.sin(2 * np.pi * 1000 * t) * (1 + 0.5 * np.sin(2 * np.pi * 200 * t)))
        parts.append(np.zeros(int(pause_after * sr), dtype=np.float32))
    pcm = np.concatenate(parts).astype(np.float32)
    import subprocess
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(sr), '-ac', '1',
                    '-i', '-', str(path)], input=pcm.tobytes(), check=True)
    return str(path), 1.0  # leading silence seconds


def test_leading_silence_respected(tmp_path):
    wav, lead = _synthetic_vo(tmp_path / 'vo.wav', [(3, 0.4), (3, 0.0)])
    tr = {'sections': [{'name': 'S'}],
          'words': [{'id': f'w{i}', 'text': f'wort{i}', 'section': 'S', 'emphasized': False}
                    for i in range(6)]}
    doc = align.align(wav, tr)
    assert doc['words'][0]['start'] >= lead - 0.05, doc['words'][0]  # old algorithm gave 0.0


def test_words_snap_to_pauses(tmp_path):
    wav, lead = _synthetic_vo(tmp_path / 'vo.wav', [(3, 0.4), (3, 0.0)])
    tr = {'sections': [{'name': 'S'}],
          'words': [{'id': f'w{i}', 'text': f'wort{i}', 'section': 'S', 'emphasized': False}
                    for i in range(6)]}
    doc = align.align(wav, tr)
    # the 4th word starts the second phrase, right after the 400 ms pause (nucleus - 40 ms lead;
    # a 120 ms burst's energy peak sits ~60 ms in, so allow for that)
    phrase2_onset = lead + 3 * 0.120 + 0.4
    assert abs(doc['words'][3]['start'] - phrase2_onset) <= 0.2, (doc['words'][3], phrase2_onset)


def test_estimate_wpm_is_per_word():
    tr = {'sections': [{'name': 'S'}],
          'words': [{'id': f'w{i}', 'text': 'w', 'section': 'S', 'emphasized': False}
                    for i in range(60)]}
    doc = align.estimate_timings(tr, wpm=140)
    total = doc['words'][-1]['end']
    assert abs(total - 60 * 60 / 140) < 0.05 * 60 * 60 / 140, total  # 25.7 s +-5 %


def test_say_german_vo_monotonic_and_inside_audio(tmp_path):
    import shutil, subprocess
    if not shutil.which('say'):
        pytest.skip('say not available (printed)')
    wav = tmp_path / 'vo.aiff'
    subprocess.run(['say', '-v', 'Anna', '[[slnc 1000]] Das ist ein Test. [[slnc 600]] Zweiter Satz hier.',
                    '-o', str(wav)], check=True)
    tr = {'sections': [{'name': 'S'}],
          'words': [{'id': f'w{i}', 'text': t, 'section': 'S', 'emphasized': False}
                    for i, t in enumerate(['Das', 'ist', 'ein', 'Test.', 'Zweiter', 'Satz', 'hier.'])]}
    doc = align.align(str(wav), tr)
    align.validate_timing(doc)
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                '-of', 'csv=p=0', str(wav)], capture_output=True, text=True).stdout.strip())
    assert doc['words'][-1]['end'] <= dur + 0.2


def test_save_timing_writes_validated_json(tmp_path):
    doc = align.estimate_timings(TR)
    p = tmp_path / 'timing.json'
    align.save_timing(str(p), doc)
    assert json.loads(p.read_text()) == doc
    with pytest.raises(ValueError, match='monotonic'):
        align.save_timing(str(p), {'source': 'x', 'method': 'm', 'sections': {},
                                  'words': [{'id': 'w0', 'word': 'a', 'start': 1.0, 'end': 0.5,
                                             'confidence': 1}]})


# golden captured from align() on the fixture BEFORE the single-decode change (X1),
# with the path-bearing 'source' key excluded so the hash is path-independent
GOLDEN_SHA256 = '878a32774eaf2ee62a84c607be7cb5ac868c644039024f226880d2830ba07a9f'


def test_align_decodes_voiceover_once_and_output_is_unchanged(tmp_path, monkeypatch):
    """X1: align() runs ffmpeg exactly ONCE (the voice-band decode); the earlier plain
    _decode_pcm + _envelope were discarded. Output must be byte-identical to the golden."""
    import hashlib
    wav = tmp_path / 'vo.wav'
    make_wav(wav, [(0.4, 0.2), (0.5, 0.2), (0.6, 0.0)])
    calls = {'n': 0}
    real_run = subprocess.run

    def counting_run(*a, **kw):
        calls['n'] += 1
        return real_run(*a, **kw)

    monkeypatch.setattr(subprocess, 'run', counting_run)
    out = align.align(str(wav), TR)
    assert calls['n'] == 1, f'ffmpeg ran {calls["n"]} times (want 1)'
    align.validate_timing(out)
    out.pop('source', None)   # embeds the audio path — excluded from the golden
    digest = hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()
    assert digest == GOLDEN_SHA256, 'timing output changed after the single-decode fix'


# ---- Task 16 (B4): measured wpm + fingerprint excludes wpm when a VO is set ----

def test_measured_wpm_from_aligned_timing():
    timing = {'source': 'whisper', 'method': 'whisper', 'sections': {},
              'words': [{'id': 'w0', 'word': 'a', 'start': 0.0, 'end': 0.5},
                        {'id': 'w1', 'word': 'b', 'start': 0.5, 'end': 1.0},
                        {'id': 'w2', 'word': 'c', 'start': 1.0, 'end': 1.5},
                        {'id': 'w3', 'word': 'd', 'start': 1.5, 'end': 2.0}]}
    assert align.measured_wpm(timing) == 120          # 4 words over 2.0 s


def test_measured_wpm_none_when_estimated():
    est = align.estimate_timings(transcript.parse('# S\na b c d\n'), wpm=140)
    assert align.measured_wpm(est) is None


def test_fingerprint_excludes_wpm_with_vo(tmp_path):
    d = str(tmp_path / 'p')
    os.makedirs(d)
    (open(os.path.join(d, 'transcript.txt'), 'w')).write('# S\nhello world\n')
    (open(os.path.join(d, 'vo.wav'), 'w')).write('x')
    p = {'transcript': 'transcript.txt', 'vo': 'vo.wav', 'wpm': 140,
         'language': 'auto', 'aligner': 'auto'}
    fp1 = align.inputs_fingerprint(d, p)
    fp2 = align.inputs_fingerprint(d, {**p, 'wpm': 200})
    assert fp1 == fp2, 'wpm must not affect the fingerprint when a VO is set'
    fp3 = align.inputs_fingerprint(d, {**p, 'vo': None})
    fp4 = align.inputs_fingerprint(d, {**p, 'vo': None, 'wpm': 200})
    assert fp3 != fp4, 'without a VO the wpm still drives the fingerprint'
