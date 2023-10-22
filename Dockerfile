# For copyright and license terms, see COPYRIGHT.md (top level of repository)
# Repository: https://github.com/georga-app/georga-server-django

FROM python:3.11-bookworm

WORKDIR /code
COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
CMD /code/scripts/startup.sh
