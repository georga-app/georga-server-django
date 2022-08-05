# GeoRGA Server Django

## What is this?


## Install for development
Generate the certs for JWT `./scripts/generate_jwt_certs.sh`

Execute the migration in your DB `python manage.py migrate`

Load the demo data `python manage.py loaddata georga/initial_data/*`

Start the server `python manage.py runserver`

You can login under /admin/ with the user `admin@georga.app` and `verysafePassword`

Further current testusers are:

`simpleuser@georga.app` and `simpleuserPassword`

`staffuser@georga.app` and `staffuserPassword` - is staff but not superuser


## Contribute


## Deploy


## Use

### GraphQL

When you open http://localhost:8000/graphql you will be presented with GraphiQL an in-browser GraphQL client.
In GraphiQL you find the api docs in the top right corner.

#### Obtain an JWT
```
mutation {
  tokenAuth(email:"admin@georga.app", password:"verysafePassword") {
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
  allPersons {
    edges {
      node {
        email
      }
    }
  }
}
```

#### Initial and demo data
For initial contents and/or demodata in the database, the yaml-files in folder initial_data can be used.

Load the demo data `python manage.py loaddata georga/initial_data/*`

For getting the password hash for a users' password, e.g. to insert it into demodata in initial_data/person.yaml the following custom management command can be used:

`python manage.py get_pw_hash passwordstring`


#### Test Subscriptions
Note: GraphiQL does not support subscriptions.
Use another desktop client like Altair or Playground instead.

```
subscription {
  mySubscription(arg1: "arg1", arg2: "arg2") {
    event
  }
}
```

To test push messages, connect to a django shell and broadcast some messages:

```
./manage.py shell
from georga.schemas import TestSubscription
TestSubscription.broadcast(group="TestSubscriptionEvents", payload="message")
```

#### Relay
Relay is a [specification](https://relay.dev/docs/guides/graphql-server-specification/)
to provide a consistent interface for global identification and pagination.
See also [graphene python docs](https://docs.graphene-python.org/en/latest/relay/).

In all graphql requests, the id field is masked by the relay global ID,
which is a base64 coded string `<model>:<uuid>`.

