#!/bin/bash

openssl genrsa  -out ../keys/wtRS256.pem 4096
openssl rsa -in ../keys/jwtRS256.pem -pubout -out ../keys/jwtRS256_pub.pem