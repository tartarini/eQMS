"""Roles held per device, the Device admin role, and moving from organisation-wide roles."""
from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from . import services
from . import workflow as wf
from .access import is_member
from .models import (AuditEvent, Device, DeviceMembership, Document, DocumentVersion, Record,
                     TrainingAssignment, TrainingRequirement)
from .roles import (all_roles, can_manage_team, device_roles, has_role, managed_devices,
                    users_with_roles)
from .services import TransitionError

PW = "test-pass-123"


def person(name, *org_roles):
    u = User.objects.create_user(name, email=f"{name}@example.org", password=PW)
    for r in org_roles:
        u.groups.add(Group.objects.get_or_create(name=r)[0])
    return u


def member(device, user, *roles):
    m = DeviceMembership(device=device, user=user)
    m.set_roles(roles)
    m.save()
    return m


class Base(TestCase):
    def setUp(self):
        for r in wf.ROLES + (wf.ALL_DEVICES,):
            Group.objects.get_or_create(name=r)
        self.a = Device.objects.create(name="Device A", code="DA")
        self.b = Device.objects.create(name="Device B", code="DB")
        self.mixed = person("mixed")                    # QA on A, Engineer on B
        member(self.a, self.mixed, wf.QA)
        member(self.b, self.mixed, wf.ENGINEER)
        self.eng_a = person("eng_a")
        member(self.a, self.eng_a, wf.ENGINEER)
        self.admin_a = person("admin_a")                # Device admin only, on A
        member(self.a, self.admin_a, wf.DEVICE_ADMIN)
        self.qa_b = person("qa_b")
        member(self.b, self.qa_b, wf.QA)


class PerDeviceRoleTests(Base):
    def test_roles_apply_only_on_their_device(self):
        self.assertEqual(device_roles(self.mixed, self.a), {wf.QA})
        self.assertEqual(device_roles(self.mixed, self.b), {wf.ENGINEER})
        self.assertTrue(has_role(self.mixed, [wf.QA], self.a))
        self.assertFalse(has_role(self.mixed, [wf.QA], self.b))
        self.assertTrue(has_role(self.mixed, [wf.QA]))          # QMS-wide: held anywhere
        self.assertEqual(all_roles(self.mixed), {wf.QA, wf.ENGINEER})

    def test_workflow_approval_checks_the_records_device(self):
        def released(device, author):
            r = Record.objects.create(device=device, record_type=wf.CHANGE_REQUEST,
                                      title="t", created_by=author, fix_version="1.0")
            Record.objects.filter(pk=r.pk).update(status="verified")
            r.refresh_from_db()
            return r
        on_a, on_b = released(self.a, self.eng_a), released(self.b, self.qa_b)
        services.perform_transition(on_a, "close", self.mixed, password=PW)
        on_a.refresh_from_db()
        self.assertEqual(on_a.status, "closed")
        with self.assertRaises(TransitionError) as ctx:
            services.perform_transition(on_b, "close", self.mixed, password=PW)
        self.assertIn("Requires role: QA on Device B.", ctx.exception.errors)

    def test_organisation_wide_role_applies_only_where_the_person_can_see(self):
        head = person("head", wf.QA)
        member(self.a, head)                            # on A's team with no device role
        self.assertTrue(has_role(head, [wf.QA], self.a))
        self.assertFalse(has_role(head, [wf.QA], self.b))  # not on B, no All-device access
        head.groups.add(Group.objects.get(name=wf.ALL_DEVICES))
        self.assertTrue(has_role(head, [wf.QA], self.b))

    def test_inactive_membership_or_retired_device_gives_no_role(self):
        m = DeviceMembership.objects.get(device=self.a, user=self.eng_a)
        m.active = False
        m.save()
        self.assertFalse(has_role(self.eng_a, [wf.ENGINEER], self.a))
        self.b.active = False
        self.b.save()
        self.assertEqual(all_roles(self.qa_b), set())

    def test_device_admin_manages_team_but_cannot_approve_or_open_records(self):
        self.assertTrue(can_manage_team(self.admin_a, self.a))
        self.assertFalse(can_manage_team(self.admin_a, self.b))
        self.assertFalse(can_manage_team(self.eng_a, self.a))
        self.assertEqual(managed_devices(self.mixed), [self.a])  # QA manages A, not B
        self.assertFalse(is_member(self.admin_a))        # no working role
        self.client.force_login(self.admin_a)
        self.assertContains(self.client.get(reverse("qms:record_list")), "Access pending",
                            status_code=403)
        resp = self.client.get(reverse("qms:device_detail", args=["DA"]))
        self.assertContains(resp, "Invite people")
        self.assertEqual(self.client.get(reverse("qms:device_detail", args=["DB"])).status_code,
                         404)

    def test_set_roles_validates_and_orders(self):
        m = DeviceMembership(device=self.a, user=self.qa_b)
        m.set_roles([wf.DEVICE_ADMIN, wf.ENGINEER])
        self.assertEqual(m.roles, "Engineer, Device admin")
        with self.assertRaises(ValueError):
            m.set_roles(["Superuser"])

    def test_emails_go_to_the_role_on_that_device(self):
        cso_a, cso_b = person("cso_a"), person("cso_b")
        member(self.a, cso_a, wf.CLINICAL_SAFETY)
        member(self.b, cso_b, wf.CLINICAL_SAFETY)
        self.assertEqual(users_with_roles([wf.CLINICAL_SAFETY], self.a), [cso_a])
        with self.captureOnCommitCallbacks(execute=True):
            Record(device=self.a, record_type=wf.INCIDENT, title="i",
                   created_by=self.eng_a).save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("cso_a@example.org", mail.outbox[0].to)
        self.assertNotIn("cso_b@example.org", mail.outbox[0].to)
        self.assertIn("mixed@example.org", mail.outbox[0].to)     # QA on A
        self.assertNotIn("qa_b@example.org", mail.outbox[0].to)

    def test_training_follows_the_role_on_the_documents_device(self):
        doc = Document(title="A procedure", doc_type="WI", device=self.a)
        doc.save()
        TrainingRequirement.objects.create(document=doc, group=Group.objects.get(name=wf.QA))
        DocumentVersion.objects.create(document=doc, version="1.0", status="effective",
                                       change_summary="First", author=self.eng_a)
        services.sync_training()
        trained = set(TrainingAssignment.objects.values_list("user__username", flat=True))
        self.assertEqual(trained, {"mixed"})         # QA on A; qa_b is QA on B only


class TeamPageTests(Base):
    def roles_url(self, device, user):
        return reverse("qms:team_roles",
                       args=[DeviceMembership.objects.get(device=device, user=user).pk])

    def test_device_admin_changes_roles_and_it_is_audited(self):
        self.client.force_login(self.admin_a)
        m = DeviceMembership.objects.get(device=self.a, user=self.eng_a)
        self.client.post(self.roles_url(self.a, self.eng_a),
                         {f"m{m.pk}-roles": [wf.ENGINEER, wf.CLINICAL_SAFETY]})
        m.refresh_from_db()
        self.assertEqual(m.role_list(), [wf.ENGINEER, wf.CLINICAL_SAFETY])
        event = AuditEvent.for_object(m).last()
        self.assertEqual(event.changes["roles"], ["Engineer", "Engineer, Clinical Safety Officer"])
        self.assertEqual(event.actor, self.admin_a)

    def test_nobody_changes_their_own_roles(self):
        self.client.force_login(self.mixed)
        m = DeviceMembership.objects.get(device=self.a, user=self.mixed)
        resp = self.client.post(self.roles_url(self.a, self.mixed),
                                {f"m{m.pk}-roles": [wf.QA, wf.DEVICE_ADMIN]}, follow=True)
        self.assertContains(resp, "You can&#x27;t change your own roles")
        m.refresh_from_db()
        self.assertEqual(m.role_list(), [wf.QA])

    def test_engineer_cannot_change_roles(self):
        self.client.force_login(self.eng_a)
        m = DeviceMembership.objects.get(device=self.a, user=self.mixed)
        self.client.post(self.roles_url(self.a, self.mixed), {f"m{m.pk}-roles": [wf.ENGINEER]})
        m.refresh_from_db()
        self.assertEqual(m.role_list(), [wf.QA])

    def test_a_team_keeps_someone_who_can_manage_it(self):
        self.client.force_login(self.admin_a)
        m = DeviceMembership.objects.get(device=self.a, user=self.mixed)
        self.client.post(self.roles_url(self.a, self.mixed), {f"m{m.pk}-roles": [wf.ENGINEER]})
        m.refresh_from_db()
        self.assertEqual(m.role_list(), [wf.ENGINEER])   # admin_a still manages A
        self.client.force_login(self.qa_b)
        only = DeviceMembership.objects.get(device=self.b, user=self.qa_b)
        other = DeviceMembership.objects.get(device=self.b, user=self.mixed)
        self.client.force_login(self.mixed)              # Engineer on B can't anyway
        self.client.post(reverse("qms:team_remove", args=[only.pk]))
        only.refresh_from_db()
        self.assertTrue(only.active)
        # QA on B tries to remove themselves as the last manager: refused
        self.client.force_login(self.qa_b)
        resp = self.client.post(reverse("qms:team_remove", args=[only.pk]), follow=True)
        self.assertContains(resp, "at least one Device admin or QA")
        only.refresh_from_db()
        self.assertTrue(only.active)
        self.assertTrue(other.active)

    def test_adding_an_existing_user_needs_roles(self):
        newbie = person("newbie")
        self.client.force_login(self.admin_a)
        self.client.post(reverse("qms:team_add", args=["DA"]), {"user": newbie.pk})
        self.assertFalse(DeviceMembership.objects.filter(user=newbie).exists())
        self.client.post(reverse("qms:team_add", args=["DA"]),
                         {"user": newbie.pk, "roles": [wf.ENGINEER, wf.DEVICE_ADMIN]})
        self.assertEqual(device_roles(newbie, self.a), {wf.ENGINEER, wf.DEVICE_ADMIN})
        events = AuditEvent.for_object(DeviceMembership.objects.get(user=newbie))
        self.assertEqual([e.action for e in events], ["create"])

    def test_team_panel_shows_roles_per_device(self):
        self.client.force_login(self.mixed)
        resp = self.client.get(reverse("qms:device_detail", args=["DB"]))
        self.assertContains(resp, "Roles on DB")
        self.assertNotContains(resp, "Invite people")      # Engineer on B
        resp = self.client.get(reverse("qms:device_detail", args=["DA"]))
        self.assertContains(resp, "Invite people")         # QA on A
        self.assertContains(resp, 'title="You can\'t change your own roles"')

    def test_device_creator_is_qa_and_device_admin(self):
        org_qa = person("org_qa", wf.QA)
        self.client.force_login(org_qa)
        self.client.post(reverse("qms:device_create"), {
            "name": "New", "code": "nw", "classification": "tbd",
            "regulatory_status": "development", "active": "on"})
        m = DeviceMembership.objects.get(device__code="NW", user=org_qa)
        self.assertEqual(m.role_list(), [wf.QA, wf.DEVICE_ADMIN])


class RoleMigrationTests(TransactionTestCase):
    """0004 copies each person's roles onto their teams and keeps every team manageable."""

    def test_roles_move_to_teams(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        before = [("qms", "0003_per_device_software_items")]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        apps = executor.loader.project_state(before).apps
        G, U = apps.get_model("auth", "Group"), apps.get_model("auth", "User")
        D, M = apps.get_model("qms", "Device"), apps.get_model("qms", "DeviceMembership")
        groups = {n: G.objects.get_or_create(name=n)[0]
                  for n in ("Engineer", "QA", "Clinical Safety Officer", "All-device access")}
        eng, qa, head, loner = (U.objects.create(username=n) for n in
                                ("eng", "qa", "head", "loner"))
        eng.groups.add(groups["Engineer"])
        qa.groups.add(groups["QA"], groups["Clinical Safety Officer"])
        head.groups.add(groups["QA"], groups["All-device access"])
        loner.groups.add(groups["Engineer"])
        d1, d2 = D.objects.create(name="One", code="ONE"), D.objects.create(name="Two", code="TWO")
        for d, users in ((d1, (eng, qa)), (d2, (eng, head))):
            for u in users:
                M.objects.create(device=d, user=u)

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes("qms"))
        roles = {(m.device.code, m.user.username): m.role_list()
                 for m in DeviceMembership.objects.select_related("device", "user")}
        self.assertEqual(roles[("ONE", "qa")], ["QA", "Clinical Safety Officer", "Device admin"])
        self.assertEqual(roles[("ONE", "eng")], ["Engineer"])
        self.assertEqual(roles[("TWO", "head")], ["QA", "Device admin"])
        self.assertEqual(roles[("TWO", "eng")], ["Engineer"])
        names = lambda n: set(User.objects.get(username=n).groups.values_list("name", flat=True))
        self.assertEqual(names("eng"), set())                     # now per device only
        self.assertEqual(names("qa"), set())
        self.assertEqual(names("head"), {"QA", "All-device access"})  # stays organisation-wide
        self.assertEqual(names("loner"), {"Engineer"})            # on no team: unchanged
        self.assertTrue(Group.objects.filter(name="Device admin").exists())
