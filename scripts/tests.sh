#!/bin/bash

$(dirname "$0")/migrate.sh

python /code/publicsite/manage.py test