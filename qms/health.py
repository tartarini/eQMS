"""Unauthenticated health check for the reverse proxy, containers and monitoring."""
import os

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@never_cache
@require_GET
def healthz(request):
    """200 when the database answers and file storage is writable; 503 otherwise.

    Reveals nothing beyond the release label and commit: no data, no error details.
    """
    checks = {}
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        checks["database"] = "fail"
    media = str(settings.MEDIA_ROOT)
    checks["storage"] = "ok" if os.path.isdir(media) and os.access(media, os.W_OK) else "fail"
    ok = all(v == "ok" for v in checks.values())
    return JsonResponse({"status": "ok" if ok else "fail", "version": settings.QMS_VERSION,
                         "commit": settings.QMS_COMMIT, "checks": checks}, status=200 if ok else 503)
