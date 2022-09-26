# flake8: noqa
# script for manual testing
# ./manage.py shell
# >>> import * from scripts.debug

# imports ---------------------------------------------------------------------

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, F
from georga.schemas import *

from django.db import connection
from django.db import reset_queries

# objects ---------------------------------------------------------------------

persons = Person.objects.all()
aces = ACE.objects.all()

org_admin = Person.objects.get(email="organization@georga.test")
pro_admin = Person.objects.get(email="project@georga.test")
ope_admin = Person.objects.get(email="operation@georga.test")
helper = Person.objects.get(email="helper.001@georga.test")

org1 = Organization.objects.get(pk=100)
org2 = Organization.objects.get(pk=200)
org3 = Organization.objects.get(pk=300)

pro1 = Project.objects.get(pk=100)
pro2 = Project.objects.get(pk=200)
pro3 = Project.objects.get(pk=300)

ope1 = Operation.objects.get(pk=100)
ope2 = Operation.objects.get(pk=200)
ope3 = Operation.objects.get(pk=300)

tas1 = Task.objects.get(pk=100)
tas2 = Task.objects.get(pk=200)
tas3 = Task.objects.get(pk=300)

shi1 = Shift.objects.get(pk=100)
shi2 = Shift.objects.get(pk=101)
shi3 = Shift.objects.get(pk=102)

ace0 = ACE()
ace0.person = pro_admin
ace0.access_object = pro2
ace0.ace_string = "ADMIN"
ace1 = ACE.objects.get(pk=100)
ace2 = ACE.objects.get(pk=101)
ace3 = ACE.objects.get(pk=200)

msg0 = Message()
msg0.scope = org1
msg0.title = "TestMessage Title"
msg0.contents = "TestMessage Content"
msg0.priority = "NORMAL"
msg0.category = "NEWS"
msg0.delivery_state_email = "NONE"
msg0.delivery_state_push = "NONE"
msg0.delivery_state_sms = "NONE"
msg1 = Message.objects.get(pk=100)
msg2 = Message.objects.get(pk=101)
msg3 = Message.objects.get(pk=102)

# profiling -------------------------------------------------------------------

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
    ace1.permits(org_admin, 'read')
    ace1.permits(org_admin, 'read')


@profile_queries
def profile_filter_permitted():
    bool(ACE.filter_permitted(None, None, org_admin, 'read'))
    bool(ACE.filter_permitted(None, None, org_admin, 'read'))


@profile_queries
def profile_cached_property():
    print(org_admin.admin_organizations)
    print(org_admin.admin_organizations)


