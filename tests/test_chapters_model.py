"""Task 6a under D1': the transcript model's `sections` ARE the chapters.

D1' (Progress log): on-disk `sections` keep meaning CHAPTER — an authored `#` heading, or a
docx formatting heading emitted as `# ` markup by transcript_formats (6b). Pages are derived
later, in generate (6c). So parse() must NOT grow a `chapters` key: the model stays exactly
{sections, words}, and a legacy 0.8.2-shaped transcript_model.json loads with no migration.
"""
import json

from motion_pipeline import transcript

FIX = '# Intro\nleading words here\n\n# Alpha\none two three\n\n# Beta\nfour five\n'


def test_sections_are_the_chapters_and_round_trip():
    m = transcript.parse(FIX)
    assert [s['name'] for s in m['sections']] == ['Intro', 'Alpha', 'Beta']
    names = {s['name'] for s in m['sections']}
    assert names and all(w['section'] in names for w in m['words'])
    assert transcript.serialize(m) == FIX  # byte-equal round-trip


def test_model_shape_stays_sections_words_no_chapters_key(tmp_path):
    """D1' pin: parse() output is exactly {sections, words} — no `chapters` key is added
    (a legacy 0.8.2 transcript_model.json must load unchanged)."""
    m = transcript.parse(FIX)
    assert set(m.keys()) == {'sections', 'words'}, m.keys()
    p = tmp_path / 'transcript_model.json'
    p.write_text(json.dumps(m))  # what prepare_inputs writes; what 0.8.2 wrote too
    loaded = json.loads(p.read_text())
    assert set(loaded.keys()) == {'sections', 'words'}
    assert [w['section'] for w in loaded['words']] == [w['section'] for w in m['words']]
    assert transcript.serialize(loaded) == FIX
