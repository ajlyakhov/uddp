# UDDP Developer Guide

This guide is implementation-focused and maps directly to the current codebase.

## 1) Manage users, teams, and workspaces

### Data model

- `Workspace` -> top-level tenant boundary.
- `Team` -> belongs to a `Workspace`.
- `TeamMember` -> links Django `auth.User` to `Team` with role:
  - `maintainer`
  - `developer`
- Most runtime entities are workspace-scoped (`Source`, `DataType`, `Consumer`, `ProcessingStage`, `DataSource`, `Webhook`, `Task`, logs).

Primary model location: `reference/models.py` and `core/models.py`.

### Option A: Django Admin (recommended)

1. Create users in `/admin/auth/user/`.
2. Create workspace in `/admin/reference/workspace/`.
3. Create team in `/admin/reference/team/` and assign workspace.
4. Add team members in team inline rows (`user` + `role`).

### Option B: Django shell (repeatable bootstrap)

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
from reference.models import Workspace, Team, TeamMember

ws, _ = Workspace.objects.get_or_create(name="Acme")
team, _ = Team.objects.get_or_create(name="Platform", workspace=ws)

user, created = User.objects.get_or_create(username="alice")
if created:
    user.set_password("change-me")
    user.is_staff = True
    user.save()

TeamMember.objects.get_or_create(
    team=team,
    user=user,
    defaults={"role": TeamMember.Roles.MAINTAINER},
)
```

## 2) Create a new pipeline and write plugins

In UDDP, a "pipeline" is:

- `DataType` (content type contract)
- plus ordered `ProcessingStage` rows (`step`, `active`)
- each stage linked to plugin/module execution logic.

### Create pipeline entities (admin flow)

1. Create `Source` (`name`, API `key`, `workspace`).
2. Create output target:
   - `Webhook` and/or `DataSource`
   - then `Consumer` (`type`, `key`, target relation, `workspace`)
3. Create `DataType`:
   - `source`
   - `source_code` (incoming `meta["type"]` value)
   - `consumer`
   - `workspace`
4. Add `ProcessingStage` rows under the `DataType` with ascending `step`.

### Trigger pipeline

`POST /publish/` with `Authorization: Token <source.key>` and JSON payload:

```json
{
  "type": "book",
  "path": "https://example.com/archive.zip"
}
```

`type` must match `DataType.source_code`.

### Plugin/module contract

Runtime entrypoint expected by pipeline executor is:

```python
def execute(task):
    ...
```

The function receives `core.models.Task`. Typical responsibilities:

- read input metadata from `task.meta`
- use/update `task.context` for cross-stage state
- write progress logs with `task.logging(...)` / `task.logging_last(...)`
- create output `DataItem` and/or deliver to target systems
- raise on failure (executor marks task as error)

Minimal plugin skeleton:

```python
from pathlib import Path
from core.models import DataItem

def execute(task):
    tmp_dir = Path(task.context["tmp_dir"])
    source_path = task.meta.get("path")
    if not source_path:
        raise ValueError("meta.path is required")

    task.logging(__name__, f"Processing source: {source_path}")

    # Your processing logic here...

    DataItem.objects.create(
        type=task.data_type,
        source=task.source,
        meta={"processed": True, "source_path": source_path},
        task=task,
        workspace=task.workspace,
    )
```

### Important current-state note

The data model has moved to `ProcessingStage.plugin` (`reference.models.Plugin`), while `core/tasks.py` still executes legacy `stage.module_file` modules. When building new pipeline/plugin flows, verify and align this before production rollout.

## 3) Observe pipeline execution

### API-level status

Call:

`GET /publish/status/<task_id>/` with `Authorization: Token <source.key>`

You get task status, progress, last log line, and error details.

### Admin-level observability

Use:

- `/admin/core/task/`
- `/admin/core/webhooklog/`
- `/admin/core/datasourcelog/`
- `/admin/core/dataitem/`

`Task` stores:

- `status` (`Error`, `Success`, `Processing`)
- `progress`, `total_tasks`, `current_task`
- `log`, `last_log`, `error_description`
- `context`

### Worker/runtime logs

When running via Docker:

```bash
cd docker
docker compose logs -f worker
docker compose logs -f core
```

When running locally:

```bash
celery -A conf worker -l info
python manage.py runserver
```

## 4) Supported libraries for pipelines/plugins

Pipelines/plugins run in the same Python environment as `core` and `worker`.

### Python packages

Defined in `requirements.txt`, including (non-exhaustive):

- Django / Celery / Redis client
- `boto3`, `django-storages`
- `requests`
- `stream-unzip`
- `Pillow`
- `PyJWT`
- `beautifulsoup4`, `html5lib`
- `structlog`
- DB clients: `psycopg`, `psycopg2-binary`

### System packages in containers

Defined in `docker/Dockerfile`:

- `ffmpeg`
- `build-essential`

If your plugin imports a package not in these environments, execution will fail at runtime.

## 5) Add support for new libraries

### Add a new Python library

1. Add dependency to `requirements.txt`.
2. Rebuild runtime images:

```bash
cd docker
docker compose build core worker
docker compose up -d core worker
```

3. Validate import in worker:

```bash
docker compose exec worker python -c "import your_library; print(your_library.__version__)"
```

### Add a new system library/binary

1. Update `docker/Dockerfile` (`apt-get install ...`).
2. Rebuild and restart `core` + `worker` images/containers.
3. Verify binary presence:

```bash
docker compose exec worker bash -lc "which <binary> && <binary> --version"
```

### Add reusable helper support for plugin authors

If a library should become part of your plugin framework contract:

1. Add wrappers/utilities in `core/utils.py` (or a new dedicated module).
2. Keep I/O, retries, and task logging inside helper functions.
3. Use the helper from plugin `execute(task)` modules.
4. Document the new helper contract in this file.

---

## Quick checklist for a new pipeline

- Workspace/team/user created
- Source token created
- Consumer target configured (webhook/datasource)
- DataType created with correct `source_code`
- Ordered processing stages added
- Plugin/module dependencies installed in worker image
- Publish test sent to `/publish/`
- Task observed in `/admin/core/task/` and `/publish/status/<id>/`
