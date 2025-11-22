import os

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class StaticStorage(S3Boto3Storage):
    location = settings.STATICFILES_LOCATION
    bucket_name = settings.S3_STATIC_BUCKET
    access_key = settings.S3_ID
    secret_key = settings.S3_KEY
    endpoint_url = settings.S3_HOST
    custom_domain = settings.S3_STATIC_HOST
