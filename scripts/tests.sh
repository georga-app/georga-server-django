#!/bin/bash

$(dirname "$0")/migrate.sh

python /code/manage.py test
