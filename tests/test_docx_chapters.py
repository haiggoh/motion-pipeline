"""Task 6b (D5 + D6): docx chapter headings by FORMATTING CONTRAST + emphasis relative to
the dominant body formatting. All fixtures are synthetic docx built with tests/docx_fixture.py —
the user's real docx never enters the repo (plan rule 5).

D5: a paragraph is a chapter heading when its pStyle says so, OR it is short (<= 8 words),
does not end in . ! ? ,, is followed by body text, and its formatting differs from the
dominant body formatting (bold flag, run size w:sz, or all-caps). A trailing short line with
no body after it is not a heading; a title with the body's formatting stays text.
D6: only runs DEVIATING from the dominant body formatting become *emphasis* — an all-bold
body is not all-emphasised.
"""
from docx_fixture import build_docx

from motion_pipeline import transcript
from motion_pipeline.transcript_formats import to_markup

CAPS = ['(CONSUMER INTELLIGENCE)', '(BRAND & BUSINESS)', '(DIGITALE WELT)', '(MARKETING)',
        '(VERTRIEB)', '(STRATEGIE)', '(PRODUKT)', '(KUNDE)', '(TEAM)', '(VISION)',
        '(MISSION)', '(WERTE)', '(ZUKUNFT)']
BODY = ('the brand grows with a clear strategy and strong teams working every day on '
        'measurable results for our clients across all markets and channels worldwide today')


def _real_file_shape(path):
    """The user's real file's shape (formatting only): all-bold body paragraphs, short
    non-bold (CAPS) headline lines, a bold short fragment ending in '.', a trailing
    attribution line, and a short bold title with the body's formatting."""
    paras = [{'text': 'ACME Brand Presentation', 'bold': True}]   # title: same fmt as body
    for i, cap in enumerate(CAPS):
        paras.append({'text': cap})                               # non-bold (CAPS) headline
        paras.append({'text': f'Chapter {i} story. ' + BODY, 'bold': True})
    paras.append({'text': 'This fragment ends with a period.', 'bold': True})  # ends '.' -> not heading
    paras.append({'text': 'A short non-bold line.'})                            # differs in bold BUT ends '.' -> not heading
    paras.append({'text': BODY + ' And more.', 'bold': True})
    paras.append({'text': '(William Cooper Procter)'})            # trailing: no body after
    return build_docx(str(path), paras)


def _user_pattern(path):
    """The user's stated shape: plain body paragraphs with short BOLD lines between them."""
    paras = [
        {'text': 'First body paragraph with plenty of plain words to say something here today.'},
        {'text': 'Part One', 'bold': True},
        {'text': 'Second body paragraph with plenty of plain words to say something here now.'},
        {'text': 'Part Two', 'bold': True},
        {'text': 'Final body paragraph with plenty of plain words to say something here too.'},
    ]
    return build_docx(str(path), paras)


def _larger_size_shape(path):
    """Short lines with a larger w:sz than the body -> headings via the size trait."""
    paras = [
        {'text': 'Body text here with enough plain words to fill a paragraph nicely today.'},
        {'text': 'Big Section', 'size': 48},
        {'text': 'More body text with enough plain words to fill another paragraph today.'},
    ]
    return build_docx(str(path), paras)


def test_real_file_shape_detects_the_13_caps_headlines(tmp_path):
    """Fixture (i): the 13 short non-bold (CAPS) lines become chapters; the bold title
    (same formatting as body), the bold fragment ending '.', and the trailing attribution
    do NOT. The all-bold body is NOT emphasised (D6) — only the deviating attribution is."""
    p = _real_file_shape(tmp_path / 'real.docx')
    model = transcript.load(p)
    names = [s['name'] for s in model['sections']]
    assert names == ['Intro'] + CAPS, names
    emph = [w['text'] for w in model['words'] if w['emphasized']]
    # only runs DEVIATING from the all-bold body are emphasised: the non-bold short line
    # and the trailing attribution — no body word
    assert emph == ['A', 'short', 'non-bold', 'line.', '(William', 'Cooper', 'Procter)'], emph
    body_words = [w for w in model['words'] if w['text'] in set(BODY.split()) | {'Chapter'}]
    assert body_words and not any(w['emphasized'] for w in body_words)


def test_user_pattern_bold_short_lines_are_chapters(tmp_path):
    """Fixture (ii): bold short lines between plain paragraphs are the chapter headlines."""
    p = _user_pattern(tmp_path / 'user.docx')
    model = transcript.load(p)
    assert [s['name'] for s in model['sections']] == ['Intro', 'Part One', 'Part Two']
    assert not any(w['emphasized'] for w in model['words'])  # plain body == dominant -> no emphasis


def test_larger_run_size_short_lines_are_chapters(tmp_path):
    """Fixture (iii): a short line with larger w:sz than the dominant size is a heading."""
    p = _larger_size_shape(tmp_path / 'size.docx')
    model = transcript.load(p)
    assert [s['name'] for s in model['sections']] == ['Intro', 'Big Section']


def test_pstyle_heading_wins_over_contrast_rules(tmp_path):
    """A Heading-styled paragraph is a chapter even when long and ending in '.'."""
    p = build_docx(str(tmp_path / 'h.docx'), [
        {'text': 'A very long heading style line that ends with a period.', 'style': 'Heading1'},
        {'text': 'body words here to follow the heading line in the document today'},
    ])
    model = transcript.load(p)
    assert [s['name'] for s in model['sections']] == [
        'A very long heading style line that ends with a period.']


def test_markup_emits_hash_headings(tmp_path):
    p = _user_pattern(tmp_path / 'user.docx')
    markup = to_markup(p)
    assert '\n\n# Part One\n\n' in markup and '\n\n# Part Two\n\n' in markup
    assert '*' not in markup  # chapter names are plain; body is not emphasised


def test_caps_is_the_sole_contrast(tmp_path):
    """D5: a non-bold (CAPS) short line against a non-bold lowercase body — the all-caps trait
    ALONE makes it a heading (RED if isupper() is removed from the traits)."""
    paras = [
        {'text': 'Body paragraph one with enough plain lowercase words to count as body text here.'},
        {'text': '(SOME HEADING)'},
        {'text': 'Body paragraph two with enough plain lowercase words to count as body text now.'},
    ]
    model = transcript.load(build_docx(str(tmp_path / 'caps.docx'), paras))
    assert [s['name'] for s in model['sections']] == ['Intro', '(SOME HEADING)']


def test_d6_italic_and_size_runs_deviate(tmp_path):
    """D6: an italic run or a larger-size run INSIDE a plain body paragraph deviates from the
    dominant formatting and is emphasised; its neighbours are not (RED if italic/size are
    dropped from the deviation check)."""
    paras = [
        {'runs': [('plain words here ', False, False, None),
                  ('italics', False, True, None),
                  (' and more plain words ', False, False, None),
                  ('bigger', False, False, 48),
                  (' tail words here.', False, False, None)]},
        {'text': 'Second body paragraph with plenty of plain words to anchor the dominant style.'},
    ]
    model = transcript.load(build_docx(str(tmp_path / 'dev.docx'), paras))
    emph = [w['text'] for w in model['words'] if w['emphasized']]
    assert emph == ['italics', 'bigger'], emph
