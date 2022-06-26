from django.contrib import admin

# Register your models here.
from .models import (
    Person,
    Device,
    Resource,
    Organization,
    Project,
    Deployment,
    Task,
    TaskType,
    Schedule,
    Timeslot,
    Qualification,
    QualificationType,
    Restriction,
    Role,
    EquipmentSelf,
    EquipmentProvided,
    Location,
    LocationType,
    Notification,
    NotificationType,
)

admin.site.register(Person)
admin.site.register(Device)
admin.site.register(Resource)
admin.site.register(Organization)
admin.site.register(Project)
admin.site.register(Deployment)
admin.site.register(Task)
admin.site.register(TaskType)
admin.site.register(Schedule)
admin.site.register(Timeslot)
admin.site.register(Qualification)
admin.site.register(QualificationType)
admin.site.register(Restriction)
admin.site.register(Role)
admin.site.register(EquipmentSelf)
admin.site.register(EquipmentProvided)
admin.site.register(Location)
admin.site.register(LocationType)
admin.site.register(Notification)
admin.site.register(NotificationType)
