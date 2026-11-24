"""
Run the daily jobs in QMS_SCHEDULED_JOBS for ever (the scheduler container's command). Queued
notifications are sent every minute while it runs.

Each job runs as a separate process, so one failure can't stop the others. A failure, a
timeout or a non-zero exit sends an alert email. Logs go to stdout for `docker compose logs`.

    python manage.py run_scheduler            # run for ever
    python manage.py run_scheduler --once verify_audit   # run one job now (for testing)
"""
import logging
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from qms.notifications import dispatch_pending

log = logging.getLogger("qms.scheduler")
JOB_TIMEOUT_SECONDS = 2 * 60 * 60
SWEEP_SECONDS = 60   # how often queued notifications are sent (retries included)


def next_run(hhmm: str, now: datetime) -> datetime:
    hour, minute = (int(x) for x in hhmm.split(":"))
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return candidate if candidate > now else candidate + timedelta(days=1)


def sweep_notifications() -> None:
    """Send queued notifications, including retries. Never stops the scheduler."""
    try:
        dispatch_pending()
    except Exception:  # noqa: BLE001
        log.exception("notification sweep failed")


def run_job(name: str, command: list) -> bool:
    log.info("job %s starting: %s", name, " ".join(command))
    started = time.monotonic()
    try:
        proc = subprocess.run(command, capture_output=True, text=True,
                              timeout=JOB_TIMEOUT_SECONDS, cwd=settings.BASE_DIR)
        output = (proc.stdout + proc.stderr).strip()
        ok = proc.returncode == 0
    except subprocess.TimeoutExpired:
        output, ok = f"Timed out after {JOB_TIMEOUT_SECONDS} s", False
    except OSError as exc:
        output, ok = f"Could not start: {exc}", False
    seconds = round(time.monotonic() - started, 1)
    for line in output.splitlines()[-20:]:
        log.info("job %s | %s", name, line)
    if ok:
        log.info("job %s succeeded in %ss", name, seconds)
    else:
        log.error("job %s FAILED after %ss", name, seconds)
        try:
            call_command("send_alert", f"Scheduled job '{name}' failed",
                         f"The job '{name}' failed at {datetime.now(timezone.utc):%Y-%m-%d %H:%M} "
                         f"UTC.\n\nLast output:\n{output[-4000:]}")
        except Exception:  # noqa: BLE001 - alerting must never kill the scheduler
            log.exception("could not send alert for job %s", name)
    return ok


class Command(BaseCommand):
    help = "Run the scheduled daily jobs (PMS generation, reminders, audit check, backup)."

    def add_arguments(self, parser):
        parser.add_argument("--once", metavar="JOB", help="Run one named job now and exit")

    def handle(self, *args, once=None, **options):
        jobs = {name: (when, cmd) for when, name, cmd in settings.QMS_SCHEDULED_JOBS}
        if once:
            if once not in jobs:
                raise CommandError(f"Unknown job {once!r}; known: {', '.join(jobs)}")
            ok = run_job(once, jobs[once][1])
            sys.exit(0 if ok else 1)

        log.info("scheduler started with %d jobs: %s", len(jobs),
                 ", ".join(f"{n} at {w} UTC" for n, (w, _) in jobs.items()))
        while True:
            now = datetime.now(timezone.utc)
            name, (when, cmd) = min(jobs.items(), key=lambda kv: next_run(kv[1][0], now))
            due = next_run(when, now)
            wait = (due - now).total_seconds()
            if wait > SWEEP_SECONDS:
                close_old_connections()  # the database may have dropped the idle connection
                sweep_notifications()
                time.sleep(SWEEP_SECONDS)
                continue
            log.info("next job %s at %s UTC (in %d min)", name, due.strftime("%Y-%m-%d %H:%M"),
                     wait // 60)
            time.sleep(max(1, wait))
            run_job(name, cmd)
            time.sleep(61)  # never run the same minute twice
