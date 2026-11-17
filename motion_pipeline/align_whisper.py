"""align_whisper.py — optional whisper.cpp speech-model engine, snapped to the transcript
(Task 17). Engine found live (never hardcoded); no model is ever downloaded by tests — the
U2 probe needs the user's permission and pins the whisper.cpp -ojf JSON layout."""
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile


class Missing(Exception):
    pass


def find_engine():
    """(cli, model) or None. MP_WHISPER_CLI or whisper-cli on PATH; MP_WHISPER_MODEL or the
    newest ggml-*.bin in MP_MODELS_DIR / ~/.cache/motion-pipeline/models. Set-but-missing
    env vars fail loudly naming them."""
    cli_env = os.environ.get('MP_WHISPER_CLI')
    if cli_env:
        if not (os.path.isfile(cli_env) and os.access(cli_env, os.X_OK)):
            raise ValueError(f'MP_WHISPER_CLI is set but is not an executable: {cli_env}')
        cli = cli_env
    else:
        cli = shutil.which('whisper-cli')
    if not cli:
        return None
    mdir_env = os.environ.get('MP_MODELS_DIR')
    if mdir_env and not os.path.isdir(mdir_env):
        raise ValueError(f'MP_MODELS_DIR is set but is not a directory: {mdir_env}')
    mdir = mdir_env or os.path.join(os.path.expanduser('~'), '.cache', 'motion-pipeline', 'models')
    model_env = os.environ.get('MP_WHISPER_MODEL')
    if model_env:
        if not os.path.isfile(model_env):
            raise ValueError(f'MP_WHISPER_MODEL is set but is not a file: {model_env}')
        return cli, model_env
    if os.path.isdir(mdir):
        models = sorted((f for f in os.listdir(mdir)
                         if f.startswith('ggml-') and f.endswith('.bin')),
                        key=lambda f: os.path.getmtime(os.path.join(mdir, f)))
        if models:
            return cli, os.path.join(mdir, models[-1])
    return None


def transcribe(cli, model, wav16k, language, prompt):
    """Run whisper-cli and return [{text, start, end}] — the -ojf JSON layout is pinned by the
    recorded fixture tests/fixtures/whisper_ojf_sample.json (U2 probe when the user allows)."""
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, 'out')
        cmd = [cli, '-m', model, '-l', language or 'auto', '-ml', '1', '-sow', '-ojf',
               '-tp', '0', '-tpi', '0', '-bs', '5', '-bo', '5', '-np',
               '--prompt', prompt, '-f', wav16k, '-of', base]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if r.returncode != 0:
            raise ValueError(f'whisper-cli failed ({r.returncode}): {r.stderr[-300:]}')
        data = json.load(open(base + '.ojf.json'))
    words = data.get('words')
    if words is None and isinstance(data.get('segments'), list):  # segment-word layouts
        words = [w for s in data['segments'] for w in s.get('words', [])]
    if not isinstance(words, list):
        raise ValueError(f'whisper -ojf JSON has no word list (keys: {sorted(data)})')
    return [{'text': str(w.get('text', w.get('word', ''))).strip(),
             'start': float(w['start']), 'end': float(w['end'])} for w in words]


def _norm(tok):
    t = re.sub(r'[^\wß]', '', tok.casefold(), flags=re.UNICODE)
    return t.replace('ß', 'ss')


def snap(recognised, transcript_words, classical_timing, model_path):
    """Match recognised tokens to transcript tokens (difflib); matched words take the recognised
    start/end; unmatched runs fall back to the classical timing; result monotonic."""
    rec = [_norm(r['text']) for r in recognised]
    tr = [_norm(w['text']) for w in transcript_words]
    sm = difflib.SequenceMatcher(a=rec, b=tr, autojunk=False)
    out: list = [None] * len(tr)
    matched = 0
    for tag, i1, i2, j1, _j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                out[j1 + k] = {'start': float(recognised[i1 + k]['start']),
                               'end': float(recognised[i1 + k]['end'])}
                matched += 1
    cls = {w['id']: w for w in classical_timing['words']}
    words_out = []
    prev_end = 0.0
    for w, m in zip(transcript_words, out, strict=True):
        t = m or {'start': cls[w['id']]['start'], 'end': cls[w['id']]['end']}
        start = max(float(t['start']), prev_end)
        end = max(float(t['end']), start)
        words_out.append({'id': w['id'], 'word': w['text'], 'start': round(start, 3),
                          'end': round(end, 3), 'confidence': 0.9 if m else 0.5})
        prev_end = end
    sections = {}
    for s in classical_timing['sections']:
        first = next((w for w in transcript_words if w.get('section') == s), None)
        if first:
            sections[s] = next(o['start'] for o in words_out if o['id'] == first['id'])
    sha = hashlib.sha256(open(model_path, 'rb').read(65536)).hexdigest()[:12]
    return {'source': str(model_path),
            'method': (f'whisper.cpp {os.path.basename(model_path)} (sha256 {sha}) snapped to '
                       f'transcript; classical fallback for {len(tr) - matched} words'),
            'sections': {k: round(v, 3) for k, v in sections.items()},
            'words': words_out}


def download_model(models_dir, log=print):
    """User-triggered only: download ggml-base.bin (multilingual) into the models dir."""
    import urllib.request
    url = 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin'
    os.makedirs(models_dir, exist_ok=True)
    dst = os.path.join(models_dir, 'ggml-base.bin')
    tmp = dst + '.tmp'
    log(f'downloading {url} -> {dst} (~150 MB)')
    urllib.request.urlretrieve(url, tmp)
    os.replace(tmp, dst)
    log('done')
    return dst
