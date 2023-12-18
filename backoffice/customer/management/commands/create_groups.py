from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

class Command(BaseCommand):
    help = 'Create groups'

    def handle(self, *args, **options):
        group_names = ['KYC_OPERATOR', 'KYC_MANAGER', 'AML_OPERATOR', 'AML_MANAGER', 'ADMIN', 'MANAGER']

        for group_name in group_names:
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                print('Created')
            else:
                print('Already Exist')

