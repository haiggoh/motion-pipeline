"""FontsScreen — font family with live search over system-installed fonts + bundled OFL
(Task 3, G4; user request 2026-11-09: search and choose any font installed on the system).

Type in the filter to search all fonts found in /Library/Fonts, ~/Library/Fonts and
/System/Library/Fonts (family names read from the font files via PIL). Bundled OFL
families are always listed first. Choosing a system (client) font copies the face file
into the project's gitignored fonts/ folder (never committed to this repo) and shows the
licence warning (decide-question 2). Role->weight selects + save into project.json.
"""
import glob
import os
import shutil

from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Label, ListItem, ListView, Select, Static

from .. import fonts as fonts_mod
from .base import SubmenuScreen

FONT_DIRS = ['/Library/Fonts', os.path.expanduser('~/Library/Fonts'), '/System/Library/Fonts']


def system_fonts():
    """{family: path} of every font file in the system font dirs (family read via PIL)."""
    from PIL import ImageFont
    out = {}
    for d in FONT_DIRS:
        for f in glob.glob(os.path.join(d, '*')):
            if not f.lower().endswith(('.ttf', '.otf', '.ttc', '.dfont')):
                continue
            try:
                name = ImageFont.truetype(f, 12).getname()[0]
            except Exception:
                continue
            out.setdefault(name, f)
    return out


def project_json_path(project_dir):
    return os.path.join(project_dir, 'project.json')


class FontsScreen(SubmenuScreen):
    TITLE = 'Font'
    ACTIONS = [('save', 'Save font config')]
    BODY_FILL = True

    def compose_body(self):
        with Horizontal():
            with Vertical(id='fontlist'):
                yield Label('Search fonts (bundled OFL first)')
                yield Input(id='font-search', placeholder='type to filter…')
                yield ListView(id='fonts')
            with Vertical(id='editor'):
                yield Static('Family: (none)', id='family')
                for role in fonts_mod.ROLES:
                    with Horizontal(classes='role-row'):
                        yield Label(f'{role}', classes='role-label')
                        yield Select([(str(w), w) for w in (400, 600, 700, 900)],
                                     id=f'role-{role}', value=fonts_mod.DEFAULT_WEIGHTS[role],
                                     allow_blank=False, classes='weight')
                yield Static('', id='licence-warning')
                yield Static('', id='status')
                yield Static('', id='error')

    def on_mount(self):
        self._all = {f: None for f in fonts_mod.bundled_families()}  # bundled OFL wins over system copies
        for fam, path in system_fonts().items():
            self._all.setdefault(fam, path)
        self._all = dict(sorted(self._all.items(), key=lambda kv: (kv[1] is not None, kv[0])))
        self._refresh_list('')

    def _refresh_list(self, query):
        lv = self.query_one('#fonts', ListView)
        lv.clear()
        q = query.strip().lower()
        self._shown = []
        for fam, path in self._all.items():
            if q and q not in fam.lower():
                continue
            tag = ' (OFL bundled)' if path is None else ''
            # unique ever-increasing ids: lv.clear() is async, so re-using font-0 would
            # raise DuplicateIds (same trap as the scheme list earlier)
            self._seq = getattr(self, '_seq', 0) + 1
            lv.append(ListItem(Label(fam + tag), id=f'font-{self._seq}'))
            self._shown.append((fam, path, self._seq))

    def on_input_changed(self, event):
        if event.input.id == 'font-search':
            self._refresh_list(event.value)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        seq = int(event.item.id.removeprefix('font-'))
        fam, _src, _seq = next(s for s in self._shown if s[2] == seq)
        path = self._all[fam]
        self._selected = fam
        self.query_one('#family', Static).update(f'Family: {fam}')
        path = self._all.get(fam)
        warn = self.query_one('#licence-warning', Static)
        if path is None:
            warn.update('')
        else:
            # copy the client/system font into the project's gitignored fonts/ (decide-question 2)
            pdir = getattr(self.app, 'project_dir', None)
            if not pdir:
                warn.update('pick or create a project in step 0 first — the font file is copied into it')
                return
            os.makedirs(os.path.join(pdir, 'fonts'), exist_ok=True)
            dst = os.path.join(pdir, 'fonts', os.path.basename(path))
            if not os.path.isfile(dst):
                shutil.copy(path, dst)
            warn.update(f'LICENCE WARNING: {fam} is a system/client font (licence not OFL-verified). '
                        f'Copied to the project\'s gitignored fonts/ ({dst}); never committed to this repo.')

    def on_action(self, action_id):
        if action_id != 'save':
            return
        import json
        err = self.query_one('#error', Static)
        err.update('')
        try:
            fam = getattr(self, '_selected', None)
            if not fam:
                raise ValueError('pick a font family from the list')
            roles = {role: self.query_one(f'#role-{role}', Select).value for role in fonts_mod.ROLES}
            pdir = self.require_project()
            path = project_json_path(pdir)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            cfg = {}
            if os.path.isfile(path):
                cfg = json.loads(open(path).read())
            cfg['fonts'] = {'family': fam, 'roles': roles}
            tmp = path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(cfg, f, indent=2)
                f.write('\n')
            os.replace(tmp, path)
            fonts_mod.font_gate(pdir, cfg)
            self.query_one('#status', Static).update(f'saved {path}')
        except (ValueError, json.JSONDecodeError) as e:
            err.update(f'error: {e}')
