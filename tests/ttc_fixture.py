"""Test helper (not a test module): build real font collections in a temp dir from the bundled
OFL fonts, so TTC handling is exercised portably — no /System/Library paths (0.8.3)."""
import os

from fontTools.ttLib import TTCollection, TTFont

import motion_pipeline

FONTS = os.path.join(os.path.dirname(motion_pipeline.__file__), 'fonts')
REGULAR = os.path.join(FONTS, 'Montserrat', 'Montserrat-Regular.ttf')
SEMIBOLD = os.path.join(FONTS, 'Montserrat', 'Montserrat-SemiBold.ttf')
BOLD = os.path.join(FONTS, 'Montserrat', 'Montserrat-Bold.ttf')


def build_ttc(out_path, sources, weights=None, styles=None, strip_os2=()):
    """Write a .ttc holding one face per source file. weights[i]/styles[i] override the face's
    OS/2 usWeightClass / name-table subfamily; strip_os2 = indices whose OS/2 table is dropped.
    Returns out_path."""
    coll = TTCollection()
    for i, src in enumerate(sources):
        f = TTFont(src)
        if weights and weights[i] is not None:
            f['OS/2'].usWeightClass = weights[i]
        if styles and styles[i] is not None:
            for rec in f['name'].names:
                if rec.nameID in (2, 17):
                    rec.string = styles[i]
        if i in strip_os2:
            del f['OS/2']
        coll.fonts.append(f)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    coll.save(out_path)
    return out_path


def os2_weights(path):
    """The instrument: weights per face as fontTools reads them (independent of our parser)."""
    coll = TTCollection(path)
    return [f['OS/2'].usWeightClass if 'OS/2' in f else None for f in coll.fonts]
