FROM python:3.11

COPY requirements.txt ./

RUN set -ex; \
    pip install -r requirements.txt; \
    pip install gunicorn; \
    pip install --no-cache-dir -r requirements.txt

ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

COPY ./certs /app/certs

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app