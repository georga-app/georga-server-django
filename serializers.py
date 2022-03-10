from rest_framework import serializers

from call_for_volunteers.models import *


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = '__all__'


class GeneralWorkAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralWorkAvailability
        fields = '__all__'


class OpeningTimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpeningTime
        fields = '__all__'


class SinglePersonUptimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SinglePersonUptime
        fields = '__all__'


class HelpOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = HelpOperation
        fields = '__all__'


class ActionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionCategory
        fields = '__all__'


class QualificationTechnicalSerializer(serializers.ModelSerializer):
    class Meta:
        model = QualificationTechnical
        fields = '__all__'


class QualificationLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = QualificationLanguage
        fields = '__all__'


class QualificationLicenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = QualificationLicense
        fields = '__all__'


class QualificationHealthSerializer(serializers.ModelSerializer):
    class Meta:
        model = QualificationHealth
        fields = '__all__'


class QualificationAdministrativeSerializer(serializers.ModelSerializer):
    class Meta:
        model = QualificationAdministrative
        fields = '__all__'


class RestrictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restriction
        fields = '__all__'


class EquipmentProvidedSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentProvided
        fields = '__all__'


class EquipmentSelfSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentSelf
        fields = '__all__'


class PublicationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicationCategory
        fields = '__all__'
