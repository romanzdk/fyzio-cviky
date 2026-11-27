import re

from django import template

from cviky.choices import WEEKDAYS

register = template.Library()

LEADING_NUMBER = re.compile(r"^\s*\d+\s*[.)]\s*")

WEEKDAY_LABELS = dict(WEEKDAYS)


@register.filter
def weekday_labels(days):
    return ", ".join(WEEKDAY_LABELS.get(day, str(day)) for day in days)


@register.filter
def weekday_abbr(day):
    return WEEKDAY_LABELS.get(day, "")


@register.filter
def days_label(count):
    if count == 1:
        return f"{count} den"
    if 2 <= count <= 4:
        return f"{count} dny"
    return f"{count} dní"


@register.filter
def exercises_label(count):
    if count == 1:
        return f"{count} cvik"
    if 2 <= count <= 4:
        return f"{count} cviky"
    return f"{count} cviků"


@register.filter
def step_lines(text):
    return [LEADING_NUMBER.sub("", line).strip() for line in text.splitlines() if line.strip()]
