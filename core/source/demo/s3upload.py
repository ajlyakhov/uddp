import os
from datetime import datetime

from django.conf import settings

from core.models import Task
from core.publisher.utils import sync_to_s3, zip_to_s3, cover_to_s3, file_to_s3
from core.publisher.teplohod.validate_teplohod import TeplohodEfuInternalMeta, TeplohodAudiobookInternalMeta


def execute(task: Task):
    task.logging(f"{__name__}", "execute")

    tmp_dir = task.context.get("tmp_dir")
    optimized_cover = task.context["optimized_cover"]
    internal_meta = TeplohodAudiobookInternalMeta(**task.context["internal_meta"])

    sku = internal_meta.code
    try:
        year = int(internal_meta.year)
    except Exception as e:
        task.logging(f"{__name__}", "Ошибку в обработке года: {e}")
        year = datetime.now().year

    # Загрузка в S3 аудиофайлы (сохраняем структуру архива)
    s3path = f"{task.service.publisher_code}/{sku}/{year}/"
    task.logging(f"{__name__}", "Загрузка Аудиокниги в S3")
    sync_to_s3(os.path.join(tmp_dir, "audio"), settings.S3_BUCKET, s3path + "audio/")
    storage_url = f"{settings.S3_HOST_CONTENT}/{s3path}"
    task.set_context({"storage_url": storage_url})
    
    # Пути в internal_meta уже корректные (с префиксом "audio/")
    task.context["internal_meta"]["audio"] = task.context["audio"]
    task.set_context({"internal_meta": task.context["internal_meta"]})

    # Загрузка в S3 объектов с интерактивами (если папка существует)
    objects_dir = os.path.join(tmp_dir, "objects")
    if os.path.exists(objects_dir):
        sync_to_s3(objects_dir, settings.S3_BUCKET, s3path+"objects/")
        task.logging(f"{__name__}", "Загрузка объектов в S3")
    else:
        task.logging(f"{__name__}", "Папка objects не найдена, пропускаем загрузку объектов")

    # Загрузка в S3 обложки
    task.logging(f"{__name__}", "Загрузка обложки аудиокниги в S3")
    cover_to_s3(optimized_cover, "original", cover_name=f"cover-{sku}-{year}.jpg")
    cover_url = f"{settings.S3_HOST_COVER}/original/cover-{sku}-{year}.jpg"
    task.set_context({"cover": cover_url})

    # Загрузка в S3 audio.json
    task.logging(f"{__name__}", "Загрузка audio.json в S3")
    file_to_s3(os.path.join(tmp_dir, "audio.json"), settings.S3_BUCKET, f"{s3path}audio.json", task=task)


