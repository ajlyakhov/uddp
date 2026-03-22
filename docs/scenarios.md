# UDDP Demo Scenarios

This document describes the two pre-configured demo scenarios included with UDDP.
Run `python manage.py shell < bootstrap_demo.py` to set them up.

---

## Scenario 1 — File Upload

**What it does:** Accepts a file URL, downloads the file, and uploads it as-is to an S3 bucket.

**Pipeline:** 1 stage
```
[Source] → upload_to_s3 → [S3: uploads/<task_id>/<filename>]
```

**API call:**
```bash
curl -X POST http://your-server:8000/publish/ \
  -H "Authorization: Token demo-token-upload" \
  -H "Content-Type: application/json" \
  -d '{"type": "file_upload", "url": "https://uddp-demo.s3.eu-west-3.amazonaws.com/source/rick.png"}'
```

**Response:**
```json
{"code": "file_upload", "task": 1}
```

**Check status:**
```bash
curl http://your-server:8000/publish/status/1/ \
  -H "Authorization: Token demo-token-upload"
```

**Output:** The file is available at:
```
https://uddp-demo.s3.eu-west-3.amazonaws.com/uploads/<task_id>/<filename>
```

---

## Scenario 2 — Image Resize + Upload

**What it does:** Downloads an image, resizes it to **50% of original dimensions** (width and height both halved), then uploads the resized image to S3.

**Pipeline:** 2 stages
```
[Source] → resize_image → upload_to_s3 → [S3: uploads/<task_id>/<filename>]
              (50% size)
```

**How the stages communicate:** Stage 1 (`resize_image`) saves the resized image to a shared temporary directory and stores the local path in `task.context["local_file"]`. Stage 2 (`upload_to_s3`) detects this and uploads the local file directly instead of re-downloading.

**API call:**
```bash
curl -X POST http://your-server:8000/publish/ \
  -H "Authorization: Token demo-token-resize" \
  -H "Content-Type: application/json" \
  -d '{"type": "image_resize", "url": "https://uddp-demo.s3.eu-west-3.amazonaws.com/source/rick.png"}'
```

**Response:**
```json
{"code": "image_resize", "task": 2}
```

**Output:** The resized image is available at:
```
https://uddp-demo.s3.eu-west-3.amazonaws.com/uploads/<task_id>/<filename>
```

The task context will include resize metadata:
```json
{
  "resize_info": {"original": "640x480", "resized": "320x240"},
  "output_url": "https://uddp-demo.s3.eu-west-3.amazonaws.com/uploads/2/rick.png"
}
```

---

## Adding Custom Scenarios

To create your own pipeline:

1. Write a Python module with an `execute(task)` function
2. Upload it as a **Plugin** via the admin panel (`/admin/`)
3. Create a **DataType** with a unique `source_code`
4. Add **ProcessingStage** records linking DataType → Plugin (ordered by `step`)
5. Create a **Source** with an API token and link it to your DataType
6. Call `POST /publish/` with `Authorization: Token <your-token>` and `{"type": "<source_code>", ...}`

See [README.md](../README.md) for full API documentation.
