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
        ('herr', 'Herr'),
        ('frau', 'Frau'),
        ('divers', 'Divers'),
        ('none', 'Keine'),
    ]

    title = models.CharField(
        max_length=6,
        choices=TITLES,
        default='none',
    )

    qualifications_language = models.ManyToManyField(
        'QualificationLanguage',
        blank=True,
        verbose_name="Sprachkenntnisse",
    )

    qualifications_technical = models.ManyToManyField(
        'QualificationTechnical',
        blank=True,
        verbose_name="Qualifikationen Technisch",
    )

    qualifications_license = models.ManyToManyField(
        'QualificationLicense',
        blank=True,
        verbose_name="Führerscheine",
    )

    qualifications_health = models.ManyToManyField(
        'QualificationHealth',
        blank=True,
        verbose_name="Qualifikationen Gesundheitswesen",
    )

    qualifications_administrative = models.ManyToManyField(
        'QualificationAdministrative',
        blank=True,
        verbose_name="Qualifikationen Verwaltung",
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

    help_operations = models.ManyToManyField(
        'HelpOperation',
        blank=True,
    )

    help_description = models.TextField(
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
        verbose_name = "Registrierter Helfer"
        verbose_name_plural = "Registrierte Helfer"


class Device(MixinUUIDs, models.Model):
    device_string = models.CharField(max_length=50, null=False, blank=False)
    os_version = models.CharField(max_length=35, null=False, blank=False)
    app_version = models.CharField(max_length=15, null=False, blank=False)
    push_token = models.UUIDField(default=uuid.uuid4, editable=False)

    def __str__(self):
        return '%s' % self.device_string

    class Meta:
        verbose_name = "Client-Gerät"
        verbose_name_plural = "Client-Geräte"


class Resource(MixinUUIDs, models.Model):
    description = models.CharField(max_length=50, null=False, blank=False)
    personal_hint = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return '%s' % self.description

    class Meta:
        verbose_name = "Ressource"
        verbose_name_plural = "Ressourcen"


class Organization(MixinUUIDs, models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Trägerorganisation"
        verbose_name_plural = "Trägerorganisationen"


class Project(MixinUUIDs, models.Model):
    organization = models.ForeignKey(to='Organization', on_delete=models.DO_NOTHING, null=False, blank=False)
    name = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Einsatzprojekt"
        verbose_name_plural = "Einsatzprojekte"


class ActionType(MixinUUIDs, models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)
    description = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Einsatzaktionstyp"
        verbose_name_plural = "Einsatzaktionstypen"


class Action(MixinUUIDs, models.Model):
    project = models.ForeignKey(to='Project', on_delete=models.DO_NOTHING, null=False, blank=False)
    action_type = models.ForeignKey(to='ActionType', on_delete=models.DO_NOTHING, null=False, blank=False)
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
        verbose_name = "Einsatzaktion"
        verbose_name_plural = "Einsatzaktionen"


class HelpOperation(MixinUUIDs, models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Hilfstätigkeit"
        verbose_name_plural = "Hilfstätigkeit"


class ActionCategory(MixinUUIDs, models.Model):
    name = models.CharField(max_length=30, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Einsatzkategorie"
        verbose_name_plural = "Einsatzkategorien"


class MixinQualification(models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        abstract = True
        verbose_name = "Qualifikation"
        verbose_name_plural = "Qualifikationen"


class QualificationTechnical(MixinQualification, MixinUUIDs, models.Model):
    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Technische Qualifikation"
        verbose_name_plural = "Technische Qualifikationen"


class QualificationLanguage(MixinQualification, MixinUUIDs, models.Model):
    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Sprachkenntnis"
        verbose_name_plural = "Sprachkenntnisse"


class QualificationLicense(MixinQualification, MixinUUIDs, models.Model):
    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Führerschein"
        verbose_name_plural = "Führerscheine"


class QualificationHealth(MixinQualification, MixinUUIDs, models.Model):
    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Qualifikation Gesundheitswesen"
        verbose_name_plural = "Qualifikationen Gesundheitswesen"


class QualificationAdministrative(MixinQualification, MixinUUIDs, models.Model):
    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Qualifikation Verwaltung"
        verbose_name_plural = "Qualifikationen Verwaltung"


class Restriction(MixinUUIDs, models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Einschränkung"
        verbose_name_plural = "Einschränkungen"


class Role(MixinUUIDs, models.Model):
    description = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return '%s' % self.description

    class Meta:
        verbose_name = "Einsatzrolle"
        verbose_name_plural = "Einsatzrollen"


class EquipmentProvided(MixinUUIDs, models.Model):
    name = models.CharField(max_length=30, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Ausstattung durch HiOrg"
        verbose_name_plural = "Ausstattungen durch HiOrg"


class EquipmentSelf(MixinUUIDs, models.Model):
    name = models.CharField(max_length=30, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Ausstattung mitzubringen"
        verbose_name_plural = "Ausstattungen mitzubringen"


class Location(MixinUUIDs, models.Model):
    address = models.CharField(max_length=200)

    class Meta:
        verbose_name = "Einsatzort"
        verbose_name_plural = "Einsatzorte"


class PollChoice(MixinUUIDs, models.Model):
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    max_participants = models.IntegerField(default=1)

    persons = models.ManyToManyField(to='Person', blank=True)

    class Meta:
        verbose_name = "Umfrageoption"
        verbose_name_plural = "Umfrageoptionen"


class Poll(MixinUUIDs, models.Model):
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=2000)
    choices = models.ManyToManyField(to='PollChoice', blank=True)
    location = models.ForeignKey(to='Location', on_delete=models.DO_NOTHING, null=True, blank=True)

    PollStyles = [
        ('default', 'default'),
        # (1, 'timetable')
    ]

    style = models.CharField(choices=PollStyles, default='default', max_length=20)

    class Meta:
        verbose_name = "Umfrage"
        verbose_name_plural = "Umfragen"
