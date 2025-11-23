FROM python:3.14-slim

# set work directory
WORKDIR /opt/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg build-essential \
    && rm -rf /var/lib/apt/lists/*

# install python packages
COPY ./requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# copy project
COPY . .

# scripts
# scripts
COPY ./docker/django.sh .
COPY ./docker/celery.sh .
RUN chmod +x ./django.sh ./celery.sh
