# UDDP User Guide

**For admin users and content managers — no coding required.**

---

## Introduction

**UDDP (Universal Data Delivery Pipeliner)** is a server-side tool that automatically processes and publishes digital assets — primarily images and files — through a configurable multi-step pipeline. You give it a file URL, and it handles everything: downloading, transforming, converting, and uploading to cloud storage, all in the background.

**In plain terms:** Imagine you have a photo on the web. You send UDDP a link to that photo, and it automatically resizes it, removes private metadata, creates multiple formats (thumbnail, medium, full-size), and puts all the results in your cloud storage — with a summary file listing where everything went.

You control what happens at each step, in what order, and for which types of content — all through the admin panel.

---

## Accessing the Admin Panel

The admin panel is available at:

```
http://your-server:8000/admin/
```

Default login credentials (development):
- **Username:** `admin`
- **Password:** `admin123`

> ⚠️ Change the password immediately in any non-development environment. Go to **Authentication → Users → admin → Change password**.

Once logged in, you'll see sections on the left sidebar for managing all aspects of UDDP.

---

## Key Concepts

Understanding these six building blocks will let you configure any pipeline.

### 🏢 Workspace

A **Workspace** is a top-level container that groups everything together — sources, data types, plugins, and processing stages. Think of it as a "project" or "client account."

Most deployments use a single workspace called **Demo** or named after your organisation.

## Managing Users, Teams, and Workspaces

Use this section when onboarding people and setting permissions boundaries.

### Permission model

- **User**: Django account used to sign into `/admin/`
- **Workspace**: tenant boundary for operational entities (`Source`, `DataType`, `Consumer`, `ProcessingStage`, task/log records)
- **Team**: group inside one workspace
- **Team Member**: user membership in team with role:
  - `maintainer`
  - `developer`

### Recommended admin workflow

1. Go to **Authentication -> Users** and create the user account.
2. Go to **Reference -> Workspaces** and create/select workspace.
3. Go to **Reference -> Teams** and create team under that workspace.
4. In the team form, add **Team Members** rows:
   - choose user
   - set role (`maintainer` or `developer`)
5. Save and verify the user can sign in to `/admin/`.

### Operational tips

- Create one workspace per client/environment boundary.
- Use teams to separate responsibilities (for example: ingestion vs. publishing).
- Keep `maintainer` role limited to people who change pipeline definitions.
- Rotate credentials and remove stale users regularly.

### 🔑 Source

A **Source** represents an external system that is allowed to publish content to UDDP. Each source has:

- **Name** — a human-readable label (e.g. "Mobile App Backend")
- **Key (token)** — a secret string that the caller must include in every API request as `Authorization: Token <key>`

If someone sends a request with an unknown token, UDDP rejects it with a 403 error. Sources are how you control *who* can trigger pipelines.

### 📄 DataType

A **DataType** defines *what kind of content* is being published. Each data type has:

- **Name** — a human-readable label (e.g. "Product Image")
- **Source Code** — a short identifier used in API calls (e.g. `product_image`)
- **Source** — the Source this data type belongs to

When you call the API with `"type": "product_image"`, UDDP looks up the DataType with that source code and runs its pipeline.

### 🔌 Plugin

A **Plugin** is a Python code module that performs one specific processing task. Examples:

- Download a file from a URL
- Resize an image
- Strip metadata
- Convert to WebP format
- Upload to S3

Plugins are uploaded via the admin panel and stored in the database. They are the building blocks of pipelines.

Each plugin exposes a single function: `execute(task)`.

### ⚙️ ProcessingStage

A **ProcessingStage** links a DataType to a Plugin and gives it a **step number**. UDDP runs all stages for a given DataType in ascending step order (step 1, then step 2, then step 3, etc.).

Each stage can be marked **Active** or **Inactive**. Inactive stages are skipped without being removed.

### 📬 Consumer

A **Consumer** (if configured) is an external endpoint that receives notifications when a task completes. Consumers allow UDDP to push results to other systems (webhooks, message queues, etc.) rather than requiring the caller to poll for status.

---

## Setting Up a New Pipeline from Scratch

This example walks through setting up the **Image Export** pipeline, which:
1. Downloads an image from a URL
2. Resizes it to a maximum of 2048px wide
3. Strips all EXIF metadata (GPS, camera info, etc.)
4. Generates three WebP variants: thumbnail (150×150), medium (800px wide), full resolution
5. Uploads all variants to S3 and creates a manifest JSON file

### Step 1 — Create or Select a Workspace

1. Go to **Reference → Workspaces**
2. If "Demo" exists, use it. Otherwise click **Add Workspace**, enter a name, and save.

### Step 2 — Upload the Plugins

1. Go to **Reference → Plugin Repos** and create a repo named "Built-in" (URL: `http://localhost`)
2. Go to **Reference → Plugins** and click **Add Plugin**
3. For each stage, upload the corresponding `.py` file from the `pipeline_plugins/` directory:
   - `normalize_image.py` → name: "Normalize Image"
   - `strip_exif.py` → name: "Strip EXIF"
   - `generate_variants.py` → name: "Generate Variants"
   - `upload_manifest.py` → name: "Upload Manifest"
4. Select the plugin repo and save each one

### Step 3 — Create a Source

1. Go to **Reference → Sources** → **Add Source**
2. Fill in:
   - **Name:** `Demo Source — Image Export`
   - **Key:** `demo-token-export` *(or generate a random secure string)*
   - **Workspace:** Demo
3. Save

### Step 4 — Create a DataType

1. Go to **Reference → Data Types** → **Add Data Type**
2. Fill in:
   - **Name:** `Image Export`
   - **Source Code:** `image_export`
   - **Source:** Demo Source — Image Export
   - **Workspace:** Demo
3. Save

### Step 5 — Add Processing Stages

1. Go to **Reference → Processing Stages** → **Add Processing Stage**
2. Add four stages:

| Step | Plugin            | Active |
|------|-------------------|--------|
| 1    | Normalize Image   | ✅ Yes |
| 2    | Strip EXIF        | ✅ Yes |
| 3    | Generate Variants | ✅ Yes |
| 4    | Upload Manifest   | ✅ Yes |

For each: select the DataType "Image Export", the correct Plugin, set the Step number, check Active, and save.

### Step 6 — Test It

Send a request to the API (see the API section below). You can also use the **bootstrap_demo.py** script to set up all demo pipelines automatically:

```bash
python manage.py shell < bootstrap_demo.py
```

---

## Monitoring Tasks

### Viewing Tasks in Admin

Go to **Core → Tasks** to see all tasks. Each task shows:

- **ID** — unique identifier
- **Status** — current state (see below)
- **Progress** — percentage complete (0–100)
- **Last Log** — the most recent log message from the pipeline

Click a task to see its full detail: all log messages, the input metadata, and the output context (including S3 URLs).

### Task Status Codes

| Status Code | Meaning |
|-------------|---------|
| `0` | **Pending** — task queued, not yet started |
| `1` | **Done** — pipeline completed successfully |
| `2` | **In Progress** — currently being processed |
| `3` | **Error** — pipeline failed (check logs for details) |

### Reading Task Logs

In the task detail view, the **Log** field shows timestamped messages from each stage. Example:

```
[normalize_image] Downloading image: https://example.com/photo.jpg
[normalize_image] Image within limits (1200x800), no resize needed
[normalize_image] Saved normalized image to /tmp/abc123/normalized_photo.png
[strip_exif] Stripping EXIF from /tmp/abc123/normalized_photo.png
[strip_exif] EXIF stripped and file saved
[generate_variants] Generated thumb_150.webp
[generate_variants] Generated medium_800.webp (800x533)
[generate_variants] Generated full.webp (1200x800)
[generate_variants] All variants generated
[upload_manifest] Uploading thumb → s3://uddp-demo/uploads/42/thumb_150.webp
[upload_manifest] Uploading medium → s3://uddp-demo/uploads/42/medium_800.webp
[upload_manifest] Uploading full → s3://uddp-demo/uploads/42/full.webp
[upload_manifest] Manifest uploaded: https://uddp-demo.s3.eu-west-3.amazonaws.com/uploads/42/manifest.json
```

If a task errors, the log will show which stage failed and the error message.

---

## Using the API to Publish Content

### Trigger a Pipeline

Send a `POST` request to `/publish/` with:
- An `Authorization` header containing your Source token
- A JSON body with `"type"` (the DataType's source code) and any data your pipeline needs

**Example — Image Export pipeline:**

```bash
curl -X POST http://your-server:8000/publish/ \
  -H "Authorization: Token demo-token-export" \
  -H "Content-Type: application/json" \
  -d '{"type": "image_export", "url": "https://example.com/photo.jpg"}'
```

**Response:**
```json
{"code": "image_export", "task": 42}
```

The `task` number is your handle for checking progress.

### Check Task Status

```bash
curl http://your-server:8000/publish/status/42/ \
  -H "Authorization: Token demo-token-export"
```

**Response (in progress):**
```json
{
  "task": 42,
  "status": 2,
  "progress": 50,
  "last_log": "[generate_variants] Generated thumb_150.webp"
}
```

**Response (complete):**
```json
{
  "task": 42,
  "status": 1,
  "progress": 100,
  "last_log": "[upload_manifest] Manifest uploaded: https://uddp-demo.s3.eu-west-3.amazonaws.com/uploads/42/manifest.json"
}
```

### Other Demo Scenarios

**File Upload (1 stage):**
```bash
curl -X POST http://your-server:8000/publish/ \
  -H "Authorization: Token demo-token-upload" \
  -H "Content-Type: application/json" \
  -d '{"type": "file_upload", "url": "https://example.com/document.pdf"}'
```

**Image Resize (2 stages):**
```bash
curl -X POST http://your-server:8000/publish/ \
  -H "Authorization: Token demo-token-resize" \
  -H "Content-Type: application/json" \
  -d '{"type": "image_resize", "url": "https://example.com/photo.jpg"}'
```

---

## Troubleshooting Common Issues

### Task is stuck "In Progress"

**Symptoms:** Status stays at `2` (In Progress) for more than a few minutes.

**Causes and fixes:**
1. **Celery worker is not running** — The worker processes tasks in the background. Check that it's running:
   - With Docker: `docker-compose ps` → look for the `worker` container
   - Without Docker: you need a process running `celery -A conf worker`
2. **Redis is down** — Celery uses Redis as its message broker. Check Redis is reachable.
3. **Task crashed silently** — Restart the worker. The task will be retried or marked as error.

### 403 Forbidden Error

**Symptoms:** API returns HTTP 403.

**Causes and fixes:**
1. **Wrong token** — Check that the `Authorization: Token <key>` header exactly matches the **Key** field on your Source in the admin panel. Tokens are case-sensitive.
2. **Token from wrong source** — Each Source token only works for the DataTypes linked to that Source. Make sure you're using the token from the Source that owns the DataType you're calling.
3. **No token** — Ensure you're including the `Authorization` header, not putting the token in the URL or body.

### S3 Upload Fails

**Symptoms:** Task ends with status `3` (Error) and the log shows an S3 or boto3 error.

**Causes and fixes:**
1. **Invalid credentials** — The AWS access key or secret in the plugin code may be wrong or expired. A developer needs to update the plugin with valid credentials.
2. **Bucket doesn't exist** — The S3 bucket named in the plugin must already exist in the correct AWS region.
3. **Permission denied** — The AWS IAM user whose keys are used must have `s3:PutObject` permission on the target bucket.
4. **Wrong region** — If the bucket is in a different region than what the plugin specifies, uploads will fail. Check the `S3_REGION` constant in the plugin.
5. **Network issue** — The server must have outbound internet access to reach AWS S3 endpoints.

### Image Fails to Download

**Symptoms:** Error log shows a requests error or HTTP error code when downloading the source image.

**Causes and fixes:**
1. **URL is not publicly accessible** — The image URL must be reachable from the server without authentication.
2. **URL returns a non-image** — The URL must point directly to an image file (jpg, png, etc.), not an HTML page.
3. **Timeout** — For very large files, the 60-second download timeout may be exceeded. Contact a developer to increase it.

### Task Errors with "No local_file in context"

**Symptoms:** `strip_exif` or `generate_variants` stage fails with this message.

**Cause:** A required earlier stage is disabled or missing from the pipeline.

**Fix:** Go to **Reference → Processing Stages** and ensure that all stages for the DataType are present and marked **Active**, numbered in the correct order (1, 2, 3, 4).
