from django.urls import path, include
from .views import index, imprint, data_protection, faq, SignUpView, CompanyRegistrationView
from .forms import SignUpForm, CompanySignUpForm

urlpatterns = [
    path('', index, name='index'),
    path('imprint/', imprint, name='imprint'),
    path('faq/', faq, name='faq'),
    path('data_protection/', data_protection, name='data_protection'),
    path('accounts/register/', SignUpView.as_view(form_class=SignUpForm), name='django_registration_register'),
    path('accounts/company_register/', CompanyRegistrationView.as_view(form_class=CompanySignUpForm), name='django_company_register'),
    path('accounts/', include('django_registration.backends.activation.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]
