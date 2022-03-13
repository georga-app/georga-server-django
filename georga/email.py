from datetime import datetime, timedelta, timezone

import jwt
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from . import settings


class Email:

    @staticmethod
    def send_activation_email(user):
        payload = {
            'uid': user.id,
            'exp':
                datetime.now(tz=timezone.utc) +
                timedelta(days=settings.ACTIVATION_DAYS),
            'iat': datetime.now(tz=timezone.utc),
            'sub': 'activation',
        }

        activation_url = settings.ACTIVATION_URL
        activation_token = jwt.encode(
            payload, settings.GRAPHQL_JWT['JWT_PRIVATE_KEY'],
            algorithm="RS256")

        email = EmailMessage(
            render_to_string(
                template_name='georga/activation_email_subject.html',
                context={'user': user}),
            render_to_string(
                template_name='georga/activation_email.html',
                context={
                    'user': user, 'activation_url': activation_url,
                    'activation_token': activation_token}),
            settings.EMAIL_SENDER,
            [user.email],
            headers={},
        )
        email.send()

    @staticmethod
    def send_password_reset_email(user):
        payload = {
            'uid': user.id,
            'exp': datetime.now(tz=timezone.utc) + timedelta(days=1),
            'iat': datetime.now(tz=timezone.utc),
            'sub': 'password_reset',
        }

        url = settings.PASSWORD_URL
        token = jwt.encode(
            payload, settings.GRAPHQL_JWT['JWT_PRIVATE_KEY'],
            algorithm="RS256")

        email = EmailMessage(
            render_to_string(
                template_name='georga/password_reset_email_subject.html',
                context={'user': user}),
            render_to_string(
                template_name='georga/password_reset_email.html',
                context={'user': user, 'url': url, 'token': token}),
            settings.EMAIL_SENDER,
            [user.email],
        )
        print(email.send())
        print("Send")
