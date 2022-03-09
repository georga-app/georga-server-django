from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from graphene_django.views import GraphQLView
from rest_framework import routers

from . import viewsets
from .forms import SignUpForm, CompanySignUpForm
from .views import index, imprint, data_protection, faq, SignUpView, CompanyRegistrationView

router = routers.DefaultRouter()
router.register(r'users', viewsets.PersonViewSet)

urlpatterns = [
    path('', index, name='index'),
    path('imprint/', imprint, name='imprint'),
    path('faq/', faq, name='faq'),
    path('data_protection/', data_protection, name='data_protection'),
    path('accounts/register/', SignUpView.as_view(form_class=SignUpForm), name='django_registration_register'),
    path('accounts/company_register/', CompanyRegistrationView.as_view(form_class=CompanySignUpForm), name='django_company_register'),
    path('accounts/', include('django_registration.backends.activation.urls')),
    path('accounts/', include('django.contrib.auth.urls')),

    # Api
    path('api/', include(router.urls)),
    path('api-auth/', include("rest_framework.urls", namespace='rest_framework')),
    # Api docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # GraphQL
    path('graphql/', GraphQLView.as_view(graphiql=True)),

]
