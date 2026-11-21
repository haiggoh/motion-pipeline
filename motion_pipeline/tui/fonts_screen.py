"""FontsScreen — role-by-role font choice over the font index (Task 9, design G4).

The font list comes from font_index.scan (recursive, cached, background worker with the loader
IN the list area — never a bottom status row). Picking a family assigns it to the role chosen in
#edit-role (or all roles). Browsing copies NOTHING (P5): a system/client face is copied into the
project's gitignored fonts/ only on Save, via fonts.copy_client_faces, and flagged non-OFL.
Save: project.load → copy_client_faces → font_gate (validate BEFORE write) → project.save.
"""
import json
import os
import subprocess

from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Label, ListItem, ListView, LoadingIndicator, Select, Static

from .. import font_index
from .. import font_preview
from .. import fonts as fonts_mod
from .. import project as project_mod
from .ansi_image import render_ansi_image
from .base import SubmenuScreen


def project_json_path(project_dir):
    return os.path.join(project_dir, 'project.json')


def bundled_ref(abs_path):
    """'motion_pipeline/fonts/...' ref for a bundled face's abs path."""
    pkg = os.path.dirname(os.path.abspath(fonts_mod.__file__))
    return 'motion_pipeline/' + os.path.relpath(abs_path, pkg)


class FontsScreen(SubmenuScreen):
    TITLE = 'Font'
    ACTIONS = [('save', 'Save font config'), ('sharp', 'Sharp preview (Quick Look)')]
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
                        yield Label(role, classes='role-label')
                        yield Static('(none)', id=f'role-{role}-family')
                        yield Select([], id=f'role-{role}-weight', allow_blank=True, classes='weight')
                yield Select([('Headline', 'headline'), ('Label', 'label'), ('Body', 'body'),
                             ('Emphasis', 'emphasis'), ('All roles', 'all')],
                            id='edit-role', value='headline', allow_blank=False)
                yield Label('Preview')
                yield Input(id='sample-text', value=font_preview.SAMPLE_TEXT)
                yield Static('', id='font-preview')
                yield Static('', id='licence-warning', classes='feedback')
                yield Static('', id='status', classes='feedback')
                yield Static('', id='error', classes='feedback-error')

    def on_mount(self):
        self._all = {}       # family -> list[Face]
        self._selected = None
        self._shown = []     # (family, seq)
        self._seq = 0
        self._role_family = {r: None for r in fonts_mod.ROLES}
        self._preview_token = 0
        self._refresh_list('')
        # the loader sits where the list will appear (never a bottom status row)
        fl = self.query_one('#fontlist')
        self._scan_status = Static('scanning fonts…', id='scan-status', classes='muted')
        self._scan_loader = LoadingIndicator(id='scan-loader')
        fl.mount(self._scan_status)
        fl.mount(self._scan_loader)
        self._scan_worker = self.run_worker(self._scan, thread=True, exclusive=True, name='font-scan')

    def _scan(self):
        def prog(done, total):
            self.app.call_from_thread(self._on_scan_progress, done, total)
        faces = font_index.scan(progress=prog)
        self.app.call_from_thread(self._on_scan_done, faces)

    def _on_scan_progress(self, done, total):
        self._scan_status.update(f'scanning fonts… {done}/{total}')

    def _on_scan_done(self, faces):
        fams = font_index.families(faces)
        self._all = dict(sorted(fams.items(),
                                key=lambda kv: (not any(f['bundled'] for f in kv[1]), kv[0])))
        self._scan_status.display = False
        self._scan_loader.display = False
        self._refresh_list(self.query_one('#font-search', Input).value)
        self._prefill_from_project()

    def _prefill_from_project(self):
        pd = getattr(self.app, 'project_dir', None)
        if not pd:
            return
        if not os.path.isfile(os.path.join(pd, 'project.json')):
            return   # no project yet — not an error
        try:
            p = project_mod.load(pd)
            cfg = fonts_mod.normalise_fonts(p.get('fonts', {}), pd)
        except (ValueError, OSError, json.JSONDecodeError) as e:
            # Task 6 (X2): name the corrupt project.json — never show defaults as real state
            from textual.widgets import Static
            self.query_one('#error', Static).update(f'error: project.json: {e}')
            return
        for role, r in cfg['roles'].items():
            self._set_role_family(role, r['family'], r['weight'])

    def _set_role_family(self, role, family, weight=None):
        self._role_family[role] = family
        faces = [f for f in self._all.get(family, []) if not f['italic']]
        sel = self.query_one(f'#role-{role}-weight', Select)
        # Select options are (prompt, value) tuples in Textual 8
        sel.set_options([(font_index.weight_label(f), f['weight']) for f in faces])
        if weight is not None and any(f['weight'] == weight for f in faces):
            sel.value = weight
        elif faces:
            default_w = fonts_mod.DEFAULT_WEIGHTS[role]
            sel.value = default_w if any(f['weight'] == default_w for f in faces) else faces[0]['weight']
        label = f'{family} · {font_index.weight_label(faces[0])}' if faces else family
        self.query_one(f'#role-{role}-family', Static).update(label)

    def _refresh_list(self, query):
        lv = self.query_one('#fonts', ListView)
        lv.clear()
        q = query.strip().lower()
        self._shown = []
        for fam in self._all:
            if q and q not in fam.lower():
                continue
            self._seq += 1  # ever-increasing ids (lv.clear() is async — DuplicateIds trap)
            bundled = any(f['bundled'] for f in self._all[fam])
            lv.append(ListItem(Label(fam + (' (OFL bundled)' if bundled else '')), id=f'font-{self._seq}'))
            self._shown.append((fam, self._seq))

    def on_input_changed(self, event):
        if event.input.id == 'font-search':
            self._refresh_list(event.value)
        elif event.input.id == 'sample-text':
            self._schedule_preview()

    def on_select_changed(self, event):
        self._schedule_preview()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        seq = int(event.item.id.removeprefix('font-'))
        fam = next(s[0] for s in self._shown if s[1] == seq)
        self._selected = fam
        self.query_one('#family', Static).update(f'Family: {fam}')
        target = self.query_one('#edit-role', Select).value
        for role in (fonts_mod.ROLES if target == 'all' else (target,)):
            self._set_role_family(role, fam)
        # P5: browsing copies NOTHING — a client face is copied into the project only on Save
        bundled = any(f['bundled'] for f in self._all[fam])
        warn = self.query_one('#licence-warning', Static)
        if not bundled:
            warn.update(f'LICENCE WARNING: {fam} is a system/client font (licence not OFL-verified). '
                        'Copied into the project\'s gitignored fonts/ only on Save; never committed to this repo.')
        else:
            warn.update('')
        self._schedule_preview()

    # --- preview (Task 10): inline half-block, debounced 150 ms; sharp = Quick Look PNG at 2x ---
    PX_BY_ROLE = {'headline': 24, 'label': 14, 'body': 16, 'emphasis': 16}

    def _schedule_preview(self):
        self._preview_token += 1
        token = self._preview_token
        self.set_timer(0.15, lambda: self._update_preview(token))

    def _preview_lines(self):
        text = self.query_one('#sample-text', Input).value or font_preview.SAMPLE_TEXT
        lines = []
        for role in fonts_mod.ROLES:
            fam = self._role_family.get(role)
            if not fam:
                continue
            w = self.query_one(f'#role-{role}-weight', Select).value
            faces = [f for f in self._all.get(fam, []) if not f['italic'] and (w is None or f['weight'] == w)]
            if not faces:
                continue
            face = next((f for f in faces if f['bundled']), faces[0])
            lines.append((text, face['path'], face['index'], self.PX_BY_ROLE[role]))
        return lines

    def _preview_colors(self):
        fg, bg = '#ffffff', '#101010'
        pd = getattr(self.app, 'project_dir', None)
        if pd:
            sp = os.path.join(pd, 'scheme.json')
            if os.path.isfile(sp):
                try:
                    from .. import scheme as scheme_mod
                    pal = scheme_mod.derive_palette(json.load(open(sp)))
                    fg, bg = pal['text'], pal['background_dark']
                except Exception:
                    pass
        return fg, bg

    def _update_preview(self, token):
        if token != self._preview_token or not self._all:
            return
        lines = self._preview_lines()
        if not lines:
            return
        fg, bg = self._preview_colors()
        img = font_preview.render_sample(lines, 88, fg, bg, scale=1.0)
        png = os.path.join(os.environ.get('TMPDIR', '/tmp'),
                           f'motion-pipeline-preview-inline-{os.getpid()}.png')
        img.save(png)
        self.query_one('#font-preview', Static).update(render_ansi_image(png, max_w=44, max_h=12))

    def _sharp_preview(self):
        err = self.query_one('#error', Static)
        err.update('')
        try:
            lines = self._preview_lines()
            if not lines:
                raise ValueError('pick a font family in the list first')
            fg, bg = self._preview_colors()
            img = font_preview.render_sample(lines, 88, fg, bg, scale=2.0)
            png = os.path.join(os.environ.get('TMPDIR', '/tmp'),
                               f'motion-pipeline-preview-{os.getpid()}.png')
            img.save(png)
            subprocess.Popen(['qlmanage', '-p', png], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.query_one('#status', Static).update(f'sharp preview: {png}')
        except (ValueError, OSError) as e:
            err.update(f'error: {e}')

    def on_action(self, action_id):
        if action_id == 'sharp':
            self._sharp_preview()
            return
        if action_id != 'save':
            return
        err = self.query_one('#error', Static)
        err.update('')
        try:
            pdir = self.require_project()
            roles = {}
            for role in fonts_mod.ROLES:
                fam = self._role_family[role] or self._selected
                if not fam:
                    raise ValueError(f'role {role!r} has no family — pick a font in the list first')
                w = self.query_one(f'#role-{role}-weight', Select).value
                faces = [f for f in self._all.get(fam, []) if not f['italic'] and f['weight'] == w]
                if not faces:
                    raise ValueError(f'font gate: no face {fam} {w} — pick a weight from the list')
                face = next((f for f in faces if f['bundled']), faces[0])
                roles[role] = {'family': fam, 'weight': w, 'index': face['index'],
                               'file': bundled_ref(face['path']) if face['bundled'] else face['path']}
            p = project_mod.load(pdir)
            cfg = {'roles': fonts_mod.copy_client_faces(pdir, roles)}  # P5: copy client faces at SAVE
            fonts_mod.font_gate(pdir, {'fonts': cfg})                   # validate BEFORE write (finding 5)
            p['fonts'] = cfg
            project_mod.save(pdir, p)
            self.query_one('#status', Static).update(f'saved {project_json_path(pdir)}')
        except (ValueError, OSError, KeyError) as e:
            err.update(f'error: {e}')
