import os
import sys
# Force reload 4
from datetime import timedelta
from pathlib import Path
# from storages.backends.s3boto3 import S3Boto3Storage


BASE_DIR = Path(__file__).resolve().parent.parent

# Monkeypatch for Django 5.1.3 + Python 3.14 compatibility
try:
    from django.template.context import BaseContext
    def patched_base_context_copy(self):
        duplicate = self.__class__.__new__(self.__class__)
        duplicate.__dict__ = self.__dict__.copy()
        duplicate.dicts = self.dicts[:]
        return duplicate
    BaseContext.__copy__ = patched_base_context_copy
except ImportError:
    pass
SECRET_KEY = 'django-insecure-yz=84@zeq(@_!+m9n+mop+s&uiilq9tr2j)+=_)h+zdib@59*j'
DEBUG = True if os.getenv('DEBUG', 'True') == 'True' else False
if DEBUG:
    ALLOWED_HOSTS = []
else:
    ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS').split(',')
    CSRF_TRUSTED_ORIGINS = [os.getenv('SERVER_NAME'), ]
ENVIRONMENT_NAME = os.environ.get('ENVIRONMENT_NAME', 'dev')


# Application definition
APPS = [
    'core',
    'reference',
    'setup',
]

LIBS = [
    # 'storages',
    'corsheaders',
    'django_extensions',
    'django_prometheus',
    'django_celery_results',
]

CORE = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

INSTALLED_APPS = CORE + LIBS + APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'conf.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'conf.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'en-US'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_ROOT = os.path.join(PROJECT_DIR, 'data')
MEDIA_URL = '/media/'

STATICFILES_LOCATION = "static"
# STATICFILES_STORAGE = "conf.s3static.StaticStorage"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL", "")
AWS_S3_ACCESS_KEY_ID = os.getenv("AWS_S3_ACCESS_KEY_ID", "")
AWS_S3_SECRET_ACCESS_KEY = os.getenv("AWS_S3_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = os.getenv("S3_REGION_NAME", "")


# CELERY
if not DEBUG:
    CELERY_BROKER_URL = os.environ.get('CELERY_REDIS_URL', None)
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
    CELERYD_MAX_TASKS_PER_CHILD = int(os.getenv("CELERY_MAX_TASKS_PER_CHILD", "100"))
    CELERY_TIMEZONE = "UTC"
    CELERY_RESULT_BACKEND = "django-db"
    CELERY_RESULT_EXTENDED = True
    CELERY_RESULT_EXPIRES = timedelta(days=int(os.getenv("CELERY_RESULT_EXPIRES", "7")))
    CELERY_WORKER_SEND_TASK_EVENTS = True
    CELERY_TASK_COMPRESSION = "gzip"
    CELERY_TASK_SEND_SENT_EVENT = True
    CELERY_TASK_TRACK_STARTED = True
    CELERY_TASK_STORE_EAGER_RESULT = True
    CELERY_TASK_STORE_ERRORS_EVEN_IF_IGNORED = True
    CELERY_TASK_IGNORE_RESULT = False
    CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
else:
    CELERY_ALWAYS_EAGER = True

# CORS
CORS_ALLOW_ALL_ORIGINS = True

LOGIN_URL = '/admin/login/'
