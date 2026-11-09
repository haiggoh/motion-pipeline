"""transcript.py — plain-text transcript with sections and key-word markup (Task 6).

Markup (decide-question 1, user-approved default): `# Section name` lines start a section,
blank lines separate paragraphs, `*word*` marks emphasis (key words). Output model (pinned):
  {"sections": [{"name": str, "char_start": int}],
   "words": [{"id": "w<index>", "text": str, "section": str, "emphasized": bool}]}
Word ids are index-based and stable across re-parse as long as the word sequence is unchanged
(a section rename never moves them). serialize() reproduces the exact markup (round-trip).
Malformed markup (`*unclosed`, `*` alone) raises naming the line number — never silently dropped.
"""
import re

SECTION_RE = re.compile(r'^#\s+(.+?)\s*$')
WORD_RE = re.compile(r'\*([^*\n]+)\*|([^\s*]+)')


def parse(text):
    if not text.strip():
        raise ValueError('transcript is empty')
    sections = []
    words = []
    section = 'default'
    pos = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        m = SECTION_RE.match(line)
        if m:
            section = m.group(1)
            sections.append({'name': section, 'char_start': pos, 'line': lineno})
            pos += len(line) + 1
            continue
        for wm in WORD_RE.finditer(line):
            if wm.group(1) is not None:
                words.append({'id': f'w{len(words)}', 'text': wm.group(1),
                              'section': section, 'emphasized': True, 'line': lineno})
            else:
                words.append({'id': f'w{len(words)}', 'text': wm.group(2),
                              'section': section, 'emphasized': False, 'line': lineno})
        pos += len(line) + 1
    # malformed markup check: any leftover '*' that is not part of a *word* pair
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = SECTION_RE.sub('', line)
        if '*' in WORD_RE.sub('', stripped):
            raise ValueError(f'malformed emphasis markup on line {lineno}: {line!r}')
    if not sections:
        sections.append({'name': 'default', 'char_start': 0})
    if not words:
        raise ValueError('transcript has no words')
    return {'sections': sections, 'words': words}


def serialize(model):
    """Reproduce the markup byte-equal: `# name` section headers, original line breaks kept
    (each word carries its source line), `*...*` around emphasized words."""
    out = []
    cur_section = None
    cur_line = None
    sec_lines = {s['name']: s.get('line', 0) for s in model['sections']}
    for w in model['words']:
        if w['section'] != cur_section:
            cur_section = w['section']
            sec_line = sec_lines.get(cur_section, 0)
            if cur_line is not None:
                for _ in range(max(sec_line - cur_line - 1, 0)):
                    out.append('')
            out.append(f'# {cur_section}')
            cur_line = sec_line
        gap = w.get('line', 0) - cur_line
        for _ in range(max(gap, 0)):
            out.append('')
        cur_line = w.get('line', 0)
        text = f"*{w['text']}*" if w['emphasized'] else w['text']
        if out[-1] == '':
            out[-1] = text
        else:
            out[-1] = out[-1] + ' ' + text
    return '\n'.join(out) + '\n'


def load(path):
    with open(path) as f:
        return parse(f.read())


def save(path, model):
    with open(path, 'w') as f:
        f.write(serialize(model))


def rename_section(model, old, new):
    """Rename a section in the model (ids and words untouched)."""
    for s in model['sections']:
        if s['name'] == old:
            s['name'] = new
    for w in model['words']:
        if w['section'] == old:
            w['section'] = new
    return model
