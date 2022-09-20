from os import listdir
from os.path import isfile, join
from unittest import SkipTest
from functools import wraps

from graphql import parse
from graphql_jwt.testcases import JSONWebTokenTestCase, JSONWebTokenClient
from graphql_jwt.shortcuts import get_token
from graphql_jwt.settings import jwt_settings
from graphql_relay.utils import base64
from graphene.utils.str_converters import to_snake_case

from ...models import MixinAuthorization, Person
from ...schemas import schema


SUPERADMIN_USER = "admin@georga.test"
FIXTURES_DIR = join("georga", "fixtures")
DEFAULT_BATCH_SIZE = 5  # number of entries tested in automated tests

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
PAGEINFO = """
        pageInfo {
            hasNextPage
            hasPreviousPage
            startCursor
            endCursor
        }
"""

TOKEN_CACHE = {}


# jwt -------------------------------------------------------------------------

class CachedJSONWebTokenClient(JSONWebTokenClient):
    """JSONWebTokenClient with cached tokens, requested only once per run."""
    def authenticate(self, user):
        if user.email not in TOKEN_CACHE:
            TOKEN_CACHE[user.email] = get_token(user)
        self._credentials = {
            jwt_settings.JWT_AUTH_HEADER_NAME: (
                f"{jwt_settings.JWT_AUTH_HEADER_PREFIX} {TOKEN_CACHE[user.email]}"
            ),
        }


# base ------------------------------------------------------------------------

class SchemaTestCaseMetaclass(type):
    """
    Metaclass for schema tests

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
            root = schema.get_type(f"{operation_type.capitalize()}Type")
            field = root.fields[operation_name]
            graphene_type_name = field.type.name.removesuffix('Connection')
            graphene_type = schema.get_type(graphene_type_name).graphene_type
            model = graphene_type._meta.model
            # assign variables
            new.operation = operation
            new.operation_type = operation_type
            new.operation_ast = operation_ast
            new.operation_name = operation_name
            new.field = field
            new.model = model
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

    Attrs set in `@auth()` decorator:
        user (georga.models.Person()): The user, which is authenticated for
            the graphql operation.
        entries (django.models.query.QuerySet()): The queryset, on which the
            operation result is based on.
    """
    client_class = CachedJSONWebTokenClient
    fixtures = [f for f in listdir(FIXTURES_DIR) if isfile(join(FIXTURES_DIR, f))]

    # mandatory attributes to override on inheritance
    operation = None

    # derived in metaclass
    field = None
    model = None
    operation_type = None
    operation_name = None
    operation_ast = None

    # set in @auth()
    user = None
    entries = None

    def shortDescription(self):
        return False

    def __str__(self):
        # Schemas|Models|...
        module = "Schema"
        # schema operation type, e.g. Query|Mutation|Subscription
        type_ = self.operation_type.capitalize()
        # schema operation name, e.g. listPersons|listAces|...
        operation = self.operation_name
        # test method name
        name = self._testMethodName
        # test method docstring
        description = super().shortDescription() or self._testMethodName
        return f"{module} | {type_} | {operation} | {name} | {description}"


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
    _permitted = permitted
    if permitted in [True, False]:
        def _permitted(*args, **kwargs):
            return permitted

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # set and authenticate user
            self.user = user
            if isinstance(self.user, str):
                self.user = Person.objects.get(email=self.user)
            self.client.authenticate(self.user)
            # override permissions
            if callable(_permitted):
                self._permitted = self.model.permitted
                setattr(self.model, 'permitted', _permitted)
            # fetch database entries for user
            self.entries = self.model.objects
            if self.user and actions:
                self.entries = self.model.filter_permitted(self.user, actions)
            self.entries = self.entries.all()
            # execute test
            func(self, *args, **kwargs)
            # reset entries
            self.entries = None
            # reset permissions
            if callable(permitted):
                self.model.permitted = self._permitted
                self._permitted = None
            # reset and logout user
            self.user = None
            self.client.logout()
        return wrapper
    return decorator


# query -----------------------------------------------------------------------

class QueryTestCaseMetaclass(SchemaTestCaseMetaclass):
    """Adds tests for query operations based on the field."""
    getter_map = {
        'id': 'gid'
    }

    def __new__(cls, name, bases, dct):
        new = super().__new__(cls, name, bases, dct)
        if not new.field:
            return new
        # add tests for filters
        for name in new.field.args.keys():
            # skip otherwise implemented filter tests
            if name in ['first', 'last', 'offset', 'before', 'after']:
                continue
            if name != 'id':  # TODO: implement other filters
                continue
            # add test for the model attribute and lookup
            model_field, *lookup = to_snake_case(name).split("__", maxsplit=1)
            lookup = lookup and lookup[0] or "exact"
            match lookup:
                # TODO: skip filters not in args new.operation_ast.arguments
                case "exact":
                    setattr(new, f'test_{name}_filter',
                            cls.create_exact_filter_test(model_field))
                case _:
                    # TODO: skip with unimplemented warning
                    pass
        return new

    @classmethod
    def create_exact_filter_test(
            cls, name, user=SUPERADMIN_USER, actions=None, permitted=True,
            min_entries=1, default_batch_size=DEFAULT_BATCH_SIZE):
        def getter(item):
            return getattr(item, cls.getter_map.get(name, name))

        @auth(user, actions, permitted)
        def test(self):
            # skip if filter not set
            if name not in self.operation_args:
                raise SkipTest("filter not set")
            # skip if not enough entries
            count = len(self.entries)
            if count < min_entries:
                raise SkipTest("not enough entries")
            # configure variables
            size = min(count, default_batch_size)
            # iterate over entries
            for item in self.entries[:size]:
                variables = {name: getter(item)}
                with self.subTest(item=item, **variables):
                    # execute operation
                    result = self.client.execute(
                        self.operation,
                        variables=variables
                    )
                    # assert no errors
                    self.assertIsNone(result.errors)
                    # assert all database objects are delivered
                    data = next(iter(result.data.values()))
                    self.assertEqual(
                        data['edges'][0]['node'][name],
                        variables[name])
        exact_filter_test.__doc__ = f"""{name} filter returns correct entries"""
        return exact_filter_test


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

    Metaclass adds some tests for:
    - filter
    - fields
    """
    __test__ = False

    # filters -----------------------------------------------------------------

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
        batch_size = min(count, DEFAULT_BATCH_SIZE)
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
                # assert all database objects are delivered
                data = next(iter(result.data.values()))
                self.assertEqual(
                    len(data['edges']),
                    first)
                # assert first/last node is equal to first/last database entry
                if first:
                    self.assertEqual(
                        data['edges'][0]['node']['id'],
                        self.entries[0].gid)
                    self.assertEqual(
                        data['edges'][-1]['node']['id'],
                        self.entries[first-1].gid)

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
        batch_size = min(count, DEFAULT_BATCH_SIZE)
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
                # assert all database objects are delivered
                data = next(iter(result.data.values()))
                self.assertEqual(
                    len(data['edges']),
                    last)
                # assert first/last node is equal to first/last database entry
                if last:
                    self.assertEqual(
                        data['edges'][0]['node']['id'],
                        self.entries[count-last].gid)
                    self.assertEqual(
                        data['edges'][-1]['node']['id'],
                        self.entries[count-1].gid)

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
        batch_size = min(count, DEFAULT_BATCH_SIZE)
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
                # assert all database objects are delivered
                data = next(iter(result.data.values()))
                self.assertEqual(
                    data['edges'][0]['node']['id'],
                    self.entries[offset].gid)

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
        batch_size = min(count, DEFAULT_BATCH_SIZE)
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
                # assert all database objects are delivered
                data = next(iter(result.data.values()))
                self.assertEqual(
                    len(data['edges']),
                    count-after-1)
                if count-after-1 > 0:
                    self.assertEqual(
                        data['edges'][0]['node']['id'],
                        self.entries[after+1].gid)

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
        batch_size = min(count, DEFAULT_BATCH_SIZE)
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
                # assert all database objects are delivered
                data = next(iter(result.data.values()))
                self.assertEqual(
                    len(data['edges']),
                    before)
                if before:
                    self.assertEqual(
                        data['edges'][-1]['node']['id'],
                        self.entries[before-1].gid)

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
        page_size = max(1, int(count / DEFAULT_BATCH_SIZE))
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
                # assert all database objects are delivered
                data = next(iter(result.data.values()))
                self.assertEqual(
                    data['edges'][0]['node']['id'],
                    self.entries[offset].gid)
                self.assertEqual(
                    data['edges'][-1]['node']['id'],
                    self.entries[offset+page_size-1].gid)
                self.assertFalse(  # https://github.com/graphql-python/graphene/issues/395
                    data['pageInfo']['hasPreviousPage'])
                self.assertEqual(
                    data['pageInfo']['hasNextPage'],
                    page != pages)
                page_start_cursor = data['pageInfo']['startCursor']
                edge_start_cursor = data['edges'][0]['cursor']
                self.assertEqual(
                    page_start_cursor,
                    edge_start_cursor)
                page_end_cursor = data['pageInfo']['endCursor']
                edge_end_cursor = data['edges'][-1]['cursor']
                self.assertEqual(
                    page_end_cursor,
                    edge_end_cursor)
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
        page_size = max(1, int(count / DEFAULT_BATCH_SIZE))
        pages = int(count / page_size)
        # iterate over pages
        before = ""
        for page in range(1, pages+1):
            page_items = pages * page_size
            offset = count - page_items + (pages - page + 1) * page_size - page_size
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
                # assert all database objects are delivered
                data = next(iter(result.data.values()))
                self.assertEqual(
                    data['edges'][0]['node']['id'],
                    self.entries[offset].gid)
                self.assertEqual(
                    data['edges'][-1]['node']['id'],
                    self.entries[offset+page_size-1].gid)
                self.assertEqual(
                    data['pageInfo']['hasPreviousPage'],
                    page != pages)
                self.assertFalse(  # https://github.com/graphql-python/graphene/issues/395
                    data['pageInfo']['hasNextPage'])
                page_start_cursor = data['pageInfo']['startCursor']
                edge_start_cursor = data['edges'][0]['cursor']
                self.assertEqual(
                    page_start_cursor,
                    edge_start_cursor)
                page_end_cursor = data['pageInfo']['endCursor']
                edge_end_cursor = data['edges'][-1]['cursor']
                self.assertEqual(
                    page_end_cursor,
                    edge_end_cursor)
                before = page_start_cursor

    # permissions -------------------------------------------------------------

    @auth(SUPERADMIN_USER, actions='read', permitted=True)
    def test_all_permitted(self):
        """all permitted returns all entries"""
        # skip if model has no permissions
        if not issubclass(self.model, MixinAuthorization):
            raise SkipTest("model has no permissions")
        # skip if not enough entries
        count = len(self.entries)
        if count < 1:
            raise SkipTest("not enough entries")
        # execute operation
        result = self.client.execute(self.operation)
        # assert no errors
        self.assertIsNone(result.errors)
        # assert all database objects are delivered
        data = next(iter(result.data.values()))
        self.assertEqual(
            len(data['edges']),
            len(self.entries))

    @auth(SUPERADMIN_USER, actions='read', permitted=False)
    def test_none_permitted(self):
        """none permitted returns no entries"""
        # skip if model has no permissions
        if not issubclass(self.model, MixinAuthorization):
            raise SkipTest("model has no permissions")
        # skip if not enough entries
        count = self.model.objects.count()
        if count < 1:
            raise SkipTest("not enough entries")
        # execute operation
        result = self.client.execute(self.operation)
        # assert no errors
        self.assertIsNone(result.errors)
        # assert all database objects are delivered
        data = next(iter(result.data.values()))
        self.assertEqual(
            len(data['edges']),
            0)
