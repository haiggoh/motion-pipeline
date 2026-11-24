"""font_index.py — every installed font face with its REAL weight, cached, scanned in the
background (Task 7).

Weight truth is the OS/2 `usWeightClass`, read by a minimal sfnt reader (PIL's getname() gives
the style LABEL, not the weight). The scan is recursive: v0.5.x only looked at the top level of
each font folder, so /Library/Fonts/P7S1_Hausschriften_2024_2/SevenOneHighlightTT-*.ttf and all
of /System/Library/Fonts/Supplemental were invisible (E3).

Cache: MP_FONT_CACHE (or ~/.cache/motion-pipeline/font-index.json), keyed by
(path, mtime_ns, size) — an unchanged tree is served without opening a single font.
"""
import json
import os
import struct
from collections.abc import Callable
from typing import TypedDict

from PIL import ImageFont

FONT_EXTS = {'.ttf', '.otf', '.ttc', '.otc'}
CSS_WEIGHT_NAMES = {100: 'Thin', 200: 'ExtraLight', 300: 'Light', 400: 'Regular', 500: 'Medium',
                    600: 'SemiBold', 700: 'Bold', 800: 'ExtraBold', 900: 'Black'}
BUNDLED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
ASSETS_DIR = '/System/Library/AssetsV2'
CORE_SYNC_MARKER = 'Adobe/CoreSync'  # obfuscated names, licence forbids copying (P7)


class Face(TypedDict):
    family: str
    style: str
    weight: int
    italic: bool
    path: str
    index: int
    bundled: bool


def default_dirs() -> list[str]:
    dirs = ['/Library/Fonts', os.path.expanduser('~/Library/Fonts'), '/System/Library/Fonts']
    if os.path.isdir(ASSETS_DIR):
        dirs += [os.path.join(ASSETS_DIR, d) for d in sorted(os.listdir(ASSETS_DIR))
                 if d.startswith('com_apple_MobileAsset_Font')]
    dirs.append(BUNDLED_DIR)
    env = os.environ.get('MP_FONT_DIRS')
    if env:
        extra = [d.strip() for d in env.split(':') if d.strip()]
        for d in extra:
            if not os.path.isdir(d):
                raise ValueError(f'MP_FONT_DIRS lists a directory that does not exist: {d}')
        dirs += extra
    return dirs


def cache_file() -> str:
    env = os.environ.get('MP_FONT_CACHE')
    if env:
        return env
    return os.path.join(os.path.expanduser('~'), '.cache', 'motion-pipeline', 'font-index.json')


# Bump whenever _scan_file's output changes for the SAME file: cache entries from another parser
# version are rescanned (0.8.3: the 0.8.2 parser cached wrong TTC weights under a valid key).
PARSER_VERSION = 2


def read_os2_weight(path: str, index: int = 0) -> int | None:
    """OS/2 usWeightClass: TTC header ('ttcf') -> face offset, then offset table -> table
    directory -> 'OS/2' -> uint16 at byte 4 of the table. None when the file has no OS/2.
    The table directory sits 12 bytes after the FACE's offset table (off), not the file start —
    0.8.2 seeked to byte 12 of the file, and read face i's offset from byte 8+4i (numFonts for
    face 0, face i-1's offset otherwise), so TTC faces read None/the wrong face (0.8.3 bug 1)."""
    try:
        with open(path, 'rb') as f:
            off = 0
            tag = f.read(4)
            if tag == b'ttcf':
                f.seek(12 + index * 4)        # ttcf, version, numFonts, THEN the offset array
                off = struct.unpack('>I', f.read(4))[0]
                f.seek(off)
                tag = f.read(4)
            if tag not in (b'\x00\x01\x00\x00', b'OTTO', b'true', b'typ1'):
                return None
            num_tables = struct.unpack('>H', f.read(2))[0]
            f.seek(off + 12)
            for _ in range(num_tables):
                ttag = f.read(4)
                f.read(4)                                     # checksum
                toff = struct.unpack('>I', f.read(4))[0]
                f.read(4)                                     # length
                if ttag == b'OS/2':
                    f.seek(toff + 4)
                    return struct.unpack('>H', f.read(2))[0]
        return None
    except (OSError, struct.error):
        return None


# style-name words -> CSS weight, checked longest-first so 'semibold' wins over 'bold'
_STYLE_WEIGHTS = (('hairline', 100), ('ultralight', 200), ('extralight', 200), ('thin', 100),
                  ('semibold', 600), ('demibold', 600), ('extrabold', 800), ('ultrabold', 800),
                  ('black', 900), ('heavy', 900), ('light', 300), ('medium', 500),
                  ('bold', 700), ('book', 400), ('regular', 400))


def weight_from_style(style: str | None) -> int:
    """Weight inferred from a style name when the face has no OS/2 table (0.8.3: no silent 400
    for a face called 'Bold')."""
    low = (style or '').lower().replace(' ', '').replace('-', '')
    for word, w in _STYLE_WEIGHTS:
        if word in low:
            return w
    return 400


def _face_count(path: str) -> int:
    """Faces in a font file: TTC numFonts (uint32 at byte 8), else 1."""
    try:
        with open(path, 'rb') as f:
            if f.read(4) == b'ttcf':
                f.seek(8)
                n = struct.unpack('>I', f.read(4))[0]
                return int(n) or 1
    except (OSError, struct.error):
        pass
    return 1


def _scan_file(path: str, bundled: bool) -> list[Face]:
    faces: list[Face] = []
    for index in range(_face_count(path)):
        try:
            font = ImageFont.truetype(path, 10, index=index)
            family, style = font.getname()
        except (OSError, ValueError):
            if index == 0 and not path.endswith(('.ttf', '.otf', '.ttc', '.otc')):
                return []                                     # e.g. an unreadable .dfont
            continue
        weight = read_os2_weight(path, index) or weight_from_style(style)
        low = (style or '').lower()
        faces.append(Face(family=family or '', style=style or '', weight=weight,
                          italic=('italic' in low or 'oblique' in low), path=path,
                          index=index, bundled=bundled))
    return faces


def _walk_files(dirs: list[str]):
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for root, subdirs, files in os.walk(d):
            if CORE_SYNC_MARKER in root:
                subdirs[:] = []
                continue
            subdirs[:] = [s for s in subdirs if not s.startswith('.')]
            for name in sorted(files):
                ext = os.path.splitext(name)[1].lower()
                if ext in FONT_EXTS or ext == '.dfont':
                    yield os.path.join(root, name), os.path.realpath(root).startswith(os.path.realpath(BUNDLED_DIR))


def _load_cache(path: str) -> dict:
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(path: str, data: dict) -> None:
    d = os.path.dirname(path)
    try:
        os.makedirs(d, exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except OSError as e:
        raise ValueError(f'font cache is not writable: {path} ({e})') from None


def scan(dirs: list[str] | None = None, cache_path: str | None = None,
         progress: Callable[[int, int], None] | None = None) -> list[Face]:
    """Every face under `dirs` (default: every system font dir + the bundled faces + MP_FONT_DIRS)."""
    dirs = dirs if dirs is not None else default_dirs()
    cache_path = cache_path or cache_file()
    cache = _load_cache(cache_path)
    fresh: dict = {}
    out: list[Face] = []
    files = list(_walk_files(dirs))
    total = len(files)
    for i, (path, bundled) in enumerate(files, 1):
        try:
            st = os.stat(path)
        except OSError:
            continue
        key = (st.st_mtime_ns, st.st_size)
        entry = cache.get(path)
        if (isinstance(entry, dict) and entry.get('mtime_ns') == key[0] and entry.get('size') == key[1]
                and entry.get('parser') == PARSER_VERSION):
            faces = [Face(**f) for f in entry['faces']]
        else:
            faces = _scan_file(path, bundled)
        fresh[path] = {'mtime_ns': key[0], 'size': key[1], 'parser': PARSER_VERSION,
                       'faces': [dict(f) for f in faces]}
        out.extend(faces)
        if progress is not None:
            progress(i, total)
    if fresh != cache:                 # B3: an unchanged tree must not rewrite the cache file
        _save_cache(cache_path, fresh)
    return out


def families(faces: list[Face], include_hidden: bool = False) -> dict[str, list[Face]]:
    """family -> faces sorted by weight, upright before italic. Apple-private families
    (name starts with '.', e.g. '.SF NS') are dropped unless include_hidden — the cache
    keeps them, the menu hides them like Font Book does (spec A6)."""
    out: dict[str, list[Face]] = {}
    for f in faces:
        if not include_hidden and f['family'].startswith('.'):
            continue
        out.setdefault(f['family'], []).append(f)
    for flist in out.values():
        flist.sort(key=lambda f: (f['weight'], f['italic']))
    return out


def weight_label(face: Face) -> str:
    """'SemiBold (600)'; an empty style falls back to the CSS weight-name table."""
    weight = face.get('weight', 400)
    name = face.get('style') or CSS_WEIGHT_NAMES.get(weight, str(weight))
    return f'{name} ({weight})'
