import io
import os
from urllib.parse import urlparse

import boto3
import requests
from PIL import Image

S3_BUCKET = "uddp-demo"
S3_REGION = "eu-west-3"
AWS_ACCESS_KEY = "AKIA2OYFKK33ZBDS5UWV"
AWS_SECRET_KEY = "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"


def execute(task):
    """
    Stage 1 of the image resize pipeline.
    Downloads the image from task.meta["url"], resizes it to 50% of original
    dimensions using Pillow (LANCZOS resampling), saves to the shared tmp_dir,
    and stores the local path in task.context["local_file"] for the next stage.
    """
    url = task.meta.get("url")
    if not url:
        raise ValueError("No 'url' field in task meta")

    task.logging("INFO", f"Downloading image from: {url}")
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    img = Image.open(io.BytesIO(response.content))
    original_size = f"{img.width}x{img.height}"

    new_width = max(1, img.width // 2)
    new_height = max(1, img.height // 2)
    resized = img.resize((new_width, new_height), Image.LANCZOS)

    filename = os.path.basename(urlparse(url).path) or "image.png"
    tmp_dir = task.context.get("tmp_dir", "/tmp")
    local_path = os.path.join(tmp_dir, f"resized_{filename}")
    resized.save(local_path)

    task.logging("INFO", f"Resized {original_size} → {new_width}x{new_height}, saved to {local_path}")
    task.set_context({
        "local_file": local_path,
        "resize_info": {"original": original_size, "resized": f"{new_width}x{new_height}"},
    })
