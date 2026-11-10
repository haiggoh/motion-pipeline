"""Positive controls for tests/tui_probe.py — a probe that cannot fail proves nothing."""
from textual.app import App
from textual.widgets import Static

from tui_probe import bg_is_default, fg_is_blue, on_screen


class _Planted(App):
    CSS = """
    Screen { background: ansi_default; }
    #filled { background: ansi_red; color: ansi_bright_blue; }
    #plain { background: ansi_default; color: ansi_default; }
    #off { offset: 200 0; width: 5; }
    """

    def compose(self):
        yield Static('x', id='filled')
        yield Static('y', id='plain')
        yield Static('z', id='off')


async def test_probes_tell_filled_from_default_and_offscreen():
    app = _Planted(ansi_color=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        filled, plain, off = (app.query_one(f'#{i}') for i in ('filled', 'plain', 'off'))
        assert not bg_is_default(filled.rich_style)   # planted positive: filled bg detected
        assert bg_is_default(plain.rich_style)
        assert fg_is_blue(filled.rich_style) and not fg_is_blue(plain.rich_style)
        assert on_screen(app, plain) and not on_screen(app, off)
