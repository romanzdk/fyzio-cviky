from django.contrib import admin
from django.urls import path

from cviky import views

urlpatterns = [
    path("sprava/", admin.site.urls),
    path("healthz", views.healthz),
]
