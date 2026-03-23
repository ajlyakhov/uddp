# UDDP Developer Guide

**For developers building plugins, extending the pipeline, or operating UDDP.**

---

## Architecture Overview

UDDP is a Django application with asynchronous task processing via Celery and Redis.

```
HTTP Request
    │
    ▼
┌─────────────────────────────┐
│  Django (PublishView)       │  — validates token, resolves DataType,
│  POST /publish/             │    creates Task record, enqueues job
└────────────┬────────────────┘
             │ enqueue via Celery
             ▼
┌─────────────────────────────┐
│  Redis                      │  — message broker
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  Celery Worker              │  — picks up task from queue
│  core.tasks.run_task()      │
└────────────┬────────────────┘
             │ loads stages
             ▼
┌─────────────────────────────────────────────────────┐
│  Task Runner                                        │
│  For each ProcessingStage (ordered by step):        │
│    1. Import plugin module from stored .py file     │
│    2. Call plugin.execute(task_proxy)               │
│    3. Persist context + log updates to database     │
│    4. If exception: mark task as error, stop chain  │
└─────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  Task record (Django ORM)   │  — status, context, log, progress
└─────────────────────────────┘
```

### Key Components

| Component | Location | Responsibility |
|-----------|----------|----------------|
| `PublishView` | `core/views.py` | HTTP entry point, token auth, task creation |
| `run_task` | `core/tasks.py` | Celery task — orchestrates stage execution |
| `Task` | `core/models.py` | Stores task state, context, log, progress |
| `TaskProxy` | `core/tasks.py` (or similar) | Wraps Task model, exposes plugin interface |
| `Plugin` | `reference/models.py` | Stores plugin `.py` file in database |
| `ProcessingStage` | `reference/models.py` | Links DataType → Plugin, with step order |
| `DataType` | `reference/models.py` | Maps `source_code` string to a pipeline |
| `Source` | `reference/models.py` | API token authentication |

### Data Flow

1. `POST /publish/` arrives with `Authorization: Token <key>` and `{"type": "image_export", "url": "..."}`
2. `PublishView` looks up the `Source` by token, finds the `DataType` by `source_code`, creates a `Task` with `meta={"type": "image_export", "url": "..."}`
3. The task is pushed onto the Celery queue
4. The Celery worker calls `run_task(task_id)`
5. `run_task` fetches all active `ProcessingStage` records for the DataType, sorted by `step`
6. For each stage, it dynamically imports the plugin module and calls `execute(task_proxy)`
7. The plugin can read/write `task.context` and append to `task.log`
8. After all stages complete, the task is marked `status=1` (Done)
9. If any stage raises an exception, the task is marked `status=3` (Error)

---

## The Plugin Interface

Every plugin is a Python module (`.py` file) that must expose a single top-level function:

```python
def execute(task):
    ...
```

The `task` argument is a proxy object that gives you everything you need.

### `task.id`

The unique integer ID of the current task. Use this to namespace uploaded files:

```python
s3_key = f"uploads/{task.id}/myfile.png"
```

### `task.meta`

A dictionary containing the original JSON body from the publish request. This is **read-only** — it is the raw input from the caller.

```python
url = task.meta.get("url")        # "https://example.com/photo.jpg"
type_ = task.meta.get("type")     # "image_export"
custom = task.meta.get("custom_field")  # whatever the caller sent
```

### `task.context`

A mutable dictionary shared across all stages. When stage 1 writes something to context, stage 2 can read it. This is how stages communicate.

```python
# Reading from a previous stage
local_file = task.context.get("local_file")
variants = task.context.get("variants")
tmp_dir = task.context.get("tmp_dir", "/tmp")
```

> **Note:** `task.context` is read-only as a plain dict. To write to it, use `task.set_context()`.

### `task.set_context(dict)`

Merges the provided dictionary into `task.context`. Keys are added or overwritten; existing unrelated keys are preserved.

```python
task.set_context({
    "local_file": "/tmp/abc/photo.png",
    "original_size": "1920x1080",
})
# Existing keys (e.g. "tmp_dir") are untouched
```

### `task.logging(type, message)`

Appends a log entry to the task's log. The entry is persisted to the database so it can be read via the admin panel or status API.

```python
task.logging("INFO", "Starting download...")
task.logging("INFO", f"File saved to {local_path}")
task.logging("WARNING", "Image smaller than expected, skipping resize")
```

Suggested log types: `"INFO"`, `"WARNING"`, `"ERROR"` (errors should also raise an exception).

### `task.set_error(message)`

Marks the task as failed and sets an error message. After calling this, you should also raise an exception to stop the pipeline chain.

```python
if not url:
    task.set_error("Missing 'url' in task meta")
    raise ValueError("Missing 'url' in task meta")
```

In most cases it's simpler to just `raise` — the task runner will catch the exception and mark the task as error automatically.

---

## How Stages Are Chained

The task runner executes stages as follows:

1. Fetch all `ProcessingStage` records where:
   - `data_type` matches the task's DataType
   - `active = True`
2. Sort them by `step` (ascending: 1, 2, 3, 4…)
3. For each stage:
   - Load the plugin's `.py` file from the database
   - Write it to a temporary location and import it as a module
   - Call `plugin.execute(task_proxy)`
   - Save the updated `task.context` and log to the database
   - Update `task.progress`
4. If any stage raises an uncaught exception:
   - Mark task `status = 3` (Error)
   - Record the error message and traceback in the log
   - Stop — do not execute further stages

### `tmp_dir` Sharing

The task runner creates a temporary directory for each task run and injects its path into the initial context:

```python
task.context["tmp_dir"] = "/tmp/uddp_task_42_abc123/"
```

Plugins that need to write intermediate files should use this directory:

```python
tmp_dir = task.context.get("tmp_dir", "/tmp")
output_path = os.path.join(tmp_dir, "output.png")
```

Files in `tmp_dir` persist for the duration of the pipeline execution. After all stages complete, the directory may be cleaned up automatically.

---

## Writing a Plugin: Step-by-Step

### 1. Create the Python file

Each plugin is a single `.py` file with an `execute(task)` function.

```python
# my_plugin.py

import os
import requests


def execute(task):
    # 1. Read inputs from task.meta (raw request) or task.context (prior stages)
    url = task.meta.get("url")
    if not url:
        raise ValueError("No 'url' in task meta")

    # 2. Log progress
    task.logging("INFO", f"Processing URL: {url}")

    # 3. Do the work
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    # 4. Save intermediate files using tmp_dir
    tmp_dir = task.context.get("tmp_dir", "/tmp")
    output_path = os.path.join(tmp_dir, "downloaded_file.bin")
    with open(output_path, "wb") as f:
        f.write(response.content)

    # 5. Pass results to the next stage via set_context
    task.set_context({
        "local_file": output_path,
        "content_type": response.headers.get("Content-Type", ""),
    })

    task.logging("INFO", f"File saved: {output_path}")
    # 6. No explicit return needed — just don't raise, and the stage is considered success
```

### 2. Key rules

- **One function:** The file must contain `def execute(task):` at the top level
- **Raise on error:** If something goes wrong, raise an exception. The task runner will catch it, log it, and mark the task as failed
- **Use `tmp_dir`:** Don't hardcode `/tmp` — always use `task.context.get("tmp_dir", "/tmp")`
- **Log liberally:** Use `task.logging("INFO", ...)` at each significant step. This is how you (and admins) debug failures
- **No side effects on import:** Don't run code at module level — only inside `execute()`
- **Keep it focused:** One plugin = one responsibility

### 3. Imports and dependencies

Plugins can import any Python package that is installed in the UDDP virtualenv. Common ones:

```python
import io
import os
import json
from urllib.parse import urlparse

import requests          # HTTP downloads
from PIL import Image    # Image processing (Pillow)
import boto3             # AWS S3
```

If your plugin needs a new dependency, add it to `requirements.txt` and redeploy.

---

## Registering a Plugin via Admin

1. Go to **Admin → Reference → Plugins → Add Plugin**
2. Fill in:
   - **Name:** a descriptive name (e.g. "Normalize Image")
   - **Repo:** select the PluginRepo (usually "Built-in")
   - **File:** upload your `.py` file
3. Save

The plugin is now stored in the database. Add it to a pipeline by creating a `ProcessingStage`.

To update a plugin, edit it in the admin and re-upload the `.py` file. The change takes effect on the next task run.

---

## Testing Plugins Locally

You can test a plugin without running the full Django/Celery stack by creating a mock task object:

```python
# test_my_plugin.py

import os
import tempfile

# ── Mock TaskProxy ──────────────────────────────────────────────────────────

class MockTask:
    def __init__(self, meta=None, context=None):
        self.id = 999
        self.meta = meta or {}
        self.context = context or {}
        self._log = []

    def logging(self, level, message):
        entry = f"[{level}] {message}"
        print(entry)
        self._log.append(entry)

    def set_context(self, data):
        self.context.update(data)

    def set_error(self, message):
        print(f"[ERROR] {message}")


# ── Test ────────────────────────────────────────────────────────────────────

import normalize_image  # import your plugin module directly

def test_normalize():
    tmp_dir = tempfile.mkdtemp()
    task = MockTask(
        meta={"url": "https://upload.wikimedia.org/wikipedia/en/a/a9/Example.jpg"},
        context={"tmp_dir": tmp_dir},
    )
    normalize_image.execute(task)

    print("Context after:", task.context)
    assert "local_file" in task.context
    assert os.path.exists(task.context["local_file"])
    print("✓ Test passed")

test_normalize()
```

Run directly:
```bash
cd pipeline_plugins
python test_my_plugin.py
```

---

## Common Patterns

### Downloading a File

```python
import io
import requests
from PIL import Image

def execute(task):
    url = task.meta.get("url")
    task.logging("INFO", f"Downloading: {url}")
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    # As bytes
    raw_bytes = response.content

    # As a PIL Image
    img = Image.open(io.BytesIO(response.content))
```

### Saving to tmp_dir

```python
import os

def execute(task):
    tmp_dir = task.context.get("tmp_dir", "/tmp")
    output_path = os.path.join(tmp_dir, "result.png")
    # ... write to output_path ...
    task.set_context({"local_file": output_path})
```

### Reading a File from a Previous Stage

```python
def execute(task):
    local_file = task.context.get("local_file")
    if not local_file or not os.path.exists(local_file):
        raise ValueError("No local_file in context — run the download stage first")
    # ... process local_file ...
```

### Uploading to S3

```python
import io
import boto3

S3_BUCKET = "my-bucket"
S3_REGION = "eu-west-3"
AWS_ACCESS_KEY = "..."
AWS_SECRET_KEY = "..."

def execute(task):
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=S3_REGION,
    )

    local_file = task.context.get("local_file")
    s3_key = f"uploads/{task.id}/output.png"

    with open(local_file, "rb") as f:
        s3.upload_fileobj(f, S3_BUCKET, s3_key, ExtraArgs={"ContentType": "image/png"})

    url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
    task.set_context({"output_url": url})
    task.logging("INFO", f"Uploaded to {url}")
```

### Passing Structured Data Between Stages

Stage 3 stores a dict of paths:
```python
task.set_context({
    "variants": {
        "thumb": "/tmp/task_42/thumb_150.webp",
        "medium": "/tmp/task_42/medium_800.webp",
        "full": "/tmp/task_42/full.webp",
    }
})
```

Stage 4 reads it:
```python
variants = task.context.get("variants")
if not variants:
    raise ValueError("No variants in context")
for key, path in variants.items():
    # upload each file
    ...
```

---

## Error Handling Best Practices

### Let exceptions propagate

The simplest and most correct pattern — just raise when something is wrong:

```python
def execute(task):
    url = task.meta.get("url")
    if not url:
        raise ValueError("Missing 'url' in task meta")

    response = requests.get(url, timeout=60)
    response.raise_for_status()  # raises on 4xx/5xx — let it propagate
```

The task runner catches all exceptions, logs the traceback, and marks the task as failed.

### Log before raising

Always log something informative before raising so the admin can see what was attempted:

```python
task.logging("INFO", f"Uploading to S3: {s3_key}")
try:
    s3.upload_fileobj(...)
except Exception as e:
    task.logging("INFO", f"S3 upload failed: {e}")
    raise
```

### Validate inputs early

Check that required context keys exist at the start of `execute()`, before doing any expensive work:

```python
def execute(task):
    local_file = task.context.get("local_file")
    if not local_file:
        raise ValueError("No 'local_file' in context — ensure normalize_image ran first")
    if not os.path.exists(local_file):
        raise FileNotFoundError(f"Expected file not found: {local_file}")

    # ... now do the real work ...
```

### Use descriptive error messages

Error messages end up in the task log visible to admins. Make them clear:

```python
# Bad
raise ValueError("error")

# Good
raise ValueError(f"Image download failed with HTTP {response.status_code}: {url}")
```

---

## Adding a Plugin to bootstrap_demo.py

The `bootstrap_demo.py` script is used to set up demo pipelines from scratch. To add a new scenario:

### 1. Load the plugin

Add a `load_plugin()` call near the top with your other plugins:

```python
my_plugin = load_plugin(repo, "My Plugin Name", "my_plugin.py")
```

This reads the `.py` file from `pipeline_plugins/`, stores it in the database, and returns the Plugin object.

### 2. Create the Source

```python
source_x, _ = Source.objects.get_or_create(
    name="Demo Source — My Scenario",
    workspace=workspace,
    defaults={"key": "demo-token-myscenario"},
)
print(f"✓ Source X: {source_x} | Token: {source_x.key}")
```

### 3. Create the DataType

```python
dt_x, _ = DataType.objects.get_or_create(
    name="My Scenario",
    source=source_x,
    workspace=workspace,
    defaults={"source_code": "my_scenario"},
)
if not dt_x.source_code:
    dt_x.source_code = "my_scenario"
    dt_x.save()
```

### 4. Add ProcessingStages

```python
ProcessingStage.objects.get_or_create(
    data_type=dt_x, step=1, workspace=workspace,
    defaults={"plugin": my_plugin, "active": True},
)
# Add more stages as needed
print(f"✓ Scenario X: My Scenario | source_code=my_scenario | 1 stage")
```

### 5. Print a curl example

```python
print("Scenario X — My Scenario:")
print("  curl -X POST http://51.44.14.81:8000/publish/ \\")
print('    -H "Authorization: Token demo-token-myscenario" \\')
print('    -H "Content-Type: application/json" \\')
print('    -d \'{"type": "my_scenario", "url": "https://example.com/file.png"}\'')
```

The `get_or_create` pattern means re-running the script is safe — it won't create duplicates.
