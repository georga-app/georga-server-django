# For copyright and license terms, see COPYRIGHT.md (top level of repository)
# Repository: https://github.com/georga-app/georga-server-django

import logging
from datetime import datetime

import graphql_jwt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels_graphql_ws import Subscription
from django.contrib.auth.password_validation import validate_password
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.exceptions import ValidationError
from django.db.models import ManyToManyField, ManyToManyRel, ManyToOneRel
from django.db.models.fields.related import ForeignKey
from django.forms import (
    ModelForm, ModelChoiceField, ModelMultipleChoiceField,
    IntegerField, CharField, ChoiceField, BooleanField
)
from django.forms.models import ModelFormMetaclass, model_to_dict
from django_filters import FilterSet, UUIDFilter
from graphene import (
    Schema, Mutation, ObjectType, Field, Union, List,
    ID, UUID, String, Int, NonNull
)
from graphene.relay import Node
from graphene.types.dynamic import Dynamic
from graphene_django import DjangoObjectType
from graphene_django.converter import (
    convert_django_field,
    convert_choices_to_named_enum_with_descriptions,
)
from graphene_django.fields import DjangoListField, DjangoConnectionField
from graphene_django.filter import (
    DjangoFilterConnectionField,
    GlobalIDFilter,
    GlobalIDMultipleChoiceFilter,
)
from graphene_django.forms import GlobalIDMultipleChoiceField, GlobalIDFormField
from graphene_django.forms.mutation import DjangoModelFormMutation
from graphql_jwt.exceptions import JSONWebTokenError, PermissionDenied
from graphql_jwt.decorators import login_required, staff_member_required
from graphql_relay import from_global_id

from .auth import jwt_decode, object_permits_user
from .email import Email
from .models import (
    ACE,
    Device,
    Equipment,
    Location,
    LocationCategory,
    Message,
    MessageFilter,
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


# Logging =====================================================================

def not_jwt_error(record):
    err_type, err_obj, traceback = record.exc_info
    return not isinstance(err_obj, JSONWebTokenError)


# see https://github.com/graphql-python/graphene-django/issues/413
logging.getLogger('graphql.execution.executor').addFilter(not_jwt_error)
# see https://github.com/graphql-python/graphene-django/issues/735
logging.getLogger("graphql.execution.utils").setLevel(logging.CRITICAL)


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


class GFKModelFormMetaclass(ModelFormMetaclass):
    """
    Metaclass for ModelForms adding FormFields for GenericForeignKey Fields.

    GFKs:
    - Adds GlobalIDFormField for GenericForeignKey fields.
    """
    def __new__(mcs, name, bases, attrs, *args, **kwargs):
        # add GlobalIDFormField for GenericForeignKey fields
        gfk_fields = []
        if "Meta" in attrs:
            model = getattr(attrs["Meta"], "model", None)
            fields = getattr(attrs["Meta"], "fields", [])
            if model:
                for field in fields:
                    formfield = getattr(model, field, False)
                    if isinstance(formfield, GenericForeignKey):
                        attrs[field] = GlobalIDFormField()
                        gfk_fields.append(field)
        cls = super().__new__(mcs, name, bases, attrs, *args, **kwargs)
        cls._meta.gfk_fields = gfk_fields
        return cls


class UUIDModelForm(ModelForm, metaclass=GFKModelFormMetaclass):
    """
    ModelForm with model.uuid as identifier.

    UUIDs:
    - Sets to_field_name of foreign relation fields to uuid if provided as input.

    GFKs:
    - Assigns model instance to GenericForeignKey fields, if GlobalID was provided.

    Conveniece:
    - Sets fields required if listed in Meta.required_fields.
    - Sets fields unrequired if not listed in Meta.only_fields.

    Bugfixes:
    - Fixes bug of saving fields present in form but not in request data.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # set to_field_name of foreign relation fields to uuid if provided as input
        for name, field in self.fields.items():
            if name in self.data and isinstance(
                    field, (ModelChoiceField, ModelMultipleChoiceField)):
                field.to_field_name = 'uuid'

        # set fields required if listed in Meta.required_fields
        if hasattr(self.Meta, 'required_fields'):
            for name, field in self.fields.items():
                field.required = name in self.Meta.required_fields
            delattr(self.Meta, 'required_fields')

        # set fields unrequired if not listed in Meta.only_fields
        if hasattr(self.Meta, 'only_fields'):
            for name, field in self.fields.items():
                if name not in self.Meta.only_fields:
                    field.required = False
            delattr(self.Meta, 'only_fields')

        # fix bug of saving fields present in form but not in request data
        # see https://github.com/graphql-python/graphene-django/issues/725
        if self.is_bound and self.instance.pk:
            modeldict = model_to_dict(self.instance)
            modeldict.update(self.data)
            self.data = modeldict

    def _post_clean(self, *args, **kwargs):
        # assigns model instance to GenericForeignKey fields, if GlobalID was provided
        for name in getattr(self._meta, 'gfk_fields', []):
            if name not in self.data:
                continue
            _type, _id = from_global_id(self.data[name])
            foreign_model_name = _type.removesuffix("Type").lower()
            foreign_model_class = ContentType.objects.get(
                app_label='georga', model=foreign_model_name
            ).model_class()
            foreign_model_instance = foreign_model_class.objects.get(uuid=_id)
            setattr(self.instance, name, foreign_model_instance)
        return super()._post_clean(*args, **kwargs)


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
        cls.permission = kwargs.get('permissions', [])
        for permission in cls.permission:
            cls.get_node = permission(cls.get_node)
            _func = cls.get_queryset.__func__
            cls.get_queryset = permission(cls.get_queryset)
            # check on __func__ introduced in graphene-django 3.1.5
            cls.get_queryset.__func__ = _func

        super().__init_subclass_with_meta__(*args, **kwargs)

    @classmethod
    def get_node(cls, info, uuid):
        # change queryset to fetch objects by uuid model field
        queryset = cls.get_queryset(cls._meta.model.objects, info)
        try:
            return queryset.get(uuid=uuid)
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
    # _lookups = [
    #     'exact', 'iexact', 'contains', 'icontains', 'in', 'gt', 'gte', 'lt', 'lte',
    #     'startswith', 'istartswith', 'endswith', 'iendswith', 'range', 'date',
    #     'year', 'iso_year', 'month', 'day', 'week', 'week_day', 'iso_week_day', 'quarter',
    #     'time', 'hour', 'minute', 'second', 'isnull', 'regex', 'iregex',
    # ]
    # @staticmethod
    # def add_uuid_to_lookup(field, lookup):
    #     if field:
    #         return f"{lookup}__uuid"
    #     return lookup

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
            filterset_class.base_filters['uuid'] = UUIDFilter('uuid')
            filtering_args['uuid'] = UUID('uuid')
            _, args['uuid'] = from_global_id(args['id'])
            del (args['id'])

        # insert uuid to filter field predicate string for forgein models
        for name, _filter in filterset_class.base_filters.items():
            if isinstance(_filter.field, (GlobalIDMultipleChoiceField, GlobalIDFormField)):
                field_name = _filter.field_name
                lookups = field_name.split("__")
                if '__uuid' not in field_name:
                    if len(lookups) == 1:
                        _filter.field_name = f"{field_name}__uuid"
                    else:
                        parts = []
                        current_field = filterset_class.Meta.model._meta.get_field(lookups[0])
                        for i in range(0, len(lookups)):
                            part = lookups[i]
                            next_part = i != len(lookups) - 1 and lookups[i+1]
                            if not isinstance(current_field, ForeignKey):
                                parts.append(part)
                                continue
                            if not next_part:
                                parts.append(f"{part}__uuid")
                                continue
                            parts.append(part)
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
    - Passes Meta.required_fields and Meta.only_fields to form class.
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
        # pass Meta.required_fields and Meta.only_fields to form class
        if 'form_class' in kwargs:
            if 'required_fields' in kwargs:
                kwargs['form_class'].Meta.required_fields = kwargs['required_fields']
                cls.required_fields = kwargs['required_fields']
            if 'only_fields' in kwargs:
                kwargs['form_class'].Meta.only_fields = kwargs['only_fields']
                cls.only_fields = kwargs['only_fields']

        # set permissions for mutation specified in Meta.permissions
        cls.permission = kwargs.get('permissions', [])
        for permission in cls.permission:
            cls.get_form_kwargs = permission(cls.get_form_kwargs)
            cls.perform_mutate = permission(cls.perform_mutate)

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
    def get_form(cls, root, info, **input):
        # pass Meta.required_fields and Meta.only_fields to form class
        if hasattr(cls, 'required_fields'):
            cls._meta.form_class.Meta.required_fields = cls.required_fields
        if hasattr(cls, 'only_fields'):
            cls._meta.form_class.Meta.only_fields = cls.only_fields
        form_kwargs = cls.get_form_kwargs(root, info, **input)
        form = cls._meta.form_class(**form_kwargs)
        form._meta.user = info.context.user
        return form

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        # delete kwargs for graphql variables defined but not passed
        kwargs = {"data": {key: value for key, value in input.items() if value is not None}}
        if 'id' in kwargs["data"]:
            del kwargs["data"]["id"]

        # replace model form id arg with model form uuid arg
        global_id = input.pop("id", None)
        if global_id:
            _, uuid = from_global_id(global_id)
            instance = cls._meta.model._default_manager.get(uuid=uuid)
            kwargs["instance"] = instance

        # replace foreign model reference ids with uuids
        for name, field in vars(cls.Input).items():
            # skip fields, that were not provided
            if name not in input:
                continue
            # skip fields starting with an underscore
            elif name.startswith("_"):
                continue
            # skip id field
            elif name == "id":
                continue
            # skip generic foreign key fields (model class needs to be passed)
            elif name in getattr(cls._meta.form_class._meta, 'gfk_fields', []):
                continue
            _type = field.type
            # ID instance
            if isinstance(_type, ID):
                kwargs["data"][name] = from_global_id(input[name])[1]
            # ID class
            elif isinstance(_type, type) and issubclass(_type, ID):
                kwargs["data"][name] = from_global_id(input[name])[1]
            # NonNull instance wrapping ID
            elif isinstance(_type, NonNull) and _type.of_type == ID:
                kwargs["data"][name] = from_global_id(input[name])[1]
            # List containing IDs
            elif isinstance(_type, List) and _type.of_type == ID and input[name]:
                kwargs["data"][name] = [from_global_id(id)[1] for id in input[name]]

        return kwargs


class GFKFilterSet(FilterSet):
    """
    FilterSet class for GenericForeignKeys using GlobalRelayID.

    Uses the type part of the GlobalRelayID to infer the GenericRelation
    related_query_name for the lookup. Uses the filter attribute name to infer
    the gfk field name to access the _cts attribute on the model to restrict
    valid lookup names.

    This works as long as the following conventions are met:
    1) The GenericRelations.related_query_name must be equal to the model name
    2) The attribute on the filter class has to start with the gfk field name,
       lookup postfixes must be separated by a double underscore
    3) The model needs to provide a list of valid foreign model names in
       Model.<gfk_field>_cts ("Contenttypes")
    """

    class Meta:
        abstract = True

    def getRelatedQueryNameAndUUID(self, name, value):
        _type, _id = from_global_id(value)
        related_query_name = _type.removesuffix("Type").lower()
        # check validity of provided name for foreign model
        gfk_field, = name.split('__')[:1]
        gfk_field_cts = f"{gfk_field}_cts"
        if not hasattr(self.queryset.model, gfk_field_cts):
            raise ValidationError(
                f"{self.queryset.model._meta.label}.{gfk_field_cts} is not "
                "defined. Please add it and assign a list with valid models.")
        valid_models = getattr(self.queryset.model, gfk_field_cts)
        if related_query_name not in valid_models:
            raise ValidationError(
                f"{related_query_name} is not a valid foreign model of "
                f"{self.queryset.model._meta.label}, as it is not listed in "
                f"{self.queryset.model._meta.label}.{gfk_field_cts}.")
        return related_query_name, _id

    def filterExact(self, queryset, name, value):
        """Exact Filter for GenericForeignKeys using GlobalRelayID."""
        if value is None:
            return queryset
        related_query_name, uuid = self.getRelatedQueryNameAndUUID(name, value)
        lookup = related_query_name + "__uuid"
        return queryset.filter(**{lookup: uuid})

    def filterIn(self, queryset, name, values):
        """In Filter for GlobalForeignKeys using GlobalRelayID."""
        if values is []:
            return queryset
        # prepare dict with lookup as key and a list of IDs as value
        lookups = {}
        for value in values:
            related_query_name, uuid = self.getRelatedQueryNameAndUUID(name, value)
            lookup = related_query_name + "__uuid__in"
            if lookup not in lookups:
                lookups[lookup] = []
            lookups[lookup].append(uuid)
        # return a union of the querysets for all different lookups
        result = self._meta.model.objects.none()
        for lookup, uuids in lookups.items():
            result = result.union(queryset.filter(**{lookup: uuids}))
        return result


# Lookups =====================================================================

# see https://docs.djangoproject.com/en/4.1/ref/models/querysets/#field-lookups-1
# LOOKUPS_ID = ['exact']
# LOOKUPS_INT = [
#     'exact', 'gt', 'gte', 'lt', 'lte',
#     'regex', 'iregex', 'isnull',
# ]
# LOOKUPS_STRING = [
#     'exact', 'iexact',
#     'contains', 'icontains',
#     'startswith', 'istartswith',
#     'endswith', 'iendswith',
#     'regex', 'iregex',
#     'in', 'isnull',
# ]
# LOOKUPS_ENUM = ['exact', 'contains', 'in', 'isnull']
# LOOKUPS_CONNECTION = ['exact']
# LOOKUPS_DATETIME = [
#     'exact', 'range', 'gt', 'gte', 'lt', 'lte',
#     'date', 'date__gt', 'date__gte', 'date__lt', 'date__lte',
#     'time', 'time__gt', 'time__gte', 'time__lt', 'time__lte',
#     'iso_year', 'iso_year__gt', 'iso_year__gte', 'iso_year__lt', 'iso_year__lte',
#     'year', 'year__gt', 'year__gte', 'year__lt', 'year__lte',
#     'month', 'month__gt', 'month__gte', 'month__lt', 'month__lte',
#     'iso_week_day', 'iso_week_day__gt', 'iso_week_day__gte',
#     'iso_week_day__lt', 'iso_week_day__lte',
#     'quarter', 'quarter__gt', 'quarter__gte', 'quarter__lt', 'quarter__lte',
#     'week_day', 'week_day__gt', 'week_day__gte', 'week_day__lt', 'week_day__lte',
#     'day', 'day__gt', 'day__gte', 'day__lt', 'day__lte',
#     'hour', 'hour__gt', 'hour__gte', 'hour__lt', 'hour__lte',
#     'minute', 'minute__gt', 'minute__gte', 'minute__lt', 'minute__lte',
#     'second', 'second__gt', 'second__gte', 'second__lt', 'second__lte',
#     'isnull',
# ]
LOOKUPS_ID = ['exact']
LOOKUPS_INT = ['exact']
LOOKUPS_STRING = ['exact', 'icontains']
LOOKUPS_ENUM = ['exact', 'in']
LOOKUPS_CONNECTION = ['exact']
LOOKUPS_DATETIME = ['exact', 'gt', 'lte']


# Non-Model ===================================================================

class ChannelFiltersType(ObjectType):
    for channel in MessageFilter.CHANNELS:
        vars()[channel] = String()


# Models ======================================================================

# ACE -------------------------------------------------------------------------

# fields
ace_ro_fields = [
    'created_at',
    'modified_at',
]
ace_wo_fields = [
]
ace_rw_fields = [
    'person',
    'instance',
    'permission',
]
ace_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
}


# types
class ACEType(UUIDDjangoObjectType):
    instance = Field('georga.schemas.ACEInstanceUnion', required=True)

    class Meta:
        model = ACE
        fields = ace_ro_fields + ace_rw_fields
        filter_fields = ace_filter_fields
        permissions = [login_required, object_permits_user('read')]


# filters
class ACEFilterSet(GFKFilterSet):
    instance = GlobalIDFilter(method='filterExact')
    instance__in = GlobalIDMultipleChoiceFilter(method='filterIn')

    class Meta:
        model = ACE
        fields = ace_filter_fields


# forms
class ACEModelForm(UUIDModelForm):
    class Meta:
        model = ACE
        fields = ace_wo_fields + ace_rw_fields


# mutations
class CreateACEMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ACEModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]


class DeleteACEMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ACEModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        ace = form.instance
        ace.delete()
        return cls(aCE=ace, errors=[])


# Device ----------------------------------------------------------------------

# fields
device_ro_fields = [
    'created_at',
    'modified_at',
]
device_wo_fields = [
]
device_rw_fields = [
    'name',
    'os_type',
    'os_version',
    'app_type',
    'app_version',
    'app_store',
    'push_token_type',
    'push_token',
]
device_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
}


# types
class DeviceType(UUIDDjangoObjectType):
    class Meta:
        model = Device
        fields = device_ro_fields + device_rw_fields
        filter_fields = device_filter_fields
        permissions = [login_required, object_permits_user('read')]


# forms
class DeviceModelForm(UUIDModelForm):
    class Meta:
        model = Device
        fields = device_wo_fields + device_rw_fields


# mutations
class CreateDeviceMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = DeviceModelForm
        exclude_fields = ['id']
        permissions = [login_required, object_permits_user('create')]

    @classmethod
    def get_form(cls, root, info, **input):
        form = super().get_form(root, info, **input)
        form.instance.person = info.context.user
        return form


class UpdateDeviceMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = DeviceModelForm
        required_fields = ['id']
        permissions = [login_required, object_permits_user('update')]


class DeleteDeviceMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = DeviceModelForm
        only_fields = ['id']
        permissions = [login_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        device = form.instance
        device.delete()
        return cls(device=device, errors=[])


# Equipment -------------------------------------------------------------------

# fields
equipment_ro_fields = [
    'created_at',
    'modified_at',
]
equipment_wo_fields = []
equipment_rw_fields = [
    'name',
    'organization',
]
equipment_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
    'name': LOOKUPS_STRING,
}


# types
class EquipmentType(UUIDDjangoObjectType):
    class Meta:
        model = Equipment
        fields = equipment_ro_fields + equipment_rw_fields
        filter_fields = equipment_filter_fields
        permissions = [login_required, object_permits_user('read')]


# forms
class EquipmentModelForm(UUIDModelForm):
    class Meta:
        model = Equipment
        fields = equipment_wo_fields + equipment_rw_fields


# mutations
class CreateEquipmentMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = EquipmentModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]


class UpdateEquipmentMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = EquipmentModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeleteEquipmentMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = EquipmentModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        equipment = form.instance
        equipment.delete()
        return cls(equipment=equipment, errors=[])


# Location --------------------------------------------------------------------

# fields
location_ro_fields = [
    'created_at',
    'modified_at',
]
location_wo_fields = []
location_rw_fields = [
    'category',
    'postal_address_name',
    'postal_address_street',
    'postal_address_zip_code',
    'postal_address_city',
    'postal_address_country',
    'task',
    'shift',
]
location_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
    'postal_address_name': LOOKUPS_STRING,
}


# types
class LocationType(UUIDDjangoObjectType):
    class Meta:
        model = Location
        fields = location_ro_fields + location_rw_fields
        filter_fields = location_filter_fields
        permissions = [login_required, object_permits_user('read')]


# forms
class LocationModelForm(UUIDModelForm):
    class Meta:
        model = Location
        fields = location_wo_fields + location_rw_fields


# mutations
class CreateLocationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = LocationModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]


class UpdateLocationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = LocationModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeleteLocationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = LocationModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        location = form.instance
        location.delete()
        return cls(location=location, errors=[])


# LocationCategory ------------------------------------------------------------

# fields
location_category_ro_fields = [
    'created_at',
    'modified_at',
]
location_category_wo_fields = [
]
location_category_rw_fields = [
    'name',
    'organization',
]
location_category_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
}


# types
class LocationCategoryType(UUIDDjangoObjectType):
    class Meta:
        model = LocationCategory
        fields = location_category_ro_fields + location_category_rw_fields
        filter_fields = location_category_filter_fields
        permissions = [login_required, object_permits_user('read')]


# forms
class LocationCategoryModelForm(UUIDModelForm):
    class Meta:
        model = LocationCategory
        fields = location_category_wo_fields + location_category_rw_fields


# mutations
class CreateLocationCategoryMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = LocationCategoryModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]


class UpdateLocationCategoryMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = LocationCategoryModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeleteLocationCategoryMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = LocationCategoryModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        location_category = form.instance
        location_category.delete()
        return cls(location_category=location_category, errors=[])


# Message ---------------------------------------------------------------------

# fields
message_ro_fields = [
    'created_at',
    'modified_at',
    'category',
    'priority',
    'state',
    'email_delivery',
    'push_delivery',
    'sms_delivery',
]
message_wo_fields = [
]
message_rw_fields = [
    'title',
    'contents',
    'priority',
    'scope',
]
message_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
    'state': LOOKUPS_ENUM,
}


# types
class MessageType(UUIDDjangoObjectType):
    scope = Field('georga.schemas.MessageScopeUnion', required=True)
    delivery = Field(
        convert_choices_to_named_enum_with_descriptions(
            'MessageDeliveryState', Message.DELIVERY_STATES),
        required=True)

    class Meta:
        model = Message
        fields = message_ro_fields + message_rw_fields
        filter_fields = message_filter_fields
        permissions = [login_required, object_permits_user('read')]


# filters
class MessageFilterSet(GFKFilterSet):
    scope = GlobalIDFilter(method='filterExact')
    scope__in = GlobalIDMultipleChoiceFilter(method='filterIn')

    class Meta:
        model = Message
        fields = message_filter_fields


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
        permissions = [staff_member_required, object_permits_user('create')]

    @classmethod
    def perform_mutate(cls, form, info):
        message = form.save()
        async_to_sync(channel_layer.group_send)("message_created", {"pk": message.id})
        return cls(message=message, errors=[])


class UpdateMessageMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = MessageModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeleteMessageMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = MessageModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        message = form.instance
        message.delete()
        return cls(message=message, errors=[])


# MessageFilter ---------------------------------------------------------------

# fields
message_filter_ro_fields = [
    'created_at',
    'modified_at',
]
message_filter_wo_fields = [
]
message_filter_rw_fields = [
    'scope',
    'person',
    'app',
    'email',
    'push',
    'sms',
]
message_filter_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
}


# types
class MessageFilterType(UUIDDjangoObjectType):
    scope = Field('georga.schemas.MessageFilterScopeUnion', required=True)

    class Meta:
        model = MessageFilter
        fields = message_filter_ro_fields + message_filter_rw_fields
        filter_fields = message_filter_filter_fields
        permissions = [login_required, object_permits_user('read')]


# filters
class MessageFilterFilterSet(GFKFilterSet):
    scope = GlobalIDFilter(method='filterExact')
    scope__in = GlobalIDMultipleChoiceFilter(method='filterIn')

    class Meta:
        model = MessageFilter
        fields = message_filter_filter_fields


# forms
class MessageFilterModelForm(UUIDModelForm):
    class Meta:
        model = MessageFilter
        fields = message_filter_wo_fields + message_filter_rw_fields


# mutations
class CreateMessageFilterMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = MessageFilterModelForm
        exclude_fields = ['id']
        permissions = [login_required, object_permits_user('create')]


class UpdateMessageFilterMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = MessageFilterModelForm
        required_fields = ['id']
        permissions = [login_required, object_permits_user('update')]


class DeleteMessageFilterMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = MessageFilterModelForm
        only_fields = ['id']
        permissions = [login_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        message_filter = form.instance
        message_filter.delete()
        return cls(messageFilter=message_filter, errors=[])


# Operation -------------------------------------------------------------------

# fields
operation_ro_fields = [
    'created_at',
    'modified_at',
    'state',
]
operation_wo_fields = [
]
operation_rw_fields = [
    'project',
    'name',
    'description',
    'is_active',
]
operation_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
    'project': LOOKUPS_ID,
    'project__organization': LOOKUPS_ID,
    'state': LOOKUPS_ENUM,
}


# types
class OperationType(UUIDDjangoObjectType):
    ace = UUIDDjangoFilterConnectionField('georga.schemas.ACEType')
    messages = UUIDDjangoFilterConnectionField('georga.schemas.MessageType')
    message_filters = UUIDDjangoFilterConnectionField('georga.schemas.MessageFilterType')
    person_attributes = UUIDDjangoFilterConnectionField('georga.schemas.PersonToObjectType')
    channel_filters = Field(ChannelFiltersType)

    class Meta:
        model = Operation
        fields = operation_ro_fields + operation_rw_fields
        filter_fields = operation_filter_fields
        permissions = [login_required, object_permits_user('read')]

    def resolve_channel_filters(parent, info):
        return parent.channel_filters(info.context.user)


# forms
class OperationModelForm(UUIDModelForm):
    class Meta:
        model = Operation
        fields = operation_wo_fields + operation_rw_fields


class CreateOperationModelForm(OperationModelForm):
    publish = BooleanField(required=False)


# mutations
class CreateOperationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = CreateOperationModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]

    @classmethod
    def perform_mutate(cls, form, info):
        operation = form.instance
        if not operation.id:
            operation.save()
        if form.data.get('publish'):
            operation.publish()
            operation.save()
        return cls(operation=operation, errors=[])


class UpdateOperationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OperationModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeleteOperationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OperationModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        operation = form.instance
        operation.delete()
        operation.save()
        return cls(operation=operation, errors=[])


class PublishOperationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OperationModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('publish')]

    @classmethod
    def perform_mutate(cls, form, info):
        operation = form.instance
        operation.publish()
        operation.save()
        return cls(operation=operation, errors=[])


class ArchiveOperationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OperationModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('archive')]

    @classmethod
    def perform_mutate(cls, form, info):
        operation = form.instance
        operation.archive()
        operation.save()
        return cls(operation=operation, errors=[])


# Organization ----------------------------------------------------------------

# fields
organization_ro_fields = [
    'created_at',
    'modified_at',
    'state',
]
organization_wo_fields = [
]
organization_rw_fields = [
    'name',
    'icon',
    'description',
]
organization_filter_fields = {
    'id': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
    'state': LOOKUPS_ENUM,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
}


# types
class OrganizationType(UUIDDjangoObjectType):
    ace = UUIDDjangoFilterConnectionField('georga.schemas.ACEType')
    messages = UUIDDjangoFilterConnectionField('georga.schemas.MessageType')
    message_filters = UUIDDjangoFilterConnectionField('georga.schemas.MessageFilterType')
    person_attributes = UUIDDjangoFilterConnectionField('georga.schemas.PersonToObjectType')
    channel_filters = Field(ChannelFiltersType)

    class Meta:
        model = Organization
        fields = organization_ro_fields + organization_rw_fields
        filter_fields = organization_filter_fields
        permissions = [object_permits_user('read')]

    def resolve_channel_filters(parent, info):
        return parent.channel_filters(info.context.user)


# forms
class OrganizationModelForm(UUIDModelForm):
    class Meta:
        model = Organization
        fields = organization_wo_fields + organization_rw_fields


# mutations
class CreateOrganizationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OrganizationModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]


class UpdateOrganizationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OrganizationModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeleteOrganizationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OrganizationModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        organization = form.instance
        organization.delete()
        organization.save()
        return cls(organization=organization, errors=[])


class PublishOrganizationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OrganizationModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('publish')]

    @classmethod
    def perform_mutate(cls, form, info):
        organization = form.instance
        organization.publish()
        organization.save()
        return cls(organization=organization, errors=[])


class ArchiveOrganizationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = OrganizationModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('archive')]

    @classmethod
    def perform_mutate(cls, form, info):
        organization = form.instance
        organization.archive()
        organization.save()
        return cls(organization=organization, errors=[])


# Participant -----------------------------------------------------------------

# fields
participant_ro_fields = [
    'created_at',
    'modified_at',
    'acceptance',
    'admin_acceptance',
    'admin_acceptance_user',
]
participant_wo_fields = [
]
participant_rw_fields = [
    'person',
    'shift',
    'role',
]
participant_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
    'role': LOOKUPS_ID,
    'shift': LOOKUPS_ID,
    'shift__task': LOOKUPS_ID,
    'shift__task__operation': LOOKUPS_ID,
    'shift__task__operation__project': LOOKUPS_ID,
    'shift__task__operation__project__organization': LOOKUPS_ID,
}


# types
class ParticipantType(UUIDDjangoObjectType):
    class Meta:
        model = Participant
        fields = participant_ro_fields + participant_rw_fields
        filter_fields = participant_filter_fields
        permissions = [login_required, object_permits_user('read')]

    @object_permits_user('admin_read')
    def resolve_admin_acceptance_user(self, info):
        return self.admin_acceptance_user


# forms
class ParticipantModelForm(UUIDModelForm):
    class Meta:
        model = Participant
        fields = participant_wo_fields + participant_rw_fields

    # def save(self, commit=True):
    #     participant = super().save(commit=False)
    #     user = self._meta.user

    #     if 'admin_acceptance' in self.changed_data:
    #         non_default_fields = ['ACCEPTED', 'DECLINED']
    #         if participant.role.needs_admin_acceptance:
    #             non_default_fields.append('NONE')
    #         else:
    #             non_default_fields.append('PENDING')
    #         needs_permission = participant.admin_acceptance in non_default_fields
    #         if needs_permission and not participant.permits(user, ('admin_create', 'admin_update')):
    #             raise PermissionDenied
    #         participant.admin_acceptance_user = user

    #     if commit:
    #         participant.save()
    #         self.save_m2m()
    #     return participant


# mutations
class CreateParticipantMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ParticipantModelForm
        exclude_fields = ['id']
        permissions = [login_required, object_permits_user('create')]


class UpdateParticipantMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ParticipantModelForm
        required_fields = ['id']
        permissions = [login_required, object_permits_user('update')]


class DeleteParticipantMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ParticipantModelForm
        only_fields = ['id']
        permissions = [login_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        participant = form.instance
        participant.delete()
        return cls(participant=participant, errors=[])


class AcceptParticipantMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ParticipantModelForm
        only_fields = ['id']
        permissions = [login_required, object_permits_user('accept')]

    @classmethod
    def perform_mutate(cls, form, info):
        participant = form.instance
        participant.accept()
        if not participant.role.needs_admin_acceptance:
            participant.admin_accept()
        participant.save()
        return cls(participant=participant, errors=[])


class DeclineParticipantMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ParticipantModelForm
        only_fields = ['id']
        permissions = [login_required, object_permits_user('decline')]

    @classmethod
    def perform_mutate(cls, form, info):
        participant = form.instance
        participant.decline()
        if not participant.role.needs_admin_acceptance:
            participant.admin_accept()
        participant.save()
        return cls(participant=participant, errors=[])


class AdminAcceptParticipantMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ParticipantModelForm
        only_fields = ['id']
        permissions = [login_required, object_permits_user('admin_accept')]

    @classmethod
    def perform_mutate(cls, form, info):
        user = info.context.user
        participant = form.instance
        participant.admin_accept()
        participant.admin_acceptance_user = user
        participant.save()
        return cls(participant=participant, errors=[])


class AdminDeclineParticipantMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ParticipantModelForm
        only_fields = ['id']
        permissions = [login_required, object_permits_user('admin_decline')]

    @classmethod
    def perform_mutate(cls, form, info):
        user = info.context.user
        participant = form.instance
        participant.admin_decline()
        participant.admin_acceptance_user = user
        participant.save()
        return cls(participant=participant, errors=[])


# Person ----------------------------------------------------------------------

# fields
person_ro_fields = [
    'created_at',
    'modified_at',
    'date_joined',
    'last_login',
    'ace_set',
]
person_wo_fields = [
    'password',
]
person_rw_fields = [
    'first_name',
    'last_name',
    'email',
    'title',
    'properties',
    'occupation',
    'street',
    'number',
    'postal_code',
    'city',
    'private_phone',
    'mobile_phone',
    'only_job_related_topics',
    'organizations_subscribed',
]
person_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
    'date_joined': LOOKUPS_DATETIME,
    'last_login': LOOKUPS_DATETIME,
    'first_name': LOOKUPS_STRING,
    'last_name': LOOKUPS_STRING,
    'email': LOOKUPS_STRING,
    'title': LOOKUPS_ENUM,
    'properties': LOOKUPS_CONNECTION,
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
    default_message_filter = UUIDDjangoFilterConnectionField('georga.schemas.MessageFilterType')
    admin_level = Field(
        convert_choices_to_named_enum_with_descriptions(
            'AdminLevel', Person.ADMIN_LEVELS),
        required=True)

    class Meta:
        model = Person
        fields = person_ro_fields + person_rw_fields
        filter_fields = person_filter_fields
        permissions = [login_required, object_permits_user('read')]


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


# mutations
class CreatePersonMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]


class UpdatePersonMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeletePersonMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        person = form.instance
        person.delete()
        return cls(person=person, errors=[])


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


class RequestPersonActivationMutation(UUIDDjangoModelFormMutation):
    id = ID()

    class Meta:
        form_class = PersonTokenModelForm
        only_fields = ['email']
        required_fields = ['email']
        permissions = []

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        form_kwargs = super().get_form_kwargs(root, info, **input)
        email = form_kwargs["data"]["email"]
        form_kwargs["instance"] = cls._meta.model._default_manager.get(email=email)
        return form_kwargs

    @classmethod
    def perform_mutate(cls, form, info):
        person = form.instance
        Email.send_activation_email(person)
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


class LoginPersonMutation(graphql_jwt.relay.JSONWebTokenMutation):
    id = ID()
    adminLevel = PersonType.admin_level.type

    @classmethod
    def resolve(cls, root, info, **kwargs):
        user = info.context.user
        return cls(id=user.gid, adminLevel=user.admin_level)


class RequestPersonPasswordResetMutation(UUIDDjangoModelFormMutation):
    id = ID()

    class Meta:
        form_class = PersonModelForm
        only_fields = ['email']
        required_fields = ['email']
        permissions = []

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


class ResetPersonPasswordMutation(UUIDDjangoModelFormMutation):
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


class UpdatePersonProfileMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonModelForm
        exclude_fields = ['id', 'password']
        required_fields = []
        permissions = [login_required, object_permits_user("update")]

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        form_kwargs = super().get_form_kwargs(root, info, **input)
        pk = info.context.user.pk
        if pk:
            form_kwargs["instance"] = cls._meta.model._default_manager.get(pk=pk)
        return form_kwargs


class ChangePersonPasswordMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonModelForm
        only_fields = ['id', 'password']
        permissions = [login_required, object_permits_user("update")]


# PersonProperty --------------------------------------------------------------

# fields
person_property_ro_fields = [
    'created_at',
    'modified_at',
    'person_set',
]
person_property_wo_fields = []
person_property_rw_fields = [
    'name',
    'group',
]
person_property_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
    'group': LOOKUPS_ID,
    'group__name': LOOKUPS_STRING,
    'group__organization__name': LOOKUPS_STRING,
    'group__organization': LOOKUPS_ID,
}


# types
class PersonPropertyType(UUIDDjangoObjectType):
    class Meta:
        model = PersonProperty
        fields = person_property_ro_fields + person_property_rw_fields
        filter_fields = person_property_filter_fields
        permissions = [login_required, object_permits_user('read')]


# forms
class PersonPropertyModelForm(UUIDModelForm):
    class Meta:
        model = PersonProperty
        fields = person_property_wo_fields + person_property_rw_fields


# mutations
class CreatePersonPropertyMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonPropertyModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]


class UpdatePersonPropertyMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonPropertyModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeletePersonPropertyMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonPropertyModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        person_property = form.instance
        person_property.delete()
        return cls(person_property=person_property, errors=[])


# PersonPropertyGroup ---------------------------------------------------------

# fields
person_property_group_ro_fields = [
    'created_at',
    'modified_at',
    'personproperty_set',
]
person_property_group_wo_fields = [
]
person_property_group_rw_fields = [
    'name',
    'organization',
    'selection_type',
    'necessity',
]
person_property_group_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
    'name': LOOKUPS_STRING,
    'necessity': LOOKUPS_ENUM,
    'organization': LOOKUPS_CONNECTION,
    'organization__name': LOOKUPS_STRING,
}


# types
class PersonPropertyGroupType(UUIDDjangoObjectType):
    class Meta:
        model = PersonPropertyGroup
        fields = person_property_group_ro_fields + person_property_group_rw_fields
        filter_fields = person_property_group_filter_fields
        permissions = [login_required, object_permits_user('read')]


# forms
class PersonPropertyGroupModelForm(UUIDModelForm):
    class Meta:
        model = PersonPropertyGroup
        fields = person_property_group_wo_fields + person_property_group_rw_fields


# mutations
class CreatePersonPropertyGroupMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonPropertyGroupModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]


class UpdatePersonPropertyGroupMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonPropertyGroupModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeletePersonPropertyGroupMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonPropertyGroupModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        person_property_group = form.instance
        person_property_group.delete()
        return cls(person_property_group=person_property_group, errors=[])


# PersonToObject --------------------------------------------------------------

# fields
person_to_object_ro_fields = [
    'created_at',
    'modified_at',
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
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
}


# types
class PersonToObjectType(UUIDDjangoObjectType):
    relation_object = Field('georga.schemas.PersonToObjectRelationObjectUnion', required=True)

    class Meta:
        model = PersonToObject
        fields = person_to_object_ro_fields + person_to_object_rw_fields
        filter_fields = person_to_object_filter_fields
        permissions = [login_required, object_permits_user('read')]


# filters
class PersonToObjectFilterSet(GFKFilterSet):
    relation_object = GlobalIDFilter(method='filterExact')
    relation_object__in = GlobalIDMultipleChoiceFilter(method='filterIn')

    class Meta:
        model = PersonToObject
        fields = person_to_object_filter_fields


# forms
class PersonToObjectModelForm(UUIDModelForm):
    class Meta:
        model = PersonToObject
        fields = person_to_object_wo_fields + person_to_object_rw_fields


# mutations
class CreatePersonToObjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonToObjectModelForm
        exclude_fields = ['id']
        permissions = [login_required, object_permits_user('create')]


class UpdatePersonToObjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonToObjectModelForm
        required_fields = ['id']
        permissions = [login_required, object_permits_user('update')]


class DeletePersonToObjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = PersonToObjectModelForm
        only_fields = ['id']
        permissions = [login_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        person_to_object = form.instance
        person_to_object.delete()
        return cls(person_to_object=person_to_object, errors=[])


# Project ---------------------------------------------------------------------

# fields
project_ro_fields = [
    'created_at',
    'modified_at',
    'channel_filters',
    'state',
]
project_wo_fields = [
]
project_rw_fields = [
    'name',
    'description',
    'organization',
]
project_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
    'organization': LOOKUPS_ID,
    'state': LOOKUPS_ENUM,
}


# types
class ProjectType(UUIDDjangoObjectType):
    ace = UUIDDjangoFilterConnectionField('georga.schemas.ACEType')
    messages = UUIDDjangoFilterConnectionField('georga.schemas.MessageType')
    message_filters = UUIDDjangoFilterConnectionField('georga.schemas.MessageFilterType')
    person_attributes = UUIDDjangoFilterConnectionField('georga.schemas.PersonToObjectType')
    channel_filters = Field(ChannelFiltersType)

    class Meta:
        model = Project
        fields = project_ro_fields + project_rw_fields
        filter_fields = project_filter_fields
        permissions = [login_required, object_permits_user('read')]

    def resolve_channel_filters(parent, info):
        return parent.channel_filters(info.context.user)


# forms
class ProjectModelForm(UUIDModelForm):
    class Meta:
        model = Project
        fields = project_wo_fields + project_rw_fields


class CreateProjectModelForm(ProjectModelForm):
    publish = BooleanField(required=False)


# mutations
class CreateProjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = CreateProjectModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]

    @classmethod
    def perform_mutate(cls, form, info):
        project = form.instance
        if not project.id:
            project.save()
        if form.data.get('publish'):
            project.publish()
            project.save()
        return cls(project=project, errors=[])


class UpdateProjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ProjectModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeleteProjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ProjectModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        project = form.instance
        project.delete()
        project.save()
        return cls(project=project, errors=[])


class PublishProjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ProjectModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('publish')]

    @classmethod
    def perform_mutate(cls, form, info):
        project = form.instance
        project.publish()
        project.save()
        return cls(project=project, errors=[])


class ArchiveProjectMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ProjectModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('archive')]

    @classmethod
    def perform_mutate(cls, form, info):
        project = form.instance
        project.archive()
        project.save()
        return cls(project=project, errors=[])


# Resource --------------------------------------------------------------------

# fields
resource_ro_fields = [
    'created_at',
    'modified_at',
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
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
}


# types
class ResourceType(UUIDDjangoObjectType):
    class Meta:
        model = Resource
        fields = resource_ro_fields + resource_rw_fields
        filter_fields = resource_filter_fields
        permissions = [login_required, object_permits_user('read')]


# forms
class ResourceModelForm(UUIDModelForm):
    class Meta:
        model = Resource
        fields = resource_wo_fields + resource_rw_fields


# mutations
class CreateResourceMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ResourceModelForm
        exclude_fields = ['id']
        permissions = [login_required, object_permits_user('create')]


class UpdateResourceMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ResourceModelForm
        required_fields = ['id']
        permissions = [login_required, object_permits_user('update')]


class DeleteResourceMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ResourceModelForm
        only_fields = ['id']
        permissions = [login_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        resource = form.instance
        resource.delete()
        return cls(resource=resource, errors=[])


# Role ------------------------------------------------------------------------

# fields
role_ro_fields = [
    'created_at',
    'modified_at',
    'participant_set',
    'rolespecification_set',
]
role_wo_fields = [
]
role_rw_fields = [
    'name',
    'description',
    'is_active',
    'is_template',
    'needs_admin_acceptance',
    'quantity',
    'shift',
    'task',
]
role_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
}


# types
class RoleType(UUIDDjangoObjectType):
    person_attributes = UUIDDjangoFilterConnectionField('georga.schemas.PersonToObjectType')
    participants_accepted = Int()
    participants_declined = Int()
    participants_pending = Int()
    mandatory = List('georga.schemas.PersonPropertyType')
    recommended = List('georga.schemas.PersonPropertyType')
    unrecommended = List('georga.schemas.PersonPropertyType')
    impossible = List('georga.schemas.PersonPropertyType')

    class Meta:
        model = Role
        fields = role_ro_fields + role_rw_fields
        filter_fields = role_filter_fields
        permissions = [login_required, object_permits_user('read')]

    def resolve_mandatory(self, info):
        specification = self.rolespecification_set.filter(necessity="MANDATORY")
        if not specification:
            return []
        return specification[0].person_properties.all()

    def resolve_recommended(self, info):
        specification = self.rolespecification_set.filter(necessity="RECOMMENDED")
        if not specification:
            return []
        return specification[0].person_properties.all()

    def resolve_unrecommended(self, info):
        specification = self.rolespecification_set.filter(necessity="UNRECOMMENDED")
        if not specification:
            return []
        return specification[0].person_properties.all()

    def resolve_impossible(self, info):
        specification = self.rolespecification_set.filter(necessity="IMPOSSIBLE")
        if not specification:
            return []
        return specification[0].person_properties.all()


# forms
class RoleModelForm(UUIDModelForm):
    mandatory = ModelMultipleChoiceField(queryset=PersonProperty.objects.all(), required=False)
    recommended = ModelMultipleChoiceField(queryset=PersonProperty.objects.all(), required=False)
    unrecommended = ModelMultipleChoiceField(queryset=PersonProperty.objects.all(), required=False)
    impossible = ModelMultipleChoiceField(queryset=PersonProperty.objects.all(), required=False)

    class Meta:
        model = Role
        fields = role_wo_fields + role_rw_fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        role = kwargs.get('instance', False)
        if role:
            qs = PersonProperty.objects.filter(group__organization=self.instance.organization)
            for field in ["mandatory", "recommended", "unrecommended", "impossible"]:
                self.fields[field].queryset = qs

    def save(self, commit=True):
        role = super().save(commit=False)
        # create
        print(role.id)
        if not role.id:
            role.save()
        # specifications
        for necessity in ["mandatory", "recommended", "unrecommended", "impossible"]:
            if necessity not in self.data:
                continue
            properties = PersonProperty.objects.filter(uuid__in=self.data[necessity])
            specification = role.rolespecification_set.filter(necessity=necessity.upper()).first()
            if not specification:
                specification = RoleSpecification(role=role, necessity=necessity.upper())
                specification.save()
            specification.person_properties.set(properties)
        # save
        if commit:
            role.save()
            self.save_m2m()
        return role


class CreateRoleModelForm(RoleModelForm):
    def __init__(self, *args, **kwargs):
        data = kwargs.get('data', False)
        if data:
            # enforce either shift or task relation
            has_shift = 'shift' in data
            has_task = 'task' in data
            if (not has_shift or has_task) and (has_shift or not has_task):
                raise ValidationError("Roles need to be assigned to either a task or a shift.")
            # auto set is_template according to shift or task relation
            data['is_template'] = True
            if 'shift' in data:
                data['is_template'] = False
        super().__init__(*args, **kwargs)


# mutations
class CreateRoleMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = CreateRoleModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]


class UpdateRoleMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = RoleModelForm
        required_fields = ['id']
        exclude_fields = ['task', 'shift']
        permissions = [staff_member_required, object_permits_user('update')]


class DeleteRoleMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = RoleModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        role = form.instance
        role.delete()
        return cls(role=role, errors=[])


class AcceptRoleMutation(UUIDDjangoModelFormMutation):
    participant = Field(ParticipantType)

    class Meta:
        form_class = RoleModelForm
        only_fields = ['id']
        required_fields = ['id']
        permissions = [login_required]

    @classmethod
    def perform_mutate(cls, form, info):
        person = info.context.user
        role = form.instance
        participant = Participant.objects.filter(person=person, role=role).first()
        # create
        if not participant:
            participant = Participant(
                person=person,
                role=role,
            )
            if not participant.permits(person, 'create'):
                raise PermissionDenied
        # update
        else:
            if not participant.permits(person, 'update'):
                raise PermissionDenied
        # accept
        if participant.acceptance != "ACCEPTED":
            participant.accept()
        participant.save()
        return cls(participant=participant, errors=[])


class DeclineRoleMutation(UUIDDjangoModelFormMutation):
    participant = Field(ParticipantType)

    class Meta:
        form_class = RoleModelForm
        only_fields = ['id']
        required_fields = ['id']
        permissions = [login_required]

    @classmethod
    def perform_mutate(cls, form, info):
        person = info.context.user
        role = form.instance
        participant = Participant.objects.filter(person=person, role=role).first()
        # create
        if not participant:
            participant = Participant(
                person=person,
                role=role,
            )
            if not participant.permits(person, 'create'):
                raise PermissionDenied
        # update
        else:
            if not participant.permits(person, 'update'):
                raise PermissionDenied
        # accept
        if participant.acceptance != "DECLINED":
            participant.decline()
        participant.save()
        return cls(participant=participant, errors=[])


# RoleSpecification -----------------------------------------------------------

# fields
role_specification_ro_fields = [
    'created_at',
    'modified_at',
]
role_specification_wo_fields = [
]
role_specification_rw_fields = [
    'role',
    'person_properties',
    'necessity',
]
role_specification_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
}


# types
class RoleSpecificationType(UUIDDjangoObjectType):
    class Meta:
        model = RoleSpecification
        fields = role_specification_ro_fields + role_specification_rw_fields
        filter_fields = role_specification_filter_fields
        permissions = [login_required, object_permits_user('read')]


# forms
class RoleSpecificationModelForm(UUIDModelForm):
    class Meta:
        model = RoleSpecification
        fields = role_specification_wo_fields + role_specification_rw_fields


# mutations
class CreateRoleSpecificationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = RoleSpecificationModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]


class UpdateRoleSpecificationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = RoleSpecificationModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeleteRoleSpecificationMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = RoleSpecificationModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        role = form.instance
        role.delete()
        return cls(role_specification=role, errors=[])


# Shift -----------------------------------------------------------------------

# fields
shift_ro_fields = [
    'created_at',
    'modified_at',
    'state',
    'role_set',
]
shift_wo_fields = [
]
shift_rw_fields = [
    'task',
    'start_time',
    'end_time',
    'enrollment_deadline',
]
shift_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
    'task': LOOKUPS_ID,
    'task__operation': LOOKUPS_ID,
    'task__operation__project': LOOKUPS_ID,
    'task__operation__project__organization': LOOKUPS_ID,
    'state': LOOKUPS_ENUM,
}


# types
class ShiftType(UUIDDjangoObjectType):
    messages = UUIDDjangoFilterConnectionField('georga.schemas.MessageType')
    message_filters = UUIDDjangoFilterConnectionField('georga.schemas.MessageFilterType')
    person_attributes = UUIDDjangoFilterConnectionField('georga.schemas.PersonToObjectType')
    channel_filters = Field(ChannelFiltersType)

    class Meta:
        model = Shift
        fields = shift_ro_fields + shift_rw_fields
        filter_fields = shift_filter_fields
        permissions = [login_required, object_permits_user('read')]

    def resolve_channel_filters(parent, info):
        return parent.channel_filters(info.context.user)


# forms
class ShiftModelForm(UUIDModelForm):
    class Meta:
        model = Shift
        fields = shift_wo_fields + shift_rw_fields


class CreateShiftModelForm(ShiftModelForm):
    publish = BooleanField(required=False)


# mutations
class CreateShiftMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = CreateShiftModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]

    @classmethod
    def perform_mutate(cls, form, info):
        shift = form.instance
        if not shift.id:
            shift.save()
        if form.data.get('publish'):
            shift.publish()
            shift.save()
        return cls(shift=shift, errors=[])


class UpdateShiftMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ShiftModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeleteShiftMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ShiftModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        shift = form.instance
        shift.delete()
        return cls(shift=shift, errors=[])


class PublishShiftMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ShiftModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('publish')]

    @classmethod
    def perform_mutate(cls, form, info):
        shift = form.instance
        shift.publish()
        shift.save()
        return cls(shift=shift, errors=[])


class ArchiveShiftMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = ShiftModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('archive')]

    @classmethod
    def perform_mutate(cls, form, info):
        shift = form.instance
        shift.archive()
        shift.save()
        return cls(shift=shift, errors=[])


# Task ------------------------------------------------------------------------

# fields
task_ro_fields = [
    'created_at',
    'modified_at',
    'state',
    'role_set',
]
task_wo_fields = [
]
task_rw_fields = [
    'field',
    'resources_required',
    'resources_desirable',
    'name',
    'description',
    'operation',
    'start_time',
    'end_time',
]
task_filter_fields = {
    'id': LOOKUPS_ID,
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
    'operation': LOOKUPS_ID,
    'operation__project': LOOKUPS_ID,
    'operation__project__organization': LOOKUPS_ID,
    'state': LOOKUPS_ENUM,
}


# types
class TaskType(UUIDDjangoObjectType):
    messages = UUIDDjangoFilterConnectionField('georga.schemas.MessageType')
    message_filters = UUIDDjangoFilterConnectionField('georga.schemas.MessageFilterType')
    person_attributes = UUIDDjangoFilterConnectionField('georga.schemas.PersonToObjectType')
    channel_filters = Field(ChannelFiltersType)

    class Meta:
        model = Task
        fields = task_ro_fields + task_rw_fields
        filter_fields = task_filter_fields
        permissions = [login_required, object_permits_user('read')]

    def resolve_channel_filters(parent, info):
        return parent.channel_filters(info.context.user)


# forms
class TaskModelForm(UUIDModelForm):
    class Meta:
        model = Task
        fields = task_wo_fields + task_rw_fields


class CreateTaskModelForm(TaskModelForm):
    publish = BooleanField(required=False)


# mutations
class CreateTaskMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = CreateTaskModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]

    @classmethod
    def perform_mutate(cls, form, info):
        task = form.instance
        if not task.id:
            task.save()
        if form.data.get('publish'):
            task.publish()
            task.save()
        return cls(task=task, errors=[])


class UpdateTaskMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeleteTaskMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        task = form.instance
        task.delete()
        task.save()
        return cls(task=task, errors=[])


class PublishTaskMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('publish')]

    @classmethod
    def perform_mutate(cls, form, info):
        task = form.instance
        task.publish()
        task.save()
        return cls(task=task, errors=[])


class ArchiveTaskMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('archive')]

    @classmethod
    def perform_mutate(cls, form, info):
        task = form.instance
        task.archive()
        task.save()
        return cls(task=task, errors=[])


# TaskField -------------------------------------------------------------------

# fields
task_field_ro_fields = [
    'created_at',
    'modified_at',
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
    'created_at': LOOKUPS_DATETIME,
    'modified_at': LOOKUPS_DATETIME,
    'organization': LOOKUPS_ID,
}


# types
class TaskFieldType(UUIDDjangoObjectType):
    class Meta:
        model = TaskField
        fields = task_field_ro_fields + task_field_rw_fields
        filter_fields = task_field_filter_fields
        permissions = [login_required, object_permits_user('read')]


# forms
class TaskFieldModelForm(UUIDModelForm):
    class Meta:
        model = TaskField
        fields = task_field_wo_fields + task_field_rw_fields


# mutations
class CreateTaskFieldMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskFieldModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required, object_permits_user('create')]


class UpdateTaskFieldMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskFieldModelForm
        required_fields = ['id']
        permissions = [staff_member_required, object_permits_user('update')]


class DeleteTaskFieldMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = TaskFieldModelForm
        only_fields = ['id']
        permissions = [staff_member_required, object_permits_user('delete')]

    @classmethod
    def perform_mutate(cls, form, info):
        task_field = form.instance
        task_field.delete()
        return cls(task_field=task_field, errors=[])


# Unions ======================================================================

# ACEinstance.
class ACEInstanceUnion(Union):
    class Meta:
        types = [OrganizationType, ProjectType, OperationType]


# Message.scope
class MessageScopeUnion(Union):
    class Meta:
        types = [OrganizationType, ProjectType, OperationType, TaskType, ShiftType]


# MessageFilter.scope
class MessageFilterScopeUnion(Union):
    class Meta:
        types = [PersonType, OrganizationType, ProjectType, OperationType, TaskType, ShiftType]


# PersonToObject
class PersonToObjectRelationObjectUnion(Union):
    class Meta:
        types = [OrganizationType, ProjectType, OperationType, TaskType, ShiftType,
                 RoleType, MessageType]


# Subscriptions ===============================================================

class TestSubscription(Subscription):
    # Simple GraphQL subscription.
    # Leave only latest 64 messages in the server queue.
    notification_queue_limit = 64

    # Subscription payload.
    message = String()
    time = String()

    class Arguments:
        # That is how subscription arguments are defined.
        arg1 = String(required=False)
        arg2 = String(required=False)

    @staticmethod
    def subscribe(root, info, arg1="", arg2=""):
        # Called when user subscribes.
        # Return the list of subscription group names.
        return ["TestSubscriptionEvents"]

    @staticmethod
    def publish(payload, info, arg1="", arg2=""):
        # Called to notify the client.
        # Here `payload` contains the `payload` from the `broadcast()`
        # invocation (see below). You can return `MySubscription.SKIP`
        # if you wish to suppress the notification to a particular
        # client. For example, this allows to avoid notifications for
        # the tasks made by this particular client.
        return TestSubscription(
            message=f"{payload}",
            time=datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        )


class TestSubscriptionEventMutationPayload(ObjectType):
    response = String()


class TestSubscriptionEventMutation(Mutation):
    class Arguments:
        message = String(required=True)

    Output = TestSubscriptionEventMutationPayload

    @classmethod
    def mutate(cls, root, info, message):
        print(f"New message broadcasted: {message}")
        TestSubscription.broadcast(group="TestSubscriptionEvents", payload=message)
        return TestSubscriptionEventMutationPayload(response="OK")


# Schema ======================================================================

Connection = UUIDDjangoFilterConnectionField


class QueryType(ObjectType):
    # Relay
    node = Node.Field()
    # ACE
    list_aces = Connection(
        ACEType, filterset_class=ACEFilterSet)
    # Device
    list_devices = Connection(DeviceType)
    # Equipment
    list_equipment = Connection(EquipmentType)
    # Location
    list_locations = Connection(LocationType)
    # LocationCategory
    list_location_categories = Connection(LocationCategoryType)
    # Message
    list_messages = Connection(
        MessageType, filterset_class=MessageFilterSet)
    # MessageFilter
    list_message_filters = Connection(
        MessageFilterType, filterset_class=MessageFilterFilterSet)
    # Operation
    list_operations = Connection(OperationType)
    # Organization
    list_organizations = Connection(OrganizationType)
    # Participant
    list_participants = Connection(ParticipantType)
    # Person
    list_persons = Connection(PersonType)
    get_person_profile = Field(PersonType)
    # PersonProperty
    list_person_properties = Connection(PersonPropertyType)
    # PersonPropertyGroup
    list_person_property_groups = Connection(PersonPropertyGroupType)
    # PersonToObject
    list_person_to_objects = Connection(
        PersonToObjectType, filterset_class=PersonToObjectFilterSet)
    # Project
    list_projects = Connection(ProjectType)
    # Resource
    list_resources = Connection(ResourceType)
    # Role
    list_roles = Connection(RoleType)
    # RoleSpecification
    list_role_specifications = Connection(RoleSpecificationType)
    # Shift
    list_shifts = Connection(ShiftType)
    # Task
    list_tasks = Connection(TaskType)
    # TaskField
    list_task_fields = Connection(TaskFieldType)

    @object_permits_user('read')
    def resolve_get_person_profile(parent, info):
        return info.context.user


class MutationType(ObjectType):
    # Authorization
    token_auth = LoginPersonMutation.Field()
    verify_token = graphql_jwt.relay.Verify.Field()
    refresh_token = graphql_jwt.relay.Refresh.Field()
    revoke_token = graphql_jwt.relay.Revoke.Field()
    # ACE
    create_ace = CreateACEMutation.Field()
    delete_ace = DeleteACEMutation.Field()
    # Device
    create_device = CreateDeviceMutation.Field()
    update_device = UpdateDeviceMutation.Field()
    delete_device = DeleteDeviceMutation.Field()
    # Equipment
    # create_equipment = CreateEquipmentMutation.Field()
    # update_equipment = UpdateEquipmentMutation.Field()
    # delete_equipment = DeleteEquipmentMutation.Field()
    # Location
    create_location = CreateLocationMutation.Field()
    update_location = UpdateLocationMutation.Field()
    delete_location = DeleteLocationMutation.Field()
    # LocationCategory
    create_location_category = CreateLocationCategoryMutation.Field()
    update_location_category = UpdateLocationCategoryMutation.Field()
    delete_location_category = DeleteLocationCategoryMutation.Field()
    # Message
    create_message = CreateMessageMutation.Field()
    update_message = UpdateMessageMutation.Field()
    delete_message = DeleteMessageMutation.Field()
    # MessageFilter
    create_message_filter = CreateMessageFilterMutation.Field()
    update_message_filter = UpdateMessageFilterMutation.Field()
    delete_message_filter = DeleteMessageFilterMutation.Field()
    # Operation
    create_operation = CreateOperationMutation.Field()
    update_operation = UpdateOperationMutation.Field()
    delete_operation = DeleteOperationMutation.Field()
    publish_operation = PublishOperationMutation.Field()
    archive_operation = ArchiveOperationMutation.Field()
    # Organization
    create_organization = CreateOrganizationMutation.Field()
    update_organization = UpdateOrganizationMutation.Field()
    delete_organization = DeleteOrganizationMutation.Field()
    publish_organization = PublishOrganizationMutation.Field()
    archive_organization = ArchiveOrganizationMutation.Field()
    # Participant
    create_participant = CreateParticipantMutation.Field()
    update_participant = UpdateParticipantMutation.Field()
    delete_participant = DeleteParticipantMutation.Field()
    accept_participant = AcceptParticipantMutation.Field()
    decline_participant = DeclineParticipantMutation.Field()
    admin_accept_participant = AdminAcceptParticipantMutation.Field()
    admin_decline_participant = AdminDeclineParticipantMutation.Field()
    # Person
    create_person = CreatePersonMutation.Field()
    update_person = UpdatePersonMutation.Field()
    delete_person = DeletePersonMutation.Field()
    register_person = RegisterPersonMutation.Field()
    request_person_activation = RequestPersonActivationMutation.Field()
    activate_person = ActivatePersonMutation.Field()
    request_person_password_reset = RequestPersonPasswordResetMutation.Field()
    reset_person_password = ResetPersonPasswordMutation.Field()
    change_person_password = ChangePersonPasswordMutation.Field()
    update_person_profile = UpdatePersonProfileMutation.Field()
    # PersonProperty
    create_person_property = CreatePersonPropertyMutation.Field()
    update_person_property = UpdatePersonPropertyMutation.Field()
    delete_person_property = DeletePersonPropertyMutation.Field()
    # PersonPropertyGroup
    create_person_property_group = CreatePersonPropertyGroupMutation.Field()
    update_person_property_group = UpdatePersonPropertyGroupMutation.Field()
    delete_person_property_group = DeletePersonPropertyGroupMutation.Field()
    # PersonToObject
    create_person_to_object = CreatePersonToObjectMutation.Field()
    update_person_to_object = UpdatePersonToObjectMutation.Field()
    delete_person_to_object = DeletePersonToObjectMutation.Field()
    # Project
    create_project = CreateProjectMutation.Field()
    update_project = UpdateProjectMutation.Field()
    delete_project = DeleteProjectMutation.Field()
    publish_project = PublishProjectMutation.Field()
    archive_project = ArchiveProjectMutation.Field()
    # Resource
    # create_resource = CreateResourceMutation.Field()
    # update_resource = UpdateResourceMutation.Field()
    # delete_resource = DeleteResourceMutation.Field()
    # Role
    create_role = CreateRoleMutation.Field()
    update_role = UpdateRoleMutation.Field()
    delete_role = DeleteRoleMutation.Field()
    accept_role = AcceptRoleMutation.Field()
    decline_role = DeclineRoleMutation.Field()
    # RoleSpecification
    create_role_specification = CreateRoleSpecificationMutation.Field()
    update_role_specification = UpdateRoleSpecificationMutation.Field()
    delete_role_specification = DeleteRoleSpecificationMutation.Field()
    # Shift
    create_shift = CreateShiftMutation.Field()
    update_shift = UpdateShiftMutation.Field()
    delete_shift = DeleteShiftMutation.Field()
    publish_shift = PublishShiftMutation.Field()
    archive_shift = ArchiveShiftMutation.Field()
    # Task
    create_task = CreateTaskMutation.Field()
    update_task = UpdateTaskMutation.Field()
    delete_task = DeleteTaskMutation.Field()
    publish_task = PublishTaskMutation.Field()
    archive_task = ArchiveTaskMutation.Field()
    # TaskField
    create_task_field = CreateTaskFieldMutation.Field()
    update_task_field = UpdateTaskFieldMutation.Field()
    delete_task_field = DeleteTaskFieldMutation.Field()

    # TestSubscription
    test_subscription_event = TestSubscriptionEventMutation.Field()


class SubscriptionType(ObjectType):
    test_subscription = TestSubscription.Field()


schema = Schema(
    query=QueryType,
    mutation=MutationType,
    subscription=SubscriptionType,
)
