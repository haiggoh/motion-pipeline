"""sample_text.py — the built-in background-test transcript (spec A4).

A background test render is about the LOOK (scheme, fonts, zones, frame), never the words:
when the project has no readable transcript, the test render uses this one-section sample
with estimated timings. Language-neutral lines so it fits any project's language setting.
"""
SAMPLE_SECTION = 'Sample'
SAMPLE_HEADLINE = 'Headline sample'
SAMPLE_BODY = 'Body text sample 0123'
SAMPLE_TRANSCRIPT = f'# {SAMPLE_SECTION}\n{SAMPLE_HEADLINE}\n{SAMPLE_BODY}\n'


def sample_markup(section: str | None = None) -> str:
    """The sample as transcript markup, optionally under a different section name (a
    background test names its section after the first keep-out zone of the current aspect)."""
    name = section or SAMPLE_SECTION
    return f'# {name}\n{SAMPLE_HEADLINE}\n{SAMPLE_BODY}\n'
