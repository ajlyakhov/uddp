"""
Demo pipeline bootstrap script.
Run with: python manage.py shell < bootstrap_demo.py
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conf.settings')

from django.core.files.base import ContentFile
from reference.models import Workspace, Source, PluginRepo, Plugin, Consumer, DataType, ProcessingStage
from django.contrib.auth.models import User

# 1. Workspace
workspace, _ = Workspace.objects.get_or_create(name="Demo")
print(f"✓ Workspace: {workspace}")

# 2. Source (API key for auth)
source, created = Source.objects.get_or_create(
    name="Demo Source",
    workspace=workspace,
    defaults={"key": "demo-token-123456"}
)
if not created and not source.key:
    source.key = "demo-token-123456"
    source.save()
print(f"✓ Source: {source} | Token: {source.key}")

# 3. Plugin repo (required FK)
repo, _ = PluginRepo.objects.get_or_create(
    name="Local Plugins",
    defaults={"url": "http://localhost"}
)
print(f"✓ PluginRepo: {repo}")

# 4. Plugin — upload the Python file
plugin_path = "/home/ubuntu/.openclaw/workspace/uddp/pipeline_plugins/upload_to_s3.py"
with open(plugin_path, "rb") as f:
    plugin_content = f.read()

plugin, created = Plugin.objects.get_or_create(
    name="Upload to S3",
    repo=repo,
)
if created or not plugin.file:
    plugin.file.save("upload_to_s3.py", ContentFile(plugin_content), save=True)
print(f"✓ Plugin: {plugin} | File: {plugin.file.name}")

# 5. DataType (no consumer needed — plugin handles output)
data_type, _ = DataType.objects.get_or_create(
    name="File Upload",
    source=source,
    workspace=workspace,
    defaults={"source_code": "file_upload", "consumer": None}
)
if not data_type.source_code:
    data_type.source_code = "file_upload"
    data_type.save()
print(f"✓ DataType: {data_type} | source_code: {data_type.source_code}")

# 6. Processing Stage
stage, _ = ProcessingStage.objects.get_or_create(
    data_type=data_type,
    step=1,
    workspace=workspace,
    defaults={"plugin": plugin, "active": True}
)
print(f"✓ ProcessingStage: {stage}")

# 7. Superuser for admin access
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser("admin", "admin@demo.local", "admin123")
    print("✓ Superuser created: admin / admin123")
else:
    print("✓ Superuser already exists")

print()
print("=" * 50)
print("Demo pipeline ready!")
print(f"API token: {source.key}")
print("Publish endpoint: POST /publish/")
print('Example: curl -X POST http://51.44.14.81:8000/publish/ \\')
print('  -H "Authorization: Token demo-token-123456" \\')
print('  -H "Content-Type: application/json" \\')
print('  -d \'{"type": "file_upload", "url": "https://example.com/yourfile.zip"}\'')
print("=" * 50)
