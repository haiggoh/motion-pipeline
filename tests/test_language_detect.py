"""0.8.3 bug 3 (user, 2026-11-24): 'language still wrongly shows Deutsch by default rather than
auto-detect. the transcript I loaded is in English.' The project file held a saved 'de' (an old
default looks exactly like a deliberate choice), so the transcript itself decides (D-LANG)."""
from motion_pipeline import language_detect

EN = ('We bring together the strongest teams and the clearest ideas for brands that want to grow. '
      'Our work starts with the people who buy and use the products every day, and it ends with '
      'measurable results that everyone in the business can see and trust. This is how we think, '
      'create and operate, and it is the reason why our partners keep coming back to us.')
DE = ('Wir bringen die stärksten Teams und die klarsten Ideen für Marken zusammen, die wachsen '
      'wollen. Unsere Arbeit beginnt mit den Menschen, die die Produkte jeden Tag kaufen und nutzen, '
      'und sie endet mit messbaren Ergebnissen, die alle im Unternehmen sehen und denen sie vertrauen '
      'können. So denken, gestalten und arbeiten wir, und deshalb kommen unsere Partner immer wieder.')


def test_english_text_is_english():
    assert language_detect.detect(EN) == 'en'


def test_german_text_is_german():
    assert language_detect.detect(DE) == 'de'


def test_short_text_is_undecided():
    assert language_detect.detect('Hello there, this is short.') is None


def test_english_with_caps_german_labels_stays_english():
    """The user's file: English prose with all-caps cue labels such as '(9er-TEILUNG)'."""
    text = '(9er-TEILUNG) (THINK_CREATE_OPERATE) ' + EN + ' (CONSUMER INTELLIGENCE) (DIGITALE WELT)'
    assert language_detect.detect(text) == 'en'


def test_mixed_half_and_half_is_undecided():
    half = ' '.join(EN.split()[:30]) + ' ' + ' '.join(DE.split()[:30])
    assert language_detect.detect(half) is None
