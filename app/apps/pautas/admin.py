from django.contrib import admin
from .models import Pauta


@admin.register(Pauta)
class PautaAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'rede_social',
        'status',
        'organization',
        'user',
        'created_at',
        'n8n_id'
    ]
    list_filter = [
        'status',
        'rede_social',
        'organization',
        'created_at'
    ]
    search_fields = [
        'title',
        'content',
        'user__email',
        'organization__name'
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'requested_at',
        'last_edited_at',
        'audit_history',
        'n8n_data',
        'generation_request'
    ]
    
    fieldsets = (
        ('Dados Principais', {
            'fields': ('title', 'content', 'rede_social', 'status')
        }),
        ('Relacionamentos', {
            'fields': ('organization', 'knowledge_base', 'user')
        }),
        ('Dados N8N', {
            'fields': ('n8n_id', 'n8n_data', 'generation_request'),
            'classes': ('collapse',)
        }),
        ('Auditoria', {
            'fields': (
                'created_at', 'updated_at', 'requested_by', 'requested_at',
                'last_edited_by', 'last_edited_at', 'audit_history'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'organization', 'user', 'knowledge_base'
        )
