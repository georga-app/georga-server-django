from datetime import datetime
import asyncio

import graphene
import graphql_jwt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.password_validation import validate_password
# from django.core.exceptions import ValidationError
from django.db.models import ManyToManyField, ManyToManyRel, ManyToOneRel
from django.forms import (
    ModelForm, ModelChoiceField, ModelMultipleChoiceField,
    IntegerField, CharField, ChoiceField
)
from django.forms.models import model_to_dict
from graphene import Schema, Field, ObjectType, Union, List, ID, String, NonNull
from graphene.relay import Node
from graphene.types.dynamic import Dynamic
from graphene_django import DjangoObjectType
from graphene_django.converter import convert_django_field
from graphene_django.fields import DjangoListField, DjangoConnectionField
from graphene_django.filter import DjangoFilterConnectionField
from graphene_django.forms import GlobalIDMultipleChoiceField, GlobalIDFormField
from graphene_django.forms.mutation import DjangoModelFormMutation
from graphql_jwt.decorators import login_required, staff_member_required
from graphql_relay import from_global_id

from .auth import jwt_decode
from .email import Email
from .models import (
    ACL,
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

channel_layer = get_channel_layer()


# Subclasses ==================================================================

@convert_django_field.register(ManyToManyField)
@convert_django_field.register(ManyToManyRel)
@convert_django_field.register(ManyToOneRel)
def convert_field_to_list_or_connection(field, registry=None):
    """
    Dynamic connection field conversion to UUIDDjangoFilterConnectionField.

    UUIDs:
    - Resolves connection to UUIDDjangoFilterConnectionField.
    """
    model = field.related_model

    def dynamic_type():
        _type = registry.get_type_for_model(model)
        if not _type:
            return
        description = (
            field.help_text
            if isinstance(field, ManyToManyField)
            else field.field.help_text
        )
        if _type._meta.connection:
            if _type._meta.filter_fields or _type._meta.filterset_class:
                # resolve connection to UUIDDjangoFilterConnectionField
                return UUIDDjangoFilterConnectionField(
                    _type, required=True, description=description)
            return DjangoConnectionField(_type, required=True, description=description)
        return DjangoListField(_type, required=True, description=description)

    return Dynamic(dynamic_type)


class UUIDModelForm(ModelForm):
    """
    ModelForm with model.uuid as identifier.

    UUIDs:
    - Sets to_field_name of foreign relation fields to uuid.

    Conveniece:
    - Sets fields required if listed in Meta.required_fields.

    Bugfixes:
    - Fixes bug of saving fields present in form but not in request data.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # set to_field_name of foreign relation fields to uuid
        for name, field in self.fields.items():
            if isinstance(field, (ModelChoiceField, ModelMultipleChoiceField)):
                field.to_field_name = 'uuid'

        # set fields required if listed in Meta.required_fields
        if hasattr(self.Meta, 'required_fields'):
            for name, field in self.fields.items():
                field.required = name in self.Meta.required_fields
            delattr(self.Meta, 'required_fields')

        # fix bug of saving fields present in form but not in request data
        # see https://github.com/graphql-python/graphene-django/issues/725
        if self.is_bound and self.instance.pk:
            modeldict = model_to_dict(self.instance)
            modeldict.update(self.data)
            self.data = modeldict


class UUIDDjangoObjectType(DjangoObjectType):
    """
    DjangoObjectType with model.uuid as identifier.

    UUIDs:
    - Changes queryset to fetch objects by uuid model field.
    - Changes resolve id to uuid model field.

    Conveniece:
    - Adds relay.Node interface if not specified in Meta.interfaces.
    - Sets permissions for query specified in Meta.permissions.
    """

    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(cls, *args, **kwargs):
        # add relay.Node interface if not specified in Meta.interfaces
        if not kwargs.get('interfaces'):
            kwargs['interfaces'] = (Node,)

        # set permissions for query specified in Meta.permissions
        for permission in kwargs.get('permissions', []):
            cls.get_queryset = permission(cls.get_queryset)

        super().__init_subclass_with_meta__(*args, **kwargs)

    @classmethod
    def get_node(cls, info, id):
        # change queryset to fetch objects by uuid model field
        queryset = cls.get_queryset(cls._meta.model.objects, info)
        try:
            return queryset.get(uuid=id)
        except cls._meta.model.DoesNotExist:
            return None

    def resolve_id(self, info):
        # change resolve id to uuid model field
        return self.uuid


class UUIDDjangoFilterConnectionField(DjangoFilterConnectionField):
    """
    DjangoFilterConnectionField with model.uuid as identifier.

    UUIDs:
    - Moves queryset id arg to uuid arg.
    - Inserts uuid to filter field predicate string for forgein models.

    Bugfixes:
    - Fixes a bug that converts model id fields to graphene.Float schema fields.
    """

    @property
    def filtering_args(self):
        # fix a bug that converts model id fields to graphene.Float schema fields
        # see https://github.com/graphql-python/graphene-django/issues/678
        if not self._filtering_args:
            self._filtering_args = super().filtering_args
            if 'id' in self._filtering_args:
                id_filter = self.filterset_class.base_filters['id']
                self._filtering_args['id'] = ID(required=id_filter.field.required)
        return self._filtering_args

    @classmethod
    def resolve_queryset(
            cls, connection, iterable, info, args, filtering_args, filterset_class
    ):
        # move queryset id arg to uuid arg
        if 'id' in args:
            _, args['uuid'] = from_global_id(args['id'])
            del (args['id'])

        # insert uuid to filter field predicate string for forgein models
        for name, _filter in filterset_class.base_filters.items():
            if isinstance(_filter.field, (GlobalIDMultipleChoiceField, GlobalIDFormField)):
                field_name = _filter.field_name
                if '__uuid' not in field_name:
                    if "__" in field_name:
                        field_name, lookup = field_name.split("__", 1)
                        parts = [field_name, "uuid", lookup]
                    else:
                        parts = [field_name, "uuid"]
                    _filter.field_name = "__".join(parts)

        return super().resolve_queryset(
            connection, iterable, info, args, filtering_args, filterset_class
        )


class UUIDDjangoModelFormMutation(DjangoModelFormMutation):
    """
    DjangoModelFormMutation with model.uuid as identifier.

    UUIDs:
    - Replaces model form id arg with model form uuid arg.
    - Replaces foreign model reference ids with uuids.

    Convenience:
    - Passes Meta.required_fields to form class.
    - Sets permissions for mutation specified in Meta.permissions.
    - Removes schema id field if Meta.only_fields is given and does not contain it.
    - Removes object return schema field if other schema fields are defined.
    - Sets id schema field required if not specified in Meta.required_fields.
    - Deletes kwargs for graphql variables defined but not passed
    """

    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(cls, *args, **kwargs):
        # pass Meta.required_fields to form class
        if all(k in kwargs for k in ['form_class', 'required_fields']):
            setattr(kwargs['form_class'].Meta, 'required_fields', kwargs['required_fields'])

        # set permissions for mutation specified in Meta.permissions
        for permission in kwargs.get('permissions', []):
            cls.mutate_and_get_payload = permission(cls.mutate_and_get_payload)

        # remove schema id field if Meta.only_fields is given and does not contain it
        if 'id' not in kwargs.get('only_fields', ['id']):
            kwargs['exclude_fields'] = kwargs.get('exclude_fields', []) + ['id']

        super().__init_subclass_with_meta__(*args, **kwargs)

        # remove object return schema field if other schema fields are defined
        if len(cls._meta.fields) > 3:
            del (cls._meta.fields[cls._meta.return_field_name])

        # set id schema field required if not specified in Meta.required_fields
        id_field = getattr(cls.Input, 'id', False)
        if id_field and 'id' in kwargs.get('required_fields', ['id']):
            id_field._type = NonNull(id_field._type)

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        # delete kwargs for graphql variables defined but not passed
        kwargs = {"data": {key: value for key, value in input.items() if value is not None}}

        # replace model form id arg with model form uuid arg
        global_id = input.pop("id", None)
        if global_id:
            _, uuid = from_global_id(global_id)
            instance = cls._meta.model._default_manager.get(uuid=uuid)
            kwargs["instance"] = instance

        # replace foreign model reference ids with uuids
        for name, field in vars(cls.Input).items():
            if name not in input or name.startswith("_"):
                continue
            if isinstance(field.type, ID):
                kwargs["data"][name] = from_global_id(input[name])[1]
            if isinstance(field.type, List) and field.type.of_type == ID and input[name]:
                kwargs["data"][name] = [from_global_id(id)[1] for id in input[name]]

        return kwargs


# Lookups =====================================================================

# see https://docs.djangoproject.com/en/4.0/ref/models/querysets/#field-lookups-1
LOOKUPS_ID = ['exact']
LOOKUPS_INT = [
    'exact', 'gt', 'gte', 'lt', 'lte',
    'regex', 'iregex', 'isnull',
]
LOOKUPS_STRING = [
    'exact', 'iexact',
    'contains', 'icontains',
    'startswith', 'istartswith',
    'endswith', 'iendswith',
    'regex', 'iregex',
    'in', 'isnull',
]
LOOKUPS_ENUM = ['exact', 'contains', 'in', 'isnull']
LOOKUPS_CONNECTION = ['exact']
LOOKUPS_DATETIME = [
    'exact', 'range', 'gt', 'gte', 'lt', 'lte',
    'date', 'date__gt', 'date__gte', 'date__lt', 'date__lte',
    'time', 'time__gt', 'time__gte', 'time__lt', 'time__lte',
    'iso_year', 'iso_year__gt', 'iso_year__gte', 'iso_year__lt', 'iso_year__lte',
    'year', 'year__gt', 'year__gte', 'year__lt', 'year__lte',
    'month', 'month__gt', 'month__gte', 'month__lt', 'month__lte',
    'iso_week_day', 'iso_week_day__gt', 'iso_week_day__gte', 'iso_week_day__lt', 'iso_week_day__lte',
    'quarter', 'quarter__gt', 'quarter__gte', 'quarter__lt', 'quarter__lte',
    'week_day', 'week_day__gt', 'week_day__gte', 'week_day__lt', 'week_day__lte',
    'day', 'day__gt', 'day__gte', 'day__lt', 'day__lte',
    'hour', 'hour__gt', 'hour__gte', 'hour__lt', 'hour__lte',
    'minute', 'minute__gt', 'minute__gte', 'minute__lt', 'minute__lte',
    'second', 'second__gt', 'second__gte', 'second__lt', 'second__lte',
    'isnull',
]

# Models ======================================================================

# ACL ----------------------------------------------------------------------

# fields
acl_ro_fields = [
    'uuid',
    'content_type',
    'object_id',
]
acl_wo_fields = [
]
acl_rw_fields = [
    'person',
    'acl_string',
]
acl_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
}


# types
class ACLType(UUIDDjangoObjectType):
    class Meta:
        model = ACL
        fields = acl_ro_fields + acl_rw_fields
        filter_fields = acl_filter_fields
        permissions = [login_required]


# forms

class ACLModelForm(UUIDModelForm):
    class Meta:
        model = ACL
        fields = acl_wo_fields + acl_rw_fields


# cud mutations
class CreateACLMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ACLModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateACLMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ACLModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteACLMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ACLModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        acl = form.instance
        acl.delete()
        return cls(acl=acl, errors=[])


# Device ----------------------------------------------------------------------

# fields
device_ro_fields = [
    'uuid',
    'push_token',
]
device_wo_fields = [
]
device_rw_fields = [
    'organization',
    'device_string',
    'os_version',
    'app_version',

]
device_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID
}


# types
class DeviceType(UUIDDjangoObjectType):
    class Meta:
        model = Device
        fields = device_ro_fields + device_rw_fields
        filter_fields = device_filter_fields
        permissions = [login_required]


# forms

class DeviceModelForm(UUIDModelForm):
    class Meta:
        model = Device
        fields = device_wo_fields + device_rw_fields


# cud mutations
class CreateDeviceMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = DeviceModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateDeviceMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = DeviceModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteDeviceMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = DeviceModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        device = form.instance
        device.delete()
        return cls(device=device, errors=[])


# Equipment -----------------------------------------------------------

# fields
equipment_ro_fields = [
    'uuid',
]
equipment_wo_fields = []
equipment_rw_fields = [
    'name',
    'organization',
]
equipment_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
}


# types
class EquipmentType(UUIDDjangoObjectType):
    class Meta:
        model = Equipment
        fields = equipment_ro_fields + equipment_rw_fields
        filter_fields = equipment_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# Location --------------------------------------------------------------------

# fields
location_ro_fields = [
    'uuid',
]
location_wo_fields = []
location_rw_fields = [
    'organization',
    'address',
    'location_category',
]
location_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'address': LOOKUPS_STRING,
}


# types
class LocationType(UUIDDjangoObjectType):
    class Meta:
        model = Location
        fields = location_ro_fields + location_rw_fields
        filter_fields = location_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# LocationCategory ----------------------------------------------------------------------

# fields
location_category_ro_fields = [
    'uuid',
]
location_category_wo_fields = [
]
location_category_rw_fields = [
    'name',
    'organization',
]
location_category_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
}


# types
class LocationCategoryType(UUIDDjangoObjectType):
    class Meta:
        model = LocationCategory
        fields = location_category_ro_fields + location_category_rw_fields
        filter_fields = location_category_filter_fields
        permissions = [login_required]


# forms

class LocationCategoryModelForm(UUIDModelForm):
    class Meta:
        model = LocationCategory
        fields = location_category_wo_fields + location_category_rw_fields


# cud mutations
class CreateLocationCategoryMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = LocationCategoryModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateLocationCategoryMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = LocationCategoryModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteLocationCategoryMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = LocationCategoryModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        location_category = form.instance
        location_category.delete()
        return cls(location_category=location_category, errors=[])


# Message ----------------------------------------------------------------------

# fields
message_ro_fields = [
    'uuid',
    'category',
    'priority',
    'state',
    'delivery_state',
]
message_wo_fields = [
]
message_rw_fields = [
    'title',
    'contents',

]
message_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'state': LOOKUPS_ENUM,
    'object_id': LOOKUPS_ID,
    'content_type': LOOKUPS_CONNECTION,
    'project__id': LOOKUPS_ID,
}


class MessageType(UUIDDjangoObjectType):
    scope = Field('georga.schemas.MessageScopeUnion', required=True)

    class Meta:
        model = Message
        fields = message_ro_fields + message_rw_fields
        filter_fields = message_filter_fields
        permissions = [login_required]


# forms
class MessageModelForm(UUIDModelForm):
    class Meta:
        model = Message
        fields = message_wo_fields + message_rw_fields


# mutations
class CreateMessageMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = MessageModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateMessageMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = MessageModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteMessageMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = MessageModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        message = form.instance
        message.delete()
        return cls(message=message, errors=[])


# Operation ----------------------------------------------------------------------

# fields
operation_ro_fields = [
    'uuid',
]
operation_wo_fields = [
]
operation_rw_fields = [
    'project',
    'name',
    'is_active',
]
operation_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
}


# types
class OperationType(UUIDDjangoObjectType):
    class Meta:
        model = Operation
        fields = operation_ro_fields + operation_rw_fields
        filter_fields = operation_filter_fields
        permissions = [login_required]


# forms

class OperationModelForm(UUIDModelForm):
    class Meta:
        model = Operation
        fields = operation_wo_fields + operation_rw_fields


# cud mutations
class CreateOperationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OperationModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateOperationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OperationModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteOperationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OperationModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        operation = form.instance
        operation.delete()
        return cls(operation=operation, errors=[])


# Organization ----------------------------------------------------------------------

# fields
organization_ro_fields = [
    'uuid',
]
organization_wo_fields = [
]
organization_rw_fields = [
    'name',
]
organization_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID
}


# types
class OrganizationType(UUIDDjangoObjectType):
    class Meta:
        model = Organization
        fields = organization_ro_fields + organization_rw_fields
        filter_fields = organization_filter_fields
        permissions = [login_required]


# forms

class OrganizationModelForm(UUIDModelForm):
    class Meta:
        model = Organization
        fields = organization_wo_fields + organization_rw_fields


# cud mutations
class CreateOrganizationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OrganizationModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateOrganizationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OrganizationModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteOrganizationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OrganizationModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        organization = form.instance
        organization.delete()
        return cls(organization=organization, errors=[])


# Participant ----------------------------------------------------------------------

# fields
participant_ro_fields = [
    'uuid',
]
participant_wo_fields = [
]
participant_rw_fields = [
    'person',
    'role',
]
participant_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
}


# types
class ParticipantType(UUIDDjangoObjectType):
    class Meta:
        model = Participant
        fields = participant_ro_fields + participant_rw_fields
        filter_fields = participant_filter_fields
        permissions = [login_required]


# forms

class ParticipantModelForm(UUIDModelForm):
    class Meta:
        model = Participant
        fields = participant_wo_fields + participant_rw_fields


# cud mutations
class CreateParticipantMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ParticipantModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateParticipantMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ParticipantModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteParticipantMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ParticipantModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        participant = form.instance
        participant.delete()
        return cls(participant=participant, errors=[])


# Project ----------------------------------------------------------------------

# Person ----------------------------------------------------------------------

# fields
person_ro_fields = [
    'uuid',
    'date_joined',
    'last_login',
]
person_wo_fields = [
    'password',
]
person_rw_fields = [
    'first_name',
    'last_name',
    'email',
    'title',
    'person_properties',
    'occupation',
    'street',
    'number',
    'postal_code',
    'city',
    'private_phone',
    'mobile_phone',
    'only_job_related_topics',
]
person_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'date_joined': LOOKUPS_DATETIME,
    'last_login': LOOKUPS_DATETIME,
    'first_name': LOOKUPS_STRING,
    'last_name': LOOKUPS_STRING,
    'email': LOOKUPS_STRING,
    'title': LOOKUPS_ENUM,
    'person_properties': LOOKUPS_CONNECTION,
    'occupation': LOOKUPS_STRING,
    'street': LOOKUPS_STRING,
    'number': LOOKUPS_STRING,
    'postal_code': LOOKUPS_STRING,
    'city': LOOKUPS_STRING,
    'private_phone': LOOKUPS_STRING,
    'mobile_phone': LOOKUPS_STRING,
    'only_job_related_topics': LOOKUPS_ENUM,
}


# types
class PersonType(UUIDDjangoObjectType):
    class Meta:
        model = Person
        fields = person_ro_fields + person_rw_fields
        filter_fields = person_filter_fields
        permissions = [login_required]


# forms
class PersonModelForm(UUIDModelForm):
    class Meta:
        model = Person
        fields = person_wo_fields + person_rw_fields

    def clean_password(self):
        password = self.cleaned_data['password']
        validate_password(password)
        return password

    def save(self, commit=True):
        person = super().save(commit=False)
        if 'email' in self.changed_data:
            person.username = self.cleaned_data["email"]
        if 'password' in self.changed_data:
            person.set_password(self.cleaned_data["password"])
        if commit:
            person.save()
            self.save_m2m()
        return person


class PersonTokenModelForm(PersonModelForm):
    token = CharField()
    exp = IntegerField()
    iat = IntegerField()
    sub = ChoiceField(choices=[
        ('activation', 'Activation'),
        ('password_reset', 'Password Reset')
    ])


# cud mutations
class CreatePersonMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdatePersonMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeletePersonMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        person = form.instance
        person.delete()
        return cls(person=person, errors=[])


# flow mutations
class RegisterPersonMutation(UUIDDjangoModelFormMutation):
    id = ID()

    class Meta:
        form_class = PersonModelForm
        exclude_fields = ['id']
        permissions = []

    @classmethod
    def perform_mutate(cls, form, info):
        person = form.save()
        Email.send_activation_email(person)
        return cls(id=person.gid, errors=[])


class RequestActivationMutation(UUIDDjangoModelFormMutation):
    id = ID()

    class Meta:
        form_class = PersonTokenModelForm
        only_fields = ['token']
        permissions = []

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        form_kwargs = super().get_form_kwargs(root, info, **input)
        payload = jwt_decode(form_kwargs["data"]["token"])
        uuid = payload.pop("uid")
        if uuid:
            form_kwargs["instance"] = cls._meta.model._default_manager.get(uuid=uuid)
            form_kwargs["data"].update(payload)
        return form_kwargs

    @classmethod
    def perform_mutate(cls, form, info):
        person = form.instance
        if form.cleaned_data.get('sub') == 'activation':
            person.is_active = True
            person.save()
        return cls(id=person.gid, errors=[])


class ActivatePersonMutation(UUIDDjangoModelFormMutation):
    email = String()

    class Meta:
        form_class = PersonTokenModelForm
        only_fields = ['token']
        permissions = []

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        form_kwargs = super().get_form_kwargs(root, info, **input)
        payload = jwt_decode(form_kwargs["data"]["token"])
        uuid = payload.pop("uid")
        if uuid:
            form_kwargs["instance"] = cls._meta.model._default_manager.get(uuid=uuid)
            form_kwargs["data"].update(payload)
        return form_kwargs

    @classmethod
    def perform_mutate(cls, form, info):
        person = form.instance
        if form.cleaned_data.get('sub') == 'activation':
            person.is_active = True
            person.save()
        return cls(email=person.email, errors=[])


class ObtainJSONWebToken(graphql_jwt.relay.JSONWebTokenMutation):
    id = ID()

    @classmethod
    def resolve(cls, root, info, **kwargs):
        return cls(id=info.context.user.gid)


class ChangePasswordMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonModelForm
        only_fields = ['id', 'password']
        permissions = [login_required]


class RequestPasswordMutation(UUIDDjangoModelFormMutation):
    id = ID()

    class Meta:
        form_class = PersonModelForm
        only_fields = ['email']
        required_fields = ['email']

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        form_kwargs = super().get_form_kwargs(root, info, **input)
        email = form_kwargs["data"]["email"]
        form_kwargs["instance"] = cls._meta.model._default_manager.get(email=email)
        return form_kwargs

    @classmethod
    def perform_mutate(cls, form, info):
        person = form.instance
        Email.send_password_reset_email(person)
        return cls(id=person.gid, errors=[])


class ResetPasswordMutation(UUIDDjangoModelFormMutation):
    id = ID()

    class Meta:
        form_class = PersonTokenModelForm
        only_fields = ['token', 'password']
        permissions = []

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        form_kwargs = super().get_form_kwargs(root, info, **input)
        payload = jwt_decode(form_kwargs["data"]["token"])
        uuid = payload.pop("uid")
        if uuid:
            form_kwargs["instance"] = cls._meta.model._default_manager.get(uuid=uuid)
            form_kwargs["data"].update(payload)
        return form_kwargs

    @classmethod
    def perform_mutate(cls, form, info):
        person = form.instance
        if form.cleaned_data.get('sub') == 'password_reset':
            person.save()
        return cls(id=person.gid, errors=[])


# PersonProperty -------------------------------------------------------

# fields
person_property_ro_fields = [
    'uuid',
    'person_set',
]
person_property_wo_fields = []
person_property_rw_fields = [
    'organization',
    'name',
    'group',
    'necessity',
]
person_property_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'group': LOOKUPS_ID,
    'group__name': LOOKUPS_STRING,
    'group__codename': LOOKUPS_STRING,
}


# types
class PersonPropertyType(UUIDDjangoObjectType):
    class Meta:
        model = PersonProperty
        fields = person_property_ro_fields + person_property_rw_fields
        filter_fields = person_property_filter_fields
        permissions = []


# forms
class PersonPropertyModelForm(UUIDModelForm):
    class Meta:
        model = PersonProperty
        fields = person_property_wo_fields + person_property_rw_fields


# cud mutations
class CreatePersonPropertyMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonPropertyModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdatePersonPropertyMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonPropertyModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeletePersonPropertyMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonPropertyModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        person_property = form.instance
        person_property.delete()
        return cls(person_property=person_property, errors=[])


# flow mutations


# PersonPropertyGroup ----------------------------------------------------------------------

# fields
person_property_group_ro_fields = [
    'uuid',
]
person_property_group_wo_fields = [
]
person_property_group_rw_fields = [
    'name',
    'organization',
    'codename',
    'selection_type',
]
person_property_group_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
    'codename': LOOKUPS_STRING,
}


# types
class PersonPropertyGroupType(UUIDDjangoObjectType):
    class Meta:
        model = PersonPropertyGroup
        fields = person_property_group_ro_fields + person_property_group_rw_fields
        filter_fields = person_property_group_filter_fields
        permissions = []


# forms

class PersonPropertyGroupModelForm(UUIDModelForm):
    class Meta:
        model = PersonPropertyGroup
        fields = person_property_group_wo_fields + person_property_group_rw_fields


# cud mutations
class CreatePersonPropertyGroupMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonPropertyGroupModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdatePersonPropertyGroupMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonPropertyGroupModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeletePersonPropertyGroupMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonPropertyGroupModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        person_property_group = form.instance
        person_property_group.delete()
        return cls(person_property_group=person_property_group, errors=[])


# PersonToObject ----------------------------------------------------------------------

# fields
person_to_object_ro_fields = [
    'uuid',
    'content_type',
    'object_id',
]
person_to_object_wo_fields = [
]
person_to_object_rw_fields = [
    'person',
    'unnoticed',
    'bookmarked',
]
person_to_object_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
}


# types
class PersonToObjectType(UUIDDjangoObjectType):
    class Meta:
        model = PersonToObject
        fields = person_to_object_ro_fields + person_to_object_rw_fields
        filter_fields = person_to_object_filter_fields
        permissions = [login_required]


# forms

class PersonToObjectModelForm(UUIDModelForm):
    class Meta:
        model = PersonToObject
        fields = person_to_object_wo_fields + person_to_object_rw_fields


# cud mutations
class CreatePersonToObjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonToObjectModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdatePersonToObjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonToObjectModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeletePersonToObjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonToObjectModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        person_to_object = form.instance
        person_to_object.delete()
        return cls(person_to_object=person_to_object, errors=[])


# Project ----------------------------------------------------------------------

# fields
project_ro_fields = [
    'uuid',
    'messages',
]
project_wo_fields = [
]
project_rw_fields = [
    'name',
    'organization',
]
project_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'messages__state': LOOKUPS_ENUM,
}


# types
class ProjectType(UUIDDjangoObjectType):
    class Meta:
        model = Project
        fields = project_ro_fields + project_rw_fields
        filter_fields = project_filter_fields
        permissions = [login_required]


# forms

class ProjectModelForm(UUIDModelForm):
    class Meta:
        model = Project
        fields = project_wo_fields + project_rw_fields


# cud mutations
class CreateProjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ProjectModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateProjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ProjectModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteProjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ProjectModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        project = form.instance
        project.delete()
        return cls(project=project, errors=[])


# Resource ----------------------------------------------------------------------

# fields
resource_ro_fields = [
    'uuid',
]
resource_wo_fields = [
]
resource_rw_fields = [
    'description',
    'personal_hint',
    'equipment_needed',
    'shift',
    'amount',
]
resource_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID
}


# types
class ResourceType(UUIDDjangoObjectType):
    class Meta:
        model = Resource
        fields = resource_ro_fields + resource_rw_fields
        filter_fields = resource_filter_fields
        permissions = [login_required]


# forms

class ResourceModelForm(UUIDModelForm):
    class Meta:
        model = Resource
        fields = resource_wo_fields + resource_rw_fields


# cud mutations
class CreateResourceMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ResourceModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateResourceMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ResourceModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteResourceMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ResourceModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        resource = form.instance
        resource.delete()
        return cls(resource=resource, errors=[])


# Role ----------------------------------------------------------------------

# fields
role_ro_fields = [
    'uuid',
]
role_wo_fields = [
]
role_rw_fields = [
    'title',
    'description',
    'is_template',
    'shift',
]
role_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
}


# types
class RoleType(UUIDDjangoObjectType):
    class Meta:
        model = Role
        fields = role_ro_fields + role_rw_fields
        filter_fields = role_filter_fields
        permissions = [login_required]


# forms

class RoleModelForm(UUIDModelForm):
    class Meta:
        model = Role
        fields = role_wo_fields + role_rw_fields


# cud mutations
class CreateRoleMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = RoleModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateRoleMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = RoleModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteRoleMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = RoleModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        role = form.instance
        role.delete()
        return cls(role=role, errors=[])


# RoleSpecification ----------------------------------------------------------------------

# fields
role_specification_ro_fields = [
    'uuid',
]
role_specification_wo_fields = [
]
role_specification_rw_fields = [
    'role',
    'person_properties',
]
role_specification_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
}


# types
class RoleSpecificationType(UUIDDjangoObjectType):
    class Meta:
        model = RoleSpecification
        fields = role_specification_ro_fields + role_specification_rw_fields
        filter_fields = role_specification_filter_fields
        permissions = [login_required]


# forms

class RoleSpecificationModelForm(UUIDModelForm):
    class Meta:
        model = RoleSpecification
        fields = role_specification_wo_fields + role_specification_rw_fields


# cud mutations
class CreateRoleSpecificationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = RoleSpecificationModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateRoleSpecificationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = RoleSpecificationModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteRoleSpecificationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = RoleSpecificationModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        role = form.instance
        role.delete()
        return cls(role_specification=role, errors=[])


# Shift ----------------------------------------------------------------------

# fields
shift_ro_fields = [
    'uuid',
]
shift_wo_fields = [
]
shift_rw_fields = [
    'task',
    'start_time',
    'end_time',
    'enrollment_deadline',
    'state',
    'locations',
]
shift_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
}


# types
class ShiftType(UUIDDjangoObjectType):
    class Meta:
        model = Shift
        fields = shift_ro_fields + shift_rw_fields
        filter_fields = shift_filter_fields
        permissions = [login_required]


# forms

class ShiftModelForm(UUIDModelForm):
    class Meta:
        model = Shift
        fields = shift_wo_fields + shift_rw_fields


# cud mutations
class CreateShiftMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ShiftModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateShiftMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ShiftModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteShiftMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ShiftModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        shift = form.instance
        shift.delete()
        return cls(shift=shift, errors=[])


# Task ----------------------------------------------------------------------

# fields
task_ro_fields = [
    'uuid',
]
task_wo_fields = [
]
task_rw_fields = [
    'operation',
    'task_field',
    'roles',
    'resources_required',
    'resources_desirable',
    'persons_registered',
    'persons_participated',
    'locations',
    'title',
    'description',
    'postal_address_name',
    'postal_address_street',
    'postal_address_zip_code',
    'postal_address_city',
    'postal_address_country',
    'start_time',
    'end_time',
]
task_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID
}


# types
class TaskType(UUIDDjangoObjectType):
    class Meta:
        model = Task
        fields = task_ro_fields + task_rw_fields
        filter_fields = task_filter_fields
        permissions = [login_required]


# forms

class TaskModelForm(UUIDModelForm):
    class Meta:
        model = Task
        fields = task_wo_fields + task_rw_fields


# cud mutations
class CreateTaskMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateTaskMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteTaskMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        task = form.instance
        task.delete()
        return cls(task=task, errors=[])


# TaskField ----------------------------------------------------------------------

# fields
task_field_ro_fields = [
    'uuid',
]
task_field_wo_fields = [
]
task_field_rw_fields = [
    'name',
    'description',
    'organization',
]
task_field_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID
}


# types
class TaskFieldType(UUIDDjangoObjectType):
    class Meta:
        model = TaskField
        fields = task_field_ro_fields + task_field_rw_fields
        filter_fields = task_field_filter_fields
        permissions = [login_required]


# forms

class TaskFieldModelForm(UUIDModelForm):
    class Meta:
        model = TaskField
        fields = task_field_wo_fields + task_field_rw_fields


# cud mutations
class CreateTaskFieldMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskFieldModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateTaskFieldMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskFieldModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteTaskFieldMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskFieldModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        task_field = form.instance
        task_field.delete()
        return cls(task_field=task_field, errors=[])


# Models with GenericForeignKeys ==============================================



# types
class MessageScopeUnion(Union):
    class Meta:
        types = [OrganizationType, ProjectType, OperationType, TaskType, ShiftType]


    class Meta:


# Subscriptions ===============================================================

class TestSubscription(graphene.ObjectType):
    message = graphene.String(required=True)
    time = graphene.DateTime(required=True)


class TestSubscriptionEventMutation(graphene.Mutation):
    class Arguments:
        message = String(required=True)

    response = String()

    @classmethod
    def mutate(cls, root, info, message):
        print(f"New message broadcasted: {message}")
        # TestSubscription.broadcast(group="TestSubscriptionEvents", payload=message)
        async_to_sync(channel_layer.group_send)("new_message", {"data": message})
        return TestSubscriptionEventMutation(response="OK")


# Schema ======================================================================

class Query(ObjectType):
    node = Node.Field()
    all_task_fields = UUIDDjangoFilterConnectionField(
        TaskFieldType)
    all_equipment = UUIDDjangoFilterConnectionField(
        EquipmentType)
    all_locations = UUIDDjangoFilterConnectionField(
        LocationType)
    all_messages = UUIDDjangoFilterConnectionField(
        MessageType)
    all_persons = UUIDDjangoFilterConnectionField(
        PersonType)
    all_person_properties = UUIDDjangoFilterConnectionField(
        PersonPropertyType)
    all_person_property_groups = UUIDDjangoFilterConnectionField(
        PersonPropertyGroupType)
    all_devices = UUIDDjangoFilterConnectionField(DeviceType)
    all_resources = UUIDDjangoFilterConnectionField(ResourceType)
    all_organizations = UUIDDjangoFilterConnectionField(OrganizationType)
    all_tasks = UUIDDjangoFilterConnectionField(TaskType)
    all_projects = UUIDDjangoFilterConnectionField(ProjectType)
    all_roles = UUIDDjangoFilterConnectionField(RoleType)


class Mutation(ObjectType):
    # Authorization
    token_auth = ObtainJSONWebToken.Field()
    verify_token = graphql_jwt.relay.Verify.Field()
    refresh_token = graphql_jwt.relay.Refresh.Field()

    # Persons
    create_person = CreatePersonMutation.Field()
    update_person = UpdatePersonMutation.Field()
    delete_person = DeletePersonMutation.Field()
    # Persons Flows
    register_person = RegisterPersonMutation.Field()
    request_activation = RequestActivationMutation.Field()
    activate_person = ActivatePersonMutation.Field()
    change_password = ChangePasswordMutation.Field()
    request_password = RequestPasswordMutation.Field()
    reset_password = ResetPasswordMutation.Field()

    # PersonProperty
    create_person_property = CreatePersonPropertyMutation.Field()
    update_person_property = UpdatePersonPropertyMutation.Field()
    delete_person_property = DeletePersonPropertyMutation.Field()
    # PersonPropertyGroup
    create_person_property_group = CreatePersonPropertyGroupMutation.Field()
    update_person_property_group = UpdatePersonPropertyGroupMutation.Field()
    delete_person_property_group = DeletePersonPropertyGroupMutation.Field()

    # Device
    create_device = CreateDeviceMutation.Field()
    update_device = UpdateDeviceMutation.Field()
    delete_device = DeleteDeviceMutation.Field()
    # Resources
    create_resource = CreateResourceMutation.Field()
    update_resource = UpdateResourceMutation.Field()
    delete_resource = DeleteResourceMutation.Field()
    # Organizations
    create_organization = CreateOrganizationMutation.Field()
    update_organization = UpdateOrganizationMutation.Field()
    delete_organization = DeleteOrganizationMutation.Field()
    # Tasks
    create_task = CreateTaskMutation.Field()
    update_task = UpdateTaskMutation.Field()
    delete_task = DeleteTaskMutation.Field()
    # TaskFields
    create_task_field = CreateTaskFieldMutation.Field()
    update_task_field = UpdateTaskFieldMutation.Field()
    delete_task_field = DeleteTaskFieldMutation.Field()
    # Projects
    create_project = CreateProjectMutation.Field()
    update_project = UpdateProjectMutation.Field()
    delete_project = DeleteProjectMutation.Field()
    # Roles
    create_role = CreateRoleMutation.Field()
    update_role = UpdateRoleMutation.Field()
    delete_role = DeleteRoleMutation.Field()

    # TestSubscription
    test_subscription_event = TestSubscriptionEventMutation.Field()


class Subscription(graphene.ObjectType):
    count_seconds = graphene.Int(up_to=graphene.Int())
    test_subscription = graphene.Field(TestSubscription)

    async def resolve_count_seconds(self, info, up_to=5):
        print(up_to)
        i = 1
        while i <= up_to:
            yield str(i)
            await asyncio.sleep(1)
            i += 1

    async def resolve_test_subscription(self, info):
        channel_name = await channel_layer.new_channel()
        await channel_layer.group_add("new_message", channel_name)
        try:
            while True:
                message = await channel_layer.receive(channel_name)
                yield TestSubscription(message=message["data"], time=datetime.now())
        finally:
            await channel_layer.group_discard("new_message", channel_name)


schema = Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)
