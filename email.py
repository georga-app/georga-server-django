from datetime import datetime, timedelta, timezone

import jwt
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from publicsite import settings


class Email:

    @staticmethod
    def send_activation_email(self):
        payload = {
            'uid': self.id,
            'exp': datetime.now(tz=timezone.utc) + timedelta(days=settings.ACTIVATION_DAYS),
            'iat': datetime.now(tz=timezone.utc),
            'sub': 'activation',
        }

        activation_url = settings.ACTIVATION_URL
        activation_token = jwt.encode(payload, settings.GRAPHQL_JWT['JWT_PRIVATE_KEY'], algorithm="RS256")

        email = EmailMessage(
            render_to_string(template_name='call_for_volunteers/activation_email_subject.html', context={'user': self}),
            render_to_string(template_name='call_for_volunteers/activation_email.html', context={'user': self, 'activation_url': activation_url, 'activation_token': activation_token}),
            settings.EMAIL_SENDER,
            [self.email],
            headers={'Message-ID': 'foo'},
        )
        email.send()

    @staticmethod
    def send_password_reset_email(self):
        payload = {
            'uid': self.id,
            'exp': datetime.now(tz=timezone.utc) + timedelta(days=1),
            'iat': datetime.now(tz=timezone.utc),
            'sub': 'password_reset',
        }

        activation_url = settings.ACTIVATION_URL
        activation_token = jwt.encode(payload, settings.GRAPHQL_JWT['JWT_PRIVATE_KEY'], algorithm="RS256")

        email = EmailMessage(
            render_to_string(template_name='call_for_volunteers/password_reset_email_subject.html', context={'user': self}),
            render_to_string(template_name='call_for_volunteers/password_reset_email.html', context={'user': self, 'url': activation_url, 'token': activation_token}),
            settings.EMAIL_SENDER,
            [self.email],
            headers={'Message-ID': 'foo'},
        )
        email.send()
