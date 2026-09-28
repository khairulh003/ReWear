from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from core.forms import LoginForm

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(authentication_form=LoginForm),
        name="login",
    ),
    path("accounts/", include("django.contrib.auth.urls")),  # logout, password views
    path("", include("core.urls")),
]
