import importlib
import json
import requests

from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from django.conf import settings
from core.models import Task, ContentItem, TaskStatus
from reference.helper import pretty_json
from conf.celery import app
# from web.resource_cache import invalidate_cache


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'created', 'source', 'service', 'service_platform', 'items')
    list_filter = ('source', 'publisher_status', 'service', 'service_status')
    readonly_fields = ('id', 'status', 'service_platform', 'publisher_meta_pretty', 'context_pretty')
    date_hierarchy = 'created'
    search_fields = ('items__sku',)
    list_display_links = ('id', 'created', 'source', 'service', 'service_platform')
    actions = ('reimport', 'republish', 'clear_log', )

    fieldsets = (
        ('', {
            'fields': ('id', 'status'),
        }),
        ('Издательская система', {
            'fields': ('publisher_meta_pretty', 'source', 'publisher_status', 'publisher_date'),
        }),
        ('Сервисная платформа', {
            'fields': (
            'service_meta_pretty', 'service', 'service_platform', 'service_response', 'service_response_code',
            'service_status', 'service_publish_date', 'service_item_link'),
        }),
        ('Логирование', {
            'fields': ('log', 'error_description', 'context_pretty'),
        }),
    )

    def context_pretty(self, obj: Task):
        return pretty_json(obj.context)
    context_pretty.short_description = "Контекст выполнения задачи"

    def publisher_meta_pretty(self, obj: Task):
        return pretty_json(obj.publisher_meta)

    publisher_meta_pretty.short_description = "JSON данные запроса на публикацию"

    def service_meta_pretty(self, obj: Task):
        return pretty_json(obj.service_meta)

    service_meta_pretty.short_description = "JSON данные запроса в сервис"

    def items(self, obj: Task):
        items = []
        for item in obj.items.all():
            url = reverse('admin:publish_contentitem_change', args=(item.id,))
            items.append(f"<a href='{url}'>{item.sku}/{item.year}</a>")
        return mark_safe("<br>".join(items) if len(items) > 0 else "-")

    items.short_description = "ЕК"

    def status(self, obj: Task):
        colors = {
            TaskStatus.STATUS_PROGRESS: "#FFD733",
            TaskStatus.STATUS_OK: "#4FFF33",
            TaskStatus.STATUS_ERROR: "#FF4513",
            None: "#8e918f",
        }
        publisher_status = TaskStatus(obj.publisher_status).label if obj.publisher_status else "не начато"
        service_status = TaskStatus(obj.service_status).label if obj.service_status else "не начато"
        html = f"""
        <div style="width:30px;min-width:30px;">
        <a href="#" title="Издательская система - {publisher_status}" style='display:inline-block;width:10px;height:10px;border-radius:50%;background-color:{colors[obj.publisher_status]}'></a>
        <a href="#" title="Сервисная платформа - {service_status}" style='display:inline-block;width:10px;height:10px;border-radius:50%;background-color:{colors[obj.service_status]}'></a>
        </div>
        """
        return mark_safe(html)

    status.short_description = "Статус"

    def service_platform(self, obj: Task):
        try:
            return obj.service.target
        except:
            return "-"

    service_platform.short_description = "Сервисная платформа"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def republish(self, request, queryset):
        for task in queryset:
            for stage in task.service.target_stages.filter(active=True).order_by('step'):
                try:
                    process_module = importlib.import_module(stage.module)
                    process_module.execute(task)
                except Exception as e:
                    task.set_publisher_error(f'module {stage.module} cannot be imported: {e}')
                    return
    republish.short_description = "Переопубликовать на сервисную платформу"

    @staticmethod
    @app.task
    def async_reimport(task_id):
        from tempfile import TemporaryDirectory
        from datetime import datetime
        import pytz
        
        task = Task.objects.get(id=task_id)
        
        with TemporaryDirectory() as tmp_dir:
            # Инициализируем контекст если он None
            if task.context is None:
                task.context = {}
            
            # Устанавливаем tmp_dir в контекст
            task.set_context({"tmp_dir": tmp_dir})
            
            for stage in task.service.source_stages.filter(active=True).order_by('step'):
                try:
                    process_module = importlib.import_module(stage.module)
                    process_module.execute(task)
                except Exception as e:
                    task.set_publisher_error(f'module {stage.module} cannot be imported: {e}')
                    return
            
            # Устанавливаем успешный статус
            task.publisher_status = TaskStatus.STATUS_OK
            task.publisher_date = datetime.now(tz=pytz.UTC)
            task.save(update_fields=['publisher_status', 'publisher_date'])

    def reimport(self, request, queryset):
        for task in queryset:
            self.async_reimport.delay(task.id)
    reimport.short_description = "Переопубликовать из издательской системы"

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
        
        self.message_user(request, f"Очищены логи и метаданные для {updated_count} задач.")
    clear_log.short_description = "Очистить лог"


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = ('created', 'type', 'source', 'sku', 'year')
    search_fields = ('sku',)
    readonly_fields = ('full_link', 'demo_link', 'meta_pretty', 'internal_meta_pretty', )
    exclude = ('meta', 'internal_meta')
    raw_id_fields = ('task',)
    actions = ('clear_cache', 'test_cdn_connection')
    list_filter = ('type', 'source')

    def meta_pretty(self, obj: ContentItem):
        return pretty_json(obj.meta)

    meta_pretty.short_description = "Метаданные пакета"

    def internal_meta_pretty(self, obj: ContentItem):
        return pretty_json(obj.internal_meta)

    internal_meta_pretty.short_description = "Метаданные внутри пакета"

    def full_link(self, obj):
        url = obj.get_absolute_url()
        return mark_safe(f"<a href='{url}' target='_blank'>Открыть</a>")

    full_link.short_description = "Ссылка на полную версию"

    def demo_link(self, obj):
        url = obj.get_absolute_url(demo=True)
        return mark_safe(f"<a href='{url}' target='_blank'>Открыть</a>")

    demo_link.short_description = "Ссылка на демо версию"

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return False

    def clear_cache(self, request, queryset):
        """
        Очищает кэш Redis и CDN для выбранных ContentItem
        """
        cleared_count = 0
        errors = []
        
        for content_item in queryset:
            try:
                # Определяем base_path для очистки кэша
                base_path = self._get_cache_base_path(content_item)
                
                if base_path:
                    # Очищаем Redis кэш
                    # redis_cleared = invalidate_cache(base_path, None)
                    redis_cleared = 0
                    
                    # Очищаем CDN кэш
                    cdn_cleared = self._clear_cdn_cache(content_item)
                    
                    cleared_count += 1
                    self.message_user(
                        request, 
                        f"Очищен кэш для {content_item.sku}/{content_item.year}: "
                        f"Redis ({redis_cleared} ключей), CDN ({cdn_cleared})"
                    )
                else:
                    errors.append(f"Не удалось определить путь кэша для {content_item.sku}/{content_item.year}")
                    
            except Exception as e:
                errors.append(f"Ошибка при очистке кэша для {content_item.sku}/{content_item.year}: {str(e)}")
        
        if errors:
            self.message_user(request, f"Ошибки при очистке кэша: {'; '.join(errors)}", level='WARNING')
        
        if cleared_count > 0:
            self.message_user(request, f"Успешно очищен кэш для {cleared_count} элементов контента.")
    
    clear_cache.short_description = "Сбросить кэш"
    
    def _get_cache_base_path(self, content_item):
        """
        Определяет base_path для очистки кэша на основе ContentItem
        """
        try:
            # Если есть offline URL, извлекаем путь из него
            if content_item.offline:
                base_path = "/".join(content_item.offline.split("/")[:-1])
                base_path = base_path.split("://")[1]
                base_path = "/".join(base_path.split("/")[3:])
                return base_path
            
            # Если есть internal_meta с информацией о контенте
            if content_item.internal_meta:
                internal_meta = content_item.internal_meta
                
                # Для efu_mob типа
                if "content" in internal_meta and "code" in internal_meta and "year" in internal_meta:
                    return "/".join([internal_meta["content"], internal_meta["code"], internal_meta["year"]])
                
                # Для playlist типа
                if content_item.type and "efu_html" in str(content_item.type):
                    return f'efu_html/{content_item.sku}/{content_item.year}/'
            
            # Fallback: используем тип контента, sku и year
            if content_item.type and content_item.sku and content_item.year:
                type_name = str(content_item.type).lower()
                return f'{type_name}/{content_item.sku}/{content_item.year}/'
                
        except Exception as e:
            pass
            
        return None
    
    def _clear_cdn_cache(self, content_item):
        """
        Очищает CDN кэш для ContentItem
        """
        if not settings.CDN_PURGE:
            return "CDN не настроен"
            
        try:
            # Определяем путь для CDN
            if content_item.internal_meta and "content" in content_item.internal_meta:
                content_type = content_item.internal_meta["content"]
                code = content_item.internal_meta.get("code", content_item.sku)
                year = content_item.internal_meta.get("year", content_item.year)
            else:
                # Fallback
                content_type = str(content_item.type).lower() if content_item.type else "unknown"
                code = content_item.sku
                year = content_item.year
            
            path = f"/{settings.S3_BUCKET}/{content_type}/{code}/{year}/"
            
            url = "https://api.cdn2.cloud.ru/cdn/resources/187148/purge"
            headers = {
                "Authorization": f"APIKey {settings.CDN_PURGE}",
                "Content-Type": "application/json",
            }
            data = json.dumps({
                "paths": [path]
            })
            
            response = requests.post(url, data=data, headers=headers, verify=False, timeout=60)
            
            if response.status_code in [200, 201]:
                return f"OK ({path})"
            elif response.status_code == 401:
                return f"Ошибка авторизации (401) - проверьте CDN_PURGE"
            elif response.status_code == 403:
                return f"Доступ запрещен (403) - недостаточно прав"
            elif response.status_code == 404:
                return f"Ресурс не найден (404) - проверьте путь {path}"
            else:
                try:
                    error_detail = response.json()
                    return f"Ошибка {response.status_code}: {error_detail}"
                except:
                    return f"Ошибка {response.status_code}: {response.text[:100]}"
                
        except Exception as e:
            return f"Ошибка: {str(e)}"
    
    def test_cdn_connection(self, request, queryset):
        """
        Тестирует соединение с CDN API
        """
        if not settings.CDN_PURGE:
            self.message_user(request, "CDN_PURGE не настроен в переменных окружения", level='ERROR')
            return
            
        try:
            # Тестовый запрос с минимальным путем
            url = "https://api.cdn2.cloud.ru/cdn/resources/187148/purge"
            headers = {
                "Authorization": f"APIKey {settings.CDN_PURGE}",
                "Content-Type": "application/json",
            }
            data = json.dumps({
                "paths": ["/test/path/"]
            })
            
            response = requests.post(url, data=data, headers=headers, verify=False, timeout=30)
            
            if response.status_code in [200, 201]:
                self.message_user(request, f"CDN API доступен. Токен корректный. Ответ: {response.text[:200]}")
            elif response.status_code == 401:
                self.message_user(request, "CDN API недоступен. Ошибка авторизации (401) - проверьте CDN_PURGE", level='ERROR')
            elif response.status_code == 403:
                self.message_user(request, "CDN API недоступен. Доступ запрещен (403) - недостаточно прав", level='ERROR')
            else:
                self.message_user(request, f"CDN API вернул код {response.status_code}. Ответ: {response.text[:200]}", level='WARNING')
                
        except requests.exceptions.Timeout:
            self.message_user(request, "CDN API недоступен. Таймаут соединения", level='ERROR')
        except requests.exceptions.ConnectionError:
            self.message_user(request, "CDN API недоступен. Ошибка соединения", level='ERROR')
        except Exception as e:
            self.message_user(request, f"Ошибка при тестировании CDN: {str(e)}", level='ERROR')
    
    test_cdn_connection.short_description = "Тестировать CDN соединение"
