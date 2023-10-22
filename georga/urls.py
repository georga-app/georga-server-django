# For copyright and license terms, see COPYRIGHT.md (top level of repository)
# Repository: https://github.com/georga-app/georga-server-django

from django.urls import path
from graphene_django.views import GraphQLView
from django.contrib import admin
from django.views.decorators.csrf import csrf_exempt

from .schemas import schema

urlpatterns = [
    # GraphQL
    path('graphql', csrf_exempt(GraphQLView.as_view(graphiql=True, schema=schema))),

    # Admin view
    path('admin/', admin.site.urls),
]
