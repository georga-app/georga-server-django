import datetime
import logging
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django_registration.forms import RegistrationFormUniqueEmail, RegistrationFormTermsOfService
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from phone_field import PhoneFormField
from .models import *

logger = logging.getLogger('forms')

general_work_widget = forms.MultiWidget(widgets=[
    forms.CheckboxSelectMultiple,
    forms.CheckboxSelectMultiple
]),

class SignUpForm(RegistrationFormUniqueEmail, RegistrationFormTermsOfService):
    def __init__(self, *args, **kwargs):
        super(SignUpForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.add_input(Submit('submit', 'Registrieren'))
        self.helper.tag = 'div'
        self.helper.error_text_inline = True
        self.helper.form_id = 'sign_up_form'
        self.helper.form_class = 'registration'
        self.helper.form_method = 'post'
        self.helper.wrapper_class = 'test'
        self.helper.inline_class = 'test'

        self.fields['expiration_date'].widget.attrs.update({
            "min": (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        })


    password1 = forms.CharField(
        max_length=30,
        required=False,
        label="Password1",
        help_text="Optionale Angabe",
    )
    password2 = forms.CharField(
        max_length=30,
        required=False,
        label="Password2",
        help_text="Optionale Angabe",
    )
    #company = forms.CharField(
    #    max_length=50,
    #    required=False,
    #    label="Firmenname",
    #    help_text="Erforderlich",
    #)
    title = forms.ChoiceField(
        label="Anrede",
        required=False,
        choices=Person.TITLES,
        help_text="Optionale Angabe",
        initial="none",
    )
    firstname = forms.CharField(
        max_length=30,
        required=True,
        label="Vorname",
        help_text="Erforderlich",
    )
    lastname = forms.CharField(
        max_length=30,
        required=True,
        label="Nachname",
        help_text="Erforderlich",
    )
    email = forms.EmailField(
        max_length=50,
        required=True,
        label="E-Mail-Adresse",
        help_text="Erforderlich, zur primären Benachrichtigung",
    )
    expiration_date = forms.DateField(
        required=False,
        label="Registriert bleiben bis",
        help_text="Optional. Kein Datum angeben, um permanent registriert zu bleiben",
        widget=forms.TextInput(attrs={'type': 'date'}),
    )
    private_phone = forms.CharField(
        label="Festnetznummer",
        help_text="Optional.",
    )
    mobile_phone = forms.CharField(
        label="Mobilnummer",
        help_text="Optional.",
    )
    street = forms.CharField(
        max_length=50,
        required=False,
        label="Straße",
        help_text="Freiwillig - erleichtert uns ggf. die räumliche Zuordnung für Hilfsangebote",
    )
    number = forms.CharField(
        max_length=8,
        required=False,
        label="Hausnummer",
        help_text="Freiwillig",
    )
    postal_code = forms.CharField(
        max_length=5,
        required=True,
        label="PLZ",
        help_text="Erforderlich",
        validators=[RegexValidator('^\\d{5}$', message="Keine gültige Postleitzahl.")],
        widget=forms.TextInput(attrs={'type': 'text', 'pattern': '^\\d{5}$'}),
    )
    city = forms.CharField(
        max_length=50,
        required=True,
        label="Ort",
        help_text="Erforderlich",
    )
    occupation = forms.CharField(
        max_length=50,
        required=False,
        label="Beruf / Branche",
        help_text="Angestellt, Student (Fach, Semster), Freiberuflich? - Freiwillige Angabe",
    )
    qualifications_language = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=QualificationLanguage.objects.all().values_list(
            "id", "name"),
        required=False,
        label="Ihre Sprachkenntnisse",
        help_text="Optional, Mehrfachauswahl möglich",
    )
    qualifications_technical = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=QualificationTechnical.objects.all().values_list(
            "id", "name"),
        required=False,
        label="Ihre technischen Qualifikationen",
        help_text="Optional, Mehrfachauswahl möglich",
    )
    qualifications_health = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=QualificationHealth.objects.all().values_list(
            "id", "name"),
        required=False,
        label="Ihre Qualifikationen im Gesundheitswesen",
        help_text="Optional, Mehrfachauswahl möglich",
    )
    qualifications_license = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=QualificationLicense.objects.all().values_list(
            "id", "name"),
        required=False,
        label="Ihre Führerscheinklassen",
        help_text="Optaional, Mehrfachauswahl möglich",
    )
    qualifications_administrative = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=QualificationAdministrative.objects.all().values_list(
            "id", "name"),
        required=False,
        label="Ihre Qualifikationen in der Verwaltung",
        help_text="Optional, Mehrfachauswahl möglich",
    )
    qualification_specific = forms.CharField(
        max_length=60,
        required=False,
        label="Detaillierte Beschreibung, weitere Qualifikationen",
        help_text="Optional",
    )
    restrictions = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=Restriction.objects.all().values_list(
            "id", "name"),
        required=False,
        label="Ggf. Einschränkungen",
        help_text="Optional, Mehrfachauswahl möglich",
    )
    restriction_specific = forms.CharField(
        max_length=60,
        required=False,
        label="Detaillierte Beschreibung, weitere Einschränkungen",
        help_text="Optional",
    )
    help_operations = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=HelpOperation.objects.all().values_list(
            "id", "name"),
        required=False,
        label="Welche Hilfeleistungen können Sie uns unter anderem anbieten?",
        help_text="Optional, Mehrfachauswahl möglich, kann später erweitert werden",
    )
    help_description = forms.CharField(
        max_length=300,
        required=False,
        label="Eigene Beschreibung für mögliche Hilfeleistungen",
        help_text="Optional",
    )
    possible_work_times_mon = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices = (
            (1, "vormittags"),
            (2, "nachmittags"),
            (3, "abends"),
        ),
        required=False,
        label="Montag",
    )
    possible_work_times_tue = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices = (
            (1, "vormittags"),
            (2, "nachmittags"),
            (3, "abends"),
        ),
        required=False,
        label="Dienstag",
    )
    possible_work_times_wed = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices = (
            (1, "vormittags"),
            (2, "nachmittags"),
            (3, "abends"),
        ),
        required=False,
        label="Mittwoch",
    )
    possible_work_times_thu = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices = (
            (1, "vormittags"),
            (2, "nachmittags"),
            (3, "abends"),
        ),
        required=False,
        label="Donnerstag",
    )
    possible_work_times_fri = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices = (
            (1, "vormittags"),
            (2, "nachmittags"),
            (3, "abends"),
        ),
        required=False,
        label="Freitag",
    )
    possible_work_times_sat = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices = (
            (1, "vormittags"),
            (2, "nachmittags"),
            (3, "abends"),
        ),
        required=False,
        label="Samstag",
    )
    possible_work_times_sun = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices = (
            (1, "vormittags"),
            (2, "nachmittags"),
            (3, "abends"),
        ),
        required=False,
        label="Sonntag",
    )
    drk_honorary = forms.BooleanField(
        widget=forms.CheckboxInput,
        label= "Ehrenamtliches Mitglied vom DRK",
        required=False,
    )
    drk_employee = forms.BooleanField(
        widget=forms.CheckboxInput,
        label= "Hauptamtlich (angestellt) tätig beim DRK",
        required=False,
    )
    drk_home = forms.CharField(
        max_length=500,
        required=False,
        label="Falls Sie beim DRK tätig sind, bei welchem Verband?",
    )
    available_for_cleaning = forms.ChoiceField(
        label="Möchten Sie für Aufräumarbeiten im Hochwassergebiet angefragt werden?",
        required=False,
        choices=Person.ANSWER_CLEANING,
        help_text="",
        initial="none",
    )
    only_job_related_topics = forms.ChoiceField(
        label="Möchten Sie NUR für Tätigkeiten innerhalb Ihrer angegebenen Fachbereiche angefragt werden?",
        required=False,
        choices=Person.ANSWER_TOPICS,
        help_text="",
        initial="none",
    )
    tos = forms.BooleanField(
        widget=forms.CheckboxInput,
        label= "Ich habe die <a href='https://www.drk-team-bonn.de/data_protection/'>Datenschutzerklärung</a> zur Kenntnis genommen. Ich willige ein, dass meine Angaben und Daten zur Beantwortung meiner Anfrage elektronisch erhoben und gespeichert werden.",
        error_messages={'required': "Die Registrierung erfordert eine Bestätigung der Datenschutzerklärung."},
    )


    field_order = [
        'title',
        'firstname',
        'lastname',
        'email',
        'expiration_date',
        'street',
        'number',
        'postal_code',
        'city',
        'occupation',
        'drk_honorary',
        'drk_employee',
        'drk_home',
        'qualifications_language',
        'qualifications_license',
        'qualifications_health',
        'qualifications_technical',
        'qualifications_administrative',
        'qualification_specific',
        'restrictions',
        'restriction_specific',
        'tos',
    ]

    class Meta(RegistrationFormUniqueEmail.Meta):
        model = Person
        fields = (
            'firstname',
            'lastname',
            'email',
            'qualifications_language',
            'qualifications_license',
            'qualifications_health',
            'qualifications_technical',
            'qualifications_administrative',
            'qualification_specific',
            'restrictions',
            'restriction_specific',
            'tos',
            #'captcha',
        )

    def save(self, commit=True):
        #person = super(SignUpForm, self).save(commit=commit)
        person = Person()
        person.title = self.cleaned_data['title']
        person.email = self.cleaned_data['email']
        person.username = self.cleaned_data['email']
        person.first_name = self.cleaned_data['firstname']
        person.last_name = self.cleaned_data['lastname']
        person.company = ""
        person.expiration_date = self.cleaned_data['expiration_date']
        person.street = self.cleaned_data['street']
        person.number = self.cleaned_data['number']
        person.postal_code = self.cleaned_data['postal_code']
        person.city = self.cleaned_data['city']
        person.occupation = self.cleaned_data['occupation']
        person.drk_honorary = self.cleaned_data['drk_honorary']
        person.drk_employee = self.cleaned_data['drk_employee']
        person.drk_home = self.cleaned_data['drk_home']
        person.available_for_cleaning = self.cleaned_data['available_for_cleaning']
        person.only_job_related_topics = self.cleaned_data['only_job_related_topics']
        try:
            person.help_operations = self.cleaned_data['help_operations']
        except Exception as e:
            pass
        try:
            person.help_description = self.cleaned_data['help_description']
        except Exception as e:
            pass
        try:
            person.private_phone = self.cleaned_data['private_phone']
        except Exception as e:
            pass
        try:
            person.mobile_phone = self.cleaned_data['mobile_phone']
        except Exception as e:
            pass
        #if commit:
        person.save()
        try:
            person.qualification_specific = self.cleaned_data['qualification_specific']
        except Exception as e:
            pass
        try:
            person.restriction_specific = self.cleaned_data['restriction_specific']
        except Exception as e:
            pass

        try:
            for lang_id in self.cleaned_data['qualifications_language']:
                q = QualificationLanguage.objects.get(id=lang_id)
                person.qualifications_language.add(q)
        except Exception as e:
            pass

        try:
            for lic_id in self.cleaned_data['qualifications_license']:
                q = QualificationLicense.objects.get(id=lic_id)
                person.qualifications_license.add(q)
        except Exception as e:
            pass

        try:
            for health_id in self.cleaned_data['qualifications_health']:
                q = QualificationHealth.objects.get(id=health_id)
                person.qualifications_health.add(q)
        except Exception as e:
            pass

        try:
            for tec_id in self.cleaned_data['qualifications_technical']:
                q = QualificationTechnical.objects.get(id=tec_id)
                person.qualifications_technical.add(q)
        except Exception as e:
            pass

        try:
            for adm_id in self.cleaned_data['qualifications_administrative']:
                q = QualificationHealth.objects.get(id=adm_id)
                person.qualifications_administrative.add(q)
        except Exception as e:
            pass

        try:
            for r_id in self.cleaned_data['restrictions']:
                r = Restriction.objects.get(id=r_id)
                person.restrictions.add(r)
        except Exception as e:
            pass

        try:
            for ho_id in self.cleaned_data['help_operations']:
                q = QualificationHealth.objects.get(id=ho_id)
                person.health_operations.add(q)
        except Exception as e:
            pass

        try:
            forenoon = False
            afternoon = False
            evening = False

            work_ids = self.cleaned_data['possible_work_times_mon']
            if '1' in work_ids:
                forenoon = True
            if '2' in work_ids:
                afternoon = True
            if '3' in work_ids:
                evening = True
            w = GeneralWorkAvailability()
            w.weekday = 1
            w.forenoon = forenoon
            w.afternoon = afternoon
            w.evening = evening
            w.save()
            person.possible_work_times.add(w)
            person.save()
        except Exception as e:
            pass

        try:
            forenoon = False
            afternoon = False
            evening = False

            work_ids = self.cleaned_data['possible_work_times_tue']
            if '1' in work_ids:
                forenoon = True
            if '2' in work_ids:
                afternoon = True
            if '3' in work_ids:
                evening = True
            w = GeneralWorkAvailability()
            w.weekday = 2
            w.forenoon = forenoon
            w.afternoon = afternoon
            w.evening = evening
            w.save()
            person.possible_work_times.add(w)
        except Exception as e:
            pass

        try:
            forenoon = False
            afternoon = False
            evening = False

            work_ids = self.cleaned_data['possible_work_times_wed']
            if '1' in work_ids:
                forenoon = True
            if '2' in work_ids:
                afternoon = True
            if '3' in work_ids:
                evening = True
            w = GeneralWorkAvailability()
            w.weekday = 3
            w.forenoon = forenoon
            w.afternoon = afternoon
            w.evening = evening
            w.save()
            person.possible_work_times.add(w)
        except Exception as e:
            pass

        try:
            forenoon = False
            afternoon = False
            evening = False

            work_ids = self.cleaned_data['possible_work_times_thu']
            if '1' in work_ids:
                forenoon = True
            if '2' in work_ids:
                afternoon = True
            if '3' in work_ids:
                evening = True
            w = GeneralWorkAvailability()
            w.weekday = 4
            w.forenoon = forenoon
            w.afternoon = afternoon
            w.evening = evening
            w.save()
            person.possible_work_times.add(w)
        except Exception as e:
            pass

        try:
            forenoon = False
            afternoon = False
            evening = False

            work_ids = self.cleaned_data['possible_work_times_fri']
            if '1' in work_ids:
                forenoon = True
            if '2' in work_ids:
                afternoon = True
            if '3' in work_ids:
                evening = True
            w = GeneralWorkAvailability()
            w.weekday = 5
            w.forenoon = forenoon
            w.afternoon = afternoon
            w.evening = evening
            w.save()
            person.possible_work_times.add(w)
        except Exception as e:
            pass

        try:
            forenoon = False
            afternoon = False
            evening = False

            work_ids = self.cleaned_data['possible_work_times_sat']
            if '1' in work_ids:
                forenoon = True
            if '2' in work_ids:
                afternoon = True
            if '3' in work_ids:
                evening = True
            w = GeneralWorkAvailability()
            w.weekday = 6
            w.forenoon = forenoon
            w.afternoon = afternoon
            w.evening = evening
            w.save()
            person.possible_work_times.add(w)
        except Exception as e:
            pass

        try:
            forenoon = False
            afternoon = False
            evening = False

            work_ids = self.cleaned_data['possible_work_times_sun']
            if '1' in work_ids:
                forenoon = True
            if '2' in work_ids:
                afternoon = True
            if '3' in work_ids:
                evening = True
            w = GeneralWorkAvailability()
            w.weekday = 7
            w.forenoon = forenoon
            w.afternoon = afternoon
            w.evening = evening
            w.save()
            person.possible_work_times.add(w)
        except Exception as e:
            pass

        #if commit:
        person.save()
        return person

    def clean_date(self):
        date = self.cleaned_data['date']
        if date < datetime.date.today():
            raise forms.ValidationError("Datum darf nicht in der Vergangenheit liegen.")
        return date


class CompanySignUpForm(SignUpForm):

    company = forms.CharField(
        max_length=50,
        required=True,
        label="Firmenname",
        help_text="Erforderlich",
    )
    company_phone = PhoneFormField(
        required=False,
        label="Festnetznummer",
        help_text="Optional",
    )
    company_phone_mobile = PhoneFormField(
        required=False,
        label="Mobilnummer",
        help_text="Optional",
    )
    emergency_phone = PhoneFormField(
        required=False,
        label="Notfallnummer",
        help_text="Optionale. Notfall-Rufnummer, falls möglich.",
    )
    #opening_times_mon = forms.MultipleChoiceField(
    #    widget=forms.MultiWidget(widgets=[
    #    forms.DateInput(format='%d/%m/%Y'),
    #    forms.DateInput(format='%d/%m/%Y')
    #    ]),
    #    required=False,
    #    label="Montag",
    #)
    def save(self, commit=True):
        #person = super(CompanySignUpForm, self).save(commit=True)
        person = Person()
        person.title = self.cleaned_data['title']
        person.company = self.cleaned_data['company']
        person.email = self.cleaned_data['email']
        person.username = self.cleaned_data['email']
        person.first_name = self.cleaned_data['firstname']
        person.last_name = self.cleaned_data['lastname']
        person.expiration_date = self.cleaned_data['expiration_date']
        person.company_phone = self.cleaned_data['company_phone']
        person.company_phone_mobile = self.cleaned_data['company_phone_mobile']
        person.emergency_phone = self.cleaned_data['emergency_phone']
        person.street = self.cleaned_data['street']
        person.number = self.cleaned_data['number']
        person.postal_code = self.cleaned_data['postal_code']
        person.city = self.cleaned_data['city']
        person.occupation = self.cleaned_data['occupation']
        person.help_description = self.cleaned_data['help_description']
        #if commit:
        person.save()
        return person

