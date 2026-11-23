"""Custom template tags for IssueSnap."""
from django import template
register = template.Library()


@register.filter
def split(value, delimiter=','):
    """Split a string into a list using the given delimiter."""
    if not value:
        return []
    return value.split(delimiter)


@register.filter
def replace_underscore(value):
    """Replace underscores with spaces and title-case."""
    if not value:
        return ''
    return value.replace('_', ' ').title()


@register.filter
def list(value):
    """No-op helper to make a value behave list-like in templates."""
    return value


@register.filter
def index(value, i):
    """Index into a list/tuple."""
    try:
        return value[i]
    except (IndexError, TypeError, KeyError):
        return ''
