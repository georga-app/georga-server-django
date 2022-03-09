import graphene
from graphene_django import DjangoObjectType

from call_for_volunteers.models import Person


class PersonType(DjangoObjectType):
    class Meta:
        model = Person
        fields = '__all__'


class Query(graphene.ObjectType):
    persons = graphene.List(PersonType)
    hello = graphene.String(default_value="Hi!")

    def resolve_persons(root, info):
        # We can easily optimize query count in the resolve method
        return Person.objects.all()


schema = graphene.Schema(query=Query)
