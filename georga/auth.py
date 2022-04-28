import jwt
from graphql_jwt.middleware import allow_any

from . import settings


# override allow_any, see https://stackoverflow.com/a/71296685
def handled_allow_any(info, **kwargs):
    try:
        return allow_any(info, **kwargs)
    except AttributeError:
        return False


def jwt_encode(payload):
    return jwt.encode(
        payload, settings.GRAPHQL_JWT['JWT_PRIVATE_KEY'], algorithm="RS256")


def jwt_decode(token):
    return jwt.decode(
        token, settings.GRAPHQL_JWT['JWT_PUBLIC_KEY'], algorithms=["RS256"])
