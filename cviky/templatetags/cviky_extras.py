from django import template

from cviky.choices import AREAS, POSITIONS

register = template.Library()

AREA_LABELS = dict(AREAS)
POSITION_LABELS = dict(POSITIONS)


@register.filter
def area_label(key):
    return AREA_LABELS.get(key, key)


@register.filter
def position_label(key):
    return POSITION_LABELS.get(key, key)
