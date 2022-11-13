from operator import or_
from datetime import datetime
from functools import cached_property, reduce
import uuid

from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser, UserManager
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, When, Case
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext as _
from django_fsm import FSMField, transition, RETURN_VALUE
from phonenumber_field.modelfields import PhoneNumberField
from graphql_relay import to_global_id


# fields ----------------------------------------------------------------------

@receiver(pre_save)
def set_fixture_timestamps(sender, instance, raw, **kwargs):
    """
    Sets timestamps of MixinTimestamps for fixtures.
    """
    if raw:
        instance.modified_at = timezone.now()
        if not instance.created_at:
            instance.created_at = timezone.now()


# mixins ----------------------------------------------------------------------

class MixinTimestamps(models.Model):
    """
    Timestamps for creation and last modification

    Attributes:
        created_at (models.DateTimeField()): Creation timestamp.
        modified_at (models.DateTimeField()): Last modification timestamp.
    """
    class Meta:
        abstract = True

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)


class MixinUUIDs(models.Model):
    """
    Public facing UUIDs.

    Attributes:
        uuid (models.UUIDField()): UUID for web/app clients.
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
        Set permissions for Person instances to be read and written only by
        themself and to be created only by staff members::

            class Person(MixinAuthorization, models.Model):
                @classmethod
                def permitted(cls, person, user, action):
                    # unpersisted instance (create)
                    if person and not person.id:
                        if user.is_staff:
                            return True
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

        Filter queryset for single permission::

            qs = Person.filter_permitted(context.user, 'read')

        Filter queryset for multiple permission (logical OR)::

            qs = Person.filter_permitted(context.user, ('read', 'write'))

        Filter a certain queryset::

            qs = Person.filter_permitted(context.user, 'read', Person.objects)

    Note:
        All permissions are denied by default when inherited from the Mixin.

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
    def filter_permitted(cls, user, actions, queryset=None, instance=None):
        """
        Filters a queryset to include only permitted instances for the user.

        Args:
            user (Person()): Person instance, for which permission is requested.
            actions (str|tuple[str]): Action or tuple of actions, one of which
                the user is required to have (logical OR, if multiple are given).
                Actions may be arbitrary strings, e.G. CRUD operations.
            queryset (QuerySet(), optional): Instance of QuerySet to filter.
            instance (Model(), optional): Model instance to be inquired.

        Returns:
            The `queryset` filtered by the Q object returned by `permitted()`.

        Examples:
            Filter queryset for single permission::

                qs = Person.filter_permitted(context.user, 'read')

            Filter queryset for multiple permission (logical OR)::

                qs = Person.filter_permitted(context.user, ('read', 'write'))

            Filter a certain queryset::

                qs = Person.filter_permitted(context.user, 'read', Person.objects)
        """
        # prepare queryset
        if queryset is None:
            queryset = cls.objects
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
            Set permissions for Person instances to be read and written only by
            themself and to be created only by staff members::

                class Person(MixinAuthorization, models.Model):
                    @classmethod
                    def permitted(cls, person, user, action):
                        # unpersisted instance (create)
                        if person and not person.id:
                            if user.is_staff:
                                return True
                            return False
                        # none or persisted instance (read, write, delete, etc)
                        if action in ['read', 'write']:
                            return Q(pk=user.pk)
                        return None
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

        Examples:
            Check permission::

                if person.permits(context.user, 'write'):
                    person.save()

            Check multiple permissions (logical OR)::

                if person.permits(context.user, ('read', 'write')):
                    person.save()
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
        qs = self.filter_permitted(user, actions, instance=self)
        return qs.filter(pk=self.pk).exists()


# manager ---------------------------------------------------------------------

class LocationCategoryManager(models.Manager):
    def get_by_natural_key(self, organization_name, location_category_name):
        return self.get(
            organization__name=organization_name,
            name=location_category_name)


class OperationManager(models.Manager):
    def get_by_natural_key(self, organization_name, project_name, operation_name):
        return self.get(
            project__organization__name=organization_name,
            project__name=project_name,
            name=operation_name)


class OrganizationManager(models.Manager):
    def get_by_natural_key(self, organization_name):
        return self.get(name=organization_name)


class PersonManager(UserManager):
    def get_by_natural_key(self, email):
        return self.get(email=email)


class PersonPropertyManager(models.Manager):
    def get_by_natural_key(self, organization_name, group_name, property_name):
        return self.get(
            group__organization__name=organization_name,
            group__name=group_name,
            name=property_name)


class PersonPropertyGroupManager(models.Manager):
    def get_by_natural_key(self, organization_name, group_name):
        return self.get(
            organization__name=organization_name,
            name=group_name)


class ProjectManager(models.Manager):
    def get_by_natural_key(self, organization_name, project_name):
        return self.get(
            organization__name=organization_name,
            name=project_name)


class RoleManager(models.Manager):
    def get_by_natural_key(self, organization_name, project_name, operation_name,
                           task_name, shift_start_time, role_title):
        if shift_start_time:
            return self.get(
                shift__task__operation__project__organization__name=organization_name,
                shift__task__operation__project__name=project_name,
                shift__task__operation__name=operation_name,
                shift__task__name=task_name,
                shift__start_time=shift_start_time,
                title=role_title)
        return self.get(
            shift__task__operation__project__organization__name=organization_name,
            shift__task__operation__project__name=project_name,
            shift__task__operation__name=operation_name,
            task__name=task_name,
            title=role_title)


class ShiftManager(models.Manager):
    def get_by_natural_key(self, organization_name, project_name, operation_name,
                           task_name, shift_start_time):
        return self.get(
            task__operation__project__organization__name=organization_name,
            task__operation__project__name=project_name,
            task__operation__name=operation_name,
            task__name=task_name,
            start_time=shift_start_time)


class TaskManager(models.Manager):
    def get_by_natural_key(self, organization_name, project_name, operation_name,
                           task_name):
        return self.get(
            operation__project__organization__name=organization_name,
            operation__project__name=project_name,
            operation__name=operation_name,
            name=task_name)


class TaskFieldManager(models.Manager):
    def get_by_natural_key(self, organization_name, task_field_name):
        return self.get(
            organization__name=organization_name,
            name=task_field_name)


# models ----------------------------------------------------------------------

class ACE(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    # *_cts list: list of valid models
    # checked in ForeignKey.limit_choices_to, Model.clean() and GQLFilterSet
    instance_cts = ['organization', 'project', 'operation']
    instance_ct = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': instance_cts},
    )
    instance_id = models.PositiveIntegerField()
    instance = GenericForeignKey(
        'instance_ct',
        'instance_id',
    )

    person = models.ForeignKey(
        to='Person',
        on_delete=models.CASCADE,
    )

    PERMISSIONS = [
        ('ADMIN', _('Admin')),
    ]
    permission = models.CharField(
        max_length=5,
        choices=PERMISSIONS,
    )

    class Meta:
        indexes = [
            models.Index(fields=["instance_ct", "instance_id"]),
        ]
        unique_together = ('instance_ct', 'instance_id', 'person', 'permission',)

    def clean(self):
        super().clean()

        # restrict foreign models of instance
        label = self.instance_ct.app_label
        model = self.instance_ct.model
        valid_models = {'georga': self.instance_cts}
        if label not in valid_models or model not in valid_models[label]:
            raise ValidationError(
                f"'{self.instance_ct.app_labeled_name}' is not a valid "
                "content type for ACE.instance")

        # restrict persons to have a true is_staff flag
        if not self.person.is_staff:
            raise ValidationError(f"person {self.person.gid} is not staff")

        # restrict persons to be employed by the organization
        organization = self.instance.organization
        valid_organizations = self.person.organizations_employed.all()
        if organization not in valid_organizations:
            raise ValidationError(
                f"person {self.person.gid} is not employed by organization "
                f"of instance {self.instance.gid}")

    # permissions
    @classmethod
    def permitted(cls, ace, user, action):
        if not user.is_staff:
            return False
        # unpersisted instances (create)
        if ace and not ace.id:
            match action:
                case 'create':
                    # ACEs for projects can be created by organization admins
                    if isinstance(ace.instance, Project):
                        return ace.instance.organization.id in user.admin_organization_ids
                    # ACEs for operations can be created by organization/project admins
                    if isinstance(ace.instance, Operation):
                        return ace.instance.project.id in user.admin_project_ids
                case _:
                    return False
        # queryset filtering and persisted instances (read, write, delete, etc)
        match action:
            case 'read':
                return reduce(or_, [
                    # ACEs for the user can be read by the user
                    Q(person=user),
                    # ACEs for organizations can be read by organization admins
                    Q(organization__in=user.admin_organization_ids),
                    # ACEs for projects can be read by organization/project admins
                    Q(project__in=user.admin_project_ids),
                    # ACEs for operations can be read by organization/project/operation admins
                    Q(operation__in=user.admin_operation_ids),
                ])
            case 'update':
                return reduce(or_, [
                    # ACEs for organizations can be updated by organization admins
                    Q(organization__in=user.admin_organization_ids),
                    # ACEs for projects can be updated by organization/project admins
                    Q(project__in=user.admin_project_ids),
                    # ACEs for operations can be updated by organization/project/operation admins
                    Q(operation__in=user.admin_operation_ids),
                ])
            case 'delete':
                return reduce(or_, [
                    # ACEs for projects can be deleted by organization admins
                    Q(project__organization__in=user.admin_organization_ids),
                    # ACEs for operations can be deleted by organization/project admins
                    Q(operation__project__in=user.admin_project_ids),
                ])
            case _:
                return None


class Device(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    person = models.ForeignKey(
        to='Person',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=50,
    )

    OS_TYPES = [
        ('ANDROID', _('Android')),
        ('IOS', _('iOS')),
        ('LINUX', _('Linux')),
        ('OTHER', _('Other')),
    ]
    os_type = models.CharField(
        max_length=7,
        choices=OS_TYPES,
    )
    os_version = models.CharField(
        max_length=35,
    )

    APP_TYPES = [
        ('MAUI', _('Maui')),
        ('REACT', _('React')),
    ]
    app_type = models.CharField(
        max_length=5,
        choices=APP_TYPES,
    )
    app_version = models.CharField(
        max_length=15,
    )
    APP_STORES = [
        ('GOOGLEPLAY', _('Google Play')),
        ('FDROID', _('F-Droid')),
        ('AMAZON', _('Amazon')),
    ]
    app_store = models.CharField(
        max_length=10,
        choices=APP_STORES,
    )

    PUSH_TOKEN_TYPES = [
        ('FCM', _('FCM')),
        ('NTFY', _('NTFY')),
        ('APN', _('APN')),
        ('ONESIGNAL', _('OneSignal')),
    ]
    push_token_type = models.CharField(
        max_length=9,
        choices=PUSH_TOKEN_TYPES,
    )
    push_token = models.CharField(  # TODO: verify schema for token type
        max_length=200,
    )

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _("client device")
        verbose_name_plural = _("client devices")
        # TODO: translation: Client-Gerät

    # permissions
    @classmethod
    def permitted(cls, device, user, action):
        # unpersisted instances (create)
        if device and not device.id:
            match action:
                case 'create':
                    # devices of the user can be created by the user
                    return device.person == user
                case _:
                    return False
        # queryset filtering and persisted instances (read, write, delete, etc)
        match action:
            case 'read':
                return reduce(or_, [
                    # devices of the user can be read by the user
                    Q(person=user),
                ])
            case 'update':
                return reduce(or_, [
                    # devices of the user can be updated by the user
                    Q(person=user),
                ])
            case 'delete':
                return reduce(or_, [
                    # devices of the user can be deleted by the user
                    Q(person=user),
                ])
            case _:
                return None


class Equipment(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=30,
        default='',
    )
    OWNER = [
        ('SELF', _('Person itself')),
        ('ORG', _('Provided by organization')),
        ('THIRDPARTY', _('Other party')),
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


class Location(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
    )
    category = models.ForeignKey(
        to='LocationCategory',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    is_template = models.BooleanField(
        default=False,
    )
    task = models.ForeignKey(  # if set: template for all subsequent shifts of the task
        to='Task',
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    shift = models.ForeignKey(  # if set: concrete location of a shift
        to='Shift',
        blank=True,
        null=True,
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

    class Meta:
        verbose_name = _("location")
        verbose_name_plural = _("locations")
        # TODO: translate: Ort

    def clean(self):
        super().clean()

        # template location must have a task
        if self.is_template and not self.task:
            raise ValidationError("template location must have a task")
        # non template location must have a shift
        if not self.is_template and not self.shift:
            raise ValidationError("non template location must have a shift")

    # permissions
    @classmethod
    def permitted(cls, location, user, action):
        # unpersisted instances (create)
        if location and not location.id:
            match action:
                case 'create':
                    # location templates can be created by organization staff
                    if location.is_template:
                        return location.task.operation in user.admin_operation_ids
                    # locations can be created by organization staff
                    return location.shift.task.operation in user.admin_operation_ids
                case _:
                    return False
        # queryset filtering and persisted instances (read, write, delete, etc)
        match action:
            case 'read':
                return reduce(or_, [
                    # locations can be read by employed users
                    Q(organization__in=user.organizations_employed.all()),
                    # locations can be read by subscribed users
                    Q(organization__in=user.organizations_subscribed.all()),
                ])
            case 'update':
                return reduce(or_, [
                    # location templates can be updated by organization staff
                    Q(is_template=True, task__operation__in=user.admin_operation_ids),
                    # locations can be updated by organization staff
                    Q(is_template=False, shift__task__operation__in=user.admin_operation_ids),
                ])
            case 'delete':
                return reduce(or_, [
                    # location templates can be deleted by organization staff
                    Q(is_template=True, task__operation__in=user.admin_operation_ids),
                    # locations can be deleted by organization staff
                    Q(is_template=False, shift__task__operation__in=user.admin_operation_ids),
                ])
            case _:
                return None


class LocationCategory(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    objects = LocationCategoryManager()

    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=50,
    )

    def natural_key(self):
        return self.organization.natural_key() + (self.name,)

    class Meta:
        verbose_name = _("location category")
        verbose_name_plural = _("location categories")
        # TODO: translate: Einsatzort-Kategorie
        # e.g. operation location

    # permissions
    @classmethod
    def permitted(cls, location_category, user, action):
        # unpersisted instances (create)
        if location_category and not location_category.id:
            match action:
                case 'create':
                    # location categories can be created by organization admins
                    return location_category.organization in user.admin_organization_ids
                case _:
                    return False
        # queryset filtering and persisted instances (read, write, delete, etc)
        match action:
            case 'read':
                return reduce(or_, [
                    # location categories can be read by employed users
                    Q(organization__in=user.organizations_employed.all()),
                    # location categories can be read by subscribed users
                    Q(organization__in=user.organizations_subscribed.all()),
                ])
            case 'update':
                return reduce(or_, [
                    # location categories can be updated by organization admins
                    Q(organization__in=user.admin_organization_ids),
                ])
            case 'delete':
                return reduce(or_, [
                    # location categories can be deleted by organization admins
                    Q(organization__in=user.admin_organization_ids),
                ])
            case _:
                return None


class PersonToObject(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
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


class Message(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    '''
    A Message is sent via different channels to registered persons.

    Priority: describes, how disruptive the message should be
    - Low: Non disruptive automated messages, filtered by default.
    - Normal: Decently disruptive automated and manual messages, default case.
    - Important: Moderately disruptive automated and manual messages,
        e.g. when shift has canceled or location has changed.
    - Urgent: Highly disruptive manual messages.

    Category:
    - News: Manually sent contents.
    - Alert: Triggered by the system by cronjobs based on analysis.
    - Activity: On change of objects, which are relevant to the persons
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
    PRIORITIES = [
        ('URGENT', _('Urgent')),
        ('IMPORTANT', _('Important')),
        ('NORMAL', _('Normal')),
        ('LOW', _('Low')),
    ]
    priority = models.CharField(
        max_length=9,
        choices=PRIORITIES,
        default='NORMAL',
    )
    CATEGORIES = [
        ('NEWS', _('News')),
        ('ALERT', _('Alert')),
        ('ACTIVITY', _('Activity')),
    ]
    category = models.CharField(
        max_length=8,
        choices=CATEGORIES,
        default='NEWS',
    )
    person_attributes = GenericRelation(
        PersonToObject,
        content_type_field='relation_object_ct',
        object_id_field='relation_object_id',
        related_query_name='message'
    )

    STATES = [
        ('DRAFT', _('Draft')),
        ('PUBLISHED', _('Published')),
        ('ARCHIVED', _('Archived')),
        ('DELETED', _('Deleted')),
    ]
    state = FSMField(
        max_length=9,
        choices=STATES,
        default='DRAFT',
    )

    # delivery
    DELIVERY_STATES = [
        ('NONE', _('None')),
        ('SCHEDULED', _('Scheduled')),
        ('SENT', _('Sent')),
        ('SUCCEEDED', _('Succeeded')),
        ('FAILED', _('Failed')),
    ]
    email_delivery = FSMField(
        max_length=9,
        choices=DELIVERY_STATES,
        default='NONE',
    )
    email_delivery_start = models.DateTimeField(
        null=True,
        blank=True,
    )
    email_delivery_end = models.DateTimeField(
        null=True,
        blank=True,
    )
    email_delivery_error = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    push_delivery = FSMField(
        max_length=9,
        choices=DELIVERY_STATES,
        default='NONE',
    )
    push_delivery_start = models.DateTimeField(
        null=True,
        blank=True,
    )
    push_delivery_end = models.DateTimeField(
        null=True,
        blank=True,
    )
    sms_delivery = FSMField(
        max_length=9,
        choices=DELIVERY_STATES,
        default='NONE',
    )
    push_delivery_start = models.DateTimeField(
        null=True,
        blank=True,
    )
    push_delivery_end = models.DateTimeField(
        null=True,
        blank=True,
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
    def delivery(self):
        """
        str (ERROR|SCHEDULED|SENT|SUCCESS|NONE): Returns the least
            optimal delivery state of all channels in the given order.
        """
        for state in ["ERROR", "SCHEDULED", "SENT", "SUCCESS"]:
            for channel_state in [self.email_delivery, self.push_delivery, self.sms_delivery]:
                if channel_state == state:
                    return state
        return "NONE"

    # state transitions
    @transition(state, 'DRAFT', 'PUBLISHED')
    def publish(self):
        # TODO: transition
        # TODO: create service/command for each channel, per user filtering
        #   via Person.channel_filters() should probably happen there
        self.schedule_email()
        self.schedule_push()
        self.schedule_sms()

    @transition(state, 'PUBLISHED', 'ARCHIVED')
    def archive(self):
        # TODO: transition
        pass

    @transition(state, '*', 'DELETED')
    def delete(self, *args, hard=False, **kwargs):
        # TODO: transition
        if hard:
            super().delete(*args, **kwargs)

    # email_delivery transitions
    @transition(email_delivery, 'NONE', 'SCHEDULED')
    def schedule_email(self):
        # TODO: transition
        pass

    @transition(email_delivery, 'SCHEDULED', 'NONE')
    def cancel_email(self):
        # TODO: transition
        pass

    @transition(email_delivery, 'SCHEDULED', 'SENT', on_error='FAILED')
    def send_email(self):
        # TODO: transition
        pass

    @transition(email_delivery, 'SENT', RETURN_VALUE('SENT', 'SUCCEEDED', 'FAILED'))
    def check_email(self):
        # TODO: transition
        if 'FEEDBACK':
            return 'SUCCEEDED' or 'FAILED'
        return 'SENT'

    @transition(email_delivery, 'FAILED', 'SENT', on_error='FAILED')
    def retry_email(self):
        # TODO: transition
        pass

    # push_delivery transitions
    @transition(push_delivery, 'NONE', 'SCHEDULED')
    def schedule_push(self):
        # TODO: transition
        pass

    @transition(push_delivery, 'SCHEDULED', 'NONE')
    def cancel_push(self):
        # TODO: transition
        pass

    @transition(push_delivery, 'SCHEDULED', 'SENT', on_error='FAILED')
    def send_push(self):
        # TODO: transition
        pass

    @transition(push_delivery, 'SENT', RETURN_VALUE('SENT', 'SUCCEEDED', 'FAILED'))
    def check_push(self):
        # TODO: transition
        if 'FEEDBACK':
            return 'SUCCEEDED' or 'FAILED'
        return 'SENT'

    @transition(push_delivery, 'FAILED', 'SENT', on_error='FAILED')
    def retry_push(self):
        # TODO: transition
        pass

    # sms_delivery transitions
    @transition(sms_delivery, 'NONE', 'SCHEDULED')
    def schedule_sms(self):
        # TODO: transition
        pass

    @transition(sms_delivery, 'SCHEDULED', 'NONE')
    def cancel_sms(self):
        # TODO: transition
        pass

    @transition(sms_delivery, 'SCHEDULED', 'SENT', on_error='FAILED')
    def send_sms(self):
        # TODO: transition
        pass

    @transition(sms_delivery, 'SENT', RETURN_VALUE('SENT', 'SUCCEEDED', 'FAILED'))
    def check_sms_delivery(self):
        # TODO: transition
        if 'FEEDBACK':
            return 'SUCCEEDED' or 'FAILED'
        return 'SENT'

    @transition(sms_delivery, 'FAILED', 'SENT', on_error='FAILED')
    def retry_sms(self):
        # TODO: transition
        pass


class MessageFilter(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    # *_cts list: list of valid models
    # checked in ForeignKey.limit_choices_to, Model.clean() and GQLFilterSet
    scope_cts = ['person', 'organization', 'project', 'operation', 'task', 'shift']
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

    person = models.ForeignKey(
        to='Person',
        on_delete=models.CASCADE,
    )

    CHANNELS = ['app', 'email', 'push', 'sms']
    FILTERS = [
        ('INHERITED', _('Inherited')),
        ('NONE', _('None')),
        *Message.PRIORITIES,
    ]
    app = models.CharField(
        max_length=9,
        choices=FILTERS,
        default='INHERITED',
    )
    email = models.CharField(
        max_length=9,
        choices=FILTERS,
        default='INHERITED',
    )
    push = models.CharField(
        max_length=9,
        choices=FILTERS,
        default='INHERITED',
    )
    sms = models.CharField(
        max_length=9,
        choices=FILTERS,
        default='INHERITED',
    )

    class Meta:
        indexes = [
            models.Index(fields=["scope_ct", "scope_id"]),
        ]
        unique_together = ('scope_ct', 'scope_id', 'person')

    def clean(self):
        super().clean()

        # restrict foreign models of scope
        label = self.scope_ct.app_label
        model = self.scope_ct.model
        valid_models = {'georga': self.scope_cts}
        if label not in valid_models or model not in valid_models[label]:
            raise ValidationError(
                f"'{self.scope_ct.app_labeled_name}' is not a valid "
                "content type for Filter.scope")

    @classmethod
    def channel_filters(cls, person, scope):
        """
        Returns merged channel filters for a scope.

        Queries the database for an ordered set of message filters of the
        person and the scope plus all the parent filters, if existant. Merges
        the default filter of the person down the hierarchy. Filters with the
        value INHERITED are ignored, other values override the last one picked.
        Missing objects behave like all channels on INHERITED.

        Args:
            scope (Person|Organization|Project|Operation|Task|Shift): Scope
                of MessageFilter.

        Returns:
            dict[str: str]: Dictionary of channels and filter level.

        Example::

            MessageFilter.channel_filters(person, task):

                | Person:       {'app': 'NORMAL',    'email': 'IMPORTANT'}
                | Organization: {'app': 'INHERITED', 'email': 'LOW'}
                | Project:      {'app': 'INHERITED', 'email': 'INHERITED'}
                | Operation:    {'app': 'INHERITED', 'email': 'INHERITED'}
                | Task:         {'app': 'INHERITED', 'email': 'NONE'}
                v Result:       {'app': 'NORMAL', '   email': 'NONE'}

            MessageFilter.channel_filters(person, operation):

                | Person:       {'app': 'NORMAL',    'email': 'IMPORTANT'}
                | Organization: {'app': 'INHERITED', 'email': 'LOW'}
                | Project:      {'app': 'INHERITED', 'email': 'INHERITED'}
                | Operation:    {'app': 'INHERITED', 'email': 'INHERITED'}
                v Result:       {'app': 'NORMAL', '   email': 'LOW'}
        """
        # prepare q objects to fetch relevant message filters
        q = Q(default=person)
        if isinstance(scope, Shift):
            q |= reduce(or_, [
                Q(shift=scope),
                Q(task=scope.task),
                Q(operation=scope.task.operation),
                Q(project=scope.task.operation.project),
                Q(organization=scope.task.operation.project.organization),
            ])
        elif isinstance(scope, Task):
            q |= reduce(or_, [
                Q(task=scope),
                Q(operation=scope.operation),
                Q(project=scope.operation.project),
                Q(organization=scope.operation.project.organization),
            ])
        elif isinstance(scope, Operation):
            q |= reduce(or_, [
                Q(operation=scope),
                Q(project=scope.project),
                Q(organization=scope.project.organization),
            ])
        elif isinstance(scope, Project):
            q |= reduce(or_, [
                Q(project=scope),
                Q(organization=scope.organization),
            ])
        elif isinstance(scope, Organization):
            q |= Q(organization=scope.organization)
        q &= Q(person=person)

        # fetch channel values from message filters, ensure hierarchical order
        scope_order = Case(*[  # ordered content ids for message filter hierarchy
            When(scope_ct=ContentType.objects.get(model=model).id, then=index)
            for index, model in enumerate(cls.scope_cts)
        ])
        channel_filters = list(
            cls.objects.filter(q).order_by(scope_order).values(*cls.CHANNELS))

        # merge and return channel filters (choose most specific level)
        result = channel_filters.pop(0)  # default filter of person
        for channel_filter in channel_filters:
            for channel, level in channel_filter.items():
                if level == "INHERITED":
                    continue
                result[channel] = level
        return result

    # permissions
    @classmethod
    def permitted(cls, message_filter, user, action):
        # unpersisted instances (create)
        if message_filter and not message_filter.id:
            match action:
                case 'create':
                    # MessageFilters for the user can be created by themself
                    return message_filter.person.id == user.id
                case _:
                    return False
        # queryset filtering and persisted instances (read, write, delete, etc)
        match action:
            case 'read' | 'update' | 'delete':
                return reduce(or_, [
                    # MessageFilters for the user can be read/updated/deleted by themself
                    Q(person=user),
                ])
            case _:
                return None


class Operation(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    objects = OperationManager()

    project = models.ForeignKey(
        to='Project',
        on_delete=models.CASCADE,
    )
    STATES = [
        ('DRAFT', _('Draft')),
        ('PUBLISHED', _('Published')),
        ('ARCHIVED', _('Archived')),
        ('DELETED', _('Deleted')),
    ]
    state = FSMField(
        max_length=9,
        choices=STATES,
        default='DRAFT',
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
        content_type_field='instance_ct',
        object_id_field='instance_id',
        related_query_name='operation'
    )
    messages = GenericRelation(
        Message,
        content_type_field='scope_ct',
        object_id_field='scope_id',
        related_query_name='operation'
    )
    message_filters = GenericRelation(
        MessageFilter,
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

    def natural_key(self):
        return self.project.natural_key() + (self.name,)

    class Meta:
        verbose_name = _("operation")
        verbose_name_plural = _("operations")
        # TODO: translate: Einsatz

    def channel_filters(self, person):
        return MessageFilter.channel_filters(person, self)

    @cached_property
    def organization(self):
        """Organisation(): Returns the Organization of the Operation."""
        return self.project.organization

    # state transitions
    @transition(state, 'DRAFT', 'PUBLISHED')
    def publish(self):
        # TODO: transition
        pass

    @transition(state, 'PUBLISHED', 'ARCHIVED')
    def archive(self):
        # TODO: transition
        pass

    @transition(state, '*', 'DELETED')
    def delete(self, *args, hard=False, **kwargs):
        # TODO: transition
        if hard:
            super().delete(*args, **kwargs)


class Organization(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    objects = OrganizationManager()

    STATES = [
        ('DRAFT', _('Draft')),
        ('PUBLISHED', _('Published')),
        ('ARCHIVED', _('Archived')),
        ('DELETED', _('Deleted')),
    ]
    state = FSMField(
        max_length=9,
        choices=STATES,
        default='DRAFT',
    )
    name = models.CharField(
        max_length=50,
    )
    icon = models.TextField(
        null=True,
        blank=True,
    )

    ace = GenericRelation(
        ACE,
        content_type_field='instance_ct',
        object_id_field='instance_id',
        related_query_name='organization'
    )
    messages = GenericRelation(
        Message,
        content_type_field='scope_ct',
        object_id_field='scope_id',
        related_query_name='organization'
    )
    message_filters = GenericRelation(
        MessageFilter,
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

    def natural_key(self):
        return (self.name,)

    class Meta:
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")
        # TODO: translation: Organisation

    @cached_property
    def organization(self):
        """
        Organisation(): Returns self. Added to ease the api for `ACL.instance`
        by being able to access acl.instance.organization for all content types.
        """
        return self

    def channel_filters(self, person):
        return MessageFilter.channel_filters(person, self)

    def subscribe(self, person):
        # TODO: track GPDR relevant consent
        # TODO: trigger mandatory non digital processes (forms to sign, etc)
        pass

    # state transitions
    @transition(state, 'DRAFT', 'PUBLISHED')
    def publish(self):
        # TODO: transition
        pass

    @transition(state, 'PUBLISHED', 'ARCHIVED')
    def archive(self):
        # TODO: transition
        pass

    @transition(state, '*', 'DELETED')
    def delete(self, *args, hard=False, **kwargs):
        # TODO: transition
        if hard:
            super().delete(*args, **kwargs)


class Participant(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    role = models.ForeignKey(
        to='Role',
        on_delete=models.CASCADE,
    )
    person = models.ForeignKey(
        to='Person',
        on_delete=models.CASCADE,
    )

    ACCEPTANCE_STATES = [
        ('ACCEPTED', _('Accepted')),
        ('DECLINED', _('Declined')),
        ('PENDING', _('Pending')),
    ]
    acceptance = FSMField(
        max_length=8,
        choices=ACCEPTANCE_STATES,
        default='PENDING',
    )
    ADMIN_ACCEPTANCE_STATES = ACCEPTANCE_STATES + [
        ('NONE', _('None')),
    ]
    admin_acceptance = FSMField(
        max_length=8,
        choices=ADMIN_ACCEPTANCE_STATES,
        default='NONE',
    )
    admin_acceptance_user = models.ForeignKey(
        to='Person',
        on_delete=models.SET_NULL,
        related_name='participants_decided',
        blank=True,
        null=True,
    )

    # acceptance transitions
    @transition(acceptance, '+', 'ACCEPTED')
    def accept(self):
        # TODO: transition
        pass

    @transition(acceptance, '+', 'DECLINED')
    def decline(self):
        # TODO: transition
        pass

    @transition(acceptance, '+', 'PENDING')
    def reinquire(self):
        # TODO: transition
        pass

    # admin_acceptance transitions
    def has_accepted(self):
        return self.acceptance == 'ACCEPTED'

    @transition(admin_acceptance, '+', 'ACCEPTED', conditions=[has_accepted])
    def confirm(self):
        # TODO: transition
        pass

    @transition(admin_acceptance, '+', 'DECLINED', conditions=[has_accepted])
    def refuse(self):
        # TODO: transition
        pass


class Person(MixinTimestamps, MixinUUIDs, MixinAuthorization, AbstractUser):
    objects = PersonManager()

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
        ('UNDEFINED', _("Undefined")),
        ('ABSOLUTE', _("Absolute")),
        ('NOTONLY', _("Not only")),
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

    activity_radius_km = models.IntegerField(
        default=0,
        null=True,
        blank=True,
        verbose_name=_("agreement to activity radius in km"),
    )

    organizations_subscribed = models.ManyToManyField(  # TODO: PersonToObject?
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

    resources_provided = models.ManyToManyField(
        to='Resource',
        blank=True,
        verbose_name=_("resources provided")
    )

    default_message_filter = GenericRelation(
        MessageFilter,
        content_type_field='scope_ct',
        object_id_field='scope_id',
        related_query_name='default'
    )

    def __name__(self):
        return self.email

    def __str__(self):
        return self.email

    def natural_key(self):
        return (self.email,)

    def set_password(self, raw_password):
        super().set_password(raw_password)
        self.password_modified = timezone.now()

    class Meta:
        verbose_name = _("registered helper")
        verbose_name_plural = _("registered helpers")
        # TODO: translation: Registrierter Helfer

    def save(self, *args, **kwargs):
        if not self.id:
            # TODO: create default MessageFilter
            pass
        super().save(*args, **kwargs)

    def channel_filters(self, scope):
        return MessageFilter.channel_filters(self, scope)

    ADMIN_LEVELS = [  # neccessary for graphene enum field
        ('NONE', _('None')),
        ('ORGANIZATION', _("Organization")),
        ('PROJECT', _("Project")),
        ('OPERATION', _('Operation')),
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
            if ace.permission != "ADMIN":
                continue
            if isinstance(ace.instance, Organization):
                return "ORGANIZATION"
            if isinstance(ace.instance, Project):
                level = "PROJECT"
            if level != "PROJECT" and isinstance(ace.instance, Operation):
                level = "OPERATION"
        return level

    @cached_property
    def admin_organization_ids(self):
        """
        list[int]: Cached list of organization ids, for which the user has
            ADMIN rights. Used to minimize db load for permission requests.
        """
        return list(Organization.objects.filter(
            # user is admin for organizations
            Q(ace__person=self.id, ace__permission="ADMIN")
        ).values_list('id', flat=True))

    @cached_property
    def admin_project_ids(self):
        """
        list[int]: Cached list of project ids, for which the user has
            ADMIN rights. Used to minimize db load for permission requests.
        """
        return list(Project.objects.filter(
            # user is admin for project.organizations
            Q(organization__ace__person=self.id,
              organization__ace__permission="ADMIN")
            # user is admin for projects
            | Q(ace__person=self.id, ace__permission="ADMIN")
        ).values_list('id', flat=True))

    @cached_property
    def admin_operation_ids(self):
        """
        list[int]: Cached list of operation ids, for which the user has
            ADMIN rights. Used to minimize db load for permission requests.
        """
        return list(Operation.objects.filter(
            # user is admin for operation.project.organizations
            Q(project__organization__ace__person=self.id,
              project__organization__ace__permission="ADMIN")
            # user is admin for operation.projects
            | Q(project__ace__person=self.id, project__ace__permission="ADMIN")
            # user is admin for projects
            | Q(ace__person=self.id, ace__permission="ADMIN")
        ).values_list('id', flat=True))

    # permissions
    @classmethod
    def permitted(cls, person, user, action):
        # unpersisted instances (create)
        if person and not person.id:
            match action:
                case _:
                    return False
        # queryset filtering and persisted instances (read, write, delete, etc)
        match action:
            case 'read' | 'write':
                # users can read and edit themself
                return Q(pk=user.pk)
            case _:
                return None


class PersonProperty(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    objects = PersonPropertyManager()

    group = models.ForeignKey(
        to='PersonPropertyGroup',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    def natural_key(self):
        return self.group.natural_key() + (self.name,)

    class Meta:
        verbose_name = _("person property")
        verbose_name_plural = _("person properties")
        # TODO: translate: PersonProperty


class PersonPropertyGroup(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    objects = PersonPropertyGroupManager()

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
        ('MULTISELECT', _('multiple choice')),
        ('SINGLESELECT', _('single choice')),
    ]

    selection_type = models.CharField(
        max_length=12,
        choices=SELECTION_TYPES,
        default='MULTISELECT',
        verbose_name=_("selection type"),
    )
    NECESSITIES = [
        ('MANDATORY', _("Mandatory")),
        ('RECOMMENDED', _("Recommended")),
        ('UNRECOMMENDED', _("Unrecommended")),
        ('IMPOSSIBLE', _("Impossible")),  # TODO: translate: ausgeschlossen
    ]
    necessity = models.CharField(
        max_length=13,
        choices=NECESSITIES,
        default="RECOMMENDED",
        verbose_name=_("necessity"),
        # TODO: translate: "Erforderlichkeit"
    )

    def __str__(self):
        return '%s' % self.name

    def __unicode__(self):
        return '%s' % self.name

    def natural_key(self):
        return self.organization.natural_key() + (self.name,)

    class Meta:
        verbose_name = _("group of person properties")
        verbose_name_plural = _("groups of person properties")
        # TODO: translate: PersonPropertyGroup


class Project(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    objects = ProjectManager()

    organization = models.ForeignKey(
        to='Organization',
        on_delete=models.CASCADE,
    )
    STATES = [
        ('DRAFT', _('Draft')),
        ('PUBLISHED', _('Published')),
        ('ARCHIVED', _('Archived')),
        ('DELETED', _('Deleted')),
    ]
    state = FSMField(
        max_length=9,
        choices=STATES,
        default='DRAFT',
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
        content_type_field='instance_ct',
        object_id_field='instance_id',
        related_query_name='project'
    )
    messages = GenericRelation(
        Message,
        content_type_field='scope_ct',
        object_id_field='scope_id',
        related_query_name='project'
    )
    message_filters = GenericRelation(
        MessageFilter,
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

    def natural_key(self):
        return self.organization.natural_key() + (self.name,)

    class Meta:
        verbose_name = _("project")
        verbose_name_plural = _("projects")
        # TODO: translation: Projekt

    def channel_filters(self, person):
        return MessageFilter.channel_filters(person, self)

    # state transitions
    @transition(state, 'DRAFT', 'PUBLISHED')
    def publish(self):
        # TODO: transition
        pass

    @transition(state, 'PUBLISHED', 'ARCHIVED')
    def archive(self):
        # TODO: transition
        pass

    @transition(state, '*', 'DELETED')
    def delete(self, *args, hard=False, **kwargs):
        # TODO: transition
        if hard:
            super().delete(*args, **kwargs)


class Resource(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
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
        verbose_name=_("amount of resources desirable with this role"),
        default=1,
    )

    def __str__(self):
        return '%s' % self.description

    class Meta:
        verbose_name = _("resource")
        verbose_name_plural = _("resources")
        # TODO: translation: Ressource


class Role(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    objects = RoleManager()

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
    quantity = models.PositiveIntegerField()
    is_active = models.BooleanField(
        default=True,
    )
    is_template = models.BooleanField(
        default=False,
    )
    needs_admin_acceptance = models.BooleanField(
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

    def natural_key(self):
        if self.is_template:
            return self.task.natural_key() + (None, self.title)
        return self.shift.natural_key() + (self.title,)

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        # TODO: translate: Einsatzrolle

    @cached_property
    def organization(self):
        """Organisation(): Returns the Organization of the Role."""
        return self.shift.task.operation.project.organization


class RoleSpecification(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    role = models.ForeignKey(
        to='Role',
        on_delete=models.CASCADE,
    )
    person_properties = models.ManyToManyField(
        to='PersonProperty',
        blank=True,
        related_name='person_properties',
    )
    necessity = models.CharField(
        max_length=13,
        choices=PersonPropertyGroup.NECESSITIES,
        verbose_name=_("necessity"),
        # TODO: translate: "Erforderlichkeit"
    )


class Shift(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    objects = ShiftManager()

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    STATES = [
        ('DRAFT', _('Draft')),
        ('PUBLISHED', _('Published')),
        ('FINISHED', _('Finished')),
        ('CANCELED', _('Canceled')),
        ('ARCHIVED', _('Archived')),
        ('DELETED', _('Deleted')),
    ]
    state = FSMField(
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
    message_filters = GenericRelation(
        MessageFilter,
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

    def natural_key(self):
        return self.task.natural_key() + (self.start_time,)

    class Meta:
        verbose_name = _("shift")
        verbose_name_plural = _("shifts")
        # TODO: translate: Schicht

    def channel_filters(self, person):
        return MessageFilter.channel_filters(person, self)

    @cached_property
    def organization(self):
        """Organisation(): Returns the Organization of the Shift."""
        return self.task.operation.project.organization

    # state transitions
    @transition(state, 'DRAFT', 'PUBLISHED')
    def publish(self):
        # TODO: transition
        pass

    @transition(state, 'PUBLISHED', 'FINISHED')
    def finish(self):
        # TODO: transition
        pass

    @transition(state, 'PUBLISHED', 'CANCELED')
    def cancel(self):
        # TODO: transition
        pass

    @transition(state, ['PUBLISHED', 'FINISHED', 'CANCELLED'], 'ARCHIVED')
    def archive(self):
        # TODO: transition
        pass

    @transition(state, '*', 'DELETED')
    def delete(self, *args, hard=False, **kwargs):
        # TODO: transition
        if hard:
            super().delete(*args, **kwargs)


class Task(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    objects = TaskManager()

    operation = models.ForeignKey(
        to='Operation',
        on_delete=models.CASCADE,
    )
    field = models.ForeignKey(
        to='TaskField',
        on_delete=models.CASCADE,
    )
    STATES = [
        ('DRAFT', _('Draft')),
        ('PUBLISHED', _('Published')),
        ('ARCHIVED', _('Archived')),
        ('DELETED', _('Deleted')),
    ]
    state = FSMField(
        max_length=9,
        choices=STATES,
        default='DRAFT',
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

    messages = GenericRelation(
        Message,
        content_type_field='scope_ct',
        object_id_field='scope_id',
        related_query_name='task'
    )
    message_filters = GenericRelation(
        MessageFilter,
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
        return '%s' % self.name

    def natural_key(self):
        return self.operation.natural_key() + (self.name,)

    class Meta:
        verbose_name = _("task")
        verbose_name_plural = _("tasks")
        # TODO: translate: Aufgabe

    def channel_filters(self, person):
        return MessageFilter.channel_filters(person, self)

    @cached_property
    def organization(self):
        """Organisation(): Returns the Organization of the Task."""
        return self.operation.project.organization

    # state transitions
    @transition(state, 'DRAFT', 'PUBLISHED')
    def publish(self):
        # TODO: transition
        pass

    @transition(state, 'PUBLISHED', 'ARCHIVED')
    def archive(self):
        # TODO: transition
        pass

    @transition(state, '*', 'DELETED')
    def delete(self, *args, hard=False, **kwargs):
        # TODO: transition
        if hard:
            super().delete(*args, **kwargs)


class TaskField(MixinTimestamps, MixinUUIDs, MixinAuthorization, models.Model):
    objects = TaskFieldManager()

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

    def natural_key(self):
        return self.organization.natural_key() + (self.name,)

    class Meta:
        verbose_name = _("task field")
        verbose_name_plural = _("task fields")
        # TODO: translate: Aufgabentyp
