"""ProjectScreen — step 0: create or load the project everything else reads and writes,
change the remembered projects folder, and set the video format (aspect / fps / UHD) in
the same create/load step (no separate action). app.project_dir is always the CURRENT
project folder.
"""
import os

from textual.containers import Horizontal
from textual.widgets import Checkbox, Input, Label, Select, Static

from .. import config
from .. import project as project_mod
from .base import ActionMenu, SubmenuScreen
from .paths import PathInput

# display order per the README's format list; values must exist in project.ASPECTS
ASPECT_OPTIONS = [(a, a) for a in ('16:9', '9:16', '1:1', '4:5')]
FPS_OPTIONS = [(str(f), f) for f in project_mod.FPS_CHOICES]


class ProjectScreen(SubmenuScreen):
    TITLE = 'New / load project'
    ACTIONS = [('create', 'Create new project'), ('load', 'Load existing project'),
               ('root', 'Save projects folder')]

    def compose_body(self):
        with Horizontal(classes='path-row'):
            yield Label('Name')
            yield Input(id='name', placeholder='my-project')
        with Horizontal(classes='path-row'):
            yield Label('Directory (drop a folder from Finder)')
            yield PathInput(id='dir', placeholder='optional — <projects folder>/<name>')
        with Horizontal(classes='path-row'):
            yield Label('Projects folder')
            yield PathInput(id='root', value=config.projects_root() or config.SUGGESTED_ROOT,
                            placeholder='where new projects are created')
        with Horizontal(classes='format-row'):
            yield Label('Aspect')
            yield Select(ASPECT_OPTIONS, value='16:9', allow_blank=False, id='aspect')
            yield Label('FPS')
            yield Select(FPS_OPTIONS, value=60, allow_blank=False, id='fps')
            yield Checkbox('UHD (16:9 only)', id='uhd')

    def compose_after_actions(self):
        # below the action rows (see _RenderScreenBase): feedback never pushes the fields around
        yield Static('', id='status')
        yield Static('', id='error')

    def trailing_action(self):
        # Launched as the app's root (0.5.2)? The last row then leads to Home and is NOT
        # called 'Back' — we did not come from Home. Entered from Home later: plain 'Back'.
        return ('home', 'Home') if getattr(self, 'root_entry', False) else ('back', 'Back')

    def on_mount(self):
        menu = self.query_one('#actions', ActionMenu)
        self._nav_id = 'home' if getattr(self, 'root_entry', False) else 'back'
        # the nav row is not available until a project is saved — create/load set the
        # format in the SAME step, there is no separate 'Save format' action (0.5.2)
        menu.set_enabled(self._nav_id, bool(getattr(self.app, 'project_dir', None)))

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
                return
            name = self.query_one('#name', Input).value.strip()
            d = self._target_dir(name)
            if action_id == 'create':
                aspect, fps, uhd = self._format_values()  # BEFORE anything is written
                if not name:
                    name = os.path.basename(d)
                os.makedirs(d, exist_ok=True)
                if not os.path.isfile(os.path.join(d, 'project.json')):
                    project_mod.save(d, project_mod.default_project(name, aspect=aspect,
                                                                    fps=fps, uhd=uhd))
                verb = 'created'
            else:
                p = project_mod.load(d)  # raises naming the problem if invalid
                name = p['name']
                self.query_one('#aspect', Select).value = p['aspect']
                self.query_one('#fps', Select).value = p['fps']
                self.query_one('#uhd', Checkbox).value = p['resolution'] == list(project_mod.UHD)
                verb = 'loaded'
            self.app.project_dir = d
            config.set_last_project(d)
            status.update(f'{verb} {name} ({d})')
            # project saved (format set in the same step) -> the nav row becomes available
            self.query_one('#actions', ActionMenu).set_enabled(self._nav_id, True)
        except (ValueError, FileNotFoundError, OSError) as e:
            err.update(f'error: {e}')
