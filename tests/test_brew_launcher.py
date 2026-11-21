"""Task 6 (plan 2026-11-16): the Homebrew formula's generated launcher — -P cwd isolation and
the dependency-stamp resync on version change. Reads the formula from MP_TAP_FORMULA; skips
with a printed reason when unset."""
import os
import re
import subprocess
import sys
import textwrap

import pytest

FORMULA = os.environ.get('MP_TAP_FORMULA')


def _extract_launcher(formula_text, version, libexec):
    m = re.search(r'\(bin/"motion-pipeline"\)\.write <<~EOS\n(.*?)\n\s*EOS', formula_text, re.S)
    assert m, 'launcher heredoc not found in formula'
    script = textwrap.dedent(m.group(1))
    script = script.replace('#{version}', version)
    script = script.replace('#{opt_libexec}', libexec)
    script = re.sub(r'#\{Formula\["python@3\.14"\]\.opt_bin\}/python3\.14', '/FAKE/PY/python3.14', script)
    assert '#{' not in script, 'unsubstituted ruby interpolation left'
    return script


def _make_fake_venv(home):
    venv = os.path.join(home, '.cache/homebrew/motion-pipeline/venv')
    os.makedirs(os.path.join(venv, 'bin'))
    py = os.path.join(venv, 'bin', 'python')
    with open(py, 'w') as f:
        f.write('#!/bin/bash\nif [ "$1" = "-c" ]; then exec %s "$@"; fi\necho "FAKE_PYTHON $*"\n' % sys.executable)
    os.chmod(py, 0o755)
    pip = os.path.join(venv, 'bin', 'pip')
    with open(pip, 'w') as f:
        f.write('#!/bin/bash\necho "pip $*" >> "$FAKE_PIP_LOG"\n')
    os.chmod(pip, 0o755)
    return venv


@pytest.mark.skipif(not FORMULA, reason='MP_TAP_FORMULA not set — formula-launcher test skipped (printed)')
def test_brew_launcher_uses_P_and_resyncs_deps_on_version_change(tmp_path):
    formula_text = open(FORMULA).read()
    libexec = tmp_path / 'libexec'
    libexec.mkdir()
    (libexec / 'pyproject.toml').write_text('[project]\nname = "motion-pipeline"\ndependencies = ["textual"]\n')
    home = tmp_path / 'home'
    home.mkdir()
    _make_fake_venv(str(home))
    pip_log = tmp_path / 'pip.log'
    env = dict(os.environ, HOME=str(home), FAKE_PIP_LOG=str(pip_log))
    launcher = tmp_path / 'motion-pipeline'

    def write_launcher(version):
        launcher.write_text(_extract_launcher(formula_text, version, str(libexec)))
        os.chmod(str(launcher), 0o755)

    write_launcher('0.6.0-test')
    r = subprocess.run(['bash', str(launcher), '--version'], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert '-P' in r.stdout and 'motion_pipeline' in r.stdout, r.stdout  # -P cwd isolation in the exec line
    venv = os.path.join(str(home), '.cache/homebrew/motion-pipeline/venv')
    stamp = os.path.join(venv, '.mp-deps')
    assert os.path.isfile(stamp)                                    # deps stamp written
    import hashlib
    assert open(stamp).read() == hashlib.sha256(b'textual').hexdigest()
    assert 'install --quiet textual' in pip_log.read_text()       # deps installed once

    r = subprocess.run(['bash', str(launcher), '--version'], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert pip_log.read_text().count('install --quiet textual') == 1  # same stamp -> no reinstall

    # a brew upgrade adding a dep (0.7.0's pypdf) changes the deps string -> stamp differs -> resync
    (libexec / 'pyproject.toml').write_text('[project]\nname = "motion-pipeline"\ndependencies = ["textual", "pypdf>=4"]\n')
    r = subprocess.run(['bash', str(launcher), '--version'], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert open(stamp).read() == hashlib.sha256(b'textual pypdf>=4').hexdigest()
    assert pip_log.read_text().count('install --quiet textual pypdf>=4') == 1  # resynced on deps change
