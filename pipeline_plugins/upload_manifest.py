import io
import json
import os

import boto3


S3_BUCKET = "uddp-demo"
S3_REGION = "eu-west-3"
AWS_ACCESS_KEY = "AKIA2OYFKK33ZBDS5UWV"
AWS_SECRET_KEY = "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"


def _s3_url(key):
    return f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{key}"


def execute(task):
    variants = task.context.get("variants")
    if not variants:
        raise ValueError("No variants in context — run generate_variants first")

    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=S3_REGION,
    )

    uploaded = {}
    variant_names = {"thumb": "thumb_150.webp", "medium": "medium_800.webp", "full": "full.webp"}

    for variant_key, local_path in variants.items():
        s3_key = f"uploads/{task.id}/{variant_names[variant_key]}"
        task.logging("INFO", f"Uploading {variant_key} → s3://{S3_BUCKET}/{s3_key}")
        with open(local_path, "rb") as f:
            s3.upload_fileobj(f, S3_BUCKET, s3_key, ExtraArgs={"ContentType": "image/webp"})
        uploaded[variant_key] = _s3_url(s3_key)

    # Build and upload manifest.json
    manifest = {
        "task_id": task.id,
        "source_url": task.meta.get("url"),
        "original_size": task.context.get("original_size"),
        "normalized_size": task.context.get("normalized_size"),
        "variants": uploaded,
    }
    manifest_json = json.dumps(manifest, indent=2).encode("utf-8")
    manifest_key = f"uploads/{task.id}/manifest.json"
    s3.upload_fileobj(
        io.BytesIO(manifest_json),
        S3_BUCKET,
        manifest_key,
        ExtraArgs={"ContentType": "application/json"},
    )
    manifest_url = _s3_url(manifest_key)
    task.logging("INFO", f"Manifest uploaded: {manifest_url}")

    task.set_context({
        "output_url": manifest_url,
        "manifest": manifest,
    })
