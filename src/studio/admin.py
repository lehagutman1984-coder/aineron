from django.contrib import admin
from .models import StudioProject, StudioFile, StudioPipelineState, StudioVersion


@admin.register(StudioProject)
class StudioProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'status', 'mode', 'stars_spent', 'created_at')
    list_filter = ('status', 'mode', 'entry_mode')
    search_fields = ('name', 'user__email')


admin.site.register(StudioFile)
admin.site.register(StudioPipelineState)
admin.site.register(StudioVersion)
