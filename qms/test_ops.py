"""Operations: health check, scheduler and alerts."""
import tempfile
from datetime import datetime, timezone

from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from .management.commands.run_scheduler import next_run, run_job

MEDIA = tempfile.mkdtemp(prefix="qms-test-ops-")


class HealthTests(TestCase):
    @override_settings(MEDIA_ROOT=MEDIA, QMS_VERSION="9.9.9")
    def test_healthz_ok_without_login_and_reveals_only_status(self):
        r = self.client.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok", "version": "9.9.9",
                                    "checks": {"database": "ok", "storage": "ok"}})
        self.assertIn("no-cache", r.headers.get("Cache-Control", ""))

    @override_settings(MEDIA_ROOT="/nonexistent/qms-media")
    def test_healthz_fails_when_storage_is_unavailable(self):
        r = self.client.get("/healthz")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["checks"]["storage"], "fail")

    def test_healthz_is_get_only(self):
        self.assertEqual(self.client.post("/healthz").status_code, 405)


class SchedulerTests(TestCase):
    def test_next_run(self):
        now = datetime(2026, 11, 5, 23, 30, tzinfo=timezone.utc)
        self.assertEqual(next_run("02:30", now), datetime(2026, 11, 6, 2, 30, tzinfo=timezone.utc))
        self.assertEqual(next_run("23:45", now), datetime(2026, 11, 5, 23, 45, tzinfo=timezone.utc))
        self.assertEqual(next_run("23:30", now), datetime(2026, 11, 6, 23, 30, tzinfo=timezone.utc))

    @override_settings(QMS_ALERT_EMAILS=["ops@example.org"])
    def test_failed_job_sends_alert_and_successful_job_does_not(self):
        self.assertTrue(run_job("fine", ["python3", "-c", "print('ok')"]))
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(run_job("broken", ["python3", "-c",
                                            "import sys; print('disk full'); sys.exit(3)"]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Scheduled job 'broken' failed", mail.outbox[0].subject)
        self.assertIn("disk full", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["ops@example.org"])

    @override_settings(QMS_ALERT_EMAILS=["ops@example.org"])
    def test_missing_command_is_a_failure(self):
        self.assertFalse(run_job("missing", ["/nonexistent/command"]))
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(QMS_ALERT_EMAILS=[])
    def test_alert_needs_recipients(self):
        with self.assertRaises(CommandError):
            call_command("send_alert", "test")

    def test_unknown_job_is_refused(self):
        with self.assertRaises(CommandError):
            call_command("run_scheduler", once="no_such_job")
