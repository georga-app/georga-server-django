from os import listdir
from os.path import isfile, join

from graphql_jwt.testcases import JSONWebTokenTestCase, JSONWebTokenClient
from graphql_jwt.shortcuts import get_token
from graphql_jwt.settings import jwt_settings

FIXTURES_DIR = join("georga", "fixtures")
TOKEN_CACHE = {}


class CachedJSONWebTokenClient(JSONWebTokenClient):
    def authenticate(self, user):
        if user.email not in TOKEN_CACHE:
            TOKEN_CACHE[user.email] = get_token(user)
        self._credentials = {
            jwt_settings.JWT_AUTH_HEADER_NAME: (
                f"{jwt_settings.JWT_AUTH_HEADER_PREFIX} {TOKEN_CACHE[user.email]}"
            ),
        }


class SchemasTestCase(JSONWebTokenTestCase):
    client_class = CachedJSONWebTokenClient
    fixtures = [f for f in listdir(FIXTURES_DIR) if isfile(join(FIXTURES_DIR, f))]
