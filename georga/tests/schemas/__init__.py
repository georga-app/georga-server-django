from os import listdir
from os.path import isfile, join
from unittest import SkipTest
from functools import wraps

from graphql_jwt.testcases import JSONWebTokenTestCase, JSONWebTokenClient
from graphql_jwt.shortcuts import get_token
from graphql_jwt.settings import jwt_settings

from georga.models import MixinAuthorization, Person

SUPERADMIN_USER = "admin@georga.test"
FIXTURES_DIR = join("georga", "fixtures")

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
    """Skips tests if class attribute __test__ is False."""
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
        return new


class SchemaTestCase(JSONWebTokenTestCase, metaclass=SchemaTestCaseMetaclass):
    """
    Base class for schema tests.

    Fetches some variables for easy access within the tests. Inserts common
    relay default values into the operation string. Formats the test output.

    Args:
        client_class (django.test.Client): The class for the client, which
            executes the graphql operation.
        fixtures (list[str]): List of fixture filenames to load.
        field (graphene.Field()): The query, mutation or subscription to test.
            Fetched via `georga.QueryType|MutationType|SubscriptionType.<operation>`.
        operation (str): The query, mutation or subscription string to execute.
            The strings `[VARIABLES]`, `[ARGUMENTS]` and `[PAGEINFO]` are
            substituted with the relay default values for the variables, fields
            or pageinfo.
        model (django.models.Model()): The model, on which the graphql operation
            operates. Fetched automatically.
        user (georga.models.Person()): The user, which is authenticated for
            the graphql operation. Set via `@auth()` decorator.
        entries (django.models.query.QuerySet()): The queryset, on which the
            operation result is based on. Set via `@auth()` decorator.
    """
    client_class = CachedJSONWebTokenClient
    fixtures = [f for f in listdir(FIXTURES_DIR) if isfile(join(FIXTURES_DIR, f))]

    # mandatory attributes to override on inheritance
    field = None
    operation = None

    # derived values from mandatory attributes
    model = None
    user = None
    entries = None

    def __init__(self, *args, **kwargs):
        # get model class
        self.model = self.field.model
        # substitute operation variables
        if self.operation:
            self.operation = self.operation.replace("[VARIABLES]", VARIABLES)
            self.operation = self.operation.replace("[ARGUMENTS]", ARGUMENTS)
            self.operation = self.operation.replace("[PAGEINFO]", PAGEINFO)
        super().__init__(*args, **kwargs)

    def shortDescription(self):
        return False

    def __str__(self):
        id = self.id().split('.')
        # Schemas|Models|...
        module = id[2].capitalize()
        # schema operation type, e.g. Query|Mutation|Subscription
        operation_type = self.operation.split(maxsplit=1)[0].strip().capitalize()
        # schema operation name, e.g. listPersons|listAces|...
        operation_name = id[4][0].lower() + id[4][1:].removesuffix("TestCase")
        # test method docstring
        test_description = super().shortDescription() or self._testMethodName
        return f"{module} | {operation_type} | {operation_name} | {test_description}"


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
        _permitted = lambda *args, **kwargs: permitted  # noqa

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
            if self.user:
                self.entries = self.model.objects
                if actions:
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
    # def __new__(cls, name, bases, dct):
    #     new = super().__new__(cls, name, bases, dct)
    #     if not new.field:
    #         return new
    #     # TODO: use schema introspection to fetch objects
    #     new.return_fields = getattr(new.field.node_type._meta, 'fields', {})
    #     new.filter_fields = getattr(new.field.node_type._meta, 'filter_fields', {})
    #     # add tests for filters
    #     for name, lookups in new.filter_fields.items():
    #         for lookup in lookups:
    #             match(lookup):
    #                 case 'exact':
    #                     pass
    #                 case _:
    #                     # TODO: add raise SkipTest("not enough entries")
    #                     pass
    #     return new

    # @staticmethod
    # def create_exact_filter_test(
    #         name, user=SUPERADMIN_USER, actions=None, permitted=True,
    #         min_entries=1, default_size=5):
    #     @auth(user, actions, permitted)
    #     def filter_test(self):
    #         f"""{name} filter returns correct entries"""
    #         # skip if not enough entries
    #         count = len(self.entries)
    #         if count < min_entries:
    #             raise SkipTest("not enough entries")
    #         # configure variables
    #         size = min(count, default_size)
    #         # iterate over entries
    #         for item in self.entries[:size]:
    #             with self.subTest(item=item, id=item.gid):
    #                 # execute operation
    #                 result = self.client.execute(
    #                     self.operation,
    #                     variables={'id': item.gid}
    #                 )
    #                 # assert no errors
    #                 self.assertIsNone(result.errors)
    #                 # assert all database objects are delivered
    #                 data = next(iter(result.data.values()))
    #                 self.assertEqual(
    #                     data['edges'][0]['node']['id'],
    #                     item.gid)
    #     return filter_test


class ListQueryTestCase(SchemaTestCase, metaclass=QueryTestCaseMetaclass):
    """
    TestCase for list query operations.

    Adds tests for filter:
    - id
    - first
    - last
    - offset
    - forward pagination
    - backward pagination

    Adds tests for permissions:
    - all permitted
    - none permitted
    """
    __test__ = False

    # filters -----------------------------------------------------------------

    @auth(SUPERADMIN_USER, permitted=True)
    def test_id_filter(self):
        """id filter returns correct entry"""
        # skip if filter not set
        if 'id' not in self.field.args:
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 1:
            raise SkipTest("not enough entries")
        # configure variables
        size = min(count, 3)
        # iterate over first 3 entries
        for item in self.entries[:size]:
            with self.subTest(item=item, id=item.gid):
                # execute operation
                result = self.client.execute(
                    self.operation,
                    variables={'id': item.gid}
                )
                # assert no errors
                self.assertIsNone(result.errors)
                # assert all database objects are delivered
                data = next(iter(result.data.values()))
                self.assertEqual(
                    data['edges'][0]['node']['id'],
                    item.gid)

    @auth(SUPERADMIN_USER, permitted=True)
    def test_first_filter(self):
        """first filter returns only first entries"""
        # skip if filter not set
        if 'first' not in self.field.args:
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 1:
            raise SkipTest("not enough entries")
        # configure variables
        size = round(count / 2)
        # execute operation
        result = self.client.execute(
            self.operation,
            variables={'first': size}
        )
        # assert no errors
        self.assertIsNone(result.errors)
        # assert all database objects are delivered
        data = next(iter(result.data.values()))
        self.assertEqual(
            len(data['edges']),
            size)
        # assert first/last nodes are equal to first/last database entries
        self.assertEqual(
            data['edges'][0]['node']['id'],
            self.entries[0].gid)
        self.assertEqual(
            data['edges'][-1]['node']['id'],
            self.entries[size-1].gid)

    @auth(SUPERADMIN_USER, permitted=True)
    def test_last_filter(self):
        """last filter returns only last entries (superadmin, all permitted)"""
        # skip if filter not set
        if 'last' not in self.field.args:
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 1:
            raise SkipTest("not enough entries")
        # configure variables
        size = round(count / 2)
        # execute operation
        result = self.client.execute(
            self.operation,
            variables={'last': size}
        )
        # assert no errors
        self.assertIsNone(result.errors)
        # assert all database objects are delivered
        data = next(iter(result.data.values()))
        self.assertEqual(
            len(data['edges']),
            size)
        # assert first/last nodes are equal to first/last database entries
        self.assertEqual(
            data['edges'][0]['node']['id'],
            self.entries[len(self.entries)-size].gid)
        self.assertEqual(
            data['edges'][-1]['node']['id'],
            self.entries[len(self.entries)-1].gid)

    @auth(SUPERADMIN_USER, permitted=True)
    def test_offset_filter(self):
        """offset returns offsetted entried (superadmin, all permitted)"""
        # skip if filter not set
        if 'offset' not in self.field.args:
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 2:
            raise SkipTest("not enough entries")
        # configure variables
        size = round(count / 2)
        # execute operation
        result = self.client.execute(
            self.operation,
            variables={'offset': size}
        )
        # assert no errors
        self.assertIsNone(result.errors)
        # assert all database objects are delivered
        data = next(iter(result.data.values()))
        self.assertEqual(
            data['edges'][0]['node']['id'],
            self.entries[size].gid)

    @auth(SUPERADMIN_USER, permitted=True)
    def test_forward_pagination_filter(self):
        """forward pagination returns correct slices (superadmin, all permitted)"""
        # skip if filter not set
        if any(arg not in self.field.args for arg in ['first', 'after']):
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 2:
            raise SkipTest("not enough entries")
        # configure variables
        pages = min(count, 3)
        size = int(count / pages)
        # iterate over pages
        after = ""
        for page in range(pages):
            with self.subTest(pages=pages, page=page, after=after, size=size):
                # execute operation
                result = self.client.execute(
                    self.operation,
                    variables={
                        'first': size,
                        'after': after,
                    }
                )
                # assert no errors
                self.assertIsNone(result.errors)
                # assert all database objects are delivered
                data = next(iter(result.data.values()))
                self.assertEqual(
                    data['edges'][0]['node']['id'],
                    self.entries[page*size].gid)
                self.assertEqual(
                    data['edges'][-1]['node']['id'],
                    self.entries[page*size+size-1].gid)
                self.assertFalse(  # https://github.com/graphql-python/graphene/issues/395
                    data['pageInfo']['hasPreviousPage'])
                self.assertEqual(
                    data['pageInfo']['hasNextPage'],
                    page != pages - 1)
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
        """backward pagination returns correct slices (superadmin, all permitted)"""
        # skip if filter not set
        if any(arg not in self.field.args for arg in ['last', 'before']):
            raise SkipTest("filter not set")
        # skip if not enough entries
        count = len(self.entries)
        if count < 2:
            raise SkipTest("not enough entries")
        # configure variables
        pages = min(count, 3)
        size = int(count / pages)
        # iterate over pages
        before = ""
        for page in reversed(range(pages)):
            with self.subTest(pages=pages, page=page, before=before, size=size):
                # execute operation
                result = self.client.execute(
                    self.operation,
                    variables={
                        'last': size,
                        'before': before,
                    }
                )
                # assert no errors
                self.assertIsNone(result.errors)
                # assert all database objects are delivered
                data = next(iter(result.data.values()))
                self.assertEqual(
                    data['edges'][0]['node']['id'],
                    self.entries[page*size].gid)
                self.assertEqual(
                    data['edges'][-1]['node']['id'],
                    self.entries[page*size+size-1].gid)
                self.assertEqual(
                    data['pageInfo']['hasPreviousPage'],
                    page != 0)
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

    @auth(SUPERADMIN_USER, permitted=True)
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

    @auth(SUPERADMIN_USER, permitted=False)
    def test_none_permitted(self):
        """none_permitted_returns no entries"""
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
