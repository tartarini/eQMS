"""In-app help: every page links to a real help section and every form field has help."""
import re
from pathlib import Path

from django import forms as django_forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from . import forms as F
from . import help as H
from . import workflow as wf

PW = "test-pass-123"
TEMPLATES = Path(__file__).resolve().parent / "templates"


def app_forms():
    """Every form class users fill in, with an instance to inspect."""
    out = [(f"record:{t}", F.record_form_class(t)()) for t, _ in wf.RECORD_TYPES]
    for name in ["SignForm", "LinkForm", "AttachmentForm", "DocumentForm", "VersionForm",
                 "TrainingRequirementForm", "HazardForm", "RiskControlForm", "SupplierForm",
                 "SupplierEvaluationForm", "SoupItemForm", "DeviceForm"]:
        out.append((name, getattr(F, name)()))
    out.append(("TeamMemberForm", F.TeamMemberForm(device=None)))
    out.append(("TeamRolesForm", F.TeamRolesForm()))
    from .models import Device
    out.append(("InvitationForm", F.InvitationForm(devices=[Device(pk=1, name="X", code="X")])))
    out.append(("SigningPinForm", F.SigningPinForm(user=User(password="x"))))
    out.append(("AuthenticationForm", AuthenticationForm()))
    return out


def url_names():
    """SAMD_QMS's own pages, plus the sign-in library pages it links to."""
    names = {"socialaccount_connections"}
    for p in get_resolver().url_patterns:
        if isinstance(p, URLResolver) and p.namespace == "qms":
            names |= {q.name for q in p.url_patterns if isinstance(q, URLPattern) and q.name}
        elif isinstance(p, URLPattern) and p.name and p.name != "healthz":
            names.add(p.name)
    return names


class HelpContentTests(TestCase):
    def test_every_page_has_a_help_section_that_exists(self):
        missing = sorted(url_names() - set(H.PAGE_HELP))
        self.assertEqual(missing, [], "Add these URL names to qms.help.PAGE_HELP")
        for name, (topic, anchor) in H.PAGE_HELP.items():
            if topic:
                self.assertIn(topic, H.TOPIC_TITLES, name)
            if anchor:
                self.assertIn(anchor, H.topic_anchors(topic), f"{name} -> {topic}#{anchor}")

    def test_every_form_field_has_help_and_a_reference_entry(self):
        for name, form in app_forms():
            for field in form.fields:
                found = H.field_help(form, field)
                self.assertIsNotNone(found, f"No help for {name}.{field} "
                                            f"(group '{H.group_for_form(form)}')")
                label, text, url = found
                self.assertGreater(len(text), 15, f"{name}.{field}")
                topic, anchor = url.split("/help/")[1].rstrip("/").split("/#")
                self.assertIn(anchor, H.topic_anchors(topic), url)

    def test_plain_html_fields_use_registered_help(self):
        uses = []
        for path in TEMPLATES.rglob("*.html"):
            uses += re.findall(r'{%\s*help_for\s+"([^"]+)"\s+"([^"]+)"\s*%}', path.read_text())
        self.assertGreater(len(uses), 10)
        for group, field in uses:
            self.assertIsNotNone(H.group_field_help(group, field), f"{group}.{field}")

    def test_every_plain_input_in_templates_has_a_help_icon(self):
        for path in TEMPLATES.joinpath("qms").glob("*.html"):
            lines = path.read_text().splitlines()
            for i, line in enumerate(lines):
                if re.search(r"<(input|textarea|select)\b", line) and "hidden" not in line \
                        and 'name="device" onchange' not in line:
                    self.assertRegex(lines[i - 1] + line, r"help_for|help_icon",
                                     f"{path.name}: field without a help icon: {line.strip()}")

    def test_topics_render_with_their_field_reference(self):
        for slug, _title, _summary in H.TOPICS:
            html, toc = H.render_topic(slug)
            self.assertGreater(len(html), 500, slug)
        self.assertIn('id="field-record-date-aware"', H.render_topic("records")[0])
        self.assertIn("2 days", H.render_topic("records")[0])  # values come from settings

    def test_help_has_no_device_specific_names(self):
        for path in list((Path(H.HELP_DIR)).glob("*.md")) + list(TEMPLATES.rglob("*.html")):
            self.assertNotIn("cognospeak", path.read_text().lower(), path.name)


class HelpPageTests(TestCase):
    def setUp(self):
        from .test_modules import make_user
        self.user = make_user("helpuser", wf.ENGINEER)

    def test_help_is_open_without_signing_in(self):
        self.assertEqual(self.client.get(reverse("qms:help_index")).status_code, 200)
        resp = self.client.get(reverse("qms:help_topic", args=["risk"]))
        self.assertContains(resp, "Accept the residual risk")
        self.assertContains(resp, 'aria-current="page"')
        self.assertEqual(self.client.get("/help/no-such-topic/").status_code, 404)

    def test_header_links_to_the_help_for_the_current_page(self):
        resp = self.client.get(reverse("login"))
        self.assertContains(resp, 'class="help-link" href="/help/getting-started/#signing-in"')
        self.client.login(username="helpuser", password=PW)
        for url, expected in [(reverse("qms:record_list"), "/help/records/"),
                              (reverse("qms:hazard_create"), "/help/risk/#add-and-control-a-hazard"),
                              (reverse("socialaccount_connections"),
                               "/help/getting-started/#connected-accounts")]:
            self.assertContains(self.client.get(url), f'class="help-link" href="{expected}"')

    def test_each_visible_form_field_gets_an_icon(self):
        self.client.login(username="helpuser", password=PW)
        resp = self.client.get(reverse("qms:record_create", args=[wf.PROBLEM_REPORT]))
        form = resp.context["form"]
        self.assertEqual(resp.content.decode().count('class="help-icon" popovertarget='),
                         len(form.visible_fields()))
        self.assertContains(resp, 'aria-label="Help: Software item"')
        self.assertContains(resp, 'href="/help/records/#field-record-software-item"')

    def test_icon_markup_is_accessible_and_escaped(self):
        from django.template import Context, Template
        html = Template('{% load qms_help %}{% help_for "sign" "password" %}'
                        '{% help_for "nope" "nope" %}').render(Context())
        self.assertIn('type="button"', html)
        self.assertIn('aria-label="Help: Password or signing PIN"', html)
        pop = re.search(r'popovertarget="([^"]+)"', html).group(1)
        self.assertIn(f'id="{pop}" class="help-pop" popover', html)
        self.assertEqual(html.count("help-icon"), 1)  # unknown help renders nothing

    def test_pages_render_for_qa_with_help_link(self):
        self.user.groups.add(Group.objects.get_or_create(name=wf.QA)[0])
        self.client.login(username="helpuser", password=PW)
        for name in ["dashboard", "device_list", "document_list", "my_training",
                     "supplier_list", "training_matrix", "signing_pin"]:
            self.assertContains(self.client.get(reverse(f"qms:{name}")), 'class="help-link"',
                                msg_prefix=name)
