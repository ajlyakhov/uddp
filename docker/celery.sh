#!/bin/sh

WORKERS=${UDDP_WORKERS_COUNT:-2}
celery -A conf worker -E -l info -B -c $WORKERS
