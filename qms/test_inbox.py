"""Notifications are stored, sent after the change commits, retried when delivery fails, and shown
in each person's own inbox."""
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from . import notifications
from . import workflow as wf
from .management.commands.run_scheduler import sweep_notifications
from .models import Device, DeviceMembership, Notification, Record


def make_user(username, role=None, email=None):
    user = User.objects.create_user(username, email=email or f"{username}@example.org",
                                    password="test-pass-123")
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    return user


class Base(TestCase):
    def setUp(self):
        self.device = Device(name="Test device", code="TST")
        self.device.save()
        self.qa = make_user("qa", wf.QA)
        self.cso = make_user("cso", wf.CLINICAL_SAFETY)
        self.eng = make_user("eng", wf.ENGINEER)
        for u in (self.qa, self.cso, self.eng):
            DeviceMembership.objects.create(device=self.device, user=u)

    def incident(self, title="Wrong score sent to GP"):
        with self.captureOnCommitCallbacks(execute=True):
            return Record.objects.create(device=self.device, record_type=wf.INCIDENT, title=title)


class InboxQueueTests(Base):
    def test_message_is_stored_per_person_and_sent_with_a_link(self):
        rec = self.incident()
        rows = Notification.objects.filter(subject__startswith="URGENT")
        self.assertEqual({n.recipient for n in rows}, {self.qa, self.cso})
        self.assertTrue(all(n.status == Notification.SENT for n in rows))
        self.assertTrue(all(n.path == reverse("qms:record_detail", args=[rec.ref]) for n in rows))
        self.assertEqual(len(mail.outbox), 2)  # one email per person, no addresses shared
        self.assertTrue(all(len(m.to) == 1 for m in mail.outbox))
        self.assertIn(reverse("qms:record_detail", args=[rec.ref]), mail.outbox[0].body)
        self.assertTrue(mail.outbox[0].subject.startswith("[SAMD_QMS] URGENT"))

    def test_rolled_back_change_tells_nobody(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                Record.objects.create(device=self.device, record_type=wf.INCIDENT, title="Gone")
                raise RuntimeError("the change was rolled back")
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(mail.outbox, [])

    @override_settings(QMS_NOTIFICATIONS_ENABLED=False)
    def test_nothing_is_stored_when_notifications_are_off(self):
        self.incident()
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_failed_send_is_kept_and_sent_on_the_next_run(self):
        with mock.patch("qms.notifications.send_mail", side_effect=OSError("relay down")), \
                self.assertLogs("qms.notifications", "ERROR"):
            self.incident()
        failed = Notification.objects.filter(status=Notification.PENDING)
        self.assertEqual(failed.count(), 2)
        self.assertTrue(all(n.attempts == 1 and "relay down" in n.last_error for n in failed))
        self.assertEqual(mail.outbox, [])

        self.assertEqual(notifications.dispatch_pending(), 2)
        self.assertFalse(Notification.objects.filter(status=Notification.PENDING).exists())
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(all(n.attempts == 2 and n.last_error == ""
                            for n in Notification.objects.all()))

    def test_gives_up_after_the_maximum_attempts(self):
        with mock.patch("qms.notifications.send_mail", side_effect=OSError("relay down")), \
                self.assertLogs("qms.notifications", "ERROR"):
            self.incident()
            for _ in range(Notification.MAX_ATTEMPTS):
                notifications.dispatch_pending()
        self.assertEqual(Notification.objects.filter(status=Notification.FAILED).count(), 2)
        self.assertEqual(notifications.dispatch_pending(), 0)  # failed ones are not retried
        self.assertEqual(mail.outbox, [])

    def test_address_without_an_account_gets_email_but_no_inbox_entry(self):
        with self.captureOnCommitCallbacks(execute=True):
            notifications.send_to("Invitation to SAMD_QMS", "Hello.", ["new@example.org"])
        n = Notification.objects.get()
        self.assertIsNone(n.recipient)
        self.assertEqual(n.email, "new@example.org")
        self.assertEqual(mail.outbox[0].to, ["new@example.org"])

    def test_dispatch_command_sends_what_is_waiting(self):
        Notification.objects.create(recipient=self.eng, email=self.eng.email, subject="Waiting",
                                    body="Body")
        call_command("dispatch_notifications", stdout=open("/dev/null", "w"))
        self.assertEqual(Notification.objects.get().status, Notification.SENT)
        self.assertEqual(mail.outbox[0].subject, "[SAMD_QMS] Waiting")

    def test_scheduler_sweep_sends_what_is_waiting(self):
        Notification.objects.create(recipient=self.eng, email=self.eng.email, subject="Waiting",
                                    body="Body")
        sweep_notifications()
        self.assertEqual(Notification.objects.get().status, Notification.SENT)


class InboxViewTests(Base):
    def setUp(self):
        super().setUp()
        self.mine = Notification.objects.create(recipient=self.eng, email=self.eng.email,
                                                subject="For Eng", body="a",
                                                path=reverse("qms:dashboard"))
        self.theirs = Notification.objects.create(recipient=self.qa, email=self.qa.email,
                                                  subject="For QA only", body="b",
                                                  path=reverse("qms:dashboard"))
        self.client.force_login(self.eng)

    def test_each_person_sees_only_their_own_notifications(self):
        response = self.client.get(reverse("qms:notification_list"))
        self.assertContains(response, "For Eng")
        self.assertNotContains(response, "For QA only")

    def test_opening_marks_it_read_and_goes_to_its_page(self):
        response = self.client.get(reverse("qms:notification_open", args=[self.mine.pk]))
        self.assertRedirects(response, reverse("qms:dashboard"))
        self.mine.refresh_from_db()
        self.assertIsNotNone(self.mine.read_at)

    def test_another_persons_notification_cannot_be_opened(self):
        response = self.client.get(reverse("qms:notification_open", args=[self.theirs.pk]))
        self.assertEqual(response.status_code, 404)
        self.theirs.refresh_from_db()
        self.assertIsNone(self.theirs.read_at)

    def test_links_to_other_sites_are_never_followed(self):
        self.mine.path = "https://elsewhere.example.org/phish"
        self.mine.save()
        response = self.client.get(reverse("qms:notification_open", args=[self.mine.pk]))
        self.assertRedirects(response, reverse("qms:notification_list"))

    def test_mark_all_read_needs_a_post_and_clears_only_my_unread(self):
        self.assertEqual(self.client.get(reverse("qms:notification_read_all")).status_code, 405)
        self.client.post(reverse("qms:notification_read_all"))
        self.mine.refresh_from_db()
        self.theirs.refresh_from_db()
        self.assertIsNotNone(self.mine.read_at)
        self.assertIsNone(self.theirs.read_at)

    def test_header_shows_the_unread_count(self):
        response = self.client.get(reverse("qms:notification_list"))
        self.assertEqual(response.context["unread_notifications"], 1)
        self.client.post(reverse("qms:notification_read_all"))
        response = self.client.get(reverse("qms:notification_list"))
        self.assertEqual(response.context["unread_notifications"], 0)
