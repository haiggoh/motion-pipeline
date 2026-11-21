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
import os
import subprocess

import numpy as np

FRAME_S = 0.010
SR = 16000


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


def _speech_segments(db, thr):
    """Speech segments (frame index ranges): maximal above-threshold runs, merged across
    pauses shorter than 200 ms; pauses >= 200 ms split segments. Leading/trailing silence is
    excluded by construction. (Task 16 spec steps 2-3)"""
    n = len(db)
    speech = db > thr
    runs = []
    i = 0
    while i < n:
        if speech[i]:
            j = i
            while j < n and speech[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    min_pause = int(0.200 / FRAME_S)
    segs = []
    for a, b in runs:
        if segs and a - segs[-1][1] < min_pause:
            segs[-1] = (segs[-1][0], b)  # short gap: same segment
        else:
            segs.append((a, b))
    return segs


def _nuclei(sm_db, thr):
    """Syllable nuclei: local maxima above the threshold, >= 100 ms apart, prominence >= 3 dB
    (50 ms Hann-smoothed envelope in dB). (Task 16 spec step 4)"""
    win = int(0.050 / FRAME_S)
    min_dist = int(0.100 / FRAME_S)
    peaks = []
    n = len(sm_db)
    for i in range(1, n - 1):
        if sm_db[i] < thr or sm_db[i] < sm_db[i - 1] or sm_db[i] < sm_db[i + 1]:
            continue
        if peaks and i - peaks[-1] < min_dist:
            if sm_db[i] > sm_db[peaks[-1]]:
                peaks[-1] = i
            continue
        left = sm_db[max(0, i - win):i].min() if i > 0 else sm_db[i]
        right = sm_db[i + 1:min(n, i + win + 1)].min() if i + 1 < n else sm_db[i]
        if sm_db[i] - max(left, right) >= 3.0:
            peaks.append(i)
    return peaks


def _assign_words(segs, nuclei, syl):
    """DP: assign the words (in order) to the segments (in order), minimising
    sum |syllables(words in segment) - nuclei(segment)|; a word never crosses a pause; a
    segment gets zero words only when it has <= 1 nucleus. (Task 16 spec step 5)"""
    import functools
    W, S = len(syl), len(segs)
    nuclei_count = [sum(1 for p in nuclei if a <= p < b) for a, b in segs]
    INF = float('inf')

    @functools.lru_cache(maxsize=None)
    def dp(s, w):
        if s == S:
            return 0.0 if w == W else INF
        if w == W:
            return 0.0 if all(nuclei_count[k] <= 1 for k in range(s, S)) else INF
        best = INF
        syl_sum = 0
        for k in range(w + 1, W + 1):  # >= 1 word in this segment
            syl_sum = sum(syl[w:k])
            sub = dp(s + 1, k)
            if sub < INF:
                best = min(best, abs(syl_sum - nuclei_count[s]) + sub)
        if nuclei_count[s] <= 1:  # zero words allowed only with <= 1 nucleus
            sub = dp(s + 1, w)
            if sub < INF:
                best = min(best, abs(nuclei_count[s]) + sub)
        return best

    # reconstruct
    assign = []
    s, w = 0, 0
    while s < S:
        best, best_k = INF, w
        syl_sum = 0
        for k in range(w + 1, W + 1):
            syl_sum = sum(syl[w:k])
            sub = dp(s + 1, k)
            if sub < INF and abs(syl_sum - nuclei_count[s]) + sub < best:
                best, best_k = abs(syl_sum - nuclei_count[s]) + sub, k
        if nuclei_count[s] <= 1:
            sub = dp(s + 1, w)
            if sub < INF and abs(nuclei_count[s]) + sub <= best:
                best, best_k = abs(nuclei_count[s]) + sub, w
        assign.append((s, w, best_k))
        w = best_k
        s += 1
    return assign, nuclei_count


def align(audio_path, transcript_model, source=None):
    """Classical aligner (Task 16 spec): voice-band energy envelope, pause runs, syllable
    nuclei, DP word assignment. Returns the pinned timing dict."""
    # X1: decode ONCE, in the voice band (the earlier plain _decode_pcm + _envelope were
    # computed and then discarded — doubling part of the "computing timings" wait)
    # 1. decode is already mono 16 kHz; voice band:
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', audio_path, '-af', 'highpass=f=300,lowpass=f=3400',
                        '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, timeout=120)
    if r.returncode != 0:
        raise ValueError(f'cannot decode audio {audio_path}: {r.stderr.decode()[-200:]}')
    pcm = np.frombuffer(r.stdout, dtype=np.float32)
    env = _envelope(pcm)
    if len(env) == 0:
        raise ValueError(f'audio {audio_path} decodes to zero frames')
    db = 20 * np.log10(env + 1e-9)
    # 2. adaptive threshold
    floor = float(np.percentile(db, 10))
    p95 = float(np.percentile(db, 95))
    thr = floor + 0.35 * (p95 - floor)
    segs = _speech_segments(db, thr)
    if not segs:
        raise ValueError('no speech detected in audio (envelope below threshold everywhere)')
    # 4. syllable nuclei on the Hann-smoothed envelope
    win = int(0.050 / FRAME_S)
    sm = np.convolve(env, np.hanning(win), mode='same')
    sm_db = 20 * np.log10(sm + 1e-9)
    nuclei = _nuclei(sm_db, thr)
    # 5. assign words to segments
    words = transcript_model['words']
    syl = [_syllable_weight(w['text']) for w in words]
    assign, nuclei_count = _assign_words(segs, nuclei, syl)
    # 6-7. word times within segments + confidence
    out_words = []
    for s, (a, b) in enumerate(segs):
        w0, w1 = assign[s][1], assign[s][2]
        seg_nuclei = [p for p in nuclei if a <= p < b]
        syl_in_seg = sum(syl[w0:w1])
        conf = round(1.0 - abs(syl_in_seg - nuclei_count[s]) / max(syl_in_seg, nuclei_count[s], 1), 2)
        seg_start_s = a * FRAME_S
        seg_end_s = b * FRAME_S
        prev_end = out_words[-1]['end'] if out_words else 0.0
        if not seg_nuclei:
            # no nuclei detected in this segment: distribute its words evenly across it
            n_seg = max(1, w1 - w0)
            for k in range(w0, w1):
                w = words[k]
                start = seg_start_s + (k - w0) * (seg_end_s - seg_start_s) / n_seg
                end = seg_start_s + (k - w0 + 1) * (seg_end_s - seg_start_s) / n_seg
                out_words.append({'id': w['id'], 'word': w['text'], 'start': round(start, 3),
                                  'end': round(end, 3), 'confidence': conf})
            continue
        cum = 0
        for k in range(w0, w1):
            w = words[k]
            n_idx = min(cum, len(seg_nuclei) - 1)
            start = max(seg_nuclei[n_idx] * FRAME_S - 0.040, seg_start_s, prev_end)
            if k + 1 < w1:
                n_next = min(cum + syl[k], len(seg_nuclei) - 1)
                end = seg_nuclei[n_next] * FRAME_S - 0.040
            else:
                end = seg_end_s
            end = min(max(end, start), seg_end_s)
            out_words.append({'id': w['id'], 'word': w['text'], 'start': round(start, 3),
                              'end': round(end, 3), 'confidence': conf})
            prev_end = end
            cum += syl[k]
    sections = {}
    for s in transcript_model['sections']:
        first = next((w for w in out_words if w['id'] == next(
            (x['id'] for x in words if x['section'] == s['name']), None)), None)
        sections[s['name']] = round(first['start'], 3) if first else 0.0
    return {'source': source or str(audio_path),
            'method': 'classical: voice-band energy, pause runs, syllable nuclei',
            'sections': sections, 'words': out_words}


def estimate_timings(transcript_model, wpm=150):
    """No-VO preview: 60/wpm seconds per WORD (finding 15). Monotonic; ids preserved."""
    words = transcript_model['words']
    per_word = 60.0 / wpm
    out_words = []
    t = 0.0
    for w in words:
        out_words.append({'id': w['id'], 'word': w['text'], 'start': round(t, 3),
                          'end': round(t + per_word, 3), 'confidence': 0.5})
        t += per_word
    sections = {}
    for s in transcript_model['sections']:
        first = next((x for x in words if x['section'] == s['name']), None)
        sections[s['name']] = round(out_words[words.index(first)]['start'], 3) if first else 0.0
    return {'source': 'estimated', 'method': f'estimated ({wpm} wpm)',
            'sections': sections, 'words': out_words}


def align_auto(audio_path, transcript_model, project=None):
    """Choose the engine per the project's `aligner` key: 'auto' = whisper when find_engine()
    returns a pair, else classical; explicit 'whisper' without an engine -> Missing naming it.
    (Task 17)"""
    from . import align_whisper
    choice = (project or {}).get('aligner', 'auto')
    eng = align_whisper.find_engine()
    if choice == 'whisper' and not eng:
        raise align_whisper.Missing('speech model — install it in step 5 or set aligner to Classical')
    if (choice == 'whisper' or choice == 'auto') and eng:
        classical = align(audio_path, transcript_model)
        # decode to a 16 kHz wav for whisper
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            wav = os.path.join(td, 'vo.wav')
            r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', audio_path, '-ar', '16000',
                                '-ac', '1', wav], capture_output=True)
            if r.returncode != 0:
                raise ValueError(f'cannot decode {audio_path} to 16k wav: {r.stderr.decode()[-200:]}')
            prompt = ' '.join(w['text'] for w in transcript_model['words'][:120])
            rec = align_whisper.transcribe(eng[0], eng[1], wav,
                                           (project or {}).get('language', 'de'), prompt)
        return align_whisper.snap(rec, transcript_model['words'], classical, eng[1])
    return align(audio_path, transcript_model)


def measured_wpm(timing):
    """Measured words-per-minute of an aligned timing: words / (last word end − first word
    start) × 60, rounded. None when the timing was estimated (no voiceover). (spec B4)"""
    if timing.get('source') == 'estimated':
        return None
    words = timing.get('words') or []
    if len(words) < 2:
        return None
    span = words[-1]['end'] - words[0]['start']
    if span <= 0:
        return None
    return round(len(words) / span * 60)


def inputs_fingerprint(project_dir, p):
    """sha256 over the transcript bytes + the VO file bytes (or "no-vo") + wpm + language +
    aligner — stored in timing.json as "inputs" (Task 21 freshness gate). With a VO set the
    wpm is EXCLUDED: it no longer affects the timing (B4)."""
    import hashlib
    h = hashlib.sha256()
    tpath = os.path.join(project_dir, p.get('transcript') or 'transcript.txt')
    h.update(open(tpath, 'rb').read() if os.path.isfile(tpath) else b'<missing>')
    vo = p.get('vo')
    if vo:
        vpath = vo if os.path.isabs(vo) else os.path.join(project_dir, vo)
        h.update(open(vpath, 'rb').read() if os.path.isfile(vpath) else b'<missing-vo>')
    else:
        h.update(b'no-vo')
    wpm_part = '' if vo else f"{p.get('wpm', 140)}|"   # B4: wpm is a measured indicator with a VO
    h.update(f"{wpm_part}{p.get('language', 'auto')}|{p.get('aligner', 'auto')}".encode())
    return h.hexdigest()


def timing_is_fresh(project_dir, p=None):
    """True when timing.json exists and its "inputs" fingerprint matches the current inputs."""
    tp = os.path.join(project_dir, 'timing.json')
    if not os.path.isfile(tp):
        return False
    try:
        doc = json.load(open(tp))
    except (OSError, json.JSONDecodeError):
        return False
    stored = doc.get('inputs')
    if not stored:
        return False
    if p is None:
        from . import project as pm
        try:
            p = pm.load(project_dir)
        except Exception:
            return False
    return stored == inputs_fingerprint(project_dir, p)


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
