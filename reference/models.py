
import importlib

from django.db.models import *
import uuid
from reference.storage import PipelineStorage

def pipeline_file_path(instance, filename):
    return f"{uuid.uuid4()}.py"


class Source(Model):
    name = CharField(max_length=512, null=True, verbose_name="Name")
    key = CharField(max_length=512, null=True, verbose_name="Access Key")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Source"
        verbose_name_plural = "Sources"


class DataType(Model):
    name = CharField(max_length=100, null=True, verbose_name="Name")
    source = ForeignKey('reference.Source', on_delete=CASCADE, null=True, verbose_name="Source System")
    source_code = CharField(max_length=100, null=True, verbose_name="Source System Content Code")
    consumer = ForeignKey('reference.Consumer', on_delete=CASCADE, null=True,
                                  verbose_name="Consumer")

    def __str__(self):
        return f"{self.name} ({self.source})"

    class Meta:
        verbose_name = "Data Type"
        verbose_name_plural = "Data Types"


class ProcessingStage(Model):
    data_type = ForeignKey('reference.DataType', on_delete=CASCADE, null=True,
                                   verbose_name="Data Type", related_name="processing_stages")
    step = IntegerField(default=0, verbose_name="Processing Step")
    module_file = FileField(storage=PipelineStorage(), upload_to=pipeline_file_path, null=True, verbose_name="Processing Software Module")
    active = BooleanField(default=True, verbose_name="Processing Stage Active")

    def __str__(self):
        return f"Step {self.step}"

    class Meta:
        verbose_name = "Processing Stage"
        verbose_name_plural = "Processing Stages"
        ordering = ('step', )


class Consumer(Model):
    class Types(TextChoices):
        WEBHOOK = "webhook", "Webhook"
        DATASOURCE = "datasource", "DataSource"

    name = CharField(max_length=1024, null=True, blank=True, verbose_name="Name")
    type = CharField(max_length=50, choices=Types.choices, default=Types.WEBHOOK, verbose_name="Type")
    key = CharField(max_length=1024, null=True, blank=True, verbose_name="Access Key")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Consumer"
        verbose_name_plural = "Consumers"






