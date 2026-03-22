import os
import boto3
import requests
from urllib.parse import urlparse


S3_BUCKET = "uddp-demo"
S3_REGION = "eu-west-3"
AWS_ACCESS_KEY = "AKIA2OYFKK33ZBDS5UWV"
AWS_SECRET_KEY = "sqpXyMevAhWCoHI7Vw91LRkyG0MouzEfbEDFCDh/"


def execute(task):
    """
    Uploads a file to S3. Two modes:
    - If context["local_file"] is set (e.g. from a previous resize stage),
      uploads that local file directly.
    - Otherwise downloads task.meta["url"] and streams it to S3.
    Stores output_url in task context.
    """
    url = task.meta.get("url")
    if not url:
        raise ValueError("No 'url' field in task meta")

    filename = os.path.basename(urlparse(url).path) or "file"
    s3_key = f"uploads/{task.id}/{filename}"

    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=S3_REGION,
    )

    local_file = task.context.get("local_file")
    if local_file and os.path.exists(local_file):
        task.logging("INFO", f"Uploading local file {local_file} to s3://{S3_BUCKET}/{s3_key}")
        with open(local_file, "rb") as f:
            s3.upload_fileobj(f, S3_BUCKET, s3_key)
    else:
        task.logging("INFO", f"Downloading and uploading {url} to s3://{S3_BUCKET}/{s3_key}")
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        response.raw.decode_content = True
        s3.upload_fileobj(response.raw, S3_BUCKET, s3_key)

    output_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
    task.logging("INFO", f"Done! File available at: {output_url}")
    task.set_context({"output_url": output_url})
