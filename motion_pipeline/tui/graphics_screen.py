"""graphics_screen.py — the "Add motion graphics" step (plan Task 23 / M5): live instructions,
status line, hand-off actions, and — only when free-agents is detected — the model/effort
Selects plus the free-session launcher row."""
import json
import os
import subprocess
import sys

from textual.containers import Horizontal
from textual.widgets import RichLog, Select, Static

from .. import free_agents, playbook
from .base import SubmenuScreen, show_path
from .jobs import run_command


def _pbcopy(text):
    p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
    p.communicate(text.encode())


class GraphicsScreen(SubmenuScreen):
    TITLE = 'Add motion graphics'
    BASE_ACTIONS = [('open', 'Open the playbook'), ('reveal', 'Show the project folder in Finder'),
                    ('copy', 'Copy the hand-off prompt'), ('check', 'Check AI graphics')]

    def compose(self):
        self._fa = None
        self._fa_error = ''
        try:
            self._fa = free_agents.detect()
        except ValueError as e:
            self._fa_error = str(e)
        self.ACTIONS = list(self.BASE_ACTIONS)
        if self._fa is not None:
            self.ACTIONS.append(('free', 'Start a free AI session for this project (free-agents)'))
        yield from super().compose()

    def compose_body(self):
        pd = getattr(self.app, 'project_dir', None)
        n_words = n_sections = None
        if pd and os.path.isfile(os.path.join(pd, 'transcript_model.json')):
            m = json.load(open(os.path.join(pd, 'transcript_model.json')))
            n_words, n_sections = len(m.get('words', [])), len(m.get('sections', []))
        if n_words is None:
            text = '(no project open — pick one in step 0 first)'
        else:
            text = (
                f'1. Your timings are saved ({n_words} words, {n_sections} sections). Graphics '
                f'attach to them, so a new VO take re-times them automatically.\n'
                f'2. Give your AI two things: this project folder ({show_path(str(pd))}) and the '
                f'playbook {playbook.OUT_NAME} inside it.\n'
                '3. Tell it: "Read MOTION_GRAPHICS_PLAYBOOK.md first and follow it." '
                '(row 3 copies this prompt to the clipboard.)\n'
                '4. The AI only adds files in ai_graphics/ — it never changes your settings. '
                'It will ask you about the style first.\n'
                '5. When it is done, come back here and choose "Check AI graphics", then render '
                'in step 7.')
        yield Static(text, id='instructions')
        if self._fa is not None:
            models = free_agents.models(self._fa)
            top = models[0]['alias'] if models else Select.BLANK
            with Horizontal(id='fa-bar'):
                yield Select([(m['display'], m['alias']) for m in models] or [('(no keyed models)', '')],
                             id='fa-model', value=top, classes='variant-select')
                yield Select([(e, e) for e in ('low', 'medium', 'high', 'xhigh', 'max')],
                             id='fa-effort', value='high', classes='variant-select')
        elif self._fa_error:
            yield Static(self._fa_error, id='fa-error', classes='feedback-error')
        yield Static('', id='status', classes='feedback')
        yield Static('', id='error', classes='feedback-error')

    def compose_after_actions(self):
        yield RichLog(id='log', wrap=True, markup=False, classes='joblog', min_width=0)

    def on_mount(self):
        pd = getattr(self.app, 'project_dir', None)
        if pd and os.path.isfile(os.path.join(pd, 'project.json')):
            try:
                playbook.write_playbook(pd)  # menu-owned: regenerated on every visit to the step
            except Exception:
                pass
        self.refresh_status()

    def playbook_path(self):
        return os.path.join(self.require_project(), playbook.OUT_NAME)

    def refresh_status(self):
        try:
            pd = self.require_project()
        except ValueError:
            return
        try:
            from .. import ai_layer
            mp = os.path.join(pd, 'transcript_model.json')
            words = json.load(open(mp))['words'] if os.path.isfile(mp) else []
            entries = ai_layer.load_manifest(pd, words)
            n_sfx = sum(len(g.get('sfx', [])) for g in entries)
            self.query_one('#status', Static).update(
                f'AI graphics: {len(entries)} declared, {n_sfx} sound effects — OK')
        except Exception as e:
            self.query_one('#status', Static).update(f'AI graphics: {e}')

    def hand_off_prompt(self):
        return free_agents.FIRST_PROMPT.format(playbook=self.playbook_path())

    def on_action(self, action_id):
        if action_id == 'open':
            subprocess.Popen(['open', self.playbook_path()])
        elif action_id == 'reveal':
            subprocess.Popen(['open', '-R', self.require_project()])
        elif action_id == 'copy':
            _pbcopy(self.hand_off_prompt())
            self.query_one('#status', Static).update('hand-off prompt copied to the clipboard')
        elif action_id == 'check':
            pd = self.require_project()
            self.query_one('#status', Static).update('checking ai_graphics…')
            self.worker = run_command(
                self.app, [sys.executable, '-P', '-m', 'motion_pipeline.render_cli',
                           '--check-graphics', pd],
                self.query_one('#log', RichLog),
                on_finish=lambda rc: self.query_one('#status', Static).update(
                    f'check-graphics exit {rc}' + (' — OK' if rc == 0 else ' — problems above')))
        elif action_id == 'free':
            self._launch_free()

    def _launch_free(self):
        fa = self._fa
        if fa is None:
            return
        alias = self.query_one('#fa-model', Select).value
        effort = self.query_one('#fa-effort', Select).value
        if not alias:
            self.query_one('#error', Static).update('no keyed free model available — set its API key first')
            return
        display = next((m['display'] for m in free_agents.models(fa) if m['alias'] == alias), alias)
        try:
            free_agents.launch(fa, alias, effort, self.require_project(), self.playbook_path())
        except RuntimeError as e:
            self.query_one('#error', Static).update(str(e))
            return
        self.query_one('#status', Static).update(
            f'free AI session opening in a new Terminal window ({display}) — answer its questions there')
