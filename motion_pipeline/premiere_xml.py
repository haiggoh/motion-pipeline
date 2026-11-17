"""premiere_xml.py — Final Cut Pro 7 XML (xmeml) sequence export so Premiere can import the
renders (Task 15c). Stdlib xml.etree only — opentimelineio has no cp314 wheel, so no new
runtime dependency. Premiere 26.5.3/27.0 and DaVinci Resolve both import FCP 7 XML."""
import os
import urllib.parse
import xml.etree.ElementTree as ET


def _rate(parent, fps):
    r = ET.SubElement(parent, 'rate')
    ET.SubElement(r, 'timebase').text = str(fps)
    ET.SubElement(r, 'ntsc').text = 'FALSE'
    return r


def _file_el(parent, fid, path, duration_frames):
    f = ET.SubElement(parent, 'file', {'id': fid})
    ET.SubElement(f, 'name').text = os.path.basename(path)
    ET.SubElement(f, 'pathurl').text = 'file://localhost' + urllib.parse.quote(path)
    ET.SubElement(f, 'duration').text = str(duration_frames)
    media = ET.SubElement(f, 'media')
    v = ET.SubElement(media, 'video')
    ET.SubElement(v, 'track')  # 1 video track in the file
    a = ET.SubElement(media, 'audio')
    ET.SubElement(a, 'track')  # VO
    ET.SubElement(a, 'track')  # SFX
    return f


def _clipitem(parent, cid, fid, name, start_frame, end_frame, in_frame, out_frame, sourcetrack=None):
    c = ET.SubElement(parent, 'clipitem', {'id': cid})
    ET.SubElement(c, 'name').text = name
    ET.SubElement(c, 'start').text = str(start_frame)
    ET.SubElement(c, 'end').text = str(end_frame)
    ET.SubElement(c, 'in').text = str(in_frame)
    ET.SubElement(c, 'out').text = str(out_frame)
    if sourcetrack is not None:
        st = ET.SubElement(c, 'sourcetrack')
        ET.SubElement(st, 'mediatype').text = 'audio'
        ET.SubElement(st, 'trackindex').text = str(sourcetrack)
    ET.SubElement(c, 'file', {'id': fid})
    return c


def _sequence(xmeml, seq_id, name, scenes, fps, width, height, full_master=None):
    seq = ET.SubElement(xmeml, 'sequence', {'id': seq_id})
    ET.SubElement(seq, 'name').text = name
    _rate(seq, fps)
    media = ET.SubElement(seq, 'media')
    video = ET.SubElement(media, 'video')
    fmt = ET.SubElement(video, 'format')
    sc = ET.SubElement(fmt, 'samplecharacteristics')
    ET.SubElement(sc, 'width').text = str(width)
    ET.SubElement(sc, 'height').text = str(height)
    ET.SubElement(sc, 'pixelaspectratio').text = 'square'
    ET.SubElement(sc, 'fielddominance').text = 'none'
    _rate(sc, fps)
    vtrack = ET.SubElement(video, 'track')
    audio = ET.SubElement(media, 'audio')
    af = ET.SubElement(audio, 'format')
    ET.SubElement(af, 'samplerate').text = '48000'
    ET.SubElement(af, 'depth').text = '24'
    a1 = ET.SubElement(audio, 'track')  # VO
    a2 = ET.SubElement(audio, 'track')  # SFX
    for n, s in enumerate(scenes):
        fid = f'file-{n}'
        frames = max(1, s['end_frame'] - s['start_frame'])
        _file_el(vtrack, fid, s['file'], frames)  # file declarations live in the video track
        _clipitem(vtrack, f'clip-v-{n}', fid, s.get('scene', os.path.basename(s['file'])),
                  s['start_frame'], s['end_frame'], 0, frames)
        _clipitem(a1, f'clip-a1-{n}', fid, 'VO', s['start_frame'], s['end_frame'], 0, frames,
                  sourcetrack=1)
        _clipitem(a2, f'clip-a2-{n}', fid, 'SFX', s['start_frame'], s['end_frame'], 0, frames,
                  sourcetrack=2)
        link = ET.SubElement(vtrack, 'link')
        for cid in (f'clip-v-{n}', f'clip-a1-{n}', f'clip-a2-{n}'):
            ET.SubElement(link, 'linkclipref').text = cid
        m = ET.SubElement(seq, 'marker')
        ET.SubElement(m, 'comment').text = s.get('scene', '')
        ET.SubElement(m, 'in').text = str(s['start_frame'])
        ET.SubElement(m, 'out').text = str(s['start_frame'])
    if full_master:
        _sequence_of_one(xmeml, seq_id + '-full', name + ' – full master', full_master, fps,
                         width, height)
    return seq


def _sequence_of_one(xmeml, seq_id, name, mov_path, fps, width, height):
    seq = ET.SubElement(xmeml, 'sequence', {'id': seq_id})
    ET.SubElement(seq, 'name').text = name
    _rate(seq, fps)
    media = ET.SubElement(seq, 'media')
    video = ET.SubElement(media, 'video')
    fmt = ET.SubElement(video, 'format')
    sc = ET.SubElement(fmt, 'samplecharacteristics')
    ET.SubElement(sc, 'width').text = str(width)
    ET.SubElement(sc, 'height').text = str(height)
    ET.SubElement(sc, 'pixelaspectratio').text = 'square'
    ET.SubElement(sc, 'fielddominance').text = 'none'
    _rate(sc, fps)
    vtrack = ET.SubElement(video, 'track')
    fid = 'file-full'
    _file_el(vtrack, fid, mov_path, 0)
    audio = ET.SubElement(media, 'audio')
    af = ET.SubElement(audio, 'format')
    ET.SubElement(af, 'samplerate').text = '48000'
    ET.SubElement(af, 'depth').text = '24'
    ET.SubElement(audio, 'track')
    ET.SubElement(audio, 'track')
    _clipitem(vtrack, 'clip-full', fid, os.path.basename(mov_path), 0, 1, 0, 1)
    return seq


def write_sequence(out_xml, sequence_name, scenes, fps, width, height, full_master=None):
    """scenes: timeline.json entries with ABSOLUTE 'file' paths (.mov masters) + start/end frames."""
    xmeml = ET.Element('xmeml', {'version': '5'})
    _sequence(xmeml, 'seq-1', sequence_name, scenes, fps, width, height, full_master)
    tree = ET.ElementTree(xmeml)
    ET.indent(tree, space='  ')
    with open(out_xml, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE xmeml>\n')
        f.write(ET.tostring(xmeml, encoding='unicode'))
        f.write('\n')
