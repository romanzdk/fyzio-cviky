from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html

from cviky.models import (
    Completion,
    Exercise,
    Invite,
    PushSubscription,
    Series,
    SeriesExercise,
    User,
)


class SeriesExerciseInline(admin.TabularInline):
    model = SeriesExercise
    extra = 0


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "remind_at")
    inlines = [SeriesExerciseInline]


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "area", "position", "created_at")
    list_filter = ("area", "position")
    search_fields = ("title", "tags")


@admin.register(Completion)
class CompletionAdmin(admin.ModelAdmin):
    list_display = ("exercise", "series", "user", "done_at")
    list_filter = ("series",)


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("endpoint", "user", "created_at")
    search_fields = ("endpoint",)


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ("token", "created_at", "used_by", "used_at", "registration_link")
    readonly_fields = ("token", "created_at", "used_by", "used_at", "registration_link")

    def get_queryset(self, request):
        self._request = request
        return super().get_queryset(request)

    @admin.display(description="Registrační odkaz")
    def registration_link(self, obj):
        path = reverse("register", args=[obj.token])
        request = getattr(self, "_request", None)
        url = request.build_absolute_uri(path) if request is not None else path
        return format_html('<a href="{0}">{0}</a>', url)


admin.site.register(User, UserAdmin)
