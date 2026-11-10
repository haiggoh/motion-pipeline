"""jobs.py — long jobs as Textual workers with progress + cancellation (design G2).

run_command(app, cmd, log_widget) runs a subprocess, streaming stdout+stderr lines into the
Log widget, and returns a Job whose cancel() STOPS the process: the command runs in its own
process group and cancel() signals the whole group (render_scene.sh -> hyperframes -> chrome
/ ffmpeg), then the worker thread reaps it. v0.1-0.4 only cancelled the Textual worker, so a
cancelled render kept running in the background.
"""
import os
import signal
import subprocess


class Job:
    def __init__(self):
        self.proc: 'subprocess.Popen | None' = None
        self.worker = None
        self.cancelled = False

    def cancel(self):
        self.cancelled = True
        p = self.proc
        if p is not None and p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if self.worker is not None:
            self.worker.cancel()


def run_command(app, cmd, log, done_msg='done', on_finish=None):
    """Run cmd (list) as a worker; each output line is appended to `log`.
    on_finish(rc), if given, is called (via call_from_thread) when the command exits —
    not after a cancel. Returns the Job."""
    job = Job()

    def _run():
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, start_new_session=True)
        job.proc = proc
        if job.cancelled:      # cancel() raced the start
            job.cancel()
        for line in proc.stdout or []:
            if job.cancelled:
                break
            if app.is_running:
                app.call_from_thread(log.write_line, line.rstrip('\n'))
        try:
            rc = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            rc = proc.wait()
        if app.is_running and not job.cancelled:
            app.call_from_thread(log.write_line, f'{done_msg} (exit {rc})')
            if on_finish is not None:
                app.call_from_thread(on_finish, rc)
        return rc

    job.worker = app.run_worker(_run, thread=True, exclusive=False, name=str(cmd[:2]))
    return job
