"""Task 10 (plan 2026-11-16): font_preview.render_sample + the fonts-screen preview/sharp actions."""
import os
import subprocess
from types import SimpleNamespace

import pytest
from PIL import Image
from textual.widgets import Checkbox, Input, Select, Static

from motion_pipeline import font_index, project
from motion_pipeline.font_index import BUNDLED_DIR
from motion_pipeline.font_preview import SAMPLE_TEXT, render_sample
from motion_pipeline.tui.app import MenuApp
from motion_pipeline.tui.fonts_screen import FontsScreen
from tui_probe import choose

_REAL_SCAN = font_index.scan
MONT_BOLD = os.path.join(BUNDLED_DIR, 'Montserrat', 'Montserrat-Bold.ttf')
MONT_SEMI = os.path.join(BUNDLED_DIR, 'Montserrat', 'Montserrat-SemiBold.ttf')
INTER_REG = os.path.join(BUNDLED_DIR, 'Inter', 'Inter-Regular.otf')


def fake_scan(tmp_path, monkeypatch):
    def fake(dirs=None, cache_path=None, progress=None):
        return _REAL_SCAN(dirs=[BUNDLED_DIR], cache_path=str(tmp_path / 'font-cache.json'))
    monkeypatch.setattr(font_index, 'scan', fake)


async def wait_scan(pilot, scr, timeout=10.0):
    for _ in range(int(timeout / 0.05)):
        await pilot.pause(0.05)
        if scr._all:
            return
    raise AssertionError('font scan never finished')


def test_render_sample_uses_each_face():
    two = render_sample([('Ag', MONT_BOLD, 0, 20), ('Ag', INTER_REG, 0, 20)], 200, '#ffffff', '#000000')
    same = render_sample([('Ag', MONT_BOLD, 0, 20), ('Ag', MONT_BOLD, 0, 20)], 200, '#ffffff', '#000000')
    h = 25  # px*1.25 line height
    crop_a, crop_b = two.crop((0, 0, 200, h)), two.crop((0, h, 200, 2 * h))
    assert crop_a.tobytes() != crop_b.tobytes(), 'two different faces must render differently'
    s1, s2 = same.crop((0, 0, 200, h)), same.crop((0, h, 200, 2 * h))
    assert s1.tobytes() == s2.tobytes(), 'same face twice must render identically'


def test_sample_text_constant():
    assert SAMPLE_TEXT == 'Kinetische Typografie — Äpfel über Größe · Quick brown fox 0123'


@pytest.mark.asyncio
async def test_preview_updates_on_weight_change(tmp_path, monkeypatch):
    fake_scan(tmp_path, monkeypatch)
    project.save(str(tmp_path), project.default_project('demo'))
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        scr = app.screen
        await wait_scan(pilot, scr)
        scr.query_one('#all-roles', Checkbox).value = False   # B2: untick -> headline is the target
        seq = next(s for f, s in scr._shown if f == 'Montserrat')
        scr.on_list_view_selected(SimpleNamespace(item=SimpleNamespace(id=f'font-{seq}')))
        await pilot.pause(0.5)  # debounce 150 ms
        w = scr.query_one('#font-preview', Static)
        before = (str(w.render()), [(s.start, s.end, str(s.style)) for s in w.render().spans])
        assert before[0].strip() != '', 'preview rendered'
        scr.query_one('#role-headline-weight', Select).value = 600
        await pilot.pause(0.5)
        after = (str(w.render()), [(s.start, s.end, str(s.style)) for s in w.render().spans])
        assert after != before, 'preview must change with the weight'


@pytest.mark.asyncio
async def test_sharp_preview_opens_quicklook(tmp_path, monkeypatch):
    fake_scan(tmp_path, monkeypatch)
    project.save(str(tmp_path), project.default_project('demo'))
    opened = []
    real_popen = subprocess.Popen

    def fake_popen(*a, **k):
        if a and a[0] and a[0][0] == 'qlmanage':
            opened.append(a[0])
            return real_popen(['true'])
        return real_popen(*a, **k)

    monkeypatch.setattr('subprocess.Popen', fake_popen)
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(FontsScreen())
        await pilot.pause()
        scr = app.screen
        await wait_scan(pilot, scr)
        scr.query_one('#all-roles', Checkbox).value = True    # B2: all roles (default)
        seq = next(s for f, s in scr._shown if f == 'Montserrat')
        scr.on_list_view_selected(SimpleNamespace(item=SimpleNamespace(id=f'font-{seq}')))
        await pilot.pause(0.5)
        await choose(pilot, scr, 'sharp')
        await pilot.pause(0.5)
        assert opened and opened[0][0] == 'qlmanage' and opened[0][1] == '-p', opened
        png = opened[0][2]
        assert os.path.isfile(png), png
        sharp_w = Image.open(png).width
        inline = os.path.join(os.environ.get('TMPDIR', '/tmp'),
                              f'motion-pipeline-preview-inline-{os.getpid()}.png')
        assert os.path.isfile(inline)
        inline_w = Image.open(inline).width
        assert sharp_w >= 2 * inline_w, (sharp_w, inline_w)


# ---- Task 13 (spec B2): bigger inline preview + live sharp window ----

# 0.6.x preview area at 120x40, measured on main: max_w=44/max_h=12 -> region 45x12
OLD_PREVIEW_AREA_120x40 = 45 * 12


async def _open_fonts_picked(pilot, app, tmp_path):
    """Open the fonts screen, wait for the scan, pick Montserrat for all roles."""
    app.push_screen(FontsScreen())
    await pilot.pause()
    scr = app.screen
    await wait_scan(pilot, scr)
    seq = next(s for f, s in scr._shown if f == 'Montserrat')
    scr.on_list_view_selected(SimpleNamespace(item=SimpleNamespace(id=f'font-{seq}')))
    for _ in range(30):
        await pilot.pause(0.1)
    return scr


@pytest.mark.asyncio
async def test_inline_preview_at_least_2x_the_063_area(tmp_path, monkeypatch):
    fake_scan(tmp_path, monkeypatch)
    project.save(str(tmp_path), project.default_project('demo'))
    app = MenuApp()
    app.project_dir = str(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        scr = await _open_fonts_picked(pilot, app, tmp_path)
        pv = scr.query_one('#font-preview', Static)
        area = pv.region.width * pv.region.height
        assert area >= 2 * OLD_PREVIEW_AREA_120x40, (area, OLD_PREVIEW_AREA_120x40)


@pytest.mark.asyncio
async def test_sharp_window_rewrites_png_live_on_sample_change(tmp_path, monkeypatch):
    """Once the sharp window is open, every preview update rewrites the SAME png (mtime
    advances, pixels differ) without spawning another viewer process."""
    fake_scan(tmp_path, monkeypatch)
    project.save(str(tmp_path), project.default_project('demo'))
    app = MenuApp()
    app.project_dir = str(tmp_path)
    opened = []
    real_popen = subprocess.Popen

    def fake_popen(*a, **k):
        if a and a[0] and a[0][0] == 'qlmanage':
            opened.append(a[0])
            return real_popen(['true'])
        return real_popen(*a, **k)

    monkeypatch.setattr('subprocess.Popen', fake_popen)
    async with app.run_test(size=(120, 40)) as pilot:
        scr = await _open_fonts_picked(pilot, app, tmp_path)
        await choose(pilot, scr, 'sharp')
        await pilot.pause(0.5)
        assert len(opened) == 1, opened
        png = opened[0][2]
        before_mtime = os.path.getmtime(png)
        before_px = Image.open(png).convert('RGB').tobytes()
        scr.query_one('#sample-text', Input).value = 'Completely different sample text 9876'
        for _ in range(30):
            await pilot.pause(0.1)
        after_mtime = os.path.getmtime(png)
        after_px = Image.open(png).convert('RGB').tobytes()
        assert after_mtime > before_mtime, (before_mtime, after_mtime)
        assert after_px != before_px, 'sharp png pixels did not change with the sample text'
        assert len(opened) == 1, 'a second viewer process was spawned'
