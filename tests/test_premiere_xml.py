"""Task 15c tests (plan 2026-11-16): FCP 7 XML sequence export for Premiere."""
import os
import xml.etree.ElementTree as ET

import pytest

from motion_pipeline import premiere_xml

SCENES = [
    {'scene': 'Intro', 'file': '/tmp/proj/renders/default/scene_00_intro.mov',
     'start': 0.0, 'end': 2.0, 'start_frame': 0, 'end_frame': 50},
    {'scene': 'Main', 'file': '/tmp/proj/renders/default/scene_01_main.mov',
     'start': 2.0, 'end': 5.5, 'start_frame': 50, 'end_frame': 138},
]


def _write(tmp_path, **kw):
    out = str(tmp_path / 'seq.xml')
    premiere_xml.write_sequence(out, kw.pop('name', 'demo – default'), SCENES, 25, 1920, 1080, **kw)
    return out


def test_sequence_xml_parses_and_lists_three_tracks(tmp_path):
    out = _write(tmp_path)
    root = ET.parse(out).getroot()
    assert root.tag == 'xmeml' and root.get('version') == '5'
    seq = root.find('sequence')
    video = seq.find('media/video')
    audio = seq.find('media/audio')
    assert video.find('format/samplecharacteristics/width').text == '1920'
    assert len(video.findall('track')) == 1 and len(audio.findall('track')) == 2
    clips = video.find('track').findall('clipitem')
    assert len(clips) == 2  # one per scene on V1
    a1 = audio.findall('track')[0].findall('clipitem')
    a2 = audio.findall('track')[1].findall('clipitem')
    assert len(a1) == 2 and len(a2) == 2
    assert all(c.find('sourcetrack/trackindex').text == '1' for c in a1)
    assert all(c.find('sourcetrack/trackindex').text == '2' for c in a2)
    # files declared once per scene with the file's media layout
    files = video.find('track').findall('file')
    assert [f.get('id') for f in files] == ['file-0', 'file-1']
    assert len(files[0].find('media/audio').findall('track')) == 2


def test_clip_positions_match_timeline_json(tmp_path):
    out = _write(tmp_path)
    clips = ET.parse(out).getroot().find('sequence/media/video/track').findall('clipitem')
    assert (clips[1].find('start').text, clips[1].find('end').text) == ('50', '138')
    assert (clips[0].find('in').text, clips[0].find('out').text) == ('0', '50')
    # links tie V1/A1/A2 per scene
    links = ET.parse(out).getroot().find('sequence/media/video/track').findall('link')
    assert len(links) == 2
    assert [p.text for p in links[0].findall('linkclipref')] == ['clip-v-0', 'clip-a1-0', 'clip-a2-0']


def test_pathurl_is_quoted_absolute_file_url(tmp_path):
    scenes = [dict(SCENES[0], file='/tmp/my proj/Über uns/scene_00.mov')]
    out = str(tmp_path / 's.xml')
    premiere_xml.write_sequence(out, 'x', scenes, 25, 1920, 1080)
    url = ET.parse(out).getroot().find('sequence/media/video/track/file/pathurl').text
    assert url == 'file://localhost' + urllib_quote('/tmp/my proj/Über uns/scene_00.mov')
    assert '%20' in url and '%C3%9C' in url.upper()  # space + Ü percent-encoded


def urllib_quote(p):
    import urllib.parse
    return urllib.parse.quote(p)


def test_full_master_sequence_only_when_opted_in(tmp_path):
    out = _write(tmp_path)
    assert len(ET.parse(out).getroot().findall('sequence')) == 1
    out2 = _write(tmp_path, full_master='/tmp/proj/renders/default/default_full.mov')
    seqs = ET.parse(out2).getroot().findall('sequence')
    assert len(seqs) == 2 and seqs[1].find('name').text.endswith('full master')


def test_sequence_xml_reads_in_otio(tmp_path):
    otio = pytest.importorskip('opentimelineio', reason='dev dep opentimelineio not installed (printed)')
    out = _write(tmp_path)
    tl = otio.adapters.read_from_file(out, adapter_name='fcp_xml')
    v = tl.tracks[0]
    assert len(v) == 2
    assert v[1].range_in_parent().start.value == 50  # frames at the sequence timebase


def test_remux_rewrites_sequence(tmp_path):
    """render_cli writes <variant>_sequence.xml after a render and rewrites it on remux."""
    from motion_pipeline import render_cli
    from test_audio_mux import _fake_renders  # mov master + scenes + render_info fixture
    d, out = _fake_renders(tmp_path)
    rc = render_cli.remux(d)
    assert rc == 0
    xml = os.path.join(out, 'default_sequence.xml')
    assert os.path.isfile(xml), os.listdir(out)
    root = ET.parse(xml).getroot()
    assert root.tag == 'xmeml'
    clips = root.find('sequence/media/video/track').findall('clipitem')
    assert len(clips) == 1 and clips[0].find('file').get('id') == 'file-0'
    assert clips[0].find('file') is not None
