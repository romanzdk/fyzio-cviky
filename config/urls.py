from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from cviky.views import auth, health

urlpatterns = [
    path("sprava/", admin.site.urls),
    path("healthz", health.healthz),
    path("", auth.home, name="home"),
    path("prihlaseni/", LoginView.as_view(), name="login"),
    path("odhlaseni/", LogoutView.as_view(), name="logout"),
    path("registrace/<uuid:token>/", auth.register, name="register"),
]
