from graphql_jwt.exceptions import JSONWebTokenError

from . import ListQueryTestCase, auth
from ...models import ACE


listAcesQuery = """
query (
    [VARIABLES]
    $instance: ID
    $instance_In: [ID]
){
    listAces (
        [ARGUMENTS]
        instance: $instance
        instance_In: $instance_In
    ) {
        [PAGEINFO]
        edges {
            cursor
            node {
                id
                createdAt
                modifiedAt
                person {
                    id
                    email
                }
                permission
                instance {
                    ... on OrganizationType {
                      __typename
                        id
                        name
                    }
                    ... on ProjectType {
                      __typename
                        id
                        name
                    }
                    ... on OperationType {
                      __typename
                        id
                        name
                    }
                }
            }
        }
    }
}
"""


class ListAcesTestCase(ListQueryTestCase):
    operation = listAcesQuery

    # authentication ----------------------------------------------------------

    def test_login_required(self):
        """non authenticated access throws permission error"""
        # execute operation
        result = self.client.execute(self.operation)
        # assert only one permission error
        self.assertIsNotNone(result.errors)
        self.assertEqual(len(result.errors), 1)
        self.assertIsInstance(result.errors[0].original_error, JSONWebTokenError)
        self.assertIn("permission", result.errors[0].message)
        # prepare query results
        data = next(iter(result.data.values()))
        # assert no data
        self.assertIsNone(data)

    # authorization -----------------------------------------------------------

    @auth("helper@georga.test")
    def test_staff_member_required(self):
        """non staff member gets an empty result"""
        # execute operation
        result = self.client.execute(self.operation)
        # assert no errors
        self.assertIsNone(result.errors)
        # prepare query results
        data = next(iter(result.data.values()))
        # assert no results
        self.assertFalse(data['edges'])

    @auth("organization@georga.test")
    def test_organization_admin_permitted(self):
        """organization admin gets all and only permitted entries"""
        expected_queryset = ACE.objects.filter(pk__in=[1, 2, 3])
        # execute operation
        result = self.client.execute(self.operation)
        # assert no errors
        self.assertIsNone(result.errors)
        # prepare query results
        data = next(iter(result.data.values()))
        result_ids = {edge["node"]["id"] for edge in data["edges"]}
        expected_ids = {entry.gid for entry in expected_queryset}
        # assert expected results
        self.assertSetEqual(result_ids, expected_ids)

    @auth("project@georga.test")
    def test_project_admin_permitted(self):
        """project admin gets all and only permitted entries"""
        expected_queryset = ACE.objects.filter(pk__in=[2, 3])
        # execute operation
        result = self.client.execute(self.operation)
        # assert no errors
        self.assertIsNone(result.errors)
        # prepare query results
        data = next(iter(result.data.values()))
        result_ids = {edge["node"]["id"] for edge in data["edges"]}
        expected_ids = {entry.gid for entry in expected_queryset}
        # assert expected results
        self.assertSetEqual(result_ids, expected_ids)

    @auth("operation@georga.test")
    def test_operation_admin_permitted(self):
        """operation admin gets all and only permitted entries"""
        expected_queryset = ACE.objects.filter(pk__in=[3])
        # execute operation
        result = self.client.execute(self.operation)
        # assert no errors
        self.assertIsNone(result.errors)
        # prepare query results
        data = next(iter(result.data.values()))
        result_ids = {edge["node"]["id"] for edge in data["edges"]}
        expected_ids = {entry.gid for entry in expected_queryset}
        # assert expected results
        self.assertSetEqual(result_ids, expected_ids)
