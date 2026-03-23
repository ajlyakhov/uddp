import os
from PIL import Image


def _square_crop(img, size):
    """Center-crop to a square, then resize."""
    w, h = img.size
    min_dim = min(w, h)
    left = (w - min_dim) // 2
    top = (h - min_dim) // 2
    cropped = img.crop((left, top, left + min_dim, top + min_dim))
    return cropped.resize((size, size), Image.LANCZOS)


def execute(task):
    local_file = task.context.get("local_file")
    if not local_file or not os.path.exists(local_file):
        raise ValueError("No local_file in context — run normalize_image and strip_exif first")

    tmp_dir = task.context.get("tmp_dir", "/tmp")
    img = Image.open(local_file).convert("RGB")
    stem = os.path.splitext(os.path.basename(local_file))[0]

    variants = {}

    # thumb — 150x150 square crop
    thumb_path = os.path.join(tmp_dir, "thumb_150.webp")
    _square_crop(img, 150).save(thumb_path, format="WEBP", quality=85)
    variants["thumb"] = thumb_path
    task.logging("INFO", "Generated thumb_150.webp")

    # medium — 800px wide
    medium_path = os.path.join(tmp_dir, "medium_800.webp")
    if img.width > 800:
        ratio = 800 / img.width
        medium = img.resize((800, int(img.height * ratio)), Image.LANCZOS)
    else:
        medium = img
    medium.save(medium_path, format="WEBP", quality=85)
    variants["medium"] = medium_path
    task.logging("INFO", f"Generated medium_800.webp ({medium.width}x{medium.height})")

    # full — full resolution in WebP
    full_path = os.path.join(tmp_dir, "full.webp")
    img.save(full_path, format="WEBP", quality=90)
    variants["full"] = full_path
    task.logging("INFO", f"Generated full.webp ({img.width}x{img.height})")

    task.set_context({"variants": variants})
    task.logging("INFO", "All variants generated")
