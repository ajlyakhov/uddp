from django.contrib import admin
from reference.models import Source, SourceContentMap, SourceStage, Target, TargetStage



@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'key')


class SourceStageInline(admin.TabularInline):
    model = SourceStage
    extra = 0


class TargetStageInline(admin.TabularInline):
    model = TargetStage
    extra = 0




@admin.register(SourceContentMap)
class SourceContentMapAdmin(admin.ModelAdmin):
    list_display = ('name', 'source', 'source_code', 'target', 'target_code')
    inlines = (SourceStageInline, TargetStageInline)
    fieldsets = (
        ('', {
            'fields': ('name', ),
        }),
        ('Source System', {
            'fields': ('source', 'source_code', ),
        }),
        ('Target Platform', {
            'fields': ('target', 'target_code', 'modifier_module', 'link_module'),
        }),
    )


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = ('name', 'publish_api', )


