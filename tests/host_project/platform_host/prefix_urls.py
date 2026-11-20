"""SAMD_QMS mounted under /qms/ instead of the root (used by platform_host.tests)."""
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/", include("allauth.urls")),
    path("qms/pms/", include("pms.urls")),
    path("qms/", include("qms.urls")),
]
