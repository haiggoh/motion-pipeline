"""Task 15b tests (plan 2026-11-16): SFX declarations in the AI manifest (D4) — cue lists,
field validation naming graphic+cue, LICENSES.md requirement."""
import json
import os

import pytest

from motion_pipeline import ai_layer


def mk_project(tmp_path, manifest, licences=None, audio_file='sfx/whoosh.wav'):
    d = tmp_path / 'proj'
    gdir = d / 'ai_graphics'
    (gdir / 'sfx').mkdir(parents=True)
    (gdir / 'g.html').write_text('<div></div>')
    (gdir / audio_file).write_bytes(b'RIFFfake')
    (gdir / 'manifest.json').write_text(json.dumps(manifest))
    if licences is not None:
        (gdir / 'sfx' / 'LICENSES.md').write_text(licences)
    words = [{'id': 'w0', 'text': 'hello', 'section': 'S', 'emphasized': False}]
    return str(d), words


def base_manifest(sfx):
    return {'graphics': [{'id': 'g1', 'file': 'g.html', 'anchor': {'word': 'w0'},
                          'layer': 'above', 'sfx': sfx}]}


GOOD_LIC = 'sfx/whoosh.wav — Me — CC0\n'


def test_valid_cue_list_parsed(tmp_path):
    d, words = mk_project(tmp_path, base_manifest([
        {'file': 'sfx/whoosh.wav', 'offset': 0.0, 'gain_db': -3.0},
        {'file': 'sfx/whoosh.wav', 'offset': 1.2, 'gain_db': 0.0}]), licences=GOOD_LIC)
    out = ai_layer.load_manifest(d, words)
    assert out[0]['sfx'] == [{'file': 'sfx/whoosh.wav', 'offset': 0.0, 'gain_db': -3.0},
                             {'file': 'sfx/whoosh.wav', 'offset': 1.2, 'gain_db': 0.0}]


def test_single_object_normalised_to_list(tmp_path):
    d, words = mk_project(tmp_path, base_manifest({'file': 'sfx/whoosh.wav'}), licences=GOOD_LIC)
    out = ai_layer.load_manifest(d, words)
    assert out[0]['sfx'] == [{'file': 'sfx/whoosh.wav', 'offset': 0.0, 'gain_db': 0.0}]


def test_no_sfx_key_means_empty_list(tmp_path):
    d, words = mk_project(tmp_path, {'graphics': [{'id': 'g1', 'file': 'g.html',
                                                   'anchor': {'word': 'w0'}}]})
    assert ai_layer.load_manifest(d, words)[0]['sfx'] == []


@pytest.mark.parametrize('sfx,match', [
    ([{'file': 'sfx/whoosh.wav', 'offset': 31.0}], 'offset'),
    ([{'file': 'sfx/whoosh.wav', 'gain_db': 13.0}], 'gain_db'),
    ([{'file': 'sfx/evil.exe'}], 'must be .wav'),
    ([{'file': '../g.html'}], 'relative path'),
    ([{'file': 'sfx/missing.wav'}], 'not found'),
    ([{'offset': 0.0}], 'file'),
])
def test_invalid_cue_named_with_graphic_and_index(tmp_path, sfx, match):
    d, words = mk_project(tmp_path, base_manifest(sfx), licences=GOOD_LIC)
    with pytest.raises(ValueError, match=f"entry 'g1' sfx cue 0.*{match}"):
        ai_layer.load_manifest(d, words)


def test_missing_licences_line_refused(tmp_path):
    d, words = mk_project(tmp_path, base_manifest([{'file': 'sfx/whoosh.wav'}]),
                          licences='sfx/other.wav — Me — CC0\n')
    with pytest.raises(ValueError, match="sfx/whoosh.wav.*LICENSES.md"):
        ai_layer.load_manifest(d, words)


def test_anchor_section_cue_time_is_section_start(tmp_path):
    # via audio_mux.sfx_cues: anchor {"section": "S"} -> scene start 0.0 + offset
    from motion_pipeline import audio_mux
    d, words = mk_project(tmp_path, {'graphics': [{'id': 'g1', 'file': 'g.html',
                                                    'anchor': {'section': 'S'},
                                                    'sfx': [{'file': 'sfx/whoosh.wav', 'offset': 0.5}]}]},
                          licences=GOOD_LIC)
    import json as _json
    os.makedirs(os.path.join(d, 'src'), exist_ok=True)
    open(os.path.join(d, 'src', 'scenes.json'), 'w').write(_json.dumps(
        [{'index': 0, 'name': 'S', 'slug': 's', 'start': 2.0, 'end': 5.0, 'file': 'scene_00_s.html'}]))
    timing = {'words': [{'id': 'w0', 'text': 'hello', 'section': 'S', 'start': 2.0, 'end': 4.0}]}
    cues = audio_mux.sfx_cues(d, timing, None)
    assert cues[0]['time'] == 2.5, cues  # section start 2.0 + offset 0.5
