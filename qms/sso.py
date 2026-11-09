"""
Single sign-on through Google, Microsoft, LinkedIn, ORCID and GitHub (django-allauth).

Rules, because these are public identity providers:
  * No self-service local sign-up.
  * An SSO login joins an existing account when the provider reports a *verified* email that
    matches it (pre-provisioned users).
  * A brand-new account is created only for verified emails in QMS_SSO_ALLOWED_DOMAINS, for
    the verified email of a pending invitation whose link was opened in this browser, or by an
    account request: this browser solved the captcha on /request-access/ in the last
    QMS_ACCESS_REQUEST_MINUTES and uses a provider in QMS_ACCESS_REQUEST_PROVIDERS (Google,
    Microsoft, LinkedIn, ORCID). See qms.access_requests.
  * A new account has no QMS role, so it can see nothing until QA or an admin assigns a role.
  * ORCID does not share email addresses: an account request collects one and confirms it by
    email. Otherwise connect ORCID from "Connected accounts" while signed in another way.
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
        emails = _verified_emails(sociallogin)
        if any(email_domain_allowed(e) for e in emails):
            return True
        from .invitations import pending_for_session
        invitation = pending_for_session(request)
        if invitation and invitation.email.lower() in emails:
            return True
        from . import access_requests
        return (access_requests.captcha_passed(request)
                and access_requests.provider_allowed(sociallogin.account.provider))

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        if not user.username:
            from allauth.account.adapter import get_adapter
            email = (data.get("email") or "").split("@")[0]
            user.username = get_adapter(request).generate_unique_username(
                [email, f"{sociallogin.account.provider}-{sociallogin.account.uid}", "user"])
        return user
