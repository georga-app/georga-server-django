"""
ASGI config for composeexample project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter
from django.core.asgi import get_asgi_application
from graphql_ws.django.routing import auth_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'georga.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": auth_application,
})
