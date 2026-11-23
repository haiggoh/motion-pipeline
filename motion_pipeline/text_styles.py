"""text_styles.py — the L0 base text styles (0.8.0 Task 4 / user decision Q1).

STYLES maps name -> TextStyle. `slide-up` is the 0.7.x default and stays byte-identical in
generated pages (Task 5 golden test). generate.py (Task 5) renders STYLES[p.get('text_style',
DEFAULT)] — emitting style.css, spans at style.granularity, layout from style.layout and the
tween loop from style.tween_js — and tools/check_zone.py reads the same style.layout so the
zone gate sees the style's real geometry. Adding a style = one table row: the menu lists
STYLES directly (pinned by a monkeypatched-row test).

Determinism: tween JS may use MP.random ONLY with a fixed per-style seed (Task 5 test:
two generations identical, different seed differs).
"""
from dataclasses import dataclass
from typing import Callable, Literal

DEFAULT = 'slide-up'


@dataclass
class TextStyle:
    label: str
    granularity: Literal['word', 'letter']   # span granularity in generated pages
    css: str                                  # extra CSS for the style's hidden initial state
    layout: Callable                          # (words, max_chars_per_line, font_px) -> lines [(w, piece, k)]
    tween_js: Callable                        # () -> the page's word-tween loop JS


def _default_layout(words, max_chars, font_px):
    from motion_pipeline.generate import layout_lines  # lazy: generate imports this module
    return layout_lines(words, max_chars, font_px)


def _one_word_per_line(words, *_args):
    return [[(w, w['text'], 0)] for w in words]


SLIDE_UP = TextStyle(
    label='Slide up (default)',
    granularity='word',
    css='.line span{display:inline-block;transform:translateY(110%);opacity:0}',
    layout=_default_layout,
    tween_js=lambda: (
        "for (const el of document.querySelectorAll('.line span')) {\n"
        "  const t = T[el.dataset.id];\n"
        "  tl.to(el, {duration: 0.35, y: '0%', opacity: 1, delay: t.start, ease: 'power3.out'});\n"
        "}"
    ),
)

SENTENCE_PER_SCREEN = TextStyle(
    label='Sentence per screen',
    granularity='word',
    css='.line{transform:translateY(110%);opacity:0}',
    layout=_default_layout,
    tween_js=lambda: (
        "for (const ln of document.querySelectorAll('.line')) {\n"
        "  const t = T[ln.querySelector('span').dataset.id];\n"
        "  tl.to(ln, {duration: 0.5, y: '0%', opacity: 1, delay: t.start, ease: 'power3.out'});\n"
        "}"
    ),
)

WORDS_APPEAR = TextStyle(
    label='Words appear',
    granularity='word',
    css='.line span{display:inline-block;opacity:0}',
    layout=_default_layout,
    tween_js=lambda: (
        "for (const el of document.querySelectorAll('.line span')) {\n"
        "  const t = T[el.dataset.id];\n"
        "  tl.to(el, {duration: 0.25, opacity: 1, delay: t.start});\n"
        "}"
    ),
)

ONE_WORD_CENTER = TextStyle(
    label='One word at a time, centred',
    granularity='word',
    css='.line span{display:inline-block;transform:scale(0.8);opacity:0}',
    layout=_one_word_per_line,
    tween_js=lambda: (
        "for (const el of document.querySelectorAll('.line span')) {\n"
        "  const t = T[el.dataset.id];\n"
        "  tl.to(el, {duration: 0.4, scale: 1, opacity: 1, delay: t.start, ease: 'back.out(1.6)'});\n"
        "}"
    ),
)

TYPEWRITER = TextStyle(
    label='Typewriter',
    granularity='letter',
    css='.line span{display:inline-block;opacity:0}',
    layout=_default_layout,
    tween_js=lambda: (
        "const rnd = MP.random(0x7e57);  // fixed per-style seed: deterministic across renders\n"
        "for (const el of document.querySelectorAll('.line span')) {\n"
        "  const t = T[el.dataset.id];\n"
        "  const k = el.dataset.k ? +el.dataset.k : 0;\n"
        "  tl.to(el, {duration: 0.03, opacity: 1, delay: t.start + k * 0.04 + rnd() * 0.02});\n"
        "}"
    ),
)

STYLES = {
    'slide-up': SLIDE_UP,
    'sentence-per-screen': SENTENCE_PER_SCREEN,
    'words-appear': WORDS_APPEAR,
    'one-word-center': ONE_WORD_CENTER,
    'typewriter': TYPEWRITER,
}
