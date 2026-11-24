"""Build minimal synthetic .docx fixtures in tests (stdlib zipfile + XML only).

The repo's docx reader (transcript_formats._docx_to_markup) reads only word/document.xml:
paragraphs (w:p) with an optional pStyle, runs (w:r) carrying w:rPr bold/italic/size
(w:sz is in half-points) and w:t text. No real Word file is needed. Not matched by test_*.py.
"""
import zipfile
from xml.sax.saxutils import escape

W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def _run(text, bold=False, italic=False, size=None):
    props = ''
    if bold:
        props += '<w:b/>'
    if italic:
        props += '<w:i/>'
    if size:
        props += f'<w:sz w:val="{size}"/>'
    rpr = f'<w:rPr>{props}</w:rPr>' if props else ''
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def build_docx(path, paras):
    """paras: list of dicts. Keys: text (single plain run), style (pStyle val),
    bold/italic/size (apply to the single run), or runs = [(text, bold, italic, size), ...].
    Writes a minimal docx to path and returns it."""
    body = []
    for p in paras:
        ppr = f'<w:pPr><w:pStyle w:val="{p["style"]}"/></w:pPr>' if p.get('style') else ''
        runs = p.get('runs')
        if runs is None:
            runs = [(p.get('text', ''), p.get('bold', False), p.get('italic', False),
                     p.get('size'))]
        body.append(f'<w:p>{ppr}{"".join(_run(*r) for r in runs)}</w:p>')
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f'<w:document xmlns:w="{W_NS}"><w:body>{"".join(body)}</w:body></w:document>')
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('word/document.xml', xml)
    return path
