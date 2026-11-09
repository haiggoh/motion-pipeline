"""ColoursScreen — CI colour setup (design §2 step 1, G3), with live swatches + HSL fields.

Each main colour has: a hex field, a live swatch that updates as you type, and separate
H/S/L text fields — editing either side updates the other and the swatch immediately.
"""
import os

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from .. import scheme as scheme_mod
from .base import SubmenuScreen

PROJECTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'projects')
COLOUR_KEYS = scheme_mod.INPUT_KEYS[1:]


def scheme_path(project_dir):
    return os.path.join(project_dir, 'scheme.json')


class ColoursScreen(SubmenuScreen):
    def compose_body(self):
        with Horizontal():
            with Vertical(id='scheme-list'):
                yield Label('Saved schemes (click to re-edit)')
                yield ListView(id='schemes')
            with Vertical(id='editor'):
                yield Label('Project name')
                yield Input(id='name', placeholder='my-project')
                for key in COLOUR_KEYS:
                    with Horizontal(classes='colour-row'):
                        yield Static('  ', id=f'swatch-{key}', classes='swatch')
                        yield Input(id=key, placeholder='#rrggbb')
                        yield Label('H')
                        yield Input(id=f'h-{key}', placeholder='0-360', classes='hsl')
                        yield Label('S')
                        yield Input(id=f's-{key}', placeholder='0-100', classes='hsl')
                        yield Label('L')
                        yield Input(id=f'l-{key}', placeholder='0-100', classes='hsl')
                with Horizontal():
                    yield Button('Derive & preview', id='derive')
                    yield Button('Save scheme', id='save', variant='primary')
                yield Static('', id='preview')
                yield Static('', id='error')

    def on_mount(self) -> None:
        self.refresh_scheme_list()

    def project_dir(self):
        return getattr(self.app, 'project_dir', PROJECTS)

    def refresh_scheme_list(self) -> None:
        if not self.query('#schemes'):
            return
        lv = self.query_one('#schemes', ListView)
        existing = {getattr(c, 'id', '') for c in lv.children}
        base = self.project_dir()
        if not os.path.isdir(base):
            return
        for name in sorted(os.listdir(base)):
            p = scheme_path(os.path.join(base, name))
            if os.path.isfile(p) and f'scheme-{name}' not in existing:
                lv.append(ListItem(Label(name), id=f'scheme-{name}'))

    def current_scheme(self):
        name = self.query_one('#name', Input).value.strip()
        vals = {k: self.query_one(f'#{k}', Input).value.strip() for k in COLOUR_KEYS}
        return {'name': name, **vals}

    def on_input_changed(self, event: Input.Changed) -> None:
        """Live two-way sync: hex <-> HSL <-> swatch for the edited colour. An HSL change
        that exactly matches the current hex (i.e. it is just the hex->hsl sync echo) is
        not written back, so the hex never degrades through a lossy round-trip."""
        wid = event.input.id
        if wid in COLOUR_KEYS:  # hex edited
            hexv = event.value.strip()
            try:
                hh, ss, ll = scheme_mod.hex_to_hsl(hexv)
                self.query_one(f'#h-{wid}', Input).value = str(hh)
                self.query_one(f'#s-{wid}', Input).value = str(ss)
                self.query_one(f'#l-{wid}', Input).value = str(ll)
                self._set_swatch(wid, hexv)
            except ValueError:
                self._set_swatch(wid, None)
        elif wid and wid[0] in 'hsl' and '-' in wid:  # HSL field edited
            _, key = wid.split('-', 1)
            if key not in COLOUR_KEYS:
                return
            try:
                hh = float(self.query_one(f'#h-{key}', Input).value or 0)
                ss = float(self.query_one(f'#s-{key}', Input).value or 0)
                ll = float(self.query_one(f'#l-{key}', Input).value or 0)
                cur = self.query_one(f'#{key}', Input).value.strip()
                ch, cs, cl = scheme_mod.hex_to_hsl(cur) if cur else (0, 0, 0)
                if (round(hh), round(ss), round(ll)) == (ch, cs, cl):
                    return  # sync echo, not a user edit — don't rewrite the hex
                hexv = scheme_mod.hsl_to_hex(hh, ss, ll)
                self.query_one(f'#{key}', Input).value = hexv
                self._set_swatch(key, hexv)
            except ValueError:
                pass

    def _set_swatch(self, key, hexv):
        sw = self.query_one(f'#swatch-{key}', Static)
        sw.update('  ')
        sw.styles.background = hexv if hexv else 'ansi_default'

    def on_button_pressed(self, event: Button.Pressed) -> None:
        err = self.query_one('#error', Static)
        err.update('')
        try:
            s = scheme_mod.validate_scheme(self.current_scheme())
            if event.button.id == 'derive':
                p = scheme_mod.derive_palette(s)
                lines = [f'{k}: {v}' for k, v in p.items() if k != 'gradient_stops']
                lines.append('gradient_stops: ' + ' -> '.join(p['gradient_stops']))
                self.query_one('#preview', Static).update('\n'.join(lines))
            elif event.button.id == 'save':
                if not s['name']:
                    raise ValueError('project name is empty')
                scheme_mod.save_scheme(scheme_path(os.path.join(self.project_dir(), s['name'])), s)
                self.query_one('#preview', Static).update(f'saved {scheme_path(os.path.join(self.project_dir(), s["name"]))}')
                self.refresh_scheme_list()
        except ValueError as e:
            err.update(f'error: {e}')

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        name = event.item.id.removeprefix('scheme-')
        s = scheme_mod.load_scheme(scheme_path(os.path.join(self.project_dir(), name)))
        self.query_one('#name', Input).value = s['name']
        for k in COLOUR_KEYS:
            hexv = s[k]
            self.query_one(f'#{k}', Input).value = hexv
            h, ss, ll = scheme_mod.hex_to_hsl(hexv)
            self.query_one(f'#h-{k}', Input).value = str(h)
            self.query_one(f'#s-{k}', Input).value = str(ss)
            self.query_one(f'#l-{k}', Input).value = str(ll)
            self._set_swatch(k, hexv)
