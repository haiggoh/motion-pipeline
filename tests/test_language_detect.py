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


# 16 all-caps German stopwords — if the caps filter is deleted, these add 16 de hits to
# EN's 35 en hits and drop the en share to 35/52 = 0.67 < MIN_SHARE (0.70).
CAPS_DE = '(DER DIE DAS UND) (IST NICHT EIN EINE) (ZU DEN DEM DES) (MIT VON FÜR AUF)'
EN38 = ('the and of to a in is it that for on with as are was be this by at from '
        'or an we you they our their his her its not but have has had will would can')


def test_caps_labels_carrying_stopword_mass_do_not_sway():
    """All-caps cue labels must not vote even when they contain stopwords of the other
    language — the user's file has 13 such labels."""
    assert language_detect.detect(EN + ' ' + CAPS_DE) == 'en'


def test_mixed_case_cue_label_does_not_leak():
    """'(9er-TEILUNG)' is NOT all-upper (lowercase 'er' prefix) — it must still be skipped as
    a cue label, not leak 'er' as a German stopword hit (30 labels = 30 de hits would flip
    EN to None: 35/66 = 0.53 < 0.70)."""
    assert language_detect.detect(EN + ' (9er-TEILUNG)' * 30) == 'en'


def test_caps_labels_do_not_count_toward_min_words():
    """Cue labels are skipped entirely — they must not pad the token count over MIN_WORDS
    either: 38 English tokens + a 4-word caps label stays undecided (38 < 40)."""
    assert language_detect.detect(EN38 + ' (DER DIE DAS UND)') is None


def test_min_words_boundary_39_vs_40():
    w39 = ' '.join(['the', 'and', 'of', 'to', 'a', 'in', 'is'] * 5 + ['the', 'and', 'of', 'to'])
    w40 = ' '.join(['the', 'and', 'of', 'to', 'a', 'in', 'is', 'it'] * 5)
    assert len(w39.split()) == 39 and len(w40.split()) == 40
    assert language_detect.detect(w39) is None
    assert language_detect.detect(w40) == 'en'
