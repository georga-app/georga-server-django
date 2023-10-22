#!/bin/bash
# For copyright and license terms, see COPYRIGHT.md (top level of repository)
# Repository: https://github.com/georga-app/georga-server-django

KEYDIR=$(dirname "$0")/../keys
mkdir -p $KEYDIR
openssl genrsa -out $KEYDIR/jwtRS256.pem 4096
openssl rsa -in $KEYDIR/jwtRS256.pem -pubout -out $KEYDIR/jwtRS256_pub.pem
