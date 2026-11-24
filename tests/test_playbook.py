"""Task 22 tests (plan 2026-11-16): the menu-owned MOTION_GRAPHICS_PLAYBOOK.md is rendered with
LIVE project facts (resolution, palette hex, scene row, word id, check command with the real
project path) and is REGENERATED on every write — a hand edit is overwritten; the project's
AGENTS.md lists it as menu-owned."""
import json
import os

from projfix import make_project

from motion_pipeline import generate, playbook
from motion_pipeline.scheme import derive_palette, resolve_variant


def test_playbook_has_live_facts(tmp_path):
    pd = make_project(tmp_path / 'p')
    generate.generate(pd)
    out = playbook.write_playbook(pd)
    assert out == os.path.join(pd, 'MOTION_GRAPHICS_PLAYBOOK.md')
    assert os.path.isfile(out)
    text = open(out).read()
    p = json.load(open(os.path.join(pd, 'project.json')))
    W, H = p['resolution']
    assert f'frame {W}x{H} at {p["fps"]} fps' in text                     # resolution + fps, live
    pal = derive_palette(resolve_variant(pd, 'default'))
    assert any(h in text for h in pal.values())                           # a palette hex
    scenes = json.load(open(os.path.join(pd, 'src', 'scenes.json')))
    assert scenes[0]['name'] in text                                      # a scene row
    words = json.load(open(os.path.join(pd, 'transcript_model.json')))['words']
    assert any(w['id'] in text for w in words)                            # a word id
    assert f'motion-pipeline --check-graphics {pd}' in text               # check command, real path
    assert f'motion-pipeline --render-test {pd}' in text                  # render-test command


def test_playbook_regenerated_not_hand_edited(tmp_path):
    pd = make_project(tmp_path / 'p')
    generate.generate(pd)
    out = playbook.write_playbook(pd)
    with open(out, 'a') as f:
        f.write('\n# HAND EDIT — must be overwritten\n')
    playbook.write_playbook(pd)
    assert '# HAND EDIT' not in open(out).read()                          # regenerated, byte-level
    agents = open(os.path.join(pd, 'AGENTS.md')).read()
    assert 'MOTION_GRAPHICS_PLAYBOOK.md' in agents                        # listed as menu-owned


def test_playbook_sections_present(tmp_path):
    pd = make_project(tmp_path / 'p')
    generate.generate(pd)
    text = open(playbook.write_playbook(pd)).read()
    for h in ('## 0 Start with questions', '## 1 The three zones', '## 2 Files and manifest',
              '## 3 The page API + mp_lib', '## 4 Timing rules', '## 5 Layout rules',
              '## 6 Determinism rules', '## 7 Sound effects', '## 8 Check your work',
              '## 9 Done criteria + hand back'):
        assert h in text, h


def test_playbook_has_zones_and_manifest_entries(tmp_path):
    pd = make_project(tmp_path / 'p')
    p = json.load(open(os.path.join(pd, 'project.json')))
    p['zones'] = [{'section': 'Welcome', 'rect': [760, 440, 400, 200]}]
    json.dump(p, open(os.path.join(pd, 'project.json'), 'w'))
    words = json.load(open(os.path.join(pd, 'transcript_model.json')))['words']
    w = next(w for w in words if w['section'] == 'Welcome')
    ag = os.path.join(pd, 'ai_graphics')
    os.makedirs(ag)
    open(os.path.join(ag, 'pulse.js'), 'w').write('window.__pulse = 1;\n')
    json.dump({'graphics': [{'id': 'pulse', 'file': 'pulse.js', 'anchor': {'word': w['id']},
                             'layer': 'below'}]}, open(os.path.join(ag, 'manifest.json'), 'w'))
    generate.generate(pd)
    text = open(playbook.write_playbook(pd)).read()
    assert '[760, 440, 400, 200]' in text        # live zone rect in the zones table
    assert '`pulse`' in text                     # live manifest entry listed
