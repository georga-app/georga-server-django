# flake8: noqa
# script for manual testing
# ./manage.py shell
# >>> import * from scripts.debug

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, F
from georga.schemas import *

from django.db import connection
from django.db import reset_queries


def profile_queries(func):
    """Decorator for performance measures on database queries."""
    def inner_func(*args, **kwargs):
        reset_queries()
        results = func()
        query_info = connection.queries
        print('function_name: {}'.format(func.__name__))
        print('query_count: {}'.format(len(query_info)))
        queries = ['{}\n\n'.format(query['sql']) for query in query_info]
        print('queries: \n\n{}'.format(''.join(queries)))
        return results
    return inner_func


@profile_queries
def profile_permits():
    org_admin = Person.objects.get(email="organization@georga.test")
    ace1 = ACE.objects.get(pk=1)
    ace1.permits(org_admin, 'read')
    ace1.permits(org_admin, 'read')


persons = Person.objects.all()
aces = ACE.objects.all()

org_admin = Person.objects.get(email="organization@georga.test")
pro_admin = Person.objects.get(email="project@georga.test")
ope_admin = Person.objects.get(email="operation@georga.test")
helper = Person.objects.get(email="helper@georga.test")

org1 = Organization.objects.get(pk=1)
org2 = Organization.objects.get(pk=2)
org3 = Organization.objects.get(pk=3)
pro1 = Project.objects.get(pk=1)
pro2 = Project.objects.get(pk=2)
pro3 = Project.objects.get(pk=3)
ope1 = Operation.objects.get(pk=1)
ope2 = Operation.objects.get(pk=2)
ope3 = Operation.objects.get(pk=3)

ace1 = ACE.objects.get(pk=1)
ace2 = ACE.objects.get(pk=2)
ace3 = ACE.objects.get(pk=3)

ace0 = ACE()
ace0.person = pro_admin
ace0.access_object = pro2
ace0.ace_string = "ADMIN"