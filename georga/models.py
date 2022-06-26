import uuid
import functools

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from graphql_relay import to_global_id


class MixinUUIDs(models.Model):
    """Public facing UUIDs."""
    class Meta:
        abstract = True
    # uuid for web/app clients
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    # global relay id
    @functools.cached_property
    def gid(self):
        return to_global_id(f"{self._meta.object_name}Type", self.uuid)


class Person(MixinUUIDs, AbstractUser):
    email = models.EmailField(
        'email address',
        blank=False,
        unique=True
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
    )

    qualifications = models.ManyToManyField(
        'Qualification',
        blank=True,
        verbose_name="qualification",
    )

    qualification_specific = models.CharField(
        max_length=60,
        null=True,
        blank=True,
        verbose_name="Qualif. Details",
    )

    restrictions = models.ManyToManyField(
        'Restriction',
        blank=True,
        verbose_name="Einschränkung",
    )

    restriction_specific = models.CharField(
        max_length=60,
        null=True,
        blank=True,
        verbose_name="Einschränkung Details",
    )

    occupation = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Beruf",
    )

    task_types_agreed = models.ManyToManyField(
        'TaskType',
        blank=True,
    )

    task_type_description = models.TextField(
        max_length=300,
        null=True,
        blank=True,
    )

    street = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Straße",
    )

    number = models.CharField(
        max_length=8,
        null=True,
        blank=True,
        verbose_name="Hausnr.",
    )

    postal_code = models.CharField(
        max_length=5,
        null=True,
        blank=True,
        verbose_name="PLZ",
    )

    city = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Ort",
    )

    private_phone = PhoneNumberField(
        null=True,
        blank=True,
        max_length=20,
        verbose_name="Festnetznummer",
    )

    mobile_phone = PhoneNumberField(
        null=True,
        blank=True,
        max_length=20,
        verbose_name="Mobilnummer",
    )

    remark = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name="Anmerkungen",
    )

    ANSWER_TOPICS = [
        ('undefiniert', 'undefiniert'),
        ('unbedingt', 'unbedingt'),
        ('nicht nur', 'nicht nur'),
    ]
    only_job_related_topics = models.CharField(
        max_length=11,
        choices=ANSWER_TOPICS,
        null=True,
        blank=True,
        verbose_name="Einsatz nur für eigene Fachtätigkeiten",
    )
    is_active = models.BooleanField(null=True, blank=True)

    roles = models.ManyToManyField(to='Role', null=True, blank=True)
    #geolocation
    activity_range_km = models.IntegerField(default=0)
    organization = models.ForeignKey(to='Device', on_delete=models.CASCADE, null=True, blank=True)
    resources_provided = models.ManyToManyField(to='Resource', null=True, blank=True)

    def __name__(self):
        return self.email

    def __str__(self):
        return self.email

    def set_password(self, raw_password):
        super().set_password(raw_password)
        self.password_modified = timezone.now()

    class Meta:
        verbose_name = "registered helper"
        verbose_name_plural = "registered helpers"
        # TODO: translation: Registrierter Helfer


class Device(MixinUUIDs, models.Model):
    device_string = models.CharField(max_length=50, null=False, blank=False)
    os_version = models.CharField(max_length=35, null=False, blank=False)
    app_version = models.CharField(max_length=15, null=False, blank=False)
    push_token = models.UUIDField(default=uuid.uuid4, editable=False)

    def __str__(self):
        return '%s' % self.device_string

    class Meta:
        verbose_name = "client device"
        verbose_name_plural = "client devices"
        # TODO: translation: Client-Gerät


class Resource(MixinUUIDs, models.Model):
    description = models.CharField(max_length=50, null=False, blank=False)
    personal_hint = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return '%s' % self.description

    class Meta:
        verbose_name = "ressource"
        verbose_name_plural = "ressources"
        # TODO: translation: Ressource


class Organization(MixinUUIDs, models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "organization"
        verbose_name_plural = "organizations"
        # TODO: translation: Organisation


class Project(MixinUUIDs, models.Model):
    organization = models.ForeignKey(to='Organization', on_delete=models.DO_NOTHING, null=False, blank=False)
    name = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "project"
        verbose_name_plural = "projects"
        # TODO: translation: Projekt


class Deployment(MixinUUIDs, models.Model):
    organization = models.ForeignKey(to='Organization', on_delete=models.DO_NOTHING, null=False, blank=False)
    name = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "deployment"
        verbose_name_plural = "deployments"
        # TODO: translate: Einsatz


class TaskType(MixinUUIDs, models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)
    description = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "task type"
        verbose_name_plural = "task types"
        # TODO: translate: Aufgabentyp



class Task(MixinUUIDs, models.Model):
    project = models.ForeignKey(to='Project', on_delete=models.DO_NOTHING, null=False, blank=False)
    task_type = models.ForeignKey(to='TaskType', on_delete=models.DO_NOTHING, null=False, blank=False)
    roles_required = models.ManyToManyField(to='Role', null=True, blank=True, related_name='roles_required')
    roles_desirable = models.ManyToManyField(to='Role', null=True, blank=True, related_name='roles_desirable')
    resources_required = models.ManyToManyField(to='Resource', null=True, blank=True, related_name='resources_required')
    resources_desirable = models.ManyToManyField(to='Resource', null=True, blank=True, related_name='resources_desirable')
    persons_registered = models.ManyToManyField(to='Person', null=True, blank=True, related_name='persons_registered')
    persons_participated = models.ManyToManyField(to='Person', null=True, blank=True, related_name='persons_participated')
    #geolocation
    title = models.CharField(max_length=50, null=False, blank=False)
    postal_address_name = models.CharField(max_length=50, null=True, blank=True)
    postal_address_street = models.CharField(max_length=50, null=True, blank=True)
    postal_address_zip_code = models.CharField(max_length=50, null=True, blank=True)
    postal_address_city = models.CharField(max_length=50, null=True, blank=True)
    postal_address_country = models.CharField(max_length=50, null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    def __str__(self):
        return '%s' % self.title

    class Meta:
        verbose_name = "task"
        verbose_name_plural = "tasks"
        # TODO: translate: Aufgabe


class Schedule(MixinUUIDs, models.Model):
    task = models.ForeignKey(to='Task', on_delete=models.CASCADE, null=False, blank=False)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    class Meta:
        verbose_name = "schedule"
        verbose_name_plural = "schedules"
        # TODO: translate: Schichtplan


class Timeslot(MixinUUIDs, models.Model):
    schedule = models.ForeignKey(to='Schedule', on_delete=models.CASCADE, null=False, blank=False)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    class Meta:
        verbose_name = "timeslot"
        verbose_name_plural = "timeslots"
        # TODO: translate: Schichtplan


class Qualification(MixinUUIDs, models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)
    qualification_type = models.ForeignKey(to='LocationType', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        abstract = True
        verbose_name = "qualification"
        verbose_name_plural = "qualification"
        # TODO: translate: Qualifikation


class QualificationType(MixinUUIDs, models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "qualification type"
        verbose_name_plural = "qualification types"
        # TODO: translate: Qualifikationstyp


class Restriction(MixinUUIDs, models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "restriction"
        verbose_name_plural = "restrictions"
        # TODO: translate: Einschränkung


class Role(MixinUUIDs, models.Model):
    description = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return '%s' % self.description

    class Meta:
        verbose_name = "role"
        verbose_name_plural = "roles"
        # TODO: translate: Einsatzrolle

class EquipmentProvided(MixinUUIDs, models.Model):
    name = models.CharField(max_length=30, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "equipment provided by organization"
        verbose_name_plural = "equipments provided by organization"
        # TODO: translate: Ausstattung durch Organisation


class EquipmentSelf(MixinUUIDs, models.Model):
    name = models.CharField(max_length=30, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "own equipment"
        verbose_name_plural = "own equipments"
        # TODO: translate: Eigene Ausstattung


class Location(MixinUUIDs, models.Model):
    address = models.CharField(max_length=200)
    location_type = models.ForeignKey(to='LocationType', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name = "location"
        verbose_name_plural = "locations"
        # TODO: translate: Ort


class LocationType(MixinUUIDs, models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        verbose_name = "location type"
        verbose_name_plural = "location types"
        # TODO: translate: Einsatzort-Typ
        # e.g. deployment location


class Notification(MixinUUIDs, models.Model):
    title = models.CharField(max_length=50)
    contents = models.CharField(max_length=1000)
    notification_type = models.ForeignKey(to='NotificationType', on_delete=models.CASCADE, null=True, blank=True)
    PRIORITY = [
        ('DISTURB', 'disturb'),
        ('ONAPPCALL', 'on app call'),
        ('ONNEWS', 'on reading news actively'),
    ]
    priority = models.CharField(max_length=8, choices=PRIORITY, default='ONNEWS')


class NotificationType(MixinUUIDs, models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        verbose_name = "notification type"
        verbose_name_plural = "notification types"
        # TODO: translate: Benachrichtigungstyp
