"""Inviting people by email: who may invite, the emailed link, expiry, and accepting."""
import hashlib
import re
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import invitations
from . import workflow as wf
from .models import AuditEvent, Device, DeviceMembership, Invitation
from .roles import device_roles
from .services import TransitionError
from .test_modules import PROVIDERS
from .test_roles import PW, member, person


@override_settings(QMS_BASE_URL="https://qms.example.org")
class InvitationTests(TestCase):
    def setUp(self):
        for r in wf.ROLES + (wf.ALL_DEVICES,):
            Group.objects.get_or_create(name=r)
        self.a = Device.objects.create(name="Device A", code="DA")
        self.b = Device.objects.create(name="Device B", code="DB")
        self.admin = person("admin")                     # Device admin on A and B
        member(self.a, self.admin, wf.DEVICE_ADMIN)
        member(self.b, self.admin, wf.DEVICE_ADMIN, wf.ENGINEER)
        self.qa_a = person("qa_a")
        member(self.a, self.qa_a, wf.QA)
        self.eng_a = person("eng_a")
        member(self.a, self.eng_a, wf.ENGINEER)

    def invite(self, email="new.person@example.org", grants=None, days=None, by=None):
        with self.captureOnCommitCallbacks(execute=True):
            return invitations.create_invitation(
                by or self.admin, email,
                grants if grants is not None else {self.a: [wf.QA], self.b: [wf.ENGINEER]},
                days)

    def link(self):
        return re.search(r"https://qms\.example\.org(/invite/[^\s]+/)", mail.outbox[-1].body).group(1)

    # --- sending ---------------------------------------------------------------------------

    def test_invitation_email_lists_devices_roles_and_expiry(self):
        inv, token = self.invite(days=7)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["new.person@example.org"])
        self.assertIn("Device A (DA): QA", msg.body)
        self.assertIn("Device B (DB): Engineer", msg.body)
        self.assertIn(f"Accept by {inv.expires_at:%d %b %Y %H:%M} UTC", msg.body)
        self.assertIn(f"/invite/{token}/", msg.body)
        self.assertAlmostEqual(inv.expires_at, timezone.now() + timedelta(days=7),
                               delta=timedelta(minutes=1))
        self.assertEqual(AuditEvent.for_object(inv).first().comment, "Invitation sent")

    def test_only_the_token_hash_is_stored(self):
        inv, token = self.invite()
        self.assertEqual(inv.token_hash, hashlib.sha256(token.encode()).hexdigest())
        self.assertNotIn(token, str(Invitation.objects.filter(pk=inv.pk).values().get()))
        self.assertGreaterEqual(len(token), 40)

    def test_you_can_only_grant_roles_on_teams_you_manage(self):
        with self.assertRaises(TransitionError) as ctx:
            self.invite(by=self.qa_a)                  # QA on A only, not on B
        self.assertIn("You can't invite people to Device B", ctx.exception.errors[0])
        inv, _ = self.invite(by=self.qa_a, grants={self.a: [wf.CLINICAL_SAFETY]})
        self.assertEqual(inv.grants, [{"device_id": self.a.pk, "device": "DA",
                                       "roles": [wf.CLINICAL_SAFETY]}])
        with self.assertRaises(TransitionError):
            self.invite(email="x@example.org", by=self.eng_a, grants={self.a: [wf.ENGINEER]})

    def test_input_is_checked(self):
        for kwargs, message in [
                ({"email": "not-an-email"}, "valid email"),
                ({"grants": {self.a: []}}, "at least one role"),
                ({"days": 31}, "between 1 and 30"),
        ]:
            with self.assertRaises(TransitionError) as ctx:
                self.invite(**kwargs)
            self.assertTrue(any(message in e for e in ctx.exception.errors), kwargs)

    def test_one_pending_invitation_per_person_and_device(self):
        self.invite()
        with self.assertRaises(TransitionError) as ctx:
            self.invite(email="NEW.person@example.org", grants={self.a: [wf.ENGINEER]})
        self.assertIn("already has a pending invitation", ctx.exception.errors[0])

    # --- accepting ------------------------------------------------------------------------

    @override_settings(SOCIALACCOUNT_PROVIDERS=PROVIDERS)
    def test_new_person_registers_only_with_single_sign_on(self):
        self.invite()
        url = self.link()
        page = self.client.get(url)
        self.assertContains(page, "You're invited to SAMD_QMS")
        self.assertContains(page, "Device A (DA)")
        self.assertContains(page, "Register with single sign-on")
        for name in ("Google", "Microsoft", "GitHub", "LinkedIn"):
            self.assertContains(page, f"Continue with {name}")
        self.assertNotContains(page, "Continue with ORCID")  # gives no email to match
        self.assertNotContains(page, 'type="password"')
        self.assertNotContains(page, 'name="username"')
        # a local account can't be created by posting to the link
        resp = self.client.post(url, {"username": "newbie", "first_name": "New",
                                      "last_name": "Person", "password1": "c0rrect-Horse-77",
                                      "password2": "c0rrect-Horse-77"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(email="new.person@example.org").exists())
        self.assertEqual(Invitation.objects.get().status, "pending")

    @override_settings(SOCIALACCOUNT_PROVIDERS={})
    def test_without_single_sign_on_nobody_can_register_from_an_invitation(self):
        self.invite()
        page = self.client.get(self.link())
        self.assertContains(page, "Single sign-on isn't available")
        self.assertNotContains(page, "Continue with")
        self.assertNotContains(page, 'type="password"')

    @override_settings(SOCIALACCOUNT_PROVIDERS=PROVIDERS, QMS_SSO_ALLOWED_DOMAINS=[])
    def test_new_person_registers_with_single_sign_on_and_joins_each_team(self):
        from allauth.account.models import EmailAddress
        from allauth.core import context
        from allauth.socialaccount.helpers import complete_social_login
        from allauth.socialaccount.models import SocialAccount, SocialLogin
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.backends.db import SessionStore
        from django.test import RequestFactory
        inv, _ = self.invite()
        url = self.link()
        self.client.get(url)                                  # remembers the invitation

        def sso(email, uid):
            request = RequestFactory().get("/accounts/google/login/callback/")
            request.session = SessionStore(self.client.session.session_key)
            request.user = AnonymousUser()
            request._messages = FallbackStorage(request)
            from allauth.socialaccount.adapter import get_adapter
            sociallogin = SocialLogin(
                provider=get_adapter().get_provider(request, "google"),
                user=User(first_name="New", last_name="Person", email=email),
                account=SocialAccount(provider="google", uid=uid),
                email_addresses=[EmailAddress(email=email, verified=True, primary=True)])
            sociallogin.state = {"process": "login", "next": url}
            with context.request_context(request):
                resp = complete_social_login(request, sociallogin)
            request.session.save()
            return resp

        # another address is refused, even with the link open in this browser
        sso("someone.else@example.org", "g-2")
        self.assertFalse(User.objects.filter(email="someone.else@example.org").exists())
        # the invited address registers, without a usable password
        self.assertEqual(sso("new.person@example.org", "g-1").status_code, 302)
        user = User.objects.get(socialaccount__uid="g-1")
        self.assertEqual(user.email, "new.person@example.org")
        self.assertFalse(user.has_usable_password())
        self.client.force_login(user)
        self.assertContains(self.client.get(url), "Accept as New Person")
        resp = self.client.post(url)
        self.assertRedirects(resp, reverse("qms:device_detail", args=["DA"]))
        self.assertEqual(device_roles(user, self.a), {wf.QA})
        self.assertEqual(device_roles(user, self.b), {wf.ENGINEER})
        inv.refresh_from_db()
        self.assertEqual((inv.status, inv.accepted_by), ("accepted", user))
        joined = AuditEvent.objects.filter(object_type="Device Membership", actor=user)
        self.assertEqual(joined.count(), 2)
        self.assertIn(inv.ref, joined.first().comment)
        # the link works once
        self.client.logout()
        self.assertContains(self.client.get(url), "already been used", status_code=410)

    def test_existing_account_signs_in_and_roles_are_added_not_replaced(self):
        existing = person("existing")
        existing.email = "new.person@example.org"
        existing.save()
        member(self.b, existing, wf.QA)
        self.invite()
        url = self.link()
        self.assertContains(self.client.get(url), "There's already an account")
        self.client.force_login(existing)
        self.assertContains(self.client.get(url), "Accept as")
        self.client.post(url)
        self.assertEqual(device_roles(existing, self.a), {wf.QA})
        self.assertEqual(device_roles(existing, self.b), {wf.QA, wf.ENGINEER})

    def test_another_account_cannot_accept(self):
        self.invite()
        url = self.link()
        self.client.force_login(self.eng_a)
        resp = self.client.post(url)
        self.assertContains(resp, "This invitation is for new.person@example.org")
        self.assertEqual(device_roles(self.eng_a, self.b), set())
        self.assertEqual(Invitation.objects.get().status, "pending")

    def test_expired_invitation_is_refused_until_resent(self):
        inv, _ = self.invite()
        old_url = self.link()
        Invitation.objects.filter(pk=inv.pk).update(expires_at=timezone.now() - timedelta(1))
        self.assertContains(self.client.get(old_url), "expired", status_code=410)
        with self.captureOnCommitCallbacks(execute=True):
            invitations.resend(Invitation.objects.get(pk=inv.pk), self.admin)
        new_url = self.link()
        self.assertNotEqual(old_url, new_url)
        self.assertEqual(self.client.get(old_url).status_code, 404)   # old link replaced
        self.assertContains(self.client.get(new_url), "You're invited to SAMD_QMS")
        self.assertIn("resent", AuditEvent.for_object(inv).last().comment)

    def test_revoked_invitation_cannot_be_used(self):
        inv, _ = self.invite()
        url = self.link()
        with self.assertRaises(TransitionError):
            invitations.revoke(inv, self.eng_a)       # not theirs, doesn't manage B
        invitations.revoke(inv, self.admin)
        self.assertContains(self.client.get(url), "withdrawn", status_code=410)
        with self.assertRaises(Exception):
            inv.email = "changed@example.org"
            inv.save()

    def test_grants_are_rechecked_when_accepted(self):
        inv, _ = self.invite(by=self.qa_a, grants={self.a: [wf.ENGINEER]})
        m = DeviceMembership.objects.get(device=self.a, user=self.qa_a)
        m.set_roles([wf.ENGINEER])                    # the inviter is no longer QA on A
        m.save()
        newbie = User.objects.create_user("n", email="new.person@example.org", password=PW)
        errors = invitations.acceptance_errors(inv, newbie)
        self.assertIn("no longer valid", errors[0])
        self.assertEqual(device_roles(newbie, self.a), set())

    def test_unknown_link_is_not_found(self):
        self.assertContains(self.client.get("/invite/not-a-real-token/"), "not found",
                            status_code=404)

    # --- pages and permissions -----------------------------------------------------------

    def test_invite_page_lists_only_managed_devices(self):
        self.client.force_login(self.qa_a)
        resp = self.client.get(reverse("qms:invitation_create") + "?device=DA")
        self.assertContains(resp, "Roles on Device A (DA)")
        self.assertNotContains(resp, "Device B")
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(reverse("qms:invitation_create") + "?device=DA", {
                "email": "x@example.org", f"roles_{self.a.pk}": [wf.ENGINEER],
                "expires_in_days": 10})
        self.assertRedirects(resp, reverse("qms:device_detail", args=["DA"]))
        self.assertEqual(len(mail.outbox), 1)
        self.client.force_login(self.eng_a)
        resp = self.client.get(reverse("qms:invitation_create"), follow=True)
        self.assertContains(resp, "Only Device admins and QA can invite people")

    def test_invitations_page_and_device_panel(self):
        self.invite()
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("qms:invitation_list"))
        self.assertContains(resp, "new.person@example.org")
        self.assertContains(resp, "Resend")
        self.assertContains(self.client.get(reverse("qms:device_detail", args=["DA"])),
                            "Invitations not yet accepted")
        self.client.force_login(self.eng_a)
        self.assertNotContains(self.client.get(reverse("qms:invitation_list")),
                               "new.person@example.org")

    def test_single_sign_on_signup_allowed_only_for_the_invited_address(self):
        from .sso import SocialAccountAdapter
        self.invite()
        self.client.get(self.link())                  # opening the link remembers it
        request = SimpleNamespace(session=self.client.session)

        def login(email, verified=True):
            return SimpleNamespace(email_addresses=[SimpleNamespace(email=email,
                                                                    verified=verified)])
        adapter = SocialAccountAdapter()
        with self.settings(QMS_SSO_ALLOWED_DOMAINS=[]):
            self.assertTrue(adapter.is_open_for_signup(request,
                                                       login("New.Person@example.org")))
            self.assertFalse(adapter.is_open_for_signup(request, login("other@example.org")))
            self.assertFalse(adapter.is_open_for_signup(
                request, login("new.person@example.org", verified=False)))
            self.assertFalse(adapter.is_open_for_signup(SimpleNamespace(session={}),
                                                        login("new.person@example.org")))
