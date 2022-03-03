from django.urls import path, re_path, include
from .views import index, imprint, data_protection, faq, SignUpView, RegistrationDoneView
from .forms import SignUpForm

urlpatterns = [
    path('', index, name='index'),
    path('imprint/', imprint, name='imprint'),
    path('faq/', faq, name='faq'),
    path('data_protection/', data_protection, name='data_protection'),
    re_path('^accounts/register/$', SignUpView.as_view(form_class=SignUpForm), name='django_registration_register'),
    path('accounts/', include('django_registration.backends.activation.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]
