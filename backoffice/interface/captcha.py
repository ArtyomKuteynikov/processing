import requests
from processing.settings import RECAPTCHA_PRIVATE_KEY
from django.http import HttpResponse


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def grecaptcha_verify(request, captcha_rs):
    if request.method == 'POST':
        url = "https://www.google.com/recaptcha/api/siteverify"
        params = {
            'secret': RECAPTCHA_PRIVATE_KEY,
            'response': captcha_rs
        }
        verify_rs = requests.get(url, params=params, verify=True)
        verify_rs = verify_rs.json()
        return verify_rs
