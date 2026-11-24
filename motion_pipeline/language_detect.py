"""language_detect.py — is a transcript German or English? (0.8.3, user decision D-LANG)

A saved 'de' written by an old default looks exactly like a deliberate choice, so the transcript
text decides: detect() votes with high-frequency function words (stopwords) and only answers when
the evidence is clear. Deterministic, offline, no dependency. Returns 'de', 'en' or None
(too short, or no clear winner) — None never overrides anything.
"""
import re


def _words(s: str) -> set[str]:
    return set(s.split())


_STOP = {
    'en': _words('the and of to a in is it that for on with as are was be this by at from or an '
              'we you they our their his her its not but have has had will would can could which '
              'who what when where why how all there these those than then so if into out up '
              'about more most every each them us one also just'),
    'de': _words('der die das und ist nicht ein eine einer eines zu den dem des mit von für auf im '
              'in sich auch es wir ihr sie er wird werden sind war wie aus bei nach oder aber '
              'noch nur so dass zum zur über unter durch vor kann können unsere unser alle '
              'diese dieser dieses wenn weil deshalb immer jeden wieder'),
}
_WORD = re.compile(r"[a-zäöüß']+")
MIN_WORDS = 40          # below this there is not enough function-word evidence
MIN_SHARE = 0.70        # the winner must own this share of all stopword hits


def detect(text: str) -> str | None:
    """'de' | 'en' | None. Words in ALL CAPS are skipped (cue labels like '(9er-TEILUNG)')."""
    words = [w.lower() for w in re.findall(r"[^\W\d_][\w'-]*", text or '') if not w.isupper()]
    tokens = [t for w in words for t in _WORD.findall(w)]
    if len(tokens) < MIN_WORDS:
        return None
    hits = {lang: sum(1 for t in tokens if t in stop) for lang, stop in _STOP.items()}
    total = sum(hits.values())
    if not total:
        return None
    lang, best = max(hits.items(), key=lambda kv: kv[1])
    return lang if best / total >= MIN_SHARE else None
