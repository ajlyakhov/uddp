import io
import os
from PIL import Image


def execute(task):
    local_file = task.context.get("local_file")
    if not local_file or not os.path.exists(local_file):
        raise ValueError("No local_file in context — run normalize_image first")

    task.logging("INFO", f"Stripping EXIF from {local_file}")

    img = Image.open(local_file)
    # Re-encode as PNG without metadata
    clean_buffer = io.BytesIO()
    img_rgb = img.convert("RGB") if img.mode not in ("RGB", "L") else img
    # Save without EXIF (PIL PNG writer does not copy EXIF by default)
    img_rgb.save(clean_buffer, format="PNG", optimize=True)
    clean_buffer.seek(0)

    # Overwrite the file
    with open(local_file, "wb") as f:
        f.write(clean_buffer.read())

    task.logging("INFO", "EXIF stripped and file saved")
    # local_file path unchanged, context already has it
