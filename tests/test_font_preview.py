"""font_preview.render_sample + the fonts-screen SHARP (Quick Look) action. The INLINE
preview was removed in 0.8.1 (user feedback) — those tests are gone with the widget."""
import os
import subprocess

import pytest
from PIL import Image
from tui_probe import choose

from motion_pipeline import font_index, project
from motion_pipeline.font_index import BUNDLED_DIR
from motion_pipeline.font_preview import SAMPLE_TEXT, render_sample
from motion_pipeline.tui.app import MenuApp
from motion_pipeline.tui.fonts_screen import CheckRow, FontsScreen

_REAL_SCAN = font_index.scan
MONT_BOLD = os.path.join(BUNDLED_DIR, 'Montserrat', 'Montserrat-Bold.ttf')
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
    h = 25
    crop_a, crop_b = two.crop((0, 0, 200, h)), two.crop((0, h, 200, 2 * h))
    assert crop_a.tobytes() != crop_b.tobytes(), 'two different faces must render differently'
    s1, s2 = same.crop((0, 0, 200, h)), same.crop((0, h, 200, 2 * h))
    assert s1.tobytes() == s2.tobytes(), 'same face twice must render identically'


def test_sample_text_constant():
    assert SAMPLE_TEXT == 'Kinetische Typografie — Äpfel über Größe · Quick brown fox 0123'


@pytest.mark.asyncio
async def test_sharp_preview_opens_quicklook(tmp_path, monkeypatch):
    """The sharp (external Quick Look) preview stays; the inline one is gone (0.8.1)."""
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
        assert scr.query_one('#all-roles', CheckRow).value is True
        assert not scr.query('#font-preview'), 'inline preview must be gone in 0.8.1'
        seq = next(s for f, s in scr._shown if f == 'Montserrat')
        from types import SimpleNamespace
        scr.on_list_view_selected(SimpleNamespace(item=SimpleNamespace(id=f'font-{seq}')))
        await pilot.pause(0.5)
        await choose(pilot, scr, 'sharp')
        await pilot.pause(0.5)
        assert opened and opened[0][0] == 'qlmanage' and opened[0][1] == '-p', opened
        png = opened[0][2]
        assert os.path.isfile(png), png
        assert Image.open(png).width >= 2 * 44, Image.open(png).width
