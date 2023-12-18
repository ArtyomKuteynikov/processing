from django import template

register = template.Library()


@register.simple_tag
def multiply(a, b):
    return a * b


@register.simple_tag
def divide(a, b):
    return "{:.8f}".format(float(a / b))


@register.simple_tag
def dict_get(a: dict, b: str, c: str):
    return a[b][c]
