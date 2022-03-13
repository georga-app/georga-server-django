from django.contrib import admin

# Register your models here.
from .models import (
    Person,
    HelpOperation,
    ActionCategory,
    EquipmentSelf,
    EquipmentProvided,
    Restriction,
    QualificationAdministrative,
    QualificationHealth,
    QualificationLicense,
    QualificationLanguage,
    QualificationTechnical,
)

admin.site.register(Person)
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
