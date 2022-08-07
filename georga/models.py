from datetime import datetime
import functools
import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext as _
from phonenumber_field.modelfields import PhoneNumberField
from graphql_relay import to_global_id


class MixinUUIDs(models.Model):
    """Public facing UUIDs."""
    class Meta:
        abstract = True
    # uuid for web/app clients
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
    )

    # global relay id
    @functools.cached_property
    def gid(self):
        return to_global_id(f"{self._meta.object_name}Type", self.uuid)


class Deployment(MixinUUIDs, models.Model):
    project = models.ForeignKey(
        to='Project',
        on_delete=models.DO_NOTHING,
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
        verbose_name = _("deployment")
        verbose_name_plural = _("deployments")
        # TODO: translate: Einsatz


class Device(MixinUUIDs, models.Model):
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
    name = models.CharField(
        max_length=30,
        null=False,
        blank=False,
        default='',
    )
    OWNER = [
        ('SELF', 'person itself'),
        ('ORG', 'provided by organisation'),
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
    name = models.CharField(
        max_length=50,
    )

    class Meta:
        verbose_name = _("location category")
        verbose_name_plural = _("location categories")
        # TODO: translate: Einsatzort-Kategorie
        # e.g. deployment location


class Notification(MixinUUIDs, models.Model):
    title = models.CharField(
        max_length=100,
    )
    contents = models.CharField(
        max_length=1000,
    )
    notification_category = models.ForeignKey(
        to='NotificationCategory',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
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


class NotificationCategory(MixinUUIDs, models.Model):
    name = models.CharField(
        max_length=100,
    )

    class Meta:
        verbose_name = _("notification category")
        verbose_name_plural = _("notification categories")
        # TODO: translate: Benachrichtigungstyp


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

    qualifications = models.ManyToManyField(
        'Qualification',
        blank=True,
        verbose_name=_("qualification"),
    )

    qualification_specific = models.CharField(
        max_length=60,
        null=True,
        blank=True,
        verbose_name=_("qualification details"),
    )

    restrictions = models.ManyToManyField(
        'Restriction',
        blank=True,
        verbose_name=_("restrictions"),
    )

    restriction_specific = models.CharField(
        max_length=60,
        null=True,
        blank=True,
        verbose_name=_("restriction details"),
    )

    occupation = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("occupation"),
    )

    task_categories_agreed = models.ManyToManyField(
        'TaskCategory',
        blank=True,
        verbose_name=_("agreement to task categories"),
    )

    task_category_description = models.TextField(
        max_length=300,
        null=True,
        blank=True,
        verbose_name=_("task category details"),
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


class Project(MixinUUIDs, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.DO_NOTHING,
        null=False,
        blank=False,
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


class Qualification(MixinUUIDs, models.Model):
    name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    qualification_category = models.ForeignKey(
        to='QualificationCategory',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("qualification")
        verbose_name_plural = _("qualification")
        # TODO: translate: Qualifikation


class QualificationCategory(MixinUUIDs, models.Model):
    code = models.CharField(
        max_length=15,
        default='',
        verbose_name=_("qualification category"),
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
        verbose_name = _("qualification category")
        verbose_name_plural = _("qualification categories")
        # TODO: translate: Qualifikationstyp


class Resource(MixinUUIDs, models.Model):
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

    def __str__(self):
        return '%s' % self.description

    class Meta:
        verbose_name = _("resource")
        verbose_name_plural = _("resources")
        # TODO: translation: Ressource


class Restriction(MixinUUIDs, models.Model):
    name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("restriction")
        verbose_name_plural = _("restrictions")
        # TODO: translate: Einschränkung


class Role(MixinUUIDs, models.Model):
    title = models.CharField(
        max_length=50,
        null=False,
        blank=False,
        default='',
    )
    amount = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Amount of people desirable with this role"),
    )
    description = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    is_template = models.BooleanField(
        null=True,
        blank=True,
        default = False,
    )
    qualifications_suitable = models.ManyToManyField(
        to='Qualification',
        blank=True,
        related_name='qualifications_suitable',
    )

    def __str__(self):
        return '%s' % self.description

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        # TODO: translate: Einsatzrolle


class Task(MixinUUIDs, models.Model):
    deployment = models.ForeignKey(
        to='Deployment',
        on_delete=models.DO_NOTHING,
        null=False,
        blank=False,
        default=0,
    )
    task_category = models.ForeignKey(
        to='TaskCategory',
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


class TaskCategory(MixinUUIDs, models.Model):
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
        verbose_name = _("task category")
        verbose_name_plural = _("task categories")
        # TODO: translate: Aufgabentyp


class Timeslot(MixinUUIDs, models.Model):
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
    enrollment_deadline = models.DateTimeField(
        default=datetime.now,
    )
    locations = models.ManyToManyField(
        to='Location',
        blank=False,
        related_name='timeslot_locations',
    )
    roles = models.ManyToManyField(
        to='Role',
        blank=False,
        related_name='timeslot_roles',
    )

    class Meta:
        verbose_name = _("timeslot")
        verbose_name_plural = _("timeslots")
        # TODO: translate: Schichtplan
