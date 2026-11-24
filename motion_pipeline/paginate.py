"""paginate.py — split a chapter that cannot fit one frame into pages (0.8.3, D1'/D2/D3/D4).

ONE function, plan_pages(), is shared by generate and tools/check_zone.py (D4) so the zone
gate lays out exactly the pages the renderer emits.

D2 byte-identity: a chapter that fits one frame — even shrunk by the legacy fit loop — is
ONE page with the chapter's own name and no new scenes.json fields. Pagination only kicks in
where the legacy loop would raise. D3: pages pack whole sentences greedily; a single sentence
that does not fit at the base font splits at clause punctuation (, ; : — –) nearest the
middle, else at the word boundary nearest the middle. Paginated pages are packed to fit at
the BASE font size (no shrink) and are named '<chapter> 1..N'.
"""
SENT_END = ('.', '!', '?')
CLAUSE_PUNCT = (',', ';', ':', '—', '–')


def _fits(words, style, W, H, f_px, zones):
    from . import generate  # lazy: generate imports this module
    lines = style.layout(words, max(8, int(W * 0.84 / (f_px * 0.52))), f_px)
    lh = int(f_px * 1.25)
    return generate._avoids_zones(lines, W, H, f_px, lh, zones)


def _sentence_chunks(words):
    """Group words into sentence chunks; a chunk also breaks at a paragraph gap (line jump
    of 2+). Deterministic."""
    chunks, cur = [], []
    prev_line = None
    for w in words:
        line = w.get('line', 0)
        if cur and prev_line is not None and line - prev_line >= 2:
            chunks.append(cur)
            cur = []
        cur.append(w)
        prev_line = line
        if w['text'][-1:] in SENT_END:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def _split_point(words, style, W, H, f_px, zones):
    """D3: the preferred split index k (1..n-1) for an oversized chunk — a clause-punctuation
    boundary nearest the middle first, then the word boundary nearest the middle — that leaves
    a fitting prefix. None when not even one word fits."""
    n = len(words)
    mid = n // 2
    clause = {i + 1 for i, w in enumerate(words[:-1]) if w['text'][-1:] in CLAUSE_PUNCT}
    cand = sorted(clause, key=lambda k: (abs(k - mid), k)) + \
        sorted((k for k in range(1, n) if k not in clause), key=lambda k: (abs(k - mid), k))
    for k in cand:
        if _fits(words[:k], style, W, H, f_px, zones):
            return k
    return None


def _paginate_chapter(chapter, words, style, W, H, font_px, zones, aspect):
    """Split an unfittable chapter into pages that each fit at the BASE font. Raises the same
    ValueError the legacy fit loop raised when even a single word cannot be placed."""
    pages, cur = [], []
    for ch in _sentence_chunks(words):
        if cur and _fits(cur + ch, style, W, H, font_px, zones):
            cur += ch
            continue
        if cur:
            pages.append(cur)
        cur = list(ch)
        while not _fits(cur, style, W, H, font_px, zones):
            k = _split_point(cur, style, W, H, font_px, zones)
            if k is None:
                raise ValueError(f'section "{chapter}" does not fit one frame at {aspect} — '
                                 'split it with a # heading or move the zone')
            pages.append(cur[:k])
            cur = cur[k:]
    if cur:
        pages.append(cur)
    return pages


def plan_pages(chapter, words, style, W, H, font_px, zones, aspect, taken):
    """Plan the pages of one chapter. Returns [{'chapter', 'name', 'slug', 'words', 'font_px',
    'paginated'}] in render order; names/slugs come from the shared `taken` set. A chapter
    that fits (shrunk or not) is one page named exactly `chapter` (D2 byte-identity)."""
    from .generate import section_slug
    if not words:
        return []
    # legacy fit loop first — byte-identical single page when it succeeds (D2)
    f = font_px
    while True:
        if _fits(words, style, W, H, f, zones):
            slug = section_slug(chapter, taken)
            taken.add(slug)
            return [{'chapter': chapter, 'name': chapter, 'slug': slug, 'words': list(words),
                     'font_px': f, 'paginated': False}]
        if f <= max(1, font_px // 2):
            break
        f = max(1, int(f * 0.9))
    # would raise -> paginate at the base font (D2/D3)
    chunks = _paginate_chapter(chapter, words, style, W, H, font_px, zones, aspect)
    pages = []
    for i, ws in enumerate(chunks):
        name = f'{chapter} {i + 1}'
        slug = section_slug(name, taken)
        taken.add(slug)
        pages.append({'chapter': chapter, 'name': name, 'slug': slug, 'words': ws,
                      'font_px': font_px, 'paginated': True})
    return pages
