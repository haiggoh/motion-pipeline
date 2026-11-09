"""MenuApp — the no-code project menu shell (Task 5, design §2 steps 1-4).

Screens: menu (step list), colours (Task 2), fonts (Task 3), zones (§8a), background test,
inputs (transcript/VO), render. Long jobs run via jobs.run_command as workers with progress
in a Log — the menu stays responsive and jobs can be cancelled (G2).
"""
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, Log, Static

from .base import MenuAppBase, SubmenuScreen
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
    ('1. CI colours', 'colours'),
    ('2. Font', 'fonts'),
    ('3. Keep-out zones', 'zones'),
    ('4. Background test', 'bgtest'),
    ('5. Transcript + voiceover', 'inputs'),
    ('6. Render', 'render'),
]


class MenuScreen(SubmenuScreen):
    BINDINGS = [Binding('q', 'quit_app', 'Quit', priority=True)]  # on the main menu, b == q

    def compose_body(self):
        yield Label('motion-pipeline — project menu (pick a step)')
        yield ListView(*[ListItem(Label(t), id=f'step-{k}') for t, k in STEPS])
        yield Static('q quit', id='hint')

    def action_back(self):
        self.app.exit()  # on the main menu, back == quit

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        key = event.item.id.removeprefix('step-')
        self.app.push_screen(self.app.SCREENS[key]())


class BgTestScreen(SubmenuScreen):
    """Background test — runs the SAME render path as the full render (anti-goal)."""

    def compose_body(self):
        from textual.widgets import Input
        with Vertical():
            yield Label('Background test render (same code path as the full render)')
            yield Label('Output directory (drop a folder from Finder to paste its path)')
            yield Input(id='outdir', placeholder='<project>/renders/default')
            yield Button('Run test render', id='run', variant='primary')
            yield Button('Cancel', id='cancel')
            yield Button('Open output in Finder', id='open', disabled=True)
            yield Log(id='log')
            yield Static('', id='status')
            yield Static('', id='link')
            yield Static('', id='image')

    def outdir(self):
        from textual.widgets import Input
        v = self.query_one('#outdir', Input).value.strip()
        return v or None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'run':
            cmd = self.app.test_render_cmd()
            if self.outdir():
                cmd += ['--out', self.outdir()]
            self.worker = run_command(self.app, cmd, self.query_one('#log', Log),
                                      on_finish=self.on_render_done)
            self.query_one('#status', Static).update('running…')
        elif event.button.id == 'cancel' and getattr(self, 'worker', None):
            self.worker.cancel()
            self.query_one('#status', Static).update('cancelled')
        elif event.button.id == 'open' and self.outdir():
            import subprocess
            subprocess.Popen(['open', self.outdir()])

    def on_render_done(self, rc):
        import glob
        import os
        import subprocess
        out = self.outdir() or self.app.default_out()
        self.query_one('#status', Static).update(f'done (exit {rc})')
        self.query_one('#open', Button).disabled = False
        # clickable file:// link (OSC-8 via Text link style; cmd+click opens Finder)
        from rich.text import Text
        self.link_url = f'file://{out}'
        self.query_one('#link', Static).update(Text(f'output: {out}', style=f'link {self.link_url}'))
        # show the rendered test frame inside the terminal (Rich ANSI half-block image)
        masters = sorted(glob.glob(os.path.join(out, 'scene_*.mp4')))
        if masters:
            png = os.path.join(out, '_test_frame.png')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', masters[0],
                            '-frames:v', '1', png], check=False)
            if os.path.isfile(png):
                self.query_one('#image', Static).update(render_ansi_image(png, max_w=160, max_h=90))


class InputsScreen(SubmenuScreen):
    def compose_body(self):
        from textual.widgets import Input
        with Vertical():
            yield Label('Project inputs — tip: drag a file/folder from Finder into a field to paste its path')
            yield Label('Project directory (custom path for the project files)')
            yield Input(id='projectdir', placeholder='projects/<name>')
            yield Label('transcript.txt path')
            yield Input(id='transcript', value='transcript.txt')
            yield Label('voiceover file (optional)')
            yield Input(id='vo', placeholder='audio/vo.wav')
            yield Button('Save inputs', id='save', variant='primary')
            yield Static('', id='status')
            yield Static('', id='error')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != 'save':
            return
        import json
        import os

        from textual.widgets import Input

        from .. import project as project_mod
        from .colours_screen import PROJECTS
        try:
            pj = os.path.join(PROJECTS, 'default', 'project.json')
            p = project_mod.load(os.path.dirname(pj)) if os.path.isfile(pj) else project_mod.default_project('default')
            p['transcript'] = self.query_one('#transcript', Input).value.strip()
            vo = self.query_one('#vo', Input).value.strip()
            p['vo'] = vo or None
            project_mod.save(os.path.join(PROJECTS, 'default'), p)
            self.query_one('#status', Static).update('saved inputs')
        except (ValueError, json.JSONDecodeError) as e:
            self.query_one('#error', Static).update(f'error: {e}')


class RenderScreen(SubmenuScreen):
    def compose_body(self):
        from textual.containers import Vertical
        from textual.widgets import Input
        with Vertical():
            yield Label('Full render (all variants)')
            yield Label('Output directory (drop a folder from Finder to paste its path)')
            yield Input(id='outdir', placeholder='<project>/renders/<variant>')
            yield Button('Render', id='run', variant='primary')
            yield Button('Cancel', id='cancel')
            yield Button('Open output in Finder', id='open', disabled=True)
            yield Log(id='log')
            yield Static('', id='status')
            yield Static('', id='link')

    def outdir(self):
        from textual.widgets import Input
        v = self.query_one('#outdir', Input).value.strip()
        return v or None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'run':
            cmd = self.app.full_render_cmd()
            if self.outdir():
                cmd += ['--out', self.outdir()]
            self.worker = run_command(self.app, cmd, self.query_one('#log', Log),
                                      on_finish=self.on_render_done)
            self.query_one('#status', Static).update('rendering…')
        elif event.button.id == 'cancel' and getattr(self, 'worker', None):
            self.worker.cancel()
            self.query_one('#status', Static).update('cancelled')
        elif event.button.id == 'open' and self.outdir():
            import subprocess
            subprocess.Popen(['open', self.outdir()])

    def on_render_done(self, rc):
        out = self.outdir() or self.app.default_out()
        self.query_one('#status', Static).update(f'done (exit {rc})')
        self.query_one('#open', Button).disabled = False
        from rich.text import Text
        self.link_url = f'file://{out}'
        self.query_one('#link', Static).update(Text(f'output: {out}', style=f'link {self.link_url}'))


class MenuApp(MenuAppBase):
    SCREENS = {}  # filled in on_mount to avoid import cycles

    def __init__(self, test_render_cmd=None, full_render_cmd=None):
        super().__init__()
        self._test_cmd = test_render_cmd or ['bash', '-c', 'echo test-render-placeholder']
        self._full_cmd = full_render_cmd or ['bash', '-c', 'echo full-render-placeholder']

    def test_render_cmd(self):
        return list(self._test_cmd)

    def full_render_cmd(self):
        return list(self._full_cmd)

    def default_out(self):
        return 'renders/default'

    def on_mount(self) -> None:
        from .colours_screen import ColoursScreen
        from .fonts_screen import FontsScreen
        from .zones_screen import ZonesScreen
        self.SCREENS = {'menu': MenuScreen, 'colours': ColoursScreen, 'fonts': FontsScreen,
                        'zones': ZonesScreen, 'bgtest': BgTestScreen, 'inputs': InputsScreen,
                        'render': RenderScreen}
        self.push_screen(MenuScreen())
