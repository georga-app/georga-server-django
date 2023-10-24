# For copyright and license terms, see COPYRIGHT.md (top level of repository)
# Repository: https://github.com/georga-app/georga-server-django

from django.core.management.base import BaseCommand
from georga.schemas import Message


class Command(BaseCommand):
    help = 'delivers push messages'

    # def add_arguments(self, parser):
    #     parser.add_argument('--argument', help='help')

    def handle(self, *args, **options):
        scheduled = Message.objects.filter(push_delivery='SCHEDULED')
        for msg in scheduled:
            print(f'sending push message: {msg}')
            msg.send_push()
