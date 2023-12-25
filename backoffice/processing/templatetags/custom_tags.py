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
    return a


@register.simple_tag
def dict_get(a: dict, b: str, c: str | None = None):
    return a[b][c] if c else a[b]
