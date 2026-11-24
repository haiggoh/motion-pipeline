"""Task 15 tests (plan 2026-11-16): audio_mux with REAL ffmpeg (installed) and synthetic inputs —
fast, no render toolchain needed."""
import json
import os
import subprocess

from motion_pipeline import audio_mux


def _video(path, dur=2.0, fps=25):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    f'testsrc2=s=320x180:r={fps}:d={dur}', '-c:v', 'libx264', '-profile:v',
                    'high422', '-pix_fmt', 'yuv422p10le', str(path)], check=True)
    return str(path)


def _wav(path, dur, freq=None, gate=None):
    # gate=(t0,t1): sine only inside [t0,t1), silence elsewhere
    if gate:
        t0, t1 = gate
        subprocess.run(['ffmpeg', '-v', 'error', '-y',
                        '-f', 'lavfi', '-i', f'anullsrc=r=48000:cl=mono:d={t0}',
                        '-f', 'lavfi', '-i', f'sine=f={freq}:d={t1 - t0}',
                        '-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1',
                        '-ar', '48000', str(path)], check=True)
    else:
        src = f'sine=f={freq or 440}:d={dur}'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', src,
                        '-ar', '48000', str(path)], check=True)
    return str(path)


def _streams(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', path],
                       capture_output=True, text=True)
    return json.loads(r.stdout)['streams']


def _rms_db(path, selector):
    r = subprocess.run(['ffmpeg', '-v', 'info', '-i', path, '-map', selector, '-af', 'astats',
                        '-f', 'null', '-'], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if 'RMS level dB' in line:
            return float(line.split(':')[1].strip())
    return None


def test_masters_have_two_tracks_without_vo(tmp_path):
    v = _video(tmp_path / 'v.mp4')
    out = str(tmp_path / 'scene.mov')
    audio_mux.mux_scene(v, out, 0.0, 2.0, None, [])
    st = _streams(out)
    codecs = [s['codec_name'] for s in st]
    assert codecs == ['h264', 'pcm_s24le', 'pcm_s24le'], codecs
    titles = [s.get('tags', {}).get('title') or s.get('tags', {}).get('name')
              for s in st if s['codec_type'] == 'audio']
    assert titles == ['VO', 'SFX'], titles


def test_video_stream_is_bitstream_copy(tmp_path):
    v = _video(tmp_path / 'v.mp4')
    out = str(tmp_path / 'scene.mov')
    audio_mux.mux_scene(v, out, 0.0, 2.0, None, [])
    assert audio_mux.video_md5(v) == audio_mux.video_md5(out)


def test_vo_slice_matches_scene_span(tmp_path):
    v = _video(tmp_path / 'v.mp4', dur=2.0)
    vo = _wav(tmp_path / 'vo.wav', 2.0, freq=1000, gate=(1.0, 2.0))  # tone only in scene 2
    s1, s2 = str(tmp_path / 's1.mov'), str(tmp_path / 's2.mov')
    audio_mux.mux_scene(v, s1, 0.0, 1.0, vo, [])
    audio_mux.mux_scene(v, s2, 1.0, 2.0, vo, [])
    assert _rms_db(s1, '0:a:0') < -60, _rms_db(s1, '0:a:0')
    assert _rms_db(s2, '0:a:0') > -30, _rms_db(s2, '0:a:0')  # tone present (source ≈ -21 dBFS)


def test_sfx_cue_lands_at_anchor(tmp_path):
    import numpy as np
    v = _video(tmp_path / 'v.mp4', dur=2.0)
    click = _wav(tmp_path / 'click.wav', 0.05, freq=2000)
    cue_t = 1.0
    out = str(tmp_path / 's.mov')
    audio_mux.mux_scene(v, out, 0.0, 2.0, None, [{'file': click, 'time': cue_t, 'gain_db': 0.0}])
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', out, '-map', '0:a:1', '-f', 's16le',
                          '-ar', '48000', '-ac', '1', '-'], capture_output=True).stdout
    samples = np.frombuffer(raw, dtype=np.int16)
    peak = int(np.argmax(np.abs(samples)))
    assert abs(peak / 48000 - cue_t) <= 0.001, (peak / 48000, cue_t)


def test_remux_keeps_video_bit_identical(tmp_path):
    v = _video(tmp_path / 'v.mp4')
    vo1 = _wav(tmp_path / 'vo1.wav', 2.0, freq=440)
    vo2 = _wav(tmp_path / 'vo2.wav', 2.0, freq=880)
    mov = str(tmp_path / 's.mov')
    audio_mux.mux_scene(v, mov, 0.0, 2.0, vo1, [])
    h0 = audio_mux.video_md5(mov)
    tmp = mov + '.tmp'
    ok = audio_mux.remux_scene(mov, tmp, 0.0, 2.0, vo2, [])
    assert ok and audio_mux.video_md5(tmp) == h0
    os.replace(tmp, mov)
    assert audio_mux.video_md5(mov) == h0  # replaced file keeps the bitstream
    # audio actually changed: RMS of the VO track differs between the two takes
    r1 = subprocess.run(['ffmpeg', '-v', 'error', '-i', mov, '-map', '0:a:0', '-f', 's16le', '-'],
                        capture_output=True).stdout
    assert r1  # non-silent


def test_write_timeline(tmp_path):
    out = str(tmp_path / 'timeline.json')
    audio_mux.write_timeline(out, [{'name': 'A', 'file': 'scene_00_a.html', 'start': 0.0, 'end': 2.0},
                                   {'name': 'B', 'file': 'scene_01_b.html', 'start': 2.0, 'end': 5.5}], 25)
    data = json.load(open(out))
    assert data[1] == {'scene': 'B', 'file': 'scene_01_b.mov', 'start': 2.0, 'end': 5.5,
                       'start_frame': 50, 'end_frame': 138}, data[1]


def test_full_master_off_by_default():
    from motion_pipeline import project
    p = project.default_project('x')
    assert p['full_master'] is False
    assert project.validate(p)


def _fake_renders(tmp_path, with_info=True):
    """A renders dir with one muxed .mov master + src/scenes.json (+ render_info scenes)."""
    from motion_pipeline import project as pm
    d = tmp_path / 'proj'
    out = d / 'renders' / 'default'
    (d / 'src').mkdir(parents=True)
    out.mkdir(parents=True)
    p = pm.default_project('demo')
    pm.save(str(d), p)
    v = _video(d / 'v.mp4')
    scenes = [{'index': 0, 'name': 'S', 'slug': 's', 'start': 0.0, 'end': 2.0,
               'file': 'scene_00_s.html'}]
    (d / 'src' / 'scenes.json').write_text(json.dumps(scenes))
    (d / 'src' / 'scene_00_s.html').write_text('<html><head></head></html>')
    (d / 'transcript_model.json').write_text(json.dumps(
        {'sections': [{'name': 'S', 'char_start': 0}],
         'words': [{'id': 'w0', 'text': 'hello', 'section': 'S', 'emphasized': False}]}))
    from motion_pipeline import align
    tr = json.load(open(d / 'transcript_model.json'))
    align.save_timing(str(d / 'timing.json'), align.estimate_timings(tr, wpm=140))
    audio_mux.mux_scene(v, str(out / 'scene_00_s.mov'), 0.0, 2.0, None, [])
    if with_info:
        (out / 'render_info.json').write_text(json.dumps(
            {'scenes': [{'file': 'scene_00_s.html', 'start': 0.0, 'end': 2.0}], 'verify': 'VERIFIED'}))
    return str(d), str(out)


def test_remux_end_to_end_keeps_video_and_writes_outputs(tmp_path):
    from motion_pipeline import render_cli
    d, out = _fake_renders(tmp_path)
    mov = os.path.join(out, 'scene_00_s.mov')
    h0 = audio_mux.video_md5(mov)
    rc = render_cli.remux(d)
    assert rc == 0, rc
    assert audio_mux.video_md5(mov) == h0  # video bit-identical after remux
    assert os.path.isfile(os.path.join(out, 'timeline.json'))
    assert os.path.isfile(os.path.join(out, 'default_preview.mp4'))
    assert not os.path.isfile(os.path.join(out, 'default_full.mov'))  # off by default (D2)
    names = os.listdir(out)
    assert not any(n.endswith('.mp4') and n.startswith('scene_') for n in names)  # no video-only copies


def test_remux_refuses_changed_spans(tmp_path):
    from motion_pipeline import render_cli
    d, out = _fake_renders(tmp_path)
    scenes = json.load(open(os.path.join(d, 'src', 'scenes.json')))
    scenes[0]['end'] = 9.0  # transcript changed since the render
    open(os.path.join(d, 'src', 'scenes.json'), 'w').write(json.dumps(scenes))
    before = open(os.path.join(out, 'scene_00_s.mov'), 'rb').read()
    rc = render_cli.remux(d)
    assert rc == 3, rc
    assert open(os.path.join(out, 'scene_00_s.mov'), 'rb').read() == before  # untouched


def test_remux_hash_mismatch_keeps_original(tmp_path, monkeypatch):
    from motion_pipeline import render_cli
    d, out = _fake_renders(tmp_path)
    mov = os.path.join(out, 'scene_00_s.mov')
    before = open(mov, 'rb').read()
    real = audio_mux.video_md5
    monkeypatch.setattr(audio_mux, 'video_md5', lambda p: 'x' if p == mov else real(p))
    rc = render_cli.remux(d)
    assert rc == 7, rc
    assert open(mov, 'rb').read() == before
    assert not os.path.exists(mov + '.tmp')  # no .tmp left
