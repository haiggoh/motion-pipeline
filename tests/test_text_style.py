"""Task 4 (0.8.0, user Q1): the text_style field + "Text animation" menu step.

validate() accepts text_style and rejects an unknown name with the valid names listed;
a 0.7.0-era project.json WITHOUT the key loads fine and consumers read DEFAULT ('slide-up');
STEPS gains 'textstyle' after 'inputs' (graphics becomes digit 7, render 8); the menu screen
lists STYLES labels (data-driven: a monkeypatched extra row appears) and saves the choice
into project.json. TUI assertions use visible geometry at 80x24, not just widget presence.
"""
import json
import os

import pytest

from motion_pipeline import project as project_mod
from motion_pipeline import text_styles
from motion_pipeline.tui.app import MenuApp, STEPS
from projfix import make_project
from tui_probe import on_screen


def test_validate_accepts_known_and_rejects_unknown_text_style():
    p = project_mod.default_project('t')
    assert p['text_style'] == text_styles.DEFAULT == 'slide-up'
    for name in text_styles.STYLES:
        p['text_style'] = name
        project_mod.validate(p)  # must not raise
    p['text_style'] = 'bogus-style'
    with pytest.raises(ValueError) as ei:
        project_mod.validate(p)
    msg = str(ei.value)
    assert 'bogus-style' in msg and all(s in msg for s in text_styles.STYLES), msg


def test_legacy_project_without_text_style_loads_and_defaults(tmp_path):
    d = tmp_path / 'legacy'
    d.mkdir()
    p = project_mod.default_project('legacy')
    del p['text_style']  # 0.7.0-era file has no such key
    project_mod.save(str(d), p)  # validate must accept the missing key
    loaded = project_mod.load(str(d))
    assert 'text_style' not in loaded
    assert loaded.get('text_style', text_styles.DEFAULT) == 'slide-up'


def test_steps_has_text_animation_after_inputs():
    ids = [k for k, _ in STEPS]
    assert ids == ['project', 'colours', 'fonts', 'zones', 'bgtest', 'inputs',
                   'textstyle', 'graphics', 'render'], ids


def test_generate_refuses_unknown_text_style_with_valid_names(tmp_path):
    """QC finding: generate() indexed STYLES directly — a bogus text_style raised a bare
    KeyError. Now it raises the same friendly message validate() gives."""
    from motion_pipeline import generate
    pd = make_project(str(tmp_path / 'p'))
    p = project_mod.load(pd)
    p['text_style'] = 'bogus'
    json.dump(p, open(os.path.join(pd, 'project.json'), 'w'))  # write raw, bypassing validate
    with pytest.raises(ValueError) as ei:
        generate.generate(pd)
    assert 'bogus' in str(ei.value) and 'slide-up' in str(ei.value), str(ei.value)


def test_text_styles_importable_before_generate():
    """QC finding: text_styles and generate reference each other — both imports are lazy
    (function-level), so either module must import cleanly first, in either order."""
    import subprocess
    import sys
    for order in ('import motion_pipeline.text_styles, motion_pipeline.generate',
                  'import motion_pipeline.generate, motion_pipeline.text_styles'):
        r = subprocess.run([sys.executable, '-c', order], capture_output=True, text=True)
        assert r.returncode == 0, (order, r.stderr[-300:])


def test_styles_table_shape():
    for name, st in text_styles.STYLES.items():
        assert st.label and st.granularity in ('word', 'letter')
        assert callable(st.layout) and callable(st.tween_js) and st.css
        assert st.tween_js(), f'{name}: tween_js must emit the loop'


@pytest.mark.asyncio
async def test_text_style_screen_lists_styles_and_saves(tmp_path):
    from motion_pipeline.tui.textstyle_screen import TextStyleScreen
    pd = tmp_path / 'p'
    pd.mkdir()
    project_mod.save(str(pd), project_mod.default_project('p'))
    app = MenuApp()
    app.project_dir = str(pd)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = TextStyleScreen()
        app.push_screen(scr)
        await pilot.pause()
        lv = scr.query_one('#styles')
        assert on_screen(app, lv), 'style list must be visible at 80x24'
        assert len(lv.children) == len(text_styles.STYLES)
        labels = [str(c.children[0].render()) for c in lv.children]
        assert all(st.label in labels[i] for i, st in enumerate(text_styles.STYLES.values())), labels
        # pick 'typewriter' (2nd-to-last row) and save through the action handler the menu calls
        target = 'typewriter'
        scr._selected = target
        scr.on_action('save')
        await pilot.pause()
        saved = json.loads(open(os.path.join(pd, 'project.json')).read())
        assert saved['text_style'] == target, saved
        assert 'typewriter' in str(scr.query_one('#status', ).render() if scr.query('#status') else '')


@pytest.mark.asyncio
async def test_style_menu_is_data_driven(tmp_path, monkeypatch):
    """Adding a table row in STYLES appears in the menu with no screen change (plan Task 4)."""
    from motion_pipeline.tui.textstyle_screen import TextStyleScreen
    extra = text_styles.TextStyle(label='Zigzag (test row)', granularity='word', css='',
                                 layout=lambda *a: [], tween_js=lambda: '')
    monkeypatch.setitem(text_styles.STYLES, 'zigzag', extra)
    pd = tmp_path / 'p'
    pd.mkdir()
    project_mod.save(str(pd), project_mod.default_project('p'))
    app = MenuApp()
    app.project_dir = str(pd)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        scr = TextStyleScreen()
        app.push_screen(scr)
        await pilot.pause()
        lv = scr.query_one('#styles')
        assert len(lv.children) == len(text_styles.STYLES)
        labels = [str(c.children[0].render()) for c in lv.children]
        assert any('Zigzag (test row)' in x for x in labels), labels
