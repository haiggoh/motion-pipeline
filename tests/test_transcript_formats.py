"""Task 15 (spec B4): transcript formats — md/rtf/doc/docx/pdf load into the repo markup.
Fixtures live in tests/fixtures/transcripts/ (built once: docx via zipfile, rtf/doc via
textutil, pdf hand-built with a text layer)."""
import os

import pytest

from motion_pipeline import align, project, transcript
from motion_pipeline.transcript_formats import SUPPORTED, to_markup

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'transcripts')


def test_supported_list():
    assert SUPPORTED == ('.txt', '.md', '.rtf', '.doc', '.docx', '.pdf')


def test_docx_maps_heading_and_bold():
    model = transcript.load(os.path.join(FIX, 'sample.docx'))
    assert [s['name'] for s in model['sections']] == ['Intro']
    assert any(w['text'] == 'world' and w.get('emphasized') for w in model['words'])
    assert not any(w['text'] == 'Hello' and w.get('emphasized') for w in model['words'])


def test_md_headings_and_emphasis():
    p = os.path.join(FIX, '_tmp.md')
    open(p, 'w').write('## Part One\nSome **bold** and *italic* words\n')
    try:
        model = transcript.load(p)
        assert [s['name'] for s in model['sections']] == ['Part One']
        assert any(w['text'] == 'bold' and w.get('emphasized') for w in model['words'])
        assert any(w['text'] == 'italic' and w.get('emphasized') for w in model['words'])
    finally:
        os.remove(p)


def test_rtf_and_doc_match_txt_source_words():
    want = transcript.load(os.path.join(FIX, 'source.txt'))
    for ext in ('rtf', 'doc'):
        got = transcript.load(os.path.join(FIX, f'sample.{ext}'))
        assert [w['text'] for w in got['words']] == [w['text'] for w in want['words']], ext


def test_pdf_extracts_text():
    got = transcript.load(os.path.join(FIX, 'sample.pdf'))
    want = transcript.load(os.path.join(FIX, 'source.txt'))
    assert [w['text'] for w in got['words']] == [w['text'] for w in want['words']]


def test_unknown_extension_named():
    p = os.path.join(FIX, '_tmp.xyz')
    open(p, 'w').write('x')
    try:
        with pytest.raises(ValueError) as ei:
            to_markup(p)
        assert '.xyz' in str(ei.value) and '.docx' in str(ei.value)
    finally:
        os.remove(p)


def test_pdf_import_error_path_named(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def no_pypdf(name, *a, **kw):
        if name == 'pypdf':
            raise ImportError('no pypdf')
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, '__import__', no_pypdf)
    with pytest.raises(ValueError, match='pypdf'):
        to_markup(os.path.join(FIX, 'sample.pdf'))


def test_fingerprint_tracks_source_bytes(tmp_path):
    d = str(tmp_path / 'p')
    project.save(d, project.default_project('demo'))
    src = os.path.join(FIX, 'sample.docx')
    dst = os.path.join(d, 'transcript.docx')
    import shutil
    shutil.copy(src, dst)
    p = project.load(d)
    p['transcript'] = 'transcript.docx'
    fp1 = align.inputs_fingerprint(d, p)
    with open(dst, 'ab') as f:
        f.write(b'x')                      # bytes change -> fingerprint changes
    fp2 = align.inputs_fingerprint(d, p)
    assert fp1 != fp2


def test_source_file_never_written(tmp_path):
    src = os.path.join(FIX, 'sample.docx')
    before = open(src, 'rb').read()
    transcript.load(src)
    assert open(src, 'rb').read() == before
