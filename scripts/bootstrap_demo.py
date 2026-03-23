"""
Demo pipeline bootstrap script.
Sets up three demo scenarios:
  1. File Upload        — 1 stage:  download URL → upload to S3
  2. Image Resize       — 2 stages: resize to 50% → upload resized image to S3
  3. Image Export       — 4 stages: normalize → strip EXIF → generate WebP variants → upload manifest to S3

Run with: python manage.py shell < bootstrap_demo.py
"""
import os
from django.core.files.base import ContentFile
from reference.models import Workspace, Source, PluginRepo, Plugin, DataType, ProcessingStage
from django.contrib.auth.models import User

BASE = "/home/ubuntu/.openclaw/workspace/uddp/pipeline_plugins"


def load_plugin(repo, name, filename):
    with open(os.path.join(BASE, filename), "rb") as f:
        content = f.read()
    plugin, created = Plugin.objects.get_or_create(name=name, repo=repo)
    if created or not plugin.file:
        plugin.file.save(filename, ContentFile(content), save=True)
    print(f"✓ Plugin: {plugin} | File: {plugin.file.name}")
    return plugin


# ── Shared infrastructure ────────────────────────────────────────────────────

# Workspace
workspace, _ = Workspace.objects.get_or_create(name="Demo")
print(f"✓ Workspace: {workspace}")

# Plugin Repo
repo, _ = PluginRepo.objects.get_or_create(name="Built-in", defaults={"url": "http://localhost"})
print(f"✓ PluginRepo: {repo}")

# Plugins — shared
upload_plugin     = load_plugin(repo, "Upload to S3",       "upload_to_s3.py")
resize_plugin     = load_plugin(repo, "Resize Image",       "resize_image.py")

# Plugins — image export pipeline
normalize_plugin  = load_plugin(repo, "Normalize Image",    "normalize_image.py")
strip_exif_plugin = load_plugin(repo, "Strip EXIF",         "strip_exif.py")
variants_plugin   = load_plugin(repo, "Generate Variants",  "generate_variants.py")
manifest_plugin   = load_plugin(repo, "Upload Manifest",    "upload_manifest.py")

print()

# ── Scenario 1: File Upload ──────────────────────────────────────────────────
source1, _ = Source.objects.get_or_create(
    name="Demo Source — File Upload",
    workspace=workspace,
    defaults={"key": "demo-token-upload"},
)
print(f"✓ Source 1: {source1} | Token: {source1.key}")

dt1, _ = DataType.objects.get_or_create(
    name="File Upload",
    source=source1,
    workspace=workspace,
    defaults={"source_code": "file_upload"},
)
if not dt1.source_code:
    dt1.source_code = "file_upload"
    dt1.save()

ProcessingStage.objects.get_or_create(
    data_type=dt1, step=1, workspace=workspace,
    defaults={"plugin": upload_plugin, "active": True},
)
print(f"✓ Scenario 1: File Upload | source_code=file_upload | 1 stage")

# ── Scenario 2: Image Resize + Upload ───────────────────────────────────────
source2, _ = Source.objects.get_or_create(
    name="Demo Source — Image Resize",
    workspace=workspace,
    defaults={"key": "demo-token-resize"},
)
print(f"✓ Source 2: {source2} | Token: {source2.key}")

dt2, _ = DataType.objects.get_or_create(
    name="Image Resize",
    source=source2,
    workspace=workspace,
    defaults={"source_code": "image_resize"},
)
if not dt2.source_code:
    dt2.source_code = "image_resize"
    dt2.save()

ProcessingStage.objects.get_or_create(
    data_type=dt2, step=1, workspace=workspace,
    defaults={"plugin": resize_plugin, "active": True},
)
ProcessingStage.objects.get_or_create(
    data_type=dt2, step=2, workspace=workspace,
    defaults={"plugin": upload_plugin, "active": True},
)
print(f"✓ Scenario 2: Image Resize | source_code=image_resize | 2 stages")

# ── Scenario 3: Multi-Format Image Export ───────────────────────────────────
source3, _ = Source.objects.get_or_create(
    name="Demo Source — Image Export",
    workspace=workspace,
    defaults={"key": "demo-token-export"},
)
print(f"✓ Source 3: {source3} | Token: {source3.key}")

dt3, _ = DataType.objects.get_or_create(
    name="Image Export",
    source=source3,
    workspace=workspace,
    defaults={"source_code": "image_export"},
)
if not dt3.source_code:
    dt3.source_code = "image_export"
    dt3.save()

ProcessingStage.objects.get_or_create(
    data_type=dt3, step=1, workspace=workspace,
    defaults={"plugin": normalize_plugin, "active": True},
)
ProcessingStage.objects.get_or_create(
    data_type=dt3, step=2, workspace=workspace,
    defaults={"plugin": strip_exif_plugin, "active": True},
)
ProcessingStage.objects.get_or_create(
    data_type=dt3, step=3, workspace=workspace,
    defaults={"plugin": variants_plugin, "active": True},
)
ProcessingStage.objects.get_or_create(
    data_type=dt3, step=4, workspace=workspace,
    defaults={"plugin": manifest_plugin, "active": True},
)
print(f"✓ Scenario 3: Image Export | source_code=image_export | 4 stages")

# ── Superuser ────────────────────────────────────────────────────────────────
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser("admin", "admin@demo.local", "admin123")
    print("✓ Superuser: admin / admin123")
else:
    print("✓ Superuser already exists")

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("Demo pipelines ready!")
print()
print("Scenario 1 — File Upload:")
print("  curl -X POST http://51.44.14.81:8000/publish/ \\")
print('    -H "Authorization: Token demo-token-upload" \\')
print('    -H "Content-Type: application/json" \\')
print('    -d \'{"type": "file_upload", "url": "https://uddp-demo.s3.eu-west-3.amazonaws.com/source/rick.png"}\'')
print()
print("Scenario 2 — Image Resize + Upload:")
print("  curl -X POST http://51.44.14.81:8000/publish/ \\")
print('    -H "Authorization: Token demo-token-resize" \\')
print('    -H "Content-Type: application/json" \\')
print('    -d \'{"type": "image_resize", "url": "https://uddp-demo.s3.eu-west-3.amazonaws.com/source/rick.png"}\'')
print()
print("Scenario 3 — Multi-Format Image Export:")
print("  curl -X POST http://51.44.14.81:8000/publish/ \\")
print('    -H "Authorization: Token demo-token-export" \\')
print('    -H "Content-Type: application/json" \\')
print('    -d \'{"type": "image_export", "url": "https://uddp-demo.s3.eu-west-3.amazonaws.com/source/rick.png"}\'')
print()
print("Then check status (replace <task_id> with the returned task number):")
print("  curl http://51.44.14.81:8000/publish/status/<task_id>/ \\")
print('    -H "Authorization: Token demo-token-export"')
print("=" * 60)
