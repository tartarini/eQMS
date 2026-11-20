"""A URLconf without the "login" URL (used by platform_host.tests)."""
from django.urls import include, path

urlpatterns = [path("", include("qms.urls"))]
