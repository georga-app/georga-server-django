import logging
from functools import wraps

from django.db.models import Model
from django.db.models.query import QuerySet
from django.db.models.manager import Manager
from django.forms import ModelForm

import jwt
from graphql_jwt import exceptions
from graphql_jwt.compat import GraphQLResolveInfo
from graphql_jwt.middleware import allow_any

from . import settings

logger = logging.getLogger(__name__)


# Authentication --------------------------------------------------------------

# override allow_any, see https://stackoverflow.com/a/71296685
def handled_allow_any(info, **kwargs):
    try:
        return allow_any(info, **kwargs)
    except AttributeError:
        return False


def jwt_encode(payload):
    return jwt.encode(
        payload, settings.GRAPHQL_JWT['JWT_PRIVATE_KEY'], algorithm="RS256")


def jwt_decode(token):
    return jwt.decode(
        token, settings.GRAPHQL_JWT['JWT_PUBLIC_KEY'], algorithms=["RS256"])


# Authorization ---------------------------------------------------------------

def info(f):
    """
    Decorator to search args for resolveinfo and inject it as first parameter.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            info = next(arg for arg in args if isinstance(arg, GraphQLResolveInfo))
            return func(info, *args, **kwargs)
        return wrapper
    return decorator


def object_permits_user(*actions, exc=exceptions.PermissionDenied):
    """
    Decorator for instance level access control in django graphql objects.

    Depending on which function is decorated, it may:
    - filter querysets
      (`DjangoObjectType.get_queryset()`)
    - restrict instance access
      (`DjangoObjectType.get_node()`)
    - restrict instance field access
      (`DjangoObjectType.resolve_<field>()`)
    - restrict instance mutations with persisted instance
      (`DjangoModelFormMutation.get_form_kwargs()`)
    - restrict instance mutations with unpersisted instance
      (`DjangoModelFormMutation.perform_mutate()`)

    For convenience, the decorator may be used via `Meta.permissions` attributes:
    - `UUIDDjangoObjectType.Meta.permissions`
      (restrict intance access & filter querysets)
    - `UUIDDjangoModelFormMutation.Meta.permissions`
      (restrict instance mutations with persisted or unpersisted instance)

    Args:
        *actions (tuple[str]): Action or tuple of actions, one of which the
            user is required to have (logical OR, if multiple are given).
            Actions may be arbitrary strings, e.G. CRUD operations.
        exc (Exception, optional): Exception to raise on denial. Defaults to
            `graphql_jwt.exceptions.PermissionDenied`.

    Returns:
        The decorated function.

    Raises:
        The exception `exc` of the Args: If access was denied. Querysets will
            be filtered silently.

    Note:
        Permission is granted/denied based on the result of the
        `MixinAuthorization` methods `permits()` for access
        restrictions and `filter_permitted()` for queryset filtering.
        Using this decorator requires all inquired models to inherit from
        `MixinAuthorization` and to override `permitted()` to porperly handle
        the inquired actions. For more deatils see the docstrings of the Mixin.

    Examples:
        Filter querysets::

            class SomeModelType(DjangoObjectType):
                @classmethod
                @object_permits_user('read')
                def get_queryset(cls, queryset, info):
                    return super().get_queryset(queryset, info)

        Restrict instance access (read OR other)::

            class SomeModelType(DjangoObjectType):
                @classmethod
                @object_permits_user('read', 'other')
                def get_node(cls, info, id):
                    return super().get_node(info, id)

        Restrict instance field access (read AND other)::

            class SomeModelType(DjangoObjectType):
                @object_permits_user('read')
                @object_permits_user('other')
                def resolve_some_field(self, info):
                    return self.some_field

        Restrict instance access & filter querysets via permission attribute::

            class SomeModelType(UUIDDjangoObjectType):
                class Meta:
                    permissions = [object_permits_user('read')]

        Restrict instance mutations with persisted instance::

            class UpdateSomeModelMutation(DjangoModelFormMutation):
                @classmethod
                @object_permits_user('write')
                def get_form_kwargs(cls, root, info, **input)
                    return super().get_form_kwargs(root, info, **input)

        Restrict instance mutations with unpersisted instance::

            class UpdateSomeModelMutation(DjangoModelFormMutation):
                @classmethod
                @object_permits_user('create')
                def perform_mutate(cls, form, info)
                    return super().perform_mutate(form, info)

        Restrict instance mutation for unpersisted or persited instances
        via permission attribute::

            class CreateSomeModelMutation(UUIDDjangoModelFormMutation):
                class Meta:
                    permissions = [object_permits_user('create')]

            class UpdateSomeModelMutation(UUIDDjangoModelFormMutation):
                class Meta:
                    permissions = [object_permits_user('write')]
    """
    # allow only tuple of strings
    assert isinstance(actions, tuple), f"Error: actions {actions} is not a tuple."
    for action in actions:
        assert isinstance(action, str), f"Error: action {action} is not a string."

    def decorator(func):
        @wraps(func)
        @info(func)
        def wrapper(info, *args, **kwargs):
            # access Mutation (without instance: create)
            if info.parent_type.name == 'MutationType':
                # func: DjangoModelFormMutation.perform_mutate()
                # args: cls, form, info
                form = next(iter(args), None)
                if isinstance(form, ModelForm):
                    if form.instance.permits(info.context.user, actions):
                        return func(*args, **kwargs)
                    raise exc

            # get return value from func
            obj = func(*args, **kwargs)

            # access Mutation (with instance: read, write, delete, etc)
            if info.parent_type.name == 'MutationType':
                # func: DjangoModelFormMutation.get_form_kwargs()
                # obj: dict with form kwargs
                # args: cls, root, info, **input
                if 'instance' not in obj:  # create has no instance, catched above
                    return obj
                if obj['instance'].permits(info.context.user, actions):
                    return obj

            # filter QuerySets
            elif isinstance(obj, (Manager, QuerySet)):
                # func: DjangoObjectType.get_queryset()
                # obj: QuerySet instance
                # args: queryset, info
                try:
                    return obj.model.filter_permitted(info.context.user, actions, obj)
                except AssertionError as e:
                    logger.error(e)
                    return obj.none()
                # TODO: restrict exception to valid subclasses
                except Exception as e:
                    logger.error(e)
                    return obj.none()

            # access ObjectTypes
            elif isinstance(obj, Model):
                # func: DjangoObjectType.get_node()
                # obj: Model instance
                # args: cls, info, id
                if obj.permits(info.context.user, actions):
                    return obj

            # access Scalars (ask parent object)
            elif isinstance(next(iter(args), None), Model):
                # func: DjangoObjectType.resolve_<field>()
                # obj: graphene Field
                # args: parent, info
                if args[0].permits(info.context.user, actions):
                    return obj

            # raise exception otherwise
            raise exc

        return wrapper
    return decorator
