import random

from django.db import transaction
from graphql_jwt.exceptions import JSONWebTokenError

from . import ListQueryTestCase, MutationTestCase
from ...models import (
    Device,
    Person,
)


class ListDevicesTestCase(ListQueryTestCase):
    operation = """
    query (
        [VARIABLES]
    ){
        listDevices (
            [ARGUMENTS]
        ) {
            [PAGEINFO]
            edges {
                cursor
                node {
                    id
                    createdAt
                    modifiedAt
                    name
                    osType
                    osVersion
                    appType
                    appVersion
                    appStore
                    pushTokenType
                    pushToken
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

    def test_object_permits_user(self):
        """authorized user can list all and only permitted entries"""
        # prepare variables
        usernames = [
            "helper.001@georga.test",
            "helper.002@georga.test",
            "helper.003@georga.test",
            "helper.004@georga.test",
            "helper.005@georga.test",
        ]
        # iterate over usernames
        for username in usernames:
            user = Person.objects.get(username=username)
            expected_queryset = Device.filter_permitted(user, 'read')
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


class CreateDeviceTestCase(MutationTestCase):
    operation = """
    mutation (
        $name: String!
        $osType: String!
        $osVersion: String!
        $appType: String!
        $appVersion: String!
        $appStore: String!
        $pushTokenType: String!
        $pushToken: String!
    ) {
        createDevice (
            input: {
                name: $name
                osType: $osType
                osVersion: $osVersion
                appType: $appType
                appVersion: $appVersion
                appStore: $appStore
                pushTokenType: $pushTokenType
                pushToken: $pushToken
            }
        ) {
            device {
                id
                createdAt
                modifiedAt
                name
                osType
                osVersion
                appType
                appVersion
                appStore
                pushTokenType
                pushToken
            }
            errors {
                field
                messages
            }
        }
    }
    """

    # TODO:
    # - wrong inputs (empty strings, wrong choices)

    # permission --------------------------------------------------------------

    def test_login_required(self):
        """non authenticated user gets a permission error"""
        # execute operation
        result = self.client.execute(
            self.operation,
            variables={
                'name': "<UNCHECKED>",
                'osType': "<UNCHECKED>",
                'osVersion': "<UNCHECKED>",
                'appType': "<UNCHECKED>",
                'appVersion': "<UNCHECKED>",
                'appStore': "<UNCHECKED>",
                'pushTokenType': "<UNCHECKED>",
                'pushToken': "<UNCHECKED>",
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
        count = Device.objects.count()
        usernames = [
            "helper.001@georga.test",
            "helper.002@georga.test",
            "helper.003@georga.test",
            "helper.004@georga.test",
            "helper.005@georga.test",
        ]
        # iterate over usernames
        for username in usernames:
            user = Person.objects.get(username=username)
            with self.subTest(user=user, permission="allowed"):
                # authenticate user
                self.client.authenticate(user)
                # execute operation
                result = self.client.execute(
                    self.operation,
                    variables={
                        'name': "Device Name",
                        'osType': random.choice(Device.OS_TYPES)[0],
                        'osVersion': "1.0",
                        'appType': random.choice(Device.APP_TYPES)[0],
                        'appVersion': "1.0",
                        'appStore': random.choice(Device.APP_STORES)[0],
                        'pushTokenType': random.choice(Device.PUSH_TOKEN_TYPES)[0],
                        'pushToken': "push-token",
                    }
                )
                # assert no error
                self.assertIsNone(result.errors)
                # assert database entry was created
                self.assertEqual(count + 1, Device.objects.count())
                # prepare query results
                data = next(iter(result.data.values()))
                entry = Device.objects.last()
                # assert id is returned
                self.assertEqual(data['device']['id'], entry.gid)
                # delete entry
                entry.delete()
                # logout user
                self.client.logout()


class UpdateDeviceTestCase(MutationTestCase):
    operation = """
    mutation (
        $id: ID!
    ) {
        deleteDevice (
            input: {
                id: $id
            }
        ) {
            device {
                id
                createdAt
                modifiedAt
                name
                osType
                osVersion
                appType
                appVersion
                appStore
                pushTokenType
                pushToken
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

    def test_object_permits_user(self):
        """authorized user can delete only permitted entries"""
        # prepare variables
        count = Device.objects.count()
        usernames = [
            "helper.001@georga.test",
            "helper.002@georga.test",
            "helper.003@georga.test",
            "helper.004@georga.test",
            "helper.005@georga.test",
        ]
        # iterate over usernames
        for username in usernames:
            # authenticate user
            user = Person.objects.get(username=username)
            self.client.authenticate(user)
            # get querysets
            allowed = Device.filter_permitted(user, 'delete')
            denied = Device.objects.difference(allowed)
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
                    self.assertEqual(count, Device.objects.count())
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
                        self.assertEqual(count - 1, Device.objects.count())
                        # assert id is returned
                        self.assertEqual(data['device']['id'], instance.gid)
                        # rollback
                        transaction.set_rollback(True)
            # logout user
            self.client.logout()


class DeleteDeviceTestCase(MutationTestCase):
    operation = """
    mutation (
        $id: ID!
    ) {
        deleteDevice (
            input: {
                id: $id
            }
        ) {
            device {
                id
                createdAt
                modifiedAt
                name
                osType
                osVersion
                appType
                appVersion
                appStore
                pushTokenType
                pushToken
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

    def test_object_permits_user(self):
        """authorized user can delete only permitted entries"""
        # prepare variables
        count = Device.objects.count()
        usernames = [
            "helper.001@georga.test",
            "helper.002@georga.test",
            "helper.003@georga.test",
            "helper.004@georga.test",
            "helper.005@georga.test",
        ]
        # iterate over usernames
        for username in usernames:
            # authenticate user
            user = Person.objects.get(username=username)
            self.client.authenticate(user)
            # get querysets
            allowed = Device.filter_permitted(user, 'delete')
            denied = Device.objects.difference(allowed)
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
                    self.assertEqual(count, Device.objects.count())
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
                        self.assertEqual(count - 1, Device.objects.count())
                        # assert id is returned
                        self.assertEqual(data['device']['id'], instance.gid)
                        # rollback
                        transaction.set_rollback(True)
            # logout user
            self.client.logout()
