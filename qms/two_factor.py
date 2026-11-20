"""Two-factor sign-in: an authenticator app (TOTP) and a code completed in each session.

Always on for the post-market surveillance pages (/pms/). On the rest of SAMD_QMS it is on only
when QMS_TWO_FACTOR is set, which the production deployment does. Sign-in by password or by
single sign-on both pass through here, so the rule holds whichever way someone came in.
"""
from urllib.parse import urlencode

from allauth.account.internal.flows.login import get_authentication_records
from allauth.mfa.utils import is_mfa_enabled
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

PMS_PREFIX = "/pms/"
# Pages anyone may open without completing a code: sign-in and sign-out, the sign-in library
# (where authenticators are set up), health checks, the account request page and static files.
# The surveillance registration pages are for people with no account yet.
OPEN_PREFIXES = ("/login/", "/logout/", "/accounts/", "/healthz", "/request-access/",
                 "/static/", "/media/", "/pms/register/", "/pms/activation-sent/",
                 "/pms/activate/")


class TwoFactorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._needs_two_factor(request):
            response = self._second_factor_step(request)
            if response is not None:
                return response
        return self.get_response(request)

    @staticmethod
    def _needs_two_factor(request):
        path = request.path
        if not request.user.is_authenticated or path.startswith(OPEN_PREFIXES):
            return False
        return path.startswith(PMS_PREFIX) or settings.QMS_TWO_FACTOR

    @staticmethod
    def _second_factor_step(request):
        user = request.user
        query = urlencode({"next": request.get_full_path()})
        if not is_mfa_enabled(user, types=["totp"]):
            return redirect(f"{reverse('mfa_activate_totp')}?{query}")
        records = get_authentication_records(request, user)
        if not any(record.get("method") == "mfa" for record in records):
            return redirect(f"{reverse('mfa_reauthenticate')}?{query}")
        return None
