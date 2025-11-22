import json
import traceback

from core.models import ContentItem, Task


def execute(task: Task):
    try:
        internal_meta = task.context.get('internal_meta')
        ContentItem.objects.create(
            type=task.service,
            publisher=task.publisher,
            meta=task.publisher_meta,
            internal_meta=internal_meta,
            task=task,
            storage="",
            sku=task.publisher_meta["code"],
            year=internal_meta["year"],
            cover=task.context.get('cover'),
        )
    except Exception as e:
        task.logging(f"{__name__}", f"content_item save error: {traceback.format_exc()}")
