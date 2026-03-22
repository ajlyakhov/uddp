# UDDP — Universal Data Delivery Pipeliner

UDDP is an open-source microservice for building robust data processing and delivery pipelines. It orchestrates the publishing, processing, and distribution of digital assets to S3-compatible cloud storage via a plugin-based pipeline architecture.

Built with **Django**, **Celery**, and **Redis**.

---

## 🚀 Features

- **Pipeline Orchestration** — define multi-stage processing pipelines per content type
- **S3 Integration** — seamless upload to AWS S3 or any S3-compatible storage (MinIO, etc.)
- **Plugin Architecture** — each pipeline stage is a standalone Python module with an `execute(task)` interface
- **Asynchronous Processing** — Celery + Redis for high-performance background task execution
- **REST API** — simple HTTP endpoints for triggering and monitoring tasks
- **Docker Ready** — fully containerized for easy deployment

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Framework | Django 5 |
| Task Queue | Celery |
| Broker | Redis |
| Storage | AWS S3 / MinIO |
| Server | Gunicorn / Uvicorn |
| Database | SQLite (dev) / PostgreSQL (prod) |

---

## 🏁 Getting Started

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for full stack)
- An S3-compatible storage bucket

### Local Dev Setup

```bash
# Clone
git clone https://github.com/ajlyakhov/uddp.git
cd uddp

# Create virtualenv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start server
python manage.py runserver 0.0.0.0:8000
```

### Docker Compose

```bash
cd docker
docker-compose up --build
```

This starts:
- **core** — Django app at `http://localhost:8000`
- **worker** — Celery worker
- **redis** — message broker

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `True` | Debug mode |
| `SECRET_KEY` | insecure default | Django secret key |
| `ALLOWED_HOSTS` | `*` (debug) | Comma-separated allowed hosts |
| `AWS_S3_ENDPOINT_URL` | `http://minio:9000` | S3 endpoint |
| `AWS_S3_ACCESS_KEY_ID` | — | S3 access key |
| `AWS_S3_SECRET_ACCESS_KEY` | — | S3 secret key |
| `AWS_STORAGE_BUCKET_NAME` | `uddp` | S3 bucket name |
| `CELERY_REDIS_URL` | — | Redis URL (production) |

---

## 📡 API

### Publish a file

```http
POST /publish/
Authorization: Token <your-source-token>
Content-Type: application/json

{
  "type": "file_upload",
  "url": "https://example.com/myfile.png"
}
```

**Response:**
```json
{"code": "file_upload", "task": 42}
```

### Check task status

```http
GET /publish/status/<task_id>/
Authorization: Token <your-source-token>
```

**Response:**
```json
{
  "task": 42,
  "status": 1,
  "progress": 100,
  "last_log": "[core.tasks] Processing completed"
}
```

### Example with curl

```bash
curl -X POST http://your-server:8000/publish/ \
  -H "Authorization: Token demo-token-123456" \
  -H "Content-Type: application/json" \
  -d '{"type": "file_upload", "url": "https://example.com/image.png"}'
```

---

## 🔌 Pipeline Plugins

Each processing stage is a Python module uploaded via the admin panel. The module must expose a single function:

```python
def execute(task):
    """
    task.meta     — the original publish request JSON
    task.context  — mutable dict for passing data between stages
    task.logging(type, message) — append to task log
    task.set_context(dict)      — merge dict into task context
    task.set_error(message)     — mark task as failed
    """
    url = task.meta.get("url")
    # ... process and upload ...
    task.set_context({"output_url": "https://..."})
```

Stages are chained by `step` number (ascending). If any stage raises an exception, the task is marked as failed and the chain stops.

### Built-in plugin: `upload_to_s3.py`

Downloads a file from `task.meta["url"]` and uploads it to the configured S3 bucket under `uploads/<task_id>/<filename>`.

---

## 📂 Project Structure

```
uddp/
├── conf/                   # Django settings, URLs, WSGI/ASGI, Celery config
├── core/                   # Core app — Task model, PublishView, Celery task runner
├── reference/              # Reference data — Workspace, Source, DataType, Plugin, ProcessingStage
├── setup/                  # Setup app (onboarding views)
├── pipeline_plugins/       # Built-in pipeline stage modules
│   └── upload_to_s3.py     # Download URL → upload to S3
├── docker/                 # Docker and docker-compose files
├── manage.py
└── requirements.txt
```

---

## 📖 Demo Scenarios

Two pre-configured scenarios are included to demonstrate the pipeline:

| Scenario | Stages | Description |
|---|---|---|
| `file_upload` | 1 | Download a file from URL → upload to S3 |
| `image_resize` | 2 | Download image → resize to 50% → upload to S3 |

👉 **See [docs/scenarios.md](docs/scenarios.md) for full walkthrough.**

To set up the demo pipelines:
```bash
python manage.py shell < bootstrap_demo.py
```

---

## 🧪 Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
python manage.py test

# Run with coverage
coverage run manage.py test
coverage report
coverage html  # opens htmlcov/index.html
```

Coverage reports are generated automatically on every push via GitHub Actions (see `.github/workflows/ci.yml`). HTML reports are available as build artifacts.

---

## 🐳 Admin Panel

Available at `/admin/` — manage workspaces, sources, plugins, data types, and processing stages.

Default dev credentials: `admin` / `admin123`

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
