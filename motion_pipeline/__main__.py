"""motion_pipeline CLI entry point — launches the interactive project menu (Textual TUI).

usage: python3 -m motion_pipeline [--help] [--version] [--check-render] [--setup-render]
  (no args)       launch the interactive menu
  --help          print this usage, exit 0
  --version       print the package version, exit 0
  --check-render  report the render toolchain (hyperframes, node, ffmpeg, chrome); exit 3 if missing
  --setup-render  install the render toolchain into ~/.cache/motion-pipeline (outside the package)
  anything else: usage on stderr, exit 2
"""
import argparse
import sys

from . import __version__

USAGE = __doc__


def main(argv=None):
    ap = argparse.ArgumentParser(prog='motion_pipeline', description='motion_pipeline — no-code motion-graphics render pipeline',
                                 epilog=USAGE, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--version', action='version', version=f'motion_pipeline {__version__}')
    ap.add_argument('--check-render', action='store_true', help='report the render toolchain')
    ap.add_argument('--setup-render', action='store_true', help='install the render toolchain')
    a = ap.parse_args(argv)
    if a.check_render or a.setup_render:
        from . import render_cli
        return render_cli.main(['--check'] if a.check_render else ['--setup'])
    from .tui.app import MenuApp
    MenuApp().run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
