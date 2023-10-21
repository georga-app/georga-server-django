from os import listdir
from os.path import isfile, join
from unittest import SkipTest
from functools import wraps
from datetime import datetime

from graphql import parse
from graphql_jwt.exceptions import JSONWebTokenError
from graphql_jwt.settings import jwt_settings
from graphql_jwt.shortcuts import get_token
from graphql_jwt.testcases import JSONWebTokenTestCase, JSONWebTokenClient
from graphql_relay.utils import base64
from graphene.utils.str_converters import to_snake_case, to_camel_case
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from graphene_django.registry import get_global_registry

from ...models import MixinAuthorization, Person
from ...schemas import schema


# configuration variables
SUPERADMIN_USER = "admin@georga.test"  # email of superadmin user
INACTIVE_USER = "inactive@georga.test"  # email of inactive user
FIXTURES_DIR = join("georga", "fixtures")  # fixtures directory
DEFAULT_BATCH_SIZE = 10  # number of entries tested, 0 = all

# shared query variables (relay node interface, MixinTimestamps)
VARIABLES = """
        $id: ID
        $offset: Int
        $before: String
        $after: String
        $first: Int
        $last: Int
        $createdAt: DateTime
        $createdAt_Gt: DateTime
        $createdAt_Lte: DateTime
        $modifiedAt: DateTime
        $modifiedAt_Gt: DateTime
        $modifiedAt_Lte: DateTime
"""
# shared query arguments (relay node interface, MixinTimestamps)
ARGUMENTS = """
            id: $id
            offset: $offset
            before: $before
            after: $after
            first: $first
            last: $last
            createdAt: $createdAt
            createdAt_Gt: $createdAt_Gt
            createdAt_Lte: $createdAt_Lte
            modifiedAt: $modifiedAt
            modifiedAt_Gt: $modifiedAt_Gt
            modifiedAt_Lte: $modifiedAt_Lte
"""
# shared query result fields (relay node interface)
PAGEINFO = """
            pageInfo {
                hasNextPage
                hasPreviousPage
                startCursor
                endCursor
            }
"""


# jwt -------------------------------------------------------------------------

TOKEN_CACHE = {}  # cache for authentication tokens


class CachedJSONWebTokenClient(JSONWebTokenClient):
    """JSONWebTokenClient with cached tokens, requested only once per run."""
    def authenticate(self, user):
        if isinstance(user, str):
            user = Person.objects.get(email=user)
        if user.email not in TOKEN_CACHE:
            TOKEN_CACHE[user.email] = get_token(user)
        self._credentials = {
            jwt_settings.JWT_AUTH_HEADER_NAME: (
                f"{jwt_settings.JWT_AUTH_HEADER_PREFIX} {TOKEN_CACHE[user.email]}"
            ),
        }


def auth(user, actions=None, permitted=None):
    """
    Decorator to authenticate a user before the graphql operation is executed.

    Args:
        user (georga.models.Person()|str): Person instance or email adress.
        actions (tuple[str]|str, optional): Action or tuple of actions. Used
            to filter the queryset in `self.entries` to match the expected
            graphql results.
        permitted (Function|True|False|None, optional): Function to override
            the model method `permitted()` with. If True/False, an function is
            used, that always returns True/False. Used to bypass permissions.

    Returns:
        The decorated function.
    """
    _actions = actions
    if permitted in [True, False]:
        def _permitted(*args, **kwargs):
            return permitted
        if not _actions:
            _actions = r"¯\_(ツ)_/¯"
    else:
        _permitted = permitted
    permission_override = callable(_permitted)

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # set and authenticate user
            self.user = user
            if isinstance(self.user, str):
                self.user = Person.objects.get(email=self.user)
            self.client.authenticate(self.user)
            # override permissions
            if permission_override:
                self._permitted = self.model.permitted
                setattr(self.model, 'permitted', _permitted)
            # fetch database entries for user
            self.entries = self.model.objects
            if self.user and _actions:
                self.entries = self.model.filter_permitted(self.user, _actions)
            self.entries = self.entries.all()
            # execute test
            func(self, *args, **kwargs)
            # reset entries
            self.entries = None
            # reset permissions
            if permission_override:
                self.model.permitted = self._permitted
                self._permitted = None
            # reset and logout user
            self.user = None
            self.client.logout()
        return wrapper
    return decorator


# schema ----------------------------------------------------------------------

GRAPHENE_DJANGO_REGISTRY = get_global_registry()


class SchemaTestCaseMetaclass(type):
    """
    Metaclass for schema tests.

    Skips tests if class attribute __test__ is False.
    Fetches some variables for easy access within the tests.
    Inserts common relay default values into the operation string.
    """
    def __new__(cls, name, bases, dct):
        # save tests to attribute _inherited_tests if __test__ is False
        if dct.pop('__test__', None) is False:
            dct['_inherited_tests'] = {}
            for test in [k for k in dct if k.startswith('test_')]:
                dct['_inherited_tests'][f'{test}'] = dct.pop(test)
            return super().__new__(cls, name, bases, dct)
        # add tests from _inherited_tests for non base classes
        new = super().__new__(cls, name, bases, dct)
        for attr, test in getattr(new, '_inherited_tests', {}).items():
            setattr(new, attr, test)
        # substitute operation variables and assign variables
        if new.operation:
            # substitue operation variables
            operation = new.operation.replace("[VARIABLES]", VARIABLES)
            operation = operation.replace("[ARGUMENTS]", ARGUMENTS)
            operation = operation.replace("[PAGEINFO]", PAGEINFO)
            # fetch variables
            document = parse(operation)
            definition = document.definitions[0]
            operation_type = definition.operation
            operation_ast = definition.selection_set.selections[0]
            operation_name = operation_ast.name.value
            operation_args = [item.name.value for item in operation_ast.arguments]
            root = schema.graphql_schema.get_type(f"{operation_type.value.capitalize()}Type")
            field = root.fields[operation_name]
            graphene_type_name = field.type.name.removesuffix('Connection')
            graphene_type = schema.graphql_schema.get_type(graphene_type_name).graphene_type
            permission = getattr(graphene_type._meta.class_type, 'permission', [])
            model = graphene_type._meta.model
            # assign variables
            new.field = field
            new.model = model
            new.operation = operation
            new.operation_type = operation_type
            new.operation_ast = operation_ast
            new.operation_name = operation_name
            new.operation_args = operation_args
            new.graphene_type = graphene_type
            new.permission = permission
        return new


class SchemaTestCase(JSONWebTokenTestCase, metaclass=SchemaTestCaseMetaclass):
    """
    Base class for schema tests.

    Formats the test output.

    Attrs:
        client_class (django.test.Client): The class for the client, which
            executes the graphql operation.
        fixtures (list[str]): List of fixture filenames to load.
        operation (str): The query, mutation or subscription string to execute.
            The strings `[VARIABLES]`, `[ARGUMENTS]` and `[PAGEINFO]` are
            substituted in the metaclass with the relay default values for the
            variables, fields or pageinfo.

    Attrs set in metaclass:
        field (graphene.Field()): Query, Mutation or Subscription field to test.
        model (django.models.Model()): Model, on which the operation operates.
        operation_type (str): query|mutation|subscription.
        operation_name (str): Name of the operation.
        operation_ast (graphql.language.ast.Field()): Parsed operation.
        operation_args (list[str]): List of filter args in parsed operation.
        graphene_type (obj): Graphene type of the model.
        permission (list[func]): List of permission decorators for graphene type.

    Attrs set in `@auth()` decorator:
        user (georga.models.Person()): The user, which is authenticated for
            the graphql operation.
        entries (django.models.query.QuerySet()): The queryset, on which the
            operation result is based on.
    """
    client_class = CachedJSONWebTokenClient
    fixtures = sorted([f for f in listdir(FIXTURES_DIR) if isfile(join(FIXTURES_DIR, f))])

    # mandatory attributes to override on inheritance
    operation = None

    # derived in metaclass
    field = None
    model = None
    operation_type = None
    operation_name = None
    operation_ast = None
    operation_args = None
    graphene_type = None
    permission = []

    # set in @auth()
    user = None
    entries = None

    def shortDescription(self):
        return False

    def __str__(self):
        # Schemas|Models|...
        module = "Schema"
        # schema operation name, e.g. listPersons|listAces|...
        operation = self.operation_name
        # test method name
        name = self._testMethodName
        # test method docstring
        description = super().shortDescription() or self._testMethodName
        return f"{module} | {operation} | {name} | {description}"

    def assertEntryEqual(self, entry, dictionary, test='assertEntryEqual'):
        """Asserts equality of a dict (e.g. query result) to django model instance fields."""
        for field in self.walk(dictionary, entry):
            with self.subTest(subtest=test, **field):
                self.assertEqual(field['dict_value'], field['database_value'])

    @staticmethod
    def walk(node, entry, path=''):
        """Traverses a dict (e.g. query result), yields api/database values to compare."""
        for key, item in node.items():
            subpath = f"{path}.{key}"
            match key:
                case "__typename":
                    _type = GRAPHENE_DJANGO_REGISTRY.get_type_for_model(entry._meta.model)
                    database_value = _type._meta.name
                case key if key.startswith("__"):
                    continue
                case "edges":
                    item = [edge["node"] for edge in item]
                    database_value = entry.all()
                case _:
                    database_value = getattr(entry, to_snake_case(key))
            if isinstance(item, dict):
                yield from SchemaTestCase.walk(item, database_value, path=subpath)
            elif isinstance(item, list):
                for index, _ in enumerate(item):
                    yield from SchemaTestCase.walk(
                        item[index], database_value[index], path=f"{subpath}.{index}")
            else:
                # id
                if key == "id":
                    database_value = entry.gid
                # model fields
                if isinstance(database_value, models.Model):
                    database_value = database_value.gid
                # datetime fields
                if isinstance(database_value, datetime):
                    database_value = database_value.isoformat()
                yield {
                    'dict_value': item,
                    'database_value': database_value,
                    'path': subpath.removeprefix(".")
                }


# query -----------------------------------------------------------------------

class QueryTestCaseMetaclass(SchemaTestCaseMetaclass):
    """Adds fields and filter tests for the provided query."""

    # TODO:
    # - wrong id filter (empty string, wrong padding, wrong model, not permitted)

    filters_skipped = ['first', 'last', 'offset', 'before', 'after']

    def __new__(cls, name, bases, dct):
        new = super().__new__(cls, name, bases, dct)
        if not new.field:
            return new
        # add tests for fields
        setattr(new, "test_fields", cls.create_fields_test())
        # add tests for filters
        for filter_arg in new.operation_args:
            # skip otherwise implemented filter tests
            if filter_arg in cls.filters_skipped:
                continue
            # add test
            setattr(new, f"test_{filter_arg}_filter", cls.create_filter_test(filter_arg))
        return new

    @classmethod
    def create_fields_test(
            cls, user=SUPERADMIN_USER, actions=None, permitted=True,
            min_entries=1, default_batch_size=DEFAULT_BATCH_SIZE):
        """
        Creates a test for all fields of a query.

        Traverses the query result and asserts equality of all fields.
        Ignores all introspection vars but __typename.
        """
        @auth(user, actions, permitted)
        def test(self):
            # skip if not enough entries
            count = len(self.entries)
            if count < min_entries:
                raise SkipTest("not enough entries")
            # configure variables
            batch_size = min(count, default_batch_size) or count
            # execute operation
            result = self.client.execute(
                self.operation,
                variables={'first': batch_size}
            )
            # assert no errors
            self.assertIsNone(result.errors)
            # prepare query results
            data = next(iter(result.data.values()))
            edges = data['edges']
            # iterate over batch
            for index, entry in enumerate(self.entries[:batch_size]):
                node = edges[index]['node']
                # assert returned values are correct
                self.assertEntryEqual(entry, node)

        test.__doc__ = """returned fields have the correct value"""
        return test

    @classmethod
    def create_filter_test(
            cls, filter_arg, user=SUPERADMIN_USER, actions=None, permitted=True,
            min_entries=1, default_batch_size=DEFAULT_BATCH_SIZE):
        """
        Creates a test for one filter `filter_arg`.

        Executes a query with the filter set to the values of the database entries
        and expects the result to include (or exclude for gt/lt) the entry.
        """
        @auth(user, actions, permitted)
        def test(self):
            # skip if not enough entries
            count = len(self.entries)
            if count < min_entries:
                raise SkipTest("not enough entries")
            # configure variables
            batch_size = min(count, default_batch_size) or count
            model_field_name, *lookup = to_snake_case(filter_arg).split("__", maxsplit=1)
            model_field = self.model._meta.get_field(model_field_name)
            lookup = to_snake_case(filter_arg)
            # iterate over batch
            for entry in self.entries[:batch_size]:
                # get expected queryset
                attr = model_field.name
                database_value = getattr(entry, attr)
                if isinstance(model_field, GenericForeignKey):  # use _id/_ct
                    queryset = self.entries.filter(**{          # for GenericForeignKey
                        f"{attr}_id": database_value.id,
                        f"{attr}_ct": ContentType.objects.get_for_model(database_value).id
                    })
                else:
                    if lookup.endswith("__in"):  # in filter
                        database_value = [database_value]
                    queryset = self.entries.filter(**{lookup: database_value})
                # get database value for graphql operation variables
                if attr == "id":  # id fields
                    attr = "gid"
                database_value = getattr(entry, attr)
                if isinstance(database_value, models.Model):  # model fields
                    database_value = database_value.gid
                variables = {filter_arg: database_value}
                if lookup.endswith("__in"):  # in filter
                    variables = {filter_arg: [database_value]}
                with self.subTest(entry=entry, **variables):
                    # execute operation
                    result = self.client.execute(
                        self.operation,
                        variables=variables
                    )
                    # assert no errors
                    self.assertIsNone(result.errors)
                    # prepare query results
                    data = next(iter(result.data.values()))
                    edges = data['edges']
                    api_values = []
                    for edge in edges:
                        value = edge['node'][to_camel_case(model_field.name)]
                        # model fields
                        if isinstance(value, dict):
                            value = value['id']
                        # datetime fields
                        if isinstance(model_field, models.DateTimeField):
                            value = datetime.fromisoformat(value)
                        api_values.append(value)
                    # assert length of result and queryset are equal
                    self.assertEqual(len(edges), queryset.count())
                    # assert only one result for id fields
                    if attr == "gid":
                        self.assertEqual(len(edges), 1)
                    # assert queried database item is in the result
                    if lookup.endswith(("__gt", "__lt")):
                        self.assertNotIn(database_value, api_values)
                    else:
                        self.assertIn(database_value, api_values)

        test.__doc__ = f"""{filter_arg} filter returns correct entries"""
        return test


class ListQueryTestCase(SchemaTestCase, metaclass=QueryTestCaseMetaclass):
    """
    TestCase for list query operations.

    Adds tests for filter:
    - first
    - last
    - after
    - before
    - offset
    - forward pagination
    - backward pagination

    Adds tests for permissions:
    - all permitted
    - none permitted
    - one permitted

    Metaclass parses query and adds tests for:
    - all filters
    - all fields
    """
    __test__ = False

    # filters -----------------------------------------------------------------

    # TODO:
    # - last negative: no entries
    # - offset > db entries: all entries
    # - offset/first negative: "Negative indexing is not supported"
    # - before/after 'arrayconnection:-1': "Negative indexing is not supported"
    # - before/after 'invalidstrings': no entries
    # - first/last > 100: "exceeds the limit of 100 records"
    # - max limit: result < max limit

    @auth(SUPERADMIN_USER, permitted=True)
    def test_first_filter(self):
        """first filter returns only first entries"""
        # skip if filter not set
        if 'first' not in self.operation_args:
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 1:
            raise SkipTest("not enough entries")
        # configure variables
        batch_size = min(count, DEFAULT_BATCH_SIZE) or count
        # iterate over batch
        for first in range(batch_size):
            with self.subTest(first=first):
                # execute operation
                result = self.client.execute(
                    self.operation,
                    variables={'first': first}
                )
                # assert no errors
                self.assertIsNone(result.errors)
                # prepare query results
                data = next(iter(result.data.values()))
                edges = data['edges']
                # assert length of query result matched the request
                self.assertEqual(len(edges), first)
                # assert first/last node is equal to first/last database entry
                if first:
                    self.assertEqual(edges[0]['node']['id'], self.entries[0].gid)
                    self.assertEqual(edges[-1]['node']['id'], self.entries[first-1].gid)

    @auth(SUPERADMIN_USER, permitted=True)
    def test_last_filter(self):
        """last filter returns only last entries"""
        # skip if filter not set
        if 'last' not in self.operation_args:
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 1:
            raise SkipTest("not enough entries")
        # configure variables
        batch_size = min(count, DEFAULT_BATCH_SIZE) or count
        # iterate over batch
        for last in range(batch_size):
            with self.subTest(last=last):
                # execute operation
                result = self.client.execute(
                    self.operation,
                    variables={'last': last}
                )
                # assert no errors
                self.assertIsNone(result.errors)
                # prepare query results
                data = next(iter(result.data.values()))
                edges = data['edges']
                # assert length of query result matched the request
                self.assertEqual(len(edges), last)
                # assert first/last node is equal to first/last database entry
                if last:
                    self.assertEqual(edges[0]['node']['id'], self.entries[count-last].gid)
                    self.assertEqual(edges[-1]['node']['id'], self.entries[count-1].gid)

    @auth(SUPERADMIN_USER, permitted=True)
    def test_offset_filter(self):
        """offset filter returns offsetted entries"""
        # skip if filter not set
        if 'offset' not in self.operation_args:
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 2:
            raise SkipTest("not enough entries")
        # configure variables
        batch_size = min(count, DEFAULT_BATCH_SIZE) or count
        # iterate over batch
        for offset in range(batch_size):
            with self.subTest(offset=offset):
                # execute operation
                result = self.client.execute(
                    self.operation,
                    variables={'offset': offset}
                )
                # assert no errors
                self.assertIsNone(result.errors)
                # prepare query results
                data = next(iter(result.data.values()))
                edges = data['edges']
                # assert first result has the right offset
                self.assertEqual(edges[0]['node']['id'], self.entries[offset].gid)

    @auth(SUPERADMIN_USER, permitted=True)
    def test_after_filter(self):
        """after filter returns entries after specified cursor"""
        # skip if filter not set
        if 'after' not in self.operation_args:
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 2:
            raise SkipTest("not enough entries")
        # configure variables
        batch_size = min(count, DEFAULT_BATCH_SIZE) or count
        # iterate over batch
        for after in range(batch_size):
            with self.subTest(after=after):
                # execute operation
                result = self.client.execute(
                    self.operation,
                    variables={'after': base64(f"arrayconnection:{after}")}
                )
                # assert no errors
                self.assertIsNone(result.errors)
                # prepare query results
                data = next(iter(result.data.values()))
                edges = data['edges']
                # assert query result length shrinks with omitted entries
                self.assertEqual(len(edges), count-after-1)
                # assert first query result is the expected one
                if count-after-1 > 0:  # skip if no entries are left
                    self.assertEqual(edges[0]['node']['id'], self.entries[after+1].gid)

    @auth(SUPERADMIN_USER, permitted=True)
    def test_before_filter(self):
        """before filter returns entries before specified cursor"""
        # skip if filter not set
        if 'before' not in self.operation_args:
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 2:
            raise SkipTest("not enough entries")
        # configure variables
        batch_size = min(count, DEFAULT_BATCH_SIZE) or count
        # iterate over batch
        for before in range(batch_size):
            with self.subTest(before=before):
                # execute operation
                result = self.client.execute(
                    self.operation,
                    variables={'before': base64(f"arrayconnection:{before}")}
                )
                # assert no errors
                self.assertIsNone(result.errors)
                # prepare query results
                data = next(iter(result.data.values()))
                edges = data['edges']
                # assert query result length shrinks with omitted entries
                self.assertEqual(len(edges), before)
                # assert last query result is the expected one
                if before:  # skip if no entries are left
                    self.assertEqual(edges[-1]['node']['id'], self.entries[before-1].gid)

    @auth(SUPERADMIN_USER, permitted=True)
    def test_forward_pagination_filter(self):
        """forward pagination returns correct slices"""
        # skip if filter not set
        if any(arg not in self.operation_args for arg in ['first', 'after']):
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 2:
            raise SkipTest("not enough entries")
        # configure variables
        batch_size = min(count, DEFAULT_BATCH_SIZE) or count
        page_size = max(1, int(count / batch_size))
        pages = int(count / page_size)
        # iterate over pages
        after = ""
        for page in range(1, pages+1):
            offset = page * page_size - page_size
            with self.subTest(pages=pages, page=page, page_size=page_size, after=after):
                # execute operation
                result = self.client.execute(
                    self.operation,
                    variables={
                        'first': page_size,
                        'after': after,
                    }
                )
                # assert no errors
                self.assertIsNone(result.errors)
                # prepare query results
                data = next(iter(result.data.values()))
                edges = data['edges']
                pageinfo = data['pageInfo']
                page_start_cursor = pageinfo['startCursor']
                edge_start_cursor = edges[0]['cursor']
                page_end_cursor = pageinfo['endCursor']
                edge_end_cursor = edges[-1]['cursor']
                # assert first item is the expected one
                self.assertEqual(edges[0]['node']['id'], self.entries[offset].gid)
                # assert last item is the expected one
                self.assertEqual(edges[-1]['node']['id'], self.entries[offset+page_size-1].gid)
                # assert no previous page, https://github.com/graphql-python/graphene/issues/395
                self.assertFalse(pageinfo['hasPreviousPage'])
                # assert next page, if not the last one
                self.assertEqual(pageinfo['hasNextPage'], page != pages)
                # assert first edge cursor and page start cursor are the same
                self.assertEqual(page_start_cursor, edge_start_cursor)
                # assert last edge cursor and page end cursor are the same
                self.assertEqual(page_end_cursor, edge_end_cursor)
                # assign the cursor for the next batch
                after = page_end_cursor

    @auth(SUPERADMIN_USER, permitted=True)
    def test_backward_pagination_filter(self):
        """backward pagination returns correct slices"""
        # skip if filter not set
        if any(arg not in self.operation_args for arg in ['last', 'before']):
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 2:
            raise SkipTest("not enough entries")
        # configure variables
        batch_size = min(count, DEFAULT_BATCH_SIZE) or count
        page_size = max(1, int(count / batch_size))
        pages = int(count / page_size)
        # iterate over pages
        before = ""
        for page in range(1, pages+1):
            page_items = pages * page_size
            offset = count - page_items + (pages - page) * page_size
            with self.subTest(pages=pages, page=page, page_size=page_size, before=before):
                # execute operation
                result = self.client.execute(
                    self.operation,
                    variables={
                        'last': page_size,
                        'before': before,
                    }
                )
                # assert no errors
                self.assertIsNone(result.errors)
                # prepare query results
                data = next(iter(result.data.values()))
                edges = data['edges']
                pageinfo = data['pageInfo']
                page_start_cursor = pageinfo['startCursor']
                edge_start_cursor = edges[0]['cursor']
                page_end_cursor = pageinfo['endCursor']
                edge_end_cursor = edges[-1]['cursor']
                # assert first item is the expected one
                self.assertEqual(edges[0]['node']['id'], self.entries[offset].gid)
                # assert last item is the expected one
                self.assertEqual(edges[-1]['node']['id'], self.entries[offset+page_size-1].gid)
                # assert previous page, if not the last one
                self.assertEqual(pageinfo['hasPreviousPage'], page != pages)
                # assert no next page, https://github.com/graphql-python/graphene/issues/395
                self.assertFalse(pageinfo['hasNextPage'])
                # assert first edge cursor and page start cursor are the same
                self.assertEqual(page_start_cursor, edge_start_cursor)
                # assert last edge cursor and page end cursor are the same
                self.assertEqual(page_end_cursor, edge_end_cursor)
                # assign the cursor for the next batch
                before = page_start_cursor

    # permissions -------------------------------------------------------------

    @auth(SUPERADMIN_USER, permitted=True)
    def test_all_permitted(self):
        """all permitted returns all entries"""
        # skip if model has not inherited MixinAuthorization
        if not issubclass(self.model, MixinAuthorization):
            raise SkipTest(
                "WARNING: model is public (not inherited MixinAuthorization)")
        # skip if graphene type did not set object_permits_user in permission
        if not any(p.__qualname__.startswith('object_permits_user')
                   for p in self.permission):
            raise SkipTest(
                "WARNING: operation has no permission check (object_permits_user)")
        # skip if not enough entries
        count = len(self.entries)
        if count < 1:
            raise SkipTest("not enough entries")
        # execute operation
        result = self.client.execute(self.operation)
        # assert no errors
        self.assertIsNone(result.errors)
        # prepare query results
        data = next(iter(result.data.values()))
        edges = data['edges']
        # assert length of query result matches the number of database entries
        self.assertEqual(len(edges), len(self.entries))

    @auth(SUPERADMIN_USER, permitted=False)
    def test_none_permitted(self):
        """none permitted returns no entries"""
        # skip if model has not inherited MixinAuthorization
        if not issubclass(self.model, MixinAuthorization):
            raise SkipTest(
                "WARNING: model is public (not inherited MixinAuthorization)")
        # skip if graphene type did not set object_permits_user in permission
        if not any(p.__qualname__.startswith('object_permits_user')
                   for p in self.permission):
            raise SkipTest(
                "WARNING: operation has no permission check (object_permits_user)")
        # skip if not enough entries
        count = self.model.objects.count()
        if count < 1:
            raise SkipTest("not enough entries")
        # execute operation
        result = self.client.execute(self.operation)
        # assert no errors
        self.assertIsNone(result.errors)
        # prepare query results
        data = next(iter(result.data.values()))
        edges = data['edges']
        # assert no results
        self.assertEqual(len(edges), 0)

    _one_permitted_id = 0

    def _one_permitted(*args, **kwargs):
        return models.Q(id=ListQueryTestCase._one_permitted_id)

    @auth(SUPERADMIN_USER, permitted=_one_permitted)
    def test_one_permitted(self):
        """one permitted returns only one entry"""
        # skip if model has not inherited MixinAuthorization
        if not issubclass(self.model, MixinAuthorization):
            raise SkipTest(
                "WARNING: model is public (not inherited MixinAuthorization)")
        # skip if graphene type did not set object_permits_user in permission
        if not any(p.__qualname__.startswith('object_permits_user')
                   for p in self.permission):
            raise SkipTest(
                "WARNING: operation has no permission check (object_permits_user)")
        # skip if not enough entries
        all_entries = self.model.objects.all()
        count = all_entries.count()
        if count < 1:
            raise SkipTest("not enough entries")
        # configure variables
        batch_size = min(count, DEFAULT_BATCH_SIZE) or count
        # iterate over batch
        for entry in all_entries[:batch_size]:
            ListQueryTestCase._one_permitted_id = entry.id
            with self.subTest(entry=entry):
                # execute operation
                result = self.client.execute(self.operation)
                # assert no errors
                self.assertIsNone(result.errors)
                # prepare query results
                data = next(iter(result.data.values()))
                edges = data['edges']
                # assert only one result
                self.assertEqual(len(edges), 1)
                # assert identiy of result
                self.assertEqual(edges[0]['node']['id'], entry.gid)

    @auth(INACTIVE_USER)
    def test_inactive_authentication_fails(self):
        """authentication of inactive user throws jwt error"""
        # execute operation
        result = self.client.execute(self.operation)
        # assert only one jwt error
        self.assertEqual(len(result.errors), 1)
        self.assertIsInstance(result.errors[0].original_error, JSONWebTokenError)
        self.assertIn("disabled", result.errors[0].message)


# mutation --------------------------------------------------------------------

class MutationTestCase(SchemaTestCase, metaclass=SchemaTestCaseMetaclass):
    """
    TestCase for mutation operations.
    """
    __test__ = False
