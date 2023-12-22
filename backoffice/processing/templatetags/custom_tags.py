from django import template

register = template.Library()


@register.simple_tag
def multiply(a, b):
    return a * b


@register.simple_tag
def divide(a, b):
    return "{:.2f}".format(float(a / b))


@register.simple_tag
def dict_get(a: dict, b: str, c: str | None = None):
    return a[b][c] if c else a[b]
