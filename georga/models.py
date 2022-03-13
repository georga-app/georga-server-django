import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


# WEEKDAYS = [
#     (1, ("Monday")),
#     (2, ("Tuesday")),
#     (3, ("Wednesday")),
#     (4, ("Thursday")),
#     (5, ("Friday")),
#     (6, ("Saturday")),
#     (7, ("Sunday")),
# ]


# class GeneralWorkAvailability(models.Model):
#     weekday = models.IntegerField(
#         choices=WEEKDAYS,
#         unique=False)
#     forenoon = models.BooleanField()
#     afternoon = models.BooleanField()
#     evening = models.BooleanField()


# class OpeningTime(models.Model):
#     weekday = models.IntegerField(
#         choices=WEEKDAYS,
#         unique=False)
#     from_hour = models.TimeField()
#     to_hour = models.TimeField()


# class SinglePersonUptime(models.Model):
#     weekday = models.IntegerField(
#         choices=WEEKDAYS,
#         unique=True)
#     DAYTIMES = [
#         ('vormittags', 'Vormittags'),
#         ('nachmittags', 'Nachmittags'),
#         ('abends', 'Abends'),
#     ]
#     daytime = models.CharField(
#         max_length=11,
#         choices=DAYTIMES,
#         blank=True,
#     )


class Person(AbstractUser):
    email = models.EmailField(
        'email address',
        blank=False,
        unique=True
    )
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

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
    # company = models.CharField(
    #     max_length=50,
    #     null=True,
    #     blank=True,
    #     verbose_name="Firma",
    # )
    # position_in_company = models.CharField(
    #     max_length=50,
    #     null=True,
    #     blank=True,
    #     verbose_name="Position im Unternehmen",
    # )
    # opening_times = models.ManyToManyField(
    #     'OpeningTime',
    #     blank=True,
    #     verbose_name="Geschäftszeiten",
    #     related_name="opening_times",
    # )
    # emergency_opening_times = models.ManyToManyField(
    #     'OpeningTime',
    #     blank=True,
    #     verbose_name="Geschäftliche Notdienstzeiten",
    #     related_name="emergency_opening_times",
    # )
    # possible_work_times = models.ManyToManyField(
    #     'GeneralWorkAvailability',
    #     blank=True,
    #     verbose_name="Verfügbarkeitszeiten für Hilfe",
    #     related_name="general_work_availability",
    # )
    # company_phone = PhoneNumberField(
    #     null=True,
    #     blank=True,
    #     max_length=20,
    #     verbose_name="Geschäftsnummer Festnetz",
    # )
    # company_phone_mobile = PhoneNumberField(
    #     null=True,
    #     blank=True,
    #     max_length=20,
    #     verbose_name="Geschäftsnummer Mobil",
    # )
    # emergency_phone = PhoneNumberField(
    #     null=True,
    #     blank=True,
    #     max_length=20,
    #     verbose_name="Notfall-Rufnummer",
    # )
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
    # expiration_date = models.DateField(
    #     null=True,
    #     blank=True,
    #     default=None,
    #     verbose_name="Registriert bleiben bis",
    # )
    remark = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name="Anmerkungen",
    )
    # drk_honorary = models.BooleanField(
    #     null=True,
    #     blank=True,
    #     verbose_name="DRK Ehrenamt",
    # )
    # drk_employee = models.BooleanField(
    #     null=True,
    #     blank=True,
    #     verbose_name="DRK Hauptamt",
    # )
    # drk_home = models.CharField(
    #     max_length=50,
    #     null=True,
    #     blank=True,
    #     verbose_name="DRK-Zugehörigkeit",
    # )

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

    poll_uuid = models.UUIDField(
        unique=True, default=uuid.uuid4, editable=False)

    def __name__(self):
        return self.email

    def __str__(self):
        return self.email

    class Meta:
        verbose_name = "Registrierter Helfer"
        verbose_name_plural = "Registrierte Helfer"


class HelpOperation(models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Hilfstätigkeit"
        verbose_name_plural = "Hilfstätigkeit"


class ActionCategory(models.Model):
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


class QualificationTechnical(MixinQualification, models.Model):
    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Technische Qualifikation"
        verbose_name_plural = "Technische Qualifikationen"


class QualificationLanguage(MixinQualification, models.Model):
    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Sprachkenntnis"
        verbose_name_plural = "Sprachkenntnisse"


class QualificationLicense(MixinQualification, models.Model):
    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Führerschein"
        verbose_name_plural = "Führerscheine"


class QualificationHealth(MixinQualification, models.Model):
    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Qualifikation Gesundheitswesen"
        verbose_name_plural = "Qualifikationen Gesundheitswesen"


class QualificationAdministrative(MixinQualification, models.Model):
    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Qualifikation Verwaltung"
        verbose_name_plural = "Qualifikationen Verwaltung"


class Restriction(models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Einschränkung"
        verbose_name_plural = "Einschränkungen"


class EquipmentProvided(models.Model):
    name = models.CharField(max_length=30, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Ausstattung durch HiOrg"
        verbose_name_plural = "Ausstattungen durch HiOrg"


class EquipmentSelf(models.Model):
    name = models.CharField(max_length=30, null=True, blank=True)

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = "Ausstattung mitzubringen"
        verbose_name_plural = "Ausstattungen mitzubringen"

# class PublicationCategory(models.Model):
#     title = models.CharField(max_length=30, null=True, blank=True)
#     slug = models.CharField(
#         max_length=30, unique=True, null=False, blank=False)
#
#     def __str__(self):
#         return '%s' % self.title
#
#     def __unicode__(self):
#         return '%s' % self.title
#
#     class Meta:
#         verbose_name = "Artikelkategorie"
#         verbose_name_plural = "Artikelkategorien"
#
#
# class MixinPublication(models.Model):
#     title = models.CharField(max_length=60, unique=True, null=False,
#         blank=False, default="none")
#     slug = models.CharField(max_length=60, unique=True, null=False,
#         blank=False)
#     body = models.TextField()
#     posted = models.DateField(db_index=True, auto_now_add=True)
#
#     # topic = models.ForeignKey(PublicationCategory,
#     #     on_delete=models.SET_NULL, null=True, blank=False)
#
#     class Meta:
#         abstract = True
