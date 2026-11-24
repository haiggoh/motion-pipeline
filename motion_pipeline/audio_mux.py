"""audio_mux.py — VO+SFX audio tracks muxed into .mov masters, joined master, preview, re-mux
(Task 15). The video stream is ALWAYS stream-copied (-c:v copy, never re-encoded): re-muxing a
new VO take never re-renders, and the video bitstream hash is identical at every stage (E9)."""
import json
import os
import subprocess

from .util import load_json


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f'ffmpeg failed ({r.returncode}): {" ".join(cmd)}\n{r.stderr[-500:]}')
    return r


def video_md5(path: str) -> str:
    """Hash of the video bitstream (ffmpeg md5 muxer over -c:v copy)."""
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-map', '0:v', '-c', 'copy',
                        '-f', 'md5', '-'], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f'video_md5 failed on {path}: {r.stderr[-300:]}')
    return r.stdout.strip().split('=')[-1]


def sfx_cues(project_dir, timing, model):
    """Absolute-time SFX cue list from the AI manifest (Task 15b): [{file, time, gain_db, graphic}].
    Anchor = word start or section (scene) start; offset adds to it."""
    from . import ai_layer
    # manifest anchors resolve against SECTION-bearing words: the transcript model, not the
    # aligner's timing words (estimate_timings drops 'section') — Task 22 regression
    words = (model or {}).get('words') or timing.get('words') or []
    times = {w['id']: w for w in timing['words']}
    scenes = None
    sp = os.path.join(project_dir, 'src', 'scenes.json')
    if os.path.isfile(sp):
        scenes = {s['name']: s for s in load_json(sp)}
    last_end = max((w['end'] for w in timing['words']), default=0.0)
    out = []
    for g in ai_layer.load_manifest(project_dir, words):
        for i, cue in enumerate(g.get('sfx') or []):
            if isinstance(cue, dict):
                pass
            else:
                raise TypeError(f"graphic {g['id']!r} sfx cue {i}: want an object")
            anchor = g.get('anchor', {})
            if 'word' in anchor and anchor['word'] in times:
                t0 = times[anchor['word']]['start']
            elif 'section' in anchor and scenes and anchor['section'] in scenes:
                t0 = scenes[anchor['section']]['start']
            else:
                t0 = 0.0
            t = t0 + float(cue.get('offset', 0.0))
            if t < 0 or t > last_end + 1.6:
                raise ValueError(f"graphic {g['id']!r} sfx cue {i}: time {t:.3f} outside the render")
            f = cue.get('file')
            if not f:
                raise ValueError(f"graphic {g['id']!r} sfx cue {i}: missing 'file'")
            path = os.path.join(project_dir, ai_layer.DIR, f)
            if not os.path.isfile(path):
                raise ValueError(f"graphic {g['id']!r} sfx cue {i}: file not found: {f}")
            out.append({'file': path, 'time': t, 'gain_db': float(cue.get('gain_db', 0.0)),
                        'graphic': g['id']})
    return out


def _audio_filters(vo, cues, start, end, sr):
    """(inputs_extra, filter_complex) for one scene: track1 VO slice, track2 SFX mix."""
    dur = max(0.0, end - start)
    inputs = []
    filt = []
    if vo:
        inputs += ['-ss', f'{start:.6f}', '-t', f'{dur:.6f}', '-i', vo]
        filt.append(f'[1:a]aresample={sr},aformat=channel_layouts=mono,apad,atrim=0:{dur:.6f}[vo]')
    else:
        filt.append(f'anullsrc=r={sr}:cl=mono,atrim=0:{dur:.6f}[vo]')
    base_in = 1 + (1 if vo else 0)  # input 0 is the video; input 1 the VO when present
    in_scene = [(base_in + i, c) for i, c in enumerate(cues) if start <= c['time'] < end]
    parts = []
    for j, (inp, c) in enumerate(in_scene):
        ms = round((c['time'] - start) * 1000)
        vol = 10 ** (c['gain_db'] / 20.0)
        parts.append(f'[{inp}:a]aresample={sr},aformat=channel_layouts=stereo,'
                     f'adelay={ms}|{ms},volume={vol:.4f}[sfx{j}]')
    if parts:
        mix = ''.join(f'[sfx{j}]' for j in range(len(parts)))
        filt.append(';'.join(parts) +
                    f';{mix}amix=inputs={len(parts)}:normalize=0,apad,atrim=0:{dur:.6f}[sfx]')
        inputs += [x for _inp, c in in_scene for x in ('-i', c['file'])]
    else:
        filt.append(f'anullsrc=r={sr}:cl=stereo,atrim=0:{dur:.6f}[sfx]')
    return inputs, ';'.join(filt)


def mux_scene(video: str, out_mov: str, start: float, end: float, vo, sfx_cues, sr: int = 48000):
    """Mux the video-only master into <scene>.mov with track 1 VO + track 2 SFX (both pcm_s24le
    48 kHz; VO mono, SFX stereo; titles VO/SFX). Video stream copied bit-exact."""
    inputs, fc = _audio_filters(vo, sfx_cues, start, end, sr)
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', video, *inputs,
           '-map', '0:v', '-c:v', 'copy',
           '-map', '[vo]', '-c:a:0', 'pcm_s24le', '-ar', str(sr), '-ac', '1',
           '-metadata:s:a:0', 'title=VO',
           '-map', '[sfx]', '-c:a:1', 'pcm_s24le', '-ar', str(sr), '-ac', '2',
           '-metadata:s:a:1', 'title=SFX',
           '-filter_complex', fc, out_mov]
    _run(cmd)


def join(scenes, out_mov, vo, sfx_cues, sr: int = 48000):
    """Joined full-length master: concat demuxer over the scene .mov files' VIDEO streams
    (-map 0:v -c:v copy) + full-length VO + SFX. Re-encode fallback is FORBIDDEN (D2); on a
    concat error or frame-count mismatch retry once with -fflags +genpts, else return False
    (skip the joined master with a loud message)."""
    lst = out_mov + '.concat.txt'
    with open(lst, 'w') as f:
        f.writelines(f"file '{s['file']}'\n" for s in scenes)
    start, end = 0.0, sum(s['end'] - s['start'] for s in scenes)
    inputs, fc = _audio_filters(vo, sfx_cues, start, end, sr)
    for extra in ([], ['-fflags', '+genpts']):
        cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', *extra, '-i', lst,
               *inputs,
               '-map', '0:v', '-c:v', 'copy',
               '-map', '[vo]', '-c:a:0', 'pcm_s24le', '-ar', str(sr), '-ac', '1',
               '-metadata:s:a:0', 'title=VO',
               '-map', '[sfx]', '-c:a:1', 'pcm_s24le', '-ar', str(sr), '-ac', '2',
               '-metadata:s:a:1', 'title=SFX',
               '-filter_complex', fc, out_mov]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            continue
        got = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v',
                              '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', out_mov],
                             capture_output=True, text=True, check=False).stdout.strip()
        return True, int(got) if got else -1  # (ok, frame_count) — the caller compares with Σ scenes
    if os.path.exists(lst):
        os.remove(lst)
    return False, -1


def preview(scene_movs, out_mp4):
    """Small VO-synced preview from the scene .mov files via the concat demuxer as INPUT:
    1280-wide yuv420p 8-bit H.264 CRF 23 + AAC 192k stereo."""
    lst = out_mp4 + '.concat.txt'
    with open(lst, 'w') as f:
        f.writelines(f"file '{m}'\n" for m in scene_movs)
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst,
           '-vf', 'scale=1280:-2', '-c:v', 'libx264', '-crf', '23', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '192k', '-ac', '2', out_mp4]
    _run(cmd)
    os.remove(lst)


def write_timeline(out_json, scenes, fps):
    """timeline.json — machine-readable placement for tools and the AI stage."""
    data = [{'scene': s['name'], 'file': s['file'].replace('.html', '.mov'),
             'start': s['start'], 'end': s['end'],
             'start_frame': round(s['start'] * fps), 'end_frame': round(s['end'] * fps)}
            for s in scenes]
    with open(out_json, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def remux_scene(mov, tmp, start, end, vo, sfx_cues, sr=48000):
    """Re-mux one scene: video read FROM the existing .mov (-c:v copy), current VO/SFX.
    Returns True when the tmp's video-stream hash equals the original's."""
    inputs, fc = _audio_filters(vo, sfx_cues, start, end, sr)
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', mov, *inputs,
           '-map', '0:v', '-c:v', 'copy',
           '-map', '[vo]', '-c:a:0', 'pcm_s24le', '-ar', str(sr), '-ac', '1',
           '-metadata:s:a:0', 'title=VO',
           '-map', '[sfx]', '-c:a:1', 'pcm_s24le', '-ar', str(sr), '-ac', '2',
           '-metadata:s:a:1', 'title=SFX',
           '-filter_complex', fc, '-f', 'mov', tmp]
    _run(cmd)
    return video_md5(mov) == video_md5(tmp)
