# GeoRGA Server Django

## What is this?


## Install for development
Generate the certs for JWT `./scripts/generate_jwt_certs.sh`

Execute the migration in your DB `python manage.py migrate`

Load the demo data `python manage.py loaddata georga/fixtures/*`

Start the server `python manage.py runserver`

You can login under /admin/ with the superadmin user `admin@georga.test` and `georga`

Further current testusers are (use password `georga` for all accounts):

- Registered helpers
    - `helper.001@georga.test`
    - `helper.002@georga.test`
    - `helper.003@georga.test`
    - `helper.004@georga.test`
    - `helper.005@georga.test`
- Organization admins
    - `organization@georga.test`
    - `organization.admin.1@frenchbluecircle.test`
    - `organization.admin.1@seaeyesinternational.test`
    - `organization.admin.1@cyberaidworldwide.test`
- Project admins
    - `project@georga.test`
    - `project.admin.1@frenchbluecircle.test`
    - `project.admin.1@seaeyesinternational.test`
    - `project.admin.1@cyberaidworldwide.test`
- Operation admin
    - `operation@georga.test`
    - `operation.admin.1@frenchbluecircle.test`
    - `operation.admin.1@seaeyesinternational.test`
    - `operation.admin.1@cyberaidworldwide.test`

## Upgrade

1. Unpin versions in `requirements.txt`
2. Upgrade pip packages

    docker compose run --rm --service-ports server bash
    > pip install --upgrade -r requirements.txt

3. Test/Fix startup

    > ./scripts/startup.sh

4. Run/Fix tests

    > ./manage.py test

5. Pin new versions in `requirements.txt`

## Contribute


## Deploy


## Test

Run django tests:

    ./manage.py test
    ./manage.py test --verbosity 2 --failfast --timing --keepdb --parallel auto
    ./manage.py test --verbosity 2 --keepdb --pdb

## UML Diagram

    docker compose run --rm --service-ports server bash
    > apt-get update && apt-get install -y graphviz graphviz-dev
    > pip install django-extensions pygraphviz
    > vi settings.py
        INSTALLED_APPS = [
            [...]
            'django_extensions',
        ]
    > ./manage.py graph_models -a \
        -X Mixin*,Abstract*,Group,Permission,ContentType,Session,LogEntry,Site \
        -o georga-uml.png

## Use

### GraphQL

When you open http://localhost:8000/graphql you will be presented with GraphiQL an in-browser GraphQL client.
In GraphiQL you find the api docs in the top right corner.

#### Obtain an JWT
```
mutation {
  tokenAuth(email:"admin@georga.test", password:"georga") {
    payload
    refreshExpiresIn
    token
  }
}
```


#### Get all Users
To query data from the server you need to send an Header including your JWT with each request you make.
In GraphiQL you can archive this by setting in the bottom left under `Request Headers` this:
```
{
  "Authorization": "JWT <YOUR_TOKEN>"
}
```
And then execute the query:
```
query {
  listPersons {
    edges {
      node {
        email
      }
    }
  }
}
```

#### Initial and demo data
For initial contents and/or demodata in the database, the yaml-files in folder fixtures can be used.

Load the demo data `python manage.py loaddata georga/fixtures/*`

For getting the password hash for a users' password, e.g. to insert it into demodata in `fixtures/005_person.yaml` the following custom management command can be used:

`python manage.py get_pw_hash passwordstring`


#### Test Subscriptions
Note: GraphiQL does not support subscriptions.
Use another desktop client like Altair or Playground instead.

```
subscription {
  testSubscription() {
    event
  }
}
```

To test push messages, use the testSubscription mutation:

```
mutation {
  testSubscription(message="message") {
    response
  }
}
```

#### Relay
Relay is a [specification](https://relay.dev/docs/guides/graphql-server-specification/)
to provide a consistent interface for global identification and pagination.
See also [graphene python docs](https://docs.graphene-python.org/en/latest/relay/).

In all graphql requests, the id field is masked by the relay global ID,
which is a base64 coded string `<model>:<uuid>`.

