"""Where Django admin may be used (finding F7).

On production, Caddy does not serve /admin/ on the public site; administrators reach it through
an SSH tunnel to https://localhost:8443. QMS_ADMIN_HOSTS lists the hosts admin answers on
(production: "localhost:8443"); on any other host /admin/ is a 404 here too, in case the proxy
is misconfigured, and the header's Admin link is hidden. Empty (development) = everywhere.
"""
from django.conf import settings
from django.http import Http404


def admin_allowed(request) -> bool:
    hosts = settings.QMS_ADMIN_HOSTS
    return not hosts or request.get_host().lower() in hosts


class AdminHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/") and not admin_allowed(request):
            raise Http404
        return self.get_response(request)
