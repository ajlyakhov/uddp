#!/bin/bash

python3 manage.py migrate
python3 manage.py collectstatic --noinput
gunicorn conf.asgi:application -w 3 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
