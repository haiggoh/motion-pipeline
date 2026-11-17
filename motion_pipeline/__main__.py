"""motion_pipeline CLI entry point — launches the interactive project menu (Textual TUI).

usage: python3 -m motion_pipeline [--help] [--version] [--check-render] [--setup-render]
       [--check-graphics DIR]
       [--render-test DIR [--section NAME] [--from S] [--to E] [--draft] [--dry-run]]
  (no args)           launch the interactive menu
  --help              print this usage, exit 0
  --version           print the package version, exit 0
  --check-render      report the render toolchain (hyperframes, node, ffmpeg, chrome); exit 3 if missing
  --setup-render      install the render toolchain into ~/.cache/motion-pipeline (outside the package)
  --dry-run           with --setup-render: print the commands, run nothing;
                      with --render-test: print the plan, run nothing
  --check-graphics    validate ai_graphics manifest + SFX + licences; exit 0 ok / 1 problems / 3 project error
  --render-test       render one scene span into <project>/scratch/ai-test/ (Task 22)
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
    ap.add_argument('--dry-run', action='store_true', help='with --setup-render: print the commands, run nothing; with --render-test: print the plan, run nothing')
    ap.add_argument('--check-graphics', metavar='DIR',
                    help='validate ai_graphics manifest + SFX + licences; exit 0 ok / 1 problems / 3 project error')
    ap.add_argument('--render-test', metavar='DIR', help='render one scene span into <project>/scratch/ai-test/')
    ap.add_argument('--section', help='with --render-test: section name')
    ap.add_argument('--from', dest='from_s', type=float, help='with --render-test: span start (s)')
    ap.add_argument('--to', dest='to_s', type=float, help='with --render-test: span end (s)')
    ap.add_argument('--draft', action='store_true', help='with --render-test: draft quality')
    a = ap.parse_args(argv)
    if a.check_graphics or a.render_test:
        from . import render_cli
        args = []
        if a.check_graphics:
            args += ['--check-graphics', a.check_graphics]
        if a.render_test:
            args += ['--render-test', a.render_test]
            for flag, val in (('--section', a.section), ('--from', a.from_s), ('--to', a.to_s)):
                if val is not None:
                    args += [flag, str(val)]
            if a.draft:
                args.append('--draft')
            if a.dry_run:
                args.append('--dry-run')
        return render_cli.main(args)
    if a.check_render or a.setup_render:
        from . import render_cli
        if a.check_render:
            return render_cli.main(['--check'])
        return render_cli.main(['--setup', '--dry-run'] if a.dry_run else ['--setup'])
    from .tui.app import MenuApp
    MenuApp().run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
