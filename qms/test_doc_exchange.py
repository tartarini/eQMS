"""Document import and export: folders, zip, markdown import, git sync, and review reminders."""
import io
import os
import shutil
import subprocess
import tempfile
import zipfile
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from . import doc_exchange, notifications, services
from . import workflow as wf
from .models import Device, DeviceMembership, Document, DocumentVersion, ReviewReminder

PW = "test-pass-123"
MEDIA = tempfile.mkdtemp(prefix="qms-test-docx-")


def person(username, device=None, roles=""):
    u = User.objects.create_user(username, email=f"{username}@example.org", password=PW)
    if device is not None:
        DeviceMembership.objects.create(device=device, user=u, roles=roles)
    return u


def effective_doc(device, owner, title="Calibration of test rigs", data=b"# Calibration\n\nText.\n",
                  name="calibration.md", review_in=365):
    doc = Document.objects.create(title=title, doc_type="SOP", device=device, owner=owner,
                                  review_period_months=12)
    v = services.create_version(doc, owner, version="1.0", change_summary="First",
                                file=ContentFile(data, name=name))
    DocumentVersion.objects.filter(pk=v.pk).update(
        status="effective", effective_date=date.today(),
        next_review_date=date.today() + timedelta(days=review_in))
    return doc


@override_settings(MEDIA_ROOT=MEDIA)
class ExportTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.a = Device.objects.create(name="Device A", code="DA")
        self.b = Device.objects.create(name="Device B", code="DB")
        self.qa_a = person("qa_a", self.a, wf.QA)
        self.qa_b = person("qa_b", self.b, wf.QA)
        self.doc_a = effective_doc(self.a, self.qa_a)
        self.doc_b = effective_doc(self.b, self.qa_b, title="Bravo SOP")

    def test_export_has_folder_per_document_with_file_and_markdown(self):
        files = doc_exchange.export_files()
        folder = f"DA/SOP/{self.doc_a.number} calibration-of-test-rigs"
        self.assertIn(f"{folder}/{self.doc_a.number}.md", files)
        self.assertIn(f"{folder}/calibration.md", files)
        text = files[f"{folder}/{self.doc_a.number}.md"].decode()
        self.assertIn(f"number: {self.doc_a.number}", text)
        self.assertIn("# Calibration", text)
        self.assertIn("INDEX.md", files)
        self.assertIn("MANIFEST.json", files)

    def test_draft_documents_are_not_exported(self):
        draft = Document.objects.create(title="Draft only", doc_type="SOP", device=self.a,
                                        owner=self.qa_a, review_period_months=12)
        services.create_version(draft, self.qa_a, version="1.0", change_summary="x",
                                file=ContentFile(b"x", name="draft.md"))
        self.assertNotIn(draft.number, " ".join(doc_exchange.export_files()))

    def test_export_only_shows_documents_the_user_can_see(self):
        names = " ".join(doc_exchange.export_files(self.qa_a))
        self.assertIn(self.doc_a.number, names)
        self.assertNotIn(self.doc_b.number, names)

    def test_zip_download_for_a_signed_in_user(self):
        self.client.force_login(self.qa_a)
        resp = self.client.get(reverse("qms:document_export"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            self.assertTrue(any(n.startswith("DA/") for n in zf.namelist()))
            self.assertFalse(any(n.startswith("DB/") for n in zf.namelist()))


@override_settings(MEDIA_ROOT=MEDIA)
class ImportTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.a = Device.objects.create(name="Device A", code="DA")
        self.b = Device.objects.create(name="Device B", code="DB")
        self.qa_a = person("qa_a", self.a, wf.QA)
        self.outsider = person("outsider", self.b, wf.ENGINEER)

    def md(self, body="Steps.", **meta):
        meta.setdefault("title", "Cleaning the rig")
        meta.setdefault("type", "WI")
        meta.setdefault("device", "DA")
        front = "\n".join(f"{k}: {v}" for k, v in meta.items())
        return f"---\n{front}\n---\n{body}\n".encode()

    def test_new_markdown_becomes_a_draft_document(self):
        results = doc_exchange.import_markdown(self.qa_a, [("rig.md", self.md(
            description="How to clean."))])
        self.assertIn("created", results[0][1])
        doc = Document.objects.get(title="Cleaning the rig")
        self.assertEqual(doc.doc_type, "WI")
        self.assertEqual(doc.device, self.a)
        self.assertEqual(doc.owner, self.qa_a)
        self.assertEqual(doc.versions.get().status, "draft")

    def test_cannot_import_onto_a_device_you_are_not_on(self):
        results = doc_exchange.import_markdown(self.outsider, [("rig.md", self.md(device="DA"))])
        self.assertIn("not on", results[0][1])
        self.assertFalse(Document.objects.filter(title="Cleaning the rig").exists())

    def test_bad_front_matter_is_reported_and_skipped(self):
        results = doc_exchange.import_markdown(self.qa_a, [("x.md", self.md(type="NOPE"))])
        self.assertIn("type", results[0][1])

    def test_only_markdown_or_zip_is_accepted(self):
        from .services import TransitionError
        with self.assertRaises(TransitionError):
            doc_exchange.import_markdown(self.qa_a, [("x.pdf", b"%PDF")])

    def test_exported_document_comes_back_as_a_revision(self):
        doc = effective_doc(self.a, self.qa_a, title="Round trip",
                            data=self.md(title="Round trip", type="SOP", device="DA"))
        exported = doc_exchange.export_files(self.qa_a)
        name = next(p for p in exported if p.endswith(f"{doc.number}.md"))
        results = doc_exchange.import_markdown(self.qa_a, [(os.path.basename(name),
                                                            exported[name])])
        self.assertIn("Draft revision", results[0][1])
        self.assertEqual(Document.objects.filter(title="Round trip").count(), 1)
        self.assertIsNotNone(doc.open_version)

    def test_zip_of_markdown_imports_each_file(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("one.md", self.md(title="One"))
            zf.writestr("two.md", self.md(title="Two"))
            zf.writestr("notes.txt", b"ignored")
        results = doc_exchange.import_markdown(self.qa_a, [("docs.zip", buf.getvalue())])
        self.assertEqual(len(results), 2)
        self.assertTrue(Document.objects.filter(title="Two").exists())

    def test_import_page_creates_documents(self):
        self.client.force_login(self.qa_a)
        upload = io.BytesIO(self.md(title="Page import"))
        upload.name = "page.md"
        resp = self.client.post(reverse("qms:document_import"), {"files": upload})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Document.objects.filter(title="Page import").exists())


@override_settings(MEDIA_ROOT=MEDIA)
class GitSyncTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="qms-test-repo-")
        subprocess.run(["git", "-C", self.repo, "init", "-q"], check=True)
        self.device = Device.objects.create(name="Device A", code="DA")
        self.qa = person("qa", self.device, wf.QA)
        self.doc = effective_doc(self.device, self.qa)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def commits(self):
        out = subprocess.run(["git", "-C", self.repo, "rev-list", "--count", "HEAD"],
                             capture_output=True, text=True)
        return int(out.stdout.strip()) if out.returncode == 0 else 0

    def test_commits_changes_and_stays_quiet_when_nothing_changed(self):
        first = doc_exchange.sync_git(self.repo)
        self.assertTrue(first["committed"])
        self.assertEqual(self.commits(), 1)
        second = doc_exchange.sync_git(self.repo)
        self.assertFalse(second["committed"])
        self.assertEqual(self.commits(), 1)

    def test_new_effective_version_is_committed(self):
        doc_exchange.sync_git(self.repo)
        v2 = services.create_version(self.doc, self.qa, version="2.0", change_summary="Edit",
                                     file=ContentFile(b"# Version 2\n", name="calibration.md"))
        DocumentVersion.objects.filter(pk=v2.pk).update(status="effective",
                                                       effective_date=date.today())
        result = doc_exchange.sync_git(self.repo)
        self.assertTrue(result["committed"])
        with open(os.path.join(self.repo, "DA", "SOP",
                               f"{self.doc.number} calibration-of-test-rigs",
                               f"{self.doc.number}.md"), encoding="utf-8") as fh:
            self.assertIn("version: 2.0", fh.read())

    def test_withdrawn_document_is_removed_from_the_repository(self):
        doc_exchange.sync_git(self.repo)
        Document.objects.filter(pk=self.doc.pk).update(obsolete=True)
        result = doc_exchange.sync_git(self.repo)
        self.assertTrue(result["committed"])
        self.assertFalse(os.path.exists(os.path.join(self.repo, "DA", "SOP")))

    def test_refuses_a_folder_that_is_not_a_clone(self):
        plain = tempfile.mkdtemp(prefix="qms-test-plain-")
        try:
            with self.assertRaises(ValueError):
                doc_exchange.sync_git(plain)
        finally:
            shutil.rmtree(plain, ignore_errors=True)


@override_settings(MEDIA_ROOT=MEDIA)
class ReviewReminderTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.device = Device.objects.create(name="Device A", code="DA")
        self.owner = person("owner", self.device, wf.ENGINEER)
        self.qa = person("qa", self.device, wf.QA)

    def test_one_email_per_stage_and_again_when_the_date_changes(self):
        doc = effective_doc(self.device, self.owner, review_in=5)  # inside the 7-day stage
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(notifications.review_reminders(), 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(notifications.review_reminders(), 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(doc.number, mail.outbox[0].subject)
        self.assertIn(self.owner.email, mail.outbox[0].to)
        self.assertIn(self.qa.email, mail.outbox[0].to)
        self.assertEqual(ReviewReminder.objects.filter(document=doc).count(), 1)

    def test_no_email_far_from_the_review_date(self):
        effective_doc(self.device, self.owner, review_in=200)
        self.assertEqual(notifications.review_reminders(), 0)

    def test_overdue_document_is_reported_once(self):
        doc = effective_doc(self.device, self.owner, review_in=-3)
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            notifications.review_reminders()
            notifications.review_reminders()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("overdue", mail.outbox[0].subject)
        self.assertTrue(ReviewReminder.objects.filter(document=doc, stage=0).exists())
