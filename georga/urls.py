from django.urls import path
from graphene_django.views import GraphQLView
from django.contrib import admin

from .schema_graphql import schema

urlpatterns = [
    # GraphQL
    path('graphql', GraphQLView.as_view(graphiql=True, schema=schema)),

    # Admin view
    path('admin/', admin.site.urls),
]
