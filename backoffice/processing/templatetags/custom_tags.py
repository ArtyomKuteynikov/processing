import datetime

from django import template

register = template.Library()


@register.simple_tag
def multiply(a, b):
    return a * b


@register.simple_tag
def divide(a, b):
    if not a or not b:
        return 0
    return "{:.2f}".format(float(float(a) / float(b)))


@register.simple_tag
def percent(a, b):
    if not a or not b:
        return 0
    return "{:.2f}".format(float(float(a) / float(b))*100)


@register.simple_tag
def zeros(a):
    if not a:
        return 0
    return round(a, 2)


@register.simple_tag
def time_date(a, b):
    final = a + datetime.timedelta(hours=abs(b)) if b > 0 else a - datetime.timedelta(hours=abs(b))
    return final.strftime("%d.%m.%Y")


@register.simple_tag
def time_hours(a, b):
    final = a + datetime.timedelta(hours=abs(b)) if b > 0 else a - datetime.timedelta(hours=abs(b))
    return final.strftime("%H:%M")


@register.simple_tag
def dict_get(a: dict, b: str, c: str | None = None):
    return a[b][c] if c else a[b]
