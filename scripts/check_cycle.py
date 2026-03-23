import sys
import os
from pathlib import Path

# Mock settings to avoid actual Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conf.settings')

try:
    from django.template import context
    print("Imported django.template.context successfully")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Exception: {e}")
