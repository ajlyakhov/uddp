import json
import traceback
from pathlib import Path
from core.models import Task
from core.publisher.teplohod.validate_teplohod import TeplhodPublishMeta
from core.publisher.utils import streaming_download_and_unzip_archive


def execute(task: Task):
    task.logging(f"{__name__}", "execute")

    meta = TeplhodPublishMeta(**task.publisher_meta)

    # Проверяем и инициализируем контекст если он None
    if task.context is None:
        task.context = {}
        task.save(update_fields=['context'])
    
    # Проверяем наличие tmp_dir в контексте
    if "tmp_dir" not in task.context:
        task.set_publisher_error("Отсутствует tmp_dir в контексте задачи")
        raise ValueError("Отсутствует tmp_dir в контексте задачи")

    # скачиваем во временную папку
    tmp_path = Path(task.context["tmp_dir"])
    task.logging(f"{__name__}", "Скачивание и распаковка пакета")

    try:
        streaming_download_and_unzip_archive(task=task, dir_path=tmp_path, url=meta.path)

        with open(tmp_path / "meta.json", "r") as f:
            internal_meta = json.load(f)

        task.set_context({"internal_meta": internal_meta})
    except Exception as e:
        task.set_publisher_error(f"Ошибка обработки пакета {traceback.format_exc()}")
        raise
