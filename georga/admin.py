from django.contrib import admin

# Register your models here.
from .models import (
    Person,
    Device,
    Resource,
    Organization,
    Project,
    Operation,
    Task,
    TaskField,
    Shift,
    PersonProperty,
    PersonPropertyGroup,
    Role,
    Equipment,
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
admin.site.register(Operation)
admin.site.register(Task)
admin.site.register(TaskField)
admin.site.register(Shift)
admin.site.register(PersonProperty)
admin.site.register(PersonPropertyGroup)
admin.site.register(Role)
admin.site.register(Equipment)
admin.site.register(Location)
admin.site.register(LocationCategory)
admin.site.register(Notification)
admin.site.register(NotificationCategory)
