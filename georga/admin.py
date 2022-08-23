from django.contrib import admin

# Register your models here.
from .models import (
    ACE,
    Device,
    Equipment,
    Location,
    LocationCategory,
    Message,
    Operation,
    Organization,
    Participant,
    Person,
    PersonProperty,
    PersonPropertyGroup,
    PersonToObject,
    Project,
    Resource,
    Role,
    RoleSpecification,
    Shift,
    Task,
    TaskField,
)

admin.site.register(ACE)
admin.site.register(Device)
admin.site.register(Equipment)
admin.site.register(Location)
admin.site.register(LocationCategory)
admin.site.register(Message)
admin.site.register(Operation)
admin.site.register(Organization)
admin.site.register(Participant)
admin.site.register(Person)
admin.site.register(PersonProperty)
admin.site.register(PersonPropertyGroup)
admin.site.register(PersonToObject)
admin.site.register(Project)
admin.site.register(Resource)
admin.site.register(Role)
admin.site.register(RoleSpecification)
admin.site.register(Shift)
admin.site.register(Task)
admin.site.register(TaskField)
