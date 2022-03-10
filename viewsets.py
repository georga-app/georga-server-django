from rest_framework import viewsets, permissions

from call_for_volunteers.models import Person, GeneralWorkAvailability, OpeningTime, SinglePersonUptime, QualificationTechnical, ActionCategory, HelpOperation, EquipmentProvided, Restriction, QualificationAdministrative, QualificationHealth, QualificationLicense, QualificationLanguage, PublicationCategory, EquipmentSelf
from call_for_volunteers.serializers import PersonSerializer, GeneralWorkAvailabilitySerializer, OpeningTimeSerializer, QualificationTechnicalSerializer, ActionCategorySerializer, HelpOperationSerializer, SinglePersonUptimeSerializer, EquipmentProvidedSerializer, RestrictionSerializer, QualificationAdministrativeSerializer, QualificationHealthSerializer, QualificationLicenseSerializer, QualificationLanguageSerializer, EquipmentSelfSerializer


class PersonViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    lookup_field = 'email'


class GeneralWorkAvailabilityViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = GeneralWorkAvailability.objects.all()
    serializer_class = GeneralWorkAvailabilitySerializer


class OpeningTimeViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = OpeningTime.objects.all()
    serializer_class = OpeningTimeSerializer


class SinglePersonUptimeViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = SinglePersonUptime.objects.all()
    serializer_class = SinglePersonUptimeSerializer


class HelpOperationViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = HelpOperation.objects.all()
    serializer_class = HelpOperationSerializer


class ActionCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ActionCategory.objects.all()
    serializer_class = ActionCategorySerializer


class QualificationTechnicalViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = QualificationTechnical.objects.all()
    serializer_class = QualificationTechnicalSerializer


class QualificationLanguageViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = QualificationLanguage.objects.all()
    serializer_class = QualificationLanguageSerializer


class QualificationLicenseViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = QualificationLicense.objects.all()
    serializer_class = QualificationLicenseSerializer


class QualificationHealthViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = QualificationHealth.objects.all()
    serializer_class = QualificationHealthSerializer


class QualificationAdministrativeViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = QualificationAdministrative.objects.all()
    serializer_class = QualificationAdministrativeSerializer


class RestrictionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Restriction.objects.all()
    serializer_class = RestrictionSerializer


class EquipmentProvidedViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = EquipmentProvided.objects.all()
    serializer_class = EquipmentProvidedSerializer


class EquipmentSelfViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = EquipmentSelf.objects.all()
    serializer_class = PersonSerializer


class PublicationCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = PublicationCategory.objects.all()
    serializer_class = EquipmentSelfSerializer
