"""Task 6 tests: transcript parsing, markup round-trip, stable ids, malformed input."""
import pytest

from motion_pipeline import transcript

FIXTURE = """# Intro
The *quick* brown fox.

# Main
It jumps over the lazy dog.
"""


def test_parse_sections_words_emphasis():
    m = transcript.parse(FIXTURE)
    assert [s['name'] for s in m['sections']] == ['Intro', 'Main']
    assert m['sections'][0]['char_start'] == 0
    assert m['words'][0] == {'id': 'w0', 'text': 'The', 'section': 'Intro', 'emphasized': False, 'line': 2}
    assert m['words'][1] == {'id': 'w1', 'text': 'quick', 'section': 'Intro', 'emphasized': True, 'line': 2}
    assert all(w['section'] == 'Main' for w in m['words'] if w['id'] >= 'w5')
    assert [w['text'] for w in m['words']] == ['The', 'quick', 'brown', 'fox.', 'It', 'jumps',
                                               'over', 'the', 'lazy', 'dog.']


def test_round_trip_byte_equal():
    m = transcript.parse(FIXTURE)
    assert transcript.serialize(m) == FIXTURE


def test_word_ids_stable_across_section_rename():
    m = transcript.parse(FIXTURE)
    ids_before = [w['id'] for w in m['words']]
    transcript.rename_section(m, 'Main', 'Body')
    assert [w['id'] for w in m['words']] == ids_before
    assert m['sections'][1]['name'] == 'Body'
    assert transcript.serialize(m).splitlines()[3] == '# Body'


def test_malformed_markup_fails_naming_line():
    with pytest.raises(ValueError, match=r'line 2.*unclosed'):
        transcript.parse('# S\nhello *unclosed world\n')
    with pytest.raises(ValueError, match=r'line 1'):
        transcript.parse('a stray * here\n')


def test_empty_transcript_loud_error():
    with pytest.raises(ValueError, match='empty'):
        transcript.parse('   \n  \n')
    with pytest.raises(ValueError, match='no words'):
        transcript.parse('# Only a section\n')


def test_save_load_round_trip(tmp_path):
    p = tmp_path / 'transcript.txt'
    m = transcript.parse(FIXTURE)
    transcript.save(str(p), m)
    assert p.read_text() == FIXTURE
    assert transcript.load(str(p)) == m
