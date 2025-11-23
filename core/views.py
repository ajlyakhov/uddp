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
from core.tasks import process_publisher


@method_decorator(csrf_exempt, name='dispatch')
class PublishView(View):

    def post(self, request):
        try:
            token = request.META["HTTP_AUTHORIZATION"].split("Token ")[1]
            source = Source.objects.get(key=token)
        except Source.DoesNotExist:
            response = HttpResponse("Invalid token", status=403)
            return response

        task = Task.objects.create(source=source, context={})

        try:
            body = request.body.decode()
            body = body.replace('""', '"/"')
            publisher_meta = json.loads(body)
        except Exception as e:
            response = JsonResponse({"error_description": str(e), "error": "invalid JSON"}, status=400)
            return response

        task.publisher_meta = publisher_meta
        task.publisher_status = TaskStatus.STATUS_PROGRESS
        task.save(update_fields=['publisher_meta', 'publisher_status'])

        # проверяем запрос на валидность для данной издательской системы
        if source.validator:
            try:
                validator_module = importlib.import_module(source.validator)
                validator_module.validate(task.publisher_meta)
            except Exception as e:
                response = JsonResponse({"error_description": str(e), "error": "invalid meta"}, status=400)
                return response

        # находим тип контента
        content = None
        if publisher_meta.get('media_type', None):
            content = DataType.objects.filter(source=source,
                                                         source_code=publisher_meta.get('media_type')).first()
        elif publisher_meta.get('content', None):
            content = DataType.objects.filter(source=source,
                                                         source_code=publisher_meta.get('content')).first()

        if not content:
            response = JsonResponse({"error_description": "Unknown content type", "error": "invalid meta"}, status=400)
            return response

        task.service = content
        task.save(update_fields=['service', ])

        if settings.DEBUG:
            process_publisher(task.id)
        else:
            @transaction.on_commit
            def execute_async_publish() -> None:
                # запускаем асинхронный процесс обработки публикации
                process_publisher.delay(task.id)

        return JsonResponse({"code": task.publisher_meta["code"], "task": task.id}, status=200)


class StatusView(View):

    def get(self, request, task_id):
        try:
            token = request.META["HTTP_AUTHORIZATION"].split("Token ")[1]
            source = Source.objects.get(key=token)
        except Source.DoesNotExist:
            response = HttpResponse("Invalid token", status=403)
            return response
        except Exception as e:
            response = HttpResponse("You should pass token in Authorization header", status=400)
            return response

        try:
            task = Task.objects.get(source=source, id=task_id)

            if task.publisher_status == TaskStatus.STATUS_ERROR or task.service_status == TaskStatus.STATUS_ERROR:
                return JsonResponse({
                    "task": task.id,
                    "code": None,
                    "status": TaskStatus.STATUS_ERROR,
                    "progress": task.progress,
                    "upload_progress": task.upload_progress,
                    "description": "",
                    "last_log": task.last_log,
                    "error": task.error_description,
                    "preview-url": task.service_item_link,
                })

            if task.items.count() > 0:
                ci = task.items.filter().first()
                return JsonResponse({
                    "task": task.id,
                    "code": ci.sku,
                    "status": task.service_status if task.service_status else TaskStatus.STATUS_PROGRESS,
                    "progress": task.progress,
                    "upload_progress": task.upload_progress,
                    "last_log": task.last_log,
                    "description": "",
                    "error": "",
                    "preview-url": task.service_item_link,
                })
            else:
                return JsonResponse({
                    "task": task.id,
                    "code": None,
                    "status": TaskStatus.STATUS_PROGRESS,
                    "progress": task.progress,
                    "last_log": task.last_log,
                    "description": "",
                    "error": "",
                    "preview-url": task.service_item_link,
                })

        except Task.DoesNotExist:
            return JsonResponse({
                "code": 0,
                "verbose": "requested task ID not found",
            }, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class UnPublishView(View):

    def post(self, request):
        try:
            token = request.META["HTTP_AUTHORIZATION"].split("Token ")[1]
            source = Source.objects.get(key=token)
        except Source.DoesNotExist:
            response = HttpResponse("Invalid token", status=403)
            return response

        body = request.body.decode()
        body = body.replace('""', '"/"')
        data = json.loads(body)
        task = Task.objects.filter(id=data["id"], source=source).first()
        if not task:
            return JsonResponse({
                "code": 0,
                "verbose": "Invalid task number",
                "task": data["id"],
            }, status=400)

        # Note: unpublish_stages functionality has been removed
        # as UnPublishStage model was deleted during refactoring

        return JsonResponse({
            "error": False,
            "error_text": None,
            "task": task.id,
        })
