FROM python:bookworm

WORKDIR /code
COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
CMD /code/scripts/startup.sh
