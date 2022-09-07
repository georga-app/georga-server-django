from datetime import datetime
import functools
import uuid

from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext as _
from phonenumber_field.modelfields import PhoneNumberField
from graphql_relay import to_global_id


# --- MIXINS

class MixinUUIDs(models.Model):
    """Public facing UUIDs."""
    class Meta:
        abstract = True
    # uuid for web/app clients
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )

    # global relay id
    @functools.cached_property
    def gid(self):
        return to_global_id(f"{self._meta.object_name}Type", self.uuid)


class MixinAuthorization(models.Model):
    """
    Methods for instance level authorization.

    Access rules for a model are defined by overriding `Model.permitted()`
    to return a dictionary of lookup expressions and values,
    which select the accessible instances.

    Access to an instance can be inquired via `instance.permits()`.
    A filtered queryset can be obtained via `Model.filter_permitted()`.

    All methods need to be called with the parameters:
        user: Person instance
        access_string: arbitraty description of a role or permission

    If the granting of some role or permission should be configurable via ACEs,
    the access_string should match the choices of ACE.access_string field.

    For usage with graphene_django see `georga.auth.object_permits_user()`.

    Example: permitted lookup expressions

        class Person(MixinAuthorization, models.Model):
            @classmethod
            def permitted(cls, user, access_string):
                permitted = None
                if access_string == 'admin':
                    permitted = {
                        'pk': user.pk
                    }
                return permitted

    Example: permit execution^

        if person.permits(context.user, 'admin'):
            person.change_password('secret')
            person.save()

    Example: filter queryset

        queryset = Person.objects.all()
        filtered_queryset = Person.filter_permitted(
            queryset, context.user, 'admin')
    """
    class Meta:
        abstract = True

    @classmethod
    def filter_permitted(cls, queryset, user, access_strings):
        """
        Filters a queryset to include only permitted instances for the user.

        Multiple access_strings (tuple) are combined with an OR.
        Returns a queryset filtered by the lookups defined in permitted().
        """
        if not isinstance(access_strings, tuple):
            access_strings = tuple([access_strings])
        result = None
        for access_string in access_strings:
            permitted = cls.permitted(user, access_string)
            if permitted is None:
                continue
            qs = queryset.filter(**permitted)
            result = result and result.union(qs) or qs
        return result or queryset.none()

    @classmethod
    def permitted(cls, user, access_string):
        """
        Defines the permissions of the object.

        Returns a dict of lookups expressions and values to filter queryset
        or None to deny all. Denies all by default.
        """
        return None

    def permits(self, user, access_strings):
        """
        Asks an object, if it grants some user certain permissions.

        Multiple access_strings (tuple) are combined with an OR.
        Issues database queries using the lookups defined in permitted().
        Returns True if permission was granted, False otherwise.
        """
        if not isinstance(access_strings, tuple):
            access_strings = (access_strings)
        result = False
        for access_string in access_strings:
            permitted = self.permitted(user, access_string)
            if permitted is None:
                return False
            if 'pk' in permitted and self.pk != permitted['pk']:
                return False
            permitted['pk'] = self.pk
            result = result or self._meta.model.objects.filter(**permitted).exists()
        return result


# --- CLASSES

class ACE(MixinUUIDs, MixinAuthorization, models.Model):
    # *_cts list: list of valid models
    # checked in ForeignKey.limit_choices_to, Model.clean() and GQLFilterSet
    access_object_cts = ['organization', 'project', 'operation']
    access_object_ct = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': access_object_cts},
    )
    access_object_id = models.PositiveIntegerField()
    access_object = GenericForeignKey(
        'access_object_ct',
        'access_object_id',
    )

    person = models.ForeignKey(
        to='Person',
        on_delete=models.CASCADE,
    )

    ACE_CODENAMES = [
        ('ADMIN', 'admin'),
    ]
    ace_string = models.CharField(
        max_length=5,
        choices=ACE_CODENAMES,
        default='ADMIN',
    )

    class Meta:
        indexes = [
            models.Index(fields=["access_object_ct", "access_object_id"]),
        ]

    def clean(self):
        super().clean()

        # restrict foreign models of access object
        label = self.access_object_ct.app_label
        model = self.access_object_ct.model
        valid_models = {'georga': self.access_object_cts}
        if label not in valid_models or model not in valid_models[label]:
            raise ValidationError(
                f"'{self.access_object_ct.app_labeled_name}' is not a valid "
                "content type for ACE.access_object")


class Device(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
    )
    device_string = models.CharField(
        max_length=50,
    )
    os_version = models.CharField(
        max_length=35,
    )
    app_version = models.CharField(
        max_length=15,
    )
    push_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
    )

    def __str__(self):
        return '%s' % self.device_string

    class Meta:
        verbose_name = _("client device")
        verbose_name_plural = _("client devices")
        # TODO: translation: Client-Gerät


class Equipment(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=30,
        default='',
    )
    OWNER = [
        ('SELF', 'person itself'),
        ('ORG', 'provided by organization'),
        ('THIRDPARTY', 'other party'),
    ]
    owner = models.CharField(
        max_length=10,
        choices=OWNER,
        default='ORG',
    )

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("equipment")
        verbose_name_plural = _("equipment")
        # TODO: translate: Eigenes oder Material der Organisation


class Location(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
    )
    postal_address_name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    postal_address_street = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    postal_address_zip_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    postal_address_city = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    postal_address_country = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    location_category = models.ForeignKey(
        to='LocationCategory',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    task = models.ForeignKey(  # if set, this becomes a template to all subsequent shifts of the task
        to='Task',
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    shift = models.ForeignKey(  # if set, concrete location associated to a shift
        to='Shift',
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name = _("location")
        verbose_name_plural = _("locations")
        # TODO: translate: Ort


class LocationCategory(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=50,
    )

    class Meta:
        verbose_name = _("location category")
        verbose_name_plural = _("location categories")
        # TODO: translate: Einsatzort-Kategorie
        # e.g. operation location


class PersonToObject(MixinUUIDs, models.Model):
    person = models.ForeignKey(
        to='Person',
        on_delete=models.CASCADE,
    )

    # *_cts list: list of valid models
    # checked in ForeignKey.limit_choices_to, Model.clean() and GQLFilterSet
    relation_object_cts = [
        'organization', 'project', 'operation', 'task', 'shift', 'role', 'message']
    relation_object_ct = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': relation_object_cts},
    )
    relation_object_id = models.PositiveIntegerField()
    relation_object = GenericForeignKey(
        'relation_object_ct',
        'relation_object_id',
    )

    unnoticed = models.BooleanField(
        default=True,
    )
    bookmarked = models.BooleanField(
        default=False,
    )

    class Meta:
        indexes = [
            models.Index(fields=["relation_object_ct", "relation_object_id"]),
        ]

    def clean(self):
        super().clean()

        # restrict foreign models of relation_object
        label = self.relation_object_ct.app_label
        model = self.relation_object_ct.model
        valid_models = {'georga': self.relation_object_cts}
        if label not in valid_models or model not in valid_models[label]:
            raise ValidationError(
                f"'{self.relation_object_ct.app_labeled_name}' is not a valid "
                "content type for PersonToObject.relation_object")


class Message(MixinUUIDs, models.Model):
    '''
    A Message is sent via different channels to registered persons.

    priority: describes, how disruptive the message should be
    - disturb:
    category:
    - news: manually sent contents
    - alert: triggered by the system by cronjobs based on analysis
    - activity: on change of objects, which are relevant to the persons
    '''
    # *_cts list: list of valid models
    # checked in ForeignKey.limit_choices_to, Model.clean() and GQLFilterSet
    scope_cts = ['organization', 'project', 'operation', 'task', 'shift']
    scope_ct = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': scope_cts},
    )
    scope_id = models.PositiveIntegerField()
    scope = GenericForeignKey(
        'scope_ct',
        'scope_id',
    )

    title = models.CharField(
        max_length=100,
    )
    contents = models.CharField(
        max_length=1000,
    )
    PRIORITY = [
        ('URGENT', 'Urgent'),
        ('IMPORTANT', 'Important'),
        ('NORMAL', 'Normal'),
    ]
    priority = models.CharField(
        max_length=9,
        choices=PRIORITY,
        default='NORMAL',
    )
    CATEGORIES = [
        ('NEWS', 'news'),
        ('ALERT', 'alert'),
        ('ACTIVITY', 'activity'),
    ]
    category = models.CharField(
        max_length=8,
        choices=CATEGORIES,
        default='NEWS',
    )
    STATES = [
        ('DRAFT', 'draft'),
        ('PUBLISHED', 'published'),
    ]
    state = models.CharField(
        max_length=9,
        choices=STATES,
        default='DRAFT',
    )

    DELIVERY_STATES = [
        ('NONE', 'none'),
        ('PENDING', 'pending'),
        ('SENT', 'sent'),
        ('SENT_SUCCESSFULLY', 'sent successfully'),
        ('SENT_ERROR', 'sent error'),
    ]
    delivery_state_email = models.CharField(
        max_length=17,
        choices=DELIVERY_STATES,
        default='NONE',
    )
    delivery_state_push = models.CharField(
        max_length=17,
        choices=DELIVERY_STATES,
        default='NONE',
    )
    delivery_state_sms = models.CharField(
        max_length=17,
        choices=DELIVERY_STATES,
        default='NONE',
    )

    person_attributes = GenericRelation(
        PersonToObject,
        content_type_field='relation_object_ct',
        object_id_field='relation_object_id',
        related_query_name='message'
    )

    class Meta:
        indexes = [
            models.Index(fields=["scope_ct", "scope_id"]),
        ]

    def clean(self):
        super().clean()

        # restrict foreign models of scope
        label = self.scope_ct.app_label
        model = self.scope_ct.model
        valid_models = {'georga': self.scope_cts}
        if label not in valid_models or model not in valid_models[label]:
            raise ValidationError(
                f"'{self.scope_ct.app_labeled_name}' is not a valid "
                "content type for Message.scope")

    @property
    def delivery_state(self):
        for state in ["SENT_ERROR", "PENDING", "SENT", "SENT_SUCCESSFULLY"]:
            for channel_state in [self.delivery_state_email,
                                  self.delivery_state_push,
                                  self.delivery_state_sms]:
                if channel_state == state:
                    return state
        return "NONE"


class Operation(MixinUUIDs, models.Model):
    project = models.ForeignKey(
        to='Project',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=100,
    )
    description = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(
        null=True,
        blank=True,
        default=True,
    )

    ace = GenericRelation(
        ACE,
        content_type_field='access_object_ct',
        object_id_field='access_object_id',
        related_query_name='operation'
    )
    messages = GenericRelation(
        Message,
        content_type_field='scope_ct',
        object_id_field='scope_id',
        related_query_name='operation'
    )
    person_attributes = GenericRelation(
        PersonToObject,
        content_type_field='relation_object_ct',
        object_id_field='relation_object_id',
        related_query_name='operation'
    )

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("operation")
        verbose_name_plural = _("operations")
        # TODO: translate: Einsatz


class Organization(MixinUUIDs, models.Model):
    name = models.CharField(
        max_length=50,
    )
    icon = models.TextField(
        null=True,
        blank=True,
    )

    ace = GenericRelation(
        ACE,
        content_type_field='access_object_ct',
        object_id_field='access_object_id',
        related_query_name='organisation'
    )
    messages = GenericRelation(
        Message,
        content_type_field='scope_ct',
        object_id_field='scope_id',
        related_query_name='organisation'
    )
    person_attributes = GenericRelation(
        PersonToObject,
        content_type_field='relation_object_ct',
        object_id_field='relation_object_id',
        related_query_name='organisation'
    )

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")
        # TODO: translation: Organisation


class Participant(MixinUUIDs, models.Model):
    role = models.ForeignKey(
        to='Role',
        on_delete=models.CASCADE,
    )
    person = models.ForeignKey(
        to='Person',
        on_delete=models.CASCADE,
    )


class Person(MixinUUIDs, MixinAuthorization, AbstractUser):
    email = models.EmailField(
        'email address',
        unique=True,
    )
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    password_modified = models.DateTimeField(default=timezone.now)

    TITLES = [
        ('MR', _('Mr.')),
        ('MS', _('Ms.')),
        ('MX', _('Mx.')),
        ('NONE', _('None')),
    ]

    title = models.CharField(
        max_length=4,
        choices=TITLES,
        default='NONE',
        blank=True,
        verbose_name=_("title"),
    )

    properties = models.ManyToManyField(
        'PersonProperty',
        blank=True,
        verbose_name=_("properties"),
    )

    person_properties_freetext = models.CharField(
        max_length=60,
        null=True,
        blank=True,
        verbose_name=_("properties freetext"),
    )

    occupation = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("occupation"),
    )

    task_fields_agreed = models.ManyToManyField(
        'TaskField',
        blank=True,
        verbose_name=_("agreement to task fields"),
    )

    task_field_note = models.TextField(
        max_length=300,
        null=True,
        blank=True,
        verbose_name=_("task field note"),
    )

    street = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("street"),
    )

    number = models.CharField(
        max_length=8,
        null=True,
        blank=True,
        verbose_name=_("street number"),
    )

    postal_code = models.CharField(
        max_length=5,
        null=True,
        blank=True,
        verbose_name=_("postal code"),
    )

    city = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("address - city"),
    )

    private_phone = PhoneNumberField(
        null=True,
        blank=True,
        max_length=20,
        verbose_name=_("fixed telephone"),
    )

    mobile_phone = PhoneNumberField(
        null=True,
        blank=True,
        max_length=20,
        verbose_name=_("mobile phone"),
    )

    remark = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name=_("remarks"),
    )

    ANSWER_TOPICS = [
        ('UNDEFINED', _("undefined")),
        ('ABSOLUTE', _("absolute")),
        ('NOTONLY', _("not only")),
    ]
    only_job_related_topics = models.CharField(
        max_length=9,
        choices=ANSWER_TOPICS,
        null=True,
        blank=True,
        verbose_name=_("commitment only for job-related topics"),
        # "Einsatz nur für eigene Fachtätigkeiten"
    )
    is_active = models.BooleanField(
        null=True,
        blank=True,
    )

    roles_agreed = models.ManyToManyField(
        to='Role',
        blank=True,
        verbose_name=_("agreement to roles"),
    )

    # geolocation
    activity_radius_km = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        verbose_name=_("agreement to activity radius in km"),
    )

    organizations_subscribed = models.ManyToManyField(
        to='Organization',
        blank=True,
        verbose_name=_("organizations subscribed to"),
    )

    devices = models.ManyToManyField(
        to='Device',
        blank=True,
        verbose_name=_("devices"),
    )

    resources_provided = models.ManyToManyField(
        to='Resource',
        blank=True,
        verbose_name=_("resources provided")
    )

    def __name__(self):
        return self.email

    def __str__(self):
        return self.email

    def set_password(self, raw_password):
        super().set_password(raw_password)
        self.password_modified = timezone.now()

    class Meta:
        verbose_name = _("registered helper")
        verbose_name_plural = _("registered helpers")
        # TODO: translation: Registrierter Helfer

    PERMISSION_LEVELS = [
        ('NONE', _('None')),
        ('OPERATION', _('Operation')),
        ('PROJECT', _("Project")),
        ('ORGANIZATION', _("Organization"))
    ]

    @property
    def permission_level(self):
        level = "NONE"
        for ace in self.ace_set.all():
            obj = ace.access_object
            if isinstance(obj, Organization):
                return "ORGANIZATION"
            if isinstance(obj, Project):
                level = "PROJECT"
            if level != "PROJECT" and isinstance(obj, Operation):
                level = "OPERATION"
        return level

    @classmethod
    def permitted(cls, user, access_string):
        permitted = None
            permitted = {
                'pk': user.pk
            }
        return permitted
        if access_string == 'self':


class PersonProperty(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    group = models.ForeignKey(
        to='PersonPropertyGroup',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("person property")
        verbose_name_plural = _("person properties")
        # TODO: translate: PersonProperty


class PersonPropertyGroup(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
    )
    codename = models.CharField(
        max_length=30,
        default='',
        verbose_name=_("person propery group"),
    )

    name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    SELECTION_TYPES = [
        ('MULTISELECT', _('multiselect')),
        ('SINGLESELECT', _('singleselect')),
    ]

    selection_type = models.CharField(
        max_length=12,
        choices=SELECTION_TYPES,
        default='MULTISELECT',
        verbose_name=_("selection type"),
    )
    NECESSITIES = [
        ('RECOMMENDED', _("recommended")),
        ('MANDATORY', _("mandatory")),
        ('NOT_POSSIBLE', _("not possible")),
    ]
    necessity = models.CharField(
        max_length=12,
        choices=NECESSITIES,
        default="RECOMMENDED",
        verbose_name=_("necessity"),
        # TODO: translate: "Erforderlichkeit"
    )

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("group of person properties")
        verbose_name_plural = _("groups of person properties")
        # TODO: translate: PersonPropertyGroup


class Project(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=50,
    )
    description = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )

    ace = GenericRelation(
        ACE,
        content_type_field='access_object_ct',
        object_id_field='access_object_id',
        related_query_name='project'
    )
    messages = GenericRelation(
        Message,
        content_type_field='scope_ct',
        object_id_field='scope_id',
        related_query_name='project'
    )
    person_attributes = GenericRelation(
        PersonToObject,
        content_type_field='relation_object_ct',
        object_id_field='relation_object_id',
        related_query_name='project'
    )

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("project")
        verbose_name_plural = _("projects")
        # TODO: translation: Projekt


class Resource(MixinUUIDs, models.Model):
    shift = models.ForeignKey(
        to='Shift',
        on_delete=models.CASCADE,
    )
    title = models.CharField(
        max_length=50,
        default='',
    )
    description = models.CharField(
        max_length=50,
    )
    personal_hint = models.CharField(
        max_length=50,
    )
    equipment_needed = models.ManyToManyField(
        to='Equipment',
        blank=True,
        related_name='equipment_needed',
    )
    amount = models.IntegerField(
        verbose_name=_("Amount of resources desirable with this role"),
        default=1,
    )

    def __str__(self):
        return '%s' % self.description

    class Meta:
        verbose_name = _("resource")
        verbose_name_plural = _("resources")
        # TODO: translation: Ressource


class Role(MixinUUIDs, models.Model):
    shift = models.ForeignKey(
        to='Shift',
        on_delete=models.CASCADE,
    )
    title = models.CharField(
        max_length=50,
        default='',
    )
    description = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    is_template = models.BooleanField(
        null=True,
        blank=True,
        default=False,
    )

    task = models.ForeignKey(
        to='Task',
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    person_attributes = GenericRelation(
        PersonToObject,
        content_type_field='relation_object_ct',
        object_id_field='relation_object_id',
        related_query_name='role'
    )

    def __str__(self):
        return '%s' % self.description

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        # TODO: translate: Einsatzrolle


class RoleSpecification(MixinUUIDs, models.Model):
    role = models.ForeignKey(
        to='Role',
        on_delete=models.CASCADE,
    )
    person_properties = models.ManyToManyField(
        to='PersonProperty',
        blank=True,
        related_name='person_properties',
    )
    NECESSITIES = [
        ('RECOMMENDED', _("recommended")),
        ('MANDATORY', _("mandatory")),
        ('NOT_POSSIBLE', _("not possible")),
    ]
    necessity = models.CharField(
        max_length=12,
        choices=NECESSITIES,
        default="RECOMMENDED",
        verbose_name=_("necessity"),
        # TODO: translate: "Erforderlichkeit"
    )


class Shift(MixinUUIDs, models.Model):
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    STATES = [
        ('DRAFT', 'draft'),
        ('PUBLISHED', 'published'),
        ('CANCELED', 'canceled'),
        ('DELETED', 'deleted'),
        ('DONE', 'done'),
    ]
    state = models.CharField(
        max_length=9,
        choices=STATES,
        default='DRAFT',
    )
    task = models.ForeignKey(
        to='Task',
        on_delete=models.CASCADE,
    )
    enrollment_deadline = models.DateTimeField(
        default=datetime.now,
    )

    messages = GenericRelation(
        Message,
        content_type_field='scope_ct',
        object_id_field='scope_id',
        related_query_name='shift'
    )
    person_attributes = GenericRelation(
        PersonToObject,
        content_type_field='relation_object_ct',
        object_id_field='relation_object_id',
        related_query_name='shift'
    )

    class Meta:
        verbose_name = _("shift")
        verbose_name_plural = _("shifts")
        # TODO: translate: Schicht


class Task(MixinUUIDs, models.Model):
    operation = models.ForeignKey(
        to='Operation',
        on_delete=models.CASCADE,
    )
    field = models.ForeignKey(
        to='TaskField',
        on_delete=models.DO_NOTHING,  # TODO: implement sane strategy how to cope with field deletion
    )
    resources_required = models.ManyToManyField(
        to='Resource',
        blank=True,
        related_name='resources_required',
    )
    resources_desirable = models.ManyToManyField(
        to='Resource',
        blank=True,
        related_name='resources_desirable',
    )
    name = models.CharField(
        max_length=100,
    )
    description = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    messages = GenericRelation(
        Message,
        content_type_field='scope_ct',
        object_id_field='scope_id',
        related_query_name='task'
    )
    person_attributes = GenericRelation(
        PersonToObject,
        content_type_field='relation_object_ct',
        object_id_field='relation_object_id',
        related_query_name='task'
    )

    def __str__(self):
        return '%s' % self.title

    class Meta:
        verbose_name = _("task")
        verbose_name_plural = _("tasks")
        # TODO: translate: Aufgabe


class TaskField(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=50,
    )
    description = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("task field")
        verbose_name_plural = _("task fields")
        # TODO: translate: Aufgabentyp
