# For copyright and license terms, see COPYRIGHT.md (top level of repository)
# Repository: https://github.com/georga-app/georga-server-django

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
            participantSet {
              edges {
                node {
                  id
                }
              }
            }
            id
            personAttributes {
              edges {
                node {
                  id
                }
              }
            }
          }
        }
      }
    }
    """
