#!/bin/bash

$(dirname "$0")/migrate.sh

python /code/manage.py runserver 0.0.0.0:8000
