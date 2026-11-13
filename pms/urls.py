from django.urls import path

from . import views

app_name = "pms"

urlpatterns = [
    path("", views.report_list, name="report_list"),
    path("register/", views.register, name="register"),
    path("activation-sent/", views.activation_sent, name="activation_sent"),
    path("activate/<str:token>/", views.activate, name="activate"),
    path("report/new/<str:kind>/", views.report_new, name="report_new"),
    path("report/<str:number>/", views.report_detail, name="report_detail"),
    path("report/<str:number>/link/", views.report_link_add, name="report_link_add"),
    path("triage/", views.triage_list, name="triage_list"),
    path("triage/<str:number>/", views.triage_update, name="triage_update"),
]
