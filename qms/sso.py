"""
Single sign-on through Google, Microsoft, LinkedIn, ORCID and GitHub (django-allauth).

Rules, because these are public identity providers:
  * No self-service local sign-up.
  * An SSO login joins an existing account when the provider reports a *verified* email that
    matches it (pre-provisioned users).
  * A brand-new account is created only for verified emails in QMS_SSO_ALLOWED_DOMAINS.
  * A new account has no QMS role, so it can see nothing until QA or an admin assigns a role.
  * ORCID does not share email addresses: connect ORCID from "Connected accounts" while
    signed in another way, then use it to sign in.
"""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings


def _verified_emails(sociallogin):
    return [e.email.lower() for e in sociallogin.email_addresses if e.verified and e.email]


def email_domain_allowed(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].lower()
    allowed = [d.lower().lstrip("@") for d in settings.QMS_SSO_ALLOWED_DOMAINS]
    return any(domain == d or domain.endswith("." + d) for d in allowed)


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False  # local accounts are created by an administrator


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return any(email_domain_allowed(e) for e in _verified_emails(sociallogin))

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        if not user.username:
            email = (data.get("email") or "").split("@")[0]
            user.username = email or f"{sociallogin.account.provider}-{sociallogin.account.uid}"
        return user
