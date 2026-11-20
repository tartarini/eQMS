"""SAMD_QMS at the root of the platform: it provides the landing page, sign-in and accounts.

Other applications mount under their own prefix, e.g. path("boss/", include("boss.urls")).
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from qms.health import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/", include("allauth.urls")),
    path("pms/", include("pms.urls")),
    path("", include("qms.urls")),
]
