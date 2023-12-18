import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')
django.setup()

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from .models import Customer


class CustomModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()

        try:
            # Check if the user can be authenticated with the Customer model
            user = Customer.objects.get(email=username)
        except Customer.DoesNotExist:
            # If the user is not found in the Customer model, try the default User model
            user = user_model.objects.filter(username=username).first()

        if user and user.check_password(password):
            return user
        return None
