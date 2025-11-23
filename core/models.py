from django.db.models import *


class TaskStatus(IntegerChoices):
    STATUS_ERROR = 0, "Error"
    STATUS_OK = 1, "Success"
    STATUS_PROGRESS = 2, "Processing"


class Task(Model):
    created = DateTimeField(auto_now_add=True)

    # Input
    publisher_meta = JSONField(null=True, verbose_name="Publication Request JSON Data")
    source = ForeignKey('reference.Source', on_delete=CASCADE, null=True, verbose_name="Source System")
    publisher_status = IntegerField(choices=TaskStatus.choices, null=True, verbose_name="[SS] Processing Status")
    publisher_date = DateTimeField(null=True, blank=True, verbose_name="Publication Processing Date")

    # Output
    service_meta = JSONField(null=True, verbose_name="Service Request JSON Data")
    service_response = JSONField(null=True, verbose_name="Service Response JSON Data")
    service_response_code = IntegerField(null=True, blank=True, verbose_name="Service Response Code")
    service = ForeignKey('reference.DataType', on_delete=SET_NULL, null=True, verbose_name="Target Service",
                         related_name="tasks")
    service_status = IntegerField(choices=TaskStatus.choices, null=True, verbose_name="[PS] Publication Status")
    service_publish_date = DateTimeField(null=True, blank=True, verbose_name="Service Publication Date")
    service_item_link = URLField(max_length=2048, null=True, blank=True, verbose_name="Link to Published Item in Service")

    # Internal Logging
    log = TextField(null=True, blank=True, verbose_name="Task Processing Log")
    last_log = TextField(null=True, blank=True, verbose_name="Last Log Line")
    progress = IntegerField(default=0, verbose_name="Progress in Percent")
    total_tasks = IntegerField(default=0, verbose_name="Total Task Execution Stages")
    current_task = IntegerField(default=0, verbose_name="Current Task Execution Stage")
    error_description = TextField(null=True, blank=True, verbose_name="Error Description")

    # S3 Upload Progress
    uploaded_files = IntegerField(default=0, verbose_name="Files Uploaded to S3")
    total_files = IntegerField(default=0, verbose_name="Total Files to Upload to S3")

    # Context
    context = JSONField(null=True, blank=True, verbose_name="Task Execution Context")

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

    def set_publisher_error(self, message: str):
        self.logging('ERR', message)
        self.error_description = message
        self.publisher_status = TaskStatus.STATUS_ERROR
        self.save(update_fields=['error_description', 'publisher_status'])

    def set_context(self, data: dict):
        self.context.update(data)
        self.save(update_fields=['context', ])

    @property
    def upload_progress(self):
        if self.total_files == 0:
            return 0
        return int(self.uploaded_files / self.total_files * 100)

    def inc_uploaded_files(self) -> int:
        self.uploaded_files += 1
        self.save(update_fields=['uploaded_files'])
        return self.uploaded_files

    def set_total_files(self, total) -> None:
        self.total_files = total
        self.save(update_fields=['total_files'])


class DataItem(Model):
    created = DateTimeField(auto_now_add=True)
    type = ForeignKey('reference.DataType', on_delete=SET_NULL, null=True, verbose_name="Content Type")
    source = ForeignKey('reference.Source', on_delete=SET_NULL, null=True, verbose_name="Source System")
    meta = JSONField(null=True, blank=True, verbose_name="Package Metadata")
    internal_meta = JSONField(null=True, blank=True, verbose_name="Internal Package Metadata")
    task = ForeignKey('core.Task', on_delete=SET_NULL, null=True, verbose_name="Publication Task",
                      related_name="items")
    storage = URLField(max_length=4096, null=True, blank=True, verbose_name="Storage Folder Path")
    sku = CharField(max_length=1024, null=True, blank=True, verbose_name="SKU", db_index=True)
    year = IntegerField(null=True, blank=True, verbose_name="Year of Publication", db_index=True)
    cover = URLField(max_length=4096, null=True, blank=True, verbose_name="Cover Path")
    offline = URLField(max_length=4096, null=True, blank=True, verbose_name="Offline Archive Path")
    offline_size = BigIntegerField(null=True, blank=True, verbose_name="Offline Package Size")
    start_file = CharField(max_length=1024, null=True, blank=True, verbose_name="Start File")

    class Meta:
        verbose_name = "Data Item"
        verbose_name_plural = "Data Items"

    def __str__(self):
        return f"{self.sku} / {self.year}"




class Webhook(Model):
    consumer = ForeignKey('reference.Consumer', on_delete=CASCADE, null=True, verbose_name="Consumer")
    url = URLField(max_length=2048, null=True, verbose_name="Webhook URL")
    jwt_secret = CharField(max_length=1024, null=True, blank=True, verbose_name="JWT Secret")
    aud = CharField(max_length=100, null=True, blank=True, verbose_name="AUD")
    ttl = IntegerField(default=3600, verbose_name="JWT TTL (seconds)")
    task = ForeignKey('core.Task', on_delete=CASCADE, null=True, verbose_name="Task", related_name="webhooks")

    class Meta:
        verbose_name = "Webhook"
        verbose_name_plural = "Webhooks"

    def __str__(self):
        return f"Webhook for {self.consumer}"


class DataSource(Model):
    class Types(TextChoices):
        POSTGRES = "postgres", "PostgreSQL"
        DUCKDB = "duckdb", "DuckDB"

    type = CharField(max_length=50, choices=Types.choices, default=Types.POSTGRES, verbose_name="Type")
    connection = CharField(max_length=2048, null=True, verbose_name="Connection String")
    task = ForeignKey('core.Task', on_delete=CASCADE, null=True, verbose_name="Task", related_name="datasources")

    class Meta:
        verbose_name = "Data Source"
        verbose_name_plural = "Data Sources"

    def __str__(self):
        return f"{self.type} DataSource"
