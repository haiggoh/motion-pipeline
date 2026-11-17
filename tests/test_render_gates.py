"""Task 13 tests (plan 2026-11-16): zone gate before capture, chroma gate after each master,
disk guard scaling with total scene duration. A fake `hyperframes` on PATH records calls and
writes real PNG frames (clean or banded), so ffmpeg/ffprobe run for real."""
import json
import os
import stat
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_BIN = os.path.join(ROOT, '.venv', 'bin')

FAKE_HYPERFRAMES = r'''#!/usr/bin/env bash
# fake hyperframes: records render calls, writes 3 PNG frames into --output (banded if __BANDED)
[ "$1" = "--version" ] && { echo "0.8.31"; exit 0; }  # version probes are not renders
echo "$@" >> "$HF_CALLS"
out=""; prev=""
for a in "$@"; do
  if [ "$prev" = "--output" ]; then out="$a"; fi
  prev="$a"
done
mkdir -p "$out"
python3 - "$out" <<'PY'
import os, sys
from PIL import Image
out = sys.argv[1]
banded = os.path.exists(os.path.join(os.getcwd(), 'index.html')) and '__BANDED' in open(os.path.join(os.getcwd(), 'index.html')).read()
for i in range(1, 4):
    img = Image.new('RGB', (1920, 1080))  # the project's real resolution
    px = img.load()
    for y in range(0, 1080, 4):
        for x in range(0, 1920, 4):
            if banded:
                c = (128, 128, 255 if (x // 8) % 2 == 0 else 0)  # full-swing BLUE alternation -> Cb staircase
            else:
                c = (x // 8, y // 8, 128)        # smooth gradient
            for dy in range(4):
                for dx in range(4):
                    if x + dx < 1920 and y + dy < 1080:
                        px[x + dx, y + dy] = c
    img.save(os.path.join(out, f'frame_{i:06d}.png'))
PY
exit 0
'''

FAKE_DF = '#!/usr/bin/env bash\necho "Filesystem 1K-blocks Used Available Capacity Mounted on"\necho "disk 1000000000 1000000 1048576 1% /"\n'  # 1 GB free


def make_project(tmp_path, duration=2.0, zones=None, banded=False):
    p = tmp_path / 'proj'
    (p / 'src').mkdir(parents=True)
    proj = {'name': 'g', 'aspect': '16:9', 'resolution': [1920, 1080], 'fps': 25,
            'variants': ['default'], 'zones': zones or [], 'fonts': {'family': 'Montserrat'},
            'transcript': 'transcript.txt', 'vo': None}
    (p / 'project.json').write_text(json.dumps(proj))
    (p / 'transcript_model.json').write_text(json.dumps(
        {'sections': [{'name': 'S', 'char_start': 0}],
         'words': [{'id': 'w0', 'text': 'hello', 'section': 'S', 'emphasized': False}]}))
    (p / 'src' / 'scenes.json').write_text(json.dumps(
        [{'index': 0, 'name': 'S', 'slug': 's', 'start': 0.0, 'end': duration, 'file': 'scene_00_s.html'}]))
    (p / 'src' / 'scene_00_s.html').write_text('<html><head></head><body></body></html>')  # --banded seds in here
    return str(p)


def run_render(p, extra_env=None, bin_dir=None, banded=False):
    env = dict(os.environ)
    env['PATH'] = (bin_dir + ':' if bin_dir else '') + VENV_BIN + ':' + env['PATH']
    env.update(extra_env or {})
    cmd = ['bash', os.path.join(ROOT, 'tools', 'render_scene.sh'),
           '--project', p, '--variant', 'default', '--mode', 'test']
    if banded:
        cmd.append('--banded')  # injects window.__BANDED into the staged page
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def make_bin(tmp_path, with_df=False):
    b = tmp_path / 'bin'
    b.mkdir()
    hf = b / 'hyperframes'
    calls = tmp_path / 'hf-calls.log'
    hf.write_text(FAKE_HYPERFRAMES.replace('$HF_CALLS', str(calls)))
    hf.chmod(hf.stat().st_mode | stat.S_IEXEC)
    open(calls, 'w').close()  # the call log exists even when nothing was rendered
    if with_df:
        df = b / 'df'
        df.write_text(FAKE_DF)
        df.chmod(df.stat().st_mode | stat.S_IEXEC)
    return str(b), str(calls)


def test_clean_render_passes_chroma_gate(tmp_path):
    p = make_project(tmp_path / 'ok')
    b, calls = make_bin(tmp_path)
    r = run_render(p, bin_dir=b)
    assert r.returncode == 0, r.stderr[-600:]
    assert 'chroma gate skipped' not in r.stdout
    assert os.path.isfile(os.path.join(p, 'renders', 'default', 'scene_00_s.mp4'))
    assert open(calls).read().strip() != '', 'hyperframes was called'


def test_banded_known_bad_fails_chroma_gate_exit6(tmp_path):
    p = make_project(tmp_path / 'bad')
    b, calls = make_bin(tmp_path)
    r = run_render(p, bin_dir=b, banded=True)
    assert r.returncode == 6, (r.returncode, r.stderr[-400:])
    assert 'chroma gate FAILED' in r.stderr
    # master kept, render_info NOT marked VERIFIED
    assert os.path.isfile(os.path.join(p, 'renders', 'default', 'scene_00_s.mp4'))
    info = json.load(open(os.path.join(p, 'renders', 'default', 'render_info.json')))
    assert info.get('verify') != 'VERIFIED'


def test_zone_overlap_fails_before_hyperframes(tmp_path):
    # a zone covering every candidate text position -> check_zone exit 1 -> gate exit 6, no render
    p = make_project(tmp_path / 'z', zones=[{'section': 'S', 'rect': [0, 0, 1920, 880], 'aspect': '16:9'}])
    b, calls = make_bin(tmp_path)
    r = run_render(p, bin_dir=b)
    assert r.returncode == 6, (r.returncode, r.stderr[-400:])
    assert 'zone gate' in r.stderr
    assert open(calls).read().strip() == '', 'hyperframes must not be called after a zone-gate failure'


def test_disk_guard_scales_with_duration(tmp_path):
    p = make_project(tmp_path / 'big', duration=600.0)  # 600 s at 25 fps, 1080p -> GBs
    b, calls = make_bin(tmp_path, with_df=True)         # fake df: ~1 GB free
    r = run_render(p, bin_dir=b)
    assert r.returncode == 3, (r.returncode, r.stderr[-400:])
    assert 'disk guard' in r.stderr
    assert open(calls).read().strip() == '', 'no render started'
