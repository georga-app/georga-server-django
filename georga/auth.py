import logging
from functools import wraps

from django.db.models import Model
from django.db.models.query import QuerySet
from django.db.models.manager import Manager

import jwt
from graphql_jwt import exceptions
from graphql_jwt.compat import GraphQLResolveInfo
from graphql_jwt.middleware import allow_any

from . import settings

logger = logging.getLogger(__name__)


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


def object_permits_user(*access_strings, exc=exceptions.PermissionDenied):
    """
    Decorator for instance level access control in django graphql objects.

    According to permissions it may:
    - filter querysets after `DjangoObjectType.get_queryset()`
    - restrict access to mutations after `DjangoModelFormMutation.get_form_kwargs()`
    - restrict access to instances after `DjangoObjectType.get_node()`
    - restrict access to fields of instances after `DjangoObjectType.resolve_<field>()`

    Permission is granted/denied based on a model instance, an user instance
    and access_strings passed to methods defined in `georga.models.MixinAuthorization`.
    Requires all inquired models to implement this mixin.

    Denial on direct access will throw the customizable `exc` Exception.
    Connections will be filtered silently.

    Usage:

        class SomeModelType(UUIDDjangoObjectType):

            # restrict object access & filter querysets
            # note: works due to adjustments in UUIDDjangoObjectType subclass
            class Meta:
                permissions = [object_permits_user('ADMIN')]

            # restrict object access
            @classmethod
            @object_permits_user('ADMIN', 'OR_some_other_access_string')
            def get_node(cls, info, id):
                return super().get_node(info, id)

            # filter querysets
            @classmethod
            @object_permits_user('ADMIN')
            @object_permits_user('AND_some_other_access_string')
            def get_queryset(cls, queryset, info):
                return super().get_queryset(queryset, info)

            # restrict field access
            @object_permits_user('ADMIN')
            def resolve_some_field(self, info):
                return self.some_field

        # restrict object mutation
        # note: works due to adjustments in UUIDDjangoModelFormMutation subclass
        class UpdateSomeModelMutation(UUIDDjangoModelFormMutation):
            class Meta:
                permissions = [object_permits_user('ADMIN')]
    """
    # allow only tuple of strings
    assert isinstance(access_strings, tuple), (
        f"Error: access_strings {access_strings} is not a tuple."
    )
    for access_string in access_strings:
        assert isinstance(access_string, str), (
            f"Error: access string {access_string} is not a string."
        )

    def decorator(func):
        @wraps(func)
        @info(func)
        def wrapper(info, *args, **kwargs):
            obj = func(*args, **kwargs)

            # access Mutation
            if info.parent_type.name == 'Mutation':
                if obj['instance'].permits(info.context.user, access_strings):
                    return obj

            # filter QuerySets
            elif isinstance(obj, (Manager, QuerySet)):
                try:
                    return obj.model.filter_permitted(obj, info.context.user, access_strings)
                except AssertionError as e:
                    logger.error(e)
                    return obj.none()
                # TODO: restrict exception to valid subclasses
                except Exception as e:
                    logger.error(e)
                    return obj.none()

            # access ObjectTypes
            elif isinstance(obj, Model):
                if obj.permits(info.context.user, access_strings):
                    return obj

            # access Scalars (ask parent object)
            elif isinstance(next(iter(args), None), Model):
                if args[0].permits(info.context.user, access_strings):
                    return obj

            # raise exception otherwise
            raise exc

        return wrapper
    return decorator
