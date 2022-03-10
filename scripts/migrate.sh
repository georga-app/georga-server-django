#!/bin/bash

export MIGRATE=True
python /code/publicsite/manage.py migrate
export MIGRATE=False