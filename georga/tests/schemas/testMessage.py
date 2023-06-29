# TODO: list, create, update, delete
from . import ListQueryTestCase


class ListMessagesTestCase(ListQueryTestCase):
    operation = """
    query (
        [VARIABLES]
        $state: GeorgaMessageStateChoices
        $scope: ID
        $scope_In: [ID]
    ){
        listMessages (
            [ARGUMENTS]
            state: $state
            scope: $scope
            scope_In: $scope_In
        ) {
            [PAGEINFO]
            edges {
                cursor
                node {
                    id
                    createdAt
                    modifiedAt
                    category
                    state
                    title
                    priority
                    delivery
                    emailDelivery
                    pushDelivery
                    smsDelivery
                    scope {
                        __typename
                        ... on OrganizationType {
                            id
                            name
                        }
                        ... on ProjectType {
                            id
                            name
                        }
                        ... on OperationType {
                            id
                            name
                        }
                        ... on TaskType {
                            id
                            name
                        }
                        ... on ShiftType {
                            id
                            startTime
                            endTime
                        }
                    }
                }
            }
        }
    }
    """
