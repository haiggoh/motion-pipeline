"""motion_pipeline CLI entry point — launches the interactive project menu (Textual TUI).

usage: python3 -m motion_pipeline [--help] [--version]
  (no args)   launch the interactive menu
  --help      print this usage, exit 0
  --version   print the package version, exit 0
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
    ap.parse_args(argv)
    from .tui.app import MenuApp
    MenuApp().run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
