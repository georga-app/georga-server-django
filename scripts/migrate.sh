#!/bin/bash

export MIGRATE=True
python /code/manage.py migrate
export MIGRATE=False
