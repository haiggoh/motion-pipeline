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
from .paths import PathInput, TRANSCRIPT_EXTS, VO_EXTS
from .jobs import run_command



from .ansi_image import render_ansi_image  # noqa: F401  (moved in Task 10; re-exported for existing imports)

STEPS = [
    ('project', 'New / load project'),
    ('colours', 'CI colours'),
    ('fonts', 'Font'),
    ('zones', 'Keep-out zones'),
    ('bgtest', 'Background test'),
    ('inputs', 'Transcript + voiceover'),
    ('textstyle', 'Text animation'),        # 0.8.0 Task 4 / Q1 — L0 base text style
    ('graphics', 'Add motion graphics'),   # Task 23 / M5 — gated on fresh saved timings
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
            menu = ActionMenu(STEPS + [('quit', 'Quit')], spaced=True, first_number=0, nav_gap=0, id='actions')  # Quit is not a nav row
            yield menu
            with Vertical(classes='footer'):
                yield Static('↑↓ move · Enter/click select · 0-8 step · q quit', classes='hint')
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

    GRAPHICS_LABEL = 'Add motion graphics'
    GRAPHICS_LABEL_GATED = 'Add motion graphics — needs saved timings (step 5)'

    def on_mount(self):
        self.refresh_gates()

    def on_screen_resume(self):
        self.query_one('#subtitle', Static).update(self.subtitle())
        self.refresh_gates()   # Task 5 (A5c): re-evaluate when returning from a submenu

    def refresh_gates(self):
        """Enable/disable the graphics step and swap its label to say WHY when disabled."""
        menu = self.query_one('#actions', ActionMenu)
        ok = self.app.graphics_step_enabled()
        menu.set_enabled('graphics', ok)
        num = next((k for k, v in menu.numbers.items() if v == 'graphics'), '?')
        menu.replace_option_prompt(
            'graphics', f'{num}) {self.GRAPHICS_LABEL if ok else self.GRAPHICS_LABEL_GATED}')

    def on_action_menu_chosen(self, event):
        if event.action_id == 'quit':
            self.app.exit()
        else:
            self.app.push_screen(self.app.SCREENS[event.action_id]())

    def on_key(self, event):
        menu = self.query_one('#actions', ActionMenu)
        if event.key in menu.numbers:
            aid = menu.numbers[event.key]
            if not menu.get_option(aid).disabled:
                self.app.push_screen(self.app.SCREENS[aid]())
            event.stop()


class _RenderScreenBase(SubmenuScreen):
    """Shared by the background test and the full render: output dir field, actions
    (run / cancel / open in Finder), then — BELOW the actions — the log, status, link, image."""

    ACTIONS = [('run', 'Run'), ('cancel', 'Cancel'), ('open', 'Open output in Finder'),
               ('setup', 'Install render toolchain')]
    OUT_PLACEHOLDER = '<project>/renders/default'

    def compose_body(self):
        from textual.widgets import Checkbox
        yield Label('Output directory (drop a folder from Finder to paste its path)')
        yield PathInput(id='outdir', placeholder=self.OUT_PLACEHOLDER, accepts_dirs=True)
        yield Checkbox('Also write one joined full-length master (doubles the disk space of the masters)',
                       id='full-master')  # D2: opt-in, persisted per project

    def compose_after_actions(self):
        from textual.widgets import RichLog
        yield Static('', id='status', classes='feedback')
        yield Static('', id='link')
        yield Static('', id='image')
        yield RichLog(id='log', wrap=True, markup=False, classes='joblog', min_width=0)

    def on_mount(self):
        menu = self.query_one('#actions', ActionMenu)
        menu.set_enabled('open', False)
        menu.set_enabled('cancel', False)
        menu.set_enabled('setup', False)  # enabled when the log reports a missing toolchain
        self.worker = None
        self._job_running = False
        self.set_interval(0.5, self._update_setup_row)  # Task 14: watch the streaming log
        # Task 15: prefill the joined-master opt-in from the project
        pd = getattr(self.app, 'project_dir', None)
        if pd:
            try:
                from textual.widgets import Checkbox
                from .. import project as project_mod
                self.query_one('#full-master', Checkbox).value = \
                    bool(project_mod.load(pd).get('full_master', False))
            except Exception:
                pass

    def outdir(self):
        from textual.widgets import Input
        v = self.query_one('#outdir', Input).value.strip()
        return v or None

    def command(self):
        raise NotImplementedError

    def open_target(self):
        return self.outdir() or self.app.default_out()

    def on_action(self, action_id):
        from textual.widgets import RichLog
        menu = self.query_one('#actions', ActionMenu)
        if action_id == 'run':
            if self._job_running:
                return  # one job at a time
            from textual.widgets import Checkbox
            from .. import project as project_mod
            pd = self.require_project()
            if os.path.isfile(os.path.join(pd, 'project.json')):
                p = project_mod.load(pd)
                p['full_master'] = bool(self.query_one('#full-master', Checkbox).value)  # D2 persist
                project_mod.save(pd, p)
            cmd = self.command()
            if self.outdir():
                cmd += ['--out', self.outdir()]
            self._job_running = True
            menu.set_enabled('run', False)
            menu.set_enabled('cancel', True)
            self.worker = run_command(self.app, cmd, self.query_one('#log', RichLog),
                                      on_finish=self.on_render_done)
            self.query_one('#status', Static).update('running…')
        elif action_id == 'cancel':
            if self._job_running and getattr(self, 'worker', None):
                self.worker.cancel()
                self._job_running = False
                menu.set_enabled('run', True)
                menu.set_enabled('cancel', False)
                self.query_one('#status', Static).update('cancelled')
        elif action_id == 'open':
            import subprocess
            subprocess.Popen(['open', self.open_target()])
        elif action_id == 'remux':
            if self._job_running:
                return
            import sys
            pd = self.require_project()
            self._job_running = True
            menu.set_enabled('run', False)
            menu.set_enabled('cancel', True)
            self.worker = run_command(self.app, [sys.executable, '-P', '-m',
                                                 'motion_pipeline.render_cli', '--project', pd,
                                                 '--mode', 'remux'],
                                      self.query_one('#log', RichLog), on_finish=self.on_render_done)
            self.query_one('#status', Static).update('re-muxing audio…')
        elif action_id == 'setup':
            if self._job_running:
                return
            import sys
            self._job_running = True
            menu.set_enabled('run', False)
            menu.set_enabled('cancel', True)
            self.worker = run_command(self.app, [sys.executable, '-P', '-m',
                                                 'motion_pipeline.render_cli', '--setup'],
                                      self.query_one('#log', RichLog),
                                      on_finish=self._on_setup_done)
            self.query_one('#status', Static).update('installing render toolchain…')

    def _update_setup_row(self):
        """Enable 'Install render toolchain' when the last log line reports a missing dep."""
        from textual.widgets import RichLog
        if not self.query('#actions'):
            return
        log = self.query_one('#log', RichLog)
        lines = [x.text if hasattr(x, 'text') else str(x) for x in log.lines]
        # the newest 'missing dependency:' line decides (the final 'failed (exit N)' follows it)
        missing = any(line.startswith(('missing dependency: hyperframes', 'missing dependency: node'))
                      for line in reversed(lines))
        self.query_one('#actions', ActionMenu).set_enabled('setup', missing)

    def _on_setup_done(self, rc):
        if not self.query('#actions'):
            return                     # job-done on a removed screen (B2)
        from textual.widgets import RichLog   # B1: was used unimported in this method (ruff F821)
        self._job_running = False
        menu = self.query_one('#actions', ActionMenu)
        menu.set_enabled('run', True)
        menu.set_enabled('cancel', False)
        if rc != 0:
            self.query_one('#status', Static).update(f'setup failed (exit {rc}) — see the log below')
            return
        import sys
        self.worker = run_command(self.app, [sys.executable, '-P', '-m',
                                             'motion_pipeline.render_cli', '--check'],
                                  self.query_one('#log', RichLog),
                                  on_finish=self._on_check_done)

    def _on_check_done(self, rc):
        if not self.query('#actions'):
            return                     # job-done on a removed screen (B2)
        self._job_running = False
        menu = self.query_one('#actions', ActionMenu)
        menu.set_enabled('cancel', False)
        if rc == 0:
            self.query_one('#status', Static).update('toolchain ready — run the test render again')
        else:
            self.query_one('#status', Static).update(f'check still failing (exit {rc}) — see the log below')
        self._update_setup_row()

    def on_render_done(self, rc):
        from textual.widgets import RichLog
        if not self.query('#actions'):
            return                     # job-done on a removed screen (B2)
        self._job_running = False
        menu = self.query_one('#actions', ActionMenu)
        menu.set_enabled('run', True)
        menu.set_enabled('cancel', False)
        out = self.open_target()
        if rc != 0:
            # name WHY, from the log (render_cli prints 'missing dependency: …' / 'error: …')
            lines = [x.text if hasattr(x, 'text') else str(x) for x in self.query_one('#log', RichLog).lines]
            why = next((x for x in reversed(lines)
                        if x.startswith(('missing dependency', 'error', 'disk guard', 'no '))), '')
            self.query_one('#status', Static).update(
                f'failed (exit {rc})' + (f' — {why}' if why else '') + ' — see the log below')
            return
        self.query_one('#status', Static).update(f'done (exit {rc})')
        self.query_one('#actions', ActionMenu).set_enabled('open', True)
        from rich.text import Text
        self.link_url = f'file://{out}'
        self.query_one('#link', Static).update(Text(f'output: {out}', style=f'link {self.link_url}'))


class BgTestScreen(_RenderScreenBase):
    """Background test — runs the SAME render path as the full render (anti-goal)."""

    TITLE = 'Background test render (same code path as the full render)'
    ACTIONS = [('run', 'Run test render'), ('cancel', 'Cancel'), ('open', 'Open output in Finder'),
               ('setup', 'Install render toolchain')]

    def command(self):
        return self.app.test_render_cmd()

    def on_render_done(self, rc):
        import glob
        import subprocess
        if not self.query('#image'):
            return                     # job-done on a removed screen (B2)
        super().on_render_done(rc)
        out = self.outdir() or self.app.default_out()
        # show the rendered test frame inside the terminal (Rich ANSI half-block image)
        # Task 15: masters are .mov — the old .mp4-only glob went stale; fixtures may use .mp4
        masters = sorted(glob.glob(os.path.join(out, 'scene_*.mov'))
                         + glob.glob(os.path.join(out, 'scene_*.mp4')))
        if masters:
            png = os.path.join(out, '_test_frame.png')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', masters[0],
                            '-frames:v', '1', png], check=False)
            if os.path.isfile(png):
                img = self.query_one('#image', Static)
                # fit the space left below the actions (half-block = 2 pixel rows per cell)
                w, h = self.app.size
                top = self.query_one('#link', Static).region.bottom + 1
                rows = max(5, h - top - 2)
                img.update(render_ansi_image(png, max_w=max(20, w - 4), max_h=rows))


class _ProgressLog:
    """Wraps the timings RichLog for jobs.run_command: every line is logged AND parsed for
    'progress: <done>/<total> <stage>' (Task 17), advancing the ProgressBar and stage label.
    run_command calls write() via call_from_thread, so this runs on the UI thread — safe."""

    def __init__(self, log, bar, stage_label):
        self._log = log
        self._bar = bar
        self._stage = stage_label
        self.last_named = None      # last 'missing dependency:'/'error:' line seen

    def write(self, line):
        self._log.write(line)
        from .. import render_cli
        if line.startswith(('missing dependency:', 'error:')):
            self.last_named = line
        parsed = render_cli.parse_progress(line)
        if parsed:
            done, total, stage = parsed
            if total:
                self._bar.update(total=100, progress=round(done / total * 100))
            self._stage.update(stage)


class InputsScreen(SubmenuScreen):
    TITLE = 'Transcript + voiceover'
    ACTIONS = [('save', 'Save inputs + compute timings'),
               ('retry-model', 'Retry speech model download')]   # Task 18 (B4): model installs itself
    CSS = '#actions { margin: 0; }'  # fit 80x24 with the engine-status line (Task 17)
    CSS += '#timing-log { display: none; height: 3; min-height: 1; }'  # shown when a timings job starts; 80x24 layout test decides
    CSS += '#timing-spinner, #timing-progress, #timing-stage { display: none; }'  # shown only while the job runs

    def compose_body(self):
        from textual.containers import Horizontal
        from textual.widgets import Input, Select
        yield Label('Transcript path — .txt/.md/.rtf/.doc/.docx/.pdf (drag a file from Finder; '
                    'docx maps real headings, rtf/doc load as plain text via textutil)')
        yield PathInput(id='transcript', value='transcript.txt', accepts=TRANSCRIPT_EXTS)
        yield Label('voiceover file — ' + ' '.join(VO_EXTS) + ' (or .mov/.mp4 video)')
        yield PathInput(id='vo', placeholder='audio/vo.wav', accepts=VO_EXTS)
        with Horizontal(classes='path-row'):
            yield Label('wpm')
            yield Input(id='wpm', placeholder='140')
            yield Label('language')
            yield Select([('Deutsch', 'de'), ('English', 'en'), ('Auto-detect', 'auto')],
                         id='language', allow_blank=False)
            yield Label('aligner')
            yield Select([('Whisper (falls back to estimate when not installed)', 'auto'),
                         ('Estimate only (no speech model)', 'classical'),
                         ('Whisper (required)', 'whisper')], id='aligner', allow_blank=False)
        yield Static('', id='status', classes='feedback')
        yield Static('', id='error', classes='feedback-error')
        yield Static('', id='engine-status', classes='muted')  # Task 17: speech-model engine line
        from textual.widgets import LoadingIndicator, ProgressBar, RichLog
        # Task 17 (B4): while the timings job runs, spinner + progress bar sit WHERE the log
        # will appear (never a bottom row); the log itself shows the result on finish
        yield LoadingIndicator(id='timing-spinner')
        yield ProgressBar(id='timing-progress', total=100)
        yield Static('', id='timing-stage', classes='muted')
        yield RichLog(id='timing-log', wrap=True, markup=False, classes='joblog', max_lines=200)

    def on_mount(self):
        import json

        from textual.widgets import Input, Select

        from .. import project as project_mod
        self._update_engine_status()
        self._load_error = None
        pd = getattr(self.app, 'project_dir', None)
        if not pd:
            return
        pj = os.path.join(pd, 'project.json')
        if not os.path.isfile(pj):
            return   # no project yet — not an error (keeps the 80x24 layout intact)
        try:
            p = project_mod.load(pd)
        except (ValueError, OSError, json.JSONDecodeError) as e:
            # Task 6 (X2): name the corrupt project.json — never show defaults as real state
            self._load_error = f'project.json: {e}'
            self.query_one('#error', Static).update(f'error: {self._load_error}')
            return
        # prefill EVERY field from the saved project — an empty vo field here is what cleared
        # the saved voiceover on a transcript-only save (data-loss bug)
        self.query_one('#transcript', Input).value = p.get('transcript') or 'transcript.txt'
        self.query_one('#vo', Input).value = p.get('vo') or ''
        self.query_one('#wpm', Input).value = str(p.get('wpm', 140))
        self.query_one('#language', Select).value = p.get('language', 'auto')   # B4: auto default
        self.query_one('#aligner', Select).value = p.get('aligner', 'auto')
        self._sync_wpm_field()
        self._update_wpm_indicator()

    def _project_wpm(self):
        pd = getattr(self.app, 'project_dir', None)
        if not pd or not os.path.isfile(os.path.join(pd, 'project.json')):
            return None
        try:
            from .. import project as project_mod
            return project_mod.load(pd).get('wpm')
        except (ValueError, OSError):
            return None

    def _sync_wpm_field(self):
        """B4: with a voiceover set, the wpm Input is replaced in place by a muted indicator
        (the VO's measured rate); without a VO it stays the editable Input."""
        from textual.widgets import Input, Static
        vo = self.query_one('#vo', Input).value.strip()
        has_input = bool(self.query('#wpm'))
        has_ind = bool(self.query('#wpm-indicator'))
        if vo and has_input and not has_ind:
            inp = self.query_one('#wpm', Input)
            ind = Static('— wpm (computed with timings)', id='wpm-indicator', classes='muted')
            inp.parent.mount(ind, before=inp)
            inp.remove()
        elif not vo and has_ind and not has_input:
            ind = self.query_one('#wpm-indicator', Static)
            # review finding: keep the saved wpm in the restored field (never wipe it)
            last = str(getattr(self, '_last_wpm', None) or self._project_wpm() or 140)
            inp = Input(id='wpm', value=last, placeholder='140')
            ind.parent.mount(inp, before=ind)
            ind.remove()

    def _update_wpm_indicator(self):
        """Once a measured timing exists, the indicator shows 'measured N wpm'."""
        import json
        from textual.widgets import Static
        if not self.query('#wpm-indicator'):   # also guards unmounted screens
            return
        pd = getattr(self.app, 'project_dir', None)
        if not pd:
            return
        try:
            timing = json.load(open(os.path.join(pd, 'timing.json')))
        except (OSError, ValueError):
            return
        from .. import align
        wpm = align.measured_wpm(timing)
        if wpm is not None:
            self.query_one('#wpm-indicator', Static).update(f'measured {wpm} wpm')

    def on_input_changed(self, event) -> None:
        if event.input.id == 'vo':
            self._sync_wpm_field()
            self._update_wpm_indicator()

    def _on_timing_done(self, rc: int) -> None:
        # user-reported crash (2026-11-21): the job can finish after the user left this screen
        # (e.g. entering step 6 mid-job) — then the widgets are gone from the DOM and
        # query_one raises NoMatches. Guard on DOM presence, not is_mounted (stays True).
        if not self.query('#timing-spinner'):
            return
        # Task 17: job finished — hide spinner/bar, show the log with the result
        from textual.widgets import LoadingIndicator, ProgressBar, RichLog
        self.query_one('#timing-spinner', LoadingIndicator).display = False
        self.query_one('#timing-progress', ProgressBar).display = False
        self.query_one('#timing-stage', Static).display = False
        self.query_one('#timing-log', RichLog).display = True
        """Task 5 (A5): the prepare-only job is observed via run_command's on_finish (called
        on the UI thread). rc 0 -> report the saved counts; else surface the named error
        line from the job log (e.g. 'missing dependency: transcript …')."""
        import json as _json
        from textual.widgets import RichLog
        pd = getattr(self.app, 'project_dir', None)
        if rc == 0 and pd:
            try:
                timing = _json.load(open(os.path.join(pd, 'timing.json')))
                model = _json.load(open(os.path.join(pd, 'transcript_model.json')))
                self.query_one('#status', Static).update(
                    f'timings saved — {len(model["words"])} words, {len(model["sections"])} sections, '
                    f'engine {timing["method"]}')
                self.query_one('#error', Static).update('')
                self._update_wpm_indicator()
                return
            except Exception as e:
                self.query_one('#error', Static).update(f'error: {e}')
                self.query_one('#status', Static).update('')
                return
        # the wrapper captured the named line (log lines can land after on_finish)
        named = getattr(self, '_timing_log_wrap', None)
        msg = named.last_named if named and named.last_named else f'failed (exit {rc})'
        self.query_one('#error', Static).update(msg)
        self.query_one('#status', Static).update('')

    def _update_engine_status(self):
        """Task 18 (B4): the engine line shows the app's live model_state (self-install)."""
        if not self.query('#engine-status'):
            return
        self.query_one('#engine-status', Static).update(self.app._engine_line())
        menu = self.query_one('#actions')
        menu.set_enabled('retry-model', self.app.model_state.startswith('failed:'))

    def on_action(self, action_id):
        if action_id == 'retry-model':
            # Task 18 (B4): retry the failed self-install
            from .. import align_whisper
            self.app.model_state = 'downloading 0%'
            self._update_engine_status()
            mdir = os.environ.get('MP_MODELS_DIR') or os.path.join(
                os.path.expanduser('~'), '.cache', 'motion-pipeline', 'models')

            def _dl():
                try:
                    align_whisper.ensure_model(
                        mdir,
                        progress=lambda d, t: self.app.call_from_thread(
                            self.app._set_model_state, f'downloading {round(d / max(t, 1) * 100)}%'))
                    self.app.call_from_thread(self.app._set_model_state, 'ready')
                except Exception as e:
                    self.app.call_from_thread(self.app._set_model_state, f'failed: {e}')

            self.run_worker(_dl, thread=True, exclusive=True, name='model-download')
            return
        if action_id != 'save':
            return
        import json

        from textual.widgets import Input, Select

        from .. import project as project_mod
        try:
            pd = self.require_project()
            if getattr(self, '_load_error', None):
                # Task 6 (X2): refuse to save over a project.json we could not read
                raise ValueError(self._load_error)
            pj = os.path.join(pd, 'project.json')
            p = project_mod.load(pd) if os.path.isfile(pj) else project_mod.default_project(os.path.basename(pd))
            p['transcript'] = self.query_one('#transcript', Input).value.strip()
            p['vo'] = self.query_one('#vo', Input).value.strip() or None
            if not p['vo']:
                raw_wpm = self.query_one('#wpm', Input).value.strip()
                # B4: with a VO the wpm is measured, not read; an emptied field keeps the saved value
                p['wpm'] = int(raw_wpm) if raw_wpm else p.get('wpm', 140)
            p['language'] = self.query_one('#language', Select).value
            p['aligner'] = self.query_one('#aligner', Select).value
            project_mod.save(pd, p)
            # Task 5 (A5): compute timings in a job (prepare-only) via jobs.run_command so the
            # output streams into #timing-log and the exit code is OBSERVED (on_finish) — the
            # graphics step gates on the result
            from textual.widgets import LoadingIndicator, ProgressBar, RichLog
            log = self.query_one('#timing-log', RichLog)
            spinner = self.query_one('#timing-spinner', LoadingIndicator)
            bar = self.query_one('#timing-progress', ProgressBar)
            stage = self.query_one('#timing-stage', Static)
            spinner.display = True       # spinner + bar replace the log area while the job runs
            bar.display = True
            stage.display = True
            bar.update(total=100, progress=0)
            stage.update('starting…')
            self._timing_log_wrap = _ProgressLog(log, bar, stage)
            self._timing_job = run_command(
                self.app,
                self.app.prepare_cmd(pd),
                self._timing_log_wrap,
                on_finish=self._on_timing_done)
            self.query_one('#status', Static).update('saving inputs… computing timings…')
        except (ValueError, json.JSONDecodeError) as e:
            self.query_one('#error', Static).update(f'error: {e}')


class RenderScreen(_RenderScreenBase):
    TITLE = 'Full render (all variants)'
    ACTIONS = [('run', 'Render'), ('cancel', 'Cancel'), ('open', 'Open output in Finder'),
               ('setup', 'Install render toolchain'), ('remux', 'Re-mux audio (no re-render)')]
    OUT_PLACEHOLDER = '<project>/renders/<variant>'

    def command(self):
        return self.app.full_render_cmd()

    def open_target(self):
        """Multiple variants render into <project>/renders/<variant>/ — open the renders ROOT;
        a single variant opens its own folder."""
        if self.outdir():
            return self.outdir()
        pd = self.app.project_dir
        try:
            from .. import project as project_mod
            variants = project_mod.load(pd)['variants']
        except Exception:
            variants = ['default']
        renders = os.path.join(pd, 'renders')
        if len(variants) > 1:
            return renders
        return os.path.join(renders, variants[0] if variants else 'default')


class FirstRunScreen(SubmenuScreen):
    """Asked once: where projects live (remembered in ~/.config/motion-pipeline). Never inside
    the installed package — Homebrew replaces it on every upgrade."""

    def compose(self):
        from textual.widgets import Input

        from .. import config
        with Vertical(classes='panel'):
            yield Static('motion-pipeline — where should your projects live?', classes='title')
            yield Static('Chosen once and remembered; change it later in step 0. '
                         'Drop a folder from Finder to paste its path.', classes='subtitle')
            yield PathInput(id='root', value=config.projects_root() or config.SUGGESTED_ROOT,
                            accepts_dirs=True)
            yield ActionMenu([('save', 'Use this folder'), ('quit', 'Quit')], id='actions')
            yield Static('', id='error', classes='feedback-error')
            yield Static('↑↓ move · Enter/click select · q quit', classes='hint')

    def on_paste(self, event):
        # same drop routing as every submenu (spec A2): a Finder drop on a non-input widget
        # (e.g. the action list) lands in #root
        from textual.widgets import Input

        from .base import route_drop
        if isinstance(self.focused, Input):
            return
        target = route_drop(self, event.text)
        if target is None:
            return
        event.stop()
        target.focus()
        target.post_message(type(event)(event.text))

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
            scr = self.app.SCREENS['project']()  # land in step 0, not Home (0.5.2)
            scr.root_entry = True
            self.app.switch_screen(scr)


class MenuApp(MenuAppBase):
    SCREENS = {}  # filled in on_mount to avoid import cycles

    def graphics_step_enabled(self):
        """Task 21 gate: the 'Add motion graphics' step needs fresh saved timings."""
        pd = getattr(self, 'project_dir', None)
        if not pd:
            return False
        from .. import align
        from .. import project as pm
        try:
            return align.timing_is_fresh(pd, pm.load(pd))
        except Exception:
            return False

    def __init__(self, test_render_cmd=None, full_render_cmd=None, test_prepare_cmd=None):
        super().__init__()
        self._test_cmd = test_render_cmd
        self._full_cmd = full_render_cmd
        self._prepare_cmd = test_prepare_cmd
        self.project_dir = None
        self.model_state = 'ready'   # 'ready' | 'downloading <pct>%' | 'failed: <msg>' | 'no whisper-cli'

    def _set_model_state(self, state):
        self.model_state = state
        for scr in self.screen_stack:
            if scr.query('#engine-status'):
                scr.query_one('#engine-status', Static).update(self._engine_line())
            menus = scr.query('#actions')
            if menus:
                menu = menus.first()
                if any(o.id == 'retry-model' for o in menu.options):
                    menu.set_enabled('retry-model', state.startswith('failed:'))

    def _engine_line(self):
        """Task 18 (B4): the engine line shows the live model state."""
        st = self.model_state
        if st == 'no whisper-cli':
            return 'speech engine not installed — brew install whisper-cpp, or restart the app to self-install'
        if st == 'ready':
            from .. import align_whisper
            try:
                eng = align_whisper.find_engine()
            except ValueError:
                eng = None
            if eng:
                return f'speech model: {os.path.basename(eng[1])} (found)'
            return 'speech model: ggml-base.bin (found)'
        return f'speech model: {st}'   # downloading N% / failed: …

    def prepare_cmd(self, pd):
        import sys
        if self._prepare_cmd:
            return list(self._prepare_cmd)
        return [sys.executable, '-P', '-m', 'motion_pipeline.render_cli',
                '--project', pd, '--prepare-only']

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
        # 2026-11-22 (user report: launch slow): import screen modules lazily on first push —
        # only the launch screen is needed at startup, the rest load when their menu row is drawn
        self.SCREENS = {
            'menu': MenuScreen,  # same module as the app — free
            'project': lambda: __import__('motion_pipeline.tui.project_screen', fromlist=['ProjectScreen']).ProjectScreen(),
            'colours': lambda: __import__('motion_pipeline.tui.colours_screen', fromlist=['ColoursScreen']).ColoursScreen(),
            'fonts': lambda: __import__('motion_pipeline.tui.fonts_screen', fromlist=['FontsScreen']).FontsScreen(),
            'zones': lambda: __import__('motion_pipeline.tui.zones_screen', fromlist=['ZonesScreen']).ZonesScreen(),
            'bgtest': lambda: __import__('motion_pipeline.tui.app', fromlist=['BgTestScreen']).BgTestScreen(),
            'inputs': lambda: __import__('motion_pipeline.tui.app', fromlist=['InputsScreen']).InputsScreen(),
            'textstyle': lambda: __import__('motion_pipeline.tui.textstyle_screen', fromlist=['TextStyleScreen']).TextStyleScreen(),
            'graphics': lambda: __import__('motion_pipeline.tui.graphics_screen', fromlist=['GraphicsScreen']).GraphicsScreen(),
            'render': lambda: __import__('motion_pipeline.tui.app', fromlist=['RenderScreen']).RenderScreen(),
        }
        if self.project_dir is None:
            self.project_dir = config.last_project()
        if config.projects_root() is None:
            scr = FirstRunScreen()
            self.push_screen(scr)
        else:
            # 0.5.2: always launch in step 0 (New / load project) — every setting depends on a
            # saved project; Home is reached from there via the 'Home' row.
            scr = self.SCREENS['project']()
            scr.root_entry = True
            self.push_screen(scr)
        # user requirement 2026-11-22: anything loading >100 ms shows a loading animation where
        # the content lands — the initial launch shows it immediately (free-agents pattern)
        def _launch_loader():
            scr.start_loading(text='loading…', immediate=True)
            scr.set_timer(0.8, scr.stop_loading)   # visible through launch, then hidden
        scr.call_after_refresh(_launch_loader)
        # Task 18 (B4): the speech model installs itself on first launch (sha256-pinned);
        # the whisper-cli binary self-installs too when Homebrew is absent (2026-11-22)
        from .. import align_whisper
        try:
            cli = align_whisper.find_cli()
            eng = align_whisper.find_engine()
        except ValueError:
            cli = eng = None
        if eng:
            self.model_state = 'ready'
        else:
            self.model_state = 'downloading 0%'
            mdir = os.environ.get('MP_MODELS_DIR') or os.path.join(
                os.path.expanduser('~'), '.cache', 'motion-pipeline', 'models')

            def _dl():
                try:
                    if not cli:
                        # non-Homebrew fallback: build/fetch whisper-cli into the user cache
                        align_whisper.ensure_cli(
                            progress=lambda s: self.call_from_thread(
                                self._set_model_state, f'installing speech engine… ({s})'))
                    align_whisper.ensure_model(
                        mdir,
                        progress=lambda d, t: self.call_from_thread(
                            self._set_model_state, f'downloading {round(d / max(t, 1) * 100)}%'))
                    self.call_from_thread(self._set_model_state, 'ready')
                except Exception as e:
                    self.call_from_thread(self._set_model_state, f'failed: {e}')

            self.run_worker(_dl, thread=True, exclusive=True, name='model-download')
