import graphene
import graphql_jwt
import jwt
from django.core.exceptions import ValidationError
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphql_jwt.decorators import login_required, staff_member_required

from call_for_volunteers.email import Email
from call_for_volunteers.models import Person, QualificationLanguage, HelpOperation, ActionCategory, QualificationTechnical, QualificationLicense, QualificationHealth, QualificationAdministrative, Restriction, EquipmentProvided, EquipmentSelf
from publicsite import settings


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
        return CreateQualificationLanguage(qualification_language=qualification_language)


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
            return UpdateQualificationLanguage(qualification_language=qualification_language)

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
        filter_fields = ['username']
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
            except Exception as e:
                pass

        try:
            person.full_clean()
            person.save()
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
            if v is not None and k is not 'password':
                setattr(person, k, v)

        for i in person_data.qualification_languages:
            try:
                ql = QualificationLanguage.objects.get(pk=i)
                person.qualifications_language.add(ql)
            except Exception as e:
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


class RegisterPerson(graphene.Mutation):
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

        if isinstance(person_data.qualification_languages, list):
            for i in person_data.qualification_languages:
                try:
                    ql = QualificationLanguage.objects.get(pk=i)
                    person.qualifications_language.add(ql)
                except Exception as e:
                    pass

        try:
            person.full_clean()
            person.save()
            person.send_activation_email()
            return CreatePerson(person=person)

        except ValidationError as e:
            raise Exception(e)


class ActivatePerson(graphene.Mutation):
    person = graphene.Field(PersonType)

    class Arguments:
        token = graphene.String()

    def mutate(self, info, token=None):
        payload = jwt.decode(token, settings.GRAPHQL_JWT['JWT_PUBLIC_KEY'], algorithms=["RS256"])
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
                if person.is_active is False:
                    Email.send_activation_email(person)
        return ResetPasswordRequest(done=True)


class ResetPasswordToken(graphene.Mutation):
    person = graphene.Field(PersonType)

    class Arguments:
        token = graphene.String()
        password = graphene.String()

    def mutate(self, info, token=None, password=None):
        payload = jwt.decode(token, settings.GRAPHQL_JWT['JWT_PUBLIC_KEY'], algorithms=["RS256"])
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


class Query(graphene.ObjectType):
    all_persons = DjangoFilterConnectionField(PersonType)
    all_qualification_languages = DjangoFilterConnectionField(QualificationLanguageType)
    all_help_operations = DjangoFilterConnectionField(QualificationLanguageType)
    all_action_categories = DjangoFilterConnectionField(ActionCategoryType)
    all_qualifications_technical = DjangoFilterConnectionField(QualificationTechnicalType)
    all_qualifications_license = DjangoFilterConnectionField(QualificationLicenseType)
    all_qualifications_health = DjangoFilterConnectionField(QualificationHealthType)
    all_qualifications_administrative = DjangoFilterConnectionField(QualificationAdministrativeType)
    all_restrictions = DjangoFilterConnectionField(RestrictionType)
    all_equipment_provided = DjangoFilterConnectionField(EquipmentProvidedType)
    all_equipment_self = DjangoFilterConnectionField(EquipmentSelfType)


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


schema = graphene.Schema(query=Query, mutation=Mutation)
