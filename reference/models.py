import importlib

from django.db.models import *


class Source(Model):
    name = CharField(max_length=512, null=True, verbose_name="Name")
    key = CharField(max_length=512, null=True, verbose_name="Access Key")
    validator = CharField(max_length=1024, null=True, blank=True, verbose_name="Publication Metadata Validation Model")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Source System"
        verbose_name_plural = "Source Systems"


class SourceContentMap(Model):
    name = CharField(max_length=1024, null=True, verbose_name="Content Type Name")
    source = ForeignKey('reference.Source', on_delete=CASCADE, null=True, verbose_name="Source System")
    source_code = CharField(max_length=100, null=True, verbose_name="Source System Content Code")
    target_code = CharField(max_length=100, null=True, verbose_name="Target Content Code")
    target = ForeignKey('reference.Target', on_delete=CASCADE, null=True,
                                  verbose_name="Target Platform")
    modifier_module = CharField(max_length=1024, null=True, blank=True, verbose_name="Demo Mode Modifier")
    link_module = CharField(max_length=1024, null=True, blank=True, verbose_name="Unified Collection Link Generator")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Content Type"
        verbose_name_plural = "Content Types"

    def get_link(self, sku, year, demo=False):
        process_module = importlib.import_module(self.link_module)
        return process_module.execute(sku=sku,
                                      year=year,
                                      secret=self.target.read_jwt_secret,
                                      code=self.target_code,
                                      demo=demo)


class SourceStage(Model):
    source_content = ForeignKey('reference.SourceContentMap', on_delete=CASCADE, null=True,
                                   verbose_name="Content Type", related_name="source_stages")
    step = IntegerField(default=0, verbose_name="Processing Step")
    module = CharField(max_length=1024, null=True, blank=True, verbose_name="Processing Software Module")
    active = BooleanField(default=True, verbose_name="Processing Stage Active")

    def __str__(self):
        return f"Step {self.step}"

    class Meta:
        verbose_name = "[Source] Processing Stage"
        verbose_name_plural = "[Source] Processing Stages"
        ordering = ('step', )


class Target(Model):
    name = CharField(max_length=1024, null=True, blank=True, verbose_name="Name")
    publish_jwt_secret = CharField(max_length=1024, null=True, blank=True,
                                   verbose_name="Metadata Publishing Secret")
    publish_api = CharField(max_length=1024, null=True, blank=True, verbose_name="Metadata Publishing API")
    unpublish_api = CharField(max_length=1024, null=True, blank=True, verbose_name="Unpublishing API")
    read_jwt_secret = CharField(max_length=1024, null=True, blank=True, verbose_name="Content Reading Secret")
    aud = CharField(max_length=100, null=True, blank=False, verbose_name="AUD for Reading JWT Tokens", db_index=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Target Platform"
        verbose_name_plural = "Target Platforms"


class TargetStage(Model):
    target_content = ForeignKey('reference.SourceContentMap', on_delete=CASCADE, null=True, blank=True,
                                  verbose_name="Target Platform", related_name="target_stages")
    step = IntegerField(default=0, verbose_name="Processing Step")
    module = CharField(max_length=1024, null=True, blank=True, verbose_name="Processing Software Module")
    active = BooleanField(default=True, verbose_name="Processing Stage Active")

    def __str__(self):
        return str(self.step)

    class Meta:
        verbose_name = "[Target] Processing Stage"
        verbose_name_plural = "[Target] Processing Stages"



