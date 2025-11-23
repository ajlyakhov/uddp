from django.contrib import admin
from reference.models import Source, DataType, ProcessingStage, Consumer



@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'key')


class ProcessingStageInline(admin.TabularInline):
    model = ProcessingStage
    extra = 0




@admin.register(DataType)
class DataTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'source', 'source_code', 'consumer')
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
    list_display = ('name', 'type', 'key', )


