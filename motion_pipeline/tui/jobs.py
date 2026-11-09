"""jobs.py — long jobs as Textual workers with progress + cancellation (design G2).

run_command(app, cmd, log_widget) runs a subprocess, streaming stdout lines into the
Log widget, and returns the Worker so the caller can cancel. The menu stays responsive
because the subprocess runs in a worker thread.
"""
import subprocess


def run_command(app, cmd, log, done_msg='done', on_finish=None):
    """Run cmd (list) as a worker; each output line is appended to `log`.
    on_finish(rc), if given, is called (via call_from_thread) when the command exits.
    Returns the Worker."""

    def _run():
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        for line in proc.stdout or []:
            if app.is_running:
                app.call_from_thread(log.write_line, line.rstrip('\n'))
        rc = proc.wait()
        if app.is_running:
            app.call_from_thread(log.write_line, f'{done_msg} (exit {rc})')
            if on_finish is not None:
                app.call_from_thread(on_finish, rc)
        return rc

    return app.run_worker(_run, thread=True, exclusive=False, name=str(cmd[:2]))
