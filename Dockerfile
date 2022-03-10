FROM python:bullseye

ENV DB_ENGINE="django.db.backends.sqlite3"
ENV DB_NAME="/db.sqlite3"

COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
RUN mkdir /code && cd /code && django-admin startproject publicsite
COPY ./ /code/publicsite/call_for_volunteers/
COPY ./scripts/startup.sh /startup.sh

COPY examplefiles/settings.py /code/publicsite/publicsite/settings.py
COPY examplefiles/urls.py /code/publicsite/publicsite/urls.py

WORKDIR /code/publicsite/
RUN chmod +x /startup.sh && chmod +x /code/publicsite/call_for_volunteers/scripts/*
CMD /startup.sh