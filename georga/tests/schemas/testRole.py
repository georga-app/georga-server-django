# TODO: list, create, update, delete
from . import ListQueryTestCase


class ListRolesTestCase(ListQueryTestCase):
    operation = """
    query (
      [VARIABLES]
    ) {
      listRoles (
        [ARGUMENTS]
      ){
        [PAGEINFO]
        edges {
          cursor
          node {
            createdAt
            modifiedAt
            shift {
              id
            }
            name
            description
            quantity
            isActive
            isTemplate
            needsAdminAcceptance
            id
          }
        }
      }
    }
    """
