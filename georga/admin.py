# For copyright and license terms, see COPYRIGHT.md (top level of repository)
# Repository: https://github.com/georga-app/georga-server-django

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


class UUIDModelAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, *args, **kwargs):
        return ('gid', 'uuid') + super().get_readonly_fields(*args, **kwargs)
    list_display = ['__str__', 'gid']


class TimestampsModelAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, *args, **kwargs):
        return ('created_at', 'modified_at') + super().get_readonly_fields(*args, **kwargs)


class GeorgaModelAdmin(UUIDModelAdmin, TimestampsModelAdmin):
    pass


admin.site.register(ACE, GeorgaModelAdmin)
admin.site.register(Device, GeorgaModelAdmin)
admin.site.register(Equipment, GeorgaModelAdmin)
admin.site.register(Location, GeorgaModelAdmin)
admin.site.register(LocationCategory, GeorgaModelAdmin)
admin.site.register(Message, GeorgaModelAdmin)
admin.site.register(Operation, GeorgaModelAdmin)
admin.site.register(Organization, GeorgaModelAdmin)
admin.site.register(Participant, GeorgaModelAdmin)
admin.site.register(Person, GeorgaModelAdmin)
admin.site.register(PersonProperty, GeorgaModelAdmin)
admin.site.register(PersonPropertyGroup, GeorgaModelAdmin)
admin.site.register(PersonToObject, GeorgaModelAdmin)
admin.site.register(Project, GeorgaModelAdmin)
admin.site.register(Resource, GeorgaModelAdmin)
admin.site.register(Role, GeorgaModelAdmin)
admin.site.register(RoleSpecification, GeorgaModelAdmin)
admin.site.register(Shift, GeorgaModelAdmin)
admin.site.register(Task, GeorgaModelAdmin)
admin.site.register(TaskField, GeorgaModelAdmin)
