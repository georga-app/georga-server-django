from . import ListQueryTestCase
from ...schemas import QueryType

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
    field = QueryType.list_aces
    # TODO: use schema introspection to fetch objects
    operation = listAcesQuery
