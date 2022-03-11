from django.urls import path
from graphene_django.views import GraphQLView

urlpatterns = [
    # GraphQL
    path('graphql/', GraphQLView.as_view(graphiql=True)),
]
