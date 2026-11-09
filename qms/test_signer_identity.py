"""Who may sign on production: an identity confirmed by an institutional single sign-on
provider (finding F6). Off unless QMS_SIGNER_SSO_PROVIDERS is set."""
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User
from django.test import override_settings

from . import workflow as wf
from .models import Signature
from .services import TransitionError, perform_transition
from .tests import PW, Base

PRODUCTION = {"QMS_SIGNER_SSO_PROVIDERS": ["microsoft", "google"],
              "QMS_SIGNER_EMAIL_DOMAINS": ["sheffield.ac.uk"]}


class SignerIdentityTests(Base):
    def reject(self, user):
        pr = self.new(wf.PROBLEM_REPORT)
        return perform_transition(pr, "reject", user, comment="Duplicate", password=PW)

    def connect(self, user, provider, email, verified=True):
        SocialAccount.objects.create(user=user, provider=provider, uid=f"{provider}-{user.pk}")
        EmailAddress.objects.create(user=user, email=email, verified=verified, primary=True)

    def test_without_the_setting_anyone_with_the_role_signs(self):
        self.assertEqual(self.reject(self.qa).status, "rejected")

    @override_settings(**PRODUCTION)
    def test_password_only_account_cannot_sign_even_as_superuser(self):
        with self.assertRaisesMessage(TransitionError, "confirmed by Microsoft or Google"):
            self.reject(self.qa)
        self.qa.is_superuser = True
        self.qa.save()
        with self.assertRaisesMessage(TransitionError, "Connected accounts"):
            self.reject(self.qa)
        self.assertFalse(Signature.objects.exists())

    @override_settings(**PRODUCTION)
    def test_other_providers_do_not_count(self):
        self.connect(self.qa, "github", "qa@sheffield.ac.uk")
        with self.assertRaises(TransitionError):
            self.reject(self.qa)

    @override_settings(**PRODUCTION)
    def test_allowed_provider_needs_a_verified_address_at_the_domain(self):
        self.connect(self.qa, "google", "qa.person@gmail.com")
        with self.assertRaisesMessage(TransitionError, "sheffield.ac.uk"):
            self.reject(self.qa)
        EmailAddress.objects.create(user=self.qa, email="qa@sheffield.ac.uk", verified=False)
        with self.assertRaises(TransitionError):
            self.reject(self.qa)
        EmailAddress.objects.filter(email="qa@sheffield.ac.uk").update(verified=True)
        self.assertEqual(self.reject(self.qa).status, "rejected")

    @override_settings(**PRODUCTION)
    def test_institutional_account_signs_and_wrong_secret_still_fails(self):
        self.connect(self.qa, "microsoft", "qa@dept.sheffield.ac.uk")
        pr = self.new(wf.PROBLEM_REPORT)
        with self.assertRaisesMessage(TransitionError, "not recognised"):
            perform_transition(pr, "reject", self.qa, comment="Duplicate", password="wrong")
        self.assertEqual(self.reject(self.qa).status, "rejected")

    @override_settings(QMS_SIGNER_SSO_PROVIDERS=["microsoft"], QMS_SIGNER_EMAIL_DOMAINS=[])
    def test_domains_are_optional(self):
        other = User.objects.get(username="qa2")
        self.connect(other, "microsoft", "someone@example.org")
        self.assertEqual(self.reject(other).status, "rejected")
