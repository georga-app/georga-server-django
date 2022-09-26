from graphql_jwt.exceptions import JSONWebTokenError

from . import auth, ListQueryTestCase, MutationTestCase
from ...models import (
    ACE,
    Organization,
    Person,
)


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

createAceQuery = """
mutation (
    $person: ID!
    $permission: String!
    $instance: ID!
) {
    createAce (
        input: {
            person: $person
            permission: $permission
            instance: $instance
        }
    ) {
        aCE {
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
        errors {
            field
            messages
        }
    }
}
"""


class ListAcesTestCase(ListQueryTestCase):
    operation = listAcesQuery

    # permission --------------------------------------------------------------

    def test_login_required(self):
        """non authenticated user gets a permission error"""
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

    @auth("helper.001@georga.test")
    def test_staff_member_required(self):
        """non staff member user gets an empty result"""
        # execute operation
        result = self.client.execute(self.operation)
        # assert no errors
        self.assertIsNone(result.errors)
        # prepare query results
        data = next(iter(result.data.values()))
        # assert no results
        self.assertFalse(data['edges'])

    def test_permitted(self):
        """authorized user gets all and only permitted entries"""
        usernames = [
            # french blue circle
            "organization.admin.1@frenchbluecircle.test",
            "project.admin.1@frenchbluecircle.test",
            "operation.admin.1@frenchbluecircle.test",
            # mixed
            "organization@georga.test",
            "project@georga.test",
            "operation@georga.test",
        ]
        for username in usernames:
            user = Person.objects.get(username=username)
            expected_queryset = ACE.filter_permitted(user, 'read')
            with self.subTest(user=user, expected_queryset=expected_queryset):
                # authenticate user
                self.client.authenticate(user)
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
                # logout user
                self.client.logout()


class CreateAceTestCase(MutationTestCase):
    operation = createAceQuery

    # TODO:
    # - wrong permission (not in choice)
    # - wrong instance (wrong padding, wrong model)
    # - wrong person (not employed by organization)

    # permission --------------------------------------------------------------

    def test_login_required(self):
        """non authenticated gets a permission error"""
        # execute operation
        result = self.client.execute(
            self.operation,
            variables={
                'person': "unchecked",
                'permission': "unchecked",
                'instance': "unchecked",
            }
        )
        # assert only one permission error
        self.assertIsNotNone(result.errors)
        self.assertEqual(len(result.errors), 1)
        self.assertIsInstance(result.errors[0].original_error, JSONWebTokenError)
        self.assertIn("permission", result.errors[0].message)
        # prepare query results
        data = next(iter(result.data.values()))
        # assert no data
        self.assertIsNone(data)

    @auth("helper.001@georga.test")
    def test_staff_member_required(self):
        """non staff member gets a permission error"""
        # execute operation
        result = self.client.execute(
            self.operation,
            variables={
                'person': "unchecked",
                'permission': "unchecked",
                'instance': "unchecked",
            }
        )
        # assert only one permission error
        self.assertIsNotNone(result.errors)
        self.assertEqual(len(result.errors), 1)
        self.assertIsInstance(result.errors[0].original_error, JSONWebTokenError)
        self.assertIn("permission", result.errors[0].message)
        # prepare query results
        data = next(iter(result.data.values()))
        # assert no data
        self.assertIsNone(data)

    def test_not_permitted(self):
        """admins cannot create entries out of admin hierarchy"""
        # prepare variables
        count = ACE.objects.count()
        root_organization = Organization.objects.get(name="French Blue Circle")
        child_project = root_organization.project_set.first()
        child_operation = child_project.operation_set.first()
        sister_project = root_organization.project_set.last()
        sister_operation = sister_project.operation_set.first()
        other_organization = Organization.objects.get(name="Sea Eyes International")
        other_project = other_organization.project_set.first()
        other_operation = other_project.operation_set.first()
        # prepare mapping of user -> instance to test
        failing_tests = {
            "organization.admin.1@frenchbluecircle.test": [
                other_organization,
                other_project,
                other_operation,
                root_organization,
            ],
            "project.admin.1@frenchbluecircle.test": [
                other_organization,
                other_project,
                other_operation,
                root_organization,
                child_project,
                sister_project,
                sister_operation,
            ],
            "operation.admin.1@frenchbluecircle.test": [
                other_organization,
                other_project,
                other_operation,
                root_organization,
                child_project,
                child_operation,
                sister_project,
                sister_operation,
            ],
        }
        # iterate over wrong instances
        for username, instances in failing_tests.items():
            for instance in instances:
                user = Person.objects.get(username=username)
                with self.subTest(user=user, instance=instance):
                    # authenticate user
                    self.client.authenticate(user)
                    # execute operation
                    result = self.client.execute(
                        self.operation,
                        variables={
                            'person': instance.organization.persons_employed.first().gid,
                            'permission': "ADMIN",
                            'instance': instance.gid,
                        }
                    )
                    # assert only one permission error
                    self.assertIsNotNone(result.errors)
                    self.assertEqual(len(result.errors), 1)
                    self.assertIsInstance(result.errors[0].original_error, JSONWebTokenError)
                    self.assertIn("permission", result.errors[0].message)
                    # prepare query results
                    data = next(iter(result.data.values()))
                    # assert no data
                    self.assertIsNone(data)
                    # assert no database entry was created
                    self.assertEqual(count, ACE.objects.count())
                    # logout user
                    self.client.logout()

    def test_permitted(self):
        """admins can create entries within admin hierarchy"""
        # prepare variables
        count = ACE.objects.count()
        root_organization = Organization.objects.get(name="French Blue Circle")
        child_project = root_organization.project_set.first()
        child_operation = child_project.operation_set.first()
        # prepare mapping of user -> instance to test
        succeeding_tests = {
            "organization.admin.1@frenchbluecircle.test": [
                child_project,
                child_operation,
            ],
            "project.admin.1@frenchbluecircle.test": [
                child_operation,
            ],
        }
        # iterate over wrong instances
        for username, instances in succeeding_tests.items():
            for instance in instances:
                user = Person.objects.get(username=username)
                with self.subTest(user=user, instance=instance):
                    # authenticate user
                    self.client.authenticate(user)
                    # execute operation
                    result = self.client.execute(
                        self.operation,
                        variables={
                            'person': instance.organization.persons_employed.first().gid,
                            'permission': "ADMIN",
                            'instance': instance.gid,
                        }
                    )
                    # assert no error
                    self.assertIsNone(result.errors)
                    # assert database entry was created
                    self.assertEqual(count + 1, ACE.objects.count())
                    # prepare query results
                    data = next(iter(result.data.values()))
                    entry = ACE.objects.last()
                    # assert id is returned
                    self.assertEqual(data['aCE']['id'], entry.gid)
                    # delete entry
                    entry.delete()
                    # logout user
                    self.client.logout()
