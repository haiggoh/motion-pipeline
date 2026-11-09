"""base.py — shared submenu behaviour: csl-style terminal-native CSS + Back-without-saving.

Style copied from csl (free-agents session_picker.py, 2026-11-09): every surface uses
`ansi_default` so the terminal's own background/theme shows through (no painted grey),
inputs get a symmetric `round ansi_bright_black` frame, highlights are text-colour only.
Menu grammar: numbers = actions, `b` = Back to main menu WITHOUT saving, `q` = Quit.
"""
from textual.app import App
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button

# csl-style CSS (session_picker.py): no painted background anywhere; the terminal's own
# theme shows through. Highlight = soft-blue text only, never a filled block.
CSL_CSS = """
Screen { layout: vertical; background: ansi_default; color: ansi_default; }
Static, Label { background: ansi_default; color: ansi_default; }
ListView { background: ansi_default; color: ansi_default; border: none; }
/* hover works like csl: soft-blue text on hover AND on keyboard highlight, never a filled block */
ListView > ListItem:hover { background: ansi_default; color: ansi_bright_blue; }
ListView > .list-item--highlighted { background: ansi_default; color: ansi_bright_blue; text-style: bold; }
/* home menu: one empty line between all items */
#menu-list > ListItem { margin: 0 0 1 0; }
/* rounded frames surround the TEXT FIELDS only (inputs + dropdowns), not the window */
Input, Select { background: ansi_default; color: ansi_default; border: round ansi_bright_black; }
Select:focus { border: round ansi_bright_blue; }
Button { background: ansi_default; color: ansi_default; border: none; }
Button:focus { background: ansi_default; color: ansi_bright_blue; text-style: bold; }
Button:hover { background: ansi_default; color: ansi_bright_blue; }
Log { background: ansi_default; color: ansi_default; border: none; }
Header, Footer { background: ansi_default; color: ansi_bright_black; }
.panel { padding: 0 1; background: ansi_default; height: auto; }
#back { margin-top: 1; }
.swatch { width: 4; height: 1; }
.colour-row { height: auto; }
.hsl { width: 7; }
"""


class MenuAppBase(App):
    """App with csl's terminal-native theme (ansi_default everywhere, ansi_color on)."""

    CSS = CSL_CSS
    # App-level raw key handler (same mechanism as csl's session_picker App.on_key):
    # `b` always means back-to-main-menu-without-saving, `q` always quits — even when an
    # Input/Select has focus (bindings lose to focused widgets, on_key with stop() wins).
    BINDINGS = [Binding('b', 'back', 'Back to main menu (no save)', show=False, priority=True),
                Binding('q', 'quit_app', 'Quit', show=False, priority=True)]

    def __init__(self, **kwargs):
        kwargs.setdefault('ansi_color', True)
        super().__init__(**kwargs)

    def on_key(self, event):
        if event.key == 'b':
            if len(self.screen_stack) > 1:
                self.pop_screen()
            event.stop()
        elif event.key == 'q':
            self.exit()
            event.stop()

    def action_back(self):
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def action_quit_app(self):
        self.exit()


class SubmenuScreen(Screen):
    """Every submenu has a visible 'Back to main menu (no save)' action (menu grammar:
    number keys = actions, b/esc = back, q = quit). Back never saves — the user may not
    have all inputs yet and wants to check the other menu options first."""

    BINDINGS = [Binding('escape', 'back', 'Back (no save)', show=False),
                Binding('b', 'back', 'Back (no save)', show=False, priority=True),
                Binding('q', 'quit_app', 'Quit', show=False)]

    def compose(self):
        with Vertical(classes='panel'):
            yield Button('0 · Back to main menu (no save)  [b/esc]', id='back')
            yield from self.compose_body()

    def compose_body(self):
        raise NotImplementedError

    def action_back(self):
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()

    def action_quit_app(self):
        self.app.exit()

    def on_button_pressed(self, event):
        if event.button.id == 'back':
            self.action_back()
