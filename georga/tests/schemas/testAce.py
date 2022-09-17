from . import SchemasTestCase

from georga.models import Person

listAcesQuery = """
query ListAces {
    listAces {
        edges {
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


class ACLTestCase(SchemasTestCase):

    def setUp(self):
        self.user = Person.objects.get(email="organization@georga.test")
        self.client.authenticate(self.user)

    def test_some_query(self):
        response = self.client.execute(listAcesQuery)
        print(response)
