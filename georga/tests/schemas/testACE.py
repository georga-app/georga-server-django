from django.db import transaction

from graphql_jwt.exceptions import JSONWebTokenError

from . import auth, ListQueryTestCase, MutationTestCase
from ...models import (
    ACE,
    Organization,
    Person,
)


class ListAcesTestCase(ListQueryTestCase):
    operation = """
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

    def test_object_permits_user(self):
        """authorized user can list all and only permitted entries"""
        # prepare variables
        usernames = [
            # single organization
            "organization.admin.1@frenchbluecircle.test",
            "project.admin.1@frenchbluecircle.test",
            "operation.admin.1@frenchbluecircle.test",
            # multiple organizations
            "organization@georga.test",
            "project@georga.test",
            "operation@georga.test",
        ]
        # iterate over usernames
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
    operation = """
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

    # TODO:
    # - wrong permission (not in choice)
    # - wrong instance (empty string, wrong padding, wrong model)
    # - wrong person (not employed by organization)

    # permission --------------------------------------------------------------

    def test_login_required(self):
        """non authenticated user gets a permission error"""
        # execute operation
        result = self.client.execute(
            self.operation,
            variables={
                'person': "<UNCHECKED>",
                'permission': "<UNCHECKED>",
                'instance': "<UNCHECKED>",
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
        """non staff member user gets a permission error"""
        # execute operation
        result = self.client.execute(
            self.operation,
            variables={
                'person': "<UNCHECKED>",
                'permission': "<UNCHECKED>",
                'instance': "<UNCHECKED>",
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

    def test_object_permits_user(self):
        """authorized user can create only permitted entries"""
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
        allowed = {
            "organization.admin.1@frenchbluecircle.test": [
                child_project, child_operation,
            ],
            "project.admin.1@frenchbluecircle.test": [
                child_operation,
            ],
        }
        denied = {
            "organization.admin.1@frenchbluecircle.test": [
                root_organization,
                other_organization, other_project, other_operation,
            ],
            "project.admin.1@frenchbluecircle.test": [
                root_organization,
                child_project,
                sister_project, sister_operation,
                other_organization, other_project, other_operation,
            ],
            "operation.admin.1@frenchbluecircle.test": [
                root_organization,
                child_project, child_operation,
                sister_project, sister_operation,
                other_organization, other_project, other_operation,
            ],
        }
        # iterate over denied instances
        for username, instances in denied.items():
            for instance in instances:
                user = Person.objects.get(username=username)
                with self.subTest(user=user, instance=instance, permission="denied"):
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
        # iterate over allowed instances
        for username, instances in allowed.items():
            for instance in instances:
                user = Person.objects.get(username=username)
                with self.subTest(user=user, instance=instance, permission="allowed"):
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


class DeleteAceTestCase(MutationTestCase):
    operation = """
    mutation (
        $id: ID!
    ) {
        deleteAce (
            input: {
                id: $id
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

    # TODO:
    # - wrong id (empty string, wrong padding, wrong model)

    # permission --------------------------------------------------------------

    def test_login_required(self):
        """non authenticated user gets a permission error"""
        # execute operation
        result = self.client.execute(self.operation, variables={'id': "<UNCHECKED>"})
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
        """non staff member user gets a permission error"""
        # execute operation
        result = self.client.execute(self.operation, variables={'id': "<UNCHECKED>"})
        # assert only one permission error
        self.assertIsNotNone(result.errors)
        self.assertEqual(len(result.errors), 1)
        self.assertIsInstance(result.errors[0].original_error, JSONWebTokenError)
        self.assertIn("permission", result.errors[0].message)
        # prepare query results
        data = next(iter(result.data.values()))
        # assert no data
        self.assertIsNone(data)

    def test_object_permits_user(self):
        """authorized user can delete only permitted entries"""
        # prepare variables
        count = ACE.objects.count()
        usernames = [
            # single organization
            "organization.admin.1@frenchbluecircle.test",
            "project.admin.1@frenchbluecircle.test",
            "operation.admin.1@frenchbluecircle.test",
            # multiple organizations
            "organization@georga.test",
            "project@georga.test",
            "operation@georga.test",
        ]
        # iterate over usernames
        for username in usernames:
            # authenticate user
            user = Person.objects.get(username=username)
            self.client.authenticate(user)
            # get querysets
            allowed = ACE.filter_permitted(user, 'delete')
            denied = ACE.objects.difference(allowed)
            # iterate over denied instances
            for instance in denied:
                with self.subTest(user=user, instance=instance, permission="denied"):
                    # execute operation
                    result = self.client.execute(self.operation, variables={'id': instance.gid})
                    # assert only one permission error
                    self.assertIsNotNone(result.errors)
                    self.assertEqual(len(result.errors), 1)
                    self.assertIsInstance(result.errors[0].original_error, JSONWebTokenError)
                    self.assertIn("permission", result.errors[0].message)
                    # prepare query results
                    data = next(iter(result.data.values()))
                    # assert no data
                    self.assertIsNone(data)
                    # assert no database entry was deleted
                    self.assertEqual(count, ACE.objects.count())
            # iterate over allowed instances
            for instance in allowed:
                with self.subTest(user=user, instance=instance, permission="allowed"):
                    with transaction.atomic():
                        # execute operation
                        result = self.client.execute(
                            self.operation, variables={'id': instance.gid})
                        # prepare query results
                        data = next(iter(result.data.values()))
                        # assert no error
                        self.assertIsNone(result.errors)
                        self.assertEqual(data['errors'], [])
                        # assert database entry was deleted
                        self.assertEqual(count - 1, ACE.objects.count())
                        # assert id is returned
                        self.assertEqual(data['aCE']['id'], instance.gid)
                        # rollback
                        transaction.set_rollback(True)
            # logout user
            self.client.logout()
