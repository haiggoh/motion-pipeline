"""0.8.3 Task 3: a cache written by the 0.8.2 parser holds wrong TTC weights under the RIGHT
mtime/size key (system fonts never change), so the fix would never reach an existing user.
Entries carry the parser version; older/unversioned entries are rescanned."""
import json
import os

from ttc_fixture import BOLD, REGULAR, build_ttc

from motion_pipeline import font_index


def _plant_082_cache(cache, ttc):
    st = os.stat(ttc)
    stale = [{'family': 'Montserrat', 'style': s, 'weight': 400, 'italic': False, 'path': ttc,
              'index': i, 'bundled': False} for i, s in enumerate(('Regular', 'Bold'))]
    with open(cache, 'w') as f:                       # exactly what 0.8.2 stored: no parser key
        json.dump({ttc: {'mtime_ns': st.st_mtime_ns, 'size': st.st_size, 'faces': stale}}, f)


def test_unversioned_cache_entry_is_rescanned(tmp_path):
    d = tmp_path / 'f'
    ttc = build_ttc(str(d / 'Duo.ttc'), [REGULAR, BOLD])
    cache = str(tmp_path / 'font-index.json')
    _plant_082_cache(cache, ttc)
    faces = font_index.scan(dirs=[str(d)], cache_path=cache)
    assert {f['style']: f['weight'] for f in faces} == {'Regular': 400, 'Bold': 700}
    saved = json.load(open(cache))
    assert saved[ttc]['parser'] == font_index.PARSER_VERSION


def test_current_cache_entry_is_reused(tmp_path):
    """The version check must not defeat the cache: a current entry is trusted as stored."""
    d = tmp_path / 'f'
    ttc = build_ttc(str(d / 'Duo.ttc'), [REGULAR, BOLD])
    cache = str(tmp_path / 'font-index.json')
    font_index.scan(dirs=[str(d)], cache_path=cache)
    data = json.load(open(cache))
    data[ttc]['faces'][1]['style'] = 'Marker'          # proves the entry is read, not rescanned
    with open(cache, 'w') as f:
        json.dump(data, f)
    faces = font_index.scan(dirs=[str(d)], cache_path=cache)
    assert 'Marker' in {f['style'] for f in faces}
