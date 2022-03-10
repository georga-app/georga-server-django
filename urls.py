from django.urls import path
from graphene_django.views import GraphQLView

from .views import index, imprint, data_protection, faq

urlpatterns = [
    path('', index, name='index'),
    path('imprint/', imprint, name='imprint'),
    path('faq/', faq, name='faq'),
    path('data_protection/', data_protection, name='data_protection'),

    # GraphQL
    path('graphql/', GraphQLView.as_view(graphiql=True)),
]
