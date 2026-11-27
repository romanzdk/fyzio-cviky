import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from cviky.models import Completion, Exercise, Series, SeriesExercise
from cviky.today import local_date, neglected, todays_series

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="a", password="SilneHeslo123")


@pytest.fixture
def other(db):
    return User.objects.create_user(username="b", password="SilneHeslo123")


@pytest.fixture
def logged_in(client, user):
    client.force_login(user)
    return client


def _series_with_exercise(user, exercise, **extra):
    series = Series.objects.create(user=user, name="S", **extra)
    SeriesExercise.objects.create(series=series, exercise=exercise, order=1)
    return series


@pytest.mark.django_db
def test_today_lists_series_for_weekday_only(user):
    today = local_date(timezone.now())
    other_day = (today.weekday() + 1) % 7
    Series.objects.create(user=user, name="Dnes", weekdays=[today.weekday()])
    Series.objects.create(user=user, name="Jindy", weekdays=[other_day])
    assert [s.name for s in todays_series(user, today)] == ["Dnes"]


@pytest.mark.django_db
def test_check_off_and_undo(logged_in, user):
    exercise = Exercise.objects.create(user=user, title="Cvik")
    series = _series_with_exercise(user, exercise)
    url = reverse("toggle")
    logged_in.post(url, {"exercise": exercise.pk, "series": series.pk})
    assert Completion.objects.filter(user=user, exercise=exercise, series=series).count() == 1
    logged_in.post(url, {"exercise": exercise.pk, "series": series.pk})
    assert Completion.objects.filter(user=user, exercise=exercise, series=series).count() == 0


def test_completion_at_2330_prague_counts_for_that_day():
    dt = datetime.datetime(2026, 1, 15, 22, 30, tzinfo=datetime.UTC)
    assert local_date(dt) == datetime.date(2026, 1, 15)


@pytest.mark.django_db
def test_neglected_after_7_days(user):
    now = timezone.now()
    exercise = Exercise.objects.create(user=user, title="Cvik")
    _series_with_exercise(user, exercise)
    completion = Completion.objects.create(
        user=user, exercise=exercise, done_at=now - datetime.timedelta(days=7)
    )
    assert [(e.title, d) for e, d in neglected(user, now)] == [("Cvik", 7)]
    completion.done_at = now - datetime.timedelta(days=6)
    completion.save(update_fields=["done_at"])
    assert neglected(user, now) == []


@pytest.mark.django_db
def test_never_done_counts_from_added_at(user):
    now = timezone.now()
    exercise = Exercise.objects.create(user=user, title="Nikdy")
    item = SeriesExercise.objects.get(series=_series_with_exercise(user, exercise))
    SeriesExercise.objects.filter(pk=item.pk).update(
        added_at=now - datetime.timedelta(days=10)
    )
    assert [(e.title, d) for e, d in neglected(user, now)] == [("Nikdy", 10)]


@pytest.mark.django_db
def test_neglect_days_setting_respected(user):
    now = timezone.now()
    user.neglect_days = 3
    user.save()
    exercise = Exercise.objects.create(user=user, title="Cvik")
    item = SeriesExercise.objects.get(series=_series_with_exercise(user, exercise))
    SeriesExercise.objects.filter(pk=item.pk).update(
        added_at=now - datetime.timedelta(days=4)
    )
    assert [(e.title, d) for e, d in neglected(user, now)] == [("Cvik", 4)]


@pytest.mark.django_db
def test_other_users_exercise_cannot_be_checked(logged_in, other):
    exercise = Exercise.objects.create(user=other, title="Cizí")
    response = logged_in.post(reverse("toggle"), {"exercise": exercise.pk})
    assert response.status_code == 404
    assert Completion.objects.count() == 0


@pytest.mark.django_db
def test_page_shows_neglected_section_only_when_non_empty(logged_in, user):
    exercise = Exercise.objects.create(user=user, title="Zapomenutý")
    item = SeriesExercise.objects.get(series=_series_with_exercise(user, exercise))
    assert "Dlouho nedělané" not in logged_in.get(reverse("home")).content.decode()
    SeriesExercise.objects.filter(pk=item.pk).update(
        added_at=timezone.now() - datetime.timedelta(days=7)
    )
    content = logged_in.get(reverse("home")).content.decode()
    assert "Dlouho nedělané" in content
    assert "7 dní" in content


@pytest.mark.django_db
def test_home_shows_series_progress_and_empty_state(logged_in, user):
    today = local_date(timezone.now())
    exercise = Exercise.objects.create(user=user, title="Cvik")
    series = _series_with_exercise(user, exercise, weekdays=[today.weekday()])
    content = logged_in.get(reverse("home")).content.decode()
    assert "0/1 ✓" in content
    logged_in.post(reverse("toggle"), {"exercise": exercise.pk, "series": series.pk})
    assert "1/1 ✓" in logged_in.get(reverse("home")).content.decode()


@pytest.mark.django_db
def test_home_empty_state_when_no_series_today(logged_in, user):
    content = logged_in.get(reverse("home")).content.decode()
    assert "Dnes nemáš naplánovanou žádnou sérii." in content
    assert reverse("series_list") in content


@pytest.mark.django_db
def test_profile_updates_neglect_days(logged_in, user):
    response = logged_in.post(reverse("profile"), {"neglect_days": "3"})
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.neglect_days == 3


@pytest.mark.django_db
def test_profile_rejects_out_of_range(logged_in, user):
    response = logged_in.post(reverse("profile"), {"neglect_days": "0"})
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.neglect_days == 7


@pytest.mark.django_db
def test_toggle_with_non_numeric_id_returns_404(client, django_user_model):
    user = django_user_model.objects.create_user(username="z", password="SilneHeslo123")
    client.force_login(user)
    assert client.post("/hotovo/", {"exercise": "abc"}).status_code == 404
