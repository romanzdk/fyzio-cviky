import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from cviky.models import Exercise, Series, SeriesExercise
from cviky.views import series as series_views

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


def _series_data(exercises, **extra):
    data = {
        "name": "Ranní série",
        "weekdays": ["0", "2", "4"],
        "remind_at": "07:30",
        "exercises": [str(e.pk) for e in exercises],
    }
    for i, exercise in enumerate(exercises, start=1):
        data[f"order_{exercise.pk}"] = str(i)
    data.update(extra)
    return data


@pytest.mark.django_db
def test_create_series_keeps_days_time_and_order(logged_in, user):
    exercises = [Exercise.objects.create(user=user, title=f"Cvik {i}") for i in range(1, 4)]
    response = logged_in.post(reverse("series_create"), _series_data(exercises))
    assert response.status_code == 302
    series = Series.objects.get()
    assert series.user == user
    assert series.name == "Ranní série"
    assert series.weekdays == [0, 2, 4]
    assert series.remind_at == datetime.time(7, 30)
    assert [item.exercise_id for item in series.items.all()] == [e.pk for e in exercises]


@pytest.mark.django_db
def test_form_offers_only_own_exercises(logged_in, user, other):
    Exercise.objects.create(user=user, title="Můj cvik")
    Exercise.objects.create(user=other, title="Cizí cvik")
    content = logged_in.get(reverse("series_create")).content.decode()
    assert "Můj cvik" in content
    assert "Cizí cvik" not in content


@pytest.mark.django_db
def test_other_users_exercise_is_not_saved(logged_in, other):
    foreign = Exercise.objects.create(user=other, title="Cizí")
    response = logged_in.post(reverse("series_create"), _series_data([foreign]))
    assert response.status_code == 302
    assert SeriesExercise.objects.count() == 0


@pytest.mark.django_db
def test_other_users_series_404(logged_in, other):
    series = Series.objects.create(user=other, name="Cizí")
    for name in ("series_edit", "series_delete"):
        assert logged_in.get(reverse(name, args=[series.pk])).status_code == 404


@pytest.mark.django_db
def test_removing_exercise_from_series_keeps_the_exercise(logged_in, user):
    a = Exercise.objects.create(user=user, title="A")
    b = Exercise.objects.create(user=user, title="B")
    logged_in.post(reverse("series_create"), _series_data([a, b]))
    series = Series.objects.get()
    logged_in.post(reverse("series_edit", args=[series.pk]), _series_data([a]))
    assert not SeriesExercise.objects.filter(series=series, exercise=b).exists()
    assert Exercise.objects.filter(pk=b.pk).exists()


@pytest.mark.django_db
def test_re_adding_resets_added_at(logged_in, user):
    a = Exercise.objects.create(user=user, title="A")
    logged_in.post(reverse("series_create"), _series_data([a]))
    series = Series.objects.get()
    item = SeriesExercise.objects.get()
    old_added_at = timezone.now() - datetime.timedelta(days=1)
    SeriesExercise.objects.filter(pk=item.pk).update(added_at=old_added_at)

    logged_in.post(reverse("series_edit", args=[series.pk]), _series_data([]))
    assert SeriesExercise.objects.count() == 0

    logged_in.post(reverse("series_edit", args=[series.pk]), _series_data([a]))
    new = SeriesExercise.objects.get()
    assert new.pk != item.pk
    assert new.added_at > old_added_at


@pytest.mark.django_db
def test_keeping_selection_updates_order_only(logged_in, user):
    a = Exercise.objects.create(user=user, title="A")
    b = Exercise.objects.create(user=user, title="B")
    logged_in.post(reverse("series_create"), _series_data([a, b]))
    series = Series.objects.get()
    item_a = SeriesExercise.objects.get(series=series, exercise=a)
    added_at = item_a.added_at

    logged_in.post(
        reverse("series_edit", args=[series.pk]),
        _series_data([b, a], order_b="1", order_a="2"),
    )
    item_a.refresh_from_db()
    assert item_a.order == 2
    assert item_a.added_at == added_at


@pytest.mark.django_db
def test_list_shows_only_own_series_with_summary(logged_in, user, other):
    a = Exercise.objects.create(user=user, title="A")
    logged_in.post(reverse("series_create"), _series_data([a]))
    Series.objects.create(user=other, name="Cizí série", weekdays=[5])
    content = logged_in.get(reverse("series_list")).content.decode()
    assert "Ranní série" in content
    assert "Cizí série" not in content
    assert "Po" in content and "St" in content and "Pá" in content
    assert "07:30" in content
    assert "1 cvik" in content


@pytest.mark.django_db
def test_delete_requires_post_and_removes(logged_in, user):
    series = Series.objects.create(user=user, name="Zmizík")
    assert logged_in.get(reverse("series_delete", args=[series.pk])).status_code == 200
    response = logged_in.post(reverse("series_delete", args=[series.pk]))
    assert response.status_code == 302
    assert not Series.objects.filter(pk=series.pk).exists()


@pytest.mark.django_db
def test_series_requires_login(client):
    response = client.get(reverse("series_list"))
    assert response.status_code == 302
    assert reverse("login") in response.url


@pytest.mark.django_db
def test_exercise_list_filters_by_series(logged_in, user):
    a = Exercise.objects.create(user=user, title="V sérii")
    Exercise.objects.create(user=user, title="Mimo sérii")
    series = Series.objects.create(user=user, name="S")
    SeriesExercise.objects.create(series=series, exercise=a, order=1)
    content = logged_in.get(reverse("exercise_list"), {"serie": series.pk}).content.decode()
    assert "V sérii" in content
    assert "Mimo sérii" not in content


@pytest.mark.django_db
def test_non_numeric_serie_is_ignored(logged_in, user):
    Exercise.objects.create(user=user, title="Cvik")
    response = logged_in.get(reverse("exercise_list"), {"serie": "abc"})
    assert response.status_code == 200
    assert "Cvik" in response.content.decode()


@pytest.mark.django_db
def test_other_users_serie_filter_is_ignored(logged_in, user, other):
    Exercise.objects.create(user=user, title="Můj cvik")
    foreign = Series.objects.create(user=other, name="Cizí")
    response = logged_in.get(reverse("exercise_list"), {"serie": foreign.pk})
    assert response.status_code == 200
    assert "Můj cvik" in response.content.decode()


@pytest.mark.django_db
def test_reminder_without_weekdays_is_rejected(logged_in, user):
    exercise = Exercise.objects.create(user=user, title="A")
    response = logged_in.post(reverse("series_create"), _series_data([exercise], weekdays=[]))
    assert response.status_code == 200
    assert "Vyber aspoň jeden den, jinak připomínka nepřijde." in response.content.decode()
    assert Series.objects.count() == 0


@pytest.mark.django_db
def test_series_save_rolls_back_when_items_fail(logged_in, user, monkeypatch):
    exercise = Exercise.objects.create(user=user, title="A")

    def boom(request, series):
        raise RuntimeError("boom")

    monkeypatch.setattr(series_views, "_sync_items", boom)
    with pytest.raises(RuntimeError):
        logged_in.post(reverse("series_create"), _series_data([exercise]))
    assert Series.objects.count() == 0
