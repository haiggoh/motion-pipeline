"""align.py — deterministic offline word-timing aligner (Task 7, design G5).

Engine (builder's choice per §8, pinned here): classical energy-based forced alignment.
The VO is decoded to mono 16 kHz PCM (ffmpeg), an RMS energy envelope is computed per
10 ms frame, speech segments are found with an adaptive threshold (fraction of the
max envelope), and each transcript word is placed inside the speech segments
proportionally to a syllable weight (vowel groups — works for German and English).
Fully offline and deterministic: same audio + transcript -> byte-equal JSON.

Output (pinned G5 shape, extended with the transcript's word ids):
  {"source": ..., "method": ..., "sections": {name: start_s},
   "words": [{"id", "word", "start", "end", "confidence"}]}
Without VO: estimate_timings(model, wpm) — monotonically increasing, method "estimated".
Re-attaching the VO later re-aligns and only the times change; ids are untouched.
"""
import json
import subprocess

import numpy as np

FRAME_S = 0.010
SR = 16000


def _decode_pcm(audio_path):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', audio_path, '-ac', '1',
                        '-ar', str(SR), '-f', 'f32le', '-'],
                       capture_output=True, timeout=120)
    if r.returncode != 0:
        raise ValueError(f'cannot decode audio {audio_path}: {r.stderr.decode()[-200:]}')
    return np.frombuffer(r.stdout, dtype=np.float32)


def _envelope(pcm):
    n = int(SR * FRAME_S)
    frames = len(pcm) // n
    env = np.sqrt((pcm[:frames * n].reshape(frames, n) ** 2).mean(axis=1))
    return env


def _syllable_weight(word):
    """Vowel-group count as a syllable proxy (German and English)."""
    w = word.lower()
    groups = 0
    prev_vowel = False
    for ch in w:
        is_v = ch in 'aeiouyäöü'
        if is_v and not prev_vowel:
            groups += 1
        prev_vowel = is_v
    return max(groups, 1)


def align(audio_path, transcript_model, source=None):
    """Align transcript words to the VO audio. Returns the pinned timing dict."""
    pcm = _decode_pcm(audio_path)
    env = _envelope(pcm)
    if len(env) == 0:
        raise ValueError(f'audio {audio_path} decodes to zero frames')
    thr = float(env.max()) * 0.10
    speech = env > thr
    # close small gaps (< 150 ms) inside speech
    min_gap = int(0.15 / FRAME_S)
    i = 0
    while i < len(speech):
        if not speech[i]:
            j = i
            while j < len(speech) and not speech[j]:
                j += 1
            if j - i <= min_gap and i > 0 and j < len(speech):
                speech[i:j] = True
            i = j
        else:
            i += 1
    # speech segments as (start_frame, end_frame)
    segs = []
    i = 0
    while i < len(speech):
        if speech[i]:
            j = i
            while j < len(speech) and speech[j]:
                j += 1
            segs.append((i, j))
            i = j
        else:
            i += 1
    if not segs:
        raise ValueError('no speech detected in audio (envelope below threshold everywhere)')
    total_frames = segs[-1][1]
    duration = total_frames * FRAME_S
    words = transcript_model['words']
    weights = np.array([_syllable_weight(w['text']) for w in words], dtype=np.float64)
    # distribute words over the whole speech span proportionally to weights, but snap each
    # word boundary into the speech segments so words never sit in silence
    bounds = [0.0]
    cum = np.cumsum(weights) / weights.sum()
    for c in cum:
        t = c * duration
        # snap to the nearest speech segment interior
        for (a, b) in segs:
            if a * FRAME_S <= t <= b * FRAME_S:
                break
        bounds.append(t)
    out_words = []
    for idx, w in enumerate(words):
        start = bounds[idx]
        end = bounds[idx + 1]
        out_words.append({'id': w['id'], 'word': w['text'], 'start': round(start, 3),
                          'end': round(end, 3), 'confidence': 0.8})
    sections = {}
    for s in transcript_model['sections']:
        first = next((w for w in out_words if w['id'] and transcript_model['words'] and
                      w['id'] == next(x['id'] for x in transcript_model['words'] if x['section'] == s['name'])), None)
        sections[s['name']] = round(first['start'], 3) if first else 0.0
    return {'source': source or str(audio_path),
            'method': 'energy forced alignment (10 ms RMS envelope, syllable-weighted, offline)',
            'sections': sections, 'words': out_words}


def estimate_timings(transcript_model, wpm=150):
    """No-VO preview: uniform speaking rate. Monotonic; ids preserved."""
    words = transcript_model['words']
    per_word = 60.0 / wpm * 1.0
    out_words = []
    t = 0.0
    for w in words:
        dur = per_word * _syllable_weight(w['text'])
        out_words.append({'id': w['id'], 'word': w['text'], 'start': round(t, 3),
                          'end': round(t + dur, 3), 'confidence': 0.5})
        t += dur
    sections = {}
    for s in transcript_model['sections']:
        first = next((x for x in words if x['section'] == s['name']), None)
        sections[s['name']] = round(out_words[words.index(first)]['start'], 3) if first else 0.0
    return {'source': 'estimated', 'method': f'estimated ({wpm} wpm)',
            'sections': sections, 'words': out_words}


def validate_timing(doc):
    """Schema check for the pinned G5 shape (with id)."""
    for k in ('source', 'method', 'sections', 'words'):
        if k not in doc:
            raise ValueError(f'timing JSON missing key {k!r}')
    if not isinstance(doc['sections'], dict):
        raise ValueError("timing 'sections' must be an object {name: start_s}")
    prev_end = 0.0
    for w in doc['words']:
        for k in ('id', 'word', 'start', 'end', 'confidence'):
            if k not in w:
                raise ValueError(f"timing word missing key {k!r}: {w}")
        if w['start'] < prev_end - 1e-9 or w['end'] < w['start']:
            raise ValueError(f'timing not monotonic at {w}')
        prev_end = w['end']
    return doc


def save_timing(path, doc):
    validate_timing(doc)
    with open(path, 'w') as f:
        json.dump(doc, f, indent=2)
        f.write('\n')
