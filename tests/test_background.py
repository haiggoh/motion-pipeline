"""Task 4 tests: generated background renders smooth in 10-bit-clean mode and bands in the
planted 8-bit-chroma mode (the gate's discriminant), and uses the scheme colours."""
import os
import subprocess

import numpy as np
import pytest

from motion_pipeline.background import generate_background_page
from motion_pipeline.scheme import derive_palette

CHROME = os.path.expanduser('~/.cache/pgcube/chrome/chrome-headless-shell/mac_arm-156.0.8078.4'
                            '/chrome-headless-shell-mac-arm64/chrome-headless-shell')
DARK = {'name': 't', 'background_dark': '#0b1a4c', 'background_light': '#1251a6',
        'accent': '#ffb400', 'text': '#f5f7ff'}
LIGHT = {'name': 't', 'background_dark': '#f4f6fb', 'background_light': '#c9d6f2',
         'accent': '#0b3d91', 'text': '#101828'}
W, H = 1920, 1080
STRIP = (0, 1920, 0, 120)  # full top band, background-only (sample text sits at top 40%)


def render_page_files(palette, banded, tmp_path):
    """Render the generated page via the pinned chrome at full frame size; return (RGB frame, PNG path)."""
    html = generate_background_page(palette, W, H, sample_text='Aa', banded=banded)
    page = tmp_path / ('bg_banded.html' if banded else 'bg_smooth.html')
    png = tmp_path / ('bg_banded.png' if banded else 'bg_smooth.png')
    page.write_text(html)
    r = subprocess.run([CHROME, f'--screenshot={png}', f'--window-size={W},{H}',
                        '--hide-scrollbars', f'file://{page}'],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and png.is_file(), r.stderr[-400:]
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(png), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, timeout=60)
    img = np.frombuffer(raw.stdout, dtype=np.uint8).reshape(H, W, 3)
    return img, png


def cb_strip_max_step_10bit(png_path, strip=STRIP):
    """Encode the capture through the real master path (single BT.709 10-bit 4:2:2 conversion,
    High 4:2:2 10-bit x264) and measure max |neighbour step| of Cb in 10-bit codes over the
    strip — the same measurement the master gate (check_chroma_steps.py) makes."""
    x0, x1, y0, y1 = strip
    w, h = x1 - x0, y1 - y0
    vf = (f'crop={w}:{h}:{x0}:{y0},'
          'scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv422p10le')
    dec = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(png_path), '-vf', vf,
                          '-frames:v', '1', '-f', 'rawvideo', '-'],
                         capture_output=True, timeout=60)
    buf = np.frombuffer(dec.stdout, dtype='<u2')
    assert buf.size >= w * h + (w // 2) * h, f'decode too small: {buf.size}'
    y_plane = w * h
    cb_plane = buf[y_plane:y_plane + (w // 2) * h].reshape(h, w // 2).astype(np.float64)
    cb = cb_plane.mean(axis=0)  # 4:2:2: each sample covers a pixel pair
    return float(np.max(np.abs(np.diff(cb))))


@pytest.fixture(scope='module')
def smooth(tmp_path_factory):
    return render_page_files(derive_palette(DARK), False, tmp_path_factory.mktemp('bg'))


@pytest.fixture(scope='module')
def banded(tmp_path_factory):
    return render_page_files(derive_palette(DARK), True, tmp_path_factory.mktemp('bg2'))


def test_smooth_background_passes_chroma_gate(smooth):
    _, png = smooth
    step = cb_strip_max_step_10bit(png)
    assert step <= 2.0, f'smooth background banded: max 10-bit Cb step {step}'


def test_banded_mode_fails_chroma_gate(banded):
    _, png = banded
    step = cb_strip_max_step_10bit(png)
    assert step > 2.0, f'discriminant did not fire: banded max 10-bit Cb step {step}'


def test_background_uses_scheme_colours(smooth):
    img, _ = smooth
    left = img[2:8, 2:8].reshape(-1, 3).mean(axis=0)
    right = img[2:8, -8:-2].reshape(-1, 3).mean(axis=0)
    dark = np.array([0x0b, 0x1a, 0x4c])
    # the gradient runs from background_dark (left) toward background_light (right):
    # left edge is closer to dark than right edge is, and the luma increases left->right
    assert np.linalg.norm(left - dark) < np.linalg.norm(right - dark), (left, right, dark)
    assert 0.2126 * left[0] + 0.7152 * left[1] + 0.0722 * left[2] < \
           0.2126 * right[0] + 0.7152 * right[1] + 0.0722 * right[2], (left, right)


def test_light_scheme_renders_and_passes(tmp_path):
    img, png = render_page_files(derive_palette(LIGHT), False, tmp_path)
    step = cb_strip_max_step_10bit(png)
    assert step <= 2.0
    left = img[2:8, 2:8].reshape(-1, 3).mean(axis=0)
    right = img[2:8, -8:-2].reshape(-1, 3).mean(axis=0)
    light = np.array([0xf4, 0xf6, 0xfb])
    glow = np.array([0xc9, 0xd6, 0xf2])
    assert np.linalg.norm(left - light) < np.linalg.norm(right - light), (left, right, light)
    assert np.linalg.norm(left - light) < np.linalg.norm(left - glow), (left, light, glow)
