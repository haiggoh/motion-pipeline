"""motion_pipeline CLI entry point — currently the menu placeholder (Task 5 builds the TUI).

usage: python3 -m motion_pipeline [--help] [--version]
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
    # no subcommand yet: print usage and exit 0 (menu lands in Task 5)
    print('motion_pipeline', __version__, '— the project menu lands in Task 5; see README.md')
    return 0


if __name__ == '__main__':
    sys.exit(main())
