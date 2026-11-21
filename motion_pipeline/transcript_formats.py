"""transcript_formats.py — load .txt/.md/.rtf/.doc/.docx/.pdf transcripts into the repo's
transcript markup ('# ' sections, '*emphasis*', blank-line paragraphs) (spec B4).

.txt plain UTF-8 · .md maps headings/bold/italic · .docx via stdlib zip+XML (Heading-styled
paragraphs -> sections, bold/italic runs -> emphasis) · .rtf/.doc via macOS textutil (plain
text; headings are not recovered — noted in the screen's label) · .pdf via pypdf (lazy import,
named error when missing). The source file is never written.
"""
import os
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET

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


def _docx_to_markup(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml')
    root = ET.fromstring(xml)
    paras = []
    for p in root.iter(_W + 'p'):
        style_el = p.find(f'{_W}pPr/{_W}pStyle')
        style = style_el.get(_W + 'val') if style_el is not None else ''
        # run text with bold/italic marking: *word* per word (repo emphasis is per word)
        parts = []
        for r in p.findall(_W + 'r'):
            text = ''.join(t.text or '' for t in r.findall(_W + 't'))
            if not text:
                continue
            rpr = r.find(_W + 'rPr')
            bold = rpr is not None and rpr.find(_W + 'b') is not None
            italic = rpr is not None and rpr.find(_W + 'i') is not None
            if bold or italic:
                text = re.sub(r'\S+', lambda m: '*' + m.group(0) + '*', text)
            parts.append(text)
        line = ''.join(parts).strip()
        if not line:
            continue
        if style in _HEADING_STYLES:
            paras.append('# ' + line)
        else:
            paras.append(line)
    return '\n\n'.join(paras) + '\n'


def _textutil(path):
    """macOS textutil plain-text conversion (headings are NOT recovered — noted in the UI)."""
    r = subprocess.run(['textutil', '-convert', 'txt', '-stdout', path],
                       capture_output=True, text=True, timeout=30)
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
