import graphene
from graphene_django import DjangoObjectType

from call_for_volunteers.models import Person, QualificationLanguage


class PersonType(DjangoObjectType):
    class Meta:
        model = Person
        fields = '__all__'


class QualificationLanguageType(DjangoObjectType):
    class Meta:
        model = QualificationLanguage
        fields = '__all__'


class Query(graphene.ObjectType):
    persons = graphene.List(PersonType)
    qualification_languages = graphene.List(QualificationLanguageType)

    def resolve_persons(root, info):
        return Person.objects.all()

    def resolve_qualification_languages(root, info):
        return QualificationLanguage.objects.all()


schema = graphene.Schema(query=Query)
