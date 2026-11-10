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
from textual.message import Message
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

# csl-style CSS (session_picker.py): no painted background anywhere; the terminal's own
# theme shows through. Highlight = soft-blue text only, never a filled block.
CSL_CSS = """
Screen { layout: vertical; background: ansi_default; color: ansi_default; }
Static, Label { background: ansi_default; color: ansi_default; }
ListView { background: ansi_default; color: ansi_default; border: none; }
/* hover works like csl: soft-blue text on hover AND on keyboard highlight, never a filled block.
   Selectors copied from Textual 8.2.8's own ListView DEFAULT_CSS (widgets/_list_view.py): the
   live classes are `-hovered` / `-highlight`. v0.4.x targeted `.list-item:hover`, which matches
   NOTHING — tests/test_hover_csl.py asserts the computed style so a dead selector goes red. */
ListView > ListItem.-hovered { background: ansi_default; color: ansi_bright_blue; }
ListView > ListItem.-highlight { background: ansi_default; color: ansi_bright_blue; text-style: none; }
ListView:focus > ListItem.-highlight { background: ansi_default; color: ansi_bright_blue; text-style: bold; }
ListView:focus { background-tint: ansi_default 0%; }
/* the row's Label sets its own colour (`Static, Label` rule above), so it must be recoloured
   explicitly — inheritance from the ListItem never reaches it */
ListView > ListItem.-hovered Label, ListView > ListItem.-highlight Label { color: ansi_bright_blue; }
ListView:focus > ListItem.-highlight Label { color: ansi_bright_blue; text-style: bold; }
/* OptionList (menus): same rules as csl session_picker.py:814-821 */
OptionList { background: ansi_default; color: ansi_default; border: none; background-tint: ansi_default 0%; }
OptionList:focus { background: ansi_default; color: ansi_default; border: none; }
OptionList > .option-list--option-highlighted { background: ansi_default; color: ansi_bright_blue; text-style: none; }
OptionList:focus > .option-list--option-highlighted { background: ansi_default; color: ansi_bright_blue; text-style: bold; }
OptionList > .option-list--option-hover { background: ansi_default; color: ansi_bright_blue; }
/* home menu: one empty line between all items */
#menu-list > ListItem { margin: 0 0 1 0; }
/* rounded frames surround the TEXT FIELDS only (inputs + dropdowns), not the window */
Input { background: ansi_default; color: ansi_default; border: round ansi_bright_black; }
Input:focus { border: round ansi_bright_blue; }
/* Select: the VISIBLE field is its inner SelectCurrent (Textual 8.2.8 _select.py gives it a
   `tall` border, also under :ansi) — frame that, never the wrapper (v0.4.x drew both) */
Select { border: none; background: ansi_default; }
Select > SelectCurrent, Select > SelectCurrent:ansi { border: round ansi_bright_black; background: ansi_default; color: ansi_default; background-tint: ansi_default 0%; }
Select:focus > SelectCurrent, Select:focus > SelectCurrent:ansi { border: round ansi_bright_blue; background-tint: ansi_default 0%; }
Select > SelectOverlay { border: round ansi_bright_black; background: ansi_default; color: ansi_default; }
/* SelectOverlay IS an OptionList: `OptionList:focus { border: none }` above outranks a plain
   `Select > SelectOverlay` while the overlay is open (it has focus) — repeat with :focus */
Select > SelectOverlay:focus { border: round ansi_bright_blue; background: ansi_default; background-tint: ansi_default 0%; }
Button { background: ansi_default; color: ansi_default; border: none; }
Button:focus { background: ansi_default; color: ansi_bright_blue; text-style: bold; }
Button:hover { background: ansi_default; color: ansi_bright_blue; }
Log { background: ansi_default; color: ansi_default; border: none; }
Header, Footer { background: ansi_default; color: ansi_bright_black; }
.panel { padding: 0 1; background: ansi_default; height: 1fr; }
.title { text-style: bold; padding: 0 0 1 0; }
.subtitle { color: ansi_bright_cyan; padding: 0 0 1 0; }
.hint { color: ansi_bright_black; }
.version { color: ansi_bright_black; text-style: italic; padding: 1 0 0 0; }
/* form fields, then the action rows DIRECTLY below them (Back last); only screens with a
   long list (fonts) let the body fill the height (class body-fill) */
#body { height: auto; }
#body.body-fill { height: 1fr; }
/* the screens' own wrapper containers default to 1fr in Textual — size them to content */
#body > Vertical, #body > Horizontal { height: auto; }
#body.body-fill > Vertical, #body.body-fill > Horizontal { height: 1fr; }
#actions { height: auto; max-height: 100%; margin: 1 0 0 0; padding: 0; }
.spacer { height: 1fr; min-height: 0; }
/* scrollbars: thin grey thumb on the terminal background, never a painted block */
* { scrollbar-background: ansi_default; scrollbar-background-hover: ansi_default;
    scrollbar-background-active: ansi_default; scrollbar-color: ansi_bright_black;
    scrollbar-color-hover: ansi_bright_blue; scrollbar-color-active: ansi_bright_blue;
    scrollbar-corner-color: ansi_default; scrollbar-size-vertical: 1; }
.swatch { width: 4; height: 1; }
.colour-row { height: 3; }
.hexfield { width: 12; }
.hsl { width: 7; }
.role-row { height: 3; }
.role-label { width: 11; padding: 1 1 0 0; }
.weight { width: 16; }
#fontlist { width: 1fr; }
#editor { width: 30; padding: 0 0 0 1; }
#family { height: 2; padding: 0 0 1 0; }
"""


class MenuAppBase(App):
    """App with csl's terminal-native theme (ansi_default everywhere, ansi_color on)."""

    CSS = CSL_CSS
    # `b`/`q` as priority bindings: a focused Input still receives typed letters (Textual's
    # Input.check_consume_key wins over single-key bindings — verified 2026-11-10: typing
    # "abc" into a path field keeps the screen and the value).
    BINDINGS = [Binding('b', 'back', 'Back to main menu (no save)', show=False, priority=True),
                Binding('q', 'quit_app', 'Quit', show=False, priority=True)]

    def __init__(self, **kwargs):
        kwargs.setdefault('ansi_color', True)
        super().__init__(**kwargs)

    def action_back(self):
        # only a SUBMENU goes back; on the main menu `b` does nothing (v0.4.x popped the main
        # menu itself and left an empty screen)
        if isinstance(self.screen, SubmenuScreen):
            self.pop_screen()

    def action_quit_app(self):
        self.exit()


class ActionMenu(OptionList):
    """csl-style action rows: `N) label` for numbered actions, bare `Back` / `Quit` last.
    spaced=True puts a blank (disabled, unselectable) row between items (home menu)."""

    class Chosen(Message):
        def __init__(self, action_id: str):
            super().__init__()
            self.action_id = action_id

    BARE = ('back', 'quit')

    def __init__(self, actions, spaced=False, first_number=1, **kwargs):
        self.actions = list(actions)
        self.numbers = {}
        opts = []
        n = first_number
        for i, (aid, label) in enumerate(self.actions):
            if spaced and i:
                opts.append(Option(' ', disabled=True, id=f'_gap{i}'))
            if aid in self.BARE:
                opts.append(Option(label, id=aid))
            else:
                self.numbers[str(n)] = aid
                opts.append(Option(f'{n}) {label}', id=aid))
                n += 1
        super().__init__(*opts, **kwargs)

    def on_option_list_option_selected(self, event):
        event.stop()
        self.post_message(self.Chosen(event.option.id))

    def set_enabled(self, action_id: str, enabled: bool) -> None:
        (self.enable_option if enabled else self.disable_option)(action_id)


class SubmenuScreen(Screen):
    """Every submenu: bold title, body, then the action rows with `Back` (no save) LAST.
    Menu grammar: digits = actions (when no text field has focus), b/esc = back, q = quit.
    Back never saves — the user may not have all inputs yet and wants to check the other
    menu options first. Subclasses set TITLE + ACTIONS and implement on_action()."""

    TITLE = ''
    ACTIONS: list = []
    BODY_FILL = False
    HINT = '↑↓ move · Enter/click select · 1-9 action · b/esc back (no save) · q quit'
    BINDINGS = [Binding('escape', 'back', 'Back (no save)', show=False)]

    def compose(self):
        with Vertical(classes='panel'):
            yield Static(self.TITLE, classes='title')
            with Vertical(id='body', classes='body-fill' if self.BODY_FILL else ''):
                yield from self.compose_body()
            yield ActionMenu(self.ACTIONS + [('back', 'Back')], id='actions')
            yield from self.compose_after_actions()
            if not self.BODY_FILL:
                yield Static('', classes='spacer')
            yield Static(self.HINT, classes='hint')

    def compose_body(self):
        raise NotImplementedError

    def compose_after_actions(self):
        return iter(())

    def on_action(self, action_id: str) -> None:
        pass

    def run_action(self, action_id: str) -> None:
        if action_id == 'back':
            self.action_back()
        else:
            self.on_action(action_id)

    def on_action_menu_chosen(self, event):
        self.run_action(event.action_id)

    def on_key(self, event):
        menu = self.query_one('#actions', ActionMenu)
        if event.key in menu.numbers and not isinstance(self.focused, Input):
            aid = menu.numbers[event.key]
            if not menu.get_option(aid).disabled:
                self.run_action(aid)
            event.stop()

    def action_back(self):
        if self.app.screen is self:
            self.app.pop_screen()

    def action_quit_app(self):
        self.app.exit()
