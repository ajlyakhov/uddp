# UDDP (Universal Data Delivery Pipeliner)

UDDP is an open-source microservice designed for building robust data processing and delivery pipelines. It orchestrates the publishing, processing, and distribution of digital assets to S3-compatible cloud storage and various target platforms.

Built with Django, Celery, and Redis, UDDP provides a flexible framework for defining custom processing stages, handling metadata, and managing asynchronous tasks.

## 🚀 Features

-   **Pipeline Orchestration**: Define multi-stage processing pipelines for different content types.
-   **S3 Integration**: Seamless upload and management of files in S3-compatible storage (AWS S3, MinIO, etc.).
-   **Extensible Architecture**: Easily add new publisher systems and service platforms via the `reference` app.
-   **Asynchronous Processing**: Powered by Celery and Redis for high-performance background task execution.
-   **Docker Ready**: Fully containerized for easy deployment and development.
-   **REST API**: (Implied) API for triggering and monitoring tasks.

## 🛠️ Tech Stack

-   **Language**: Python 3.11
-   **Framework**: Django
-   **Task Queue**: Celery
-   **Broker**: Redis
-   **Server**: Gunicorn / Uvicorn (ASGI)
-   **Database**: SQLite (default) / PostgreSQL (supported)

## 🏁 Getting Started

### Prerequisites

-   Docker
-   Docker Compose

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/yourusername/uddp.git
    cd uddp
    ```

2.  **Environment Configuration:**

    Create a `.env` file in the root directory (or rely on Docker defaults for dev). Key environment variables include:

    ```env
    DEBUG=True
    SECRET_KEY=your-secret-key
    ALLOWED_HOSTS=localhost,127.0.0.1
    
    # S3 Configuration
    AWS_S3_ENDPOINT_URL=https://s3.example.com
    AWS_S3_ACCESS_KEY_ID=your-access-key
    AWS_S3_SECRET_ACCESS_KEY=your-secret-key
    AWS_STORAGE_BUCKET_NAME=your-bucket-name
    
    # Celery
    CELERY_REDIS_URL=redis://redis:6379/0
    ```

3.  **Run with Docker Compose:**

    ```bash
    cd docker
    docker-compose up --build
    ```

    This will start:
    -   **Core**: The Django application (available at `http://localhost:8000`).
    -   **Worker**: The Celery worker for background tasks.
    -   **Redis**: The message broker.

### Manual Setup (Local Dev)

1.  Create a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Run migrations:
    ```bash
    python manage.py migrate
    ```

4.  Start the server:
    ```bash
    python manage.py runserver
    ```

5.  Start Celery worker:
    ```bash
    celery -A conf worker -l info
    ```

## 📂 Project Structure

```
uddp/
├── conf/               # Project configuration (settings, urls, wsgi/asgi)
├── core/               # Core application (Tasks, ContentItems)
├── reference/          # Reference data (Publishers, Platforms, Stages)
├── docker/             # Docker configuration and scripts
├── manage.py           # Django management script
└── requirements.txt    # Python dependencies
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
