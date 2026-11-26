"""Creating a QMS admin account from the command line: the account is put in the QMS admin group,
its password is asked for at a prompt, and the creation is recorded in the audit trail."""
from io import StringIO
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from . import workflow as wf
from .models import AuditEvent
from .roles import is_qms_admin

PROMPT = "qms.management.commands.create_qms_admin.getpass"
PASSWORD = "Sufficiently-long-1"
CREATED = "QMS admin account created from the command line"


class CreateQmsAdminTests(TestCase):
    def run_command(self, *args, answers=(PASSWORD, PASSWORD)):
        out = StringIO()
        with mock.patch(PROMPT, side_effect=list(answers)):
            call_command("create_qms_admin", *args, stdout=out)
        return out.getvalue()

    def test_creates_an_account_in_the_qms_admin_group(self):
        out = self.run_command("qms_admin", "--email", "qms.admin@example.org",
                               "--first-name", "Ada", "--last-name", "Lovelace")
        user = User.objects.get(username="qms_admin")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual((user.email, user.first_name, user.last_name),
                         ("qms.admin@example.org", "Ada", "Lovelace"))
        self.assertTrue(user.groups.filter(name=wf.QMS_ADMIN).exists())
        self.assertTrue(is_qms_admin(user))
        self.assertFalse(user.is_staff)  # Django admin is a separate, superuser-only setting
        self.assertIn("Created QMS admin qms_admin", out)

    def test_creation_is_recorded_in_the_audit_trail(self):
        self.run_command("qms_admin", "--email", "qms.admin@example.org")
        event = AuditEvent.objects.get(action="security", comment=CREATED)
        self.assertEqual(event.changes, {"account": [None, "qms_admin"],
                                         "group": [None, wf.QMS_ADMIN]})

    def test_the_group_is_created_if_it_is_missing(self):
        Group.objects.filter(name=wf.QMS_ADMIN).delete()
        self.run_command("qms_admin", "--email", "qms.admin@example.org")
        self.assertTrue(User.objects.get(username="qms_admin").groups.filter(
            name=wf.QMS_ADMIN).exists())

    def test_an_existing_username_is_refused(self):
        User.objects.create_user("qms_admin", "other@example.org", PASSWORD)
        with self.assertRaisesMessage(CommandError, "already exists"):
            self.run_command("qms_admin", "--email", "qms.admin@example.org")
        self.assertEqual(User.objects.filter(username="qms_admin").count(), 1)

    def test_an_email_already_in_use_is_refused(self):
        User.objects.create_user("someone", "qms.admin@example.org", PASSWORD)
        with self.assertRaisesMessage(CommandError,
                                      "Another account already uses QMS.admin@example.org"):
            self.run_command("qms_admin", "--email", "QMS.admin@example.org")
        self.assertFalse(User.objects.filter(username="qms_admin").exists())

    def test_mismatched_passwords_create_nothing(self):
        with self.assertRaisesMessage(CommandError, "do not match"):
            self.run_command("qms_admin", "--email", "qms.admin@example.org",
                             answers=(PASSWORD, "Something-else-2"))
        self.assertFalse(User.objects.filter(username="qms_admin").exists())

    def test_a_weak_password_is_refused(self):
        with self.assertRaisesMessage(CommandError, "too short"):
            self.run_command("qms_admin", "--email", "qms.admin@example.org",
                             answers=("short", "short"))
        self.assertFalse(User.objects.filter(username="qms_admin").exists())

    def test_email_is_required(self):
        with self.assertRaises(CommandError):
            call_command("create_qms_admin", "qms_admin", stdout=StringIO())
        self.assertFalse(User.objects.filter(username="qms_admin").exists())
