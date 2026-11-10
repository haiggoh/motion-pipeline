"""ColoursScreen — CI colours of the CURRENT project (design §2 step 1, G3), with live
swatches + H/S/L fields and optional colour variants (0.5.0 Tasks 4/4b/4c).

One labelled row per colour: [name][swatch][hex][H][S][L]. Values are prefilled from the
project's scheme.json; each hex edit live-updates its swatch + H/S/L, and an H/S/L edit
updates hex + swatch. Off by default, the "Multiple colour variants" checkbox reveals a
variant picker: a variant is an OVERLAY (<project>/variants/<name>.json holding only the
colours that differ from the base), so it stays in sync with every other project change.
"""
import os

from textual.containers import Horizontal, Vertical
from textual.widgets import Checkbox, Input, Label, Select, Static

from .. import project as project_mod
from .. import scheme as scheme_mod
from .base import SubmenuScreen

COLOUR_KEYS = scheme_mod.COLOUR_KEYS
NEW_VARIANT = '__new__'


def scheme_path(project_dir):
    return scheme_mod.base_scheme_path(project_dir)


class ColoursScreen(SubmenuScreen):
    TITLE = 'CI colours'
    ACTIONS = [('derive', 'Derive & preview'), ('save', 'Save colours')]

    def compose_body(self):
        with Vertical(id='colour-rows'):
            for key in COLOUR_KEYS:
                with Horizontal(classes='colour-row'):
                    yield Label(key.replace('_', ' '), classes='colour-label')
                    yield Static('░░', id=f'swatch-{key}', classes='swatch -empty')
                    yield Input(id=key, placeholder='#rrggbb', classes='hexfield')
                    yield Label('H', classes='hsl-label')
                    yield Input(id=f'h-{key}', placeholder='H', classes='hsl')
                    yield Label('S', classes='hsl-label')
                    yield Input(id=f's-{key}', placeholder='S', classes='hsl')
                    yield Label('L', classes='hsl-label')
                    yield Input(id=f'l-{key}', placeholder='L', classes='hsl')
        with Horizontal(id='variant-bar'):
            yield Checkbox('Multiple colour variants', id='multi')
            yield Select([('default', 'default')], id='variant', value='default',
                         allow_blank=False, classes='variant-select')
            yield Input(id='variant-name', placeholder='new variant name', classes='variant-name')

    def compose_after_actions(self):
        yield Static('', id='preview')
        yield Static('', id='error')

    # ---- state ------------------------------------------------------------------------
    def project_dir(self):
        return getattr(self.app, 'project_dir', None)

    def on_mount(self):
        self._echo = set()
        pd = self.project_dir()
        variants = scheme_mod.list_variants(pd) if pd else ['default']
        multi = len(variants) > 1
        self.query_one('#multi', Checkbox).value = multi
        self._refresh_variant_options(variants, 'default')
        self._show_variant_bar(multi)
        self.load_variant('default')

    def _refresh_variant_options(self, variants, selected):
        sel = self.query_one('#variant', Select)
        sel.set_options([(v, v) for v in variants] + [('+ new variant', NEW_VARIANT)])
        sel.value = selected

    def _show_variant_bar(self, on):
        self.query_one('#variant', Select).display = on
        self.query_one('#variant-name', Input).display = on and self.current_variant() == NEW_VARIANT

    def current_variant(self):
        v = self.query_one('#variant', Select).value
        return v if isinstance(v, str) else 'default'

    def load_variant(self, name):
        """Fill the rows from the resolved variant (base for 'default')."""
        pd = self.project_dir()
        if not pd or not os.path.isfile(scheme_path(pd)):
            for k in COLOUR_KEYS:
                self._set_swatch(k, None)
            return
        try:
            s = scheme_mod.resolve_variant(pd, name)
        except ValueError as e:
            self.query_one('#error', Static).update(f'error: {e}')
            return
        for k in COLOUR_KEYS:
            self.set_colour(k, s[k])

    def set_colour(self, key, hexv):
        hh, ss, ll = scheme_mod.hex_to_hsl(hexv)
        self._set_field(key, hexv)
        self._set_field(f'h-{key}', str(hh))
        self._set_field(f's-{key}', str(ss))
        self._set_field(f'l-{key}', str(ll))
        self._set_swatch(key, hexv)

    def current_colours(self):
        return {k: self.query_one(f'#{k}', Input).value.strip() for k in COLOUR_KEYS}

    # ---- events -----------------------------------------------------------------------
    def on_checkbox_changed(self, event):
        if event.checkbox.id == 'multi':
            if not event.value:
                self.query_one('#variant', Select).value = 'default'
            self._show_variant_bar(event.value)

    def on_select_changed(self, event):
        if event.select.id != 'variant':
            return
        v = event.value
        self.query_one('#variant-name', Input).display = (v == NEW_VARIANT)
        if isinstance(v, str) and v != NEW_VARIANT:
            self.load_variant(v)

    def _set_field(self, wid, value):
        """Set a field programmatically and mark the resulting Changed event as an echo, so
        it is not mistaken for a user edit (v0.5.0 bug: a deferred H/S/L echo overwrote a
        just-typed invalid hex with the previous colour). Only marks when the value really
        changes — an unchanged value fires no event and would swallow the next real edit."""
        inp = self.query_one(f'#{wid}', Input)
        if inp.value != value:
            self._echo.add(wid)
            inp.value = value

    def on_input_changed(self, event: Input.Changed) -> None:
        """Live two-way sync: hex <-> HSL <-> swatch."""
        wid = event.input.id
        if wid in self._echo:
            self._echo.discard(wid)
            return
        if wid in COLOUR_KEYS:  # hex edited by the user
            # NB: never _set_field(wid, …) here — Input.value applies immediately but Changed
            # events queue, so rewriting the field would mark the NEXT queued edit as an echo
            # and swallow it (0.5.1 bug). The field keeps the raw text; canonicalise at the
            # swatch/HSL and at save.
            try:
                canon = scheme_mod.normalise_hex(event.value)  # accepts bare 'ffffff' too
            except ValueError:
                self._set_swatch(wid, None)  # invalid input: empty swatch, never a crash
                return
            hh, ss, ll = scheme_mod.hex_to_hsl(canon)
            self._set_field(f'h-{wid}', str(hh))
            self._set_field(f's-{wid}', str(ss))
            self._set_field(f'l-{wid}', str(ll))
            self._set_swatch(wid, canon)
        elif wid and wid[0] in 'hsl' and wid[1:2] == '-':  # H/S/L edited by the user
            key = wid[2:]
            if key not in COLOUR_KEYS:
                return
            try:
                hh = float(self.query_one(f'#h-{key}', Input).value or 0)
                ss = float(self.query_one(f'#s-{key}', Input).value or 0)
                ll = float(self.query_one(f'#l-{key}', Input).value or 0)
            except ValueError:
                return
            hexv = scheme_mod.hsl_to_hex(hh, ss, ll)
            self._set_field(key, hexv)
            self._set_swatch(key, hexv)

    def _set_swatch(self, key, hexv):
        """A field value must never be able to crash the app: only a canonical '#rrggbb'
        (Textual's parser rejects bare hex) is ever assigned to the style."""
        sw = self.query_one(f'#swatch-{key}', Static)
        try:
            canon = scheme_mod.normalise_hex(hexv) if hexv else None
        except ValueError:
            canon = None
        sw.set_class(canon is None, '-empty')
        if canon:
            sw.update('')
            sw.styles.background = canon
        else:
            sw.update('░░')  # visible empty marker: no colour yet
            sw.styles.background = 'ansi_default'

    def on_action(self, action_id) -> None:
        err = self.query_one('#error', Static)
        err.update('')
        try:
            pd = self.require_project()
            # canonicalise on the way in: scheme.json always stores '#rrggbb', never bare hex
            colours = {k: scheme_mod.normalise_hex(v) for k, v in self.current_colours().items()}
            scheme = scheme_mod.validate_scheme({'name': os.path.basename(pd), **colours})
            if action_id == 'derive':
                p = scheme_mod.derive_palette(scheme)
                self.query_one('#preview', Static).update(self._palette_line(p))
            elif action_id == 'save':
                variant = self.current_variant() if self.query_one('#multi', Checkbox).value else 'default'
                if variant == NEW_VARIANT:
                    variant = scheme_mod.check_variant_name(self.query_one('#variant-name', Input).value.strip())
                if variant == 'default':
                    scheme_mod.save_scheme(scheme_path(pd), scheme)
                    msg = f'saved {scheme_path(pd)}'
                else:
                    if not os.path.isfile(scheme_path(pd)):
                        raise ValueError('save the default colours first — a variant only overrides them')
                    ov = scheme_mod.save_variant(pd, variant, colours)
                    msg = f'saved variant {variant!r} ({len(ov)} colour(s) differ from default)'
                self._sync_project_variants(pd)
                self._refresh_variant_options(scheme_mod.list_variants(pd), variant)
                self._show_variant_bar(self.query_one('#multi', Checkbox).value)
                self.query_one('#preview', Static).update(msg)
        except ValueError as e:
            err.update(f'error: {e}')

    def _sync_project_variants(self, pd):
        pj = os.path.join(pd, 'project.json')
        p = project_mod.load(pd) if os.path.isfile(pj) else project_mod.default_project(os.path.basename(pd))
        p['variants'] = scheme_mod.list_variants(pd)
        project_mod.save(pd, p)

    @staticmethod
    def _palette_line(p):
        from rich.text import Text
        t = Text()
        for k in ('secondary_text', 'label_tint', 'particle_colour', 'highlight_bar'):
            t.append(f'{k.replace("_", " ")} ')
            t.append('  ', style=f'on {p[k]}')
            t.append('  ')
        t.append('gradient ')
        for stop in p['gradient_stops']:
            t.append('  ', style=f'on {stop}')
        return t
