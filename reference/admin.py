from django.contrib import admin
from reference.models import Source, DataType, ProcessingStage, Consumer, Webhook, DataSource, Workspace, Team, TeamMember, PluginRepo, Plugin



@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'workspace')
    list_filter = ('workspace', )


class ProcessingStageInline(admin.TabularInline):
    model = ProcessingStage
    extra = 0




@admin.register(DataType)
class DataTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'source', 'source_code', 'consumer', 'workspace')
    list_filter = ('source', 'consumer', 'workspace')
    inlines = (ProcessingStageInline, )
    fieldsets = (
        ('', {
            'fields': ('name', ),
        }),
        ('Source System', {
            'fields': ('source', 'source_code', ),
        }),
        ('Consumer', {
            'fields': ('consumer', ),
        }),
    )


@admin.register(Consumer)
class ConsumerAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'key', 'webhook', 'datasource', 'workspace')
    list_filter = ('type', 'workspace')


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ('url', 'jwt_secret', 'workspace')
    list_filter = ('workspace', )


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ('type', 'connection', 'workspace')
    list_filter = ('type', 'workspace')



@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', )
    search_fields = ('name', )


class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 0


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'workspace')
    list_filter = ('workspace', )
    inlines = (TeamMemberInline, )


@admin.register(PluginRepo)
class PluginRepoAdmin(admin.ModelAdmin):
    list_display = ('name', 'url')


@admin.register(Plugin)
class PluginAdmin(admin.ModelAdmin):
    list_display = ('name', 'repo', 'file')
    list_filter = ('repo', )
