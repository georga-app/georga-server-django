from datetime import datetime
import functools
import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
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


# --- CLASSES

class ACL(MixinUUIDs, models.Model):
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
    )
    object_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
    )
    access_object = GenericForeignKey(
        'content_type',
        'object_id',
    )

    person = models.ForeignKey(
        to='Person',
        to_field='uuid',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        default=uuid.uuid4,
    )

    ACL_CODENAMES = [
        ('ADMIN', 'admin'),
    ]
    acl_string = models.CharField(
        max_length=5,
        choices=ACL_CODENAMES,
        default='ADMIN',
    )

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]


class Device(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        default=0,
    )
    device_string = models.CharField(
        max_length=50,
        null=False,
        blank=False,
    )
    os_version = models.CharField(
        max_length=35,
        null=False,
        blank=False,
    )
    app_version = models.CharField(
        max_length=15,
        null=False,
        blank=False,
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
        null=False,
        blank=False,
        default=0,
    )
    name = models.CharField(
        max_length=30,
        null=False,
        blank=False,
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
        null=False,
        blank=False,
        default=0,
    )
    address = models.CharField(max_length=200)
    location_category = models.ForeignKey(
        to='LocationCategory',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("location")
        verbose_name_plural = _("locations")
        # TODO: translate: Ort


class LocationCategory(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        default=0,
    )
    name = models.CharField(
        max_length=50,
    )

    class Meta:
        verbose_name = _("location category")
        verbose_name_plural = _("location categories")
        # TODO: translate: Einsatzort-Kategorie
        # e.g. operation location


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
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
    )
    object_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
    )
    scope = GenericForeignKey(
        'content_type',
        'object_id',
    )
    title = models.CharField(
        max_length=100,
    )
    contents = models.CharField(
        max_length=1000,
    )
    PRIORITY = [
        ('DISTURB', 'disturb'),
        ('ONAPPCALL', 'on app call'),
        ('ONNEWS', 'on reading news actively'),
    ]
    priority = models.CharField(
        max_length=9,
        choices=PRIORITY,
        default='ONNEWS',
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
    delivery_state = models.CharField(
        max_length=17,
        choices=DELIVERY_STATES,
        default='NONE',
    )


class Operation(MixinUUIDs, models.Model):
    project = models.ForeignKey(
        to='Project',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        default=0,
    )
    name = models.CharField(
        max_length=100,
        null=False,
        blank=False,
    )
    is_active = models.BooleanField(
        null=True,
        blank=True,
        default=True,
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
        null=False,
        blank=False,
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
        null=False,
        blank=False,
        default=0,
    )
    person = models.ForeignKey(
        to='Person',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        default=0,
    )


class Person(MixinUUIDs, AbstractUser):
    email = models.EmailField(
        'email address',
        blank=False,
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
        verbose_name=_("title"),
    )

    person_properties = models.ManyToManyField(
        'PersonProperty',
        blank=True,
        verbose_name=_("person properties"),
    )

    person_properties_freetext = models.CharField(
        max_length=60,
        null=True,
        blank=True,
        verbose_name=_("person properties freetext"),
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
        blank=False,
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


class PersonProperty(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        default=0,
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
        related_name="person_property_group",
    )
    NECESSITIES = [
        ('RECOMMENDED', _("recommended")),
        ('MANDATORY', _("mandatory")),
    ]
    necessity = models.CharField(
        max_length=11,
        choices=NECESSITIES,
        null=False,
        blank=False,
        default="RECOMMENDED",
        verbose_name=_("necessity"),
        # TODO: translate: "Erforderlichkeit"
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
        null=False,
        blank=False,
        default=0,
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

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("group of person properties")
        verbose_name_plural = _("groups of person properties")
        # TODO: translate: PersonPropertyGroup


class PersonToObject(MixinUUIDs, models.Model):
    person = models.ForeignKey(
        to='Person',
        to_field='uuid',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        default=uuid.uuid4,
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
    )
    object_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
    )
    access_object = GenericForeignKey(
        'content_type',
        'object_id',
    )
    unseen = models.BooleanField(
        null=False,
        blank=False,
        default=True,
    )
    bookmarked = models.BooleanField(
        null=False,
        blank=False,
        default=False,
    )


class Project(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        default=0,
    )
    name = models.CharField(
        max_length=50,
        null=False,
        blank=False,
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
        null=False,
        blank=False,
        default=0,
    )
    title = models.CharField(
        max_length=50,
        null=False,
        blank=False,
        default='',
    )
    description = models.CharField(
        max_length=50,
        null=False,
        blank=False,
    )
    personal_hint = models.CharField(
        max_length=50,
        null=False,
        blank=False,
    )
    equipment_needed = models.ManyToManyField(
        to='Equipment',
        blank=True,
        related_name='equipment_needed',
    )
    amount = models.IntegerField(
        null=False,
        blank=False,
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
        null=False,
        blank=False,
        default=0,
    )
    title = models.CharField(
        max_length=50,
        null=False,
        blank=False,
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
        null=False,
        blank=False,
        default=0,
    )
    person_properties = models.ManyToManyField(
        to='PersonProperty',
        blank=True,
        related_name='person_properties',
    )


class Shift(MixinUUIDs, models.Model):
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    STATES = [
        ('DRAFT', 'draft'),
        ('PUBLISHED', 'published'),
        ('CANCELED', 'canceled'),
        ('DELETED', 'deleted'),
    ]
    state = models.CharField(
        max_length=9,
        choices=STATES,
        default='DRAFT',
    )
    task = models.ForeignKey(
        to='Task',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        default=0,
    )
    enrollment_deadline = models.DateTimeField(
        default=datetime.now,
    )
    locations = models.ManyToManyField(
        to='Location',
        blank=False,
        related_name='shift_locations',
    )

    class Meta:
        verbose_name = _("shift")
        verbose_name_plural = _("shifts")
        # TODO: translate: Schicht


class Task(MixinUUIDs, models.Model):
    operation = models.ForeignKey(
        to='Operation',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        default=0,
    )
    task_field = models.ForeignKey(
        to='TaskField',
        on_delete=models.DO_NOTHING,
        null=False,
        blank=False,
    )
    roles = models.ManyToManyField(
        to='Role',
        blank=True,
        related_name='task_roles',
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
    persons_registered = models.ManyToManyField(
        to='Person',
        blank=True,
        related_name='persons_registered',
    )
    persons_participated = models.ManyToManyField(
        to='Person',
        blank=True,
        related_name='persons_participated',
    )
    locations = models.ManyToManyField(
        to='Location',
        blank=True,
        related_name='task_locations',
    )
    title = models.CharField(
        max_length=100,
        null=False,
        blank=False,
    )
    description = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
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
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(
        null=True,
        blank=True,
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
        null=False,
        blank=False,
        default=0,
    )
    name = models.CharField(
        max_length=50,
        null=False,
        blank=False,
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
