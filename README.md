# GeoRGA Server Django

## What is this?


## Install for development
Generate the certs for JWT `./scripts/generate_jwt_certs.sh`

Execute the migration in your DB `python manage.py migrate`

Load the demo data `python manage.py loaddata georga/initial_data/*`

Start the server `python manage.py runserver`

You can login under /admin/ with the user `admin@georga.app` and `verysafePassword`

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
