import datetime
import json
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from pywebpush import WebPushException

from cviky.models import Completion, Exercise, PushSubscription, ReminderSent, Series, SeriesExercise
from cviky.reminders import due_series, reminder_text, send_due
from cviky.today import local_date

User = get_user_model()

PRAGUE = ZoneInfo("Europe/Prague")


class _Response:
    def __init__(self, status_code):
        self.status_code = status_code


def at(year, month, day, hour, minute=0):
    return datetime.datetime(year, month, day, hour, minute, tzinfo=PRAGUE)


def make_series(user, name="Ranní série", weekdays=None, remind_at=None, exercises=0):
    series = Series.objects.create(
        user=user, name=name, weekdays=weekdays or [], remind_at=remind_at
    )
    for index in range(exercises):
        exercise = Exercise.objects.create(user=user, title=f"Cvik {index}")
        SeriesExercise.objects.create(series=series, exercise=exercise, order=index)
    return series


def subscribe(user, endpoint="https://push.example.com/sub", p256dh="p", auth="a"):
    return PushSubscription.objects.create(
        user=user, endpoint=endpoint, p256dh=p256dh, auth=auth
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(username="a", password="SilneHeslo123")


def test_due_at_exact_time(user):
    now = at(2026, 6, 15, 7, 30)
    series = make_series(
        user,
        weekdays=[local_date(now).weekday()],
        remind_at=datetime.time(7, 30),
        exercises=1,
    )
    assert due_series(now) == [series]


def test_not_due_on_other_weekday(user):
    now = at(2026, 6, 15, 7, 30)
    other_day = (local_date(now).weekday() + 1) % 7
    make_series(
        user,
        weekdays=[other_day],
        remind_at=datetime.time(7, 30),
        exercises=1,
    )
    assert due_series(now) == []


def test_sent_once_per_day(user, settings, monkeypatch):
    settings.VAPID_PRIVATE_KEY = "private"
    pushes = []
    monkeypatch.setattr("cviky.reminders.webpush", lambda **kwargs: pushes.append(kwargs))
    subscribe(user)
    now = at(2026, 6, 15, 7, 30)
    make_series(
        user,
        weekdays=[local_date(now).weekday()],
        remind_at=datetime.time(7, 30),
        exercises=1,
    )
    assert send_due(now) == 1
    assert send_due(now) == 0
    assert len(pushes) == 1
    assert ReminderSent.objects.count() == 1


def test_missed_by_30_min_still_sent(user, settings, monkeypatch):
    settings.VAPID_PRIVATE_KEY = "private"
    monkeypatch.setattr("cviky.reminders.webpush", lambda **kwargs: None)
    now = at(2026, 6, 15, 8, 0)
    make_series(
        user,
        weekdays=[local_date(now).weekday()],
        remind_at=datetime.time(7, 30),
        exercises=1,
    )
    assert send_due(now) == 1


def test_missed_by_90_min_not_sent(user, settings, monkeypatch):
    settings.VAPID_PRIVATE_KEY = "private"
    monkeypatch.setattr("cviky.reminders.webpush", lambda **kwargs: None)
    now = at(2026, 6, 15, 9, 0)
    make_series(
        user,
        weekdays=[local_date(now).weekday()],
        remind_at=datetime.time(7, 30),
        exercises=1,
    )
    assert send_due(now) == 0
    assert ReminderSent.objects.count() == 0


def test_skipped_when_all_done_today(user, settings, monkeypatch):
    settings.VAPID_PRIVATE_KEY = "private"
    pushes = []
    monkeypatch.setattr("cviky.reminders.webpush", lambda **kwargs: pushes.append(kwargs))
    now = at(2026, 6, 15, 7, 30)
    series = make_series(
        user,
        weekdays=[local_date(now).weekday()],
        remind_at=datetime.time(7, 30),
        exercises=2,
    )
    for item in series.items.all():
        Completion.objects.create(user=user, exercise=item.exercise, series=series, done_at=now)
    assert due_series(now) == []
    assert send_due(now) == 0
    assert pushes == []


def test_text_with_and_without_neglected(user):
    one = make_series(user, name="Jedna", exercises=1)
    four = make_series(user, name="Ranní série", exercises=4)
    five = make_series(user, name="Pět", exercises=5)

    assert reminder_text(one, 0) == ("Jedna", "1 cvik")
    assert reminder_text(four, 0) == ("Ranní série", "4 cviky")
    assert reminder_text(four, 2) == ("Ranní série", "4 cviky + 2 dlouho nedělané")
    assert reminder_text(four, 3) == ("Ranní série", "4 cviky + 3 dlouho nedělané")
    assert reminder_text(five, 0) == ("Pět", "5 cviků")
    assert reminder_text(five, 1) == ("Pět", "5 cviků + 1 dlouho nedělaný")
    assert reminder_text(five, 5) == ("Pět", "5 cviků + 5 dlouho nedělaných")


def test_empty_series_skipped(user, settings, monkeypatch):
    settings.VAPID_PRIVATE_KEY = "private"
    monkeypatch.setattr("cviky.reminders.webpush", lambda **kwargs: None)
    now = at(2026, 6, 15, 7, 30)
    make_series(
        user,
        weekdays=[local_date(now).weekday()],
        remind_at=datetime.time(7, 30),
        exercises=0,
    )
    assert send_due(now) == 0


def test_no_vapid_key_sends_and_records_nothing(user, settings, monkeypatch):
    settings.VAPID_PRIVATE_KEY = ""
    calls = []
    monkeypatch.setattr("cviky.reminders.webpush", lambda **kwargs: calls.append(kwargs))
    now = at(2026, 6, 15, 7, 30)
    make_series(
        user,
        weekdays=[local_date(now).weekday()],
        remind_at=datetime.time(7, 30),
        exercises=1,
    )
    assert send_due(now) == 0
    assert calls == []
    assert ReminderSent.objects.count() == 0


def test_recorded_even_without_subscriptions(user, settings, monkeypatch):
    settings.VAPID_PRIVATE_KEY = "private"
    monkeypatch.setattr("cviky.reminders.webpush", lambda **kwargs: None)
    now = at(2026, 6, 15, 7, 30)
    series = make_series(
        user,
        weekdays=[local_date(now).weekday()],
        remind_at=datetime.time(7, 30),
        exercises=1,
    )
    assert send_due(now) == 1
    assert ReminderSent.objects.filter(series=series, date=local_date(now)).exists()


def test_gone_subscription_deleted_and_others_still_sent(user, settings, monkeypatch):
    settings.VAPID_PRIVATE_KEY = "private"
    gone = subscribe(user, endpoint="https://push.example.com/gone")
    good = subscribe(user, endpoint="https://push.example.com/good")
    sent = []

    def fake_webpush(**kwargs):
        if kwargs["subscription_info"]["endpoint"] == gone.endpoint:
            raise WebPushException("gone", response=_Response(410))
        sent.append(kwargs)

    monkeypatch.setattr("cviky.reminders.webpush", fake_webpush)
    now = at(2026, 6, 15, 7, 30)
    make_series(
        user,
        weekdays=[local_date(now).weekday()],
        remind_at=datetime.time(7, 30),
        exercises=1,
    )

    assert send_due(now) == 1
    assert not PushSubscription.objects.filter(pk=gone.pk).exists()
    assert PushSubscription.objects.filter(pk=good.pk).exists()
    assert [kw["subscription_info"]["endpoint"] for kw in sent] == [good.endpoint]


@pytest.mark.parametrize("day", [datetime.date(2027, 3, 28), datetime.date(2027, 10, 31)])
def test_dst_day_sends_once(user, settings, monkeypatch, day):
    settings.VAPID_PRIVATE_KEY = "private"
    pushes = []
    monkeypatch.setattr("cviky.reminders.webpush", lambda **kwargs: pushes.append(kwargs))
    subscribe(user)
    make_series(
        user,
        weekdays=[day.weekday()],
        remind_at=datetime.time(7, 30),
        exercises=1,
    )

    total = 0
    for hour, minute in [(7, 30), (7, 45), (8, 0), (8, 29)]:
        total += send_due(at(day.year, day.month, day.day, hour, minute))

    assert total == 1
    assert ReminderSent.objects.count() == 1
    assert len(pushes) == 1


def test_payload_contents(user, settings, monkeypatch):
    settings.VAPID_PRIVATE_KEY = "private"
    settings.VAPID_SUBJECT = "mailto:test@example.com"
    pushes = []
    monkeypatch.setattr("cviky.reminders.webpush", lambda **kwargs: pushes.append(kwargs))
    subscribe(user)
    now = at(2026, 6, 15, 7, 30)
    make_series(
        user,
        name="Ranní série",
        weekdays=[local_date(now).weekday()],
        remind_at=datetime.time(7, 30),
        exercises=4,
    )

    send_due(now)

    call = pushes[0]
    assert call["vapid_private_key"] == "private"
    assert call["vapid_claims"] == {"sub": "mailto:test@example.com"}
    assert call["ttl"] == 3600
    assert call["subscription_info"]["keys"] == {"p256dh": "p", "auth": "a"}
    import json

    assert json.loads(call["data"]) == {
        "title": "Ranní série",
        "body": "4 cviky",
        "url": "/",
    }


def test_command_prints_count(user, settings, monkeypatch, capsys):
    settings.VAPID_PRIVATE_KEY = "private"
    monkeypatch.setattr("cviky.reminders.webpush", lambda **kwargs: None)
    now = timezone.now()
    make_series(
        user,
        weekdays=[local_date(now).weekday()],
        remind_at=timezone.localtime(now).time().replace(second=0, microsecond=0),
        exercises=1,
    )
    call_command("send_reminders")
    assert "Odesláno: 1" in capsys.readouterr().out


def test_neglected_count_includes_other_series(user, monkeypatch, settings):
    settings.VAPID_PRIVATE_KEY = "key"
    sent = []
    monkeypatch.setattr("cviky.reminders.webpush", lambda **kw: sent.append(kw["data"]))
    now = at(2027, 3, 1, 7, 30)
    today_series = make_series(user, weekdays=[now.weekday()], remind_at=datetime.time(7, 30), exercises=1)
    SeriesExercise.objects.filter(series=today_series).update(added_at=now)
    other = make_series(user, name="Večerní", weekdays=[], exercises=1)
    SeriesExercise.objects.filter(series=other).update(added_at=now - datetime.timedelta(days=10))
    subscribe(user)
    assert send_due(now) == 1
    assert json.loads(sent[0])["body"] == "1 cvik + 1 dlouho nedělaný"


def test_unexpected_push_error_does_not_stop_other_subscriptions(user, monkeypatch, settings):
    settings.VAPID_PRIVATE_KEY = "key"
    sent = []

    def fake_webpush(**kw):
        if kw["subscription_info"]["endpoint"].endswith("bad"):
            raise ConnectionError("boom")
        sent.append(kw)

    monkeypatch.setattr("cviky.reminders.webpush", fake_webpush)
    now = at(2027, 3, 1, 7, 30)
    make_series(user, weekdays=[now.weekday()], remind_at=datetime.time(7, 30), exercises=1)
    subscribe(user, endpoint="https://push.example.com/bad")
    subscribe(user, endpoint="https://push.example.com/good")
    assert send_due(now) == 1
    assert len(sent) == 1
