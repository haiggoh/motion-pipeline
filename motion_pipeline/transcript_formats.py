"""transcript_formats.py — load .txt/.md/.rtf/.doc/.docx/.pdf transcripts into the repo's
transcript markup ('# ' sections, '*emphasis*', blank-line paragraphs) (spec B4).

.txt plain UTF-8 · .md maps headings/bold/italic · .docx via stdlib zip+XML (Heading-styled
paragraphs -> chapters; formatting-contrast headings D5 -> '# ' chapters; emphasis D6 is
relative to the dominant body formatting, so an all-bold body is not all-emphasised) ·
.rtf/.doc via macOS textutil (plain text; headings are not recovered — noted in the screen's
label) · .pdf via pypdf (lazy import, named error when missing). The source file is never
written.
"""
import os
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

SUPPORTED = ('.txt', '.md', '.rtf', '.doc', '.docx', '.pdf')
_W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
_HEADING_STYLES = {'Title', 'Heading1', 'Heading2', 'Heading3', 'Heading4', 'Heading5', 'Heading6'}


def to_markup(path):
    """The file's content as transcript markup. Unknown extension -> ValueError naming it."""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.txt':
        with open(path, encoding='utf-8') as f:
            return f.read()
    if ext == '.md':
        with open(path, encoding='utf-8') as f:
            return _md_to_markup(f.read())
    if ext == '.docx':
        return _docx_to_markup(path)
    if ext in ('.rtf', '.doc'):
        return _textutil(path)
    if ext == '.pdf':
        return _pdf_to_markup(path)
    raise ValueError(f"unsupported transcript format '{ext or '(none)'}' ({path}) — "
                     f"supported: {', '.join(SUPPORTED)}")


def _md_to_markup(text):
    out = []
    for line in text.splitlines():
        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if m:
            out.append('# ' + m.group(2))
            continue
        # bold then italic: **x** / __x__ -> *x*, then *x* / _x_ -> *x*
        line = re.sub(r'\*\*(.+?)\*\*|__(.+?)__', lambda m: '*' + (m.group(1) or m.group(2)) + '*', line)
        line = re.sub(r'(?<![*\w])\*(.+?)\*(?![*\w])|(?<![\w_])_(.+?)_(?![\w_])',
                      lambda m: '*' + (m.group(1) or m.group(2)) + '*', line)
        out.append(line)
    return '\n'.join(out) + '\n'


def _docx_paragraphs(root):
    """Non-empty paragraphs as dicts: {text, style, runs} — runs = [(text, bold, italic,
    size_halfpoints|None)]."""
    paras = []
    for p in root.iter(_W + 'p'):
        style_el = p.find(f'{_W}pPr/{_W}pStyle')
        style = style_el.get(_W + 'val') if style_el is not None else ''
        runs = []
        for r in p.findall(_W + 'r'):
            text = ''.join(t.text or '' for t in r.findall(_W + 't'))
            if not text:
                continue
            rpr = r.find(_W + 'rPr')
            bold = rpr is not None and rpr.find(_W + 'b') is not None
            italic = rpr is not None and rpr.find(_W + 'i') is not None
            sz = rpr.find(_W + 'sz') if rpr is not None else None
            size = int(sz.get(_W + 'val')) if sz is not None else None
            runs.append((text, bold, italic, size))
        text = ''.join(t for t, *_ in runs).strip()
        if text:
            paras.append({'text': text, 'style': style, 'runs': runs})
    return paras


def _mode(values, default):
    from collections import Counter
    vals = list(values)
    return Counter(vals).most_common(1)[0][0] if vals else default


def _para_traits(p):
    """(all_bold, modal_run_size, all_caps) — the formatting a paragraph carries."""
    runs = p['runs']
    bold = bool(runs) and all(b for _, b, _, _ in runs)
    sizes = [s for _, _, _, s in runs if s is not None]
    return bold, _mode(sizes, None), p['text'].isupper()


def _dominant_traits(paras):
    """The DOMINANT body formatting (mode over non-heading paragraphs): (bold, size, caps)."""
    bodies = [p for p in paras if p['style'] not in _HEADING_STYLES]
    if not bodies:
        return (False, None, False)
    traits = [_para_traits(p) for p in bodies]
    return (_mode([t[0] for t in traits], False),
            _mode([t[1] for t in traits], None),
            _mode([t[2] for t in traits], False))


def _is_heading(p, dom, has_body_after):
    """D5: a paragraph is a chapter heading when its pStyle says so, OR it is short (<= 8
    words), does not end in . ! ? , is followed by body text, and its formatting DIFFERS
    from the dominant body formatting (bold flag, run size w:sz, or all-caps). A trailing
    short line with no body after it is not a heading."""
    if p['style'] in _HEADING_STYLES:
        return True
    if not has_body_after:
        return False
    if len(p['text'].split()) > 8:
        return False
    if p['text'][-1] in '.,!?':
        return False
    return _para_traits(p) != dom


def _mark_runs(runs, dom):
    """D6: emphasis relative to the dominant body — a run is *emphasised* only when it
    DEVIATES from the dominant formatting (bold flag, italic, or a non-dominant size).
    Bold that IS the body formatting is not emphasis (the real docx is all-bold body)."""
    dom_b, dom_s, _ = dom
    parts = []
    for text, bold, italic, size in runs:
        deviates = bold != dom_b or italic or (size is not None and size != dom_s)
        if deviates:
            text = re.sub(r'\S+', lambda m: '*' + m.group(0) + '*', text)
        parts.append(text)
    return ''.join(parts).strip()


def _docx_to_markup(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml')
    root = ET.fromstring(xml)
    paras = _docx_paragraphs(root)
    dom = _dominant_traits(paras)
    out = []
    for i, p in enumerate(paras):
        has_body_after = any(q['text'] for q in paras[i + 1:])
        if _is_heading(p, dom, has_body_after):
            out.append('# ' + p['text'])   # chapter names are plain text
        else:
            out.append(_mark_runs(p['runs'], dom))
    return '\n\n'.join(out) + '\n'


def _textutil(path):
    """macOS textutil plain-text conversion (headings are NOT recovered — noted in the UI)."""
    r = subprocess.run(['textutil', '-convert', 'txt', '-stdout', path],
                       capture_output=True, text=True, timeout=30, check=False)
    if r.returncode != 0:
        raise ValueError(f'cannot convert {path}: {r.stderr.strip()[-200:]}')
    return r.stdout


def _pdf_to_markup(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ValueError('PDF support needs pypdf — reinstall motion-pipeline '
                         '(brew reinstall motion-pipeline)') from None
    try:
        reader = PdfReader(path)
        pages = [pg.extract_text() or '' for pg in reader.pages]
    except Exception as e:
        raise ValueError(f'cannot read PDF {path}: {e}') from e
    return '\n\n'.join(pages) + '\n'
