from rest_framework import viewsets, permissions

from call_for_volunteers.models import Person
from call_for_volunteers.serializers import PersonSerializer


class PersonViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.DjangoModelPermissionsOrAnonReadOnly]
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    filterset_fields = ['username']
