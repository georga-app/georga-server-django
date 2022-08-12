from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password


class Command(BaseCommand):
    help = 'returns password hash e.g. for inserting into demo data'

    def __init__(self):
        super().__init__()
        self.session = ''

    def add_arguments(self, parser):
        parser.add_argument(
            'passwd',
            help='password to hash',
        )

    def handle(self, *args, **options):
        print(make_password(options['passwd']))
