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
    TaskCategory,
    Schedule,
    Timeslot,
    Qualification,
    QualificationCategory,
    Restriction,
    Role,
    EquipmentSelf,
    EquipmentProvided,
    Location,
    LocationCategory,
    Notification,
    NotificationCategory,
)

admin.site.register(Person)
admin.site.register(Device)
admin.site.register(Resource)
admin.site.register(Organization)
admin.site.register(Project)
admin.site.register(Deployment)
admin.site.register(Task)
admin.site.register(TaskCategory)
admin.site.register(Schedule)
admin.site.register(Timeslot)
admin.site.register(Qualification)
admin.site.register(QualificationCategory)
admin.site.register(Restriction)
admin.site.register(Role)
admin.site.register(EquipmentSelf)
admin.site.register(EquipmentProvided)
admin.site.register(Location)
admin.site.register(LocationCategory)
admin.site.register(Notification)
admin.site.register(NotificationCategory)
