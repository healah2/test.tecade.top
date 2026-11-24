from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Safely get item from dictionary."""
    if not dictionary:
        return ''
    return dictionary.get(key, '')

@register.filter
def dict_get(d, key):
    """Safely get value from a dictionary by key."""
    if not d:
        return ''
    try:
        return d.get(key, '')
    except AttributeError:
        return ''

@register.filter
def split(value, separator=','):
    """
    Splits a string by separator.
    Usage: {{ value|split:"," }}
    """
    if not value:
        return []
    return [item.strip() for item in value.split(separator)]

# @register.filter
# def is_selected(course_id, selected_id):
#     return course_id == selected_id

@register.filter
def is_selected(value, arg):
    return 'selected' if str(value) == str(arg) else ''

@register.filter
def term_selected(unit_term, term_value):
    return 'selected' if str(unit_term) == str(term_value) else ''