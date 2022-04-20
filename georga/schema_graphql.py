import channels_graphql_ws
import graphene
import graphql_jwt
import jwt
from django import forms
from django.contrib.auth.password_validation import validate_password
from graphene_django.forms.mutation import DjangoModelFormMutation
from django.core.exceptions import ValidationError
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphql_jwt.decorators import login_required, staff_member_required

from . import settings
from .email import Email
from .models import (
    Person,
    QualificationLanguage,
    HelpOperation,
    ActionCategory,
    QualificationTechnical,
    QualificationLicense,
    QualificationHealth,
    QualificationAdministrative,
    Restriction,
    EquipmentProvided,
    EquipmentSelf, Location, Poll, PollChoice,
)


# QualificationLanguage
class QualificationLanguageType(DjangoObjectType):
    class Meta:
        model = QualificationLanguage
        fields = '__all__'
        filter_fields = ['id', 'name']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


class QualificationLanguageInput(graphene.InputObjectType):
    name = graphene.String(required=False)


class CreateQualificationLanguage(graphene.Mutation):
    qualification_language = graphene.Field(QualificationLanguageType)

    class Arguments:
        qualification_language_data = QualificationLanguageInput(required=True)

    @staff_member_required
    def mutate(self, info, qualification_language_data=None):
        qualification_language = QualificationLanguage()
        for k, v in qualification_language_data.items():
            if v is not None:
                setattr(qualification_language, k, v)

        qualification_language.save()
        return CreateQualificationLanguage(
            qualification_language=qualification_language)


class UpdateQualificationLanguage(graphene.Mutation):
    qualification_language = graphene.Field(QualificationLanguageType)

    class Arguments:
        id = graphene.ID()
        qualification_language_data = QualificationLanguageInput(required=True)

    @staff_member_required
    def mutate(self, info, id=None, qualification_language_data=None):
        qualification_language = QualificationLanguage.objects.get(pk=id)

        for k, v in qualification_language_data.items():
            if v is not None:
                setattr(qualification_language, k, v)

        try:
            qualification_language.full_clean()
            qualification_language.save()
            return UpdateQualificationLanguage(
                qualification_language=qualification_language)

        except ValidationError as e:
            raise Exception(e)


class DeleteQualificationLanguage(graphene.Mutation):
    ok = graphene.Boolean()

    class Arguments:
        id = graphene.ID()

    @staff_member_required
    def mutate(self, info, id=None):
        qualification_language = QualificationLanguage.objects.get(pk=id)
        if qualification_language is not None:
            qualification_language.delete()
        return DeleteQualificationLanguage(ok=True)


# Person
class PersonType(DjangoObjectType):
    class Meta:
        model = Person
        fields = '__all__'
        filter_fields = {
            'email': ['icontains']
        }
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


class PersonInput(graphene.InputObjectType):
    email = graphene.String(required=False)
    first_name = graphene.String(required=False)
    last_name = graphene.String(required=False)
    mobile_phone = graphene.String(required=False)
    qualification_languages = graphene.List(graphene.ID)


class CreatePerson(graphene.Mutation):
    person = graphene.Field(PersonType)

    class Arguments:
        person_data = PersonInput(required=True)

    def mutate(self, info, person_data=None):
        person = Person()

        for k, v in person_data.items():
            if v is not None:
                setattr(person, k, v)

        person.username = person_data.email
        person.set_unusable_password()
        # Save for creating relationships to other objects
        try:
            person.full_clean()
            person.save()
        except ValidationError as e:
            raise Exception(e)

        for i in person_data.qualification_languages:
            try:
                ql = QualificationLanguage.objects.get(pk=i)
                person.qualifications_language.add(ql)
            except Exception:
                pass

        try:
            person.full_clean()
            person.save()
            Email.send_activation_email(person)
            return CreatePerson(person=person)

        except ValidationError as e:
            raise Exception(e)


class UpdatePerson(graphene.Mutation):
    person = graphene.Field(PersonType)

    class Arguments:
        id = graphene.ID()
        person_data = PersonInput(required=True)

    def mutate(self, info, id=None, person_data=None):
        person = Person.objects.get(pk=id)

        for k, v in person_data.items():
            if v is not None and k != 'password':
                setattr(person, k, v)

        for i in person_data.qualification_languages:
            try:
                ql = QualificationLanguage.objects.get(pk=i)
                person.qualifications_language.add(ql)
            except Exception:
                pass

        try:
            person.full_clean()
            person.save()
            return UpdatePerson(person=person)

        except ValidationError as e:
            raise Exception(e)


class DeletePerson(graphene.Mutation):
    ok = graphene.Boolean()

    class Arguments:
        id = graphene.ID()

    def mutate(self, info, id):
        person = Person.objects.get(pk=id)
        if person is not None:
            person.delete()
        return DeletePerson(ok=True)


class ChangePasswordPerson(graphene.Mutation):
    person = graphene.Field(PersonType)

    class Arguments:
        id = graphene.ID()
        password = graphene.String()

    def mutate(self, info, id=None, password=None):
        person = Person.objects.get(pk=id)
        if password is not None:
            person.set_password(password)
            person.save()
        return ChangePasswordPerson(person=person)


class RegisterPersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ('email', 'password', 'first_name', 'last_name', 'mobile_phone', 'qualifications_language')

    def clean_password(self):
        password = self.cleaned_data['password']
        validate_password(password)
        return password

    def save(self, commit=True):
        self.full_clean()
        person = super().save(commit=False)
        person.username = self.cleaned_data["email"]
        person.set_password(self.cleaned_data["password"])
        # person.set_unusable_password()
        if commit:
            person.save()
            self.save_m2m()
        Email.send_activation_email(person)
        return person


class RegisterPerson(DjangoModelFormMutation):
    person = graphene.Field(PersonType)

    class Meta:
        form_class = RegisterPersonForm
        exclude_fields = ('id',)


class ActivatePerson(graphene.Mutation):
    person = graphene.Field(PersonType)

    class Arguments:
        token = graphene.String()

    def mutate(self, info, token=None):
        payload = jwt.decode(
            token, settings.GRAPHQL_JWT['JWT_PUBLIC_KEY'],
            algorithms=["RS256"])
        if payload.get('sub') == 'activation':
            person = Person.objects.get(pk=payload.get('uid'))
            person.is_active = True
            person.save()
        else:
            person = None
        return ActivatePerson(person=person)


class ActivatePersonRequest(graphene.Mutation):
    done = graphene.Boolean()

    class Arguments:
        email = graphene.String()

    def mutate(self, info, email=None):
        if email is not None:
            person = Person.objects.get(email=email)
            if person is not None:
                if not person.is_active:
                    Email.send_activation_email(person)
        return ResetPasswordRequest(done=True)


class ResetPasswordToken(graphene.Mutation):
    person = graphene.Field(PersonType)

    class Arguments:
        token = graphene.String()
        password = graphene.String()

    def mutate(self, info, token=None, password=None):
        payload = jwt.decode(
            token, settings.GRAPHQL_JWT['JWT_PUBLIC_KEY'],
            algorithms=["RS256"])
        if payload.get('sub') == 'password_reset':
            person = Person.objects.get(pk=payload.get('uid'))
            if person.password_modified.timestamp() < payload.get('iat'):
                person.set_password(password)
                person.save()
            else:
                person = None
        else:
            person = None

        return ResetPasswordToken(person=person)


class ResetPasswordRequest(graphene.Mutation):
    done = graphene.Boolean()

    class Arguments:
        email = graphene.String()

    def mutate(self, info, email=None):
        if email is not None:
            print(email)
            person = Person.objects.get(email=email)
            if person is not None:
                Email.send_password_reset_email(person)
        return ResetPasswordRequest(done=True)


# HelpOperation
class HelpOperationType(DjangoObjectType):
    class Meta:
        model = HelpOperation
        fields = '__all__'
        filter_fields = ['id']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


# ActionCategory
class ActionCategoryType(DjangoObjectType):
    class Meta:
        model = ActionCategory
        fields = '__all__'
        filter_fields = ['id']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


# QualificationTechnical
class QualificationTechnicalType(DjangoObjectType):
    class Meta:
        model = QualificationTechnical
        fields = '__all__'
        filter_fields = ['id']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


# QualificationLicense
class QualificationLicenseType(DjangoObjectType):
    class Meta:
        model = QualificationLicense
        fields = '__all__'
        filter_fields = ['id']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


# QualificationHealth
class QualificationHealthType(DjangoObjectType):
    class Meta:
        model = QualificationHealth
        fields = '__all__'
        filter_fields = ['id']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


# QualificationAdministrative
class QualificationAdministrativeType(DjangoObjectType):
    class Meta:
        model = QualificationAdministrative
        fields = '__all__'
        filter_fields = ['id']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


# Restriction
class RestrictionType(DjangoObjectType):
    class Meta:
        model = Restriction
        fields = '__all__'
        filter_fields = ['id']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


# EquipmentProvided
class EquipmentProvidedType(DjangoObjectType):
    class Meta:
        model = EquipmentProvided
        fields = '__all__'
        filter_fields = ['id']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


# EquipmentSelf
class EquipmentSelfType(DjangoObjectType):
    class Meta:
        model = EquipmentSelf
        fields = '__all__'
        filter_fields = ['id']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


# Location
class LocationType(DjangoObjectType):
    class Meta:
        model = Location
        fields = '__all__'
        filter_fields = ['address']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


# Location
class PollType(DjangoObjectType):
    class Meta:
        model = Poll
        fields = '__all__'
        filter_fields = ['uuid']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


# Location
class PollChoiceType(DjangoObjectType):
    class Meta:
        model = PollChoice
        fields = '__all__'
        filter_fields = ['uuid']
        interfaces = (relay.Node,)

    @classmethod
    @login_required
    def get_queryset(cls, queryset, info):
        return super().get_queryset(queryset, info)


class Query(graphene.ObjectType):
    all_persons = DjangoFilterConnectionField(
        PersonType)
    all_qualification_languages = DjangoFilterConnectionField(
        QualificationLanguageType)
    all_help_operations = DjangoFilterConnectionField(
        QualificationLanguageType)
    all_action_categories = DjangoFilterConnectionField(
        ActionCategoryType)
    all_qualifications_technical = DjangoFilterConnectionField(
        QualificationTechnicalType)
    all_qualifications_license = DjangoFilterConnectionField(
        QualificationLicenseType)
    all_qualifications_health = DjangoFilterConnectionField(
        QualificationHealthType)
    all_qualifications_administrative = DjangoFilterConnectionField(
        QualificationAdministrativeType)
    all_restrictions = DjangoFilterConnectionField(
        RestrictionType)
    all_equipment_provided = DjangoFilterConnectionField(
        EquipmentProvidedType)
    all_equipment_self = DjangoFilterConnectionField(
        EquipmentSelfType)
    all_locations = DjangoFilterConnectionField(LocationType)
    all_polls = DjangoFilterConnectionField(PollType)
    all_poll_choices = DjangoFilterConnectionField(PollChoiceType)


class Mutation(graphene.ObjectType):
    # Authorization
    token_auth = graphql_jwt.ObtainJSONWebToken.Field()
    verify_token = graphql_jwt.Verify.Field()
    refresh_token = graphql_jwt.Refresh.Field()

    # Persons
    create_person = CreatePerson.Field()
    update_person = UpdatePerson.Field()
    delete_person = DeletePerson.Field()
    # Person Flows
    change_password = ChangePasswordPerson.Field()
    register_person = RegisterPerson.Field()
    activate_person = ActivatePerson.Field()
    request_password = ResetPasswordRequest.Field()
    reset_password = ResetPasswordToken.Field()
    request_activation = ActivatePersonRequest.Field()

    # Qualification language
    create_qualification_language = CreateQualificationLanguage.Field()
    update_qualification_language = UpdateQualificationLanguage.Field()
    delete_qualification_language = DeleteQualificationLanguage.Field()


class MySubscription(channels_graphql_ws.Subscription):
    """Simple GraphQL subscription."""

    # Leave only latest 64 messages in the server queue.
    notification_queue_limit = 64

    # Subscription payload.
    event = graphene.String()

    class Arguments:
        """That is how subscription arguments are defined."""
        arg1 = graphene.String()
        arg2 = graphene.String()

    @staticmethod
    def subscribe(root, info, arg1, arg2):
        """Called when user subscribes."""

        # Return the list of subscription group names.
        return ["group42"]

    @staticmethod
    def publish(payload, info, arg1, arg2):
        """Called to notify the client."""

        # Here `payload` contains the `payload` from the `broadcast()`
        # invocation (see below). You can return `MySubscription.SKIP`
        # if you wish to suppress the notification to a particular
        # client. For example, this allows to avoid notifications for
        # the actions made by this particular client.

        return MySubscription(event="Something has happened!")


class Subscription(graphene.ObjectType):
    """Root GraphQL subscription."""
    my_subscription = MySubscription.Field()


schema = graphene.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)
