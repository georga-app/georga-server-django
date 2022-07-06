import uuid
import functools

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
        ('HERR', 'Herr'),
        ('FRAU', 'Frau'),
        ('DIVERS', 'Divers'),
        ('NONE', 'Keine'),
    ]

    title = models.CharField(
        max_length=6,
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

    def __str__(self):
        return '%s' % self.description

    class Meta:
        verbose_name = _("resource")
        verbose_name_plural = _("resources")
        # TODO: translation: Ressource


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


class Deployment(MixinUUIDs, models.Model):
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
        verbose_name = _("deployment")
        verbose_name_plural = _("deployments")
        # TODO: translate: Einsatz


class Task(MixinUUIDs, models.Model):
    project = models.ForeignKey(
        to='Project',
        on_delete=models.DO_NOTHING,
        null=False,
        blank=False,
    )
    task_category = models.ForeignKey(
        to='TaskCategory',
        on_delete=models.DO_NOTHING,
        null=False,
        blank=False,
    )
    roles_required = models.ManyToManyField(
        to='Role',
        blank=True,
        related_name='roles_required',
    )
    roles_desirable = models.ManyToManyField(
        to='Role',
        blank=True,
        related_name='roles_desirable',
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
    # geolocation
    title = models.CharField(
        max_length=50,
        null=False,
        blank=False,
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
    end_time = models.DateTimeField()

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
        max_length=50,
        null=False,
        blank=False,
    )

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("task category")
        verbose_name_plural = _("task categories")
        # TODO: translate: Aufgabentyp


class Schedule(MixinUUIDs, models.Model):
    task = models.ForeignKey(
        to='Task',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    class Meta:
        verbose_name = _("schedule")
        verbose_name_plural = _("schedules")
        # TODO: translate: Schichtplan


class Timeslot(MixinUUIDs, models.Model):
    schedule = models.ForeignKey(
        to='Schedule',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    class Meta:
        verbose_name = _("timeslot")
        verbose_name_plural = _("timeslots")
        # TODO: translate: Schichtplan


class Qualification(MixinUUIDs, models.Model):
    name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    qualification_category = models.ForeignKey(
        to='LocationCategory',
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
        verbose_name = _("qualification category")
        verbose_name_plural = _("qualification categories")
        # TODO: translate: Qualifikationstyp


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
    description = models.CharField(
        max_length=50,
        null=False,
        blank=False,
    )

    def __str__(self):
        return '%s' % self.description

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        # TODO: translate: Einsatzrolle


class EquipmentProvided(MixinUUIDs, models.Model):
    name = models.CharField(
        max_length=30,
        null=True,
        blank=True,
    )

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("equipment provided by organization")
        verbose_name_plural = _("equipments provided by organization")
        # TODO: translate: Ausstattung durch Organisation


class EquipmentSelf(MixinUUIDs, models.Model):
    name = models.CharField(
        max_length=30,
        null=True,
        blank=True,
    )

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("own equipment")
        verbose_name_plural = _("own equipments")
        # TODO: translate: Eigene Ausstattung


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
        # TODO: translate: Einsatzort-Typ
        # e.g. deployment location


class Notification(MixinUUIDs, models.Model):
    title = models.CharField(
        max_length=50,
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
        max_length=50,
    )

    class Meta:
        verbose_name = _("notification category")
        verbose_name_plural = _("notification categories")
        # TODO: translate: Benachrichtigungstyp
