
import importlib

from django.db.models import *
import uuid
from reference.storage import PipelineStorage

def pipeline_file_path(instance, filename):
    return f"{uuid.uuid4()}.py"


def plugin_file_path(instance, filename):
    return f"plugins/{uuid.uuid4()}.zip"


class Workspace(Model):
    name = CharField(max_length=512, verbose_name="Name")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Workspace"
        verbose_name_plural = "Workspaces"


class Team(Model):
    workspace = ForeignKey('reference.Workspace', on_delete=CASCADE, verbose_name="Workspace", related_name="teams")
    name = CharField(max_length=512, verbose_name="Name")

    def __str__(self):
        return f"{self.name} ({self.workspace})"

    class Meta:
        verbose_name = "Team"
        verbose_name_plural = "Teams"


class TeamMember(Model):
    class Roles(TextChoices):
        MAINTAINER = "maintainer", "Maintainer"
        DEVELOPER = "developer", "Developer"

    team = ForeignKey('reference.Team', on_delete=CASCADE, verbose_name="Team", related_name="members")
    user = ForeignKey('auth.User', on_delete=CASCADE, verbose_name="User", related_name="team_memberships")
    role = CharField(max_length=50, choices=Roles.choices, default=Roles.DEVELOPER, verbose_name="Role")

    def __str__(self):
        return f"{self.user} - {self.team} ({self.role})"

    class Meta:
        verbose_name = "Team Member"
        verbose_name_plural = "Team Members"


class PluginRepo(Model):
    name = CharField(max_length=512, verbose_name="Name")
    url = URLField(max_length=2048, verbose_name="Repository URL")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Plugin Repository"
        verbose_name_plural = "Plugin Repositories"


class Plugin(Model):
    name = CharField(max_length=512, verbose_name="Name")
    repo = ForeignKey('reference.PluginRepo', on_delete=CASCADE, verbose_name="Repository", related_name="plugins")
    file = FileField(upload_to=plugin_file_path, verbose_name="Plugin File")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Plugin"
        verbose_name_plural = "Plugins"

class Source(Model):
    name = CharField(max_length=512, null=True, verbose_name="Name")
    key = CharField(max_length=512, null=True, verbose_name="Access Key")
    workspace = ForeignKey('reference.Workspace', on_delete=CASCADE, null=True, verbose_name="Workspace")

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
    workspace = ForeignKey('reference.Workspace', on_delete=CASCADE, null=True, verbose_name="Workspace")

    def __str__(self):
        return f"{self.name} ({self.source})"

    class Meta:
        verbose_name = "Data Type"
        verbose_name_plural = "Data Types"


class ProcessingStage(Model):
    data_type = ForeignKey('reference.DataType', on_delete=CASCADE, null=True,
                                   verbose_name="Data Type", related_name="processing_stages")
    step = IntegerField(default=0, verbose_name="Processing Step")
    plugin = ForeignKey('reference.Plugin', on_delete=CASCADE, null=True, verbose_name="Plugin")
    active = BooleanField(default=True, verbose_name="Processing Stage Active")
    workspace = ForeignKey('reference.Workspace', on_delete=CASCADE, null=True, verbose_name="Workspace")

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

    webhook = ForeignKey('reference.Webhook', on_delete=CASCADE, null=True, blank=True, verbose_name="Webhook")
    datasource = ForeignKey('reference.DataSource', on_delete=CASCADE, null=True, blank=True, verbose_name="DataSource")
    workspace = ForeignKey('reference.Workspace', on_delete=CASCADE, null=True, verbose_name="Workspace")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Consumer"
        verbose_name_plural = "Consumers"


class Webhook(Model):
    url = URLField(max_length=2048, null=True, verbose_name="Webhook URL")
    jwt_secret = CharField(max_length=1024, null=True, blank=True, verbose_name="JWT Secret")
    aud = CharField(max_length=100, null=True, blank=True, verbose_name="AUD")
    ttl = IntegerField(default=3600, verbose_name="JWT TTL (seconds)")
    workspace = ForeignKey('reference.Workspace', on_delete=CASCADE, null=True, verbose_name="Workspace")

    class Meta:
        verbose_name = "Webhook"
        verbose_name_plural = "Webhooks"

    def __str__(self):
        return f"Webhook {self.url}"


class DataSource(Model):
    class Types(TextChoices):
        POSTGRES = "postgres", "PostgreSQL"
        DUCKDB = "duckdb", "DuckDB"

    type = CharField(max_length=50, choices=Types.choices, default=Types.POSTGRES, verbose_name="Type")
    connection = CharField(max_length=2048, null=True, verbose_name="Connection String")
    workspace = ForeignKey('reference.Workspace', on_delete=CASCADE, null=True, verbose_name="Workspace")

    class Meta:
        verbose_name = "Data Source"
        verbose_name_plural = "Data Sources"

    def __str__(self):
        return f"{self.type} DataSource"