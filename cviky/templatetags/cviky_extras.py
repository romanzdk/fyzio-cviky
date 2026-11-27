from django import template

from cviky.choices import AREAS, POSITIONS, WEEKDAYS

register = template.Library()

AREA_LABELS = dict(AREAS)
POSITION_LABELS = dict(POSITIONS)
WEEKDAY_LABELS = dict(WEEKDAYS)


@register.filter
def area_label(key):
    return AREA_LABELS.get(key, key)


@register.filter
def position_label(key):
    return POSITION_LABELS.get(key, key)


@register.filter
def weekday_labels(days):
    return ", ".join(WEEKDAY_LABELS.get(day, str(day)) for day in days)
