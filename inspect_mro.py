
import os
import sys
import django
from django.conf import settings

if not settings.configured:
    settings.configure()
    django.setup()

from django.template import Context, BaseContext

print(f"Context MRO: {Context.mro()}")
print(f"BaseContext MRO: {BaseContext.mro()}")
