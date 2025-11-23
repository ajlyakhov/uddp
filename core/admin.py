import importlib
import json
import requests

from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from django.conf import settings
from core.models import Task, DataItem, TaskStatus, WebhookLog, DatasourceLog
from reference.helper import pretty_json
from conf.celery import app
# from web.resource_cache import invalidate_cache


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'created', 'source', 'data_type', 'service_platform', 'items')
    list_filter = ('source', 'status', 'data_type')
    readonly_fields = ('id', 'status', 'service_platform', 'publisher_meta_pretty', 'context_pretty')
    date_hierarchy = 'created'
    search_fields = ('id',)
    list_display_links = ('id', 'created', 'source', 'data_type', 'service_platform')
    actions = ('reimport', 'republish', 'clear_log', )

    fieldsets = (
        ('', {
            'fields': ('id', 'status'),
        }),
        ('Source System', {
            'fields': ('publisher_meta_pretty', 'source', 'publisher_date'),
        }),
        ('Consumer', {
            'fields': (
            'service_meta_pretty', 'data_type', 'service_platform', 'service_response', 'service_response_code',
            'service_publish_date', 'service_item_link'),
        }),
        ('Logging', {
            'fields': ('log', 'error_description', 'context_pretty'),
        }),
    )

    def context_pretty(self, obj: Task):
        return pretty_json(obj.context)
    context_pretty.short_description = "Task Execution Context"

    def publisher_meta_pretty(self, obj: Task):
        return pretty_json(obj.publisher_meta)

    publisher_meta_pretty.short_description = "Publication Request JSON Data"

    def service_meta_pretty(self, obj: Task):
        return pretty_json(obj.service_meta)

    service_meta_pretty.short_description = "Service Request JSON Data"

    def items(self, obj: Task):
        items = []
        for item in obj.items.all():
            url = reverse('admin:publish_contentitem_change', args=(item.id,))
            items.append(f"<a href='{url}'>{item.id}</a>")
        return mark_safe("<br>".join(items) if len(items) > 0 else "-")

    items.short_description = "Content Item"

    def status(self, obj: Task):
        colors = {
            TaskStatus.STATUS_PROGRESS: "#FFD733",
            TaskStatus.STATUS_OK: "#4FFF33",
            TaskStatus.STATUS_ERROR: "#FF4513",
            None: "#8e918f",
        }
        status = TaskStatus(obj.status).label if obj.status else "not started"
        html = f"""
        <div style="width:30px;min-width:30px;">
        <a href="#" title="Status - {status}" style='display:inline-block;width:10px;height:10px;border-radius:50%;background-color:{colors[obj.status]}'></a>
        </div>
        """
        return mark_safe(html)

    status.short_description = "Status"

    def service_platform(self, obj: Task):
        try:
            return obj.data_type.consumer
        except:
            return "-"

    service_platform.short_description = "Consumer"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def republish(self, request, queryset):
        for task in queryset:
            for stage in task.data_type.processing_stages.filter(active=True).order_by('step'):
                try:
                    process_module = importlib.import_module(stage.module)
                    process_module.execute(task)
                except Exception as e:
                    task.set_publisher_error(f'module {stage.module} cannot be imported: {e}')
                    return
    republish.short_description = "Republish to Consumer"

    @staticmethod
    @app.task
    def async_reimport(task_id):
        from tempfile import TemporaryDirectory
        from datetime import datetime
        import pytz
        
        task = Task.objects.get(id=task_id)
        
        with TemporaryDirectory() as tmp_dir:
            # Initialize context if None
            if task.context is None:
                task.context = {}
            
            # Set tmp_dir in context
            task.set_context({"tmp_dir": tmp_dir})
            
            for stage in task.data_type.processing_stages.filter(active=True).order_by('step'):
                try:
                    process_module = importlib.import_module(stage.module)
                    process_module.execute(task)
                except Exception as e:
                    task.set_publisher_error(f'module {stage.module} cannot be imported: {e}')
                    return
            
            # Set success status
            task.status = TaskStatus.STATUS_OK
            task.publisher_date = datetime.now(tz=pytz.UTC)
            task.save(update_fields=['status', 'publisher_date'])

    def reimport(self, request, queryset):
        for task in queryset:
            self.async_reimport.delay(task.id)
    reimport.short_description = "Republish from Source System"

    def clear_log(self, request, queryset):
        updated_count = 0
        for task in queryset:
            task.log = None
            task.last_log = None
            task.error_description = None
            task.context = None
            task.service_meta = None
            task.service_response = None
            task.save(update_fields=['log', 'last_log', 'error_description', 'context', 'service_meta', 'service_response'])
            updated_count += 1
        
        self.message_user(request, f"Logs and metadata cleared for {updated_count} tasks.")
    clear_log.short_description = "Clear Log"


@admin.register(DataItem)
class DataItemAdmin(admin.ModelAdmin):
    list_display = ('created', 'type', 'source')
    search_fields = ('id',)
    readonly_fields = ('meta_pretty', )
    exclude = ('meta', )
    raw_id_fields = ('task',)
    list_filter = ('type', 'source')

    def meta_pretty(self, obj: DataItem):
        return pretty_json(obj.meta)

    meta_pretty.short_description = "Package Metadata"

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return False




@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ('created', 'task', 'webhook', 'status_code')
    list_filter = ('webhook', 'status_code')
    date_hierarchy = 'created'


@admin.register(DatasourceLog)
class DatasourceLogAdmin(admin.ModelAdmin):
    list_display = ('created', 'task', 'datasource', 'status_code')
    list_filter = ('datasource', 'status_code')
    date_hierarchy = 'created'
