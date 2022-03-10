from django.contrib import admin

# Register your models here.
from call_for_volunteers.models import Person, GeneralWorkAvailability, OpeningTime, SinglePersonUptime, HelpOperation, ActionCategory, PublicationCategory, EquipmentSelf, EquipmentProvided, Restriction, QualificationAdministrative, QualificationHealth, QualificationLicense, QualificationLanguage, QualificationTechnical

admin.site.register(Person)
admin.site.register(GeneralWorkAvailability)
admin.site.register(OpeningTime)
admin.site.register(SinglePersonUptime)
admin.site.register(HelpOperation)
admin.site.register(ActionCategory)
admin.site.register(QualificationTechnical)
admin.site.register(QualificationLanguage)
admin.site.register(QualificationLicense)
admin.site.register(QualificationHealth)
admin.site.register(QualificationAdministrative)
admin.site.register(Restriction)
admin.site.register(EquipmentProvided)
admin.site.register(EquipmentSelf)
admin.site.register(PublicationCategory)
