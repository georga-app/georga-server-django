#!/bin/bash
# For copyright and license terms, see COPYRIGHT.md (top level of repository)
# Repository: https://github.com/georga-app/georga-server-django

$(dirname "$0")/migrate.sh

python /code/manage.py test
