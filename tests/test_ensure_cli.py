"""Task 19-fallback (user request 2026-11-22): whisper-cli self-installs for non-Homebrew
users — source build with CLT cmake, Rosetta x64 prebuilt as fallback. Tests never hit the
network: the tarball/prebuilt URLs point at local files, and cmake is faked."""
import os
import shutil
import subprocess
import zipfile

import pytest

from motion_pipeline import align_whisper


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(align_whisper, 'WHISPER_CACHE_BIN', str(tmp_path / 'cache' / 'bin'))
    return str(tmp_path / 'cache' / 'bin')


def _make_src_tarball(tmp_path):
    """A tar.gz that looks like the whisper.cpp source root (a CMakeLists.txt + a build dir)."""
    import tarfile
    src = tmp_path / 'src-tree'
    (src / 'build' / 'bin').mkdir(parents=True)
    (src / 'CMakeLists.txt').write_text('# fake')
    built = src / 'build' / 'bin' / 'whisper-cli'
    built.write_text('#!/bin/bash\necho fake-whisper\n')
    os.chmod(built, 0o755)
    tar = tmp_path / 'whisper-src.tar.gz'
    with tarfile.open(tar, 'w:gz') as tf:
        tf.add(src, arcname='whisper.cpp-b5907')
    return str(tar)


def test_find_cli_prefers_cache_bin(tmp_path, monkeypatch):
    monkeypatch.delenv('MP_WHISPER_CLI', raising=False)
    monkeypatch.setattr(shutil, 'which', lambda name: None)
    cached = os.path.join(align_whisper.WHISPER_CACHE_BIN, 'whisper-cli')
    os.makedirs(align_whisper.WHISPER_CACHE_BIN, exist_ok=True)
    open(cached, 'w').write('#!/bin/bash\n')
    os.chmod(cached, 0o755)
    assert align_whisper.find_cli() == cached


def test_ensure_cli_returns_existing_without_touching_network(tmp_path, monkeypatch):
    monkeypatch.delenv('MP_WHISPER_CLI', raising=False)
    monkeypatch.setattr(shutil, 'which', lambda name: None)
    cached = os.path.join(align_whisper.WHISPER_CACHE_BIN, 'whisper-cli')
    os.makedirs(align_whisper.WHISPER_CACHE_BIN, exist_ok=True)
    open(cached, 'w').write('#!/bin/bash\n')
    os.chmod(cached, 0o755)

    def _no_net(*a, **k):
        raise AssertionError('ensure_cli must not download when the cli already exists')
    monkeypatch.setattr(subprocess, 'run', _no_net)
    assert align_whisper.ensure_cli() == cached


def test_ensure_cli_builds_from_source_with_cmake(tmp_path, monkeypatch):
    monkeypatch.delenv('MP_WHISPER_CLI', raising=False)
    monkeypatch.setattr(shutil, 'which', lambda name: '/usr/bin/cmake' if name == 'cmake' else None)
    monkeypatch.setenv('MP_WHISPER_TARBALL', _make_src_tarball(tmp_path))
    monkeypatch.setenv('HOME', str(tmp_path))          # cache under the tmp home

    # fake cmake: "build" = copy the staged fake binary where the real build would put it
    real_run = subprocess.run

    def fake_run(cmd, *a, **k):
        if os.path.basename(cmd[0]) == 'cmake':
            if '--build' in cmd:   # "compile": stage the fake binary where ensure_cli looks
                src_dir = os.path.dirname(cmd[2])   # cmd[2] IS <src>/build
                os.makedirs(os.path.join(src_dir, 'build', 'bin'), exist_ok=True)
                built = os.path.join(src_dir, 'build', 'bin', 'whisper-cli')
                with open(built, 'w') as f:
                    f.write('#!/bin/bash\necho built\n')
                os.chmod(built, 0o755)
            return subprocess.CompletedProcess(cmd, 0, '', '')   # configure: pretend OK
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    out = align_whisper.ensure_cli(progress=[])
    assert out == os.path.join(align_whisper.WHISPER_CACHE_BIN, 'whisper-cli')
    assert os.path.isfile(out) and os.access(out, os.X_OK)


def test_ensure_cli_rosetta_prebuilt_when_no_cmake(tmp_path, monkeypatch):
    monkeypatch.delenv('MP_WHISPER_CLI', raising=False)
    monkeypatch.setattr(shutil, 'which', lambda name: None)   # no cmake anywhere
    # a real zip with the binary — ditto (real macOS tool) extracts it for real
    zip_path = tmp_path / 'prebuilt' / 'whisper-bin-x64.zip'
    zip_path.parent.mkdir()
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr('whisper-cli', '#!/bin/bash\necho rosetta\n')
    monkeypatch.setenv('MP_WHISPER_PREBUILT_URL', 'file://' + str(zip_path))
    monkeypatch.setenv('HOME', str(tmp_path))
    out = align_whisper.ensure_cli()
    assert out == os.path.join(align_whisper.WHISPER_CACHE_BIN, 'whisper-cli')
    assert os.path.isfile(out) and os.access(out, os.X_OK)


def test_ensure_cli_fails_loudly_when_everything_fails(tmp_path, monkeypatch):
    monkeypatch.delenv('MP_WHISPER_CLI', raising=False)
    monkeypatch.setattr(shutil, 'which', lambda name: None)
    monkeypatch.setenv('MP_WHISPER_TARBALL', str(tmp_path / 'missing.tar.gz'))
    monkeypatch.setenv('MP_WHISPER_PREBUILT_URL', 'file:///nonexistent/whisper.zip')
    monkeypatch.setenv('HOME', str(tmp_path))
    with pytest.raises(ValueError, match='whisper-cli|whisper.cpp'):
        align_whisper.ensure_cli()
