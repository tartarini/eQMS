"""The product name (QMS_PRODUCT_NAME, default SAMD_QMS): read from the environment, and shown in
page titles, emails and help instead of a fixed name."""
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from . import help as H
from . import notifications

ROOT = Path(__file__).resolve().parent.parent
NAME = "Acme QMS"


def settings_name_with(env):
    """The QMS_PRODUCT_NAME that a fresh process reads from ``env``."""
    code = "import config.settings as s; print(s.QMS_PRODUCT_NAME)"
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True,
                         text=True, check=True)
    return out.stdout.strip()


class ProductNameSettingTests(TestCase):
    def test_defaults_to_samd_qms_when_not_set(self):
        env = {k: v for k, v in os.environ.items() if k != "QMS_PRODUCT_NAME"}
        self.assertEqual(settings_name_with(env), "SAMD_QMS")

    def test_is_read_from_the_environment_and_trimmed(self):
        env = dict(os.environ, QMS_PRODUCT_NAME="  Acme QMS  ")
        self.assertEqual(settings_name_with(env), "Acme QMS")

    def test_a_blank_value_falls_back_to_the_default(self):
        env = dict(os.environ, QMS_PRODUCT_NAME="   ")
        self.assertEqual(settings_name_with(env), "SAMD_QMS")


@override_settings(QMS_PRODUCT_NAME=NAME)
class ProductNameUseTests(TestCase):
    def test_pages_show_the_name_and_never_the_default(self):
        for url in ["/", "/login/", "/help/getting-started/", "/help/documents/"]:
            content = self.client.get(url, follow=True).content.decode()
            self.assertIn(NAME, content, url)
            self.assertNotIn("SAMD_QMS", content, url)

    def test_notification_subject_uses_the_name(self):
        with self.captureOnCommitCallbacks(execute=True):
            notifications.send_to("Waiting", "Body", ["new@example.org"])
        call_command("dispatch_notifications", stdout=StringIO())
        self.assertEqual(mail.outbox[0].subject, f"[{NAME}] Waiting")

    def test_field_labels_use_the_name(self):
        label, text, _url = H.group_field_help("accessrequest", "reason")
        self.assertEqual(label, f"What you'll use {NAME} for")
        self.assertNotIn("{product}", text)

    def test_field_reference_on_the_topic_page_uses_the_name(self):
        topic = H.FIELD_HELP["accessrequest"][0]
        html, _toc = H.render_topic(topic)
        self.assertIn("use Acme QMS for", html)
        self.assertNotIn("{product}", html)

    def test_a_name_with_html_characters_is_escaped_in_help(self):
        with override_settings(QMS_PRODUCT_NAME="A&B <i>x</i>"):
            html, _toc = H.render_topic("getting-started")
            self.assertIn("A&amp;B &lt;i&gt;x&lt;/i&gt;", html)
            self.assertNotIn("<i>x</i>", html)

    def test_help_text_uses_the_name(self):
        html, _toc = H.render_topic("getting-started")
        self.assertIn(NAME, html)
        self.assertNotIn("SAMD_QMS", html)
        _label, text, _url = H.group_field_help("login", "password")
        self.assertIn(NAME, text)
        self.assertEqual(settings.QMS_PRODUCT_NAME, NAME)
