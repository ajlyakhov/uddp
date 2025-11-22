
import os
import sys
# Do not call django.setup()

try:
    from django.template.context import BaseContext
    print("Import successful")
except Exception as e:
    print(f"Import failed: {e}")
