import io
import os
from urllib.parse import urlparse

import requests
from PIL import Image

MAX_WIDTH = 2048


def execute(task):
    url = task.meta.get("url")
    if not url:
        raise ValueError("No 'url' field in task meta")

    task.logging("INFO", f"Downloading image: {url}")
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    img = Image.open(io.BytesIO(response.content))
    original_size = f"{img.width}x{img.height}"

    # Convert to RGB if needed (e.g. RGBA, palette)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Resize if wider than MAX_WIDTH
    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        new_h = int(img.height * ratio)
        img = img.resize((MAX_WIDTH, new_h), Image.LANCZOS)
        task.logging("INFO", f"Resized {original_size} → {img.width}x{img.height}")
    else:
        task.logging("INFO", f"Image within limits ({original_size}), no resize needed")

    filename = os.path.basename(urlparse(url).path) or "image.png"
    stem = os.path.splitext(filename)[0]
    tmp_dir = task.context.get("tmp_dir", "/tmp")
    local_path = os.path.join(tmp_dir, f"normalized_{stem}.png")
    img.save(local_path, format="PNG")

    task.set_context({
        "local_file": local_path,
        "original_filename": filename,
        "original_size": original_size,
        "normalized_size": f"{img.width}x{img.height}",
    })
    task.logging("INFO", f"Saved normalized image to {local_path}")
