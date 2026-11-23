"""B3 (0.8.0 plan): font_index.scan() rewrote the cache file even when NOTHING changed —
so a test pointing MP_FONT_CACHE at the tracked fixture tests/fixtures/font-index-mini.json
got it overwritten with the real machine index (observed twice, 2026-11-22). scan() now
saves only when the index actually changed. RED pre-fix: the mtime assertion fails."""
import os

from motion_pipeline import font_index


def _font_dir(tmp_path):
    src = os.path.join(os.path.dirname(font_index.__file__), 'fonts')
    hits = []
    for root, _dirs, files in os.walk(src):
        hits += [os.path.join(root, f) for f in files if f.lower().endswith(('.ttf', '.otf'))]
    assert hits, 'no bundled font files found'
    dst = tmp_path / 'fonts'
    dst.mkdir()
    name = os.path.basename(hits[0])
    (dst / name).write_bytes(open(hits[0], 'rb').read())
    return str(dst)


def test_scan_does_not_rewrite_an_unchanged_cache(tmp_path):
    d = _font_dir(tmp_path)
    cache = str(tmp_path / 'cache.json')
    font_index.scan(dirs=[d], cache_path=cache)
    first = open(cache, 'rb').read()
    mtime1 = os.stat(cache).st_mtime_ns
    font_index.scan(dirs=[d], cache_path=cache)      # everything hits the cache now
    assert os.stat(cache).st_mtime_ns == mtime1, 'unchanged tree must not rewrite the cache'
    assert open(cache, 'rb').read() == first
