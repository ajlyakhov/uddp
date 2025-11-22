
import os
import sys
import django
from django.conf import settings

# Configure minimal settings
if not settings.configured:
    settings.configure(
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
    )
    django.setup()

from django.template import Context

def test_context_copy():
    c = Context({'a': 1})
    print(f"Original dicts: {c.dicts}")
    try:
        copy_c = c.__copy__()
        print(f"Copied dicts: {copy_c.dicts}")
    except Exception as e:
        print(f"Error during copy: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_context_copy()
