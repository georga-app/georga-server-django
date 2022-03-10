import graphene
from django.core.exceptions import ValidationError
from graphene_django import DjangoObjectType

from call_for_volunteers.models import Person, QualificationLanguage


# QualificationLanguage
class QualificationLanguageType(DjangoObjectType):
    class Meta:
        model = QualificationLanguage
        fields = '__all__'


class QualificationLanguageInput(graphene.InputObjectType):
    name = graphene.String(required=False)


class CreateQualificationLanguage(graphene.Mutation):
    qualification_language = graphene.Field(QualificationLanguageType)

    class Arguments:
        qualification_language_data = QualificationLanguageInput(required=True)

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

        person.username = person_data.email
        person.password = "NOT_SET"
        for k, v in person_data.items():
            if v is not None:
                setattr(person, k, v)

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
            if (k == 'password') and (v is not None):
                person.set_password(person_data.password)
            else:
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


class Query(graphene.ObjectType):
    persons = graphene.List(PersonType)
    qualification_languages = graphene.List(QualificationLanguageType)

    def resolve_persons(root, info):
        return Person.objects.all()

    def resolve_qualification_languages(root, info):
        return QualificationLanguage.objects.all()


class Mutation(graphene.ObjectType):
    create_person = CreatePerson.Field()
    update_person = UpdatePerson.Field()
    delete_person = DeletePerson.Field()

    create_qualification_language = CreateQualificationLanguage.Field()
    update_qualification_language = UpdateQualificationLanguage.Field()
    delete_qualification_language = DeleteQualificationLanguage.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
