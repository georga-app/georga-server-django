import logging
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth import login, authenticate
#from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django.views.generic.base import TemplateView
from django_registration.backends.activation.views import RegistrationView, ActivationView
from .forms import SignUpForm, CompanySignUpForm


logger = logging.getLogger('forms')

class RegistrationDoneView(TemplateView):
    template_name = 'django_registration/registration_complete.html'


class SignUpView(RegistrationView):
    form = SignUpForm()
    template_name = 'django_registration/registration_form.html'
    success_url = '/accounts/register/complete/'

    def get_success_url(self, user=None):
        return redirect('/accounts/register/complete/')

    def post(self, request):
        form = SignUpForm(request.POST)
        if not form.is_valid():
            errors = {}
            for field in form.errors.keys():
                errors[field] = form.errors[field].as_text()
                logger.error("ValidationError: %s[%s] <- %s" % (
                    type(form),
                    field,
                    form.errors[field].as_text()
                ))
            return render(request, 'core/not_valid.html', {"errors": errors})
        self.register(form)
        return redirect('/accounts/register/complete/')


def index(request):
    return render(request, 'core/index.html')

def imprint(request):
    return render(request, 'core/imprint.html')

def data_protection(request):
    return render(request, 'core/data_protection.html')

def faq(request):
    return render(request, 'core/faq.html')


class CompanyRegistrationView(RegistrationView):
    form = CompanySignUpForm()
    template_name = 'core/company_registration.html'
    success_url = '/accounts/register/complete/'

    def get_success_url(self, user=None):
        return redirect('/accounts/register/complete/')

    def post(self, request):
        form = CompanySignUpForm(request.POST)
        if not form.is_valid():
            errors = {}
            for field in form.errors.keys():
                errors[field] = form.errors[field].as_text()
                logger.error("ValidationError: %s[%s] <- %s" % (
                    type(form),
                    field,
                    form.errors[field].as_text()
                ))
            #self.form.save(True)
            return render(request, 'core/not_valid.html', {"errors": errors})
        self.register(form)
        return redirect('/accounts/register/complete/')


class IndividualActivationView(ActivationView):
    template_name = 'core/individual_activation.html'


class CompanyActivationView(ActivationView):
    template_name = 'core/company_activation.html'
