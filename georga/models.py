from operator import or_
from datetime import datetime
from functools import cached_property, reduce
import uuid

from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from phonenumber_field.modelfields import PhoneNumberField
from graphql_relay import to_global_id


# --- MIXINS

class MixinUUIDs(models.Model):
    """
    Public facing UUIDs.

    Attributes:
        uuid (models.UUIDField()): uuid for web/app clients.
    """
    class Meta:
        abstract = True
    # uuid for web/app clients
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )

    # global relay id
    @cached_property
    def gid(self):
        """str: global relay id (base64 encoded `<ModelName>,<UUID>`)"""
        return to_global_id(f"{self._meta.object_name}Type", self.uuid)


class MixinAuthorization(models.Model):
    """
    Methods for instance level authorization.

    Permissions are deduced from:
    - an instance: Model instance to be inquired.
    - a user: Person instance, for which permission is requested.
    - an action: Actions may be arbitrary strings, e.G. CRUD operations.

    Access rules for a model are defined by overriding `Model.permitted()`,
    which has to return a bool or a Q object to filter the accessible instances.
    For details on how to override, see the docstring of the method.

    Permission on instances can be inquired by `instance.permits()`,
    querysets can be filtered by `Model.filter_permitted()`.

    Examples:
        Set permissions for Person instances to read and write only itself::

            class Person(MixinAuthorization, models.Model):
                @classmethod
                def permitted(cls, instance, user, action):
                    # unpersisted instance (create)
                    if instance and not instance.id:
                        return False
                    # none or persisted instance (read, write, delete, etc)
                    if action in ['read', 'write']:
                        return Q(pk=user.pk)
                    return None

        Check permission::

            if person.permits(context.user, 'write'):
                person.save()

        Check multiple permission (logical OR)::

            if person.permits(context.user, ('read', 'write')):
                person.save()

        Filter queryset::

            qs = Person.filter_permitted(Person.objects, context.user, 'read')

    Note:
        For usage with graphene_django, see `georga.auth.object_permits_user()`.
    """
    class Meta:
        abstract = True

    @staticmethod
    def _prepare_permission_actions(actions):
        """
        Helper method to ensure actions to be a tuple of strings.

        Args:
            actions (str|tuple[str]): Action or tuple of actions.

        Returns:
            tuple[str]: Tuple of action strings.

        Raises:
            AssertionError: If `actions` is not a str or a tuple[str].
        """
        # convert string to tuple
        if isinstance(actions, str):
            actions = tuple([actions])
        # allow only tuple
        assert isinstance(actions, tuple), f"Error: actions {actions} is not a tuple."
        # allow only strings in tuple
        for action in actions:
            assert isinstance(action, str), f"Error: action {action} is not a string."
        return actions

    @classmethod
    def filter_permitted(cls, queryset, instance, user, actions):
        """
        Filters a queryset to include only permitted instances for the user.

        Args:
            queryset (QuerySet()): Instance of QuerySet to filter.
            instance (Model()|None): Model instance to be inquired or None.
            user (Person()): Person instance, for which permission is requested.
            actions (str|tuple[str]): Action or tuple of actions, one of which
                the user is required to have (logical OR, if multiple are given).
                Actions may be arbitrary strings, e.G. CRUD operations.

        Returns:
            The `queryset` filtered by the Q object returned by `permitted()`.
        """
        # prepare actions
        actions = cls._prepare_permission_actions(actions)
        # combine Q objects for each action
        q = Q()
        for action in actions:
            # get the Q object
            permitted = cls.permitted(instance, user, action)
            # don't combine, if False or None
            if permitted in [False, None]:
                continue
            # return full queryset, if True
            if permitted is True:
                return queryset
            # combine Q objects (logical OR)
            q |= permitted
        # return filtered or none queryset
        if q:
            return queryset.filter(q)
        return queryset.none()

    @classmethod
    def permitted(cls, instance, user, action):
        """
        Defines the permissions for the user, instance and action.

        This method has to be overridden in each model to define the permissions.
        To specify the permissions, two cases have to be handeled differently:
        1. Queryset filtering and persisted instances:
           The return value has to be
           - a `Q` object to obtain the filtered queryset, which should only
             include the accessible instances.
           - `True` to allow all and obtain a queryset with all instances
             included (via `Model.objects.all()`).
           - `False|None` to deny all and obtain a queryset with no instances
             included (via `Model.objects.none()`).
           The resulting queryset is directly used for queryset filtering.
           Inquiries on persisted instances add an additional constraint for
           its pk and query the database for the existance of a match.
           This way the load is delegated to the database service and only
           one access rule needs to be defined in `permitted()` for both access
           control and filtering.
        2. Unpersisted instances:
           As the database can't be queried for unpersisted instances, the
           permission should be derived directly and the return value has to
           evaluate to bool, e.G.:
           - `True` to permit the action.
           - `False|None` to deny the action.

        Args:
            instance (Model()|None): Model instance to be inquired or None.
            user (Person()): Person instance, for which permission is requested.
            action (str): Actions may be arbitrary strings, e.G. CRUD operations.

        Returns:
            Q object: To filter a queryset.
            True: To allow all or permit the action.
            False|None: To deny all or deny the action.

        Examples:
            Set permissions for Person instances to read and write only itself::

                class Person(MixinAuthorization, models.Model):
                    @classmethod
                    def permitted(cls, instance, user, action):
                        # unpersisted instance (create)
                        if instance and not instance.id:
                            return False
                        # none or persisted instance (read, write, delete, etc)
                        if action in ['read', 'write']:
                            return Q(pk=user.pk)
                        return None

        Note:
            All permissions are denied by default when inherited from the Mixin.
        """
        # unpersisted instances (create)
        if instance and not instance.id:
            match action:
                case _:
                    return False
        # queryset filtering and persisted instances (read, write, delete, etc)
        match action:
            case _:
                return None

    def permits(self, user, actions):
        """
        Inquires a Model instance, if it grants some user certain permissions.

        Persisted instances use the filtered queryset result of
        `filter_permitted()`, add another constraint for its pk, and query the
        database for the existance of a match.

        Unpersisted instances evaluate the return value of `permitted()` to
        bool to decide, if the permission is granted or not.

        Args:
            user (Person()): Person instance, for which permission is requested.
            actions (str|tuple[str]): Action or tuple of actions, one of which
                the user is required to have (logical OR, if multiple are given).
                Actions may be arbitrary strings, e.G. CRUD operations.

        Returns:
            True if permission was granted, False otherwise.
        """
        # unpersisted instances (create)
        if not self.pk:
            # prepare actions
            actions = self._prepare_permission_actions(actions)
            # get and combine permitted results
            permit = False
            for action in actions:
                permit |= bool(self.permitted(self, user, action))
            return permit
        # queryset filtering and persisted instances (read, write, delete, etc)
        qs = self.filter_permitted(self._meta.model.objects, self, user, actions)
        return qs.filter(pk=self.pk).exists()


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
        unique_together = ('access_object_ct', 'access_object_id', 'person', 'ace_string',)

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

        # restrict persons to have a true is_staff flag
        if not self.person.is_staff:
            raise ValidationError(f"person {self.person.gid} is not staff")

        # restrict persons to be employed by the organization
        organization = self.access_object.organization
        valid_organizations = self.person.organizations_employed.all()
        if organization not in valid_organizations:
            raise ValidationError(
                f"person {self.person.gid} is not employed by organization "
                f"of access_object {self.access_object.gid}")

    @classmethod
    def permitted(cls, instance, user, action):
        if not user.is_staff:
            return False
        admin_organizations = Organization.objects.filter(
            Q(ace__person=user.id, ace__ace_string="ADMIN")
        )
        admin_projects = Project.objects.filter(
            Q(organization__ace__person=user.id,
              organization__ace__ace_string="ADMIN")
            | Q(ace__person=user.id, ace__ace_string="ADMIN")
        )
        admin_operations = Operation.objects.filter(
            Q(project__organization__ace__person=user.id,
              project__organization__ace__ace_string="ADMIN")
            | Q(project__ace__person=user.id, project__ace__ace_string="ADMIN")
            | Q(ace__person=user.id, ace__ace_string="ADMIN")
        )
        # unpersisted instances (create)
        if instance and not instance.id:
            match action:
                case 'create':
                    obj = instance.access_object
                    # ACEs for projects can be created by organization admins
                    if isinstance(obj, Project):
                        return obj.organization in admin_organizations
                    # ACEs for operations can be created by organization/project admins
                    if isinstance(obj, Operation):
                        return obj.project in admin_projects
                case _:
                    return False
        # queryset filtering and persisted instances (read, write, delete, etc)
        match action:
            case 'read':
                return reduce(or_, [
                    # ACEs for the user can be read by the user
                    Q(person=user),
                    # ACEs for organizations can be read by organization admins
                    Q(organization__in=admin_organizations),
                    # ACEs for projects can be read by organization/project admins
                    Q(project__in=admin_projects),
                    # ACEs for operations can be read by organization/project/operation admins
                    Q(operation__in=admin_operations),
                ])
            case 'update':
                return reduce(or_, [
                    # ACEs for organizations can be updated by organization admins
                    Q(organization__in=admin_organizations),
                    # ACEs for projects can be updated by organization/project admins
                    Q(project__in=admin_projects),
                    # ACEs for operations can be updated by organization/project/operation admins
                    Q(operation__in=admin_operations),
                ])
            case 'delete':
                return reduce(or_, [
                    # ACEs for projects can be deleted by organization admins
                    Q(project__organization__in=admin_organizations),
                    # ACEs for operations can be deleted by organization/project admins
                    Q(operation__project__in=admin_projects),
                ])
            case _:
                return None


class Device(MixinUUIDs, MixinAuthorization, models.Model):
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


class Equipment(MixinUUIDs, MixinAuthorization, models.Model):
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


class Location(MixinUUIDs, MixinAuthorization, models.Model):
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


class LocationCategory(MixinUUIDs, MixinAuthorization, models.Model):
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


class PersonToObject(MixinUUIDs, MixinAuthorization, models.Model):
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


class Message(MixinUUIDs, MixinAuthorization, models.Model):
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
        """
        str (SENT_ERROR|PENDING|SENT|SENT_SUCCESSFULLY): Returns the least
            optimal delivery state of all channels in the given order.
        """
        for state in ["SENT_ERROR", "PENDING", "SENT", "SENT_SUCCESSFULLY"]:
            for channel_state in [self.delivery_state_email,
                                  self.delivery_state_push,
                                  self.delivery_state_sms]:
                if channel_state == state:
                    return state
        return "NONE"


class Operation(MixinUUIDs, MixinAuthorization, models.Model):
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

    @property
    def organization(self):
        """Organisation(): Returns the Organization of the Operation."""
        return self.project.organization


class Organization(MixinUUIDs, MixinAuthorization, models.Model):
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
        related_query_name='organization'
    )
    messages = GenericRelation(
        Message,
        content_type_field='scope_ct',
        object_id_field='scope_id',
        related_query_name='organization'
    )
    person_attributes = GenericRelation(
        PersonToObject,
        content_type_field='relation_object_ct',
        object_id_field='relation_object_id',
        related_query_name='organization'
    )

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")
        # TODO: translation: Organisation

    @property
    def organization(self):
        """
        Organisation(): Returns self. Added to ease the handling of all
            `ACL.access_object`s by being able to get the organization attribute.
        """
        return self


class Participant(MixinUUIDs, MixinAuthorization, models.Model):
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
        related_name='persons_subscribed',
    )
    organizations_employed = models.ManyToManyField(
        to='Organization',
        blank=True,
        verbose_name=_("organizations employed at"),
        related_name='persons_employed',
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

    ADMIN_LEVELS = [
        ('NONE', _('None')),
        ('OPERATION', _('Operation')),
        ('PROJECT', _("Project")),
        ('ORGANIZATION', _("Organization"))
    ]

    @property
    def admin_level(self):
        """
        str (NONE|ORGANIZATION|PROJECT|OPERATION): Returns the highest
            hierarchical level for which the user has ADMIN rights. Used as
            indicator for clients to adjust the interface accordingly.
        """
        level = "NONE"
        for ace in self.ace_set.all():
            if ace.ace_string != "ADMIN":
                continue
            obj = ace.access_object
            if isinstance(obj, Organization):
                return "ORGANIZATION"
            if isinstance(obj, Project):
                level = "PROJECT"
            if level != "PROJECT" and isinstance(obj, Operation):
                level = "OPERATION"
        return level

    @classmethod
    def permitted(cls, instance, user, action):
        # unpersisted instances (create)
        if instance and not instance.id:
            match action:
                case _:
                    return False
        # queryset filtering and persisted instances (read, write, delete, etc)
        match action:
            case 'read' | 'write':
                return Q(pk=user.pk)
            case _:
                return None


class PersonProperty(MixinUUIDs, MixinAuthorization, models.Model):
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


class PersonPropertyGroup(MixinUUIDs, MixinAuthorization, models.Model):
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


class Project(MixinUUIDs, MixinAuthorization, models.Model):
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


class Resource(MixinUUIDs, MixinAuthorization, models.Model):
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


class Role(MixinUUIDs, MixinAuthorization, models.Model):
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


class RoleSpecification(MixinUUIDs, MixinAuthorization, models.Model):
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


class Shift(MixinUUIDs, MixinAuthorization, models.Model):
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


class Task(MixinUUIDs, MixinAuthorization, models.Model):
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


class TaskField(MixinUUIDs, MixinAuthorization, models.Model):
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
