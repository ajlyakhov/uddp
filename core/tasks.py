import traceback
from datetime import datetime
from tempfile import TemporaryDirectory

import pytz

from core.models import Task, TaskStatus
from conf.celery import app
import importlib.util
import os


@app.task
def process_source_data(task_id):
    task: Task = Task.objects.get(id=task_id)

    with TemporaryDirectory() as tmp_dir:

        task.total_tasks = task.data_type.processing_stages.filter(active=True).count()
        task.save(update_fields=['total_tasks', ])

        current_task = 0
        for stage in task.data_type.processing_stages.filter(active=True).order_by('step'):
            try:
                task.set_context({"tmp_dir": tmp_dir})
                
                module_filename = os.path.basename(stage.plugin.file.name)
                # Always save with .py extension so importlib can load it
                local_module_path = os.path.join(tmp_dir, f"stage_{stage.step}.py")
                
                with stage.plugin.file.open('rb') as f:
                    with open(local_module_path, 'wb') as local_f:
                        local_f.write(f.read())

                spec = importlib.util.spec_from_file_location("processing_module", local_module_path)
                process_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(process_module)
                
                process_module.execute(task)

                current_task += 1
                task.current_task = current_task
                task.progress = int((float(task.current_task) / float(task.total_tasks))*100)
                task.save(update_fields=['current_task', 'progress', ])

            except Exception as e:
                task.set_error(f'module {stage.plugin.file.name}: {e}, traceback: {traceback.format_exc()}')
                return

        task.logging(f"{__name__}", "Processing completed")
        task.status = TaskStatus.STATUS_OK
        task.created = datetime.now(tz=pytz.UTC)
        task.save(update_fields=['status', 'created', ])
