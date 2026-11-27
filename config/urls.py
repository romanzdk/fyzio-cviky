from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from cviky.views import auth, exercises, health, profile, series, today

urlpatterns = [
    path("sprava/", admin.site.urls),
    path("healthz", health.healthz),
    path("", today.home, name="home"),
    path("hotovo/", today.toggle, name="toggle"),
    path("profil/", profile.profile, name="profile"),
    path("prihlaseni/", LoginView.as_view(), name="login"),
    path("odhlaseni/", LogoutView.as_view(), name="logout"),
    path("registrace/<uuid:token>/", auth.register, name="register"),
    path("cviky/", exercises.index, name="exercise_list"),
    path("cviky/novy/", exercises.create, name="exercise_create"),
    path("cviky/<int:pk>/", exercises.detail, name="exercise_detail"),
    path("cviky/<int:pk>/upravit/", exercises.edit, name="exercise_edit"),
    path("cviky/<int:pk>/smazat/", exercises.delete, name="exercise_delete"),
    path("serie/", series.index, name="series_list"),
    path("serie/nova/", series.create, name="series_create"),
    path("serie/<int:pk>/upravit/", series.edit, name="series_edit"),
    path("serie/<int:pk>/smazat/", series.delete, name="series_delete"),
]
