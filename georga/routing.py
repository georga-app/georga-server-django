import channels_graphql_ws
from django.urls import re_path, path


# Websocket endpoints
from georga import schema_graphql


class MyGraphqlWsConsumer(channels_graphql_ws.GraphqlWsConsumer):
    """Channels WebSocket consumer which provides GraphQL API."""
    schema = schema_graphql.schema

    # Uncomment to send keepalive message every 42 seconds.
    # send_keepalive_every = 42

    # Uncomment to process requests sequentially (useful for tests).
    # strict_ordering = True

    async def on_connect(self, payload):
        """New client connection handler."""
        # You can `raise` from here to reject the connection.
        print("New client connected!")


websocket_urlpatterns = [
    path("graphql", MyGraphqlWsConsumer.as_asgi()),
]
