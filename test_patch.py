
import os
import sys
import django
from django.conf import settings
import copy

# Configure minimal settings
if not settings.configured:
    settings.configure(
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
    )
    django.setup()

from django.template import Context
from django.template.context import BaseContext

# Monkeypatch BaseContext.__copy__
def patched_base_context_copy(self):
    # Create a new instance without calling super().__copy__() if it fails
    duplicate = self.__class__.__new__(self.__class__)
    duplicate.__dict__ = self.__dict__.copy()
    duplicate.dicts = self.dicts[:]
    return duplicate

BaseContext.__copy__ = patched_base_context_copy

def test_context_copy():
    c = Context({'a': 1})
    print(f"Original dicts: {c.dicts}")
    try:
        copy_c = c.__copy__()
        print(f"Copied dicts: {copy_c.dicts}")
        print("Copy successful with patch!")
    except Exception as e:
        print(f"Error during copy: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_context_copy()
