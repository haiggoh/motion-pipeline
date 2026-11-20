"""ProjectScreen — step 0: project picker + create / create-from-sample / load / apply format /
projects folder. app.project_dir is always the CURRENT project folder.

The picker lists every folder in the projects root, newest first; a folder with an invalid
project.json is listed with its error (dimmed), never hidden (Task 3).
"""
import os
import shutil

from textual.containers import Horizontal
from textual.widgets import Checkbox, Input, Label, ListItem, ListView, Select, Static

from .. import config
from .. import project as project_mod
from .. import projects_list
from .base import ActionMenu, SubmenuScreen
from .paths import PathInput

# display order per the README's format list; values must exist in project.ASPECTS
# (Select options are (prompt, value) tuples in Textual 8)
ASPECT_OPTIONS = [(a, a) for a in ('16:9', '9:16', '1:1', '4:5')]
FPS_OPTIONS = [(str(f), f) for f in project_mod.FPS_CHOICES]
SAMPLE_DIR = os.path.join(config.PKG_ROOT, 'samples', 'globe')


class ProjectScreen(SubmenuScreen):
    TITLE = 'New / load project'
    ACTIONS = [('create', 'Create new project'), ('sample', 'Create from sample'),
               ('load', 'Load from directory'), ('format', 'Apply format'),
               ('root', 'Save projects folder')]
    BODY_FILL = True
    # reclaim two rows so the format row stays on screen at 80x24 with the picker (Task 3 layout)
    CSS = ('.title { padding: 0; } #actions { margin: 0 0 0 0; } '
           '#feedback-row { height: 1; margin: 1 0 0 0; } '
           '#feedback-row .feedback, #feedback-row .feedback-error { margin: 0; }')

    def compose_body(self):
        yield Label('Projects', id='projects-label')
        yield ListView(id='projects')
        with Horizontal(classes='path-row'):
            yield Label('Name')
            yield Input(id='name', placeholder='my-project')
        with Horizontal(classes='path-row'):
            yield Label('Directory (drop a folder from Finder)')
            yield PathInput(id='dir', placeholder='optional — <projects folder>/<name>',
                            accepts_dirs=True)
        with Horizontal(classes='path-row'):
            yield Label('Projects folder')
            yield PathInput(id='root', value=config.projects_root() or config.SUGGESTED_ROOT,
                            placeholder='where new projects are created', accepts_dirs=True)
        with Horizontal(classes='format-row'):
            yield Label('Aspect')
            yield Select(ASPECT_OPTIONS, value='16:9', allow_blank=False, id='aspect')
            yield Label('FPS')
            yield Select(FPS_OPTIONS, value=60, allow_blank=False, id='fps')
            yield Checkbox('UHD (16:9 only)', id='uhd')

    def compose_after_actions(self):
        # below the action rows, ONE row for both (80x24 fit): feedback never pushes the fields around
        with Horizontal(id='feedback-row'):
            yield Static('', id='status', classes='feedback')
            yield Static('', id='error', classes='feedback-error')

    def trailing_action(self):
        # Launched as the app's root (0.5.2)? The last row then leads to Home and is NOT
        # called 'Back' — we did not come from Home. Entered from Home later: plain 'Back'.
        return ('home', 'Continue to main menu') if getattr(self, 'root_entry', False) else ('back', 'Back to main menu')

    def on_mount(self):
        menu = self.query_one('#actions', ActionMenu)
        self._nav_id = 'home' if getattr(self, 'root_entry', False) else 'back'
        # the nav row is not available until a project is saved
        menu.set_enabled(self._nav_id, bool(getattr(self.app, 'project_dir', None)))
        menu.set_enabled('format', False)
        self.refresh_picker()
        self._prefill_from_current_project()
        self._update_format_enabled()

    def refresh_picker(self):
        root = config.projects_root()
        entries = projects_list.list_projects(root) if root else []
        if not root:
            label = 'Projects (no projects folder chosen yet)'
        elif entries:
            label = f'Projects in {root}'
        else:
            label = '(no projects yet — create one below)'
        self.query_one('#projects-label', Label).update(label)
        lv = self.query_one('#projects', ListView)
        lv.clear()
        self._entries = {i: e for i, e in enumerate(entries)}
        lv.display = bool(entries)  # empty picker takes no row (format row must fit 80x24)
        for i, e in enumerate(entries):
            text = e['name'] if not e['error'] else f"{e['name']} — {e['error']}"
            lv.append(ListItem(Label(text, classes='' if not e['error'] else 'muted'), id=f'proj-{i}'))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        i = int(event.item.id.removeprefix('proj-'))
        e = self._entries[i]
        self.query_one('#error', Static).update('')
        if e['error']:
            self.query_one('#error', Static).update(f"error: {e['name']}: {e['error']}")
            return
        self._load_project(e['dir'])

    def on_select_changed(self, event) -> None:
        if self.query('#actions'):
            self._update_format_enabled()

    def _prefill_from_current_project(self):
        p = self._current_project()
        if not p:
            return
        self.query_one('#name', Input).value = p['name']
        self.query_one('#dir', Input).value = getattr(self.app, 'project_dir', '') or ''
        self._fill_format(p)

    def _fill_format(self, p):
        self.query_one('#aspect', Select).value = p['aspect']
        self.query_one('#fps', Select).value = p['fps']
        self.query_one('#uhd', Checkbox).value = p['resolution'] == list(project_mod.UHD)

    def _current_project(self):
        pd = getattr(self.app, 'project_dir', None)
        if not pd:
            return None
        try:
            return project_mod.load(pd)
        except Exception:
            return None

    def _update_format_enabled(self):
        p = self._current_project()
        if not p:
            self.query_one('#actions', ActionMenu).set_enabled('format', False)
            return
        changed = (self.query_one('#aspect', Select).value != p['aspect']
                   or self.query_one('#fps', Select).value != p['fps']
                   or bool(self.query_one('#uhd', Checkbox).value)
                   != (p['resolution'] == list(project_mod.UHD)))
        self.query_one('#actions', ActionMenu).set_enabled('format', changed)

    def _load_project(self, d):
        p = project_mod.load(d)  # raises naming the problem if invalid
        self.app.project_dir = d
        config.set_last_project(d)
        self.query_one('#name', Input).value = p['name']
        self.query_one('#dir', Input).value = d
        self._fill_format(p)
        self.query_one('#actions', ActionMenu).set_enabled(self._nav_id, True)
        self._update_format_enabled()
        self.query_one('#status', Static).update(f'loaded {p["name"]} ({d})')

    def _target_dir(self, name):
        d = self.query_one('#dir', Input).value.strip()
        if d:
            return os.path.abspath(os.path.expanduser(d))
        root = config.projects_root()
        if not root:
            raise ValueError('no projects folder chosen yet — set one below and save it')
        if not name:
            raise ValueError('project name is empty')
        return os.path.join(root, name)

    def _format_values(self):
        """The three format fields, with the UHD-outside-16:9 combination refused loudly
        (set-but-invalid must abort naming it — never silently fall back)."""
        aspect = self.query_one('#aspect', Select).value
        fps = self.query_one('#fps', Select).value
        uhd = self.query_one('#uhd', Checkbox).value
        if uhd and aspect != '16:9':
            raise ValueError(f'UHD is 16:9 only — uncheck UHD or set aspect to 16:9 (got {aspect})')
        return aspect, fps, uhd

    def _apply_format(self):
        pd = self.require_project()
        p = project_mod.load(pd)
        aspect, fps, uhd = self._format_values()  # refuses UHD outside 16:9 loudly
        p['aspect'] = aspect
        p['resolution'] = project_mod.resolution_for(aspect, uhd)
        p['fps'] = fps
        inactive = sum(1 for z in p.get('zones', []) if 'aspect' in z and z['aspect'] != aspect)
        project_mod.save(pd, p)  # validate() frame-checks active zones against the new resolution
        note = f' — {inactive} zone(s) inactive in {aspect}' if inactive else ''
        w, h = p['resolution']
        self.query_one('#status', Static).update(f'format applied: {aspect} {w}x{h} {fps}fps{note}')
        self._update_format_enabled()

    def on_action(self, action_id):
        if action_id == 'home':  # launch screen (0.5.2): the nav row leads to the main menu
            from .app import MenuScreen
            self.app.push_screen(MenuScreen())
            return
        err = self.query_one('#error', Static)
        err.update('')
        status = self.query_one('#status', Static)
        try:
            if action_id == 'root':
                root = config.set_projects_root(self.query_one('#root', Input).value)
                status.update(f'projects folder: {root}')
                self.refresh_picker()
                return
            if action_id == 'format':
                self._apply_format()
                return
            name = self.query_one('#name', Input).value.strip()
            d = self._target_dir(name)
            aspect, fps, uhd = self._format_values()  # BEFORE anything is written
            if not name:
                name = os.path.basename(d)
            if action_id in ('create', 'sample'):
                if os.path.isfile(os.path.join(d, 'project.json')):
                    raise ValueError(f"project '{name}' already exists — select it in the list to load it")
                if action_id == 'sample':
                    shutil.copytree(SAMPLE_DIR, d)  # FLAG F2
                else:
                    os.makedirs(d, exist_ok=True)
                project_mod.save(d, project_mod.default_project(name, aspect=aspect, fps=fps, uhd=uhd))
                self._load_project(d)
                status.update(f'created {name} ({d})')
                self.refresh_picker()
                return
            # load from a directory (possibly outside the root)
            self._load_project(d)
        except (ValueError, FileNotFoundError, OSError) as e:
            err.update(f'error: {e}')
