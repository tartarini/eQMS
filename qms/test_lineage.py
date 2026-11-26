"""Document lineage: links from a document version to other versions (any document the person
can see), removing a link while the version is open, and the lineage page with each version's
changes, approvers and links."""
import tempfile

from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from . import services
from . import workflow as wf
from .forms import DocumentLinkForm
from .models import AuditEvent, Device, Document, DocumentLink, ImmutableError
from .services import TransitionError
from .test_roles import PW, member, person

MEDIA = tempfile.mkdtemp(prefix="qms-test-lineage-")


@override_settings(MEDIA_ROOT=MEDIA)
class LineageBase(TestCase):
    def setUp(self):
        for r in wf.ROLES + (wf.ALL_DEVICES,):
            Group.objects.get_or_create(name=r)
        self.a = Device.objects.create(name="Device A", code="DA")
        self.b = Device.objects.create(name="Device B", code="DB")
        self.eng = person("engineer_a", wf.ENGINEER)
        member(self.a, self.eng, wf.ENGINEER)
        self.qa = person("qa_a", wf.QA)
        member(self.a, self.qa, wf.QA)
        self.outsider = person("engineer_b", wf.ENGINEER)
        member(self.b, self.outsider, wf.ENGINEER)
        self.qa_b = person("qa_b", wf.QA)
        member(self.b, self.qa_b, wf.QA)
        self.spec = Document.objects.create(title="Software specification", doc_type="SPEC",
                                            device=self.a, owner=self.eng)
        self.spec_v1 = self.effective(self.spec, "spec-1.txt", b"specification one")
        self.plan = Document.objects.create(title="Test plan", doc_type="PLAN", device=self.a,
                                            owner=self.eng)
        self.plan_v1 = self.effective(self.plan, "plan-1.txt", b"plan one")

    def draft(self, doc, name, data, version="1.0", summary="Change", author=None):
        return services.create_version(doc, author or self.eng, version=version,
                                       change_summary=summary,
                                       file=ContentFile(data, name=name))

    def effective(self, doc, name, data, version="1.0", summary="First issue", author=None,
                  approver=None):
        author, approver = author or self.eng, approver or self.qa
        v = self.draft(doc, name, data, version=version, summary=summary, author=author)
        services.submit_version(v, author)
        services.approve_version(v, approver, PW, "Reviewed")
        services.make_effective(v, approver)
        return v


class LinkTests(LineageBase):
    def test_engineer_links_a_version_to_another_document_version(self):
        link = services.link_versions(self.plan_v1, self.spec_v1, "implements", self.eng)
        self.assertEqual(str(link), "PLAN-001 v1.0 implements SPEC-001 v1.0")
        event = AuditEvent.for_object(self.plan_v1).get(action="link")
        self.assertEqual(event.actor_name, "engineer_a")
        self.assertIn("SPEC-001 v1.0", event.change_lines[0][1])

    def test_a_version_cannot_be_linked_to_itself(self):
        with self.assertRaisesMessage(TransitionError, "A version cannot be linked to itself."):
            services.link_versions(self.spec_v1, self.spec_v1, "relates_to", self.eng)

    def test_the_same_link_cannot_be_added_twice(self):
        services.link_versions(self.plan_v1, self.spec_v1, "relates_to", self.eng)
        with self.assertRaisesMessage(TransitionError, "That link already exists."):
            services.link_versions(self.plan_v1, self.spec_v1, "relates_to", self.eng)

    def test_a_document_on_another_team_cannot_be_linked_to(self):
        other = Document.objects.create(title="Secret B spec", doc_type="SPEC", device=self.b,
                                        owner=self.outsider)
        other_v = self.effective(other, "b.txt", b"device B", author=self.outsider,
                                 approver=self.qa_b)
        with self.assertRaisesMessage(TransitionError, "Choose a document you can see."):
            services.link_versions(self.plan_v1, other_v, "relates_to", self.eng)

    def test_a_person_outside_the_source_team_cannot_link(self):
        with self.assertRaisesMessage(TransitionError, "You are not on this device's team."):
            services.link_versions(self.plan_v1, self.spec_v1, "relates_to", self.outsider)

    def test_the_form_offers_only_versions_the_person_can_see(self):
        other = Document.objects.create(title="Secret B spec", doc_type="SPEC", device=self.b,
                                        owner=self.outsider)
        self.effective(other, "b.txt", b"device B", author=self.outsider, approver=self.qa_b)
        form = DocumentLinkForm(user=self.eng, source=self.plan_v1)
        offered = set(form.fields["target"].queryset)
        self.assertIn(self.spec_v1, offered)
        self.assertNotIn(self.plan_v1, offered)
        self.assertFalse(any(v.document.device == self.b for v in offered))

    def test_a_link_can_be_removed_while_the_version_is_a_draft(self):
        draft = self.draft(self.plan, "plan-2.txt", b"plan two", version="2.0")
        link = services.link_versions(draft, self.spec_v1, "refers_to", self.eng)
        services.unlink_versions(link, self.eng)
        self.assertFalse(DocumentLink.objects.filter(pk=link.pk).exists())
        self.assertTrue(AuditEvent.for_object(draft).filter(action="unlink").exists())

    def test_links_on_an_approved_version_are_locked(self):
        link = services.link_versions(self.plan_v1, self.spec_v1, "relates_to", self.eng)
        with self.assertRaisesMessage(TransitionError, "its links are locked."):
            services.unlink_versions(link, self.eng)
        with self.assertRaises(ImmutableError):
            link.delete()
        self.assertTrue(DocumentLink.objects.filter(pk=link.pk).exists())


class LineageViewTests(LineageBase):
    def test_lineage_shows_each_version_in_order_with_what_changed_and_who_approved(self):
        v2 = self.draft(self.spec, "spec-2.txt", b"specification two", version="2.0",
                        summary="Adds the alarm limits")
        services.submit_version(v2, self.eng)
        services.approve_version(v2, self.qa, PW, "Reviewed")
        self.client.force_login(self.eng)
        content = self.client.get(reverse("qms:document_lineage", args=["SPEC-001"])).content.decode()
        self.assertLess(content.index("v1.0"), content.index("v2.0"))
        self.assertIn("First file: spec-1.txt.", content)
        self.assertIn("File replaced: spec-1.txt → spec-2.txt.", content)
        self.assertIn("Adds the alarm limits", content)
        self.assertIn("qa_a · Document approval", content)

    def test_an_unchanged_file_is_reported_as_unchanged(self):
        self.draft(self.spec, "spec-1.txt", b"specification one", version="2.0")
        self.client.force_login(self.eng)
        content = self.client.get(reverse("qms:document_lineage", args=["SPEC-001"])).content.decode()
        self.assertIn("File unchanged.", content)

    def test_a_linked_version_shows_the_approvers_of_that_version(self):
        services.link_versions(self.plan_v1, self.spec_v1, "implements", self.eng)
        self.client.force_login(self.eng)
        content = self.client.get(reverse("qms:document_lineage", args=["PLAN-001"])).content.decode()
        self.assertIn("This version implements", content)
        self.assertIn("SPEC-001 v1.0", content)
        self.assertIn("Approved by qa_a", content)

    def test_links_to_documents_the_person_cannot_see_are_hidden(self):
        secret = Document.objects.create(title="Secret B spec", doc_type="SPEC", device=self.b,
                                         owner=self.outsider)
        secret_v = self.effective(secret, "b.txt", b"device B", author=self.outsider,
                                  approver=self.qa_b)
        DocumentLink.objects.create(source=self.plan_v1, target=secret_v, link_type="relates_to")
        self.client.force_login(self.eng)
        resp = self.client.get(reverse("qms:document_lineage", args=["PLAN-001"]))
        self.assertNotContains(resp, "Secret B spec")
        self.assertNotContains(resp, secret.number)

    def test_lineage_needs_access_to_the_document(self):
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(reverse("qms:document_lineage", args=["SPEC-001"])).status_code, 404)

    def test_signed_out_users_are_sent_to_sign_in(self):
        resp = self.client.get(reverse("qms:document_lineage", args=["SPEC-001"]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_document_page_links_to_the_lineage(self):
        self.client.force_login(self.eng)
        url = reverse("qms:document_lineage", args=["SPEC-001"])
        self.assertContains(self.client.get(reverse("qms:document_detail", args=["SPEC-001"])),
                            f'href="{url}"')

    def test_post_adds_a_link_from_the_lineage_page(self):
        self.client.force_login(self.eng)
        prefix = f"v{self.plan_v1.pk}"
        resp = self.client.post(reverse("qms:version_link_add", args=[self.plan_v1.pk]), {
            f"{prefix}-target": self.spec_v1.pk, f"{prefix}-link_type": "refers_to"})
        self.assertRedirects(resp, reverse("qms:document_lineage", args=["PLAN-001"]))
        self.assertTrue(DocumentLink.objects.filter(source=self.plan_v1, target=self.spec_v1,
                                                    link_type="refers_to").exists())

    def test_post_removes_a_link_while_the_version_is_a_draft(self):
        draft = self.draft(self.plan, "plan-2.txt", b"plan two", version="2.0")
        link = services.link_versions(draft, self.spec_v1, "relates_to", self.eng)
        self.client.force_login(self.eng)
        self.client.post(reverse("qms:document_link_remove", args=[link.pk]))
        self.assertFalse(DocumentLink.objects.filter(pk=link.pk).exists())

    def test_a_person_outside_the_team_cannot_add_links(self):
        self.client.force_login(self.outsider)
        resp = self.client.post(reverse("qms:version_link_add", args=[self.plan_v1.pk]), {
            f"v{self.plan_v1.pk}-target": self.spec_v1.pk,
            f"v{self.plan_v1.pk}-link_type": "relates_to"})
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(DocumentLink.objects.exists())

    def test_adding_a_link_needs_a_post(self):
        self.client.force_login(self.eng)
        self.assertEqual(
            self.client.get(reverse("qms:version_link_add", args=[self.plan_v1.pk])).status_code,
            405)
