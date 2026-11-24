# home/templatetags/random_color.py

from django import template
import random

register = template.Library()

@register.filter
def random_color(value):
    # Random color generation logic
    random_color = "#{:02x}{:02x}{:02x}".format(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    return random_color
