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
        return ('gid',) + super().get_readonly_fields(*args, **kwargs)
    list_display = ['__str__', 'gid']


admin.site.register(ACE, UUIDModelAdmin)
admin.site.register(Device, UUIDModelAdmin)
admin.site.register(Equipment, UUIDModelAdmin)
admin.site.register(Location, UUIDModelAdmin)
admin.site.register(LocationCategory, UUIDModelAdmin)
admin.site.register(Message, UUIDModelAdmin)
admin.site.register(Operation, UUIDModelAdmin)
admin.site.register(Organization, UUIDModelAdmin)
admin.site.register(Participant, UUIDModelAdmin)
admin.site.register(Person, UUIDModelAdmin)
admin.site.register(PersonProperty, UUIDModelAdmin)
admin.site.register(PersonPropertyGroup, UUIDModelAdmin)
admin.site.register(PersonToObject, UUIDModelAdmin)
admin.site.register(Project, UUIDModelAdmin)
admin.site.register(Resource, UUIDModelAdmin)
admin.site.register(Role, UUIDModelAdmin)
admin.site.register(RoleSpecification, UUIDModelAdmin)
admin.site.register(Shift, UUIDModelAdmin)
admin.site.register(Task, UUIDModelAdmin)
admin.site.register(TaskField, UUIDModelAdmin)
