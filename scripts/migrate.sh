#!/bin/bash
# For copyright and license terms, see COPYRIGHT.md (top level of repository)
# Repository: https://github.com/georga-app/georga-server-django

export MIGRATE=True
python /code/manage.py migrate
export MIGRATE=False
