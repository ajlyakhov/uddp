import importlib
import json

from django.conf import settings
from django.db import transaction
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from core.models import Task, TaskStatus
from reference.models import Source, DataType
from core.tasks import process_source_data


@method_decorator(csrf_exempt, name='dispatch')
class PublishView(View):
    def post(self, request):
        try:
            token = request.META["HTTP_AUTHORIZATION"].split("Token ")[1]
            source = Source.objects.get(key=token)
        except (KeyError, IndexError, Source.DoesNotExist):
            return HttpResponse("Invalid token", status=403)

        task = Task.objects.create(source=source, context={})

        try:
            body = request.body.decode()
            body = body.replace('""', '"/"')
            meta = json.loads(body)
        except Exception as e:
            return JsonResponse({"error_description": str(e), "error": "invalid JSON"}, status=400)

        task.meta = meta
        task.status = TaskStatus.STATUS_PROGRESS
        task.save(update_fields=['meta', 'status'])

        data_type = None
        if meta.get('type', None):
            data_type = DataType.objects.filter(source=source, source_code=meta.get('type')).first()

        if not data_type:
            return JsonResponse({"error_description": "Unknown data type", "error": "invalid meta"}, status=400)

        task.data_type = data_type
        task.save(update_fields=['data_type', ])

        if settings.DEBUG:
            process_source_data(task.id)
        else:
            @transaction.on_commit
            def execute_async_publish() -> None:
                process_source_data.delay(task.id)

        return JsonResponse({"code": task.data_type.source_code, "task": task.id}, status=200)


class StatusView(View):
    def get(self, request, task_id):
        try:
            token = request.META["HTTP_AUTHORIZATION"].split("Token ")[1]
            source = Source.objects.get(key=token)
        except (KeyError, IndexError, Source.DoesNotExist):
            return HttpResponse("Invalid token", status=403)

        try:
            task = Task.objects.get(source=source, id=task_id)

            if task.status == TaskStatus.STATUS_ERROR:
                return JsonResponse({
                    "task": task.id,
                    "code": None,
                    "status": TaskStatus.STATUS_ERROR,
                    "progress": task.progress,
                    "description": "",
                    "last_log": task.last_log,
                    "error": task.error_description,
                })

            if task.items.count() > 0:
                ci = task.items.filter().first()
                return JsonResponse({
                    "task": task.id,
                    "code": ci.type.source_code if ci.type else None,
                    "status": task.status,
                    "progress": task.progress,
                    "last_log": task.last_log,
                    "description": "",
                    "error": "",
                })
            else:
                return JsonResponse({
                    "task": task.id,
                    "code": None,
                    "status": task.status,
                    "progress": task.progress,
                    "last_log": task.last_log,
                    "description": "",
                    "error": "",
                })

        except Task.DoesNotExist:
            return JsonResponse({
                "code": 0,
                "verbose": "requested task ID not found",
            }, status=400)
