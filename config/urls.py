from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from qms.health import healthz

admin.site.site_header = "SAMD_QMS administration"

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Single sign-on (Google, Microsoft, LinkedIn, ORCID, GitHub) and connected accounts
    path("accounts/", include("allauth.urls")),
    path("", include("qms.urls")),
]
