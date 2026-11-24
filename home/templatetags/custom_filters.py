import re
from django import template

register = template.Library()

@register.filter
def regex_replace(value, pattern):
    return re.sub(pattern, '', value)