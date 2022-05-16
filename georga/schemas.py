# from django.core.exceptions import ValidationError
from django.db.models import ManyToManyField, ManyToManyRel, ManyToOneRel
from django.forms.models import model_to_dict
from django.forms import (
    ModelForm, ModelChoiceField, ModelMultipleChoiceField,
    IntegerField, CharField, ChoiceField
)
from django.contrib.auth.password_validation import validate_password

from graphql_relay import from_global_id
from graphene import Schema, ObjectType, List, ID, String, NonNull
from graphene.relay import Node
from graphene.types.dynamic import Dynamic

from graphene_django import DjangoObjectType
from graphene_django.fields import DjangoListField, DjangoConnectionField
from graphene_django.filter import DjangoFilterConnectionField
from graphene_django.converter import convert_django_field
from graphene_django.forms import GlobalIDMultipleChoiceField
from graphene_django.forms.mutation import DjangoModelFormMutation

import graphql_jwt
from graphql_jwt.decorators import login_required, staff_member_required

from channels_graphql_ws import Subscription as GQLSubscription

from .auth import jwt_decode
from .email import Email
from .models import (
    ActionCategory,
    EquipmentProvided,
    EquipmentSelf,
    HelpOperation,
    Location,
    Person,
    Poll,
    PollChoice,
    QualificationAdministrative,
    QualificationHealth,
    QualificationLanguage,
    QualificationLicense,
    QualificationTechnical,
    Restriction,
)


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
            del(args['id'])

        # insert uuid to filter field predicate string for forgein models
        for name, _filter in filterset_class.base_filters.items():
            if isinstance(_filter.field, GlobalIDMultipleChoiceField):
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
            del(cls._meta.fields[cls._meta.return_field_name])

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
            if isinstance(field.type, List) and field.type.of_type == ID:
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

# ActionCategory --------------------------------------------------------------

# fields
action_category_ro_fields = [
    'uuid',
]
action_category_wo_fields = []
action_category_rw_fields = [
    'name',
]
action_category_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
}


# types
class ActionCategoryType(UUIDDjangoObjectType):
    class Meta:
        model = ActionCategory
        fields = action_category_ro_fields + action_category_rw_fields
        filter_fields = action_category_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# EquipmentProvided -----------------------------------------------------------

# fields
equipment_provided_ro_fields = [
    'uuid',
]
equipment_provided_wo_fields = []
equipment_provided_rw_fields = [
    'name',
]
equipment_provided_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
}


# types
class EquipmentProvidedType(UUIDDjangoObjectType):
    class Meta:
        model = EquipmentProvided
        fields = equipment_provided_ro_fields + equipment_provided_rw_fields
        filter_fields = equipment_provided_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# EquipmentSelf ---------------------------------------------------------------

# fields
equipment_self_ro_fields = [
    'uuid',
]
equipment_self_wo_fields = []
equipment_self_rw_fields = [
    'name',
]
equipment_self_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
}


# types
class EquipmentSelfType(UUIDDjangoObjectType):
    class Meta:
        model = EquipmentSelf
        fields = equipment_self_ro_fields + equipment_self_rw_fields
        filter_fields = equipment_self_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# HelpOperation ---------------------------------------------------------------

# fields
help_operation_ro_fields = [
    'uuid',
    'person_set',
]
help_operation_wo_fields = []
help_operation_rw_fields = [
    'name',
]
help_operation_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
    'person': LOOKUPS_CONNECTION,
}


# types
class HelpOperationType(UUIDDjangoObjectType):
    class Meta:
        model = HelpOperation
        fields = help_operation_ro_fields + help_operation_rw_fields
        filter_fields = help_operation_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# Location --------------------------------------------------------------------

# fields
location_ro_fields = [
    'uuid',
    'poll_set',
]
location_wo_fields = []
location_rw_fields = [
    'address',
]
location_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'address': LOOKUPS_STRING,
    'poll': LOOKUPS_CONNECTION,
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
    'qualifications_language',
    'qualifications_technical',
    'qualifications_license',
    'qualifications_health',
    'qualifications_administrative',
    'qualification_specific',
    'restrictions',
    'restriction_specific',
    'occupation',
    'help_operations',
    'help_description',
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
    'qualifications_language': LOOKUPS_CONNECTION,
    'qualifications_technical': LOOKUPS_CONNECTION,
    'qualifications_license': LOOKUPS_CONNECTION,
    'qualifications_health': LOOKUPS_CONNECTION,
    'qualifications_administrative': LOOKUPS_CONNECTION,
    'qualification_specific': LOOKUPS_STRING,
    'restrictions': LOOKUPS_CONNECTION,
    'restriction_specific': LOOKUPS_STRING,
    'occupation': LOOKUPS_STRING,
    'help_operations': LOOKUPS_CONNECTION,
    'help_description': LOOKUPS_STRING,
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


# Poll ------------------------------------------------------------------------

# fields
poll_ro_fields = [
    'uuid',
]
poll_wo_fields = []
poll_rw_fields = [
    'title',
    'description',
    'choices',
    'location',
    'style',
]
poll_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'title': LOOKUPS_STRING,
    'description': LOOKUPS_STRING,
    'choices': LOOKUPS_CONNECTION,
    'location': LOOKUPS_ID,
    'style': LOOKUPS_ENUM,
}


# types
class PollType(UUIDDjangoObjectType):
    class Meta:
        model = Poll
        fields = poll_ro_fields + poll_rw_fields
        filter_fields = poll_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# PollChoice ------------------------------------------------------------------

# fields
poll_choice_ro_fields = [
    'uuid',
    'poll_set',
]
poll_choice_wo_fields = []
poll_choice_rw_fields = [
    'start_time',
    'end_time',
    'max_participants',
    'persons',
]
poll_choice_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'start_time': LOOKUPS_DATETIME,
    'end_time': LOOKUPS_DATETIME,
    'max_participants': LOOKUPS_INT,
    'persons': LOOKUPS_CONNECTION,
    'poll': LOOKUPS_CONNECTION,
}


# types
class PollChoiceType(UUIDDjangoObjectType):
    class Meta:
        model = PollChoice
        fields = poll_choice_ro_fields + poll_choice_rw_fields
        filter_fields = poll_choice_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# QualificationAdministrative -------------------------------------------------

# fields
qualification_administrative_ro_fields = [
    'uuid',
    'person_set',
]
qualification_administrative_wo_fields = []
qualification_administrative_rw_fields = [
    'name',
]
qualification_administrative_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
    'person': LOOKUPS_CONNECTION,
}


# types
class QualificationAdministrativeType(UUIDDjangoObjectType):
    class Meta:
        model = QualificationAdministrative
        fields = qualification_administrative_ro_fields + qualification_administrative_rw_fields
        filter_fields = qualification_administrative_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# QualificationHealth ---------------------------------------------------------

# fields
qualification_health_ro_fields = [
    'uuid',
    'person_set',
]
qualification_health_wo_fields = []
qualification_health_rw_fields = [
    'name',
]
qualification_health_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
    'person': LOOKUPS_CONNECTION,
}


# types
class QualificationHealthType(UUIDDjangoObjectType):
    class Meta:
        model = QualificationHealth
        fields = qualification_health_ro_fields + qualification_health_rw_fields
        filter_fields = qualification_health_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# QualificationLanguage -------------------------------------------------------

# fields
qualification_language_ro_fields = [
    'uuid',
    'person_set',
]
qualification_language_wo_fields = []
qualification_language_rw_fields = [
    'name',
]
qualification_language_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
    'person': LOOKUPS_CONNECTION,
}


# types
class QualificationLanguageType(UUIDDjangoObjectType):
    class Meta:
        model = QualificationLanguage
        fields = qualification_language_ro_fields + qualification_language_rw_fields
        filter_fields = qualification_language_filter_fields
        permissions = [login_required]


# forms
class QualificationLanguageModelForm(UUIDModelForm):
    class Meta:
        model = QualificationLanguage
        fields = qualification_language_wo_fields + qualification_language_rw_fields


# cud mutations
class CreateQualificationLanguageMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = QualificationLanguageModelForm
        exclude_fields = ['id']
        permissions = [staff_member_required]


class UpdateQualificationLanguageMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = QualificationLanguageModelForm
        required_fields = ['id']
        permissions = [login_required]


class DeleteQualificationLanguageMutation(UUIDDjangoModelFormMutation):
    class Meta:
        form_class = QualificationLanguageModelForm
        only_fields = ['id']
        permissions = [staff_member_required]

    @classmethod
    def perform_mutate(cls, form, info):
        qualification_language = form.instance
        qualification_language.delete()
        return cls(qualification_language=qualification_language, errors=[])

# flow mutations


# QualificationLicense --------------------------------------------------------

# fields
qualification_license_ro_fields = [
    'uuid',
    'person_set',
]
qualification_license_wo_fields = []
qualification_license_rw_fields = [
    'name',
]
qualification_license_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
    'person': LOOKUPS_CONNECTION,
}


# types
class QualificationLicenseType(UUIDDjangoObjectType):
    class Meta:
        model = QualificationLicense
        fields = qualification_license_ro_fields + qualification_license_rw_fields
        filter_fields = qualification_license_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# QualificationTechnical ------------------------------------------------------

# fields
qualification_technical_ro_fields = [
    'uuid',
    'person_set',
]
qualification_technical_wo_fields = []
qualification_technical_rw_fields = [
    'name',
]
qualification_technical_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
    'person': LOOKUPS_CONNECTION,
}


# types
class QualificationTechnicalType(UUIDDjangoObjectType):
    class Meta:
        model = QualificationTechnical
        fields = qualification_technical_ro_fields + qualification_technical_rw_fields
        filter_fields = qualification_technical_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# Restriction -----------------------------------------------------------------

# fields
restriction_ro_fields = [
    'uuid',
    'person_set',
]
restriction_wo_fields = []
restriction_rw_fields = [
    'name',
]
restriction_filter_fields = {
    'id': LOOKUPS_ID,
    'uuid': LOOKUPS_ID,
    'name': LOOKUPS_STRING,
    'person': LOOKUPS_CONNECTION,
}


# types
class RestrictionType(UUIDDjangoObjectType):
    class Meta:
        model = Restriction
        fields = restriction_ro_fields + restriction_rw_fields
        filter_fields = restriction_filter_fields
        permissions = [login_required]


# forms
# cud mutations
# flow mutations


# Subscriptions ===============================================================

class TestSubscription(GQLSubscription):
    """Simple GraphQL subscription."""

    # Leave only latest 64 messages in the server queue.
    notification_queue_limit = 64

    # Subscription payload.
    event = String()

    class Arguments:
        """That is how subscription arguments are defined."""
        arg1 = String()
        arg2 = String()

    @staticmethod
    def subscribe(root, info, arg1, arg2):
        """Called when user subscribes."""

        # Return the list of subscription group names.
        return ["group42"]

    @staticmethod
    def publish(payload, info, arg1, arg2):
        """Called to notify the client."""

        # Here `payload` contains the `payload` from the `broadcast()`
        # invocation (see below). You can return `MySubscription.SKIP`
        # if you wish to suppress the notification to a particular
        # client. For example, this allows to avoid notifications for
        # the actions made by this particular client.

        return TestSubscription(event="Something has happened!")


# Schema ======================================================================

class Query(ObjectType):
    node = Node.Field()
    all_action_categories = UUIDDjangoFilterConnectionField(
        ActionCategoryType)
    all_equipment_provided = UUIDDjangoFilterConnectionField(
        EquipmentProvidedType)
    all_equipment_self = UUIDDjangoFilterConnectionField(
        EquipmentSelfType)
    all_help_operations = UUIDDjangoFilterConnectionField(
        HelpOperationType)
    all_locations = UUIDDjangoFilterConnectionField(
        LocationType)
    all_persons = UUIDDjangoFilterConnectionField(
        PersonType)
    all_polls = UUIDDjangoFilterConnectionField(
        PollType)
    all_poll_choices = UUIDDjangoFilterConnectionField(
        PollChoiceType)
    all_qualifications_administrative = UUIDDjangoFilterConnectionField(
        QualificationAdministrativeType)
    all_qualifications_health = UUIDDjangoFilterConnectionField(
        QualificationHealthType)
    all_qualifications_language = UUIDDjangoFilterConnectionField(
        QualificationLanguageType)
    all_qualifications_license = UUIDDjangoFilterConnectionField(
        QualificationLicenseType)
    all_qualifications_technical = UUIDDjangoFilterConnectionField(
        QualificationTechnicalType)
    all_restrictions = UUIDDjangoFilterConnectionField(
        RestrictionType)


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

    # QualificationLanguage
    create_qualification_language = CreateQualificationLanguageMutation.Field()
    update_qualification_language = UpdateQualificationLanguageMutation.Field()
    delete_qualification_language = DeleteQualificationLanguageMutation.Field()


class Subscription(ObjectType):
    test_subscription = TestSubscription.Field()


schema = Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)
