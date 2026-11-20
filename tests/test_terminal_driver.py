"""Task 1 (spec A1): Apple Terminal must not receive the DECRQM 2048 query.

Apple Terminal does not consume `ESC[?2048$p` and prints the trailing `p` visibly
(stray `p` on startup). LinuxDriver._query_in_band_window_resize (textual 8.2.8,
linux_driver.py:157) writes it unconditionally; the driver subclass skips it only
when TERM_PROGRAM=Apple_Terminal.
"""
import os
import pty
import select
import subprocess
import sys
import time

import pytest

QUERY = b'\x1b[?2048$p'
QUERY_STR = QUERY.decode()  # LinuxDriver.write receives str, not bytes


def _driver_with_stub_write(cls):
    # __new__ + stub: the ctor needs a live App; the method under test only calls self.write
    d = cls.__new__(cls)
    written = []
    d.write = written.append
    return d, written


@pytest.mark.parametrize('term_program,expect_query', [
    ('Apple_Terminal', False),
    ('iTerm.app', True),
])
def test_query_in_band_window_resize_respects_terminal(monkeypatch, term_program, expect_query):
    from motion_pipeline.tui.terminal_driver import AppleTerminalSafeDriver
    monkeypatch.setenv('TERM_PROGRAM', term_program)
    d, written = _driver_with_stub_write(AppleTerminalSafeDriver)
    d._query_in_band_window_resize()
    assert (QUERY_STR in ''.join(written)) is expect_query


def test_get_driver_class_posix_returns_subclass():
    from motion_pipeline.tui.terminal_driver import AppleTerminalSafeDriver, get_driver_class
    if os.name == 'posix':
        assert get_driver_class() is AppleTerminalSafeDriver
    else:
        assert get_driver_class() is None


def test_menu_app_uses_safe_driver_on_posix():
    from motion_pipeline.tui.app import MenuApp
    from motion_pipeline.tui.terminal_driver import AppleTerminalSafeDriver
    if os.name == 'posix':
        # textual 8.2.8 App.__init__ stores the ctor arg: self.driver_class = driver_class or ...
        assert MenuApp().driver_class is AppleTerminalSafeDriver


def _pty_run(term_program: str, tmp_path, timeout: float = 15.0) -> bytes:
    """Spawn the real TUI in a pty with an isolated HOME + MP_* overrides, read ~2s, send q."""
    env = dict(os.environ)
    env['TERM_PROGRAM'] = term_program
    env['TERM'] = 'xterm-256color'
    env['HOME'] = str(tmp_path)
    env['MP_CONFIG_DIR'] = str(tmp_path / 'config')
    env['MP_MODELS_DIR'] = str(tmp_path / 'models')
    env['MP_FONT_CACHE'] = str(tmp_path / 'fontcache')
    env['MP_TOOLCHAIN_DIR'] = str(tmp_path / 'toolchain')
    master, slave = pty.openpty()
    proc = subprocess.Popen([sys.executable, '-P', '-m', 'motion_pipeline'],
                            stdin=slave, stdout=slave, stderr=slave, env=env,
                            cwd=str(tmp_path), close_fds=True)
    os.close(slave)
    out = b''
    deadline = time.time() + timeout
    sent_q = False
    try:
        while time.time() < deadline:
            r, _, _ = select.select([master], [], [], 0.2)
            if r:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                out += chunk
            if not sent_q and time.time() > deadline - timeout + 2.0:
                os.write(master, b'q')
                sent_q = True
            if proc.poll() is not None:
                # drain
                while True:
                    r, _, _ = select.select([master], [], [], 0.2)
                    if not r:
                        break
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    out += chunk
                break
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        os.close(master)
    return out


def test_pty_apple_terminal_never_gets_2048_query(tmp_path):
    out = _pty_run('Apple_Terminal', tmp_path)
    assert QUERY not in out


def test_pty_other_terminal_still_gets_2048_query(tmp_path):
    """Discriminant: under a non-Apple terminal the query IS written (proves the probe
    reads the byte stream and the suppression is terminal-gated, not absent)."""
    out = _pty_run('iTerm.app', tmp_path)
    assert QUERY in out
