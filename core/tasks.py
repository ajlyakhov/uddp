import traceback
from datetime import datetime
from tempfile import TemporaryDirectory

import pytz

from core.models import Task, TaskStatus
from conf.celery import app
import importlib


@app.task
def process_publisher(task_id):
    task: Task = Task.objects.get(id=task_id)

    with TemporaryDirectory() as tmp_dir:

        task.total_tasks = task.service.source_stages.filter(active=True).count()
        task.total_tasks += task.service.target_stages.filter(active=True).count()
        task.save(update_fields=['total_tasks', ])

        current_task = 0
        # PUBLISHER SYSTEM
        for stage in task.service.source_stages.filter(active=True).order_by('step'):
            try:
                task.set_context({"tmp_dir": tmp_dir})
                process_module = importlib.import_module(stage.module)
                process_module.execute(task)

                current_task += 1
                task.current_task = current_task
                task.progress = int((float(task.current_task) / float(task.total_tasks))*100)
                task.save(update_fields=['current_task', 'progress', ])

            except Exception as e:
                task.set_publisher_error(f'module {stage.module}: {e}, traceback: {traceback.format_exc()}')
                return

        task.logging(f"{__name__}", "Source System publication completed")
        task.publisher_status = TaskStatus.STATUS_OK
        task.publisher_date = datetime.now(tz=pytz.UTC)
        task.save(update_fields=['publisher_status', 'publisher_date', ])

        # SERVICE SYSTEM
        for stage in task.service.target_stages.filter(active=True).order_by('step'):
            try:
                task.set_context({"tmp_dir": tmp_dir})
                process_module = importlib.import_module(stage.module)
                process_module.execute(task)

                current_task += 1
                task.current_task = current_task
                task.progress = int((float(task.current_task) / float(task.total_tasks))*100)
                task.save(update_fields=['current_task', 'progress', ])

            except Exception as e:
                task.set_publisher_error(f'module {stage.module}: {e}, traceback: {traceback.format_exc()}')
                return

        task.logging(f"{__name__}", "Target Service publication completed")
