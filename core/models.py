from django.db.models import *


class TaskStatus(IntegerChoices):
    STATUS_ERROR = 0, "Error"
    STATUS_OK = 1, "Success"
    STATUS_PROGRESS = 2, "Processing"


class Task(Model):
    created = DateTimeField(auto_now_add=True)

    # Input
    meta = JSONField(null=True, verbose_name="Publication Request JSON Data")
    source = ForeignKey('reference.Source', on_delete=CASCADE, null=True, verbose_name="Source System")

    # Processing
    status = IntegerField(choices=TaskStatus.choices, null=True, verbose_name="[SS] Processing Status")

    # Context
    context = JSONField(null=True, blank=True, verbose_name="Task Execution Context")

    # Output
    data_type = ForeignKey('reference.DataType', on_delete=SET_NULL, null=True, verbose_name="Target Service",
                         related_name="tasks")
    workspace = ForeignKey('reference.Workspace', on_delete=CASCADE, null=True, verbose_name="Workspace")

    # Internal Logging
    log = TextField(null=True, blank=True, verbose_name="Task Processing Log")
    last_log = TextField(null=True, blank=True, verbose_name="Last Log Line")
    progress = IntegerField(default=0, verbose_name="Progress in Percent")
    total_tasks = IntegerField(default=0, verbose_name="Total Task Execution Stages")
    current_task = IntegerField(default=0, verbose_name="Current Task Execution Stage")
    error_description = TextField(null=True, blank=True, verbose_name="Error Description")

    class Meta:
        verbose_name = "Task"
        verbose_name_plural = "Tasks"

    def __str__(self):
        return f"Task #{self.id}"

    def logging(self, type: str, message: str):
        log_message = f"[{type}] {message}"
        # Truncate last_log to 200 chars for backward compatibility
        self.last_log = log_message[:200] if len(log_message) > 200 else log_message
        if self.log:
            self.log = f"{self.log}\n{log_message}"
        else:
            self.log = log_message
        self.save(update_fields=['log', 'last_log', ])

    def logging_last(self, type: str, message: str):
        log_message = f"[{type}] {message}"
        # Truncate last_log to 200 chars for backward compatibility
        self.last_log = log_message[:200] if len(log_message) > 200 else log_message
        if self.log:
            lines = self.log.split('\n')
            lines[-1] = log_message
            self.log = '\n'.join(lines)
        else:
            self.log = log_message
        self.save(update_fields=['log', 'last_log', ])

    def set_error(self, message: str):
        self.logging('ERR', message)
        self.error_description = message
        self.status = TaskStatus.STATUS_ERROR
        self.save(update_fields=['error_description', 'status'])

    def set_context(self, data: dict):
        self.context.update(data)
        self.save(update_fields=['context', ])


class DataItem(Model):
    created = DateTimeField(auto_now_add=True)
    type = ForeignKey('reference.DataType', on_delete=SET_NULL, null=True, verbose_name="Content Type")
    source = ForeignKey('reference.Source', on_delete=SET_NULL, null=True, verbose_name="Source System")
    meta = JSONField(null=True, blank=True, verbose_name="Package Metadata")
    task = ForeignKey('core.Task', on_delete=SET_NULL, null=True, verbose_name="Publication Task",
                      related_name="items")
    workspace = ForeignKey('reference.Workspace', on_delete=CASCADE, null=True, verbose_name="Workspace")

    class Meta:
        verbose_name = "Data Item"
        verbose_name_plural = "Data Items"

    def __str__(self):
        return f"{self.type} / {self.source}"


class WebhookLog(Model):
    created = DateTimeField(auto_now_add=True)
    task = ForeignKey('core.Task', on_delete=SET_NULL, null=True, verbose_name="Publication Task",
                      related_name="webhook_logs")
    webhook = ForeignKey('reference.Webhook', on_delete=SET_NULL, null=True, verbose_name="Webhook")
    workspace = ForeignKey('reference.Workspace', on_delete=CASCADE, null=True, verbose_name="Workspace")

    response = JSONField(null=True, blank=True, verbose_name="Response Body")
    status_code = IntegerField(null=True, verbose_name="Status Code")
    headers = JSONField(null=True, blank=True, verbose_name="Response Headers")

    class Meta:
        verbose_name = "Webhook Log"
        verbose_name_plural = "Webhook Logs"

    def __str__(self):
        return f"{self.task} / {self.webhook}"


class DatasourceLog(Model):
    created = DateTimeField(auto_now_add=True)
    task = ForeignKey('core.Task', on_delete=SET_NULL, null=True, verbose_name="Publication Task",
                      related_name="datasource_logs")
    datasource = ForeignKey('reference.DataSource', on_delete=SET_NULL, null=True, verbose_name="Datasource")
    workspace = ForeignKey('reference.Workspace', on_delete=CASCADE, null=True, verbose_name="Workspace")

    response = JSONField(null=True, blank=True, verbose_name="Response Body")
    status_code = IntegerField(null=True, verbose_name="Status Code")
    headers = JSONField(null=True, blank=True, verbose_name="Response Headers")

    class Meta:
        verbose_name = "Datasource Log"
        verbose_name_plural = "Datasource Logs"

    def __str__(self):
        return f"{self.task} / {self.datasource}"