"""MenuApp — the no-code project menu shell (Task 5, design §2 steps 1-4).

Screens: menu (step list), colours (Task 2), fonts (Task 3), zones (§8a), background test,
inputs (transcript/VO), render. Long jobs run via jobs.run_command as workers with progress
in a Log — the menu stays responsive and jobs can be cancelled (G2).
"""
import os

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Label, Log, Static

from .base import ActionMenu, MenuAppBase, SubmenuScreen
from .paths import PathInput
from .jobs import run_command



def render_ansi_image(path, max_w=160, max_h=90):
    """Render a PNG as an ANSI half-block image (Textual Static renderable) using PIL+numpy —
    one '▀' cell per 1x2 pixel block, fg = top pixel, bg = bottom pixel."""
    import numpy as np
    from PIL import Image as PILImage
    from rich.text import Text

    img = PILImage.open(path).convert('RGB')
    img.thumbnail((max_w, max_h * 2))  # 2 pixel rows per terminal cell row
    a = np.asarray(img)
    h, w = a.shape[:2]
    rows = h // 2
    out = Text()
    for y in range(rows):
        top = a[y * 2]
        bot = a[y * 2 + 1] if y * 2 + 1 < h else top
        for x in range(w):
            t, b = top[x], bot[x]
            out.append('▀', style=f'#{t[0]:02x}{t[1]:02x}{t[2]:02x} on #{b[0]:02x}{b[1]:02x}{b[2]:02x}')
        if y < rows - 1:
            out.append('\n')
    return out

STEPS = [
    ('project', 'New / load project'),
    ('colours', 'CI colours'),
    ('fonts', 'Font'),
    ('zones', 'Keep-out zones'),
    ('bgtest', 'Background test'),
    ('inputs', 'Transcript + voiceover'),
    ('render', 'Render'),
]


class MenuScreen(Screen):
    """Home menu, csl layout: bold title, cyan subheadline, `N) step` rows with a blank line
    between every row (user 2026-11-09), plain `Quit` last (no Back here), key hint, version."""

    def compose(self):
        from .. import __version__
        with Vertical(classes='panel'):
            yield Static('motion-pipeline — Project Menu', classes='title')
            yield Static(self.subtitle(), classes='subtitle', id='subtitle')
            yield ActionMenu(STEPS + [('quit', 'Quit')], spaced=True, first_number=0, id='actions')
            with Vertical(classes='footer'):
                yield Static('↑↓ move · Enter/click select · 0-6 step · q quit', classes='hint')
                yield Static(f'motion-pipeline v{__version__}', classes='version')

    def subtitle(self):
        from .. import config
        pd = getattr(self.app, 'project_dir', None)
        root = config.projects_root() or '(not chosen)'
        home = os.path.expanduser('~')
        if root.startswith(home):
            root = '~' + root[len(home):]
        name = os.path.basename(pd) if pd else '(none — pick one in step 0)'
        return f'project: {name} · projects folder: {root}'

    def on_screen_resume(self):
        self.query_one('#subtitle', Static).update(self.subtitle())

    def on_action_menu_chosen(self, event):
        if event.action_id == 'quit':
            self.app.exit()
        else:
            self.app.push_screen(self.app.SCREENS[event.action_id]())

    def on_key(self, event):
        menu = self.query_one('#actions', ActionMenu)
        if event.key in menu.numbers:
            self.app.push_screen(self.app.SCREENS[menu.numbers[event.key]]())
            event.stop()


class _RenderScreenBase(SubmenuScreen):
    """Shared by the background test and the full render: output dir field, actions
    (run / cancel / open in Finder), then — BELOW the actions — the log, status, link, image."""

    ACTIONS = [('run', 'Run'), ('cancel', 'Cancel'), ('open', 'Open output in Finder')]
    OUT_PLACEHOLDER = '<project>/renders/default'

    def compose_body(self):
        from textual.widgets import Input
        yield Label('Output directory (drop a folder from Finder to paste its path)')
        yield PathInput(id='outdir', placeholder=self.OUT_PLACEHOLDER)

    def compose_after_actions(self):
        yield Static('', id='status')
        yield Static('', id='link')
        yield Log(id='log')
        yield Static('', id='image')

    def on_mount(self):
        self.query_one('#actions', ActionMenu).set_enabled('open', False)

    def outdir(self):
        from textual.widgets import Input
        v = self.query_one('#outdir', Input).value.strip()
        return v or None

    def command(self):
        raise NotImplementedError

    def on_action(self, action_id):
        if action_id == 'run':
            cmd = self.command()
            if self.outdir():
                cmd += ['--out', self.outdir()]
            self.worker = run_command(self.app, cmd, self.query_one('#log', Log),
                                      on_finish=self.on_render_done)
            self.query_one('#status', Static).update('running…')
        elif action_id == 'cancel' and getattr(self, 'worker', None):
            self.worker.cancel()
            self.query_one('#status', Static).update('cancelled')
        elif action_id == 'open':
            import subprocess
            subprocess.Popen(['open', self.outdir() or self.app.default_out()])

    def on_render_done(self, rc):
        out = self.outdir() or self.app.default_out()
        self.query_one('#status', Static).update(f'done (exit {rc})')
        self.query_one('#actions', ActionMenu).set_enabled('open', True)
        from rich.text import Text
        self.link_url = f'file://{out}'
        self.query_one('#link', Static).update(Text(f'output: {out}', style=f'link {self.link_url}'))


class BgTestScreen(_RenderScreenBase):
    """Background test — runs the SAME render path as the full render (anti-goal)."""

    TITLE = 'Background test render (same code path as the full render)'
    ACTIONS = [('run', 'Run test render'), ('cancel', 'Cancel'), ('open', 'Open output in Finder')]

    def command(self):
        return self.app.test_render_cmd()

    def on_render_done(self, rc):
        import glob
        import subprocess
        super().on_render_done(rc)
        out = self.outdir() or self.app.default_out()
        # show the rendered test frame inside the terminal (Rich ANSI half-block image)
        masters = sorted(glob.glob(os.path.join(out, 'scene_*.mp4')))
        if masters:
            png = os.path.join(out, '_test_frame.png')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', masters[0],
                            '-frames:v', '1', png], check=False)
            if os.path.isfile(png):
                self.query_one('#image', Static).update(render_ansi_image(png, max_w=160, max_h=90))


class InputsScreen(SubmenuScreen):
    TITLE = 'Transcript + voiceover'
    ACTIONS = [('save', 'Save inputs')]

    def compose_body(self):
        from textual.widgets import Input
        yield Label('Tip: drag a file/folder from Finder into a field to paste its path')
        yield Label('transcript.txt path')
        yield PathInput(id='transcript', value='transcript.txt')
        yield Label('voiceover file (optional)')
        yield PathInput(id='vo', placeholder='audio/vo.wav')
        yield Static('', id='status')
        yield Static('', id='error')

    def on_action(self, action_id):
        if action_id != 'save':
            return
        import json

        from textual.widgets import Input

        from .. import project as project_mod
        try:
            pd = self.require_project()
            pj = os.path.join(pd, 'project.json')
            p = project_mod.load(pd) if os.path.isfile(pj) else project_mod.default_project(os.path.basename(pd))
            p['transcript'] = self.query_one('#transcript', Input).value.strip()
            vo = self.query_one('#vo', Input).value.strip()
            p['vo'] = vo or None
            project_mod.save(pd, p)
            self.query_one('#status', Static).update(f'saved inputs to {pj}')
        except (ValueError, json.JSONDecodeError) as e:
            self.query_one('#error', Static).update(f'error: {e}')


class RenderScreen(_RenderScreenBase):
    TITLE = 'Full render (all variants)'
    ACTIONS = [('run', 'Render'), ('cancel', 'Cancel'), ('open', 'Open output in Finder')]
    OUT_PLACEHOLDER = '<project>/renders/<variant>'

    def command(self):
        return self.app.full_render_cmd()


class FirstRunScreen(Screen):
    """Asked once: where projects live (remembered in ~/.config/motion-pipeline). Never inside
    the installed package — Homebrew replaces it on every upgrade."""

    def compose(self):
        from textual.widgets import Input

        from .. import config
        with Vertical(classes='panel'):
            yield Static('motion-pipeline — where should your projects live?', classes='title')
            yield Static('Chosen once and remembered; change it later in step 0. '
                         'Drop a folder from Finder to paste its path.', classes='subtitle')
            yield PathInput(id='root', value=config.projects_root() or config.SUGGESTED_ROOT)
            yield ActionMenu([('save', 'Use this folder'), ('quit', 'Quit')], id='actions')
            yield Static('', id='error')
            yield Static('↑↓ move · Enter/click select · q quit', classes='hint')

    def on_action_menu_chosen(self, event):
        from textual.widgets import Input

        from .. import config
        if event.action_id == 'quit':
            self.app.exit()
            return
        try:
            config.set_projects_root(self.query_one('#root', Input).value)
        except (ValueError, OSError) as e:
            self.query_one('#error', Static).update(f'error: {e}')
            return
        if len(self.app.screen_stack) > 2:
            self.app.pop_screen()
        else:
            self.app.switch_screen(MenuScreen())


class MenuApp(MenuAppBase):
    SCREENS = {}  # filled in on_mount to avoid import cycles

    def __init__(self, test_render_cmd=None, full_render_cmd=None):
        super().__init__()
        self._test_cmd = test_render_cmd
        self._full_cmd = full_render_cmd
        self.project_dir = None

    def _cli(self, mode):
        import sys
        if not self.project_dir:
            return ['bash', '-c', 'echo "no project open — create or load one in step 0 first" >&2; exit 2']
        return [sys.executable, '-m', 'motion_pipeline.render_cli', '--project', self.project_dir,
                '--mode', mode]

    def test_render_cmd(self):
        return list(self._test_cmd) if self._test_cmd else self._cli('test')

    def full_render_cmd(self):
        return list(self._full_cmd) if self._full_cmd else self._cli('full')

    def default_out(self):
        return os.path.join(self.project_dir or '.', 'renders', 'default')

    def on_mount(self) -> None:
        from .. import config
        from .colours_screen import ColoursScreen
        from .fonts_screen import FontsScreen
        from .project_screen import ProjectScreen
        from .zones_screen import ZonesScreen
        self.SCREENS = {'menu': MenuScreen, 'project': ProjectScreen, 'colours': ColoursScreen,
                        'fonts': FontsScreen, 'zones': ZonesScreen, 'bgtest': BgTestScreen,
                        'inputs': InputsScreen, 'render': RenderScreen}
        if self.project_dir is None:
            self.project_dir = config.last_project()
        if config.projects_root() is None:
            self.push_screen(FirstRunScreen())
        else:
            self.push_screen(MenuScreen())
